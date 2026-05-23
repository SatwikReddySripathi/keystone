"""
Test: proof generation, verification, and tamper detection.
"""
import json
from app.engine.proof import generate_proof, verify_proof

# ── Test 1: Generate and verify a proof ──
print("=== GENERATE + VERIFY ===")
proof = generate_proof(
    action_id="act_test_001",
    org_id="org_demo",
    environment="simulation",
    action_snapshot={
        "tool": "servicenow",
        "action_type": "bulk_update",
        "actor": {"id": "agent-001", "name": "Demo Agent"},
        "params": {"query": {"state": "open"}, "changes": {"state": "resolved"}},
    },
    preview_summary={
        "blast_radius": 20,
        "preview_hash": "abc123def456",
        "flags": {"has_p1": False, "has_vip": False},
        "diffs": [{"sys_id": "inc_0000", "fields": {"state": {"before": "open", "after": "resolved"}}}],
    },
    decision={
        "policy_id": "default",
        "policy_version": "1.0.0",
        "decision": "CANARY",
        "reasons": [{"rule": "canary_for_medium_blast", "reason": "Blast radius > 10"}],
        "thresholds": {"canary_size": 5},
    },
    approvals=[],
    canary={"phase": "canary", "subset": ["inc_0000", "inc_0001"], "error_rate": 0.0},
    checks=[
        {"check_name": "no_out_of_scope", "passed": True, "details": {}},
        {"check_name": "error_rate_ok", "passed": True, "details": {}},
    ],
    breaker={"tripped": False, "reason": None},
    events=[
        {"type": "action.created", "timestamp": "2025-01-15T10:00:00Z"},
        {"type": "canary.completed", "timestamp": "2025-01-15T10:00:01Z"},
        {"type": "action.completed", "timestamp": "2025-01-15T10:00:02Z"},
    ],
)

print(f"Signature: {proof['signature'][:40]}...")
print(f"Receipt keys: {list(proof['receipt'].keys())}")

# Verify
verified = verify_proof(proof["receipt"], proof["signature"])
print(f"Verified: {verified}")
assert verified, "Fresh proof should verify"
print(" Proof generated and verified")

# ── Test 2: Tamper detection ──
print("\n=== TAMPER DETECTION ===")

# Tamper 1: Change the org_id
tampered1 = json.loads(json.dumps(proof["receipt"]))
tampered1["org_id"] = "org_evil"
result1 = verify_proof(tampered1, proof["signature"])
print(f"Tampered org_id → verified: {result1}")
assert not result1, "Tampered receipt should fail verification"

# Tamper 2: Change the decision
tampered2 = json.loads(json.dumps(proof["receipt"]))
tampered2["policy"]["decision"] = "AUTO"
result2 = verify_proof(tampered2, proof["signature"])
print(f"Tampered decision → verified: {result2}")
assert not result2

# Tamper 3: Change breaker status
tampered3 = json.loads(json.dumps(proof["receipt"]))
tampered3["execution"]["breaker"]["tripped"] = True
result3 = verify_proof(tampered3, proof["signature"])
print(f"Tampered breaker → verified: {result3}")
assert not result3

# Tamper 4: Change blast radius
tampered4 = json.loads(json.dumps(proof["receipt"]))
tampered4["preview"]["blast_radius"] = 1
result4 = verify_proof(tampered4, proof["signature"])
print(f"Tampered blast radius → verified: {result4}")
assert not result4

print(" All tampering detected — signature catches every change")

# ── Test 3: Receipt contains full audit trail ──
print("\n=== AUDIT COMPLETENESS ===")
r = proof["receipt"]
print(f"  WHO: {r['action']['actor']['name']}")
print(f"  WHAT: {r['action']['tool']}.{r['action']['action_type']}")
print(f"  PREVIEW: blast_radius={r['preview']['blast_radius']}, hash={r['preview']['preview_hash'][:12]}...")
print(f"  POLICY: {r['policy']['decision']} (v{r['policy']['policy_version']})")
print(f"  APPROVALS: {len(r['approvals'])}")
print(f"  BREAKER: tripped={r['execution']['breaker']['tripped']}")
print(f"  CHECKS: {len(r['execution']['checks'])} checks")
print(f"  TIMELINE: {len(r['timeline'])} events")
print(" Receipt contains complete who/what/why/when audit trail")

print("\n All proof tests passed")