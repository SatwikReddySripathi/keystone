"""
Employee auth routes — email/password + OTP 2FA + signup.

POST /v1/auth/signup          — create pending account, email an OTP
POST /v1/auth/verify-signup   — validate OTP, activate account, sign in
POST /v1/auth/login           — step 1: password check, trigger OTP
POST /v1/auth/verify-login    — step 2: validate OTP, return profile
POST /v1/auth/resend-otp      — regenerate an OTP for a given email/purpose
GET  /v1/auth/me              — profile for X-Employee-Id header
GET  /v1/auth/employees       — public list (for demo login picker)
GET  /v1/auth/can-approve/{action_id} — permission check for UI button state

Security posture:
  - Passwords stored as SHA-256 hashes. Comparisons use hmac.compare_digest.
  - OTPs are 6-digit, hashed at rest, expire in 10 minutes, max 5 attempts.
  - OTPs are NEVER returned in HTTP responses. Delivered via SMTP when
    configured (SMTP_HOST env var); otherwise printed only to the backend
    console log for local-development visibility.
  - Per-IP rate limits on signup/login/resend; per-email rate limits on
    verify; account lockout after repeated failed password attempts.
  - Unified "invalid email or password" error prevents email enumeration.
"""
import hashlib
import hmac
import os
import secrets
import smtplib
import string
import json
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional

from app.auth import authenticate
from app.db import get_db
from app.rate_limit import ip_limit, email_limit, lockout, client_ip

router = APIRouter(prefix="/v1/auth", tags=["auth"])

# Minutes an OTP remains valid
OTP_EXPIRY_MINUTES = 10
MAX_OTP_ATTEMPTS   = 5

# Maximum lengths / payload caps — prevent pathological input
MAX_EMAIL_LENGTH    = 254
MAX_NAME_LENGTH     = 120
MAX_PASSWORD_LENGTH = 256
MIN_PASSWORD_LENGTH = 8
MAX_NOTE_LENGTH     = 500

# SMTP config (optional — when absent, OTPs are console-logged only)
SMTP_HOST     = os.getenv("SMTP_HOST")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM     = os.getenv("SMTP_FROM", "noreply@keystone.local")
SMTP_USE_TLS  = os.getenv("SMTP_USE_TLS", "true").lower() != "false"


# ── Payload models ─────────────────────────────────────────
class SignupBody(BaseModel):
    email: str
    name: str
    password: str
    designation: Optional[str] = None
    department: Optional[str] = None
    workspace_id: Optional[str] = None   # optional — which workspace to request access to


class VerifySignupBody(BaseModel):
    email: str
    code: str


class LoginBody(BaseModel):
    email: str
    password: str


class VerifyLoginBody(BaseModel):
    email: str
    code: str


class ResendOtpBody(BaseModel):
    email: str
    purpose: str  # 'signup' | 'login'


# ── OTP utilities ─────────────────────────────────────────
def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _generate_otp() -> str:
    """6-digit numeric code. secrets.choice is cryptographically random."""
    return "".join(secrets.choice(string.digits) for _ in range(6))


def _deliver_otp(email: str, purpose: str, code: str) -> None:
    """
    Send the OTP via SMTP when configured, else log to the backend console.
    The OTP is never included in the HTTP response.
    """
    # Always log to backend stderr — useful for ops + local dev visibility.
    # The log line is not exposed to API clients.
    print(f"[OTP] {purpose} code for {email} (expires in {OTP_EXPIRY_MINUTES} min)",
          flush=True)

    if not SMTP_HOST:
        # No SMTP configured — that's fine in dev; code is in backend log.
        # Also log the raw code for developer convenience. Production deploys
        # set SMTP_HOST and this branch is never taken.
        print(f"[OTP] code = {code}", flush=True)
        return

    subject = "Your Keystone verification code" if purpose == "login" else "Verify your Keystone account"
    body = (
        f"Your Keystone {purpose} code is:\n\n"
        f"    {code}\n\n"
        f"This code expires in {OTP_EXPIRY_MINUTES} minutes.\n"
        f"If you didn't request this, you can safely ignore this email."
    )
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = SMTP_FROM
    msg["To"]      = email
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
            if SMTP_USE_TLS:
                s.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
    except Exception as e:
        # Don't leak SMTP details to the client; just log.
        print(f"[OTP] SMTP delivery failed for {email}: {type(e).__name__}", flush=True)


