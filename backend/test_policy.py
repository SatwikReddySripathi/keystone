"""Test: policy engine makes correct decisions for each scenario."""
from app.connectors.servicenow_sim import get_connector
from app.engine.preview import generate_preview
from app.engine.policy import evaluate_policy

c = get_connector()
c.reset()

# ── Test 1: Safe scenario → should be CANARY ──
print("=== SAFE SCENARIO ===")
safe_preview = generate_preview(c, {
    "query": {"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}},
    "changes": {"state": "in_progress"},
})
safe_decision = evaluate_policy(safe_preview)

print(f"Decision: {safe_decision['decision']}")
print(f"Policy version: {safe_decision['policy_version']}")
print(f"Matched rules: {safe_decision['matched_rules']}")
print(f"Required checks: {safe_decision['required_checks']}")
print("Reasons:")
for r in safe_decision["reasons"]:
    print(f"  [{r['decision']}] {r['rule']}: {r['reason']}")

assert safe_decision["decision"] == "CANARY"
assert "canary_for_medium_blast" in safe_decision["matched_rules"]
print(" Safe scenario → CANARY (correct)")

# ── Test 2: Dangerous scenario → should be BLOCK ──
print("\n=== DANGEROUS SCENARIO ===")
danger_preview = generate_preview(c, {
    "query": {"state": "open"},
    "changes": {"state": "resolved"},
})
danger_decision = evaluate_policy(danger_preview)

print(f"Decision: {danger_decision['decision']}")
print(f"Matched rules: {danger_decision['matched_rules']}")
print("Reasons:")
for r in danger_decision["reasons"]:
    print(f"  [{r['decision']}] {r['rule']}: {r['reason']}")

assert danger_decision["decision"] == "BLOCK"
assert "no_p1_incidents" in danger_decision["matched_rules"]
print(" Dangerous scenario → BLOCK (correct)")

# ── Test 3: Small blast radius → should be AUTO ──
print("\n=== SMALL SCENARIO (<=10 records) ===")
# Query just one assignment group to get fewer records
small_preview = generate_preview(c, {
    "query": {"state": "open", "priority": "P4", "assignment_group": "Server Team"},
    "changes": {"state": "in_progress"},
})
print(f"Blast radius: {small_preview['blast_radius']}")
small_decision = evaluate_policy(small_preview)

print(f"Decision: {small_decision['decision']}")
print("Reasons:")
for r in small_decision["reasons"]:
    print(f"  [{r['decision']}] {r['rule']}: {r['reason']}")

assert small_decision["decision"] == "AUTO"
print(" Small scenario -> AUTO (correct)")

# ── Test 4: Determinism — same input, same decision ──
print("\n=== DETERMINISM TEST ===")
safe_decision_2 = evaluate_policy(safe_preview)
assert safe_decision["decision"] == safe_decision_2["decision"]
assert safe_decision["reasons"] == safe_decision_2["reasons"]
print(" Same preview -> same decision (deterministic)")

print("\n All policy tests passed")