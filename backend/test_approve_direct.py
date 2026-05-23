import requests

BASE = "http://localhost:8000"
H = {"X-API-Key": "ks_test_demo_key_001", "Content-Type": "application/json"}

resp = requests.post(f"{BASE}/v1/actions/act_14cde9f5b21d467c/approve", headers=H, json={
    "approver_id": "test-user",
    "approver_name": "Test User",
    "channel": "ui",
})

print(f"Status: {resp.status_code}")
print(f"Body: {resp.json()}")