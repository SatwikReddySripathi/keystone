"""
In-memory rate limiting + account lockout.

Production deployments should back this with Redis so limits hold across
multiple workers / instances. For single-process demo and small deployments
the in-memory store is sufficient. Thread-safe.

Usage:
    from app.rate_limit import ip_limit, email_limit, lockout
    from fastapi import HTTPException

    if not ip_limit.allow(f"login:{ip}", max_requests=5, window_seconds=60):
        raise HTTPException(429, "Too many attempts — try again in a minute")

    if lockout.is_locked(email):
        raise HTTPException(429, "Account locked — try again later")
"""
import time
from collections import defaultdict, deque
from threading import Lock


class SlidingWindowLimiter:
    """
    Sliding-window rate limiter. Records request timestamps and evicts them
    when they fall outside the window. Memory grows with the number of
    distinct keys; bounded by `max_requests` per key.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, *, max_requests: int, window_seconds: int) -> bool:
        """Returns True if allowed and records the hit; False if rate-limited."""
        now = time.time()
        with self._lock:
            hits = self._hits[key]
            cutoff = now - window_seconds
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= max_requests:
                return False
            hits.append(now)
            return True

    def retry_after(self, key: str, *, window_seconds: int) -> int:
        """Seconds until the oldest hit falls out of the window."""
        with self._lock:
            hits = self._hits.get(key)
            if not hits:
                return 0
            return max(0, int(hits[0] + window_seconds - time.time()))

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


class AccountLockout:
    """
    Track failed password attempts per email and lock out after too many.
    Reset on successful login. Lockout duration is fixed.
    """

    def __init__(self) -> None:
        self._failures: dict[str, deque] = defaultdict(deque)
        self._locked_until: dict[str, float] = {}
        self._lock = Lock()

    def is_locked(self, key: str) -> bool:
        with self._lock:
            unlock = self._locked_until.get(key)
            if unlock is None:
                return False
            if time.time() >= unlock:
                self._locked_until.pop(key, None)
                return False
            return True

    def lock_remaining(self, key: str) -> int:
        with self._lock:
            unlock = self._locked_until.get(key)
            if unlock is None:
                return 0
            return max(0, int(unlock - time.time()))

    def record_failure(
        self,
        key: str,
        *,
        max_attempts: int = 5,
        count_window_seconds: int = 900,
        lockout_seconds: int = 900,
    ) -> bool:
        """
        Record a failed attempt. Returns True if this attempt triggered a lock.
        """
        now = time.time()
        with self._lock:
            fails = self._failures[key]
            cutoff = now - count_window_seconds
            while fails and fails[0] < cutoff:
                fails.popleft()
            fails.append(now)
            if len(fails) >= max_attempts:
                self._locked_until[key] = now + lockout_seconds
                fails.clear()
                return True
            return False

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)


# Module-level singletons
ip_limit = SlidingWindowLimiter()
email_limit = SlidingWindowLimiter()
lockout = AccountLockout()


def client_ip(request) -> str:
    """Extract the best-available client IP from a FastAPI Request."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return request.client.host if request.client else "unknown"
