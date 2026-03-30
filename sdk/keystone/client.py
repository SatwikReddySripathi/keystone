"""
Keystone Python SDK — drop-in transaction governance.

Usage:
    from keystone import Keystone, Action, ActionParams

    ks = Keystone(api_key="ks_test_demo_key_001")
    result = ks.run(Action(
        params=ActionParams(
            query={"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}},
            changes={"state": "in_progress"},
        )
    ))
    print(result.status, result.decision_value, result.breaker_tripped)
"""
import requests
from dataclasses import dataclass, field, asdict
from typing import Optional


# ── Data classes for building actions ──────────────

@dataclass
class Actor:
    id: str = "agent-001"
    name: str = "Demo Agent"
    type: str = "agent"


@dataclass
class Approver:
    id: str = ""
    name: str = ""
    type: str = "human"


@dataclass
class Approval:
    approver: Approver = None
    preview_hash: str = ""
    policy_version: str = ""
    channel: str = "sdk"


@dataclass
class ActionParams:
    connector: str = "servicenow_sim"
    query: dict = field(default_factory=dict)
    changes: dict = field(default_factory=dict)


@dataclass
class Action:
    """
    The Action Object — what the agent wants to do.
    Mirrors the backend's ActionInput model exactly.
    """
    tool: str = "servicenow"
    action_type: str = "bulk_update"
    environment: str = "simulation"
    actor: Actor = field(default_factory=Actor)
    params: ActionParams = field(default_factory=ActionParams)
    idempotency_key: Optional[str] = None
    approval: Optional[Approval] = None

    def to_dict(self):
        d = asdict(self)
        if d["approval"] is None:
            del d["approval"]
        if d["idempotency_key"] is None:
            del d["idempotency_key"]
        return d


# ── Result wrapper ─────────────────────────────────

class KeystoneResult:
    """
    Structured result from ks.run().
    Provides convenient properties so callers don't dig through raw dicts.
    """
    def __init__(self, data: dict):
        self._data = data
        self.action_id = data.get("action_id")
        self.status = data.get("status")
        self.preview = data.get("preview")
        self.decision = data.get("decision")
        self.breaker = data.get("breaker")
        self.proof_available = data.get("proof_available", False)
        self.proof_url = data.get("proof_url")
        self.ui_urls = data.get("ui_urls", {})

    @property
    def decision_value(self) -> str:
        """The policy decision: AUTO, CANARY, BLOCK, APPROVAL_REQUIRED."""
        return self.decision.get("decision", "UNKNOWN") if self.decision else "UNKNOWN"

    @property
    def is_blocked(self) -> bool:
        """True if the action was stopped (blocked, contained, or awaiting approval)."""
        return self.status in ("blocked", "contained", "awaiting_approval")

    @property
    def breaker_tripped(self) -> bool:
        """True if the circuit breaker halted execution."""
        return self.breaker.get("tripped", False) if self.breaker else False

    @property
    def blast_radius(self) -> int:
        """Number of records that would be affected."""
        return self.preview.get("blast_radius", 0) if self.preview else 0

    def __repr__(self):
        return (
            f"KeystoneResult(action_id={self.action_id!r}, "
            f"status={self.status!r}, "
            f"decision={self.decision_value!r}, "
            f"breaker_tripped={self.breaker_tripped})"
        )


# ── SDK Client ─────────────────────────────────────

class Keystone:
    """
    Keystone SDK client.

    Initialize with your API key, then call .run() to govern any action.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._session = requests.Session()
        self._session.headers["X-API-Key"] = api_key

    def run(self, action: Action, mode: str = "enforce") -> KeystoneResult:
        """
        Execute an action through Keystone governance.

        Args:
            action: The Action object describing what to do
            mode: "enforce" (actually execute) or "observe_only" (preview + decision only)

        Returns:
            KeystoneResult with status, decision, breaker state, proof URL, etc.
        """
        payload = action.to_dict()
        payload["mode"] = mode
        resp = self._session.post(f"{self.base_url}/v1/run", json=payload)
        if not resp.ok:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise RuntimeError(f"HTTP {resp.status_code}: {detail}")
        return KeystoneResult(resp.json())

    def get_action(self, action_id: str) -> dict:
        """Fetch full action detail (joined view across all tables)."""
        resp = self._session.get(f"{self.base_url}/v1/actions/{action_id}")
        resp.raise_for_status()
        return resp.json()

    def get_proof(self, action_id: str) -> dict:
        """Fetch the signed proof receipt for an action."""
        resp = self._session.get(f"{self.base_url}/v1/actions/{action_id}/proof")
        resp.raise_for_status()
        return resp.json()

    def list_actions(self, **filters) -> list[dict]:
        """List actions with optional filters (status, tool, etc.)."""
        resp = self._session.get(f"{self.base_url}/v1/actions", params=filters)
        resp.raise_for_status()
        return resp.json()

    def get_policy(self) -> dict:
        """Fetch the current active policy."""
        resp = self._session.get(f"{self.base_url}/v1/policies/current")
        resp.raise_for_status()
        return resp.json()