"""
Test: canary selection, post-checks, and circuit breaker.
Two scenarios:
  1. Safe canary (P3/P4 only) → all checks pass → breaker stays open
  2. Dangerous canary (includes VIP) → checks fail → breaker trips
"""
from app.connectors.servicenow_sim import get_connector
from app.engine.preview import generate_preview
from app.engine.canary import select_canary_subset, run_post_checks
from app.engine.breaker import evaluate_breaker

c = get_connector()

# ═══════════════════════════════════════════════════
# TEST 1: Canary subset is deterministic
# ═══════════════════════════════════════════════════
print("=== DETERMINISM TEST ===")
target_ids = [f"inc_{i:04d}" for i in range(20)]

subset1 = select_canary_subset("action_001", target_ids, 5)
subset2 = select_canary_subset("action_001", target_ids, 5)
subset3 = select_canary_subset("action_002", target_ids, 5)

print(f"Action 001, run 1: {subset1}")
print(f"Action 001, run 2: {subset2}")
print(f"Action 002:        {subset3}")
assert subset1 == subset2, "Same action must select same subset"
assert subset1 != subset3, "Different action should select different subset"
print(" Deterministic canary selection confirmed")

# ═══════════════════════════════════════════════════
# TEST 2: Safe canary → all checks pass → breaker open
# ═══════════════════════════════════════════════════
print("\n=== SAFE CANARY (P3/P4 only) ===")
c.reset()

safe_preview = generate_preview(c, {
    "query": {"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}},
    "changes": {"state": "in_progress"},
})

canary_ids = select_canary_subset("safe_action", safe_preview["target_ids"], 5)
print(f"Canary subset: {canary_ids}")

# Execute canary
results = c.execute_update(canary_ids, {"state": "in_progress"})
print(f"Results: {len(results)} records updated")

# Run post-checks
checks = run_post_checks(
    "safe_action", canary_ids, results,
    changes={"state": "in_progress"},
    flags=safe_preview["flags"],
    thresholds={"canary_max_error_rate": 0.0},
)

print("Post-checks:")
for ch in checks:
    status = "PASS" if ch["passed"] else "FAIL"
    print(f"  [{status}] {ch['check_name']}")

# Evaluate breaker
breaker = evaluate_breaker(checks)
print(f"\nCircuit breaker: {'TRIPPED' if breaker['tripped'] else 'OK'}")

assert not breaker["tripped"], "Safe canary should not trip breaker"
assert all(ch["passed"] for ch in checks), "All checks should pass"
print(" Safe canary: all checks passed, breaker stays open")

# ═══════════════════════════════════════════════════
# TEST 3: Dangerous canary → VIP check fails → breaker trips
# ═══════════════════════════════════════════════════
print("\n=== DANGEROUS CANARY (includes VIP/P1) ===")
c.reset()

# Simulate a scenario where canary subset includes a VIP record
# We'll manually include a VIP record in the canary
dangerous_ids = ["inc_0000", "inc_0001", "inc_0002", "inc_0020", "inc_0021"]
#                  P3 safe     P3 safe     P4 safe     P1+VIP      P1+VIP
print(f"Canary subset (forced dangerous): {dangerous_ids}")

results = c.execute_update(dangerous_ids, {"state": "resolved"})
print("Results:")
for r in results:
    flags_str = f" ⚠ {r['unexpected_flags']}" if r.get("unexpected_flags") else ""
    print(f"  {r['sys_id']}: success={r['success']}{flags_str}")

# Run post-checks
checks = run_post_checks(
    "danger_action", dangerous_ids, results,
    changes={"state": "resolved"},
    flags={"has_p1": True, "has_vip": True},
    thresholds={"canary_max_error_rate": 0.0},
)

print("\nPost-checks:")
for ch in checks:
    status = "PASS" if ch["passed"] else "FAIL"
    details = ""
    if not ch["passed"]:
        details = f" → {ch['details']}"
    print(f"  [{status}] {ch['check_name']}{details}")

# Evaluate breaker
breaker = evaluate_breaker(checks)
print(f"\nCircuit breaker: {'TRIPPED' if breaker['tripped'] else 'OK'}")
if breaker["tripped"]:
    print(f"Reason: {breaker['reason']}")
    print(f"Failed checks: {breaker['failed_checks']}")

assert breaker["tripped"], "Dangerous canary should trip breaker"
print(" Dangerous canary: breaker tripped, expansion prevented")

c.reset()
print("\n All canary/breaker tests passed")