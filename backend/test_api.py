"""
Test: full API flow — hit the running server with both scenarios.
Run this in a SECOND terminal while uvicorn is running in the first.
"""
import requests
import json

BASE = "http://localhost:8000"
HEADERS = {"X-API-Key": "ks_test_demo_key_001", "Content-Type": "application/json"}


def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════
# Scenario 1: PASS — P3/P4 bulk update
# ═══════════════════════════════════════════════════
separator("SCENARIO 1: PASS — P3/P4 bulk update")

resp = requests.post(f"{BASE}/v1/run", headers=HEADERS, json={
    "tool": "servicenow",
    "action_type": "bulk_update",
    "environment": "simulation",
    "actor": {"id": "agent-demo", "name": "Demo Agent", "type": "agent"},
    "params": {
        "connector": "servicenow_sim",
        "query": {
            "state": "open",
            "priority": {"op": "in", "value": ["P3", "P4"]},
        },
        "changes": {
            "state": "in_progress",
            "assignment_group": "Triage Team",
        },
    },
    "mode": "enforce",
})

print(f"HTTP {resp.status_code}")
data = resp.json()
print(f"Action ID:    {data['action_id']}")
print(f"Status:       {data['status']}")
print(f"Decision:     {data['decision']['decision']}")
print(f"Blast radius: {data['preview']['blast_radius']}")
print(f"Breaker:      {'TRIPPED' if data['breaker']['tripped'] else 'OK'}")
print(f"Proof:        {'Available' if data['proof_available'] else 'No'}")
print(f"Reasons:")
for r in data["decision"]["reasons"]:
    print(f"  [{r['decision']}] {r['reason']}")

assert data["status"] == "completed", f"Expected completed, got {data['status']}"
assert data["decision"]["decision"] == "CANARY"
assert not data["breaker"]["tripped"]
assert data["proof_available"]
print("\n Scenario 1 PASSED: canary → checks → expand → completed")

# Fetch the proof
action_id_1 = data["action_id"]
proof_resp = requests.get(f"{BASE}/v1/actions/{action_id_1}/proof", headers=HEADERS)
proof = proof_resp.json()
print(f"Proof signature: {proof['signature'][:32]}...")
print(f"Proof verified:  {proof['verified']}")
assert proof["verified"]


# ═══════════════════════════════════════════════════
# Scenario 2: BLOCK — includes P1/VIP
# ═══════════════════════════════════════════════════
separator("SCENARIO 2: BLOCK — includes P1 incidents")

resp2 = requests.post(f"{BASE}/v1/run", headers=HEADERS, json={
    "tool": "servicenow",
    "action_type": "bulk_update",
    "environment": "simulation",
    "actor": {"id": "agent-demo", "name": "Demo Agent", "type": "agent"},
    "params": {
        "connector": "servicenow_sim",
        "query": {"state": "open"},
        "changes": {"state": "resolved"},
    },
    "mode": "enforce",
})

print(f"HTTP {resp2.status_code}")
data2 = resp2.json()
print(f"Action ID:    {data2['action_id']}")
print(f"Status:       {data2['status']}")
print(f"Decision:     {data2['decision']['decision']}")
print(f"Blast radius: {data2['preview']['blast_radius']}")
print(f"Proof:        {'Available' if data2['proof_available'] else 'No'}")
print(f"Reasons:")
for r in data2["decision"]["reasons"]:
    print(f"  [{r['decision']}] {r['reason']}")

assert data2["status"] == "blocked", f"Expected blocked, got {data2['status']}"
assert data2["decision"]["decision"] == "BLOCK"
assert data2["proof_available"]
print("\n Scenario 2 PASSED: P1 detected → BLOCK → no execution")


# ═══════════════════════════════════════════════════
# Scenario 3: OBSERVE ONLY — preview + decision, no execution
# ═══════════════════════════════════════════════════
separator("SCENARIO 3: OBSERVE ONLY")

resp3 = requests.post(f"{BASE}/v1/run", headers=HEADERS, json={
    "tool": "servicenow",
    "action_type": "bulk_update",
    "environment": "simulation",
    "actor": {"id": "agent-demo", "name": "Demo Agent", "type": "agent"},
    "params": {
        "connector": "servicenow_sim",
        "query": {
            "state": "open",
            "priority": {"op": "in", "value": ["P3", "P4"]},
        },
        "changes": {"state": "resolved"},
    },
    "mode": "observe_only",
})

data3 = resp3.json()
print(f"Status:       {data3['status']}")
print(f"Decision:     {data3['decision']['decision']}")
print(f"Blast radius: {data3['preview']['blast_radius']}")
print(f"Proof:        {'Available' if data3['proof_available'] else 'No'}")

assert data3["status"] == "observed"
assert data3["proof_available"]
print("\n Scenario 3 PASSED: observe_only → preview + decision, no execution")


# ═══════════════════════════════════════════════════
# Test: List actions
# ═══════════════════════════════════════════════════
separator("LIST ACTIONS")

list_resp = requests.get(f"{BASE}/v1/actions", headers=HEADERS)
actions = list_resp.json()
print(f"Total actions: {len(actions)}")
for a in actions:
    print(f"  {a['action_id']} | {a['status']:20s} | {a['mode']}")

assert len(actions) == 3


# ═══════════════════════════════════════════════════
# Test: Action detail
# ═══════════════════════════════════════════════════
separator("ACTION DETAIL")

detail_resp = requests.get(f"{BASE}/v1/actions/{action_id_1}", headers=HEADERS)
detail = detail_resp.json()
print(f"Action:     {detail['action']['action_id']}")
print(f"Status:     {detail['action']['status']}")
print(f"Preview:    blast_radius={detail['preview']['blast_radius_json']['count']}")
print(f"Decision:   {detail['decision']['decision']}")
print(f"Executions: {len(detail['executions'])} phases")
print(f"Checks:     {len(detail['checks'])} checks")
print(f"Events:     {len(detail['events'])} events")
for e in detail["events"]:
    print(f"  [{e['created_at']}] {e['type']}")

separator("ALL API TESTS PASSED")