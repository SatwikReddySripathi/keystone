from app.db import get_db

with get_db() as conn:
    actions = conn.execute("SELECT action_id, status, org_id FROM actions").fetchall()
    print(f"Total actions: {len(actions)}")
    for a in actions:
        print(f"  {a['action_id']}  status={a['status']}  org={a['org_id']}")