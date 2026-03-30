"""
ServiceNow simulator connector.

25 seeded incidents that behave like a real ServiceNow incident table.
- Records 0-19: P3/P4, no VIP — the "safe" set for the PASS scenario
- Records 20-24: P1/P2, VIP callers — the "dangerous" set for the BLOCK scenario

NEW: Simulates ServiceNow business rules.
When state is set to "resolved", ServiceNow auto-populates resolved_at
and work_notes. This creates a side-effect that trips the
"only_intended_fields" post-check, demonstrating the circuit breaker
catching a real-world surprise.
"""
import copy
from datetime import datetime
from app.connectors.base import BaseConnector


# ── Seed Data ──────────────────────────────────────
INCIDENT_SEEDS = [
    # Records 0-19: Safe P3/P4 incidents
    ("open", "P3", "Network Ops",     False, "Wi-Fi intermittent in Building A"),
    ("open", "P3", "Network Ops",     False, "VPN timeout for remote users"),
    ("open", "P4", "Network Ops",     False, "DNS resolution slow"),
    ("open", "P4", "Desktop Support", False, "Printer offline Floor 3"),
    ("open", "P3", "Desktop Support", False, "Monitor flickering"),
    ("open", "P4", "Desktop Support", False, "Keyboard replacement needed"),
    ("open", "P3", "Server Team",     False, "Disk usage warning on app-srv-02"),
    ("open", "P4", "Server Team",     False, "Log rotation not running"),
    ("open", "P3", "Server Team",     False, "Backup job delayed"),
    ("open", "P4", "Network Ops",     False, "Switch port flapping"),
    ("open", "P3", "Network Ops",     False, "Firewall rule review needed"),
    ("open", "P4", "Desktop Support", False, "Software license expired"),
    ("open", "P3", "Desktop Support", False, "Email sync issue"),
    ("open", "P4", "Server Team",     False, "Test VM cleanup"),
    ("open", "P3", "Server Team",     False, "Certificate expiring soon"),
    ("open", "P3", "Network Ops",     False, "Load balancer health check flap"),
    ("open", "P4", "Network Ops",     False, "Unused VLAN cleanup"),
    ("open", "P3", "Desktop Support", False, "Outlook crash on startup"),
    ("open", "P4", "Desktop Support", False, "File share permission request"),
    ("open", "P3", "Server Team",     False, "Memory leak in staging app"),
    # Records 20-24: Dangerous P1/P2 + VIP incidents
    ("open", "P1", "Server Team",     True,  "Production DB replication lag - CEO impacted"),
    ("open", "P1", "Network Ops",     True,  "Core switch failure - CTO impacted"),
    ("open", "P2", "Server Team",     True,  "Payment gateway timeout - CFO impacted"),
    ("open", "P2", "Network Ops",     False, "Branch office connectivity lost"),
    ("open", "P1", "Desktop Support", True,  "Executive laptop compromised"),
]

SEED_INCIDENTS = [
    {
        "sys_id": f"inc_{i:04d}",
        "number": f"INC{10000 + i}",
        "state": state,
        "priority": priority,
        "assignment_group": group,
        "caller_vip": vip,
        "short_description": desc,
        "resolved_at": None,
        "work_notes": "",
        "updated_at": "2025-01-15T10:00:00Z",
    }
    for i, (state, priority, group, vip, desc) in enumerate(INCIDENT_SEEDS)
]


class ServiceNowSimulator(BaseConnector):
    """
    In-memory ServiceNow simulator.
    Includes business rule simulation: resolving an incident
    auto-populates resolved_at and work_notes (side effect).
    """

    def __init__(self):
        self._data = {r["sys_id"]: copy.deepcopy(r) for r in SEED_INCIDENTS}

    def reset(self):
        """Reset to seed data."""
        self._data = {r["sys_id"]: copy.deepcopy(r) for r in SEED_INCIDENTS}

    def query(self, filters: dict) -> list[dict]:
        results = []
        for rec in self._data.values():
            if self._matches(rec, filters):
                results.append(copy.deepcopy(rec))
        return sorted(results, key=lambda r: r["sys_id"])

    def compute_diffs(self, records: list[dict], changes: dict) -> list[dict]:
        """
        Compute what WOULD change. Read-only, no side effects.
        Note: this does NOT predict business rule side effects.
        That's the point — the preview shows intended changes,
        but reality includes side effects that checks catch.
        """
        diffs = []
        for rec in records:
            diff = {
                "sys_id": rec["sys_id"],
                "number": rec["number"],
                "fields": {}
            }
            for field, new_val in changes.items():
                old_val = rec.get(field)
                if old_val != new_val:
                    diff["fields"][field] = {"before": old_val, "after": new_val}
            diffs.append(diff)
        return diffs

    def execute_update(self, sys_ids: list[str], changes: dict, metadata: dict | None = None) -> list[dict]:
        """
        Apply changes to records. Returns per-record results.

        BUSINESS RULE SIMULATION:
        When state is set to "resolved", ServiceNow auto-populates:
          - resolved_at: current timestamp
          - work_notes: "Auto-resolved by bulk action"
        These are NOT in the intended changes, so the post-check
        "only_intended_fields" will detect them and trip the breaker.

        Also detects VIP/P1 state changes for other checks.
        """
        results = []
        for sid in sys_ids:
            rec = self._data.get(sid)
            if not rec:
                results.append({"sys_id": sid, "success": False, "error": "not_found"})
                continue

            # Track all fields that actually change
            fields_changed = []
            unexpected = {}

            # Apply intended changes
            for field, new_val in changes.items():
                rec[field] = new_val
                fields_changed.append(field)

                # Detect risky changes
                if rec.get("caller_vip") and field == "state":
                    unexpected["vip_state_changed"] = True
                if rec.get("priority") == "P1" and field == "state":
                    unexpected["p1_state_changed"] = True

            # ── BUSINESS RULE: state → "resolved" triggers side effects ──
            if changes.get("state") == "resolved":
                rec["resolved_at"] = datetime.utcnow().isoformat() + "Z"
                rec["work_notes"] = "Auto-resolved by bulk action"
                fields_changed.append("resolved_at")
                fields_changed.append("work_notes")

            rec["updated_at"] = datetime.utcnow().isoformat() + "Z"

            result = {
                "sys_id": sid,
                "success": True,
                "changes_applied": fields_changed,
            }
            if unexpected:
                result["unexpected_flags"] = unexpected
            results.append(result)

        return results

    def get_record(self, sys_id: str) -> dict | None:
        r = self._data.get(sys_id)
        return copy.deepcopy(r) if r else None

    def _matches(self, rec: dict, filters: dict) -> bool:
        for key, condition in filters.items():
            val = rec.get(key)
            if isinstance(condition, dict):
                op = condition.get("op", "eq")
                target = condition.get("value")
                if op == "eq" and val != target:
                    return False
                if op == "ne" and val == target:
                    return False
                if op == "in" and val not in target:
                    return False
                if op == "not_in" and val in target:
                    return False
            else:
                if val != condition:
                    return False
        return True


# Singleton
_connector = ServiceNowSimulator()

def get_connector() -> ServiceNowSimulator:
    return _connector