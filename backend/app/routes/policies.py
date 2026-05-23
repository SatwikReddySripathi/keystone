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


# ── GET /v1/policies ───────────────────────────────────────────
@router.get("/policies")
def list_policies(org_id: str = Depends(authenticate)):
    """
    Return every registered policy along with the workspaces and agents
    bound to it. Powers the /policies UI.
    """
    with get_db() as conn:
        policies = conn.execute(
            """SELECT policy_id, name, version, source_file, hash,
                      content_json, is_default, description, created_at, updated_at
               FROM policies WHERE org_id = ?
               ORDER BY is_default DESC, name""",
            (org_id,)
        ).fetchall()

        result = []
        for p in policies:
            content = {}
            try:
                content = json.loads(p["content_json"] or "{}")
            except (json.JSONDecodeError, TypeError):
                pass
            rules = content.get("rules", [])
            thresholds = content.get("thresholds", {})

            bound_workspaces = conn.execute(
                """SELECT workspace_id, name, risk_posture
                   FROM workspaces WHERE org_id = ? AND policy_id = ?
                   ORDER BY name""",
                (org_id, p["policy_id"])
            ).fetchall()

            # Explicit agent overrides (agents.policy_id = this policy)
            direct_agents = conn.execute(
                """SELECT a.agent_id, a.name, a.workspace_id, a.status,
                          w.name AS workspace_name, 'override' AS binding_type
                   FROM agents a
                   LEFT JOIN workspaces w ON a.workspace_id = w.workspace_id
                   WHERE a.org_id = ? AND a.policy_id = ?
                   ORDER BY a.name""",
                (org_id, p["policy_id"])
            ).fetchall()

            # Agents that inherit this policy because their workspace is bound
            # AND they don't have an agent-level override of their own.
            inherited_agents = conn.execute(
                """SELECT a.agent_id, a.name, a.workspace_id, a.status,
                          w.name AS workspace_name, 'inherited' AS binding_type
                   FROM agents a
                   JOIN workspaces w ON a.workspace_id = w.workspace_id
                   WHERE a.org_id = ?
                     AND w.policy_id = ?
                     AND (a.policy_id IS NULL OR a.policy_id = '')
                   ORDER BY a.name""",
                (org_id, p["policy_id"])
            ).fetchall()

            all_agents = [dict(a) for a in direct_agents] + [dict(a) for a in inherited_agents]

            # Count actions that have actually been evaluated against this policy
            action_count = conn.execute(
                """SELECT COUNT(*) as cnt FROM decisions d
                   JOIN actions a ON d.action_id = a.action_id
                   WHERE a.org_id = ? AND d.policy_id = ?""",
                (org_id, content.get("policy_id") or p["policy_id"])
            ).fetchone()["cnt"]

            result.append({
                "policy_id": p["policy_id"],
                "name": p["name"],
                "version": p["version"],
                "source_file": p["source_file"],
                "hash": p["hash"],
                "is_default": bool(p["is_default"]),
                "description": p["description"],
                "rule_count": len(rules),
                "thresholds": thresholds,
                "bound_workspaces": [dict(w) for w in bound_workspaces],
                "bound_agents": all_agents,
                "direct_agent_count": len(direct_agents),
                "inherited_agent_count": len(inherited_agents),
                "action_count": action_count,
                "updated_at": p["updated_at"],
            })

        return result


# ── GET /v1/policies/{policy_id} ───────────────────────────────
@router.get("/policies/{policy_id}")
def get_policy_detail(policy_id: str, org_id: str = Depends(authenticate)):
    """Full detail view of one policy: rules, thresholds, bindings."""
    with get_db() as conn:
        p = conn.execute(
            """SELECT * FROM policies WHERE policy_id = ? AND org_id = ?""",
            (policy_id, org_id)
        ).fetchone()
        if not p:
            raise HTTPException(404, "Policy not found")

        content = {}
        try:
            content = json.loads(p["content_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            pass

        bound_workspaces = conn.execute(
            """SELECT workspace_id, name, risk_posture
               FROM workspaces WHERE org_id = ? AND policy_id = ?
               ORDER BY name""",
            (org_id, policy_id)
        ).fetchall()

        bound_agents = conn.execute(
            """SELECT a.agent_id, a.name, a.workspace_id, a.status,
                      w.name AS workspace_name
               FROM agents a
               LEFT JOIN workspaces w ON a.workspace_id = w.workspace_id
               WHERE a.org_id = ? AND a.policy_id = ?
               ORDER BY a.name""",
            (org_id, policy_id)
        ).fetchall()

        return {
            "policy_id": p["policy_id"],
            "name": p["name"],
            "version": p["version"],
            "source_file": p["source_file"],
            "hash": p["hash"],
            "is_default": bool(p["is_default"]),
            "description": p["description"],
            "rules": content.get("rules", []),
            "thresholds": content.get("thresholds", {}),
            "bound_workspaces": [dict(w) for w in bound_workspaces],
            "bound_agents": [dict(a) for a in bound_agents],
            "updated_at": p["updated_at"],
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
