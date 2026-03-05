"""
Pydantic models — the API contract.

These define exactly what the SDK sends and what the backend returns.
Pydantic validates everything automatically — if a field is missing
or the wrong type, the API returns a clear 422 error.

The Action Object is the core concept:
  "An agent wants to do [action_type] on [tool] with [params],
   proposed by [actor] in [environment]"
"""
from pydantic import BaseModel, Field
from typing import Optional
import uuid


class Actor(BaseModel):
    """Who is proposing this action? An agent, a service, a human."""
    id: str = "agent-001"
    name: str = "Demo Agent"
    type: str = "agent"  # agent | human | service


class Approver(BaseModel):
    """Who approved (or will approve) the action."""
    id: str
    name: str
    type: str = "human"


class Approval(BaseModel):
    """
    An approval binding. This is the critical piece:
    - preview_hash: the approval is for THIS EXACT preview
    - policy_version: the approval was made under THIS policy
    If either changes, the approval is invalid.
    """
    approver: Approver
    preview_hash: str
    policy_version: str
    channel: str = "sdk"  # sdk | slack | ui


class ActionParams(BaseModel):
    """What the action will do — connector + query + changes."""
    connector: str = "servicenow_sim"
    query: dict = Field(default_factory=dict)
    changes: dict = Field(default_factory=dict)


class ActionInput(BaseModel):
    """
    The full Action Object — everything needed to govern an action.

    This is what the SDK sends to POST /v1/run.
    Maps directly to checklist item B (Action intake → normalized Action Object).
    """
    tool: str = "servicenow"
    action_type: str = "bulk_update"
    environment: str = "simulation"
    actor: Actor = Field(default_factory=Actor)
    params: ActionParams = Field(default_factory=ActionParams)
    idempotency_key: Optional[str] = None
    approval: Optional[Approval] = None
    mode: str = "enforce"  # enforce | observe_only

    def generate_action_id(self) -> str:
        return f"act_{uuid.uuid4().hex[:16]}"


class RunResponse(BaseModel):
    """
    What POST /v1/run returns.
    Gives the caller everything they need: status, decision, breaker, proof URL.
    """
    action_id: str
    status: str
    preview: Optional[dict] = None
    decision: Optional[dict] = None
    breaker: Optional[dict] = None
    proof_available: bool = False
    proof_url: Optional[str] = None
    ui_urls: dict = Field(default_factory=dict)


#python -c "from app.models import ActionInput, RunResponse; print('Models OK'); a = ActionInput(); print(f'Default action: tool={a.tool}, type={a.action_type}, mode={a.mode}')"
#above is comment to check this file