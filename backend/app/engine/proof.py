"""
Proof receipt — immutable signed audit artifact.

The proof is the final output of every action. It captures:
  - WHO: actor (proposer) + approver identities
  - WHAT: action params + preview (blast radius, diffs, flags)
  - WHY: policy decision + reasons + matched rules
  - WHEN: full event timeline with timestamps
  - OUTCOME: canary results + checks + breaker status

The signature is HMAC-SHA256 over the canonical (sorted, compact) JSON.
To verify: recompute the HMAC with the same secret and compare.
If a single character of the receipt is changed, verification fails.

This is the "audit-grade proof of execution" from the checklist.
"""
import hmac
import hashlib
import json
import os
from datetime import datetime

PROOF_SECRET = os.getenv("PROOF_SECRET", "keystone-dev-secret-change-in-production")


def generate_proof(
    action_id: str,
    org_id: str,
    environment: str,
    action_snapshot: dict,
    preview_summary: dict,
    decision: dict,
    approvals: list[dict],
    canary: dict | None,
    checks: list[dict],
    breaker: dict,
    events: list[dict],
) -> dict:
    """
    Build and sign a proof receipt.

    Returns: {receipt: dict, signature: str}
    """
    receipt = {
        "version": "1.0.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "org_id": org_id,
        "environment": environment,

        # WHO proposed this action
        "action": {
            "action_id": action_id,
            **action_snapshot,
        },

        # WHAT would happen (preview)
        "preview": {
            "blast_radius": preview_summary.get("blast_radius"),
            "preview_hash": preview_summary.get("preview_hash"),
            "flags": preview_summary.get("flags"),
            "diffs_sample": preview_summary.get("diffs", [])[:5],
        },

        # WHY (policy decision)
        "policy": {
            "policy_id": decision.get("policy_id"),
            "policy_version": decision.get("policy_version"),
            "decision": decision.get("decision"),
            "reasons": decision.get("reasons"),
            "thresholds": decision.get("thresholds"),
        },

        # WHO approved (if anyone)
        "approvals": approvals,

        # WHAT actually happened
        "execution": {
            "canary": canary,
            "checks": checks,
            "breaker": breaker,
        },

        # WHEN (full timeline)
        "timeline": events,
    }

    # Sign: canonical JSON (sorted keys, no whitespace) → HMAC-SHA256
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    signature = hmac.new(
        PROOF_SECRET.encode(),
        canonical.encode(),
        hashlib.sha256,
    ).hexdigest()

    return {"receipt": receipt, "signature": signature}


def verify_proof(receipt: dict, signature: str) -> bool:
    """
    Verify a proof receipt's signature.
    Returns True if the receipt is untampered.
    """
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    expected = hmac.new(
        PROOF_SECRET.encode(),
        canonical.encode(),
        hashlib.sha256,
    ).hexdigest()
    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected, signature)