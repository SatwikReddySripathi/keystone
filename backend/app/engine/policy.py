"""
Policy engine — versioned YAML evaluation with deterministic decisions.

Key design decisions:
1. Rules are evaluated IN ORDER, but the STRICTEST decision wins.
   BLOCK > APPROVAL_REQUIRED > CANARY > AUTO
2. ALL matching rules are collected as reasons (not just the first).
   This means the UI can show "Blocked because: P1 present AND VIP present"
3. If approval is required and provided, we validate it matches the
   preview_hash and policy_version before downgrading to CANARY.
4. Same preview data + same policy version = same decision. Always.
"""
import yaml
import hashlib
import json
from pathlib import Path

POLICY_DIR = Path(__file__).parent.parent / "policies"

# Decision priority — higher number = stricter
DECISION_PRIORITY = {
    "AUTO": 1,
    "CANARY": 2,
    "APPROVAL_REQUIRED": 3,
    "BLOCK": 4,
}


def load_policy(policy_file: str = "default_policy.yaml") -> dict:
    """Load and parse the policy YAML file."""
    path = POLICY_DIR / policy_file
    with open(path) as f:
        return yaml.safe_load(f)


def get_policy_hash(policy: dict) -> str:
    """Hash the policy for versioning/tracking."""
    raw = json.dumps(policy, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def evaluate_policy(preview: dict, approval: dict = None, policy_file: str = "default_policy.yaml") -> dict:
    """
    Evaluate policy rules against preview data.

    Input:
        preview: output from generate_preview()
        approval: optional {preview_hash, policy_version, approver: {...}}
        policy_file: YAML filename in the policies directory (default: default_policy.yaml)

    Output: {
        policy_id, policy_version, decision, reasons,
        thresholds, required_checks, matched_rules
    }
    """
    policy = load_policy(policy_file)
    blast_radius = preview["blast_radius"]
    flags = preview["flags"]

    matched_rules = []
    reasons = []
    required_checks = set()
    decision = "AUTO"  # default if no rules match

    for rule in policy.get("rules", []):
        cond = rule["condition"]
        matched = _evaluate_condition(cond, blast_radius, flags)

        if matched:
            rule_decision = rule["decision"]
            # Format the reason string with actual values
            reason = rule["reason"].format(
                blast_radius=blast_radius,
                threshold=cond.get("value", ""),
            )

            matched_rules.append(rule["name"])
            reasons.append({
                "rule": rule["name"],
                "decision": rule_decision,
                "reason": reason,
            })
            required_checks.update(rule.get("required_checks", []))

            # Keep the strictest decision
            if DECISION_PRIORITY.get(rule_decision, 0) > DECISION_PRIORITY.get(decision, 0):
                decision = rule_decision

    # ── Handle approval if provided ──
    if decision == "APPROVAL_REQUIRED" and approval:
        hash_match = approval.get("preview_hash") == preview["preview_hash"]
        version_match = approval.get("policy_version") == policy["version"]

        if hash_match and version_match:
            # Approval is valid — downgrade to CANARY
            approver_name = approval.get("approver", {}).get("name", "unknown")
            reasons.append({
                "rule": "approval_satisfied",
                "decision": "CANARY",
                "reason": f"Approval verified for preview_hash={preview['preview_hash'][:8]}... by {approver_name}",
            })
            decision = "CANARY"
        else:
            # Approval doesn't match — escalate to BLOCK
            reasons.append({
                "rule": "approval_mismatch",
                "decision": "BLOCK",
                "reason": f"Approval provided but hash_match={hash_match}, version_match={version_match}",
            })
            decision = "BLOCK"

    return {
        "policy_id": policy["policy_id"],
        "policy_version": policy["version"],
        "decision": decision,
        "reasons": reasons,
        "thresholds": policy.get("thresholds", {}),
        "required_checks": sorted(required_checks),
        "matched_rules": matched_rules,
    }


def _evaluate_condition(cond: dict, blast_radius: int, flags: dict) -> bool:
    """Evaluate a single rule condition against preview data."""
    if "field" in cond:
        # Numeric field comparison (blast_radius)
        field_val = {"blast_radius": blast_radius}.get(cond["field"], 0)
        op = cond["op"]
        threshold = cond["value"]

        if op == "gt":
            return field_val > threshold
        if op == "gte":
            return field_val >= threshold
        if op == "lt":
            return field_val < threshold
        if op == "lte":
            return field_val <= threshold
        if op == "eq":
            return field_val == threshold

    elif "flag" in cond:
        # Boolean flag check (has_p1, has_vip, etc.)
        flag_val = flags.get(cond["flag"], False)
        op = cond["op"]
        target = cond["value"]

        if op == "eq":
            return flag_val == target
        if op == "ne":
            return flag_val != target

    return False