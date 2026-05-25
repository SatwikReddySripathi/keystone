"""
Action Marshall Python SDK.

Action-level release control for AI agents. Wrap the tools or functions
your agent already calls and Action Marshall runs preview, policy, approval,
canary, breaker, and signed audit before the action is released.

Quickstart:

    from action_marshall import MarshallClient, Action, ActionParams

    ks = MarshallClient(api_key="am_test_demo_key_001",
                        base_url="http://localhost:8000")

    result = ks.run(Action(
        params=ActionParams(
            query={"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}},
            changes={"state": "in_progress"},
        )
    ))
    print(result.decision_value, result.status)

Wrap an existing Python function so every call is governed:

    @ks.wrap_function(tool="servicenow",
                      action_type="update_incident",
                      connector="servicenow_sim",
                      agent_id="incident-agent")
    def update_incident(payload: dict) -> dict:
        ...

    result = update_incident({"incident_id": "INC001", "status": "resolved"})
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Optional

import requests


# ── Exceptions ─────────────────────────────────────

class MarshallError(RuntimeError):
    """Base class for SDK errors."""


class MarshallAPIError(MarshallError):
    """The Action Marshall API returned an error response."""

    def __init__(self, status_code: int, message: str):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class MarshallDenied(MarshallError):
    """The policy decided BLOCK. The wrapped function was not called."""

    def __init__(self, result: "ActionResult"):
        super().__init__(f"action denied by policy: {result.action_id}")
        self.result = result


class MarshallApprovalRequired(MarshallError):
    """The policy decided APPROVAL_REQUIRED. The wrapped function was not called."""

    def __init__(self, result: "ActionResult"):
        super().__init__(f"action requires approval: {result.action_id}")
        self.result = result


# ── Data classes for building actions ──────────────

@dataclass
class Actor:
    """Who is taking the action — usually an agent ID."""
    id: str = "agent-001"
    name: str = "Demo Agent"
    type: str = "agent"


@dataclass
class Approver:
    """Who approved an action (when an approval is replayed via the SDK)."""
    id: str = ""
    name: str = ""
    type: str = "human"


@dataclass
class Approval:
    """An approval record submitted along with an action."""
    approver: Optional[Approver] = None
    preview_hash: str = ""
    policy_version: str = ""
    channel: str = "sdk"


@dataclass
class ActionParams:
    """The connector-shaped payload for an action: which records, what changes."""
    connector: str = "servicenow_sim"
    query: dict = field(default_factory=dict)
    changes: dict = field(default_factory=dict)


@dataclass
class Action:
    """
    What the agent wants to do.

    Mirrors the backend's ``ActionInput`` model. ``workspace_id`` and
    ``connection_id`` are optional; when set they link the action to that
    workspace / connection so it appears in workspace stats, audit filters,
    and connection usage counts.
    """
    tool: str = "servicenow"
    action_type: str = "bulk_update"
    environment: str = "simulation"
    actor: Actor = field(default_factory=Actor)
    params: ActionParams = field(default_factory=ActionParams)
    idempotency_key: Optional[str] = None
    approval: Optional[Approval] = None
    workspace_id: Optional[str] = None
    connection_id: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("approval", "idempotency_key", "workspace_id", "connection_id"):
            if d.get(k) is None:
                d.pop(k, None)
        return d


# ── Result wrappers ────────────────────────────────

class ActionResult:
    """
    Structured result from ``ks.run()`` and ``ks.preview()``.

    Provides convenient properties so callers do not have to dig through
    the raw response dict.
    """

    def __init__(self, data: dict):
        self._data = data
        self.action_id: Optional[str] = data.get("action_id")
        self.status: Optional[str] = data.get("status")
        self.preview: Optional[dict] = data.get("preview")
        self.decision: Optional[dict] = data.get("decision")
        self.breaker: Optional[dict] = data.get("breaker")
        self.proof_available: bool = data.get("proof_available", False)
        self.proof_url: Optional[str] = data.get("proof_url")
        self.ui_urls: dict = data.get("ui_urls", {})

    @property
    def decision_value(self) -> str:
        """Policy decision: AUTO, CANARY, BLOCK, APPROVAL_REQUIRED, or UNKNOWN."""
        return self.decision.get("decision", "UNKNOWN") if self.decision else "UNKNOWN"

    @property
    def is_blocked(self) -> bool:
        """True if the action was stopped (blocked, contained, or awaiting approval)."""
        return self.status in ("blocked", "contained", "awaiting_approval")

    @property
    def breaker_tripped(self) -> bool:
        """True if the circuit breaker halted execution after canary."""
        return self.breaker.get("tripped", False) if self.breaker else False

    @property
    def blast_radius(self) -> int:
        """Number of records the action would affect."""
        return self.preview.get("blast_radius", 0) if self.preview else 0

    @property
    def preview_hash(self) -> Optional[str]:
        """Deterministic hash of the preview — binds approvals to a specific payload."""
        return self.preview.get("preview_hash") if self.preview else None

    @property
    def policy_version(self) -> Optional[str]:
        """Version of the policy that produced this decision."""
        return self.decision.get("policy_version") if self.decision else None

    @property
    def raw(self) -> dict:
        """The full raw API response."""
        return self._data

    def __repr__(self) -> str:
        return (
            f"ActionResult(action_id={self.action_id!r}, "
            f"status={self.status!r}, "
            f"decision={self.decision_value!r}, "
            f"breaker_tripped={self.breaker_tripped})"
        )


class PreviewResult(ActionResult):
    """
    Result from ``ks.preview()``.

    Same shape as ``ActionResult`` but never executes — only preview + policy.
    """


@dataclass
class Receipt:
    """A signed audit receipt fetched from the backend."""
    action_id: str
    receipt: dict
    signature: str
    verified: bool

    @classmethod
    def from_api(cls, data: dict) -> "Receipt":
        return cls(
            action_id=data["action_id"],
            receipt=data["receipt"],
            signature=data["signature"],
            verified=bool(data.get("verified", False)),
        )


# ── SDK Client ─────────────────────────────────────

# Decision values that mean "the wrapped function may run."
_ALLOWED_DECISIONS = ("AUTO", "CANARY")


class MarshallClient:
    """
    Action Marshall SDK client.

    Initialize with an API key, then call ``.run()``, ``.preview()``, or wrap
    existing functions / tools via ``.wrap()``, ``.wrap_function()``,
    ``.wrap_tool()``.

    Example:
        ks = MarshallClient(api_key="...", base_url="http://localhost:8000")
        result = ks.run(Action(...))
    """

    HOSTED_URL = "https://api.action-marshall.dev"

    def __init__(
        self,
        api_key: str = "",
        base_url: str = HOSTED_URL,
        timeout: float = 30.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        if api_key:
            self._session.headers["X-API-Key"] = api_key

    # ── Core lifecycle methods ─────────────────────

    def run(self, action: Action, mode: str = "enforce") -> ActionResult:
        """
        Execute an action through the full Action Marshall lifecycle: preview →
        policy → optional approval → canary → checks → breaker → signed proof.

        Args:
            action: The action to govern.
            mode: ``"enforce"`` (run it for real) or ``"observe_only"`` (preview
                and policy only — no side effects).

        Returns:
            ``ActionResult`` with status, decision, breaker state, proof URL.

        Raises:
            MarshallAPIError: backend returned a non-2xx response.
        """
        return ActionResult(self._post_run(action, mode))

    def preview(self, action: Action) -> PreviewResult:
        """
        Preview an action without executing it.

        Equivalent to ``run(action, mode="observe_only")``. Returns blast
        radius, preview hash, policy decision, and what would happen — but
        nothing is changed in the target system.
        """
        return PreviewResult(self._post_run(action, "observe_only"))

    def verify_receipt(self, action_id: str) -> Receipt:
        """
        Fetch the signed proof receipt for an action and verify its signature
        server-side. Returns a ``Receipt`` whose ``.verified`` field tells you
        whether the HMAC matches.
        """
        resp = self._session.get(
            f"{self.base_url}/v1/actions/{action_id}/proof",
            timeout=self.timeout,
        )
        self._raise_for_status(resp)
        return Receipt.from_api(resp.json())

    # ── Wrappers ────────────────────────────────────

    def wrap(
        self,
        target: Any,
        **wrap_kwargs: Any,
    ) -> Any:
        """
        Govern any callable or tool object with Action Marshall.

        Dispatches based on the target:

        - If ``target`` is a plain Python callable: returns a wrapped callable
          (see :meth:`wrap_function`).
        - Otherwise: returns a wrapped tool (see :meth:`wrap_tool`).

        ``wrap_kwargs`` are passed through to the underlying wrapper.
        """
        if callable(target) and not hasattr(target, "_run"):
            return self.wrap_function(target, **wrap_kwargs)
        return self.wrap_tool(target, **wrap_kwargs)

    def wrap_function(
        self,
        fn: Optional[Callable[..., Any]] = None,
        *,
        tool: str = "custom",
        action_type: str = "call",
        connector: str = "servicenow_sim",
        agent_id: str = "agent-001",
        agent_name: Optional[str] = None,
        mode: str = "enforce",
        return_action_marshall_result: bool = False,
        on_denied: Optional[Callable[["MarshallDenied"], Any]] = None,
        on_approval_required: Optional[Callable[["MarshallApprovalRequired"], Any]] = None,
        metadata: Optional[dict] = None,
        workspace_id: Optional[str] = None,
        connection_id: Optional[str] = None,
    ) -> Callable[..., Any]:
        """
        Wrap a plain Python function so every call is governed.

        Can be used directly (``ks.wrap_function(fn, ...)``) or as a decorator
        factory (``@ks.wrap_function(...)``).

        On each call the wrapper:

        1. Builds an ``Action`` from the call's first positional dict
           argument or from the kwargs.
        2. Calls ``ks.preview(action)`` to get the policy decision.
        3. If decision is BLOCK → raises :class:`MarshallDenied` (or invokes
           ``on_denied`` if provided). The wrapped function does **not** run.
        4. If decision is APPROVAL_REQUIRED → raises
           :class:`MarshallApprovalRequired` (or invokes
           ``on_approval_required``). The wrapped function does **not** run.
        5. Otherwise (AUTO or CANARY) → calls the wrapped function and returns
           its result. If ``return_action_marshall_result=True``, returns the
           ``ActionResult`` instead.

        Args:
            fn: The function to wrap. If omitted, returns a decorator.
            tool: Logical tool name (e.g. ``"servicenow"``).
            action_type: Logical action type (e.g. ``"update_incident"``).
            connector: Backend connector to evaluate against
                (e.g. ``"servicenow_sim"``).
            agent_id: ID of the agent making the call.
            agent_name: Optional agent display name.
            mode: ``"enforce"`` (default) or ``"observe_only"``. In observe
                mode the function is not called and only the preview is run.
            return_action_marshall_result: If True, return ``ActionResult`` instead
                of the wrapped function's return value.
            on_denied: Optional callback to call instead of raising on BLOCK.
            on_approval_required: Optional callback to call instead of
                raising on APPROVAL_REQUIRED.
            metadata: Extra metadata to attach (currently ignored by the
                backend; reserved for future use).
            workspace_id: Optional workspace binding.
            connection_id: Optional connection binding.
        """
        # Allow decorator-style usage: @ks.wrap_function(...)
        if fn is None:
            def _decorator(real_fn: Callable[..., Any]) -> Callable[..., Any]:
                return self.wrap_function(
                    real_fn,
                    tool=tool,
                    action_type=action_type,
                    connector=connector,
                    agent_id=agent_id,
                    agent_name=agent_name,
                    mode=mode,
                    return_action_marshall_result=return_action_marshall_result,
                    on_denied=on_denied,
                    on_approval_required=on_approval_required,
                    metadata=metadata,
                    workspace_id=workspace_id,
                    connection_id=connection_id,
                )
            return _decorator

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            payload = _extract_payload(args, kwargs)
            action = Action(
                tool=tool,
                action_type=action_type,
                actor=Actor(id=agent_id, name=agent_name or agent_id),
                params=ActionParams(
                    connector=connector,
                    query=payload,
                    changes=payload,
                ),
                workspace_id=workspace_id,
                connection_id=connection_id,
            )

            preview = self.preview(action)

            if preview.decision_value == "BLOCK":
                err = MarshallDenied(preview)
                if on_denied is not None:
                    return on_denied(err)
                raise err

            if preview.decision_value == "APPROVAL_REQUIRED":
                err = MarshallApprovalRequired(preview)
                if on_approval_required is not None:
                    return on_approval_required(err)
                raise err

            if preview.decision_value not in _ALLOWED_DECISIONS:
                raise MarshallError(
                    f"unexpected policy decision: {preview.decision_value!r}"
                )

            if mode == "observe_only":
                return preview if return_action_marshall_result else None

            result = fn(*args, **kwargs)
            return preview if return_action_marshall_result else result

        wrapper.__action_marshall__ = {
            "tool": tool,
            "action_type": action_type,
            "connector": connector,
            "agent_id": agent_id,
        }
        return wrapper

    def wrap_tool(self, tool_obj: Any, **wrap_kwargs: Any) -> Any:
        """
        Wrap a framework tool object (LangChain, CrewAI, AutoGen, MCP, etc.).

        The base SDK ships a generic wrapper that looks for a callable
        attribute on the tool (``_run``, ``run``, ``__call__``) and wraps it
        with :meth:`wrap_function`. Framework-specific adapters live under
        ``action_marshall.adapters.<framework>`` and handle quirks per framework.

        Args:
            tool_obj: The tool object to wrap.
            **wrap_kwargs: Passed to :meth:`wrap_function`.
        """
        for attr in ("_run", "run", "__call__"):
            target = getattr(tool_obj, attr, None)
            if callable(target):
                wrapped = self.wrap_function(target, **wrap_kwargs)
                # Best-effort in-place patch. If the tool is immutable
                # (pydantic BaseModel etc.), advise using the framework adapter.
                try:
                    setattr(tool_obj, attr, wrapped)
                    return tool_obj
                except (AttributeError, TypeError) as e:
                    raise MarshallError(
                        f"Could not wrap tool in-place (attribute {attr!r} "
                        f"is read-only). Use the matching framework adapter "
                        f"from action_marshall.adapters instead. Original error: {e}"
                    )
        raise MarshallError(
            "Tool object has no callable _run / run / __call__ attribute. "
            "Use ks.wrap_function() with a plain callable instead."
        )

    # ── Convenience accessors (kept for back-compat) ──

    def get_action(self, action_id: str) -> dict:
        """Fetch full action detail (joined view across all tables)."""
        resp = self._session.get(
            f"{self.base_url}/v1/actions/{action_id}",
            timeout=self.timeout,
        )
        self._raise_for_status(resp)
        return resp.json()

    def get_proof(self, action_id: str) -> dict:
        """Fetch the proof payload (use :meth:`verify_receipt` for structured access)."""
        resp = self._session.get(
            f"{self.base_url}/v1/actions/{action_id}/proof",
            timeout=self.timeout,
        )
        self._raise_for_status(resp)
        return resp.json()

    def list_actions(self, **filters: Any) -> list[dict]:
        """List actions with optional filters (status, tool, limit, offset)."""
        resp = self._session.get(
            f"{self.base_url}/v1/actions",
            params=filters,
            timeout=self.timeout,
        )
        self._raise_for_status(resp)
        return resp.json()

    def execute(self, action_id: str) -> ActionResult:
        """
        Convert an observed (dry-run) action into a real enforced run.

        Call after ``run(..., mode="observe_only")`` to commit it for real.
        """
        resp = self._session.post(
            f"{self.base_url}/v1/actions/{action_id}/execute-from-dry-run",
            timeout=self.timeout,
        )
        self._raise_for_status(resp)
        return ActionResult(resp.json())

    def get_policy(self) -> dict:
        """Fetch the current active policy."""
        resp = self._session.get(
            f"{self.base_url}/v1/policies/current",
            timeout=self.timeout,
        )
        self._raise_for_status(resp)
        return resp.json()

    # ── Internal helpers ───────────────────────────

    def _post_run(self, action: Action, mode: str) -> dict:
        payload = action.to_dict()
        payload["mode"] = mode
        resp = self._session.post(
            f"{self.base_url}/v1/run",
            json=payload,
            timeout=self.timeout,
        )
        self._raise_for_status(resp)
        return resp.json()

    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        if resp.ok:
            return
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise MarshallAPIError(resp.status_code, str(detail))


# ── Internal helpers ───────────────────────────────

def _extract_payload(args: tuple, kwargs: dict) -> dict:
    """
    Best-effort: derive a dict payload from a function call's arguments.

    Priority:
      1. The first positional argument if it is a dict.
      2. All keyword arguments collapsed into a dict.
      3. {} otherwise.

    This is intentionally simple. Callers with non-dict signatures should
    pass through ``wrap_function(..., metadata={...})`` (planned) or use
    ``ks.run(Action(...))`` directly.
    """
    if args and isinstance(args[0], dict):
        return dict(args[0])
    if kwargs:
        return dict(kwargs)
    return {}
