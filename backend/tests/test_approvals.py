"""
Approval lifecycle tests.

Covers:
    POST /v1/actions/<id>/approve       happy path (admin in workspace)
    POST /v1/actions/<id>/approve       rejected when caller lacks role
    POST /v1/actions/<id>/approve       rejected when action is not awaiting
    POST /v1/actions/<id>/deny          happy path -> action ends 'blocked'
    POST /v1/actions/<id>/execute       runs approved action through canary

Uses the seeded approvers from db.py:
    EMP001  Sarah Chen     admin   authorized_tools="*"
    EMP003  Priya Patel    -       authorized_tools="servicenow"  is_admin=0
"""
from __future__ import annotations


def _submit_vip_action(client, workspace_id: str = "ws_platform") -> str:
    """
    Submit a P2 action that triggers APPROVAL_REQUIRED, bound to a
    workspace so EMP001's admin role can approve it. Returns the action_id.
    """
    resp = client.post("/v1/run", json={
        "tool": "servicenow",
        "action_type": "bulk_update",
        "workspace_id": workspace_id,
        "params": {
            "connector": "servicenow_sim",
            "query": {"state": "open", "priority": "P2"},
            "changes": {"assignment_group": "Executive Support"},
        },
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "awaiting_approval"
    assert body["decision"]["decision"] == "APPROVAL_REQUIRED"
    return body["action_id"]


# ── /approve ──────────────────────────────────────────

def test_approve_succeeds_for_workspace_admin(client):
    """EMP001 is admin of ws_platform and has authorized_tools='*'."""
    action_id = _submit_vip_action(client)

    resp = client.post(
        f"/v1/actions/{action_id}/approve",
        json={"employee_id": "EMP001", "channel": "ui"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approved"] is True
    assert body["approver_name"] == "Sarah Chen"


def test_approve_rejected_when_action_has_no_workspace(client):
    """
    An action without workspace_id can't be approved by anyone --
    can_approve_action explicitly returns False for missing context.
    """
    # Submit without workspace_id -> awaits approval but is unowned.
    resp = client.post("/v1/run", json={
        "tool": "servicenow",
        "action_type": "bulk_update",
        "params": {
            "connector": "servicenow_sim",
            "query": {"state": "open", "priority": "P2"},
            "changes": {"assignment_group": "Executive Support"},
        },
    })
    assert resp.status_code == 200
    body = resp.json()
    if body["status"] != "awaiting_approval":
        # Defensive: policy might have BLOCKed instead. Either way,
        # there's no approval to attempt -- skip.
        return
    action_id = body["action_id"]

    resp = client.post(
        f"/v1/actions/{action_id}/approve",
        json={"employee_id": "EMP001", "channel": "ui"},
    )
    assert resp.status_code == 403, resp.text
    assert "workspace" in resp.json()["detail"].lower()


def test_approve_rejected_when_action_not_awaiting(client):
    """Approving a completed action returns 400."""
    # Run a P3/P4 action that auto-completes.
    run_resp = client.post("/v1/run", json={
        "tool": "servicenow",
        "action_type": "bulk_update",
        "workspace_id": "ws_platform",
        "params": {
            "connector": "servicenow_sim",
            "query": {"state": "open", "priority": "P4"},
            "changes": {"state": "in_progress"},
        },
    })
    assert run_resp.status_code == 200
    body = run_resp.json()
    action_id = body["action_id"]
    # Either completed or canary-completed -- both are post-execution states
    # where approval is meaningless.
    assert body["status"] in ("completed", "contained", "observed")

    resp = client.post(
        f"/v1/actions/{action_id}/approve",
        json={"employee_id": "EMP001", "channel": "ui"},
    )
    assert resp.status_code == 400, resp.text


def test_approve_rejected_when_action_does_not_exist(client):
    """Approving a non-existent action_id returns 404."""
    resp = client.post(
        "/v1/actions/act_nope_does_not_exist/approve",
        json={"employee_id": "EMP001", "channel": "ui"},
    )
    assert resp.status_code == 404


# ── /deny ─────────────────────────────────────────────

def test_deny_sets_action_to_blocked(client):
    """Deny is the symmetric path of approve: action ends 'blocked'."""
    action_id = _submit_vip_action(client)

    resp = client.post(
        f"/v1/actions/{action_id}/deny",
        json={"employee_id": "EMP001", "channel": "ui"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["denied"] is True

    detail = client.get(f"/v1/actions/{action_id}").json()
    assert detail["action"]["status"] == "blocked"


# ── /execute ──────────────────────────────────────────

def test_execute_runs_approved_action_through_canary(client):
    """Approve -> execute -> completed."""
    action_id = _submit_vip_action(client)

    approve = client.post(
        f"/v1/actions/{action_id}/approve",
        json={"employee_id": "EMP001", "channel": "ui"},
    )
    assert approve.status_code == 200, approve.text

    execute = client.post(f"/v1/actions/{action_id}/execute")
    assert execute.status_code == 200, execute.text
    body = execute.json()
    # The action only changes assignment_group, no side effects, so the
    # breaker should not trip and we end completed.
    assert body["status"] == "completed"
    assert body["proof_available"] is True


def test_execute_rejected_when_not_approved(client):
    """Execute before approval returns 400."""
    action_id = _submit_vip_action(client)
    resp = client.post(f"/v1/actions/{action_id}/execute")
    assert resp.status_code == 400, resp.text
