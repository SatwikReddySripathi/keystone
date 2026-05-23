"""
Agent registry — first-class agents with owner, permissions, and rate limits.

GET    /v1/agents                      — List registered agents (filter by workspace)
POST   /v1/agents                      — Register a new agent
GET    /v1/agents/{id}                 — Agent detail + owner + recent runs + stats
PATCH  /v1/agents/{id}                 — Update status, permissions, rate limit, owner
DELETE /v1/agents/{id}                 — Revoke (soft-delete, status = 'revoked')
GET    /v1/agents/{id}/runs            — Recent actions proposed by this agent
"""
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel
from typing import Optional

from app.auth import authenticate
from app.db import get_db


# Fields on an agent that change its lifecycle (pause/resume/revoke).
# Writing to any of these requires the stricter "manager" permission.
LIFECYCLE_FIELDS = {"status"}
# All other fields stay under the general admin permission.


def _can_manage_agent_lifecycle(
    conn, org_id: str, agent_id: str, employee_id: str
) -> tuple[bool, str]:
    """
    Permission to pause/resume/revoke an agent:
      1. Owner of the agent, OR
      2. Workspace admin (role='admin' in agents.workspace_id) or global admin, OR
      3. Explicit collaborator with role='manager' (designated by admin)

    Collaborators without 'manager' role can only approve actions, not change
    lifecycle. Non-collaborators can do neither.
    """
    emp = conn.execute(
        "SELECT employee_id, is_admin, active FROM approvers WHERE employee_id = ?",
        (employee_id,)
    ).fetchone()
    if not emp or not emp["active"]:
        return (False, "Not an active employee")

    agent = conn.execute(
        "SELECT owner_employee_id, workspace_id FROM agents WHERE agent_id = ? AND org_id = ?",
        (agent_id, org_id)
    ).fetchone()
    if not agent:
        return (False, "Agent not found")

    if agent["owner_employee_id"] == employee_id:
        return (True, "Agent owner")

    if bool(emp["is_admin"]):
        return (True, "Global admin")

    # Workspace admin of the agent's workspace
    if agent["workspace_id"]:
        wsm = conn.execute(
            "SELECT role FROM workspace_members WHERE workspace_id = ? AND employee_id = ?",
            (agent["workspace_id"], employee_id)
        ).fetchone()
        if wsm and wsm["role"] == "admin":
            return (True, "Workspace admin")

    # Manager collaborator
    collab = conn.execute(
        "SELECT role FROM agent_collaborators WHERE agent_id = ? AND employee_id = ?",
        (agent_id, employee_id)
    ).fetchone()
    if collab and collab["role"] == "manager":
        return (True, "Agent manager")

    return (False, "Only the agent owner, a workspace admin, or a designated manager can change lifecycle")

router = APIRouter(prefix="/v1/agents", tags=["agents"])


class AgentCreate(BaseModel):
    agent_id: str
    name: str
    description: Optional[str] = None
    workspace_id: Optional[str] = None
    owner_employee_id: Optional[str] = None
    permissions: dict = {}          # {"tools":[...], "action_types":[...]}
    rate_limit_per_hour: Optional[int] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    workspace_id: Optional[str] = None
    owner_employee_id: Optional[str] = None
    status: Optional[str] = None    # active | paused | revoked | pending_registration
    permissions: Optional[dict] = None
    rate_limit_per_hour: Optional[int] = None


class AgentRegisterBody(BaseModel):
    workspace_id: str
    owner_employee_id: str
    permissions: dict = {}         # {"tools":[...], "action_types":[...]}
    rate_limit_per_hour: Optional[int] = None
    description: Optional[str] = None


def _parse_agent(row, conn=None) -> dict:
    d = dict(row)
    try:
        d["permissions"] = json.loads(d.pop("permissions_json") or "{}")
    except Exception:
        d["permissions"] = {}
        d.pop("permissions_json", None)
    if conn and d.get("owner_employee_id"):
        owner = conn.execute(
            "SELECT name, designation, department, email FROM approvers WHERE employee_id = ?",
            (d["owner_employee_id"],)
        ).fetchone()
        d["owner"] = dict(owner) if owner else None
    if conn and d.get("workspace_id"):
        ws = conn.execute(
            "SELECT name FROM workspaces WHERE workspace_id = ?",
            (d["workspace_id"],)
        ).fetchone()
        d["workspace_name"] = ws["name"] if ws else None
    return d


