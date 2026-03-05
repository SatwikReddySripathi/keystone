"""
Approval + denial + execution routes.

Approvals are employee-based: only authorized employees can approve.
The approver enters their employee_id, we look them up in the approvers table,
verify they're authorized for this tool, and record the approval with their
full identity (name, designation, department).
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import authenticate
from app.db import get_db, add_event
from app.connectors.servicenow_sim import get_connector as get_snow
from app.engine.canary import select_canary_subset, run_post_checks
from app.engine.breaker import evaluate_breaker
from app.engine.proof import generate_proof
from app.slack import post_approval_result

router = APIRouter(prefix="/v1", tags=["approvals"])

CONNECTORS = {
    "servicenow_sim": get_snow,
}


# ── Request/Response Models ──

class ApproveRequest(BaseModel):
    employee_id: str
    channel: str = "ui"

class ApproveResponse(BaseModel):
    action_id: str
    approved: bool
    approver_name: str
    message: str

class DenyRequest(BaseModel):
    employee_id: str
    channel: str = "ui"

class DenyResponse(BaseModel):
    action_id: str
    denied: bool
    approver_name: str
    message: str


# ── Helper: look up and validate approver ──

def _get_approver(conn, employee_id: str, tool: str) -> dict:
    """Look up employee and verify they can approve for this tool."""
    row = conn.execute(
        "SELECT * FROM approvers WHERE employee_id = ? AND active = 1",
        (employee_id,)
    ).fetchone()
    if not row:
        raise HTTPException(403, f"Employee ID '{employee_id}' not found or not authorized")

    authorized = row["authorized_tools"]
    if authorized != "*" and tool not in authorized.split(","):
        raise HTTPException(
            403,
            f"{row['name']} is not authorized to approve '{tool}' actions. "
            f"Authorized for: {authorized}"
        )

    return {
        "id": row["employee_id"],
        "name": row["name"],
        "email": row["email"],
        "designation": row["designation"],
        "department": row["department"],
        "type": "human",
    }


# ── GET: list approvers (for UI dropdown) ──

@router.get("/approvers")
def list_approvers(org_id: str = Depends(authenticate)):
    """List all active approvers. Used by the UI to show who can approve."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT employee_id, name, designation, department, authorized_tools FROM approvers WHERE active = 1"
        ).fetchall()
        return [dict(r) for r in rows]


# ── POST: approve ──

@router.post("/actions/{action_id}/approve", response_model=ApproveResponse)
def approve_action(
    action_id: str,
    body: ApproveRequest,
    org_id: str = Depends(authenticate),
):
    """Approve an action. Validates employee_id against the approvers table."""
    with get_db() as conn:
        action = conn.execute(
            "SELECT * FROM actions WHERE action_id=? AND org_id=?",
            (action_id, org_id)
        ).fetchone()
        if not action:
            raise HTTPException(404, "Action not found")
        if action["status"] != "awaiting_approval":
            raise HTTPException(400, f"Action is '{action['status']}', not awaiting_approval")

        # Validate approver
        approver = _get_approver(conn, body.employee_id, action["tool"])

        # Get preview hash and policy version
        preview = conn.execute(
            "SELECT preview_hash FROM previews WHERE action_id=?", (action_id,)
        ).fetchone()
        decision = conn.execute(
            "SELECT policy_version FROM decisions WHERE action_id=?", (action_id,)
        ).fetchone()
        if not preview or not decision:
            raise HTTPException(400, "Action missing preview or decision")

        preview_hash = preview["preview_hash"]
        policy_version = decision["policy_version"]

        # Record the approval with full approver identity
        conn.execute(
            """INSERT INTO approvals
               (action_id, approver_json, preview_hash, policy_version, channel)
               VALUES (?,?,?,?,?)""",
            (action_id, json.dumps(approver), preview_hash, policy_version, body.channel)
        )

        conn.execute(
            "UPDATE actions SET status='approved', updated_at=? WHERE action_id=?",
            (datetime.utcnow().isoformat(), action_id)
        )

        add_event(conn, action_id, "approval.recorded", {
            "approver": approver["name"],
            "employee_id": approver["id"],
            "designation": approver["designation"],
            "department": approver["department"],
            "channel": body.channel,
            "preview_hash": preview_hash,
            "policy_version": policy_version,
        })

    # Notify Slack
    post_approval_result(action_id, approver["name"], True, "approved")

    return ApproveResponse(
        action_id=action_id,
        approved=True,
        approver_name=approver["name"],
        message=f"Approved by {approver['name']} ({approver['designation']}) via {body.channel}",
    )


