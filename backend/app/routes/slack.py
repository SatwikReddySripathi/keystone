"""
Slack interaction handler.

When someone clicks Approve or Deny in Slack, Slack sends a POST
to /v1/slack/interact with the button payload. We parse it,
record the approval, and trigger execution.

Slack sends the payload as application/x-www-form-urlencoded with
a 'payload' field containing JSON.
"""
import json
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.db import get_db, add_event
from app.slack import post_approval_result
from app.connectors.servicenow_sim import get_connector as get_snow
from app.engine.canary import select_canary_subset, run_post_checks
from app.engine.breaker import evaluate_breaker
from app.engine.proof import generate_proof

router = APIRouter(prefix="/v1", tags=["slack"])

import requests as http_requests

CONNECTORS = {
    "servicenow_sim": get_snow,
}


def _update_slack_message(response_url: str, text: str):
    """Replace the original Slack message (removes buttons)."""
    if not response_url:
        return
    try:
        http_requests.post(response_url, json={
            "replace_original": "true",
            "text": text,
        }, timeout=5)
    except Exception as e:
        print(f"Failed to update Slack message: {e}")


@router.post("/slack/interact")
async def slack_interact(request: Request):
    """Handle Slack interactive message callbacks."""
    form = await request.form()
    raw_payload = form.get("payload", "{}")
    payload = json.loads(raw_payload)

    # response_url lets us UPDATE the original Slack message (remove buttons)
    response_url = payload.get("response_url", "")

    user = payload.get("user", {})
    approver_id = user.get("id", "unknown")
    approver_name = user.get("real_name", user.get("username", "Unknown"))

    actions = payload.get("actions", [])
    if not actions:
        return JSONResponse({"text": "No action received."})

    action = actions[0]
    action_id_slack = action.get("action_id", "")
    value = json.loads(action.get("value", "{}"))
    keystone_action_id = value.get("action_id", "")

    if not keystone_action_id:
        return JSONResponse({"text": "Missing action ID."})

    if action_id_slack == "keystone_approve":
        return _handle_approve(keystone_action_id, approver_id, approver_name, value, response_url)
    elif action_id_slack == "keystone_deny":
        return _handle_deny(keystone_action_id, approver_id, approver_name, response_url)
    elif action_id_slack == "keystone_view":
        return JSONResponse({"text": "Opening details..."})

    return JSONResponse({"text": "Unknown action."})


