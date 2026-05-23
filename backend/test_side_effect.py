"""
Test: ServiceNow business rule side effect triggers breaker.

When state → "resolved", ServiceNow auto-populates resolved_at + work_notes.
The agent only intended to change "state", so the post-check
"only_intended_fields" should FAIL and trip the breaker.
"""
from app.connectors.servicenow_sim import get_connector
from app.engine.canary import run_post_checks
from app.engine.breaker import evaluate_breaker

c = get_connector()
c.reset()

# Simulate: agent changes only "state" to "resolved"
intended_changes = {"state": "resolved"}
canary_ids = ["inc_0000", "inc_0001", "inc_0002", "inc_0003", "inc_0004"]

print("=== EXECUTE WITH SIDE EFFECT ===")
results = c.execute_update(canary_ids, intended_changes)
for r in results:
    print(f"  {r['sys_id']}: changed={r['changes_applied']}")

# Notice: changes_applied includes resolved_at and work_notes
# but the agent only intended to change "state"
print(f"\n  Intended fields: {list(intended_changes.keys())}")
print(f"  Actual fields:   {results[0]['changes_applied']}")

# Run post-checks
print("\n=== POST-CHECKS ===")
checks = run_post_checks(
    "test_side_effect", canary_ids, results,
    changes=intended_changes,
    flags={"has_p1": False, "has_vip": False},
    thresholds={"canary_max_error_rate": 0.0},
)

for ch in checks:
    status = "PASS" if ch["passed"] else "FAIL"
    print(f"  [{status}] {ch['check_name']}")
    if not ch["passed"]:
        print(f"         Details: {ch['details']}")

# Evaluate breaker
print("\n=== CIRCUIT BREAKER ===")
breaker = evaluate_breaker(checks)
print(f"  Tripped: {breaker['tripped']}")
if breaker["tripped"]:
    print(f"  Reason:  {breaker['reason']}")

assert breaker["tripped"], "Breaker should trip on side-effect"

# Verify the right check failed
failed_names = [ch["check_name"] for ch in checks if not ch["passed"]]
assert "only_intended_fields" in failed_names, f"Expected only_intended_fields to fail, got {failed_names}"

print("\n✓ Side effect detected → only_intended_fields failed → breaker tripped")
print("  This is the 'contained' scenario: policy allowed, reality diverged, Keystone halted.")

c.reset()