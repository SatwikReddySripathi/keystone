"""Quick test: verify database initializes correctly."""
from app.db import init_db, get_db

# Create all tables + seed demo data
init_db()

# Read it back
with get_db() as conn:
    orgs = conn.execute("SELECT * FROM orgs").fetchall()
    keys = conn.execute("SELECT * FROM api_keys").fetchall()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()

    print(f"Orgs: {len(orgs)}")
    print(f"API Keys: {len(keys)}")
    print(f"Org: {dict(orgs[0])}")
    print(f"Tables ({len(tables)}): {[t['name'] for t in tables]}")