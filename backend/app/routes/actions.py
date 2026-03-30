"""
Action routes — the API surface.

POST /v1/run         → Full action lifecycle (the main endpoint)
GET  /v1/actions     → List actions (filtered by org)
GET  /v1/actions/:id → Full detail view (joined across all tables)
GET  /v1/actions/:id/proof → Signed proof receipt

The /v1/run endpoint is the orchestrator. It calls each engine
in sequence and writes to the database at every step. If anything
fails or is blocked, we still generate a proof of what happened.
"""
import json
import traceback
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
import requests as _http

from app.auth import authenticate
from app.db import get_db, add_event
from app.models import ActionInput, RunResponse
from app.connectors.servicenow_sim import get_connector as get_snow
from app.connectors.servicenow_real import get_connector as get_snow_real
from app.engine.preview import generate_preview
from app.engine.policy import evaluate_policy
from app.engine.canary import select_canary_subset, run_post_checks
from app.engine.breaker import evaluate_breaker
from app.engine.proof import generate_proof, verify_proof
from app.slack import post_approval_request

router = APIRouter(prefix="/v1", tags=["actions"])

# ── Connector registry ──────────────────────────────
# Add new connectors here. Each maps a name to a factory function.
CONNECTORS = {
    "servicenow_sim": get_snow,
    "servicenow_real": get_snow_real,
}


