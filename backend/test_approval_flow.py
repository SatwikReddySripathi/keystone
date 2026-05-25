"""
Test: full approval flow.
1. Submit action with VIP (no P1) → APPROVAL_REQUIRED
2. Approve via /approve endpoint
3. Execute via /execute endpoint
"""
import requests

BASE = "http://localhost:8000"
H = {"X-API-Key": "am_test_demo_key_001", "Content-Type": "application/json"}

# ── Step 1: Submit action that requires approval ──
# Action is bound to ws_platform so EMP001 (a seeded admin of that workspace)
# has standing to approve it. The permission model in can_approve_action
# requires either agent ownership or workspace membership — an action with
# no workspace context cannot be approved by anyone.
print("=== STEP 1: Submit action with VIP records ===")
resp = requests.post(f"{BASE}/v1/run", headers=H, json={
    "tool": "servicenow",
    "action_type": "bulk_update",
    "workspace_id": "ws_platform",
    "params": {
        "connector": "servicenow_sim",
        "query": {
            "state": "open",
            "priority": "P2",  # P2 includes VIP (CFO) but no P1
        },
        "changes": {"assignment_group": "Executive Support"},
    },
    "mode": "enforce",
})
data = resp.json()
action_id = data["action_id"]
print(f"  Action ID: {action_id}")
print(f"  Status:    {data['status']}")
print(f"  Decision:  {data['decision']['decision']}")
print(f"  Reasons:")
for r in data["decision"]["reasons"]:
    print(f"    [{r['decision']}] {r['reason']}")

assert data["status"] == "awaiting_approval", f"Expected awaiting_approval, got {data['status']}"
print("   Action is awaiting approval")

# ── Step 2: Approve it ──
# EMP001 = Sarah Chen, admin (authorized_tools='*'), seeded by init_db().
# Send only the fields ApproveRequest accepts — approver_name is looked up
# from the DB, not passed in.
print(f"\n=== STEP 2: Approve action {action_id} ===")
approve_resp = requests.post(f"{BASE}/v1/actions/{action_id}/approve", headers=H, json={
    "employee_id": "EMP001",
    "channel": "slack",
})
approve_resp.raise_for_status()
approve_data = approve_resp.json()
print(f"  Approved: {approve_data['approved']}")
print(f"  Approver: {approve_data['approver_name']}")
print(f"  Message:  {approve_data['message']}")
assert approve_data["approved"]
print("   Approval recorded")

# ── Step 3: Execute it ──
print(f"\n=== STEP 3: Execute action {action_id} ===")
exec_resp = requests.post(f"{BASE}/v1/actions/{action_id}/execute", headers=H)
exec_data = exec_resp.json()
print(f"  Status:   {exec_data['status']}")
print(f"  Breaker:  {'TRIPPED' if exec_data['breaker_tripped'] else 'OK'}")
print(f"  Proof:    {'Available' if exec_data['proof_available'] else 'No'}")

# This should complete because we're only changing assignment_group (no side effects)
assert exec_data["status"] == "completed", f"Expected completed, got {exec_data['status']}"
print("   Executed successfully after approval")

# ── Step 4: Verify the detail shows approval ──
print(f"\n=== STEP 4: Verify detail ===")
detail = requests.get(f"{BASE}/v1/actions/{action_id}", headers=H).json()
print(f"  Approvals: {len(detail['approvals'])}")
if detail["approvals"]:
    a = detail["approvals"][0]
    approver = a.get("approver_json", {})
    print(f"  Approver:  {approver.get('name', 'Unknown')}")
    print(f"  Channel:   {a.get('channel')}")
    print(f"  Hash:      {a.get('preview_hash', '')[:16]}...")
print(f"  Events:    {len(detail['events'])} total")
for e in detail["events"]:
    print(f"    {e['type']}")

print("\n Full approval flow passed")