"""Policy routes — expose current policy and compare alternate policies."""
import json
import os
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.auth import authenticate
from app.db import get_db
from app.engine.policy import load_policy, get_policy_hash, evaluate_policy

router = APIRouter(prefix="/v1", tags=["policies"])


@router.get("/system/connector-url")
def get_connector_url(org_id: str = Depends(authenticate)):
    """Return the ServiceNow base URL if SNOW_INSTANCE is configured. Used by the UI to build deep links."""
    instance = os.getenv("SNOW_INSTANCE", "").strip()
    if not instance:
        return {"servicenow_url": None}
    m = re.match(r'https?://([^\.]+)\.service-now\.com', instance)
    if m:
        instance = m.group(1)
    return {"servicenow_url": f"https://{instance}.service-now.com"}


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


class CompareRequest(BaseModel):
    action_id: str
    policy_file: str = "strict_policy.yaml"


@router.post("/policies/compare")
def compare_policies(body: CompareRequest, org_id: str = Depends(authenticate)):
    """
    Re-evaluate a previously previewed action against an alternate policy.

    Returns both the original decision and the alternate decision side by side,
    using the exact same preview data so the comparison is apples-to-apples.
    """
    with get_db() as conn:
        # Verify the action belongs to this org
        action = conn.execute(
            "SELECT action_id FROM actions WHERE action_id=? AND org_id=?",
            (body.action_id, org_id)
        ).fetchone()
        if not action:
            raise HTTPException(404, "Action not found")

        # Fetch the stored preview
        preview_row = conn.execute(
            "SELECT preview_hash, blast_radius_json, flags_json FROM previews WHERE action_id=?",
            (body.action_id,)
        ).fetchone()
        if not preview_row:
            raise HTTPException(404, "No preview found for this action")

        # Reconstruct preview dict in the format evaluate_policy expects
        blast_obj = json.loads(preview_row["blast_radius_json"] or "{}")
        flags = json.loads(preview_row["flags_json"] or "{}")
        preview_for_eval = {
            "blast_radius": blast_obj.get("count", 0),
            "flags": flags,
            "preview_hash": preview_row["preview_hash"],
        }

    # Evaluate against default policy
    default_result = evaluate_policy(preview_for_eval, policy_file="default_policy.yaml")

    # Evaluate against alternate policy
    try:
        alternate_result = evaluate_policy(preview_for_eval, policy_file=body.policy_file)
    except FileNotFoundError:
        raise HTTPException(400, f"Policy file not found: {body.policy_file}")

    return {
        "action_id": body.action_id,
        "preview_hash": preview_row["preview_hash"],
        "blast_radius": preview_for_eval["blast_radius"],
        "flags": flags,
        "default": {
            "policy_id": default_result["policy_id"],
            "version": default_result["policy_version"],
            "decision": default_result["decision"],
            "reasons": default_result["reasons"],
            "matched_rules": default_result["matched_rules"],
        },
        "alternate": {
            "policy_file": body.policy_file,
            "policy_id": alternate_result["policy_id"],
            "version": alternate_result["policy_version"],
            "decision": alternate_result["decision"],
            "reasons": alternate_result["reasons"],
            "matched_rules": alternate_result["matched_rules"],
        },
        "same_decision": default_result["decision"] == alternate_result["decision"],
    }
