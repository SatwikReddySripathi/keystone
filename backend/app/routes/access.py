"""
Workspace access requests + agent ownership/collaboration management.

Employees self-request workspace access; workspace admins approve.
Workspace admins add/remove agent collaborators and transfer ownership.

Routes:
  POST   /v1/workspaces/{ws}/requests              — current user requests access
  GET    /v1/workspaces/{ws}/requests              — admin lists pending
  POST   /v1/workspaces/{ws}/requests/{id}/approve — admin approves
  POST   /v1/workspaces/{ws}/requests/{id}/deny    — admin denies
  GET    /v1/access-requests/mine                  — list my own requests
  GET    /v1/access-requests/pending-as-admin      — all pending in workspaces I admin

  POST   /v1/agents/{agent_id}/transfer-ownership  — admin sets new owner
  GET    /v1/agents/{agent_id}/collaborators       — list collaborators (owner included)
  POST   /v1/agents/{agent_id}/collaborators       — admin adds a collaborator
  DELETE /v1/agents/{agent_id}/collaborators/{emp} — admin removes a collaborator

Permission for admin actions: the acting employee must be is_admin OR a
workspace_member with role='admin' in the relevant workspace.
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from app.auth import authenticate
from app.db import get_db

router = APIRouter(prefix="/v1", tags=["access"])


# ── Payload models ─────────────────────────────────────────
class RequestAccessBody(BaseModel):
    role: str = "viewer"
    note: Optional[str] = None


class DecideRequestBody(BaseModel):
    role: Optional[str] = None  # override the requested role on approve


class AddCollaboratorBody(BaseModel):
    employee_id: str
    role: str = "collaborator"


class TransferOwnershipBody(BaseModel):
    new_owner_employee_id: str


# ── Helpers ─────────────────────────────────────────────────
def _require_signed_in(x_employee_id: Optional[str]) -> str:
    if not x_employee_id:
        raise HTTPException(401, "X-Employee-Id header missing — not signed in")
    return x_employee_id


def _is_workspace_admin(conn, workspace_id: str, employee_id: str, org_id: str) -> tuple[bool, str]:
    """
    A workspace's access decisions / agent management can be done by:
      - is_admin=1 employees (global admins), OR
      - workspace members with role='admin'
    Workspace owner (workspaces.owner_id) implicitly counts as admin.
    """
    emp = conn.execute(
        "SELECT employee_id, is_admin, active FROM approvers WHERE employee_id = ?",
        (employee_id,)
    ).fetchone()
    if not emp or not emp["active"]:
        return (False, "Not an active employee")

    # Workspace owner
    ws = conn.execute(
        "SELECT owner_id FROM workspaces WHERE workspace_id = ? AND org_id = ?",
        (workspace_id, org_id)
    ).fetchone()
    if not ws:
        return (False, "Workspace not found")
    if ws["owner_id"] == employee_id:
        return (True, "Workspace owner")

    # Workspace member with admin role
    mem = conn.execute(
        "SELECT role FROM workspace_members WHERE workspace_id = ? AND employee_id = ?",
        (workspace_id, employee_id)
    ).fetchone()
    if mem and mem["role"] == "admin":
        return (True, "Workspace admin member")

    # Global admin can also manage (they can still SEE everything; granting
    # access to a workspace they don't belong to is reasonable)
    if bool(emp["is_admin"]):
        return (True, "Global admin")

    return (False, "Not a workspace admin")


def _employee_summary(conn, employee_id: str) -> dict | None:
    row = conn.execute(
        """SELECT employee_id, name, email, designation, department
           FROM approvers WHERE employee_id = ?""",
        (employee_id,)
    ).fetchone()
    return dict(row) if row else None


# ── Workspace access requests ─────────────────────────────────────────
@router.post("/workspaces/{workspace_id}/requests")
def request_access(
    workspace_id: str,
    body: RequestAccessBody,
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    """Current signed-in user requests access to a workspace."""
    me = _require_signed_in(x_employee_id)
    if body.role not in ("viewer", "approver"):
        raise HTTPException(400, "role must be viewer or approver")

    with get_db() as conn:
        ws = conn.execute(
            "SELECT workspace_id FROM workspaces WHERE workspace_id = ? AND org_id = ?",
            (workspace_id, org_id)
        ).fetchone()
        if not ws:
            raise HTTPException(404, "Workspace not found")

        existing_membership = conn.execute(
            "SELECT role FROM workspace_members WHERE workspace_id = ? AND employee_id = ?",
            (workspace_id, me)
        ).fetchone()
        if existing_membership:
            raise HTTPException(409, f"Already a member (role: {existing_membership['role']})")

        existing_req = conn.execute(
            """SELECT id, status FROM workspace_access_requests
               WHERE workspace_id = ? AND employee_id = ?""",
            (workspace_id, me)
        ).fetchone()
        if existing_req and existing_req["status"] == "pending":
            raise HTTPException(409, "Access request already pending")

        if existing_req:
            # Re-open a previously denied request
            conn.execute(
                """UPDATE workspace_access_requests
                   SET status='pending', role=?, note=?, requested_at=datetime('now'),
                       decided_by_employee_id=NULL, decided_at=NULL
                   WHERE id=?""",
                (body.role, body.note, existing_req["id"])
            )
            return {"request_id": existing_req["id"], "status": "pending"}

        cur = conn.execute(
            """INSERT INTO workspace_access_requests
               (workspace_id, employee_id, role, note, status)
               VALUES (?,?,?,?,'pending')""",
            (workspace_id, me, body.role, body.note)
        )
        return {"request_id": cur.lastrowid, "status": "pending"}


@router.get("/workspaces/{workspace_id}/requests")
def list_workspace_requests(
    workspace_id: str,
    status: str = "pending",
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    """Admins see all requests for a workspace they manage."""
    me = _require_signed_in(x_employee_id)
    with get_db() as conn:
        allowed, reason = _is_workspace_admin(conn, workspace_id, me, org_id)
        if not allowed:
            raise HTTPException(403, reason)

        rows = conn.execute(
            """SELECT id, workspace_id, employee_id, role, note, status,
                      requested_at, decided_by_employee_id, decided_at
               FROM workspace_access_requests
               WHERE workspace_id = ? AND status = ?
               ORDER BY requested_at DESC""",
            (workspace_id, status)
        ).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["employee"] = _employee_summary(conn, d["employee_id"])
            if d["decided_by_employee_id"]:
                d["decided_by"] = _employee_summary(conn, d["decided_by_employee_id"])
            results.append(d)
        return results


@router.post("/workspaces/{workspace_id}/requests/{request_id}/approve")
def approve_access_request(
    workspace_id: str,
    request_id: int,
    body: DecideRequestBody = DecideRequestBody(),
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    me = _require_signed_in(x_employee_id)
    with get_db() as conn:
        allowed, reason = _is_workspace_admin(conn, workspace_id, me, org_id)
        if not allowed:
            raise HTTPException(403, reason)

        req = conn.execute(
            "SELECT * FROM workspace_access_requests WHERE id = ? AND workspace_id = ?",
            (request_id, workspace_id)
        ).fetchone()
        if not req:
            raise HTTPException(404, "Request not found")
        if req["status"] != "pending":
            raise HTTPException(400, f"Request already {req['status']}")

        role = body.role or req["role"] or "viewer"
        if role not in ("viewer", "approver", "admin"):
            raise HTTPException(400, "role must be viewer, approver, or admin")

        # Add to workspace_members (if not already)
        conn.execute(
            """INSERT OR IGNORE INTO workspace_members (workspace_id, employee_id, role)
               VALUES (?, ?, ?)""",
            (workspace_id, req["employee_id"], role)
        )
        conn.execute(
            """UPDATE workspace_access_requests
               SET status='approved', decided_by_employee_id=?, decided_at=?, role=?
               WHERE id=?""",
            (me, datetime.utcnow().isoformat(), role, request_id)
        )
        return {"request_id": request_id, "status": "approved", "role": role}


@router.post("/workspaces/{workspace_id}/requests/{request_id}/deny")
def deny_access_request(
    workspace_id: str,
    request_id: int,
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    me = _require_signed_in(x_employee_id)
    with get_db() as conn:
        allowed, reason = _is_workspace_admin(conn, workspace_id, me, org_id)
        if not allowed:
            raise HTTPException(403, reason)

        req = conn.execute(
            "SELECT status FROM workspace_access_requests WHERE id = ? AND workspace_id = ?",
            (request_id, workspace_id)
        ).fetchone()
        if not req:
            raise HTTPException(404, "Request not found")
        if req["status"] != "pending":
            raise HTTPException(400, f"Request already {req['status']}")

        conn.execute(
            """UPDATE workspace_access_requests
               SET status='denied', decided_by_employee_id=?, decided_at=?
               WHERE id=?""",
            (me, datetime.utcnow().isoformat(), request_id)
        )
        return {"request_id": request_id, "status": "denied"}


@router.get("/access-requests/mine")
def my_access_requests(
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    me = _require_signed_in(x_employee_id)
    with get_db() as conn:
        rows = conn.execute(
            """SELECT r.*, w.name AS workspace_name
               FROM workspace_access_requests r
               JOIN workspaces w ON r.workspace_id = w.workspace_id
               WHERE r.employee_id = ? AND w.org_id = ?
               ORDER BY r.requested_at DESC""",
            (me, org_id)
        ).fetchall()
        return [dict(r) for r in rows]


@router.get("/access-requests/pending-as-admin")
def pending_as_admin(
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    """Return all pending access requests across workspaces the caller admins.
    Powers the sidebar badge + a unified admin queue."""
    me = _require_signed_in(x_employee_id)
    with get_db() as conn:
        emp = conn.execute(
            "SELECT is_admin FROM approvers WHERE employee_id = ?", (me,)
        ).fetchone()
        is_global_admin = bool(emp["is_admin"]) if emp else False

        if is_global_admin:
            ws_filter = "r.workspace_id IN (SELECT workspace_id FROM workspaces WHERE org_id = ?)"
            params: list = [org_id]
        else:
            # Only workspaces they're admin of (membership role='admin' or owner_id)
            admin_ws = [
                r["workspace_id"] for r in conn.execute(
                    """SELECT workspace_id FROM workspace_members
                       WHERE employee_id = ? AND role = 'admin'""",
                    (me,)
                ).fetchall()
            ]
            owned_ws = [
                r["workspace_id"] for r in conn.execute(
                    "SELECT workspace_id FROM workspaces WHERE owner_id = ? AND org_id = ?",
                    (me, org_id)
                ).fetchall()
            ]
            all_ws = sorted(set(admin_ws + owned_ws))
            if not all_ws:
                return []
            placeholders = ",".join("?" for _ in all_ws)
            ws_filter = f"r.workspace_id IN ({placeholders})"
            params = list(all_ws)

        rows = conn.execute(
            f"""SELECT r.id, r.workspace_id, r.employee_id, r.role, r.note,
                       r.status, r.requested_at,
                       w.name AS workspace_name,
                       a.name AS requester_name, a.email AS requester_email,
                       a.designation AS requester_designation, a.department AS requester_department
                FROM workspace_access_requests r
                JOIN workspaces w ON r.workspace_id = w.workspace_id
                JOIN approvers a ON r.employee_id = a.employee_id
                WHERE r.status = 'pending' AND {ws_filter}
                ORDER BY r.requested_at DESC""",
            params
        ).fetchall()
        return [dict(r) for r in rows]


# ── Agent ownership + collaborators ─────────────────────────────────────────
def _agent_workspace_admin(conn, agent_id: str, employee_id: str, org_id: str) -> tuple[bool, str]:
    """Caller must be admin of the agent's workspace (or global admin)."""
    agent = conn.execute(
        "SELECT workspace_id FROM agents WHERE agent_id = ? AND org_id = ?",
        (agent_id, org_id)
    ).fetchone()
    if not agent:
        return (False, "Agent not found")
    if not agent["workspace_id"]:
        # Global agents: only global admins can manage
        emp = conn.execute(
            "SELECT is_admin FROM approvers WHERE employee_id = ?", (employee_id,)
        ).fetchone()
        if emp and bool(emp["is_admin"]):
            return (True, "Global admin")
        return (False, "Only global admins manage cross-workspace agents")
    return _is_workspace_admin(conn, agent["workspace_id"], employee_id, org_id)


