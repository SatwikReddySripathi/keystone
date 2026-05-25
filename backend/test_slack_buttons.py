"""
Test: Submit an action that requires approval, then wait for Slack button click.

Steps:
  1. This script submits the action → posts to Slack
  2. YOU click Approve or Deny in Slack
  3. Slack calls /v1/slack/interact on our backend via ngrok
  4. This script polls until the status changes

Make sure ngrok is running and pointed at localhost:8000.
"""
import requests
import time

BASE = "http://localhost:8000"
H = {"X-API-Key": "am_test_demo_key_001", "Content-Type": "application/json"}

# Submit action with VIP (P2) → APPROVAL_REQUIRED
print("Submitting action with VIP records...")
resp = requests.post(f"{BASE}/v1/run", headers=H, json={
    "tool": "servicenow",
    "action_type": "bulk_update",
    "params": {
        "connector": "servicenow_sim",
        "query": {"state": "open", "priority": "P2"},
        "changes": {"assignment_group": "Executive Support"},
    },
    "mode": "enforce",
})
data = resp.json()
action_id = data["action_id"]

print(f"\nAction ID: {action_id}")
print(f"Status:    {data['status']}")
print(f"Decision:  {data['decision']['decision']}")
print(f"\n>>> Check your Slack channel! Click Approve or Deny. <<<\n")

# Poll for status change
print("Waiting for Slack button click", end="", flush=True)
for i in range(60):  # Wait up to 60 seconds
    time.sleep(2)
    print(".", end="", flush=True)

    detail = requests.get(f"{BASE}/v1/actions/{action_id}", headers=H).json()
    status = detail["action"]["status"]

    if status != "awaiting_approval":
        print(f"\n\nStatus changed to: {status}")

        if detail["approvals"]:
            a = detail["approvals"][0]
            approver = a.get("approver_json", {})
            print(f"Approved by: {approver.get('name', 'Unknown')}")
            print(f"Channel:     {a.get('channel')}")

        if detail["breaker"]:
            tripped = detail["breaker"].get("tripped")
            print(f"Breaker:     {'TRIPPED' if tripped else 'OK'}")

        print(f"\nTimeline:")
        for e in detail["events"]:
            print(f"  {e['type']}")

        print(f"\nView in UI: http://localhost:3000/actions/{action_id}")
        break
else:
    print("\n\nTimed out waiting for Slack response.")
    print("Make sure ngrok is running and Slack interactivity URL is set to:")
    print("  https://YOUR-NGROK-URL/v1/slack/interact")