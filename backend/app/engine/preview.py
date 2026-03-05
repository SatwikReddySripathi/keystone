"""
Preview engine — blast radius, diffs, flags, deterministic preview_hash.

This is the "dry run" that shows what WOULD happen before anything executes.
The preview_hash is the most important output: it's a deterministic fingerprint
of the exact records + changes. Approvals bind to this hash, so if the
underlying data changes, the approval is invalidated.
"""
import hashlib
import json
from app.connectors.base import BaseConnector


def generate_preview(connector: BaseConnector, params: dict) -> dict:
    """
    Generate a full preview for an action.

    Input:
        connector: the tool connector (ServiceNow, Jira, etc.)
        params: {query: {...}, changes: {...}}

    Output: {
        blast_radius: int,
        breakdowns: {by_priority: {...}, by_assignment_group: {...}},
        diffs: [{sys_id, number, fields: {field: {before, after}}}],
        flags: {has_p1, has_vip, cross_group, state_transition, ...},
        target_ids: [sorted list of sys_ids],
        preview_hash: deterministic hash string
    }
    """
    query = params.get("query", {})
    changes = params.get("changes", {})

    # Step 1: Find all records that match the query
    records = connector.query(query)
    target_ids = sorted([r["sys_id"] for r in records])

    # Step 2: Compute diffs (read-only, no side effects)
    diffs = connector.compute_diffs(records, changes)

    # Step 3: Blast radius = simply how many records would be touched
    blast_radius = len(records)

    # Step 4: Breakdowns — group counts by key fields
    by_priority = {}
    by_group = {}
    for r in records:
        p = r.get("priority", "Unknown")
        g = r.get("assignment_group", "Unknown")
        by_priority[p] = by_priority.get(p, 0) + 1
        by_group[g] = by_group.get(g, 0) + 1

    breakdowns = {
        "by_priority": by_priority,
        "by_assignment_group": by_group,
    }

    # Step 5: Risk flags — conditions the policy engine will evaluate
    flags = {
        "has_p1": any(r.get("priority") == "P1" for r in records),
        "has_p2": any(r.get("priority") == "P2" for r in records),
        "has_vip": any(r.get("caller_vip") for r in records),
        "cross_group": len(by_group) > 1,
        "state_transition": "state" in changes,
        "fields_changed": list(changes.keys()),
    }

    # Step 6: Deterministic preview_hash
    # This is the fingerprint. Same query + same targets + same changes
    # ALWAYS produces the same hash. This is what approvals bind to.
    hash_input = json.dumps({
        "query": query,
        "target_ids": target_ids,
        "changes": changes,
    }, sort_keys=True)
    preview_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:32]

    return {
        "blast_radius": blast_radius,
        "breakdowns": breakdowns,
        "diffs": diffs,
        "flags": flags,
        "target_ids": target_ids,
        "preview_hash": preview_hash,
    }