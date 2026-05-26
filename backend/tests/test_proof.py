"""
Proof receipt tests: HMAC sign / verify / tamper detection.

Exercises both the in-process functions (generate_proof / verify_proof)
and the API roundtrip (POST /v1/run -> GET /v1/actions/<id>/proof).
"""
from __future__ import annotations


def _sample_receipt_inputs() -> dict:
    """The kwargs generate_proof needs for a minimal valid receipt."""
    return dict(
        action_id="act_test_proof_001",
        org_id="org_demo",
        environment="simulation",
        action_snapshot={
            "tool": "servicenow",
            "action_type": "bulk_update",
            "actor": {"id": "agent-001", "name": "Test Agent"},
            "params": {"query": {"state": "open"}, "changes": {"state": "resolved"}},
        },
        preview_summary={
            "blast_radius": 20,
            "preview_hash": "test_hash_abc123",
            "flags": {"has_p1": False},
            "diffs": [],
        },
        decision={
            "policy_id": "default",
            "policy_version": "1.0.0",
            "decision": "CANARY",
            "reasons": [{"rule": "blast_radius_canary", "reason": "blast >= 10"}],
            "thresholds": {"canary_size": 5},
        },
        approvals=[],
        canary=None,
        checks=[],
        breaker={"tripped": False, "reason": None},
        events=[],
    )


def test_generate_proof_returns_receipt_and_signature(client):
    """The function shape: returns dict with `receipt` and `signature` keys."""
    from app.engine.proof import generate_proof

    out = generate_proof(**_sample_receipt_inputs())
    assert isinstance(out, dict)
    assert "receipt" in out
    assert "signature" in out
    assert isinstance(out["signature"], str)
    assert len(out["signature"]) == 64  # SHA-256 hex digest length


def test_verify_proof_accepts_unmodified_receipt(client):
    """A receipt + signature pair produced by generate_proof must verify."""
    from app.engine.proof import generate_proof, verify_proof

    out = generate_proof(**_sample_receipt_inputs())
    assert verify_proof(out["receipt"], out["signature"]) is True


def test_verify_proof_rejects_tampered_receipt(client):
    """
    Any modification to the receipt body invalidates the signature.
    Crucial property -- without it, the audit log is meaningless.
    """
    from app.engine.proof import generate_proof, verify_proof

    out = generate_proof(**_sample_receipt_inputs())
    tampered = dict(out["receipt"])
    # Forge a softer decision than what was actually decided.
    tampered["policy"] = dict(tampered["policy"], decision="AUTO")
    assert verify_proof(tampered, out["signature"]) is False


def test_verify_proof_rejects_wrong_signature(client):
    """A receipt with a foreign signature must not verify."""
    from app.engine.proof import generate_proof, verify_proof

    out = generate_proof(**_sample_receipt_inputs())
    bogus_sig = "0" * 64
    assert verify_proof(out["receipt"], bogus_sig) is False


def test_proof_endpoint_returns_verified_receipt(client):
    """
    End-to-end: submitting a real action through /v1/run produces a
    receipt that verifies through the proof endpoint.
    """
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

    proof_resp = client.get(f"/v1/actions/{action_id}/proof")
    assert proof_resp.status_code == 200, proof_resp.text
    body = proof_resp.json()
    assert body["verified"] is True
    assert body["action_id"] == action_id
    assert len(body["signature"]) == 64
    # Receipt body carries the decision + preview hash for offline audit.
    assert body["receipt"]["action"]["action_id"] == action_id
    assert body["receipt"]["policy"]["decision"] in ("AUTO", "CANARY")


def test_proof_endpoint_404s_for_unknown_action(client):
    resp = client.get("/v1/actions/act_does_not_exist/proof")
    assert resp.status_code == 404
