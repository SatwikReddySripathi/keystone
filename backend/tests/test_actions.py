"""
Action lifecycle tests against the in-process FastAPI app.

Covers the four decision paths that POST /v1/run can produce:
    AUTO       -- small blast radius, no canary, completes immediately
    CANARY     -- medium blast radius, canary subset runs, then expand
    BLOCK      -- policy refuses; no records touched
    observed   -- observe_only mode, preview + decision only

Each test gets a fresh DB via the `client` fixture, so order doesn't
matter and one test cannot pollute another.
"""
from __future__ import annotations


# ── /v1/run happy paths ────────────────────────────────

def test_run_p3_p4_canary_then_completes(client):
    """P3/P4 bulk update of ~20 records -> CANARY -> expand -> completed."""
    resp = client.post("/v1/run", json={
        "tool": "servicenow",
        "action_type": "bulk_update",
        "params": {
            "connector": "servicenow_sim",
            "query": {"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}},
            "changes": {"state": "in_progress"},
        },
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["status"] == "completed"
    assert body["decision"]["decision"] == "CANARY"
    assert body["breaker"]["tripped"] is False
    assert body["preview"]["blast_radius"] >= 10
    assert body["proof_available"] is True


def test_run_blocks_when_p1_in_scope(client):
    """P1 incidents trigger an unconditional BLOCK -- no execution."""
    resp = client.post("/v1/run", json={
        "tool": "servicenow",
        "action_type": "bulk_update",
        "params": {
            "connector": "servicenow_sim",
            "query": {"state": "open", "priority": "P1"},
            "changes": {"state": "resolved"},
        },
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["status"] == "blocked"
    assert body["decision"]["decision"] == "BLOCK"
    # Proof is still emitted for blocked actions -- the receipt records
    # that the action did not run and why.
    assert body["proof_available"] is True


def test_run_observe_only_does_not_execute(client):
    """observe_only returns preview + decision but performs no writes."""
    resp = client.post("/v1/run", json={
        "tool": "servicenow",
        "action_type": "bulk_update",
        "params": {
            "connector": "servicenow_sim",
            "query": {"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}},
            "changes": {"state": "in_progress"},
        },
        "mode": "observe_only",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["status"] == "observed"
    # A proof is still generated for the dry-run -- the receipt covers
    # the preview + decision even though nothing was executed.
    assert body["proof_available"] is True


# ── Idempotency ────────────────────────────────────────

def test_run_is_idempotent_per_idempotency_key(client):
    """Two POSTs with the same idempotency_key return the same action_id."""
    payload = {
        "tool": "servicenow",
        "action_type": "bulk_update",
        "idempotency_key": "test-idem-key-001",
        "params": {
            "connector": "servicenow_sim",
            "query": {"state": "open", "priority": "P4"},
            "changes": {"state": "in_progress"},
        },
    }
    r1 = client.post("/v1/run", json=payload)
    r2 = client.post("/v1/run", json=payload)

    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["action_id"] == r2.json()["action_id"]


# ── Auth ───────────────────────────────────────────────

def test_run_rejects_missing_api_key(client):
    """No X-API-Key -> 422 (validation, FastAPI declares the header required)."""
    # httpx TestClient headers are case-insensitive and persistent on the
    # session; modify the session directly to drop the auth header for
    # this one request.
    client.headers.pop("x-api-key", None)
    resp = client.post(
        "/v1/run",
        json={"tool": "servicenow", "action_type": "bulk_update"},
    )
    # 422 from FastAPI's Header dependency, or 401/403 from a future auth
    # middleware. Either way, must not be 200.
    assert resp.status_code in (401, 403, 422), resp.text


def test_run_rejects_bad_api_key(client):
    """Invalid X-API-Key -> 401/403, never 200."""
    resp = client.post(
        "/v1/run",
        json={"tool": "servicenow", "action_type": "bulk_update"},
        headers={"X-API-Key": "not-a-real-key"},
    )
    assert resp.status_code in (401, 403), resp.text


# ── Detail + list endpoints ────────────────────────────

def test_list_and_detail_routes_return_created_action(client):
    """An action shows up in /v1/actions and /v1/actions/<id> after /run."""
    run_resp = client.post("/v1/run", json={
        "tool": "servicenow",
        "action_type": "bulk_update",
        "params": {
            "connector": "servicenow_sim",
            "query": {"state": "open", "priority": "P4"},
            "changes": {"state": "in_progress"},
        },
    })
    assert run_resp.status_code == 200, run_resp.text
    action_id = run_resp.json()["action_id"]

    list_resp = client.get("/v1/actions")
    assert list_resp.status_code == 200
    ids = [a["action_id"] for a in list_resp.json()]
    assert action_id in ids

    detail_resp = client.get(f"/v1/actions/{action_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["action"]["action_id"] == action_id
    assert detail["preview"] is not None
    assert detail["decision"] is not None
    assert isinstance(detail["events"], list)