def _handle_approve(action_id: str, approver_id: str, approver_name: str, value: dict, response_url: str = ""):
    """Record approval and execute the action."""
    with get_db() as conn:
        action = conn.execute(
            "SELECT * FROM actions WHERE action_id=?", (action_id,)
        ).fetchone()

        if not action:
            return JSONResponse({
                "response_type": "ephemeral",
                "replace_original": True,
                "text": f":warning: Action `{action_id}` not found.",
            })

        if action["status"] != "awaiting_approval":
            msg = f":information_source: Action `{action_id}` is already `{action['status']}`. No further action needed."
            _update_slack_message(response_url, msg)
            return JSONResponse({
                "response_type": "ephemeral",
                "replace_original": True,
                "text": msg,
            })

        # Get preview and decision data
        preview = conn.execute(
            "SELECT * FROM previews WHERE action_id=?", (action_id,)
        ).fetchone()
        decision = conn.execute(
            "SELECT * FROM decisions WHERE action_id=?", (action_id,)
        ).fetchone()

        preview_hash = preview["preview_hash"]
        policy_version = decision["policy_version"]

        # Record approval — only store what Slack actually gives us
        approver_json = json.dumps({
            "id": approver_id,
            "name": approver_name,
            "type": "human",
        })
        conn.execute(
            """INSERT INTO approvals
               (action_id, approver_json, preview_hash, policy_version, channel)
               VALUES (?,?,?,?,?)""",
            (action_id, approver_json, preview_hash, policy_version, "slack")
        )
        conn.execute(
            "UPDATE actions SET status='approved', updated_at=? WHERE action_id=?",
            (datetime.utcnow().isoformat(), action_id)
        )
        add_event(conn, action_id, "approval.recorded", {
            "approver": approver_name,
            "approver_id": approver_id,
            "channel": "slack",
            "preview_hash": preview_hash,
        })

        # ── Execute: canary → checks → breaker → expand → proof ──
        params = json.loads(action["params_json"])
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
        conn.execute(
            "UPDATE actions SET status='canary_executing', updated_at=? WHERE action_id=?",
            (datetime.utcnow().isoformat(), action_id)
        )

        canary_results = connector.execute_update(canary_ids, changes)
        canary_error_rate = len([r for r in canary_results if not r.get("success")]) / max(len(canary_results), 1)
        conn.execute(
            """INSERT INTO executions (action_id, phase, subset_ids_json, results_json, error_rate)
               VALUES (?,?,?,?,?)""",
            (action_id, "canary", json.dumps(canary_ids), json.dumps(canary_results), canary_error_rate)
        )
        add_event(conn, action_id, "canary.completed", {
            "count": len(canary_ids), "error_rate": canary_error_rate,
        })

        # Checks
        all_checks = run_post_checks(action_id, canary_ids, canary_results, changes, flags, thresholds)
        for c in all_checks:
            conn.execute(
                "INSERT INTO checks (action_id, check_name, passed, details_json) VALUES (?,?,?,?)",
                (action_id, c["check_name"], int(c["passed"]), json.dumps(c["details"]))
            )
        add_event(conn, action_id, "checks.completed", {
            "results": {c["check_name"]: c["passed"] for c in all_checks}
        })

        # Breaker
        breaker_status = evaluate_breaker(all_checks)
        conn.execute(
            "INSERT INTO breaker (action_id, tripped, reason, tripped_at) VALUES (?,?,?,?)",
            (action_id, int(breaker_status["tripped"]), breaker_status["reason"],
             datetime.utcnow().isoformat() if breaker_status["tripped"] else None)
        )

        final_status = "completed"
        if breaker_status["tripped"]:
            final_status = "contained"
            conn.execute(
                "UPDATE actions SET status='contained', updated_at=? WHERE action_id=?",
                (datetime.utcnow().isoformat(), action_id)
            )
            add_event(conn, action_id, "breaker.tripped", {"reason": breaker_status["reason"]})
        else:
            # Expand
            remaining_ids = [sid for sid in target_ids if sid not in canary_ids]
            if remaining_ids:
                add_event(conn, action_id, "expand.started", {"count": len(remaining_ids)})
                conn.execute(
                    "UPDATE actions SET status='expanding', updated_at=? WHERE action_id=?",
                    (datetime.utcnow().isoformat(), action_id)
                )
                expand_results = connector.execute_update(remaining_ids, changes)
                expand_error_rate = len([r for r in expand_results if not r.get("success")]) / max(len(expand_results), 1)
                conn.execute(
                    """INSERT INTO executions (action_id, phase, subset_ids_json, results_json, error_rate)
                       VALUES (?,?,?,?,?)""",
                    (action_id, "expand", json.dumps(remaining_ids), json.dumps(expand_results), expand_error_rate)
                )
                add_event(conn, action_id, "expand.completed", {"count": len(remaining_ids), "error_rate": expand_error_rate})

            conn.execute(
                "UPDATE actions SET status='completed', updated_at=? WHERE action_id=?",
                (datetime.utcnow().isoformat(), action_id)
            )
            add_event(conn, action_id, "action.completed", {})

        # Proof
        events = []
        for r in conn.execute(
            "SELECT type, payload_json, created_at FROM events WHERE action_id=? ORDER BY created_at",
            (action_id,)
        ).fetchall():
            try:
                p = json.loads(r["payload_json"])
            except:
                p = {}
            events.append({"type": r["type"], "payload": p, "timestamp": r["created_at"]})

        approvals_list = []
        for r in conn.execute("SELECT * FROM approvals WHERE action_id=?", (action_id,)).fetchall():
            d = dict(r)
            try:
                d["approver_json"] = json.loads(d["approver_json"])
            except:
                pass
            approvals_list.append(d)

        canary_data = None
        cr = conn.execute("SELECT * FROM executions WHERE action_id=? AND phase='canary'", (action_id,)).fetchone()
        if cr:
            canary_data = dict(cr)
            try:
                canary_data["subset_ids_json"] = json.loads(canary_data["subset_ids_json"])
                canary_data["results_json"] = json.loads(canary_data["results_json"])
            except:
                pass

        actor = json.loads(action["actor_json"])
        proof = generate_proof(
            action_id=action_id, org_id=action["org_id"], environment=action["environment"],
            action_snapshot={"tool": action["tool"], "action_type": action["action_type"], "actor": actor, "params": params},
            preview_summary={"blast_radius": blast_radius_data["count"], "preview_hash": preview_hash, "flags": flags, "diffs": []},
            decision={"policy_id": decision["policy_id"], "policy_version": policy_version,
                       "decision": decision["decision"], "reasons": json.loads(decision["reasons_json"]), "thresholds": thresholds},
            approvals=approvals_list, canary=canary_data, checks=all_checks, breaker=breaker_status, events=events,
        )
        conn.execute(
            "INSERT INTO proofs (action_id, receipt_json, signature) VALUES (?,?,?)",
            (action_id, json.dumps(proof["receipt"]), proof["signature"])
        )
        add_event(conn, action_id, "proof.generated", {"signature_prefix": proof["signature"][:16]})

    # Post result to Slack
    post_approval_result(action_id, approver_name, True, final_status)

    # Replace the original message with the result (removes buttons)
    result_text = f":white_check_mark: *Approved by {approver_name}*\nAction `{action_id}` — Status: `{final_status}`\n<http://localhost:3000/actions/{action_id}|View Details>"
    _update_slack_message(response_url, result_text)

    return JSONResponse({
        "response_type": "in_channel",
        "replace_original": True,
        "text": result_text,
    })


