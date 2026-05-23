"""Test: ServiceNow simulator behaves correctly for both demo scenarios."""
from app.connectors.servicenow_sim import get_connector

c = get_connector()

# ── Test 1: Query safe records (P3/P4 only) ──
safe = c.query({
    "state": "open",
    "priority": {"op": "in", "value": ["P3", "P4"]}
})
print(f"Safe records (P3/P4): {len(safe)}")
assert len(safe) == 20, f"Expected 20, got {len(safe)}"

# Verify none are VIP or P1
for r in safe:
    assert r["priority"] in ("P3", "P4"), f"Found {r['priority']} in safe set"
    assert not r["caller_vip"], f"Found VIP in safe set: {r['sys_id']}"
print("  No P1/P2 or VIP in safe set ")

# ── Test 2: Query ALL records ──
all_records = c.query({"state": "open"})
print(f"\nAll records: {len(all_records)}")
assert len(all_records) == 25

vips = [r for r in all_records if r["caller_vip"]]
p1s = [r for r in all_records if r["priority"] == "P1"]
print(f"  VIP records: {len(vips)}")
print(f"  P1 records: {len(p1s)}")

# ── Test 3: Compute diffs (dry-run, no side effects) ──
diffs = c.compute_diffs(safe[:3], {"state": "in_progress"})
print(f"\nDiff sample (3 records):")
for d in diffs:
    print(f"  {d['number']}: {d['fields']}")

# Verify original data unchanged
original = c.get_record(safe[0]["sys_id"])
assert original["state"] == "open", "compute_diffs should not modify data"
print("  Diffs are read-only (no side effects) ")

# ── Test 4: Execute update on 2 records ──
result = c.execute_update(["inc_0000", "inc_0001"], {"state": "in_progress"})
print(f"\nUpdate results:")
for r in result:
    print(f"  {r['sys_id']}: success={r['success']}, changed={r['changes_applied']}")

# Verify data actually changed
updated = c.get_record("inc_0000")
assert updated["state"] == "in_progress", "Record should be updated"
print("  Records actually modified ")

# ── Test 5: Execute on VIP record (triggers unexpected flag) ──
c.reset()  # Reset to clean state
vip_result = c.execute_update(["inc_0020"], {"state": "resolved"})
print(f"\nVIP update result:")
print(f"  {vip_result[0]}")
assert "unexpected_flags" in vip_result[0], "VIP state change should flag"
print("  VIP state change detected ")

# Reset for clean state
c.reset()
print("\n All simulator tests passed")