# ═════════════════════════════════════════════════════
# POST /v1/run — The main endpoint
# ═════════════════════════════════════════════════════
@router.post("/run", response_model=RunResponse)
def run_action(body: ActionInput, org_id: str = Depends(authenticate)):
    """
    Execute an action through the full governance lifecycle.

    Flow:
      1. Create action (idempotent)
      2. Generate preview (blast radius + diffs + flags + hash)
      3. Evaluate policy → decision + reasons
      4. If BLOCK → stop, generate proof
      5. If CANARY/AUTO + enforce mode:
         a. Select canary subset (5 records)
         b. Execute canary
         c. Run post-checks
         d. Evaluate circuit breaker
         e. If breaker OK → expand to remaining records
         f. If breaker tripped → halt (status = contained)
      6. Generate signed proof receipt
    """
    # Validate connector
    connector_name = body.params.connector
    if connector_name not in CONNECTORS:
        raise HTTPException(400, f"Unknown connector: {connector_name}")
    connector = CONNECTORS[connector_name]()

    action_id = body.generate_action_id()

    with get_db() as conn:

        # ── Step 1: Create action (idempotent) ──
        if body.idempotency_key:
            existing = conn.execute(
                "SELECT action_id FROM actions WHERE org_id=? AND idempotency_key=?",
                (org_id, body.idempotency_key)
            ).fetchone()
            if existing:
                # Return the existing action instead of creating a duplicate
                return _build_response(conn, existing["action_id"], org_id)

        conn.execute(
            """INSERT INTO actions
               (action_id, org_id, status, tool, action_type,
                environment, actor_json, params_json, idempotency_key, mode)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (action_id, org_id, "pending", body.tool, body.action_type,
             body.environment, body.actor.model_dump_json(),
             body.params.model_dump_json(), body.idempotency_key, body.mode)
        )
        add_event(conn, action_id, "action.created", {"mode": body.mode})

        # ── Step 2: Generate preview ──
        params = body.params.model_dump()
        try:
            preview = generate_preview(connector, params)
        except _http.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 503
            raise HTTPException(status_code, f"Connector query failed: HTTP {status_code} — {str(e)}")
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(500, f"Preview generation failed: {type(e).__name__}: {str(e)}")

        conn.execute(
            """INSERT INTO previews
               (action_id, preview_hash, blast_radius_json, diffs_json, flags_json)
               VALUES (?,?,?,?,?)""",
            (action_id, preview["preview_hash"],
             json.dumps({
                 "count": preview["blast_radius"],
                 "breakdowns": preview["breakdowns"],
                 "target_ids": preview["target_ids"],
             }),
             json.dumps(preview["diffs"]),
             json.dumps(preview["flags"]))
        )
        add_event(conn, action_id, "preview.generated", {
            "blast_radius": preview["blast_radius"],
            "preview_hash": preview["preview_hash"],
        })
        _update_status(conn, action_id, "previewed")

        # ── Step 3: Evaluate policy ──
        approval_dict = None
        if body.approval:
            approval_dict = {
                "preview_hash": body.approval.preview_hash,
                "policy_version": body.approval.policy_version,
                "approver": body.approval.approver.model_dump(),
            }

        decision = evaluate_policy(preview, approval_dict)

        conn.execute(
            """INSERT INTO decisions
               (action_id, policy_id, policy_version, decision,
                reasons_json, thresholds_json, required_checks_json)
               VALUES (?,?,?,?,?,?,?)""",
            (action_id, decision["policy_id"], decision["policy_version"],
             decision["decision"], json.dumps(decision["reasons"]),
             json.dumps(decision["thresholds"]),
             json.dumps(decision["required_checks"]))
        )
        add_event(conn, action_id, "decision.made", {
            "decision": decision["decision"],
            "matched_rules": decision.get("matched_rules", []),
        })

        # Store approval if provided
        if body.approval:
            conn.execute(
                """INSERT INTO approvals
                   (action_id, approver_json, preview_hash, policy_version, channel)
                   VALUES (?,?,?,?,?)""",
                (action_id, json.dumps(body.approval.approver.model_dump()),
                 body.approval.preview_hash, body.approval.policy_version,
                 body.approval.channel)
            )
            add_event(conn, action_id, "approval.recorded", {
                "approver": body.approval.approver.name,
                "preview_hash_match": body.approval.preview_hash == preview["preview_hash"],
            })

        # ── Step 4: Handle decision ──
        breaker_status = {"tripped": False, "reason": None}
        all_checks = []

        if decision["decision"] == "BLOCK":
            _update_status(conn, action_id, "blocked")
            add_event(conn, action_id, "action.blocked", {
                "reasons": [r["reason"] for r in decision["reasons"]]
            })

        elif decision["decision"] == "APPROVAL_REQUIRED":
            _update_status(conn, action_id, "awaiting_approval")
            add_event(conn, action_id, "action.awaiting_approval", {})

            # Post to Slack
            slack_sent = post_approval_request(
                action_id=action_id,
                blast_radius=preview["blast_radius"],
                preview_hash=preview["preview_hash"],
                policy_version=decision["policy_version"],
                flags=preview["flags"],
                reasons=decision["reasons"],
                diffs_sample=preview["diffs"][:3],
                actor=body.actor.model_dump(),
                tool=body.tool,
                action_type=body.action_type,
                ui_url=f"http://localhost:3000/actions/{action_id}",
            )
            if slack_sent:
                add_event(conn, action_id, "slack.notification_sent", {
                    "channel": "keystone-approvals"
                })

        elif decision["decision"] in ("CANARY", "AUTO") and body.mode == "enforce":
            # ── Step 5: Canary execution ──
            target_ids = preview["target_ids"]
            canary_size = decision["thresholds"].get("canary_size", 5)
            canary_ids = select_canary_subset(action_id, target_ids, canary_size)

            add_event(conn, action_id, "canary.started", {"subset": canary_ids})
            _update_status(conn, action_id, "canary_executing")

            # Execute on canary subset only
            _meta = {"action_id": action_id, "actor_name": body.actor.name}
            canary_results = connector.execute_update(canary_ids, body.params.changes, metadata=_meta)
            canary_errors = [r for r in canary_results if not r.get("success")]
            canary_error_rate = len(canary_errors) / max(len(canary_results), 1)

            conn.execute(
                """INSERT INTO executions
                   (action_id, phase, subset_ids_json, results_json, error_rate)
                   VALUES (?,?,?,?,?)""",
                (action_id, "canary", json.dumps(canary_ids),
                 json.dumps(canary_results), canary_error_rate)
            )
            add_event(conn, action_id, "canary.completed", {
                "count": len(canary_ids),
                "error_rate": canary_error_rate,
            })

            # ── Step 6: Post-checks ──
            all_checks = run_post_checks(
                action_id, canary_ids, canary_results,
                body.params.changes, preview["flags"], decision["thresholds"]
            )
            for c in all_checks:
                conn.execute(
                    """INSERT INTO checks
                       (action_id, check_name, passed, details_json)
                       VALUES (?,?,?,?)""",
                    (action_id, c["check_name"], int(c["passed"]),
                     json.dumps(c["details"]))
                )
            add_event(conn, action_id, "checks.completed", {
                "results": {c["check_name"]: c["passed"] for c in all_checks}
            })

            # ── Step 7: Circuit breaker ──
            breaker_status = evaluate_breaker(all_checks)
            conn.execute(
                """INSERT INTO breaker
                   (action_id, tripped, reason, tripped_at)
                   VALUES (?,?,?,?)""",
                (action_id, int(breaker_status["tripped"]),
                 breaker_status["reason"],
                 datetime.utcnow().isoformat() if breaker_status["tripped"] else None)
            )

            if breaker_status["tripped"]:
                # HALT — only canary records were touched
                _update_status(conn, action_id, "contained")
                add_event(conn, action_id, "breaker.tripped", {
                    "reason": breaker_status["reason"],
                    "failed_checks": breaker_status["failed_checks"],
                })
            else:
                # ── Step 8: Expand to remaining records ──
                remaining_ids = [sid for sid in target_ids if sid not in canary_ids]
                if remaining_ids:
                    add_event(conn, action_id, "expand.started", {
                        "count": len(remaining_ids)
                    })
                    _update_status(conn, action_id, "expanding")

                    expand_results = connector.execute_update(
                        remaining_ids, body.params.changes, metadata=_meta
                    )
                    expand_errors = [r for r in expand_results if not r.get("success")]
                    expand_error_rate = len(expand_errors) / max(len(expand_results), 1)

                    conn.execute(
                        """INSERT INTO executions
                           (action_id, phase, subset_ids_json, results_json, error_rate)
                           VALUES (?,?,?,?,?)""",
                        (action_id, "expand", json.dumps(remaining_ids),
                         json.dumps(expand_results), expand_error_rate)
                    )
                    add_event(conn, action_id, "expand.completed", {
                        "count": len(remaining_ids),
                        "error_rate": expand_error_rate,
                    })

                _update_status(conn, action_id, "completed")
                add_event(conn, action_id, "action.completed", {})

        elif body.mode == "observe_only":
            # Preview + decision only, no execution
            _update_status(conn, action_id, "observed")
            add_event(conn, action_id, "action.observed", {
                "note": "Observe-only mode - no execution performed"
            })

        # ── Step 9: Generate signed proof ──
        events = _get_events(conn, action_id)
        approvals_list = _get_approvals(conn, action_id)
        canary_data = _get_canary(conn, action_id)

        proof = generate_proof(
            action_id=action_id,
            org_id=org_id,
            environment=body.environment,
            action_snapshot={
                "tool": body.tool,
                "action_type": body.action_type,
                "actor": body.actor.model_dump(),
                "params": body.params.model_dump(),
            },
            preview_summary=preview,
            decision=decision,
            approvals=approvals_list,
            canary=canary_data,
            checks=all_checks,
            breaker=breaker_status,
            events=events,
        )

        conn.execute(
            "INSERT INTO proofs (action_id, receipt_json, signature) VALUES (?,?,?)",
            (action_id, json.dumps(proof["receipt"]), proof["signature"])
        )
        add_event(conn, action_id, "proof.generated", {
            "signature_prefix": proof["signature"][:16]
        })

        return _build_response(conn, action_id, org_id)


# ═════════════════════════════════════════════════════
# GET /v1/actions — List actions
# ═════════════════════════════════════════════════════
@router.post("/actions/{action_id}/execute-from-dry-run")
def execute_from_dry_run(action_id: str, org_id: str = Depends(authenticate)):
    """
    Take a dry-run (observed) action and execute it for real.
    Creates a new action in enforce mode with the same params.
    Links the two via events. Can only be called once per dry run.
    """
    with get_db() as conn:
        # Verify the action exists, belongs to org, and is observed
        action = conn.execute(
            "SELECT * FROM actions WHERE action_id=? AND org_id=?",
            (action_id, org_id)
        ).fetchone()
        if not action:
            raise HTTPException(404, "Action not found")
        if action["status"] != "observed":
            raise HTTPException(400, f"Action is '{action['status']}', not observed. Only dry-run actions can be executed.")

        # Check if already executed (look for existing link event)
        existing = conn.execute(
            "SELECT payload_json FROM events WHERE action_id=? AND type='dryrun.executed_as'",
            (action_id,)
        ).fetchone()
        if existing:
            child_id = json.loads(existing["payload_json"]).get("child_action_id")
            raise HTTPException(400, f"Already executed as {child_id}")

    # Build the action input from the original
    from app.models import ActionInput as AI, Actor, ActionParams
    actor_data = json.loads(action["actor_json"])
    params_data = json.loads(action["params_json"])

    body = AI(
        tool=action["tool"],
        action_type=action["action_type"],
        environment=action["environment"],
        actor=Actor(**actor_data),
        params=ActionParams(**params_data),
        mode="enforce",
    )

    # Run it through the normal flow
    connector_name = body.params.connector
    if connector_name not in CONNECTORS:
        raise HTTPException(400, f"Unknown connector: {connector_name}")
    connector = CONNECTORS[connector_name]()

    new_action_id = body.generate_action_id()

    with get_db() as conn:
        # Create new action
        conn.execute(
            """INSERT INTO actions
               (action_id, org_id, status, tool, action_type,
                environment, actor_json, params_json, idempotency_key, mode)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (new_action_id, org_id, "pending", body.tool, body.action_type,
             body.environment, body.actor.model_dump_json(),
             body.params.model_dump_json(), None, "enforce")
        )
        add_event(conn, new_action_id, "action.created", {"mode": "enforce", "parent_dry_run": action_id})

        # Link: mark the dry run as executed
        add_event(conn, action_id, "dryrun.executed_as", {"child_action_id": new_action_id})

        # Generate preview
        params = body.params.model_dump()
        preview = generate_preview(connector, params)
        conn.execute(
            """INSERT INTO previews
               (action_id, preview_hash, blast_radius_json, diffs_json, flags_json)
               VALUES (?,?,?,?,?)""",
            (new_action_id, preview["preview_hash"],
             json.dumps({"count": preview["blast_radius"], "breakdowns": preview["breakdowns"], "target_ids": preview["target_ids"]}),
             json.dumps(preview["diffs"]), json.dumps(preview["flags"]))
        )
        add_event(conn, new_action_id, "preview.generated", {"blast_radius": preview["blast_radius"], "preview_hash": preview["preview_hash"]})
        _update_status(conn, new_action_id, "previewed")

        # Evaluate policy
        decision = evaluate_policy(preview, None)
        conn.execute(
            """INSERT INTO decisions
               (action_id, policy_id, policy_version, decision,
                reasons_json, thresholds_json, required_checks_json)
               VALUES (?,?,?,?,?,?,?)""",
            (new_action_id, decision["policy_id"], decision["policy_version"],
             decision["decision"], json.dumps(decision["reasons"]),
             json.dumps(decision["thresholds"]), json.dumps(decision["required_checks"]))
        )
        add_event(conn, new_action_id, "decision.made", {"decision": decision["decision"], "matched_rules": decision.get("matched_rules", [])})

        breaker_status = {"tripped": False, "reason": None}
        all_checks = []

        if decision["decision"] == "BLOCK":
            _update_status(conn, new_action_id, "blocked")
            add_event(conn, new_action_id, "action.blocked", {"reasons": [r["reason"] for r in decision["reasons"]]})
        elif decision["decision"] == "APPROVAL_REQUIRED":
            _update_status(conn, new_action_id, "awaiting_approval")
            add_event(conn, new_action_id, "action.awaiting_approval", {})

            # Post to Slack
            slack_sent = post_approval_request(
                action_id=new_action_id,
                blast_radius=preview["blast_radius"],
                preview_hash=preview["preview_hash"],
                policy_version=decision["policy_version"],
                flags=preview["flags"],
                reasons=decision["reasons"],
                diffs_sample=preview["diffs"][:3],
                actor=actor_data,
                tool=action["tool"],
                action_type=action["action_type"],
                ui_url=f"http://localhost:3000/actions/{new_action_id}",
            )
            if slack_sent:
                add_event(conn, new_action_id, "slack.notification_sent", {"channel": "keystone-approvals"})
        elif decision["decision"] in ("CANARY", "AUTO"):
            target_ids = preview["target_ids"]
            canary_size = decision["thresholds"].get("canary_size", 5)
            canary_ids = select_canary_subset(new_action_id, target_ids, canary_size)
            add_event(conn, new_action_id, "canary.started", {"subset": canary_ids})
            _update_status(conn, new_action_id, "canary_executing")

            _meta2 = {"action_id": new_action_id, "actor_name": actor_data.get("name", "Keystone Agent")}
            canary_results = connector.execute_update(canary_ids, body.params.changes, metadata=_meta2)
            canary_error_rate = len([r for r in canary_results if not r.get("success")]) / max(len(canary_results), 1)
            conn.execute(
                """INSERT INTO executions (action_id, phase, subset_ids_json, results_json, error_rate) VALUES (?,?,?,?,?)""",
                (new_action_id, "canary", json.dumps(canary_ids), json.dumps(canary_results), canary_error_rate)
            )
            add_event(conn, new_action_id, "canary.completed", {"count": len(canary_ids), "error_rate": canary_error_rate})

            all_checks = run_post_checks(new_action_id, canary_ids, canary_results, body.params.changes, preview["flags"], decision["thresholds"])
            for c in all_checks:
                conn.execute("INSERT INTO checks (action_id, check_name, passed, details_json) VALUES (?,?,?,?)",
                    (new_action_id, c["check_name"], int(c["passed"]), json.dumps(c["details"])))
            add_event(conn, new_action_id, "checks.completed", {"results": {c["check_name"]: c["passed"] for c in all_checks}})

            breaker_status = evaluate_breaker(all_checks)
            conn.execute("INSERT INTO breaker (action_id, tripped, reason, tripped_at) VALUES (?,?,?,?)",
                (new_action_id, int(breaker_status["tripped"]), breaker_status["reason"],
                 datetime.utcnow().isoformat() if breaker_status["tripped"] else None))

            if breaker_status["tripped"]:
                _update_status(conn, new_action_id, "contained")
                add_event(conn, new_action_id, "breaker.tripped", {"reason": breaker_status["reason"], "failed_checks": breaker_status["failed_checks"]})
            else:
                remaining_ids = [sid for sid in target_ids if sid not in canary_ids]
                if remaining_ids:
                    add_event(conn, new_action_id, "expand.started", {"count": len(remaining_ids)})
                    _update_status(conn, new_action_id, "expanding")
                    expand_results = connector.execute_update(remaining_ids, body.params.changes, metadata=_meta2)
                    expand_error_rate = len([r for r in expand_results if not r.get("success")]) / max(len(expand_results), 1)
                    conn.execute("INSERT INTO executions (action_id, phase, subset_ids_json, results_json, error_rate) VALUES (?,?,?,?,?)",
                        (new_action_id, "expand", json.dumps(remaining_ids), json.dumps(expand_results), expand_error_rate))
                    add_event(conn, new_action_id, "expand.completed", {"count": len(remaining_ids), "error_rate": expand_error_rate})
                _update_status(conn, new_action_id, "completed")
                add_event(conn, new_action_id, "action.completed", {})

        # Proof
        events_list = _get_events(conn, new_action_id)
        proof = generate_proof(
            action_id=new_action_id, org_id=org_id, environment=body.environment,
            action_snapshot={"tool": body.tool, "action_type": body.action_type, "actor": body.actor.model_dump(), "params": body.params.model_dump()},
            preview_summary=preview, decision=decision, approvals=[], canary=_get_canary(conn, new_action_id),
            checks=all_checks, breaker=breaker_status, events=events_list,
        )
        conn.execute("INSERT INTO proofs (action_id, receipt_json, signature) VALUES (?,?,?)",
            (new_action_id, json.dumps(proof["receipt"]), proof["signature"]))
        add_event(conn, new_action_id, "proof.generated", {"signature_prefix": proof["signature"][:16]})

        return _build_response(conn, new_action_id, org_id)


