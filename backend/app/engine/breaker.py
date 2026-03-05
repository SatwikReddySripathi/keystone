"""
Circuit breaker — auto-halt when post-checks fail.

Simple logic: if ANY check failed, trip the breaker.
When tripped:
  - Expansion is prevented (only the canary 5 were touched)
  - Action status becomes "contained" (not "completed")
  - The proof receipt records WHY it was halted
  - UI shows a red banner with the reason

This is the safety net. Even if the policy allowed execution,
the breaker can still stop it based on what ACTUALLY happened.
"""


def evaluate_breaker(checks: list[dict]) -> dict:
    """
    Evaluate whether circuit breaker should trip.

    Input: list of check results from run_post_checks()
    Output: {tripped: bool, reason: str|None, failed_checks: list}
    """
    failed = [c for c in checks if not c["passed"]]

    if not failed:
        return {
            "tripped": False,
            "reason": None,
            "failed_checks": [],
        }

    reasons = [f"{c['check_name']}: {_summarize(c)}" for c in failed]
    return {
        "tripped": True,
        "reason": "; ".join(reasons),
        "failed_checks": [c["check_name"] for c in failed],
    }


def _summarize(check: dict) -> str:
    """Human-readable summary of why a check failed."""
    name = check["check_name"]
    d = check.get("details", {})

    if name == "error_rate_ok":
        return f"error_rate={d.get('error_rate', '?')} > max={d.get('max_allowed', '?')}"
    if name == "no_vip_state_change":
        return f"VIP records affected: {d.get('vip_records_with_state_change', [])}"
    if name == "no_p1_state_change":
        return f"P1 records affected: {d.get('p1_records_with_state_change', [])}"
    if name == "no_out_of_scope":
        return f"out-of-scope IDs: {d.get('out_of_scope', [])}"
    if name == "only_intended_fields":
        return f"unintended changes: {d.get('unintended_changes', [])}"
    return str(d)