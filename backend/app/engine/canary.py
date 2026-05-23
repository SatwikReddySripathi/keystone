"""
Canary execution — deterministic subset selection + post-checks.

The canary is the "test batch." Before updating all 20 records,
we update 5 first. If those 5 go well, we expand to the rest.

CRITICAL: The 5 records must be selected DETERMINISTICALLY.
Same action_id + same target set = same 5 records every time.
This means:
  - Auditors can verify which records were in the canary
  - Replaying the action produces the same subset
  - No randomness = no "it worked in my test but failed in yours"
"""
import hashlib


def select_canary_subset(
    action_id: str,
    target_ids: list[str],
    size: int = 5
) -> list[str]:
    """
    Deterministically select `size` records for canary.

    Algorithm: hash(action_id + sys_id) for each target,
    sort by hash, take the first `size`.

    Same action_id + same targets = same subset. Always.
    Different action_id = different subset (spreads risk across retries).
    """
    def sort_key(sys_id):
        return hashlib.sha256(f"{action_id}:{sys_id}".encode()).hexdigest()

    sorted_ids = sorted(target_ids, key=sort_key)
    return sorted_ids[:min(size, len(sorted_ids))]


def run_post_checks(
    action_id: str,
    canary_ids: list[str],
    results: list[dict],
    changes: dict,
    flags: dict,
    thresholds: dict,
) -> list[dict]:
    """
    Run post-execution checks on canary results.

    These are the safety gates. Each check answers one question:
    1. no_out_of_scope: Did we ONLY touch the records we intended to?
    2. only_intended_fields: Did we ONLY change the fields we specified?
    3. no_vip_state_change: Did any VIP records get their state changed?
    4. no_p1_state_change: Did any P1 records get their state changed?
    5. error_rate_ok: Is the error rate within threshold?

    Returns: list of {check_name, passed: bool, details: dict}
    """
    checks = []

    # ── Check 1: No out-of-scope changes ──
    # Only the canary IDs should have been touched
    result_ids = {r["sys_id"] for r in results}
    canary_set = set(canary_ids)
    out_of_scope = result_ids - canary_set
    checks.append({
        "check_name": "no_out_of_scope",
        "passed": len(out_of_scope) == 0,
        "details": {
            "expected_ids": sorted(canary_ids),
            "actual_ids": sorted(result_ids),
            "out_of_scope": sorted(out_of_scope) if out_of_scope else [],
        }
    })

    # ── Check 2: Only intended fields changed ──
    # If we said "change state", only state should have changed
    intended_fields = set(changes.keys())
    unintended = []
    for r in results:
        applied = set(r.get("changes_applied", []))
        extra = applied - intended_fields
        if extra:
            unintended.append({"sys_id": r["sys_id"], "extra_fields": sorted(extra)})
    checks.append({
        "check_name": "only_intended_fields",
        "passed": len(unintended) == 0,
        "details": {"unintended_changes": unintended}
    })

    # ── Check 3: No VIP state changes ──
    # If a VIP record's state was changed, that's a red flag
    vip_violations = [
        r["sys_id"] for r in results
        if r.get("unexpected_flags", {}).get("vip_state_changed")
    ]
    checks.append({
        "check_name": "no_vip_state_change",
        "passed": len(vip_violations) == 0,
        "details": {"vip_records_with_state_change": vip_violations}
    })

    # ── Check 4: No P1 state changes ──
    p1_violations = [
        r["sys_id"] for r in results
        if r.get("unexpected_flags", {}).get("p1_state_changed")
    ]
    checks.append({
        "check_name": "no_p1_state_change",
        "passed": len(p1_violations) == 0,
        "details": {"p1_records_with_state_change": p1_violations}
    })

    # ── Check 5: Error rate within threshold ──
    errors = [r for r in results if not r.get("success", True)]
    error_rate = len(errors) / max(len(results), 1)
    max_rate = thresholds.get("canary_max_error_rate", 0.0)
    checks.append({
        "check_name": "error_rate_ok",
        "passed": error_rate <= max_rate,
        "details": {
            "error_count": len(errors),
            "total": len(results),
            "error_rate": error_rate,
            "max_allowed": max_rate,
        }
    })

    return checks