@router.post("/agents/{agent_id}/transfer-ownership")
def transfer_ownership(
    agent_id: str,
    body: TransferOwnershipBody,
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    me = _require_signed_in(x_employee_id)
    with get_db() as conn:
        allowed, reason = _agent_workspace_admin(conn, agent_id, me, org_id)
        if not allowed:
            raise HTTPException(403, reason)

        new_owner = conn.execute(
            "SELECT employee_id, name FROM approvers WHERE employee_id = ? AND active = 1",
            (body.new_owner_employee_id,)
        ).fetchone()
        if not new_owner:
            raise HTTPException(404, "New owner not found")

        conn.execute(
            "UPDATE agents SET owner_employee_id = ? WHERE agent_id = ? AND org_id = ?",
            (body.new_owner_employee_id, agent_id, org_id)
        )
        return {
            "agent_id": agent_id,
            "new_owner": {"employee_id": new_owner["employee_id"], "name": new_owner["name"]},
        }


@router.get("/agents/{agent_id}/collaborators")
def list_collaborators(
    agent_id: str,
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    _require_signed_in(x_employee_id)
    with get_db() as conn:
        agent = conn.execute(
            """SELECT agent_id, owner_employee_id FROM agents
               WHERE agent_id = ? AND org_id = ?""",
            (agent_id, org_id)
        ).fetchone()
        if not agent:
            raise HTTPException(404, "Agent not found")

        rows = conn.execute(
            """SELECT c.id, c.employee_id, c.role, c.added_at, c.added_by_employee_id,
                      a.name, a.email, a.designation, a.department
               FROM agent_collaborators c
               JOIN approvers a ON c.employee_id = a.employee_id
               WHERE c.agent_id = ?
               ORDER BY c.added_at DESC""",
            (agent_id,)
        ).fetchall()

        owner = _employee_summary(conn, agent["owner_employee_id"]) if agent["owner_employee_id"] else None
        return {
            "owner": owner,
            "collaborators": [dict(r) for r in rows],
        }


@router.post("/agents/{agent_id}/collaborators")
def add_collaborator(
    agent_id: str,
    body: AddCollaboratorBody,
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    me = _require_signed_in(x_employee_id)
    if body.role not in ("collaborator", "manager", "co-owner"):
        raise HTTPException(400, "role must be collaborator, manager, or co-owner")

    with get_db() as conn:
        allowed, reason = _agent_workspace_admin(conn, agent_id, me, org_id)
        if not allowed:
            raise HTTPException(403, reason)

        emp = conn.execute(
            "SELECT employee_id, name FROM approvers WHERE employee_id = ? AND active = 1",
            (body.employee_id,)
        ).fetchone()
        if not emp:
            raise HTTPException(404, "Employee not found")

        try:
            conn.execute(
                """INSERT INTO agent_collaborators
                   (agent_id, employee_id, role, added_by_employee_id)
                   VALUES (?,?,?,?)""",
                (agent_id, body.employee_id, body.role, me)
            )
        except Exception:
            raise HTTPException(409, "Already a collaborator on this agent")

        return {
            "agent_id": agent_id,
            "collaborator": {"employee_id": emp["employee_id"], "name": emp["name"]},
            "role": body.role,
        }


@router.delete("/agents/{agent_id}/collaborators/{employee_id}")
def remove_collaborator(
    agent_id: str,
    employee_id: str,
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    org_id: str = Depends(authenticate),
):
    me = _require_signed_in(x_employee_id)
    with get_db() as conn:
        allowed, reason = _agent_workspace_admin(conn, agent_id, me, org_id)
        if not allowed:
            raise HTTPException(403, reason)

        removed = conn.execute(
            "DELETE FROM agent_collaborators WHERE agent_id = ? AND employee_id = ?",
            (agent_id, employee_id)
        ).rowcount
        if not removed:
            raise HTTPException(404, "Not a collaborator")
        return {"removed": True}
