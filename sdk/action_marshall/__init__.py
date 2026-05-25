"""
Action Marshall — action-level release control for AI agents.

Wrap the tools or functions your agent already calls and Action Marshall runs
preview, policy, approval, canary, breaker, and signed audit before the
action is released.
"""
from action_marshall.client import (
    # Client
    MarshallClient,
    # Action types
    Action,
    ActionParams,
    Actor,
    Approval,
    Approver,
    # Result types
    ActionResult,
    PreviewResult,
    Receipt,
    # Exceptions
    MarshallError,
    MarshallAPIError,
    MarshallDenied,
    MarshallApprovalRequired,
)

__all__ = [
    "MarshallClient",
    "Action",
    "ActionParams",
    "Actor",
    "Approval",
    "Approver",
    "ActionResult",
    "PreviewResult",
    "Receipt",
    "MarshallError",
    "MarshallAPIError",
    "MarshallDenied",
    "MarshallApprovalRequired",
]
__version__ = "0.1.0"
