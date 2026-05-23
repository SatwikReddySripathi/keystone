"""
Workspace routes — team-scoped governance spaces.

GET  /v1/workspaces              — List all workspaces for the org
POST /v1/workspaces              — Create a workspace
GET  /v1/workspaces/{id}         — Workspace detail with members + recent runs
POST /v1/workspaces/{id}/members — Add a member
PATCH /v1/workspaces/{id}/members/{eid} — Change a member's role
DELETE /v1/workspaces/{id}/members/{eid} — Remove a member
"""
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.auth import authenticate
from app.db import get_db

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    owner_id: Optional[str] = None
    risk_posture: str = "healthy"


class MemberAdd(BaseModel):
    employee_id: str
    role: str = "viewer"  # admin | approver | viewer


class MemberUpdate(BaseModel):
    role: str


# ── List ──────────────────────────────────────────────
@router.get("")
def list_workspaces(org_id: str = Depends(authenticate)):
    with get_db() as conn:
        workspaces = conn.execute(
            "SELECT * FROM workspaces WHERE org_id = ? ORDER BY created_at DESC",
            (org_id,)
        ).fetchall()

        result = []
        for ws in workspaces:
            ws_id = ws["workspace_id"]

            member_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM workspace_members WHERE workspace_id = ?",
                (ws_id,)
            ).fetchone()["cnt"]

            connection_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM connections WHERE workspace_id = ?",
                (ws_id,)
            ).fetchone()["cnt"]

            agent_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM agents WHERE workspace_id = ? AND status != 'revoked'",
                (ws_id,)
            ).fetchone()["cnt"]

            run_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM actions WHERE workspace_id = ?",
                (ws_id,)
            ).fetchone()["cnt"]

            pending_approvals = conn.execute(
                "SELECT COUNT(*) as cnt FROM actions WHERE workspace_id = ? AND status = 'awaiting_approval'",
                (ws_id,)
            ).fetchone()["cnt"]

            owner = None
            if ws["owner_id"]:
                owner_row = conn.execute(
                    "SELECT name, designation, department FROM approvers WHERE employee_id = ?",
                    (ws["owner_id"],)
                ).fetchone()
                if owner_row:
                    owner = dict(owner_row)

            result.append({
                **dict(ws),
                "owner": owner,
                "stats": {
                    "members": member_count,
                    "connections": connection_count,
                    "agents": agent_count,
                    "total_runs": run_count,
                    "pending_approvals": pending_approvals,
                },
            })

        return result


# ── Create ────────────────────────────────────────────
@router.post("")
def create_workspace(body: WorkspaceCreate, org_id: str = Depends(authenticate)):
    ws_id = f"ws_{uuid.uuid4().hex[:12]}"
    with get_db() as conn:
        if body.owner_id:
            owner = conn.execute(
                "SELECT employee_id FROM approvers WHERE employee_id = ?",
                (body.owner_id,)
            ).fetchone()
            if not owner:
                raise HTTPException(404, f"Approver {body.owner_id} not found")

        conn.execute(
            """INSERT INTO workspaces
               (workspace_id, org_id, name, description, owner_id, risk_posture)
               VALUES (?,?,?,?,?,?)""",
            (ws_id, org_id, body.name, body.description,
             body.owner_id, body.risk_posture)
        )

        if body.owner_id:
            conn.execute(
                """INSERT OR IGNORE INTO workspace_members
                   (workspace_id, employee_id, role) VALUES (?,?,?)""",
                (ws_id, body.owner_id, "admin")
            )

    return {"workspace_id": ws_id, "name": body.name}


