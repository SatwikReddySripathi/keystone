"""
Real ServiceNow connector.

Connects to a live ServiceNow Developer Instance via the Table REST API.

Required env vars (set in backend/.env):
  SNOW_INSTANCE   — instance name only, e.g. "dev123456"
                    (not the full URL — we build it as dev123456.service-now.com)
  SNOW_USERNAME   — developer instance admin username
  SNOW_PASSWORD   — developer instance admin password

Get a free dev instance at: https://developer.servicenow.com

Filter format accepted by query():
  {"state": "open"}
  {"priority": {"op": "in", "value": ["3", "4"]}}
  {"state": {"op": "ne", "value": "resolved"}}

Keystone priority/state values vs ServiceNow numeric codes:
  P1 ↔ 1 (Critical), P2 ↔ 2 (High), P3 ↔ 3 (Moderate), P4 ↔ 4 (Low)
  new ↔ 1, in_progress ↔ 2, on_hold ↔ 3, resolved ↔ 6, closed ↔ 7
"""
import os
import re
import requests
from datetime import datetime, timezone
from urllib.parse import quote
from app.connectors.base import BaseConnector

SYSPARM_FIELDS = (
    "sys_id,number,state,priority,urgency,assignment_group,"
    "caller_id,short_description,resolved_at,work_notes,sys_updated_on"
)

# ServiceNow numeric codes → Keystone internal strings
PRIORITY_MAP = {"1": "P1", "2": "P2", "3": "P3", "4": "P4", "5": "P5"}
STATE_MAP = {
    "1": "new",
    "2": "in_progress",
    "3": "on_hold",
    "6": "resolved",
    "7": "closed",
}

# Reverse: Keystone internal → ServiceNow numeric codes
PRIORITY_REVERSE = {v: k for k, v in PRIORITY_MAP.items()}
STATE_REVERSE = {v: k for k, v in STATE_MAP.items()}


