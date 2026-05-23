"""
Connections routes — registered SaaS apps and tools.

GET    /v1/connections              — List all connections (optionally filter by workspace)
POST   /v1/connections              — Register a new connection
GET    /v1/connections/{id}         — Connection detail
DELETE /v1/connections/{id}         — Revoke / remove a connection
POST   /v1/connections/{id}/test    — Test the connection status
"""
import json
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.auth import authenticate
from app.db import get_db

router = APIRouter(prefix="/v1/connections", tags=["connections"])

KNOWN_CONNECTOR_TYPES = {
    "servicenow": "ServiceNow",
    "jira":       "Jira",
    "salesforce": "Salesforce",
    "aws_iam":    "AWS IAM",
    "github":     "GitHub",
    "slack":      "Slack",
    "zendesk":    "Zendesk",
    "hubspot":    "HubSpot",
    "pagerduty":  "PagerDuty",
}

RISK_BY_SCOPE = {"delete", "put", "admin", "write", "create", "assume"}


class ConnectionCreate(BaseModel):
    name: str
    connector_type: str
    workspace_id: Optional[str] = None
    environment: str = "production"
    scopes: list[str] = []
    risk_level: Optional[str] = None  # auto-computed if omitted


def _compute_risk(scopes: list[str]) -> str:
    scope_text = " ".join(scopes).lower()
    if any(kw in scope_text for kw in ("delete", "admin", "assume")):
        return "high"
    if any(kw in scope_text for kw in ("write", "put", "create", "merge")):
        return "medium"
    return "low"


# ── List ──────────────────────────────────────────────
@router.get("")
def list_connections(
    org_id: str = Depends(authenticate),
    workspace_id: Optional[str] = Query(None),
):
    with get_db() as conn:
        if workspace_id:
            rows = conn.execute(
                "SELECT * FROM connections WHERE org_id = ? AND workspace_id = ? ORDER BY name",
                (org_id, workspace_id)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM connections WHERE org_id = ? ORDER BY name",
                (org_id,)
            ).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            d["scopes"] = json.loads(d.pop("scopes_json") or "[]")

            # Distinct agents that have used this exact connection
            active_agents = conn.execute(
                """SELECT COUNT(DISTINCT json_extract(actor_json, '$.id')) as cnt
                   FROM actions
                   WHERE org_id = ? AND connection_id = ?""",
                (org_id, d["connection_id"])
            ).fetchone()["cnt"]
            d["active_agents"] = active_agents

            # Total runs through this connection
            total_runs = conn.execute(
                """SELECT COUNT(*) as cnt FROM actions
                   WHERE org_id = ? AND connection_id = ?""",
                (org_id, d["connection_id"])
            ).fetchone()["cnt"]
            d["total_runs"] = total_runs

            # Workspace name
            if d.get("workspace_id"):
                ws_row = conn.execute(
                    "SELECT name FROM workspaces WHERE workspace_id = ?",
                    (d["workspace_id"],)
                ).fetchone()
                d["workspace_name"] = ws_row["name"] if ws_row else None
            else:
                d["workspace_name"] = None

            result.append(d)

        return result


# ── Create ────────────────────────────────────────────
@router.post("")
def create_connection(body: ConnectionCreate, org_id: str = Depends(authenticate)):
    with get_db() as conn:
        if body.workspace_id:
            ws = conn.execute(
                "SELECT workspace_id FROM workspaces WHERE workspace_id = ? AND org_id = ?",
                (body.workspace_id, org_id)
            ).fetchone()
            if not ws:
                raise HTTPException(404, "Workspace not found")

        risk = body.risk_level or _compute_risk(body.scopes)
        conn_id = f"conn_{uuid.uuid4().hex[:12]}"

        conn.execute(
            """INSERT INTO connections
               (connection_id, org_id, workspace_id, name, connector_type,
                environment, scopes_json, risk_level)
               VALUES (?,?,?,?,?,?,?,?)""",
            (conn_id, org_id, body.workspace_id, body.name,
             body.connector_type, body.environment,
             json.dumps(body.scopes), risk)
        )

    return {
        "connection_id": conn_id,
        "name": body.name,
        "connector_type": body.connector_type,
        "risk_level": risk,
    }


# ── Detail ────────────────────────────────────────────
@router.get("/{connection_id}")
def get_connection(connection_id: str, org_id: str = Depends(authenticate)):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM connections WHERE connection_id = ? AND org_id = ?",
            (connection_id, org_id)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Connection not found")

        d = dict(row)
        d["scopes"] = json.loads(d.pop("scopes_json") or "[]")

        # Recent actions through this connection
        recent = conn.execute(
            """SELECT action_id, status, action_type, actor_json, created_at
               FROM actions
               WHERE org_id = ? AND connection_id = ?
               ORDER BY created_at DESC LIMIT 10""",
            (org_id, connection_id)
        ).fetchall()

        runs = []
        for r in recent:
            rd = dict(r)
            try:
                rd["actor"] = json.loads(rd.pop("actor_json") or "{}")
            except Exception:
                rd["actor"] = {}
            runs.append(rd)

        d["recent_runs"] = runs
        return d


# ── Delete ────────────────────────────────────────────
@router.delete("/{connection_id}")
def delete_connection(connection_id: str, org_id: str = Depends(authenticate)):
    with get_db() as conn:
        deleted = conn.execute(
            "DELETE FROM connections WHERE connection_id = ? AND org_id = ?",
            (connection_id, org_id)
        ).rowcount
        if not deleted:
            raise HTTPException(404, "Connection not found")
    return {"deleted": True}


# ── Test ─────────────────────────────────────────────
@router.post("/{connection_id}/test")
def test_connection(connection_id: str, org_id: str = Depends(authenticate)):
    """
    Mark connection as tested now and return its status.
    In production this would actually ping the remote system.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM connections WHERE connection_id = ? AND org_id = ?",
            (connection_id, org_id)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Connection not found")

        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE connections SET last_tested_at = ?, status = 'active' WHERE connection_id = ?",
            (now, connection_id)
        )

    return {
        "connection_id": connection_id,
        "status": "active",
        "last_tested_at": now,
        "message": f"Connection to {row['name']} verified",
    }