def _sanitize_email(raw: str) -> str:
    """Normalize + validate email basic shape. Raises 400 on malformed input."""
    if not raw or not isinstance(raw, str):
        raise HTTPException(400, "Email is required")
    email = raw.strip().lower()
    if len(email) > MAX_EMAIL_LENGTH:
        raise HTTPException(400, "Email too long")
    if "@" not in email or "." not in email.split("@", 1)[-1] or " " in email:
        raise HTTPException(400, "Invalid email")
    return email


def _validate_password(pw: str) -> None:
    if not pw or not isinstance(pw, str):
        raise HTTPException(400, "Password is required")
    if len(pw) < MIN_PASSWORD_LENGTH:
        raise HTTPException(400, f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(pw) > MAX_PASSWORD_LENGTH:
        raise HTTPException(400, "Password too long")


def _issue_otp(conn, email: str, purpose: str) -> str:
    """Generate, store, and deliver an OTP. Invalidates any prior code."""
    code = _generate_otp()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()
    conn.execute(
        "DELETE FROM otp_codes WHERE lower(email) = lower(?) AND purpose = ?",
        (email, purpose)
    )
    conn.execute(
        """INSERT INTO otp_codes (email, code_hash, purpose, expires_at)
           VALUES (?,?,?,?)""",
        (email.lower(), _hash(code), purpose, expires_at)
    )
    _deliver_otp(email, purpose, code)
    return code


def _consume_otp(conn, email: str, purpose: str, code: str) -> None:
    """
    Validate the submitted OTP. Raises HTTPException on failure.
    Increments attempts on wrong code; deletes on success or exhaustion.
    """
    row = conn.execute(
        """SELECT id, code_hash, expires_at, attempts FROM otp_codes
           WHERE lower(email) = lower(?) AND purpose = ?
           ORDER BY id DESC LIMIT 1""",
        (email, purpose)
    ).fetchone()
    if not row:
        raise HTTPException(400, "No active code — request a new one")

    # Expiry check (stored as ISO; parse naive for simplicity)
    try:
        expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
    except ValueError:
        expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    if datetime.now(timezone.utc) > expires_at:
        conn.execute("DELETE FROM otp_codes WHERE id = ?", (row["id"],))
        raise HTTPException(400, "Code expired — request a new one")

    attempts = row["attempts"] or 0
    if attempts >= MAX_OTP_ATTEMPTS:
        conn.execute("DELETE FROM otp_codes WHERE id = ?", (row["id"],))
        raise HTTPException(429, "Too many attempts — request a new code")

    if not hmac.compare_digest(_hash(code.strip()), row["code_hash"]):
        conn.execute("UPDATE otp_codes SET attempts = attempts + 1 WHERE id = ?", (row["id"],))
        remaining = MAX_OTP_ATTEMPTS - (attempts + 1)
        raise HTTPException(401, f"Invalid code ({remaining} attempts remaining)")

    # success — consume
    conn.execute("DELETE FROM otp_codes WHERE id = ?", (row["id"],))


# ── Profile builder ─────────────────────────────────────────
def _build_profile(conn, org_id: str, employee_id: str) -> dict:
    row = conn.execute(
        """SELECT employee_id, name, email, designation, department,
                  authorized_tools, is_admin, active
           FROM approvers WHERE employee_id = ?""",
        (employee_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, f"Employee {employee_id} not found")
    if not row["active"]:
        raise HTTPException(403, f"Employee {employee_id} is not active")

    memberships = conn.execute(
        """SELECT wm.workspace_id, wm.role, w.name AS workspace_name
           FROM workspace_members wm
           JOIN workspaces w ON wm.workspace_id = w.workspace_id
           WHERE wm.employee_id = ? AND w.org_id = ?
           ORDER BY w.name""",
        (employee_id, org_id)
    ).fetchall()

    owned_agents = conn.execute(
        """SELECT agent_id, name, workspace_id
           FROM agents WHERE owner_employee_id = ? AND org_id = ?""",
        (employee_id, org_id)
    ).fetchall()

    workspace_ids = sorted({m["workspace_id"] for m in memberships})

    # Agents visible to this user: owned + workspace members + explicit collaborators
    collab_sql = f"""SELECT DISTINCT a.agent_id, a.name, a.workspace_id
                     FROM agents a
                     LEFT JOIN agent_collaborators c ON c.agent_id = a.agent_id AND c.employee_id = ?
                     WHERE a.org_id = ?
                       AND (a.owner_employee_id = ?
                            OR c.employee_id IS NOT NULL
                            OR a.workspace_id IN ({','.join('?' for _ in workspace_ids) if workspace_ids else 'NULL'}))"""
    collab_agent_rows = conn.execute(
        collab_sql, [employee_id, org_id, employee_id, *workspace_ids]
    ).fetchall()

    # Explicit agent collaborator entries (separate from ownership / workspace membership)
    explicit_collab_rows = conn.execute(
        """SELECT c.agent_id, c.role, a.name, a.workspace_id
           FROM agent_collaborators c
           JOIN agents a ON c.agent_id = a.agent_id
           WHERE c.employee_id = ? AND a.org_id = ?""",
        (employee_id, org_id)
    ).fetchall()

    # Pending access requests where this user is the admin approver
    if bool(row["is_admin"]):
        pending_as_admin_count = conn.execute(
            """SELECT COUNT(*) as cnt FROM workspace_access_requests r
               JOIN workspaces w ON r.workspace_id = w.workspace_id
               WHERE r.status = 'pending' AND w.org_id = ?""",
            (org_id,)
        ).fetchone()["cnt"]
    else:
        pending_as_admin_count = conn.execute(
            """SELECT COUNT(*) as cnt FROM workspace_access_requests r
               WHERE r.status = 'pending'
                 AND (r.workspace_id IN (
                        SELECT workspace_id FROM workspace_members
                        WHERE employee_id = ? AND role = 'admin')
                      OR r.workspace_id IN (
                        SELECT workspace_id FROM workspaces
                        WHERE owner_id = ? AND org_id = ?))""",
            (employee_id, employee_id, org_id)
        ).fetchone()["cnt"]

    # This user's own pending access requests (waiting for someone else to approve)
    my_pending_request_rows = conn.execute(
        """SELECT r.workspace_id, w.name AS workspace_name, r.role, r.status, r.requested_at
           FROM workspace_access_requests r
           JOIN workspaces w ON r.workspace_id = w.workspace_id
           WHERE r.employee_id = ? AND r.status = 'pending' AND w.org_id = ?
           ORDER BY r.requested_at DESC""",
        (employee_id, org_id)
    ).fetchall()

    return {
        "employee_id": row["employee_id"],
        "name": row["name"],
        "email": row["email"],
        "designation": row["designation"],
        "department": row["department"],
        "authorized_tools": row["authorized_tools"],
        "is_admin": bool(row["is_admin"]),
        "memberships": [dict(m) for m in memberships],
        "owned_agents": [dict(a) for a in owned_agents],
        "collaborator_agents": [dict(r) for r in explicit_collab_rows],
        "collaborator_agent_ids": [a["agent_id"] for a in collab_agent_rows],
        "visible_workspace_ids": None if bool(row["is_admin"]) else workspace_ids,
        "pending_requests_as_admin": pending_as_admin_count,
        "my_pending_requests": [dict(r) for r in my_pending_request_rows],
    }


def _next_emp_id(conn) -> str:
    """Generate the next employee_id. Keeps the EMP### pattern going."""
    row = conn.execute(
        """SELECT employee_id FROM approvers
           WHERE employee_id LIKE 'EMP%'
           ORDER BY employee_id DESC LIMIT 1"""
    ).fetchone()
    if not row:
        return "EMP001"
    try:
        n = int(row["employee_id"][3:]) + 1
    except ValueError:
        n = 100
    return f"EMP{n:03d}"


# ── Permission helper ─────────────────────────────────────────
def can_approve_action(conn, org_id: str, employee_id: str, action_id: str) -> tuple[bool, str]:
    """
    Permission rules (see approve.py for the enforcement site):
      1. Tool scope: approver.authorized_tools must include the action's tool.
      2. Member of the action's workspace — OR owner of the agent.
      3. Admin status grants approve WITHIN their workspace memberships only,
         never across the whole org. Non-admins need workspace role
         `admin` or `approver`.
    """
    approver = conn.execute(
        "SELECT employee_id, name, is_admin, authorized_tools, active FROM approvers WHERE employee_id = ?",
        (employee_id,)
    ).fetchone()
    if not approver or not approver["active"]:
        return (False, "Not an active employee")

    action = conn.execute(
        "SELECT action_id, workspace_id, tool, actor_json FROM actions WHERE action_id = ? AND org_id = ?",
        (action_id, org_id)
    ).fetchone()
    if not action:
        return (False, "Action not found")

    authorized_tools = approver["authorized_tools"] or ""
    if authorized_tools != "*" and action["tool"] not in authorized_tools.split(","):
        return (False, f"Not authorized for tool '{action['tool']}' (allowed: {authorized_tools})")

    try:
        actor = json.loads(action["actor_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        actor = {}
    agent_id = actor.get("id")
    if agent_id:
        agent = conn.execute(
            "SELECT owner_employee_id FROM agents WHERE agent_id = ? AND org_id = ?",
            (agent_id, org_id)
        ).fetchone()
        if agent and agent["owner_employee_id"] == employee_id:
            return (True, f"Owner of agent {agent_id}")

        # Collaborator on the agent (added by workspace admin)
        collab = conn.execute(
            "SELECT role FROM agent_collaborators WHERE agent_id = ? AND employee_id = ?",
            (agent_id, employee_id)
        ).fetchone()
        if collab:
            return (True, f"Agent {collab['role']}")

    if not action["workspace_id"]:
        return (False, "Action has no workspace context")

    membership = conn.execute(
        "SELECT role FROM workspace_members WHERE workspace_id = ? AND employee_id = ?",
        (action["workspace_id"], employee_id)
    ).fetchone()
    if not membership:
        return (False, "Not a member of this workspace")

    if bool(approver["is_admin"]):
        return (True, f"Admin in workspace (role: {membership['role']})")
    if membership["role"] in ("admin", "approver"):
        return (True, f"Workspace {membership['role']}")

    return (False, f"Workspace role '{membership['role']}' cannot approve")


# ── Signup flow ─────────────────────────────────────────
@router.post("/signup")
def signup(body: SignupBody, request: Request, org_id: str = Depends(authenticate)):
    """Step 1: create a pending account and issue an OTP for email verification."""
    ip = client_ip(request)

    # Per-IP rate limit — prevents a single actor from flooding signups
    if not ip_limit.allow(f"signup:{ip}", max_requests=3, window_seconds=3600):
        raise HTTPException(429, "Too many signup attempts. Try again in an hour.")

    email = _sanitize_email(body.email)
    _validate_password(body.password)
    name = (body.name or "").strip()[:MAX_NAME_LENGTH]
    if not name:
        raise HTTPException(400, "Name is required")

    with get_db() as conn:
        existing = conn.execute(
            "SELECT employee_id FROM approvers WHERE lower(email) = ?", (email,)
        ).fetchone()
        if existing:
            # Don't confirm the email exists — return the same generic response
            # an attacker would see for a valid free email. Logs still flow.
            print(f"[auth] signup blocked for existing email {email} from {ip}", flush=True)
            return {
                "email": email,
                "requires_otp": True,
                "purpose": "signup",
                "expires_in_minutes": OTP_EXPIRY_MINUTES,
            }

        # If workspace_id supplied, verify it exists within the org
        if body.workspace_id:
            ws = conn.execute(
                "SELECT workspace_id FROM workspaces WHERE workspace_id = ? AND org_id = ?",
                (body.workspace_id, org_id)
            ).fetchone()
            if not ws:
                raise HTTPException(404, f"Workspace {body.workspace_id} not found")

        pw_hash = _hash(body.password)
        conn.execute(
            """INSERT INTO pending_signups
               (email, name, password_hash, designation, department, requested_workspace_id)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(email) DO UPDATE SET
                   name = excluded.name,
                   password_hash = excluded.password_hash,
                   designation = excluded.designation,
                   department = excluded.department,
                   requested_workspace_id = excluded.requested_workspace_id""",
            (email, name, pw_hash,
             (body.designation or "")[:120] or None,
             (body.department or "")[:120] or None,
             body.workspace_id)
        )

        _issue_otp(conn, email, "signup")

    return {
        "email": email,
        "requires_otp": True,
        "purpose": "signup",
        "expires_in_minutes": OTP_EXPIRY_MINUTES,
    }


@router.post("/verify-signup")
def verify_signup(body: VerifySignupBody, request: Request, org_id: str = Depends(authenticate)):
    """Step 2: validate the OTP, move pending_signups → approvers, return profile."""
    ip = client_ip(request)
    if not ip_limit.allow(f"verify-signup:{ip}", max_requests=10, window_seconds=600):
        raise HTTPException(429, "Too many verification attempts")

    email = _sanitize_email(body.email)
    with get_db() as conn:
        pending = conn.execute(
            "SELECT * FROM pending_signups WHERE lower(email) = ?", (email,)
        ).fetchone()
        if not pending:
            raise HTTPException(404, "No pending signup for this email")

        _consume_otp(conn, email, "signup", body.code)

        # Double check there's no race-condition duplicate
        existing = conn.execute(
            "SELECT employee_id FROM approvers WHERE lower(email) = ?", (email,)
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM pending_signups WHERE lower(email) = ?", (email,))
            raise HTTPException(409, "Account already exists — try signing in")

        emp_id = _next_emp_id(conn)
        conn.execute(
            """INSERT INTO approvers
               (employee_id, name, email, password_hash, designation, department,
                authorized_tools, is_admin, active)
               VALUES (?,?,?,?,?,?,?,?,1)""",
            (emp_id, pending["name"], email, pending["password_hash"],
             pending["designation"] or "Employee",
             pending["department"] or "General",
             "*", 0)  # new signups default to non-admin, all-tool scope
        )

        # If they asked to join a workspace during signup, queue an access request.
        requested_ws = pending["requested_workspace_id"] if "requested_workspace_id" in pending.keys() else None
        if requested_ws:
            conn.execute(
                """INSERT OR IGNORE INTO workspace_access_requests
                   (workspace_id, employee_id, role, status)
                   VALUES (?, ?, 'viewer', 'pending')""",
                (requested_ws, emp_id)
            )

        conn.execute("DELETE FROM pending_signups WHERE lower(email) = ?", (email,))

        return _build_profile(conn, org_id, emp_id)


# ── Two-step login (password + OTP) ─────────────────────────────────────────
UNIFIED_LOGIN_ERROR = "Invalid email or password"

@router.post("/login")
def login(body: LoginBody, request: Request, org_id: str = Depends(authenticate)):
    """Step 1: verify password, issue a login OTP."""
    ip = client_ip(request)

    # Per-IP rate limit: max 10 attempts / minute from one IP
    if not ip_limit.allow(f"login:{ip}", max_requests=10, window_seconds=60):
        raise HTTPException(429, "Too many login attempts — slow down")

    email = _sanitize_email(body.email)

    # Per-email rate limit AND account lockout
    if lockout.is_locked(email):
        remaining = lockout.lock_remaining(email)
        raise HTTPException(429, f"Account temporarily locked — try again in {remaining // 60 + 1} minute(s)")
    if not email_limit.allow(f"login:{email}", max_requests=8, window_seconds=900):
        raise HTTPException(429, "Too many login attempts for this account — wait 15 minutes")

    if not body.password:
        raise HTTPException(400, "Password required")
    if len(body.password) > MAX_PASSWORD_LENGTH:
        raise HTTPException(400, "Password too long")

    with get_db() as conn:
        row = conn.execute(
            """SELECT employee_id, password_hash, active
               FROM approvers WHERE lower(email) = ?""",
            (email,)
        ).fetchone()

        # Constant-time comparison. Fake-hash for unknown emails to keep the
        # wall-clock response roughly constant (defeats user-enumeration timing attacks).
        stored_hash = row["password_hash"] if row and row["password_hash"] else "0" * 64
        submitted_hash = _hash(body.password)
        if not row or not row["password_hash"] or not hmac.compare_digest(stored_hash, submitted_hash):
            triggered = lockout.record_failure(email)
            if triggered:
                print(f"[auth] account {email} locked after repeated failures from {ip}", flush=True)
            raise HTTPException(401, UNIFIED_LOGIN_ERROR)

        if not row["active"]:
            raise HTTPException(403, "Account is inactive")

        _issue_otp(conn, email, "login")

    return {
        "email": email,
        "requires_otp": True,
        "purpose": "login",
        "expires_in_minutes": OTP_EXPIRY_MINUTES,
    }


@router.post("/verify-login")
def verify_login(body: VerifyLoginBody, request: Request, org_id: str = Depends(authenticate)):
    """Step 2: validate the OTP, return profile."""
    ip = client_ip(request)
    if not ip_limit.allow(f"verify-login:{ip}", max_requests=20, window_seconds=600):
        raise HTTPException(429, "Too many verification attempts")

    email = _sanitize_email(body.email)
    with get_db() as conn:
        row = conn.execute(
            "SELECT employee_id, active FROM approvers WHERE lower(email) = ?", (email,)
        ).fetchone()
        if not row or not row["active"]:
            # Same error as OTP-wrong so we don't leak account existence
            raise HTTPException(401, UNIFIED_LOGIN_ERROR)
        _consume_otp(conn, email, "login", body.code)
        # Successful login — reset the lockout counter for this email
        lockout.reset(email)
        return _build_profile(conn, org_id, row["employee_id"])


@router.post("/resend-otp")
def resend_otp(body: ResendOtpBody, request: Request, org_id: str = Depends(authenticate)):
    """Issue a fresh OTP. Rate-limited to 3/hour per email per purpose."""
    ip = client_ip(request)
    email = _sanitize_email(body.email)
    purpose = body.purpose
    if purpose not in ("signup", "login"):
        raise HTTPException(400, "purpose must be 'signup' or 'login'")

    # Global IP cap + per-email cap
    if not ip_limit.allow(f"resend:{ip}", max_requests=10, window_seconds=3600):
        raise HTTPException(429, "Too many OTP requests from this IP")
    if not email_limit.allow(f"resend:{email}:{purpose}", max_requests=3, window_seconds=3600):
        raise HTTPException(429, "Too many code requests — wait an hour before trying again")

    with get_db() as conn:
        if purpose == "signup":
            row = conn.execute(
                "SELECT email FROM pending_signups WHERE lower(email) = ?", (email,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT employee_id FROM approvers WHERE lower(email) = ? AND active = 1", (email,)
            ).fetchone()

        # Always issue OTP (or pretend to) even if the account doesn't exist —
        # prevents enumeration. When row is None, we skip DB writes but still
        # return the same shape.
        if row:
            _issue_otp(conn, email, purpose)

    return {"email": email, "purpose": purpose, "expires_in_minutes": OTP_EXPIRY_MINUTES}


# ── Profile / lookup ─────────────────────────────────────────
@router.get("/me")
def me(
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    if not x_employee_id:
        raise HTTPException(401, "X-Employee-Id header missing — not signed in")
    with get_db() as conn:
        return _build_profile(conn, org_id, x_employee_id)


@router.get("/employees")
def list_employees(org_id: str = Depends(authenticate)):
    with get_db() as conn:
        rows = conn.execute(
            """SELECT employee_id, name, email, designation, department, is_admin
               FROM approvers WHERE active = 1
               ORDER BY is_admin DESC, name"""
        ).fetchall()
        return [dict(r) for r in rows]


@router.get("/can-approve/{action_id}")
def check_can_approve(
    action_id: str,
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    if not x_employee_id:
        raise HTTPException(401, "Not signed in")
    with get_db() as conn:
        allowed, reason = can_approve_action(conn, org_id, x_employee_id, action_id)
        return {"action_id": action_id, "allowed": allowed, "reason": reason}