# ── POST: deny ──

@router.post("/actions/{action_id}/deny", response_model=DenyResponse)
def deny_action(
    action_id: str,
    body: DenyRequest,
    org_id: str = Depends(authenticate),
):
    """Deny an action. Validates employee_id against the approvers table."""
    with get_db() as conn:
        action = conn.execute(
            "SELECT * FROM actions WHERE action_id=? AND org_id=?",
            (action_id, org_id)
        ).fetchone()
        if not action:
            raise HTTPException(404, "Action not found")
        if action["status"] != "awaiting_approval":
            raise HTTPException(400, f"Action is '{action['status']}', not awaiting_approval")

        # Validate approver
        approver = _get_approver(conn, body.employee_id, action["tool"])

        conn.execute(
            "UPDATE actions SET status='blocked', updated_at=? WHERE action_id=?",
            (datetime.utcnow().isoformat(), action_id)
        )

        add_event(conn, action_id, "approval.denied", {
            "approver": approver["name"],
            "employee_id": approver["id"],
            "designation": approver["designation"],
            "channel": body.channel,
        })

    # Notify Slack
    post_approval_result(action_id, approver["name"], False, "blocked")

    return DenyResponse(
        action_id=action_id,
        denied=True,
        approver_name=approver["name"],
        message=f"Denied by {approver['name']} ({approver['designation']}) via {body.channel}",
    )


# ── POST: execute (after approval) ──