@router.get("/actions")
def list_actions(
    org_id: str = Depends(authenticate),
    status: str = Query(None),
    tool: str = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
):
    """List actions for the authenticated org, with optional filters."""
    with get_db() as conn:
        sql = "SELECT * FROM actions WHERE org_id = ?"
        params = [org_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        if tool:
            sql += " AND tool = ?"
            params.append(tool)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


# ═════════════════════════════════════════════════════
# GET /v1/actions/:id — Full action detail
# ═════════════════════════════════════════════════════
@router.get("/actions/{action_id}")
def get_action(action_id: str, org_id: str = Depends(authenticate)):
    """
    Full joined view of an action: action + preview + decision +
    approvals + executions + checks + breaker + events.
    This powers the detail page in the UI.
    """
    with get_db() as conn:
        action = conn.execute(
            "SELECT * FROM actions WHERE action_id=? AND org_id=?",
            (action_id, org_id)
        ).fetchone()
        if not action:
            raise HTTPException(404, "Action not found")

        preview = conn.execute(
            "SELECT * FROM previews WHERE action_id=?", (action_id,)
        ).fetchone()
        decision = conn.execute(
            "SELECT * FROM decisions WHERE action_id=?", (action_id,)
        ).fetchone()
        approvals = conn.execute(
            "SELECT * FROM approvals WHERE action_id=?", (action_id,)
        ).fetchall()
        executions = conn.execute(
            "SELECT * FROM executions WHERE action_id=? ORDER BY created_at",
            (action_id,)
        ).fetchall()
        checks = conn.execute(
            "SELECT * FROM checks WHERE action_id=?", (action_id,)
        ).fetchall()
        breaker_row = conn.execute(
            "SELECT * FROM breaker WHERE action_id=?", (action_id,)
        ).fetchone()
        events = conn.execute(
            "SELECT * FROM events WHERE action_id=? ORDER BY created_at",
            (action_id,)
        ).fetchall()

        return {
            "action": dict(action),
            "preview": _parse_row(preview) if preview else None,
            "decision": _parse_row(decision) if decision else None,
            "approvals": [_parse_row(a) for a in approvals],
            "executions": [_parse_row(e) for e in executions],
            "checks": [_parse_row(c) for c in checks],
            "breaker": _parse_row(breaker_row) if breaker_row else None,
            "events": [_parse_row(e) for e in events],
        }


# ═════════════════════════════════════════════════════
# GET /v1/actions/:id/proof — Signed proof receipt
# ═════════════════════════════════════════════════════
@router.get("/actions/{action_id}/targets")
def get_action_targets(action_id: str, org_id: str = Depends(authenticate)):
    """
    Returns the flat list of target records for an action — incident numbers,
    sys_ids, and their current (pre-execution) field values.

    Primary use: open all target records in ServiceNow before execution so
    you can watch them change in real time.

    Also returns:
    - a single ServiceNow list-view URL filtering to just these records
    - which records were canary (if already executed)
    - which are still protected (not yet touched)
    """
    with get_db() as conn:
        action = conn.execute(
            "SELECT * FROM actions WHERE action_id=? AND org_id=?",
            (action_id, org_id)
        ).fetchone()
        if not action:
            raise HTTPException(404, "Action not found")

        preview = conn.execute(
            "SELECT * FROM previews WHERE action_id=?", (action_id,)
        ).fetchone()
        if not preview:
            return {"action_id": action_id, "records": [], "total": 0}

        diffs = []
        try:
            diffs = json.loads(preview["diffs_json"]) or []
        except (json.JSONDecodeError, TypeError):
            diffs = []

        br = {}
        try:
            br = json.loads(preview["blast_radius_json"]) or {}
        except (json.JSONDecodeError, TypeError):
            pass
        target_ids = br.get("target_ids", [])

        # Which records were canary / expand
        canary_ids: set = set()
        expand_ids: set = set()
        for ex in conn.execute(
            "SELECT phase, subset_ids_json FROM executions WHERE action_id=?",
            (action_id,)
        ).fetchall():
            try:
                ids = json.loads(ex["subset_ids_json"]) or []
            except (json.JSONDecodeError, TypeError):
                ids = []
            if ex["phase"] == "canary":
                canary_ids = set(ids)
            elif ex["phase"] == "expand":
                expand_ids = set(ids)

        records = []
        for d in diffs:
            sid = d.get("sys_id")
            if not sid:
                continue
            phase = (
                "canary" if sid in canary_ids else
                "expand" if sid in expand_ids else
                "pending"
            )
            before = {
                field: val.get("before")
                for field, val in (d.get("fields") or {}).items()
                if isinstance(val, dict)
            }
            records.append({
                "sys_id": sid,
                "number": d.get("number") or sid[:12],
                "phase": phase,
                "before": before,
            })

        # Build a single ServiceNow list-view URL for all target records
        snow_instance = __import__("os").getenv("SNOW_INSTANCE", "").strip()
        snow_list_url = None
        if snow_instance and target_ids:
            parts = "^OR".join(f"sys_id={sid}" for sid in target_ids if sid)
            snow_list_url = f"https://{snow_instance}.service-now.com/incident_list.do?sysparm_query={parts}"

        return {
            "action_id": action_id,
            "total": len(records),
            "canary_count": len(canary_ids),
            "expand_count": len(expand_ids),
            "pending_count": len([r for r in records if r["phase"] == "pending"]),
            "snow_list_url": snow_list_url,
            "records": records,
        }


@router.get("/actions/{action_id}/record-timeline")
def get_record_timeline(action_id: str, org_id: str = Depends(authenticate)):
    """
    Returns a per-record before/during/after timeline for the action.

    For each record in the blast radius:
      - before:   field values at time of preview (real values from the live system)
      - after:    confirmed field values after execution (from connector's response)
      - phase:    canary / expand / protected / blocked
      - verified: True when the connector returned real before/after snapshots

    This is the "trust but verify" endpoint — it shows exactly what changed,
    where it came from, and lets you cross-check against the live system.
    """
    with get_db() as conn:
        action = conn.execute(
            "SELECT * FROM actions WHERE action_id=? AND org_id=?",
            (action_id, org_id)
        ).fetchone()
        if not action:
            raise HTTPException(404, "Action not found")

        preview = conn.execute(
            "SELECT * FROM previews WHERE action_id=?", (action_id,)
        ).fetchone()

        params = json.loads(action["params_json"])
        changes_intended = list(params.get("changes", {}).keys())

        # Build diff lookup from preview: sys_id -> diff
        diffs = []
        if preview:
            try:
                diffs = json.loads(preview["diffs_json"]) or []
            except (json.JSONDecodeError, TypeError):
                diffs = []
        diff_map = {d.get("sys_id"): d for d in diffs if isinstance(d, dict)}

        # Build execution result lookup: sys_id -> {result, phase}
        exec_map: dict = {}
        for ex in conn.execute(
            "SELECT * FROM executions WHERE action_id=? ORDER BY created_at",
            (action_id,)
        ).fetchall():
            results = []
            try:
                results = json.loads(ex["results_json"]) or []
            except (json.JSONDecodeError, TypeError):
                results = []
            for r in results:
                if isinstance(r, dict) and r.get("sys_id"):
                    exec_map[r["sys_id"]] = {"result": r, "phase": ex["phase"]}

        is_blocked = action["status"] == "blocked"
        records = []

        for diff in diffs:
            sid = diff.get("sys_id")
            if not sid:
                continue

            exec_entry = exec_map.get(sid)
            result = exec_entry["result"] if exec_entry else None

            if is_blocked:
                phase = "blocked"
            elif exec_entry:
                phase = exec_entry["phase"]
            else:
                phase = "protected"

            # Before: from preview diff "before" values (captured from live system at query time)
            before: dict = {}
            for field, val in (diff.get("fields") or {}).items():
                if isinstance(val, dict):
                    before[field] = val.get("before")

            # After: prefer real snapshot from connector, fall back to predicted preview value
            after: dict = {}
            verified = False
            unexpected_fields: list = []

            if result:
                applied = set(result.get("changes_applied", []))
                unexpected_fields = sorted(applied - set(changes_intended))

                if result.get("after_snapshot"):
                    # Real values confirmed by ServiceNow/Jira/etc API response
                    after = dict(result["after_snapshot"])
                    verified = True
                    # Include unexpected fields in before/after
                    if result.get("before_snapshot"):
                        for f in unexpected_fields:
                            if f not in before:
                                before[f] = result["before_snapshot"].get(f)
                            if f not in after:
                                after[f] = result["after_snapshot"].get(f)
                elif applied:
                    # Execution happened but no snapshot — use predicted values
                    for f in applied:
                        if f in (diff.get("fields") or {}):
                            after[f] = diff["fields"][f].get("after")
            elif phase not in ("protected", "blocked"):
                # Observed/dry-run path — use predicted values
                for field, val in (diff.get("fields") or {}).items():
                    if isinstance(val, dict):
                        after[field] = val.get("after")

            records.append({
                "sys_id": sid,
                "number": (result.get("number") if result else None) or diff.get("number") or sid[:12],
                "phase": phase,
                "before": before,
                "after": after if phase not in ("protected", "blocked") else {},
                "unchanged_before": before if phase == "protected" else {},
                "unexpected_fields": unexpected_fields,
                "verified": verified,
                "success": result.get("success", False) if result else (phase == "protected"),
                "error": result.get("error") if (result and not result.get("success")) else None,
            })

        # Summary counts
        phase_counts = {"canary": 0, "expand": 0, "protected": 0, "blocked": 0}
        for r in records:
            phase_counts[r["phase"]] = phase_counts.get(r["phase"], 0) + 1

        return {
            "action_id": action_id,
            "changes_intended": changes_intended,
            "total_records": len(records),
            "phase_counts": phase_counts,
            "has_verified_snapshots": any(r["verified"] for r in records),
            "records": records,
        }


@router.get("/actions/{action_id}/proof")
def get_proof(action_id: str, org_id: str = Depends(authenticate)):
    """Return the proof receipt + signature + live verification result."""
    with get_db() as conn:
        action = conn.execute(
            "SELECT org_id FROM actions WHERE action_id=? AND org_id=?",
            (action_id, org_id)
        ).fetchone()
        if not action:
            raise HTTPException(404, "Action not found")

        proof = conn.execute(
            "SELECT * FROM proofs WHERE action_id=?", (action_id,)
        ).fetchone()
        if not proof:
            raise HTTPException(404, "Proof not found")

        receipt = json.loads(proof["receipt_json"])
        sig = proof["signature"]
        verified = verify_proof(receipt, sig)

        return {
            "action_id": action_id,
            "receipt": receipt,
            "signature": sig,
            "verified": verified,
        }


# ═════════════════════════════════════════════════════
# Helper functions
# ═════════════════════════════════════════════════════

def _update_status(conn, action_id: str, status: str):
    """Update action status + timestamp."""
    conn.execute(
        "UPDATE actions SET status=?, updated_at=? WHERE action_id=?",
        (status, datetime.utcnow().isoformat(), action_id)
    )


def _parse_row(row) -> dict:
    """Convert a sqlite Row to dict, auto-parsing JSON columns."""
    if row is None:
        return None
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, str) and k.endswith("_json"):
            try:
                d[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def _get_events(conn, action_id: str) -> list[dict]:
    """Get all events for an action, formatted for the proof receipt."""
    rows = conn.execute(
        "SELECT type, payload_json, created_at FROM events WHERE action_id=? ORDER BY created_at",
        (action_id,)
    ).fetchall()
    events = []
    for r in rows:
        payload = {}
        try:
            payload = json.loads(r["payload_json"])
        except (json.JSONDecodeError, TypeError):
            pass
        events.append({
            "type": r["type"],
            "payload": payload,
            "timestamp": r["created_at"],
        })
    return events


def _get_approvals(conn, action_id: str) -> list[dict]:
    """Get all approvals for an action."""
    rows = conn.execute(
        "SELECT * FROM approvals WHERE action_id=?", (action_id,)
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["approver_json"] = json.loads(d["approver_json"])
        except (json.JSONDecodeError, TypeError):
            pass
        result.append(d)
    return result


def _get_canary(conn, action_id: str) -> dict | None:
    """Get canary execution data for an action."""
    row = conn.execute(
        "SELECT * FROM executions WHERE action_id=? AND phase='canary'",
        (action_id,)
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["subset_ids_json"] = json.loads(d["subset_ids_json"])
        d["results_json"] = json.loads(d["results_json"])
    except (json.JSONDecodeError, TypeError):
        pass
    return d


def _build_response(conn, action_id: str, org_id: str) -> RunResponse:
    """Build the RunResponse from database state."""
    action = conn.execute(
        "SELECT * FROM actions WHERE action_id=?", (action_id,)
    ).fetchone()
    preview = conn.execute(
        "SELECT * FROM previews WHERE action_id=?", (action_id,)
    ).fetchone()
    decision = conn.execute(
        "SELECT * FROM decisions WHERE action_id=?", (action_id,)
    ).fetchone()
    breaker_row = conn.execute(
        "SELECT * FROM breaker WHERE action_id=?", (action_id,)
    ).fetchone()
    proof = conn.execute(
        "SELECT * FROM proofs WHERE action_id=?", (action_id,)
    ).fetchone()

    # Build preview summary
    preview_summary = None
    if preview:
        try:
            br = json.loads(preview["blast_radius_json"])
            preview_summary = {
                "blast_radius": br.get("count"),
                "preview_hash": preview["preview_hash"],
                "flags": json.loads(preview["flags_json"]),
            }
        except (json.JSONDecodeError, TypeError):
            pass

    # Build decision summary
    decision_summary = None
    if decision:
        decision_summary = {
            "decision": decision["decision"],
            "policy_version": decision["policy_version"],
            "reasons": json.loads(decision["reasons_json"]) if decision["reasons_json"] else [],
        }

    # Build breaker summary
    breaker_summary = None
    if breaker_row:
        breaker_summary = {
            "tripped": bool(breaker_row["tripped"]),
            "reason": breaker_row["reason"],
        }

    base_url = "http://localhost:3000"
    return RunResponse(
        action_id=action_id,
        status=action["status"],
        preview=preview_summary,
        decision=decision_summary,
        breaker=breaker_summary,
        proof_available=proof is not None,
        proof_url=f"/v1/actions/{action_id}/proof" if proof else None,
        ui_urls={
            "detail": f"{base_url}/actions/{action_id}",
            "proof": f"{base_url}/actions/{action_id}/proof",
        },
    )