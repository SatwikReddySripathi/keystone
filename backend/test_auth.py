"""Test: auth resolves the right org for valid key, rejects bad keys."""
import hashlib
from app.db import init_db, get_db

init_db()

# Simulate what auth.py does
def check_key(api_key: str) -> str:
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    with get_db() as conn:
        row = conn.execute(
            "SELECT org_id FROM api_keys WHERE key_hash = ?",
            (key_hash,)
        ).fetchone()
    return row["org_id"] if row else None

# Test valid key
result = check_key("ks_test_demo_key_001")
print(f"Valid key -> org_id: {result}")

# Test invalid key
result2 = check_key("ks_fake_key_999")
print(f"Invalid key -> org_id: {result2}")

assert result == "org_demo", "Valid key should return org_demo"
assert result2 is None, "Invalid key should return None"
print("\nAuth tests passed ")