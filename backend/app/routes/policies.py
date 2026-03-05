"""Policy route — exposes current policy for inspection."""
from fastapi import APIRouter, Depends
from app.auth import authenticate
from app.engine.policy import load_policy, get_policy_hash

router = APIRouter(prefix="/v1", tags=["policies"])


@router.get("/policies/current")
def get_current_policy(org_id: str = Depends(authenticate)):
    """Return the current policy YAML as JSON, with version and hash."""
    policy = load_policy()
    return {
        "policy_id": policy["policy_id"],
        "version": policy["version"],
        "hash": get_policy_hash(policy),
        "policy": policy,
    }