class ServiceNowRealConnector(BaseConnector):
    """
    Real ServiceNow connector using the Table API.
    Normalizes all field values to match Keystone's internal format
    so the engine (preview, policy, canary, checks) stays tool-agnostic.
    """

    def __init__(self):
        instance = os.getenv("SNOW_INSTANCE", "").strip()
        username = os.getenv("SNOW_USERNAME", "").strip()
        password = os.getenv("SNOW_PASSWORD", "").strip()

        if not instance:
            raise RuntimeError(
                "SNOW_INSTANCE is not set. Add it to backend/.env.\n"
                "Get a free developer instance at https://developer.servicenow.com"
            )

        # Accept both bare instance name ("dev271195") and full URLs
        # ("https://dev271195.service-now.com/...") — extract subdomain either way
        m = re.match(r'https?://([^\.]+)\.service-now\.com', instance)
        if m:
            instance = m.group(1)

        self._base_url = f"https://{instance}.service-now.com/api/now/table/incident"
        self._auth = (username, password)
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # Fetch valid close_code value from THIS instance — hardcoded strings break
        # across different PDI configurations. Use the first value from the picklist.
        self._close_code = self._fetch_close_code(instance)

    def _fetch_close_code(self, instance: str) -> str:
        """
        Query this ServiceNow instance for the first valid close_code picklist value.
        Different PDIs can have different values — hardcoding "Solved (Permanently)"
        breaks when the instance uses a custom list.
        Falls back to the standard value if the query fails.
        """
        try:
            url = (
                f"https://{instance}.service-now.com/api/now/table/sys_choice"
                "?sysparm_query=name%3Dincident%5Eelement%3Dclose_code%5Einactive%3Dfalse"
                "&sysparm_fields=value&sysparm_limit=1"
            )
            resp = requests.get(url, auth=self._auth, headers=self._headers, timeout=10)
            if resp.ok:
                results = resp.json().get("result", [])
                if results:
                    return results[0].get("value", "Solved (Permanently)")
        except Exception:
            pass
        return "Solved (Permanently)"

    def query(self, filters: dict) -> list[dict]:
        """
        Query incidents from the real ServiceNow instance.
        Translates Keystone filter format to sysparm_query string.
        Returns normalized records.
        """
        sysparm_query = _build_sysparm_query(filters)
        url = f"{self._base_url}?sysparm_fields={SYSPARM_FIELDS}&sysparm_limit=200&sysparm_display_value=all"
        if sysparm_query:
            url += f"&sysparm_query={quote(sysparm_query)}"

        resp = requests.get(url, auth=self._auth, headers=self._headers, timeout=30)
        resp.raise_for_status()

        return [_normalize(r) for r in resp.json().get("result", [])]

    def compute_diffs(self, records: list[dict], changes: dict) -> list[dict]:
        """
        Compute what WOULD change without executing anything.
        Same logic as the sim connector — this is intentionally read-only.
        Does NOT predict business rule side-effects (that's the point).
        """
        diffs = []
        for rec in records:
            diff = {"sys_id": rec["sys_id"], "number": rec["number"], "fields": {}}
            for field, new_val in changes.items():
                old_val = rec.get(field)
                if old_val != new_val:
                    diff["fields"][field] = {"before": old_val, "after": new_val}
            diffs.append(diff)
        return diffs

    def execute_update(self, sys_ids: list[str], changes: dict, metadata: dict | None = None) -> list[dict]:
        """
        PATCH each record via the REST API.

        Workflow per record:
          1. Fetch before-state (for accurate diff computation)
          2. PATCH with ServiceNow-format changes
          3. Normalize the updated record
          4. Compute changes_applied = fields that actually differ
          5. Flag unexpected changes (business rule side-effects)
          6. Detect fields that were intended but NOT applied by ServiceNow

        ServiceNow silent-rejection note:
          Some state transitions require additional fields that ServiceNow won't
          tell you about — it just returns HTTP 200 without applying the change.
          The most common case: state=resolved requires close_code + close_notes.
          We auto-add defaults for these so the transition actually sticks.
        """
        # Always include close_code + close_notes.
        # Some ServiceNow instances have Data Policies that require Resolution code
        # on every update, not just resolved state. Including them is harmless for
        # in_progress / on_hold updates; for resolved it's required.
        augmented = dict(changes)
        augmented.setdefault("close_code",  self._close_code)
        augmented.setdefault("close_notes", "Resolved by Keystone automation")

        # Always append a work_notes attribution so every agent-driven change
        # has an audit trail visible in the ServiceNow activity log.
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        actor_name = (metadata or {}).get("actor_name", "Keystone Agent")
        action_id  = (metadata or {}).get("action_id", "")
        note_parts = [f"[Keystone Governance Engine] Automated update by {actor_name} at {ts}."]
        if action_id:
            note_parts.append(f"Action ID: {action_id}")
        field_summary = ", ".join(f"{k}={v}" for k, v in changes.items())
        note_parts.append(f"Changes applied: {field_summary}")
        augmented["work_notes"] = " | ".join(note_parts)

        # Convert Keystone internal values → ServiceNow numeric codes
        snow_changes = _to_snow_format(augmented)
        intended_fields = set(changes.keys())  # what the caller asked for (not augmented)

        results = []
        for sys_id in sys_ids:
            try:
                # Step 1: Fetch before-state
                before = self.get_record(sys_id)
                if before is None:
                    results.append({
                        "sys_id": sys_id,
                        "success": False,
                        "error": "Record not found",
                        "changes_applied": [],
                    })
                    continue

                # Step 2: PATCH the record.
                # work_notes requires the 'itil' role in ServiceNow.
                # If the PATCH returns 403, retry without work_notes so the
                # real changes still go through even if audit notes are blocked.
                # sysparm_display_value=all ensures the PATCH response uses the
                # same format as get_record() — reference fields return display
                # values (e.g. "Fred Luddy") not raw sys_ids, so the before/after
                # comparison doesn't false-flag caller_id as an unexpected change.
                url = f"{self._base_url}/{sys_id}?sysparm_display_value=all"
                resp = requests.patch(
                    url,
                    auth=self._auth,
                    headers=self._headers,
                    json=snow_changes,
                    timeout=30,
                )
                if resp.status_code == 403:
                    # work_notes requires the 'itil' role — strip it and retry.
                    # All other fields (including close_code for Data Policy) are kept.
                    snow_fallback = {k: v for k, v in snow_changes.items() if k != "work_notes"}
                    resp = requests.patch(
                        url,
                        auth=self._auth,
                        headers=self._headers,
                        json=snow_fallback,
                        timeout=30,
                    )
                resp.raise_for_status()

                # Step 3: Normalize after-state
                after = _normalize(resp.json().get("result", {}))

                # Step 4: Compute what actually changed
                changes_applied = []
                unexpected_flags = {}
                # work_notes is intentionally added by us (attribution) — skip it.
                # resolved_at / sys_updated_on are ServiceNow metadata — skip updated_at.
                skip_fields = {"sys_id", "number", "updated_at", "work_notes"}

                for field in set(list(before.keys()) + list(after.keys())):
                    if field in skip_fields:
                        continue
                    if before.get(field) != after.get(field):
                        changes_applied.append(field)
                        # Step 5: Flag unexpected changes (business rule side-effects)
                        if field not in intended_fields:
                            unexpected_flags[f"{field}_changed"] = True
                        # Risk flags for safety checks
                        if before.get("caller_vip") and field == "state":
                            unexpected_flags["vip_state_changed"] = True
                        if before.get("priority") == "P1" and field == "state":
                            unexpected_flags["p1_state_changed"] = True

                # Detect intended fields that ServiceNow silently did not apply.
                # This happens when ServiceNow returns HTTP 200 but ignores the change
                # (e.g. missing mandatory fields, state machine rules, business rules).
                fields_not_applied = sorted(
                    f for f in intended_fields
                    if f not in changes_applied and before.get(f) == after.get(f)
                )

                result = {
                    "sys_id": sys_id,
                    "number": before.get("number", sys_id),
                    "success": True,
                    "changes_applied": changes_applied,
                    # Actual values fetched from ServiceNow — not predicted from preview
                    "before_snapshot": {f: before.get(f) for f in changes_applied},
                    "after_snapshot":  {f: after.get(f)  for f in changes_applied},
                }
                if unexpected_flags:
                    result["unexpected_flags"] = unexpected_flags
                if fields_not_applied:
                    result["fields_not_applied"] = fields_not_applied
                    result["warning"] = (
                        f"ServiceNow did not apply: {', '.join(fields_not_applied)}. "
                        f"The values shown for these fields are predictions from the preview, "
                        f"not confirmed values from ServiceNow."
                    )
                results.append(result)

            except requests.HTTPError as e:
                results.append({
                    "sys_id": sys_id,
                    "success": False,
                    "error": f"HTTP {e.response.status_code}: {e.response.text[:300]}",
                    "changes_applied": [],
                })
            except Exception as e:
                results.append({
                    "sys_id": sys_id,
                    "success": False,
                    "error": str(e),
                    "changes_applied": [],
                })

        return results

    def get_record(self, sys_id: str) -> dict | None:
        """Fetch a single incident by sys_id. Returns normalized record or None."""
        url = f"{self._base_url}/{sys_id}?sysparm_fields={SYSPARM_FIELDS}&sysparm_display_value=all"
        resp = requests.get(url, auth=self._auth, headers=self._headers, timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        result = resp.json().get("result")
        return _normalize(result) if result else None


# ── Normalization helpers ──────────────────────────────

def _normalize(r: dict) -> dict:
    """
    Normalize a raw ServiceNow API record to Keystone's internal format.

    With sysparm_display_value=all, ServiceNow returns all fields as:
      {"value": "<raw_code>", "display_value": "<human_label>"}

    Strategy:
    - priority/state: use "value" (numeric code) for our mapping table
    - reference fields (assignment_group, caller_id): use "display_value" for readability
    - plain string fields (sys_id, number, etc.): use as-is
    """
    def raw_value(field_key):
        """Extract the raw coded value (for numeric/enum fields like priority, state)."""
        v = r.get(field_key, "")
        if isinstance(v, dict):
            return v.get("value") or ""
        return v or ""

    def display_value(field_key):
        """Extract the human-readable display value (for reference fields like group, caller)."""
        v = r.get(field_key, "")
        if isinstance(v, dict):
            return v.get("display_value") or v.get("value") or ""
        return v or ""

    raw_priority = raw_value("priority")
    raw_state = raw_value("state")

    return {
        "sys_id": raw_value("sys_id") or r.get("sys_id", ""),
        "number": raw_value("number") or r.get("number", ""),
        "state": STATE_MAP.get(str(raw_state), raw_state),
        "priority": PRIORITY_MAP.get(str(raw_priority), raw_priority),
        "urgency": raw_value("urgency") or None,
        "assignment_group": display_value("assignment_group"),
        "caller_id": display_value("caller_id"),
        # ServiceNow has no standard caller_vip field.
        # Extend this if your instance has a custom VIP field.
        "caller_vip": False,
        "short_description": raw_value("short_description"),
        "resolved_at": raw_value("resolved_at") or None,
        "work_notes": raw_value("work_notes"),
        "updated_at": raw_value("sys_updated_on"),
    }


def _to_snow_format(changes: dict) -> dict:
    """
    Convert Keystone internal values to ServiceNow numeric codes.
    e.g. {"state": "resolved"} → {"state": "6"}
         {"priority": "P3"}    → {"priority": "3"}
    """
    snow = {}
    for field, val in changes.items():
        if field == "priority" and val in PRIORITY_REVERSE:
            snow[field] = PRIORITY_REVERSE[val]
        elif field == "state" and val in STATE_REVERSE:
            snow[field] = STATE_REVERSE[val]
        else:
            snow[field] = val
    return snow


def _translate_filter_val(field: str, val) -> str:
    """
    Translate a Keystone internal filter value to a ServiceNow API value.
    state: "in_progress" → "2"   priority: "P3" → "3"
    Leaves unknown values untouched so raw numeric codes still work.
    """
    if field == "state" and isinstance(val, str):
        return STATE_REVERSE.get(val, val)
    if field == "priority" and isinstance(val, str):
        return PRIORITY_REVERSE.get(val, val)
    return val


def _build_sysparm_query(filters: dict) -> str:
    """
    Convert Keystone filter format to ServiceNow sysparm_query string.
    Also translates internal state/priority values to ServiceNow numeric codes.

    Examples:
      {"state": "in_progress"}
        → "state=2"
      {"priority": {"op": "in", "value": ["P3", "P4"]}}
        → "priority=3^ORpriority=4"
      {"priority": {"op": "in", "value": ["3", "4"]}}   (raw codes also work)
        → "priority=3^ORpriority=4"
      {"state": {"op": "ne", "value": "resolved"}}
        → "state!=6"
    """
    parts = []
    for field, condition in filters.items():
        if isinstance(condition, dict):
            op = condition.get("op", "eq")
            val = condition.get("value")
            if op == "eq":
                parts.append(f"{field}={_translate_filter_val(field, val)}")
            elif op == "ne":
                parts.append(f"{field}!={_translate_filter_val(field, val)}")
            elif op == "in" and isinstance(val, list):
                parts.append("^OR".join(f"{field}={_translate_filter_val(field, v)}" for v in val))
            elif op == "not_in" and isinstance(val, list):
                parts.append("^".join(f"{field}!={_translate_filter_val(field, v)}" for v in val))
            elif op == "gt":
                parts.append(f"{field}>{_translate_filter_val(field, val)}")
            elif op == "lt":
                parts.append(f"{field}<{_translate_filter_val(field, val)}")
            elif op == "gte":
                parts.append(f"{field}>={_translate_filter_val(field, val)}")
            elif op == "lte":
                parts.append(f"{field}<={_translate_filter_val(field, val)}")
        else:
            parts.append(f"{field}={_translate_filter_val(field, condition)}")
    return "^".join(parts)


def get_connector() -> ServiceNowRealConnector:
    return ServiceNowRealConnector()