# ── List ────────────────────────────────────────────────
@router.get("")
def list_agents(
    org_id: str = Depends(authenticate),
    workspace_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    with get_db() as conn:
        sql = "SELECT * FROM agents WHERE org_id = ?"
        params: list = [org_id]
        if workspace_id:
            sql += " AND workspace_id = ?"
            params.append(workspace_id)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC"
        rows = conn.execute(sql, params).fetchall()

        result = []
        for row in rows:
            agent = _parse_agent(row, conn)
            total = conn.execute(
                """SELECT COUNT(*) as cnt FROM actions
                   WHERE org_id = ? AND json_extract(actor_json, '$.id') = ?""",
                (org_id, agent["agent_id"])
            ).fetchone()["cnt"]
            last = conn.execute(
                """SELECT created_at FROM actions
                   WHERE org_id = ? AND json_extract(actor_json, '$.id') = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (org_id, agent["agent_id"])
            ).fetchone()
            agent["total_runs"] = total
            agent["last_run_at"] = last["created_at"] if last else None
            result.append(agent)
        return result


# ── Create ──────────────────────────────────────────────
@router.post("")
def create_agent(body: AgentCreate, org_id: str = Depends(authenticate)):
    with get_db() as conn:
        if body.workspace_id:
            ws = conn.execute(
                "SELECT workspace_id FROM workspaces WHERE workspace_id = ? AND org_id = ?",
                (body.workspace_id, org_id)
            ).fetchone()
            if not ws:
                raise HTTPException(404, "Workspace not found")
        if body.owner_employee_id:
            owner = conn.execute(
                "SELECT employee_id FROM approvers WHERE employee_id = ?",
                (body.owner_employee_id,)
            ).fetchone()
            if not owner:
                raise HTTPException(404, f"Approver {body.owner_employee_id} not found")

        try:
            conn.execute(
                """INSERT INTO agents
                   (agent_id, org_id, workspace_id, name, description,
                    owner_employee_id, status, permissions_json, rate_limit_per_hour)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (body.agent_id, org_id, body.workspace_id, body.name,
                 body.description, body.owner_employee_id, "active",
                 json.dumps(body.permissions or {}),
                 body.rate_limit_per_hour)
            )
        except Exception:
            raise HTTPException(409, f"Agent {body.agent_id} already exists")

    return {"agent_id": body.agent_id, "name": body.name, "status": "active"}


# ── Detail ──────────────────────────────────────────────
@router.get("/{agent_id}")
def get_agent(
    agent_id: str,
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM agents WHERE agent_id = ? AND org_id = ?",
            (agent_id, org_id)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Agent not found")

        agent = _parse_agent(row, conn)

        # Tell the UI whether the signed-in user can change this agent's
        # lifecycle (pause/resume/revoke). Backend still re-checks on write.
        if x_employee_id:
            allowed, reason = _can_manage_agent_lifecycle(conn, org_id, agent_id, x_employee_id)
            agent["can_manage_lifecycle"] = allowed
            agent["lifecycle_permission_reason"] = reason
        else:
            agent["can_manage_lifecycle"] = False
            agent["lifecycle_permission_reason"] = "Not signed in"

        # Stats: count by status
        status_rows = conn.execute(
            """SELECT status, COUNT(*) as cnt FROM actions
               WHERE org_id = ? AND json_extract(actor_json, '$.id') = ?
               GROUP BY status""",
            (org_id, agent_id)
        ).fetchall()
        sc = {r["status"]: r["cnt"] for r in status_rows}

        agent["stats"] = {
            "total_runs":        sum(sc.values()),
            "completed":         sc.get("completed", 0),
            "blocked":           sc.get("blocked", 0),
            "contained":         sc.get("contained", 0),
            "awaiting_approval": sc.get("awaiting_approval", 0),
        }

        # Recent runs
        recent = conn.execute(
            """SELECT action_id, status, tool, action_type, created_at
               FROM actions
               WHERE org_id = ? AND json_extract(actor_json, '$.id') = ?
               ORDER BY created_at DESC LIMIT 20""",
            (org_id, agent_id)
        ).fetchall()
        agent["recent_runs"] = [dict(r) for r in recent]

        return agent


# ── Update ──────────────────────────────────────────────
@router.patch("/{agent_id}")
def update_agent(
    agent_id: str,
    body: AgentUpdate,
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    if not x_employee_id:
        raise HTTPException(401, "Not signed in")

    # If the caller is changing lifecycle (status), enforce manager permission
    touching_lifecycle = body.status is not None
    with get_db() as conn:
        row = conn.execute(
            "SELECT agent_id FROM agents WHERE agent_id = ? AND org_id = ?",
            (agent_id, org_id)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Agent not found")

        if touching_lifecycle:
            allowed, reason = _can_manage_agent_lifecycle(conn, org_id, agent_id, x_employee_id)
            if not allowed:
                raise HTTPException(403, f"Cannot change agent lifecycle: {reason}")

        fields = []
        params: list = []
        if body.name is not None:
            fields.append("name = ?"); params.append(body.name)
        if body.description is not None:
            fields.append("description = ?"); params.append(body.description)
        if body.workspace_id is not None:
            ws = conn.execute(
                "SELECT workspace_id FROM workspaces WHERE workspace_id = ? AND org_id = ?",
                (body.workspace_id, org_id)
            ).fetchone()
            if not ws:
                raise HTTPException(404, "Workspace not found")
            fields.append("workspace_id = ?"); params.append(body.workspace_id)
        if body.owner_employee_id is not None:
            fields.append("owner_employee_id = ?"); params.append(body.owner_employee_id)
        if body.status is not None:
            if body.status not in ("active", "paused", "revoked"):
                raise HTTPException(400, "status must be active, paused, or revoked")
            fields.append("status = ?"); params.append(body.status)
        if body.permissions is not None:
            fields.append("permissions_json = ?"); params.append(json.dumps(body.permissions))
        if body.rate_limit_per_hour is not None:
            fields.append("rate_limit_per_hour = ?"); params.append(body.rate_limit_per_hour)

        if not fields:
            return {"agent_id": agent_id, "updated": False}

        params.extend([agent_id, org_id])
        conn.execute(
            f"UPDATE agents SET {', '.join(fields)} WHERE agent_id = ? AND org_id = ?",
            params
        )

    return {"agent_id": agent_id, "updated": True}


# ── Register (move pending_registration → active) ─────────
@router.post("/{agent_id}/register")
def register_agent(
    agent_id: str,
    body: AgentRegisterBody,
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    """
    Approve an auto-registered agent: assign its workspace, owner, and
    permissions, flipping status to 'active'. Only admins of the target
    workspace (or global admins) can register an agent.
    """
    if not x_employee_id:
        raise HTTPException(401, "Not signed in")

    with get_db() as conn:
        agent = conn.execute(
            "SELECT agent_id, status FROM agents WHERE agent_id = ? AND org_id = ?",
            (agent_id, org_id)
        ).fetchone()
        if not agent:
            raise HTTPException(404, "Agent not found")

        # Verify the target workspace belongs to the org + caller is its admin
        ws = conn.execute(
            "SELECT workspace_id, owner_id FROM workspaces WHERE workspace_id = ? AND org_id = ?",
            (body.workspace_id, org_id)
        ).fetchone()
        if not ws:
            raise HTTPException(404, f"Workspace {body.workspace_id} not found")

        # Admin gate: global admin, workspace owner, or workspace admin role
        emp = conn.execute(
            "SELECT is_admin FROM approvers WHERE employee_id = ?",
            (x_employee_id,)
        ).fetchone()
        is_global_admin = bool(emp and emp["is_admin"])
        is_ws_owner = ws["owner_id"] == x_employee_id
        is_ws_admin_member = bool(conn.execute(
            "SELECT 1 FROM workspace_members WHERE workspace_id = ? AND employee_id = ? AND role = 'admin'",
            (body.workspace_id, x_employee_id)
        ).fetchone())
        if not (is_global_admin or is_ws_owner or is_ws_admin_member):
            raise HTTPException(403, "Only a workspace admin can register agents into that workspace")

        # Verify the chosen owner is a real active employee (ideally a member of the ws)
        owner = conn.execute(
            "SELECT employee_id FROM approvers WHERE employee_id = ? AND active = 1",
            (body.owner_employee_id,)
        ).fetchone()
        if not owner:
            raise HTTPException(404, f"Owner employee {body.owner_employee_id} not found")

        conn.execute(
            """UPDATE agents SET
                 workspace_id = ?,
                 owner_employee_id = ?,
                 permissions_json = ?,
                 rate_limit_per_hour = ?,
                 description = COALESCE(?, description),
                 status = 'active'
               WHERE agent_id = ? AND org_id = ?""",
            (body.workspace_id, body.owner_employee_id,
             json.dumps(body.permissions or {}),
             body.rate_limit_per_hour, body.description,
             agent_id, org_id)
        )

        return {
            "agent_id": agent_id,
            "status": "active",
            "workspace_id": body.workspace_id,
            "owner_employee_id": body.owner_employee_id,
        }


# ── Revoke ──────────────────────────────────────────────
@router.delete("/{agent_id}")
def revoke_agent(
    agent_id: str,
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    if not x_employee_id:
        raise HTTPException(401, "Not signed in")
    with get_db() as conn:
        allowed, reason = _can_manage_agent_lifecycle(conn, org_id, agent_id, x_employee_id)
        if not allowed:
            raise HTTPException(403, f"Cannot revoke: {reason}")
        updated = conn.execute(
            "UPDATE agents SET status = 'revoked' WHERE agent_id = ? AND org_id = ?",
            (agent_id, org_id)
        ).rowcount
        if not updated:
            raise HTTPException(404, "Agent not found")
    return {"agent_id": agent_id, "status": "revoked"}


# ── Activity ────────────────────────────────────────────
@router.get("/{agent_id}/runs")
def list_agent_runs(
    agent_id: str,
    org_id: str = Depends(authenticate),
    limit: int = Query(50),
):
    with get_db() as conn:
        agent = conn.execute(
            "SELECT agent_id FROM agents WHERE agent_id = ? AND org_id = ?",
            (agent_id, org_id)
        ).fetchone()
        if not agent:
            raise HTTPException(404, "Agent not found")

        rows = conn.execute(
            """SELECT action_id, status, tool, action_type, workspace_id,
                      connection_id, created_at, mode
               FROM actions
               WHERE org_id = ? AND json_extract(actor_json, '$.id') = ?
               ORDER BY created_at DESC LIMIT ?""",
            (org_id, agent_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]
