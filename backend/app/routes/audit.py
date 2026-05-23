"""
Audit log routes — full attribution trail for every governed action.

GET /v1/audit                    — Filtered list with full attribution
GET /v1/audit/{action_id}        — Single entry detail
GET /v1/audit/export/csv         — CSV download (same filters)
GET /v1/audit/export/json-proofs — Signed proof receipts as JSON download
"""
import csv
import io
import json
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from typing import Optional

from app.auth import authenticate
from app.db import get_db

router = APIRouter(prefix="/v1/audit", tags=["audit"])


# ── Core query ────────────────────────────────────────
def _audit_query(conn, org_id: str, filters: dict) -> list[dict]:
    """
    Join actions + decisions + approvals + previews + proofs into
    one flat audit record per action, with full attribution.
    """
    where = ["a.org_id = ?"]
    params: list = [org_id]

    if filters.get("date_from"):
        where.append("a.created_at >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        where.append("a.created_at <= ?")
        params.append(filters["date_to"])
    if filters.get("status"):
        where.append("a.status = ?")
        params.append(filters["status"])
    if filters.get("tool"):
        where.append("a.tool = ?")
        params.append(filters["tool"])
    if filters.get("workspace_id"):
        where.append("a.workspace_id = ?")
        params.append(filters["workspace_id"])
    if filters.get("agent"):
        where.append("json_extract(a.actor_json, '$.name') LIKE ?")
        params.append(f"%{filters['agent']}%")
    if filters.get("decision"):
        where.append("d.decision = ?")
        params.append(filters["decision"])

    limit = min(int(filters.get("limit", 100)), 500)
    offset = int(filters.get("offset", 0))

    # Subquery joins: each action has at most 1 row per related table.
    # If a relation has multiple rows (e.g. multiple approvals), take the latest by rowid.
    sql = f"""
        SELECT
            a.action_id,
            a.created_at       AS timestamp,
            a.status,
            a.tool,
            a.action_type,
            a.mode,
            a.environment,
            a.actor_json,
            a.workspace_id,
            a.client_ip,
            d.decision,
            d.policy_id,
            d.policy_version,
            d.reasons_json,
            p.blast_radius_json,
            apr.approver_json,
            apr.channel        AS approval_channel,
            apr.created_at     AS approved_at,
            pr.signature
        FROM actions a
        LEFT JOIN (
            SELECT action_id, decision, policy_id, policy_version, reasons_json
            FROM decisions
            WHERE id IN (SELECT MAX(id) FROM decisions GROUP BY action_id)
        ) d ON a.action_id = d.action_id
        LEFT JOIN (
            SELECT action_id, blast_radius_json FROM previews
            WHERE id IN (SELECT MAX(id) FROM previews GROUP BY action_id)
        ) p ON a.action_id = p.action_id
        LEFT JOIN (
            SELECT action_id, approver_json, channel, created_at FROM approvals
            WHERE id IN (SELECT MAX(id) FROM approvals GROUP BY action_id)
        ) apr ON a.action_id = apr.action_id
        LEFT JOIN (
            SELECT action_id, signature FROM proofs
            WHERE id IN (SELECT MAX(id) FROM proofs GROUP BY action_id)
        ) pr ON a.action_id = pr.action_id
        WHERE {" AND ".join(where)}
        GROUP BY a.action_id
        ORDER BY a.created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    rows = conn.execute(sql, params).fetchall()

    results = []
    for r in rows:
        d = dict(r)

        actor = {}
        try:
            actor = json.loads(d.pop("actor_json") or "{}")
        except Exception:
            d.pop("actor_json", None)

        approver_raw = {}
        try:
            approver_raw = json.loads(d.pop("approver_json") or "{}")
        except Exception:
            d.pop("approver_json", None)

        blast_radius = 0
        try:
            br = json.loads(d.pop("blast_radius_json") or "{}")
            blast_radius = br.get("count", 0)
        except Exception:
            d.pop("blast_radius_json", None)

        reasons = []
        try:
            reasons = json.loads(d.pop("reasons_json") or "[]")
        except Exception:
            d.pop("reasons_json", None)

        # Enrich approver with full employee record if matched
        full_approver = None
        if approver_raw.get("id"):
            emp = conn.execute(
                """SELECT name, email, designation, department
                   FROM approvers WHERE employee_id = ?""",
                (approver_raw["id"],)
            ).fetchone()
            if emp:
                full_approver = {
                    "id": approver_raw["id"],
                    **dict(emp),
                    "channel": d.pop("approval_channel", None),
                    "approved_at": d.pop("approved_at", None),
                }
            else:
                d.pop("approval_channel", None)
                d.pop("approved_at", None)
        else:
            d.pop("approval_channel", None)
            d.pop("approved_at", None)

        # Workspace name
        workspace_name = None
        if d.get("workspace_id"):
            ws_row = conn.execute(
                "SELECT name FROM workspaces WHERE workspace_id = ?",
                (d["workspace_id"],)
            ).fetchone()
            workspace_name = ws_row["name"] if ws_row else None

        # Objects touched: pull from executions subset_ids
        objects_touched = []
        exec_rows = conn.execute(
            "SELECT subset_ids_json FROM executions WHERE action_id = ?",
            (d["action_id"],)
        ).fetchall()
        for ex in exec_rows:
            try:
                objects_touched.extend(json.loads(ex["subset_ids_json"] or "[]"))
            except Exception:
                pass

        results.append({
            "action_id":      d["action_id"],
            "timestamp":      d["timestamp"],
            "status":         d["status"],
            "tool":           d["tool"],
            "action_type":    d["action_type"],
            "mode":           d["mode"],
            "environment":    d["environment"],
            "workspace_id":   d["workspace_id"],
            "workspace_name": workspace_name,
            "client_ip":      d["client_ip"],
            "agent": {
                "id":   actor.get("id"),
                "name": actor.get("name"),
                "type": actor.get("type"),
            },
            "governance": {
                "decision":       d["decision"],
                "policy_id":      d["policy_id"],
                "policy_version": d["policy_version"],
                "reasons":        reasons,
                "blast_radius":   blast_radius,
            },
            "approver":       full_approver,
            "objects_touched": objects_touched,
            "proof_signature": d["signature"],
        })

    return results


# ── List ──────────────────────────────────────────────
@router.get("")
def list_audit(
    org_id: str = Depends(authenticate),
    date_from:    Optional[str] = Query(None),
    date_to:      Optional[str] = Query(None),
    status:       Optional[str] = Query(None),
    tool:         Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
    agent:        Optional[str] = Query(None),
    decision:     Optional[str] = Query(None),
    limit:        int = Query(100),
    offset:       int = Query(0),
):
    with get_db() as conn:
        return _audit_query(conn, org_id, {
            "date_from": date_from, "date_to": date_to,
            "status": status, "tool": tool,
            "workspace_id": workspace_id, "agent": agent,
            "decision": decision, "limit": limit, "offset": offset,
        })


# ── Single detail ─────────────────────────────────────
@router.get("/entry/{action_id}")
def get_audit_entry(action_id: str, org_id: str = Depends(authenticate)):
    with get_db() as conn:
        results = _audit_query(conn, org_id, {"limit": 1, "offset": 0})
        # Re-query for specific action
        sql = """
            SELECT a.*, d.decision, d.policy_id, d.policy_version,
                   d.reasons_json, p.blast_radius_json,
                   apr.approver_json, apr.channel, apr.created_at as approved_at,
                   pr.signature
            FROM actions a
            LEFT JOIN decisions d   ON a.action_id = d.action_id
            LEFT JOIN previews  p   ON a.action_id = p.action_id
            LEFT JOIN approvals apr ON a.action_id = apr.action_id
            LEFT JOIN proofs    pr  ON a.action_id = pr.action_id
            WHERE a.action_id = ? AND a.org_id = ?
        """
        row = conn.execute(sql, (action_id, org_id)).fetchone()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(404, "Action not found")

        entries = _audit_query(conn, org_id, {"limit": 1, "offset": 0})

    # Just delegate to list with a temp workaround — filter inline
    with get_db() as conn:
        all_entries = _audit_query(conn, org_id, {"limit": 500, "offset": 0})
    matched = [e for e in all_entries if e["action_id"] == action_id]
    if not matched:
        from fastapi import HTTPException
        raise HTTPException(404, "Action not found")
    return matched[0]


# ── CSV Export ────────────────────────────────────────
@router.get("/export/csv")
def export_csv(
    org_id: str = Depends(authenticate),
    date_from:    Optional[str] = Query(None),
    date_to:      Optional[str] = Query(None),
    status:       Optional[str] = Query(None),
    tool:         Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
    agent:        Optional[str] = Query(None),
    decision:     Optional[str] = Query(None),
):
    with get_db() as conn:
        rows = _audit_query(conn, org_id, {
            "date_from": date_from, "date_to": date_to,
            "status": status, "tool": tool,
            "workspace_id": workspace_id, "agent": agent,
            "decision": decision, "limit": 500, "offset": 0,
        })

    def generate():
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=[
            "timestamp", "action_id", "status", "tool", "action_type",
            "mode", "environment", "workspace_name", "client_ip",
            "agent_id", "agent_name", "agent_type",
            "decision", "policy_id", "policy_version", "blast_radius",
            "approver_id", "approver_name", "approver_designation",
            "approver_department", "approval_channel", "approved_at",
            "objects_touched_count", "proof_signature",
        ])
        writer.writeheader()
        yield buf.getvalue()
        buf.truncate(0)
        buf.seek(0)

        for r in rows:
            approver = r.get("approver") or {}
            writer.writerow({
                "timestamp":            r["timestamp"],
                "action_id":            r["action_id"],
                "status":               r["status"],
                "tool":                 r["tool"],
                "action_type":          r["action_type"],
                "mode":                 r["mode"],
                "environment":          r["environment"],
                "workspace_name":       r.get("workspace_name") or "",
                "client_ip":            r.get("client_ip") or "",
                "agent_id":             r["agent"].get("id") or "",
                "agent_name":           r["agent"].get("name") or "",
                "agent_type":           r["agent"].get("type") or "",
                "decision":             r["governance"].get("decision") or "",
                "policy_id":            r["governance"].get("policy_id") or "",
                "policy_version":       r["governance"].get("policy_version") or "",
                "blast_radius":         r["governance"].get("blast_radius", 0),
                "approver_id":          approver.get("id") or "",
                "approver_name":        approver.get("name") or "",
                "approver_designation": approver.get("designation") or "",
                "approver_department":  approver.get("department") or "",
                "approval_channel":     approver.get("channel") or "",
                "approved_at":          approver.get("approved_at") or "",
                "objects_touched_count": len(r.get("objects_touched") or []),
                "proof_signature":      (r.get("proof_signature") or "")[:32],
            })
            yield buf.getvalue()
            buf.truncate(0)
            buf.seek(0)

    filename = f"keystone_audit_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── JSON Proofs Export ────────────────────────────────
@router.get("/export/json-proofs")
def export_json_proofs(
    org_id: str = Depends(authenticate),
    date_from:    Optional[str] = Query(None),
    date_to:      Optional[str] = Query(None),
    status:       Optional[str] = Query(None),
    tool:         Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
):
    with get_db() as conn:
        where = ["a.org_id = ?"]
        params: list = [org_id]
        if date_from:
            where.append("a.created_at >= ?")
            params.append(date_from)
        if date_to:
            where.append("a.created_at <= ?")
            params.append(date_to)
        if status:
            where.append("a.status = ?")
            params.append(status)
        if tool:
            where.append("a.tool = ?")
            params.append(tool)
        if workspace_id:
            where.append("a.workspace_id = ?")
            params.append(workspace_id)

        rows = conn.execute(
            f"""SELECT pr.action_id, pr.receipt_json, pr.signature, pr.created_at
                FROM proofs pr
                JOIN actions a ON pr.action_id = a.action_id
                WHERE {" AND ".join(where)}
                ORDER BY pr.created_at DESC
                LIMIT 500""",
            params
        ).fetchall()

        proofs = []
        for r in rows:
            try:
                receipt = json.loads(r["receipt_json"])
            except Exception:
                receipt = {}
            proofs.append({
                "action_id": r["action_id"],
                "created_at": r["created_at"],
                "signature": r["signature"],
                "receipt": receipt,
            })

    filename = f"keystone_proofs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    content = json.dumps({"exported_at": datetime.utcnow().isoformat(), "proofs": proofs}, indent=2)

    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