def _handle_deny(action_id: str, approver_id: str, approver_name: str, response_url: str = ""):
    """Record denial and block the action."""
    with get_db() as conn:
        action = conn.execute(
            "SELECT * FROM actions WHERE action_id=?", (action_id,)
        ).fetchone()

        if not action:
            return JSONResponse({
                "response_type": "ephemeral",
                "replace_original": True,
                "text": f":warning: Action `{action_id}` not found.",
            })

        if action["status"] != "awaiting_approval":
            msg = f":information_source: Action `{action_id}` is already `{action['status']}`. No further action needed."
            _update_slack_message(response_url, msg)
            return JSONResponse({
                "response_type": "ephemeral",
                "replace_original": True,
                "text": msg,
            })

        conn.execute(
            "UPDATE actions SET status='blocked', updated_at=? WHERE action_id=?",
            (datetime.utcnow().isoformat(), action_id)
        )
        add_event(conn, action_id, "approval.denied", {
            "approver": approver_name,
            "approver_id": approver_id,
            "channel": "slack",
        })

        # Generate proof for the denial
        preview = conn.execute("SELECT * FROM previews WHERE action_id=?", (action_id,)).fetchone()
        decision = conn.execute("SELECT * FROM decisions WHERE action_id=?", (action_id,)).fetchone()

        events = []
        for r in conn.execute(
            "SELECT type, payload_json, created_at FROM events WHERE action_id=? ORDER BY created_at",
            (action_id,)
        ).fetchall():
            try:
                p = json.loads(r["payload_json"])
            except:
                p = {}
            events.append({"type": r["type"], "payload": p, "timestamp": r["created_at"]})

        actor = json.loads(action["actor_json"])
        params = json.loads(action["params_json"])
        blast_data = json.loads(preview["blast_radius_json"])
        flags = json.loads(preview["flags_json"])

        proof = generate_proof(
            action_id=action_id, org_id=action["org_id"], environment=action["environment"],
            action_snapshot={"tool": action["tool"], "action_type": action["action_type"], "actor": actor, "params": params},
            preview_summary={"blast_radius": blast_data["count"], "preview_hash": preview["preview_hash"], "flags": flags, "diffs": []},
            decision={"policy_id": decision["policy_id"], "policy_version": decision["policy_version"],
                       "decision": decision["decision"], "reasons": json.loads(decision["reasons_json"]),
                       "thresholds": json.loads(decision["thresholds_json"])},
            approvals=[], canary=None, checks=[], breaker={"tripped": False, "reason": None}, events=events,
        )
        conn.execute(
            "INSERT INTO proofs (action_id, receipt_json, signature) VALUES (?,?,?)",
            (action_id, json.dumps(proof["receipt"]), proof["signature"])
        )

    post_approval_result(action_id, approver_name, False, "blocked")

    # Replace original message (removes buttons)
    result_text = f":x: *Denied by {approver_name}*\nAction `{action_id}` — Status: `blocked` \n <http://localhost:3000/actions/{action_id}|View Details>"
    _update_slack_message(response_url, result_text)

    return JSONResponse({
        "response_type": "in_channel",
        "replace_original": True,
        "text": result_text,
    })