# ── Detail ────────────────────────────────────────────
@router.get("/{workspace_id}")
def get_workspace(workspace_id: str, org_id: str = Depends(authenticate)):
    with get_db() as conn:
        ws = conn.execute(
            "SELECT * FROM workspaces WHERE workspace_id = ? AND org_id = ?",
            (workspace_id, org_id)
        ).fetchone()
        if not ws:
            raise HTTPException(404, "Workspace not found")

        members_rows = conn.execute(
            """SELECT wm.*, a.name, a.email, a.designation, a.department
               FROM workspace_members wm
               JOIN approvers a ON wm.employee_id = a.employee_id
               WHERE wm.workspace_id = ?
               ORDER BY wm.role, a.name""",
            (workspace_id,)
        ).fetchall()

        connections_rows = conn.execute(
            "SELECT * FROM connections WHERE workspace_id = ? ORDER BY name",
            (workspace_id,)
        ).fetchall()

        agents_rows = conn.execute(
            """SELECT agent_id, name, description, owner_employee_id, status,
                      permissions_json, rate_limit_per_hour, last_used_at
               FROM agents WHERE workspace_id = ? ORDER BY name""",
            (workspace_id,)
        ).fetchall()

        recent_runs = conn.execute(
            """SELECT action_id, status, tool, action_type, actor_json,
                      created_at, mode
               FROM actions WHERE workspace_id = ?
               ORDER BY created_at DESC LIMIT 20""",
            (workspace_id,)
        ).fetchall()

        status_counts = conn.execute(
            """SELECT status, COUNT(*) as cnt FROM actions
               WHERE workspace_id = ? GROUP BY status""",
            (workspace_id,)
        ).fetchall()
        sc = {r["status"]: r["cnt"] for r in status_counts}

        owner = None
        if ws["owner_id"]:
            owner_row = conn.execute(
                "SELECT name, designation, department, email FROM approvers WHERE employee_id = ?",
                (ws["owner_id"],)
            ).fetchone()
            if owner_row:
                owner = dict(owner_row)

        runs_parsed = []
        for r in recent_runs:
            d = dict(r)
            try:
                d["actor"] = json.loads(d.pop("actor_json") or "{}")
            except Exception:
                d["actor"] = {}
            runs_parsed.append(d)

        # Parse agents with permissions dict
        agents = []
        for a in agents_rows:
            ad = dict(a)
            try:
                ad["permissions"] = json.loads(ad.pop("permissions_json") or "{}")
            except Exception:
                ad["permissions"] = {}
                ad.pop("permissions_json", None)
            agents.append(ad)

        return {
            **dict(ws),
            "owner": owner,
            "members": [dict(m) for m in members_rows],
            "connections": [
                {**dict(c), "scopes": json.loads(c["scopes_json"] or "[]")}
                for c in connections_rows
            ],
            "agents": agents,
            "recent_runs": runs_parsed,
            "stats": {
                "total_runs": sum(sc.values()),
                "completed": sc.get("completed", 0),
                "blocked": sc.get("blocked", 0),
                "contained": sc.get("contained", 0),
                "awaiting_approval": sc.get("awaiting_approval", 0),
                "members": len(members_rows),
                "connections": len(connections_rows),
                "agents": len(agents),
            },
        }


# ── Members ───────────────────────────────────────────
@router.post("/{workspace_id}/members")
def add_member(
    workspace_id: str,
    body: MemberAdd,
    org_id: str = Depends(authenticate),
):
    if body.role not in ("admin", "approver", "viewer"):
        raise HTTPException(400, "role must be admin, approver, or viewer")

    with get_db() as conn:
        ws = conn.execute(
            "SELECT workspace_id FROM workspaces WHERE workspace_id = ? AND org_id = ?",
            (workspace_id, org_id)
        ).fetchone()
        if not ws:
            raise HTTPException(404, "Workspace not found")

        emp = conn.execute(
            "SELECT employee_id, name FROM approvers WHERE employee_id = ?",
            (body.employee_id,)
        ).fetchone()
        if not emp:
            raise HTTPException(404, f"Employee {body.employee_id} not found")

        try:
            conn.execute(
                """INSERT INTO workspace_members (workspace_id, employee_id, role)
                   VALUES (?,?,?)""",
                (workspace_id, body.employee_id, body.role)
            )
        except Exception:
            raise HTTPException(409, f"{body.employee_id} is already a member")

    return {"workspace_id": workspace_id, "employee_id": body.employee_id, "role": body.role}


@router.patch("/{workspace_id}/members/{employee_id}")
def update_member_role(
    workspace_id: str,
    employee_id: str,
    body: MemberUpdate,
    org_id: str = Depends(authenticate),
):
    if body.role not in ("admin", "approver", "viewer"):
        raise HTTPException(400, "role must be admin, approver, or viewer")

    with get_db() as conn:
        ws = conn.execute(
            "SELECT workspace_id FROM workspaces WHERE workspace_id = ? AND org_id = ?",
            (workspace_id, org_id)
        ).fetchone()
        if not ws:
            raise HTTPException(404, "Workspace not found")

        updated = conn.execute(
            """UPDATE workspace_members SET role = ?
               WHERE workspace_id = ? AND employee_id = ?""",
            (body.role, workspace_id, employee_id)
        ).rowcount
        if not updated:
            raise HTTPException(404, "Member not found in this workspace")

    return {"workspace_id": workspace_id, "employee_id": employee_id, "role": body.role}


@router.delete("/{workspace_id}/members/{employee_id}")
def remove_member(
    workspace_id: str,
    employee_id: str,
    org_id: str = Depends(authenticate),
):
    with get_db() as conn:
        ws = conn.execute(
            "SELECT workspace_id, owner_id FROM workspaces WHERE workspace_id = ? AND org_id = ?",
            (workspace_id, org_id)
        ).fetchone()
        if not ws:
            raise HTTPException(404, "Workspace not found")
        if ws["owner_id"] == employee_id:
            raise HTTPException(400, "Cannot remove the workspace owner")

        deleted = conn.execute(
            "DELETE FROM workspace_members WHERE workspace_id = ? AND employee_id = ?",
            (workspace_id, employee_id)
        ).rowcount
        if not deleted:
            raise HTTPException(404, "Member not found")

    return {"removed": True}
