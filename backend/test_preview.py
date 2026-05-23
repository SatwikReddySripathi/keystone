"""Test: preview engine produces correct blast radius, flags, and deterministic hash."""
from app.connectors.servicenow_sim import get_connector
from app.engine.preview import generate_preview

c = get_connector()
c.reset()

# ── Test 1: Safe scenario preview ──
print("=== SAFE SCENARIO (P3/P4 only) ===")
safe_preview = generate_preview(c, {
    "query": {"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}},
    "changes": {"state": "in_progress", "assignment_group": "Triage Team"},
})

print(f"Blast radius: {safe_preview['blast_radius']}")
print(f"Breakdowns: {safe_preview['breakdowns']}")
print(f"Flags: {safe_preview['flags']}")
print(f"Preview hash: {safe_preview['preview_hash']}")
print(f"Target IDs (first 5): {safe_preview['target_ids'][:5]}")
print(f"Diff sample: {safe_preview['diffs'][0]}")

assert safe_preview["blast_radius"] == 20
assert safe_preview["flags"]["has_p1"] == False
assert safe_preview["flags"]["has_vip"] == False
assert safe_preview["flags"]["cross_group"] == True  # Network Ops + Desktop Support + Server Team
assert safe_preview["flags"]["state_transition"] == True
print(" Safe preview correct")

# ── Test 2: Dangerous scenario preview ──
print("\n=== DANGEROUS SCENARIO (all open) ===")
danger_preview = generate_preview(c, {
    "query": {"state": "open"},
    "changes": {"state": "resolved"},
})

print(f"Blast radius: {danger_preview['blast_radius']}")
print(f"Flags: {danger_preview['flags']}")
print(f"Preview hash: {danger_preview['preview_hash']}")

assert danger_preview["blast_radius"] == 25
assert danger_preview["flags"]["has_p1"] == True
assert danger_preview["flags"]["has_vip"] == True
print(" Dangerous preview correct — P1 and VIP detected")

# ── Test 3: Hash determinism ──
print("\n=== DETERMINISM TEST ===")
safe_preview_2 = generate_preview(c, {
    "query": {"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}},
    "changes": {"state": "in_progress", "assignment_group": "Triage Team"},
})
print(f"Hash 1: {safe_preview['preview_hash']}")
print(f"Hash 2: {safe_preview_2['preview_hash']}")
assert safe_preview["preview_hash"] == safe_preview_2["preview_hash"]
print(" Same input → same hash (deterministic)")

# Different changes → different hash
different_preview = generate_preview(c, {
    "query": {"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}},
    "changes": {"state": "resolved"},  # different change
})
print(f"Hash 3 (different changes): {different_preview['preview_hash']}")
assert different_preview["preview_hash"] != safe_preview["preview_hash"]
print(" Different input → different hash")

print("\n All preview tests passed")