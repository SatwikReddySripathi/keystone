"""
GET /v1/stats — Aggregate dashboard metrics for the org.
"""
import json
from fastapi import APIRouter, Depends
from app.auth import authenticate
from app.db import get_db

router = APIRouter()


@router.get("/v1/stats")
def get_stats(org_id: str = Depends(authenticate)):
    with get_db() as conn:
        # Action counts by status
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM actions WHERE org_id = ? GROUP BY status",
            (org_id,)
        ).fetchall()
        status_counts = {r["status"]: r["cnt"] for r in rows}

        total_actions = sum(status_counts.values())
        completed = status_counts.get("completed", 0)
        contained = status_counts.get("contained", 0)
        blocked = status_counts.get("blocked", 0)
        awaiting_approval = status_counts.get("awaiting_approval", 0)

        # Total approvals
        total_approvals = conn.execute(
            """SELECT COUNT(*) as cnt FROM approvals
               WHERE action_id IN (SELECT action_id FROM actions WHERE org_id = ?)""",
            (org_id,)
        ).fetchone()["cnt"]

        # Breaker trips
        breaker_trips = conn.execute(
            """SELECT COUNT(*) as cnt FROM breaker
               WHERE tripped = 1
               AND action_id IN (SELECT action_id FROM actions WHERE org_id = ?)""",
            (org_id,)
        ).fetchone()["cnt"]

        # Records governed: sum of all executed subset sizes
        exec_rows = conn.execute(
            """SELECT subset_ids_json FROM executions
               WHERE action_id IN (SELECT action_id FROM actions WHERE org_id = ?)""",
            (org_id,)
        ).fetchall()
        records_governed = sum(
            len(json.loads(r["subset_ids_json"] or "[]"))
            for r in exec_rows
        )

        # Records protected: for contained actions, records NOT executed
        # = blast_radius - records that were executed
        contained_action_ids = conn.execute(
            "SELECT action_id FROM actions WHERE org_id = ? AND status = 'contained'",
            (org_id,)
        ).fetchall()
        records_protected = 0
        for row in contained_action_ids:
            aid = row["action_id"]
            preview = conn.execute(
                "SELECT blast_radius_json FROM previews WHERE action_id = ?",
                (aid,)
            ).fetchone()
            if preview:
                blast = json.loads(preview["blast_radius_json"] or "{}")
                total_records = blast.get("count", 0)
                executed = conn.execute(
                    "SELECT SUM(json_array_length(subset_ids_json)) as cnt FROM executions WHERE action_id = ?",
                    (aid,)
                ).fetchone()["cnt"] or 0
                protected = max(0, total_records - executed)
                records_protected += protected

        # Actions in the last 24 hours
        last_24h_actions = conn.execute(
            """SELECT COUNT(*) as cnt FROM actions
               WHERE org_id = ? AND created_at >= datetime('now', '-24 hours')""",
            (org_id,)
        ).fetchone()["cnt"]

    return {
        "total_actions": total_actions,
        "completed": completed,
        "contained": contained,
        "blocked": blocked,
        "awaiting_approval": awaiting_approval,
        "total_approvals": total_approvals,
        "breaker_trips": breaker_trips,
        "records_governed": records_governed,
        "records_protected": records_protected,
        "last_24h_actions": last_24h_actions,
    }