@router.post("/actions/{action_id}/execute")
def execute_action(action_id: str, org_id: str = Depends(authenticate)):
    """Resume execution of an approved action."""
    with get_db() as conn:
        action = conn.execute(
            "SELECT * FROM actions WHERE action_id=? AND org_id=?",
            (action_id, org_id)
        ).fetchone()
        if not action:
            raise HTTPException(404, "Action not found")
        if action["status"] != "approved":
            raise HTTPException(400, f"Action is '{action['status']}', not approved")

        params = json.loads(action["params_json"])
        preview = conn.execute("SELECT * FROM previews WHERE action_id=?", (action_id,)).fetchone()
        decision = conn.execute("SELECT * FROM decisions WHERE action_id=?", (action_id,)).fetchone()

        blast_radius_data = json.loads(preview["blast_radius_json"])
        target_ids = blast_radius_data["target_ids"]
        flags = json.loads(preview["flags_json"])
        thresholds = json.loads(decision["thresholds_json"])
        changes = params["changes"]

        connector_name = params.get("connector", "servicenow_sim")
        connector = CONNECTORS.get(connector_name, get_snow)()

        # Canary
        canary_size = thresholds.get("canary_size", 5)
        canary_ids = select_canary_subset(action_id, target_ids, canary_size)
        add_event(conn, action_id, "canary.started", {"subset": canary_ids})
        conn.execute("UPDATE actions SET status='canary_executing', updated_at=? WHERE action_id=?",
            (datetime.utcnow().isoformat(), action_id))

        canary_results = connector.execute_update(canary_ids, changes)
        canary_error_rate = len([r for r in canary_results if not r.get("success")]) / max(len(canary_results), 1)
        conn.execute("INSERT INTO executions (action_id, phase, subset_ids_json, results_json, error_rate) VALUES (?,?,?,?,?)",
            (action_id, "canary", json.dumps(canary_ids), json.dumps(canary_results), canary_error_rate))
        add_event(conn, action_id, "canary.completed", {"count": len(canary_ids), "error_rate": canary_error_rate})

        # Checks
        all_checks = run_post_checks(action_id, canary_ids, canary_results, changes, flags, thresholds)
        for c in all_checks:
            conn.execute("INSERT INTO checks (action_id, check_name, passed, details_json) VALUES (?,?,?,?)",
                (action_id, c["check_name"], int(c["passed"]), json.dumps(c["details"])))
        add_event(conn, action_id, "checks.completed", {"results": {c["check_name"]: c["passed"] for c in all_checks}})

        # Breaker
        breaker_status = evaluate_breaker(all_checks)
        conn.execute("INSERT INTO breaker (action_id, tripped, reason, tripped_at) VALUES (?,?,?,?)",
            (action_id, int(breaker_status["tripped"]), breaker_status["reason"],
             datetime.utcnow().isoformat() if breaker_status["tripped"] else None))

        final_status = "completed"
        if breaker_status["tripped"]:
            final_status = "contained"
            conn.execute("UPDATE actions SET status='contained', updated_at=? WHERE action_id=?",
                (datetime.utcnow().isoformat(), action_id))
            add_event(conn, action_id, "breaker.tripped", {"reason": breaker_status["reason"]})
        else:
            remaining_ids = [sid for sid in target_ids if sid not in canary_ids]
            if remaining_ids:
                add_event(conn, action_id, "expand.started", {"count": len(remaining_ids)})
                conn.execute("UPDATE actions SET status='expanding', updated_at=? WHERE action_id=?",
                    (datetime.utcnow().isoformat(), action_id))
                expand_results = connector.execute_update(remaining_ids, changes)
                expand_error_rate = len([r for r in expand_results if not r.get("success")]) / max(len(expand_results), 1)
                conn.execute("INSERT INTO executions (action_id, phase, subset_ids_json, results_json, error_rate) VALUES (?,?,?,?,?)",
                    (action_id, "expand", json.dumps(remaining_ids), json.dumps(expand_results), expand_error_rate))
                add_event(conn, action_id, "expand.completed", {"count": len(remaining_ids), "error_rate": expand_error_rate})
            conn.execute("UPDATE actions SET status='completed', updated_at=? WHERE action_id=?",
                (datetime.utcnow().isoformat(), action_id))
            add_event(conn, action_id, "action.completed", {})

        # Proof
        events = []
        for r in conn.execute("SELECT type, payload_json, created_at FROM events WHERE action_id=? ORDER BY created_at", (action_id,)).fetchall():
            try: p = json.loads(r["payload_json"])
            except: p = {}
            events.append({"type": r["type"], "payload": p, "timestamp": r["created_at"]})

        approvals = []
        for r in conn.execute("SELECT * FROM approvals WHERE action_id=?", (action_id,)).fetchall():
            d = dict(r)
            try: d["approver_json"] = json.loads(d["approver_json"])
            except: pass
            approvals.append(d)

        canary_data = None
        cr = conn.execute("SELECT * FROM executions WHERE action_id=? AND phase='canary'", (action_id,)).fetchone()
        if cr:
            canary_data = dict(cr)
            try:
                canary_data["subset_ids_json"] = json.loads(canary_data["subset_ids_json"])
                canary_data["results_json"] = json.loads(canary_data["results_json"])
            except: pass

        actor = json.loads(action["actor_json"])
        proof = generate_proof(
            action_id=action_id, org_id=action["org_id"], environment=action["environment"],
            action_snapshot={"tool": action["tool"], "action_type": action["action_type"], "actor": actor, "params": params},
            preview_summary={"blast_radius": blast_radius_data["count"], "preview_hash": preview["preview_hash"], "flags": flags, "diffs": []},
            decision={"policy_id": decision["policy_id"], "policy_version": decision["policy_version"],
                       "decision": decision["decision"], "reasons": json.loads(decision["reasons_json"]), "thresholds": thresholds},
            approvals=approvals, canary=canary_data, checks=all_checks, breaker=breaker_status, events=events,
        )
        conn.execute("INSERT INTO proofs (action_id, receipt_json, signature) VALUES (?,?,?)",
            (action_id, json.dumps(proof["receipt"]), proof["signature"]))
        add_event(conn, action_id, "proof.generated", {"signature_prefix": proof["signature"][:16]})

        return {
            "action_id": action_id,
            "status": final_status,
            "breaker_tripped": breaker_status["tripped"],
            "breaker_reason": breaker_status["reason"],
            "proof_available": True,
        }