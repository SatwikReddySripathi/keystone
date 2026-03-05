#!/usr/bin/env python3
"""
Keystone MVP — Full Product Demo

This script demonstrates every governance capability in sequence.
Run it while recording your screen for the demo video.

Scenarios:
  1. COMPLETED  — Safe change flows through entire lifecycle
  2. CONTAINED  — Breaker catches unexpected side-effect mid-execution
  3. BLOCKED    — Policy prevents dangerous action before any execution
  4. APPROVAL   — Action pauses for human approval via Slack

Prerequisites:
  - Backend running: cd backend && python -m uvicorn app.main:app --reload --port 8000
  - UI running:      cd ui && npm run dev
  - Fresh database:  del backend/keystone.db before starting backend
  - Slack (optional): for scenario 4 approval buttons

Usage:
  cd sdk
  pip install -e .
  python demo.py
"""
import time
import sys
from keystone import Keystone, Action, ActionParams, Actor

# ── Config ──
API_KEY = "ks_test_demo_key_001"
BASE_URL = "http://localhost:8000"
UI_URL = "http://localhost:3000"

ks = Keystone(base_url=BASE_URL, api_key=API_KEY)

# ── Helpers ──
def header(title, subtitle=""):
    print(f"\n{'━'*70}")
    print(f"  {title}")
    if subtitle:
        print(f"  {subtitle}")
    print(f"{'━'*70}\n")

def step(num, text):
    print(f"  [{num}] {text}")

def result_block(result):
    print(f"\n  ┌─────────────────────────────────────────────────")
    print(f"  │ Action ID:    {result.action_id}")
    print(f"  │ Status:       {result.status}")
    print(f"  │ Decision:     {result.decision_value}")
    print(f"  │ Blast Radius: {result.blast_radius} records")
    if result.breaker:
        tripped = result.breaker.get("tripped", False)
        print(f"  │ Breaker:      {' TRIPPED' if tripped else 'Armed (OK)'}")
        if tripped and result.breaker.get("reason"):
            reason = result.breaker["reason"]
            if len(reason) > 60:
                reason = reason[:60] + "..."
            print(f"  │ Halt Reason:  {reason}")
    print(f"  │ Proof:        {' Signed & verified' if result.proof_available else '—'}")
    print(f"  │ UI:           {result.ui_urls.get('detail', '')}")
    print(f"  └─────────────────────────────────────────────────\n")

def reasons_block(result):
    if result.decision and result.decision.get("reasons"):
        print(f"  Policy reasons:")
        for r in result.decision["reasons"]:
            print(f"    [{r['decision']:20s}] {r['reason']}")
        print()

def proof_block(action_id):
    proof = ks.get_proof(action_id)
    sig = proof["signature"]
    print(f"  Proof receipt:")
    print(f"    Signature:  {sig[:40]}...")
    print(f"    Verified:   {' Authentic' if proof['verified'] else ' TAMPERED'}")
    print(f"    Export:      {UI_URL}/actions/{action_id}/proof")
    print()

def detail_block(action_id):
    detail = ks.get_action(action_id)
    events = detail.get("events", [])
    print(f"  Lifecycle ({len(events)} events):")
    for e in events:
        t = e.get("type", "")
        ts = e.get("created_at", "")
        # Color-code important events
        if "breaker" in t or "blocked" in t or "denied" in t:
            marker = "  "
        elif "completed" in t or "approval.recorded" in t:
            marker = "  "
        elif "canary" in t:
            marker = "  ●"
        else:
            marker = "   "
        print(f"   {marker} {t:30s} {ts}")

    # Show checks if any
    checks = detail.get("checks", [])
    if checks:
        print(f"\n  Safety invariants:")
        for c in checks:
            passed = c.get("passed", 0)
            name = c.get("check_name", "unknown")
            icon = "" if passed else ""
            color_label = "PASS" if passed else "FAIL"
            print(f"    [{icon} {color_label}] {name}")

    # Show approvals if any
    approvals = detail.get("approvals", [])
    if approvals:
        print(f"\n  Approvals:")
        for a in approvals:
            approver = a.get("approver_json", {})
            if isinstance(approver, str):
                import json
                try: approver = json.loads(approver)
                except: approver = {}
            name = approver.get("name", "Unknown")
            channel = a.get("channel", "unknown")
            preview_hash = a.get("preview_hash", "")[:12]
            print(f"    {name} via {channel} (hash: {preview_hash}...)")

    print()

def pause(msg="Press Enter to continue to next scenario...", seconds=0):
    if seconds:
        for i in range(seconds, 0, -1):
            print(f"\r  Next scenario in {i}s... ", end="", flush=True)
            time.sleep(1)
        print("\r" + " " * 40 + "\r", end="")
    else:
        input(f"  {msg}")
    print()


# ═══════════════════════════════════════════════════════
# Pre-flight check
# ═══════════════════════════════════════════════════════
header("KEYSTONE MVP DEMO", "Transaction governance for autonomous agent actions")

print("  Checking backend connectivity...")
try:
    policy = ks.get_policy()
    print(f"   Backend connected")
    print(f"   Policy loaded: {policy['policy_id']} v{policy['version']}")
    print(f"   UI available at {UI_URL}")
except Exception as e:
    print(f"   Cannot reach backend at {BASE_URL}")
    print(f"    Error: {e}")
    print(f"    Make sure: cd backend && python -m uvicorn app.main:app --reload --port 8000")
    sys.exit(1)

pause(seconds=3)


# ═══════════════════════════════════════════════════════
# SCENARIO 1: COMPLETED — Safe bulk reassignment
# ═══════════════════════════════════════════════════════
header(
    "SCENARIO 1: COMPLETED",
    "Safe bulk reassignment — full lifecycle with canary"
)

print("  Situation: An agent wants to reassign 20 P3/P4 incidents to the")
print("  Triage Team. No P1, no VIP, no risky fields. Policy should allow")
print("  it with canary execution.\n")

step(1, "Agent proposes action via SDK...")
action_safe = Action(
    tool="servicenow",
    action_type="bulk_update",
    environment="simulation",
    actor=Actor(id="incident-resolver-v2", name="Incident Resolver Agent", type="agent"),
    params=ActionParams(
        connector="servicenow_sim",
        query={"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}},
        changes={"assignment_group": "Triage Team"},
    ),
)

result1 = ks.run(action_safe, mode="enforce")

step(2, "Keystone previews blast radius...")
print(f"      -> {result1.blast_radius} records matched")
if result1.preview:
    flags1 = result1.preview.get("flags", {})
    active_flags = [k for k, v in flags1.items() if v is True]
    if active_flags:
        print(f"      -> Flags: {', '.join(active_flags)}")
    else:
        print(f"      -> No risk flags detected")
    print(f"      -> Preview hash: {result1.preview.get('preview_hash', '')[:16]}...")

step(3, "Policy evaluates...")
print(f"      -> Decision: {result1.decision_value}")
reasons_block(result1)

step(4, "Execution result:")
result_block(result1)

step(5, "Full lifecycle:")
detail_block(result1.action_id)

step(6, "Proof receipt:")
proof_block(result1.action_id)

if result1.status == "completed":
    print(f"  RESULT: All {result1.blast_radius} records updated. Proof signed.")
else:
    print(f"    RESULT: Status is {result1.status}.")
print(f"  View in UI: {result1.ui_urls.get('detail')}")

pause(seconds=5)


# ═══════════════════════════════════════════════════════
# SCENARIO 2: CONTAINED — Breaker catches side-effect
# ═══════════════════════════════════════════════════════
header(
    "SCENARIO 2: CONTAINED",
    "Breaker catches unexpected side-effect during canary"
)

print("  Situation: The same agent now wants to resolve these incidents.")
print("  Policy allows it (no P1/VIP, medium blast radius -> canary).")
print("  But when ServiceNow sets state='resolved', a business rule")
print("  auto-populates 'resolved_at' and 'work_notes' — fields the")
print("  agent didn't intend to change.\n")
print("  Keystone's 'only_intended_fields' check will catch this.\n")

step(1, "Agent proposes resolve action...")
action_resolve = Action(
    tool="servicenow",
    action_type="bulk_update",
    environment="simulation",
    actor=Actor(id="incident-resolver-v2", name="Incident Resolver Agent", type="agent"),
    params=ActionParams(
        connector="servicenow_sim",
        query={"assignment_group": "Triage Team"},
        changes={"state": "resolved"},
    ),
)

result2 = ks.run(action_resolve, mode="enforce")

step(2, "Preview: blast radius...")
print(f"      -> {result2.blast_radius} records matched")

step(3, "Policy evaluates...")
print(f"      -> Decision: {result2.decision_value}")
reasons_block(result2)

step(4, "Execution result:")
result_block(result2)

# Show what actually happened from the detail
detail2 = ks.get_action(result2.action_id)
canary_exec = None
for ex in detail2.get("executions", []):
    if ex.get("phase") == "canary":
        canary_exec = ex
        break

if canary_exec:
    canary_results = canary_exec.get("results_json", [])
    if isinstance(canary_results, str):
        import json as _json
        canary_results = _json.loads(canary_results)
    intended_fields = set(action_resolve.params.changes.keys())
    print(f"  Canary details:")
    print(f"    Intended fields:  {', '.join(sorted(intended_fields))}")
    for cr in canary_results[:2]:
        actual_fields = set(cr.get("changes_applied", []))
        extra = actual_fields - intended_fields
        print(f"    {cr['sys_id']}: changed={', '.join(sorted(actual_fields))}", end="")
        if extra:
            print(f"   unexpected: {', '.join(sorted(extra))}", end="")
        print()
    if len(canary_results) > 2:
        print(f"    ... and {len(canary_results) - 2} more records")
    print()

checks2 = detail2.get("checks", [])
if checks2:
    print(f"  Safety invariants:")
    for c in checks2:
        passed = c.get("passed", 0)
        name = c.get("check_name", "unknown")
        icon = " PASS" if passed else " FAIL"
        print(f"    [{icon}] {name}")
    print()

if result2.breaker_tripped:
    step(5, "Circuit breaker TRIPPED — expansion halted!")
    print(f"      -> Reason: {result2.breaker.get('reason', 'unknown')[:80]}")
else:
    step(5, "Circuit breaker: OK")

step(6, "Proof receipt:")
proof_block(result2.action_id)

step(7, "Full lifecycle:")
detail_block(result2.action_id)

if result2.status == "contained":
    canary_count = len(canary_exec.get("subset_ids_json", [])) if canary_exec else "?"
    print(f"  RESULT: Only {canary_count} of {result2.blast_radius} records touched. Rest protected.")
    print(f"  Keystone caught the divergence and halted before damage spread.")
elif result2.status == "completed":
    print(f"  RESULT: All {result2.blast_radius} records updated (no side-effects detected).")
else:
    print(f"  RESULT: Status is {result2.status}.")
print(f"  View in UI: {result2.ui_urls.get('detail')}")

pause(seconds=5)


# ═══════════════════════════════════════════════════════
# SCENARIO 3: BLOCKED — Policy prevents dangerous action
# ═══════════════════════════════════════════════════════
header(
    "SCENARIO 3: BLOCKED",
    "Policy blocks dangerous action before any execution"
)

print("  Situation: The agent tries to resolve ALL open incidents,")
print("  including P1 critical and VIP-caller records. Policy has")
print("  hard rules: never auto-update P1, require approval for VIP.\n")
print("  Since P1 is present, the strictest rule wins: BLOCK.\n")

step(1, "Agent proposes broad resolve action...")
action_dangerous = Action(
    tool="servicenow",
    action_type="bulk_update",
    environment="simulation",
    actor=Actor(id="incident-resolver-v2", name="Incident Resolver Agent", type="agent"),
    params=ActionParams(
        connector="servicenow_sim",
        query={"state": "open"},
        changes={"state": "resolved"},
    ),
)

result3 = ks.run(action_dangerous, mode="enforce")

step(2, "Preview result:")
print(f"      -> {result3.blast_radius} records matched")
if result3.preview:
    flags3 = result3.preview.get("flags", {})
    active_flags3 = [k for k, v in flags3.items() if v is True]
    if active_flags3:
        print(f"      -> Risk flags: {', '.join(active_flags3)}")

step(3, "Policy evaluates:")
print(f"      -> Decision: {result3.decision_value}")
reasons_block(result3)

step(4, "Result:")
result_block(result3)

step(5, "Proof (documents the block):")
proof_block(result3.action_id)

if result3.status == "blocked":
    print(f"  RESULT: Policy blocked the action. Zero records modified.")
else:
    print(f"  RESULT: Status is {result3.status}.")
print(f"  View in UI: {result3.ui_urls.get('detail')}")

pause(seconds=5)


# ═══════════════════════════════════════════════════════
# SCENARIO 4: APPROVAL REQUIRED — Human oversight via Slack
# ═══════════════════════════════════════════════════════
header(
    "SCENARIO 4: APPROVAL REQUIRED",
    "Action pauses for human approval (Slack integration)"
)

print("  Situation: The agent wants to reassign P2 incidents to")
print("  Executive Support. P2 records include VIP callers (CFO).")
print("  Policy requires human approval for VIP-impacting actions.\n")
print("  Keystone will pause the action and post to Slack.\n")

step(1, "Agent proposes VIP-impacting action...")
action_vip = Action(
    tool="servicenow",
    action_type="bulk_update",
    environment="simulation",
    actor=Actor(id="incident-resolver-v2", name="Incident Resolver Agent", type="agent"),
    params=ActionParams(
        connector="servicenow_sim",
        query={"state": "open", "priority": "P2"},
        changes={"assignment_group": "Executive Support"},
    ),
)

result4 = ks.run(action_vip, mode="enforce")

step(2, "Preview result:")
print(f"      -> {result4.blast_radius} records matched")
if result4.preview:
    flags4 = result4.preview.get("flags", {})
    active_flags4 = [k for k, v in flags4.items() if v is True]
    if active_flags4:
        print(f"      -> Flags: {', '.join(active_flags4)}")

step(3, f"Policy decision: {result4.decision_value}")
reasons_block(result4)

result_block(result4)

if result4.status == "awaiting_approval":
    step(4, "Slack notification sent! Check your Slack channel.")
    print(f"      ->The message includes: blast radius, risk flags,")
    print(f"        preview hash, sample diffs, and Approve/Deny buttons.")
    print(f"      -> Approval binds to preview_hash + policy_version.")
    print(f"      -> If data changes, the approval is invalidated.\n")

    print(f" Go to Slack and click Approve or Deny.")
    print(f" Or view in UI: {result4.ui_urls.get('detail')}\n")

    # Poll for resolution
    print(f"  Waiting for Slack response", end="", flush=True)
    resolved = False
    for i in range(90):
        time.sleep(2)
        print(".", end="", flush=True)
        try:
            detail = ks.get_action(result4.action_id)
            status = detail["action"]["status"]
            if status != "awaiting_approval":
                print(f"\n\n  Status changed: {status}")

                if detail.get("approvals"):
                    a = detail["approvals"][0]
                    approver = a.get("approver_json", {})
                    if isinstance(approver, str):
                        import json
                        try: approver = json.loads(approver)
                        except: approver = {}
                    print(f"  Approved by: {approver.get('name', 'Unknown')}")
                    print(f"  Channel:     {a.get('channel', 'unknown')}")

                if detail.get("breaker"):
                    br = detail["breaker"]
                    tripped = br.get("tripped", 0)
                    print(f"  Breaker:     {'TRIPPED' if tripped else 'OK'}")

                print(f"\n  Full lifecycle:")
                for e in detail.get("events", []):
                    t = e.get("type", "")
                    print(f"    {t}")

                resolved = True
                break
        except:
            pass

    if not resolved:
        print(f"\n\n  Timed out waiting (3 minutes). You can still approve in Slack")
        print(f"  and refresh the UI to see the result.")
else:
    print(f"  Note: Action got {result4.status} instead of awaiting_approval.")
    print(f"  This may happen if the VIP records were already modified by a previous scenario.")


# ═══════════════════════════════════════════════════════
# SCENARIO 5: OBSERVE ONLY — Dry run
# ═══════════════════════════════════════════════════════
header(
    "SCENARIO 5: OBSERVE ONLY",
    "Preview and policy evaluation without any execution"
)

print("  Situation: Before running anything, the agent wants to see")
print("  what WOULD happen. Observe mode generates preview + policy")
print("  decision + proof, but touches zero records.\n")

step(1, "Agent runs in observe_only mode...")
result5 = ks.run(action_safe, mode="observe_only")

step(2, "Preview generated, policy evaluated, no execution")
result_block(result5)

print(f"  RESULT: Full preview and decision without side effects.")
print(f"  Use this for: pre-flight checks, testing policy rules, auditing intent.")
print(f"  View in UI: {result5.ui_urls.get('detail')}")

pause(seconds=3)


# ═══════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════
header("DEMO COMPLETE", "Keystone — Transaction governance for autonomous agent actions")

actions = ks.list_actions()
print(f"  Actions created: {len(actions)}")
print()
print(f"  Scenarios demonstrated:")
print(f"    1.  COMPLETED  — Safe action, full lifecycle, canary -> expand -> proof")
print(f"    2.  CONTAINED — Policy allowed, breaker caught side-effect, halted expansion")
print(f"    3.  BLOCKED    — Policy caught P1/VIP, refused before execution")
print(f"    4.  APPROVAL   — Human oversight via Slack, approval bound to preview hash")
print(f"    5.  OBSERVED   — Dry run, preview + decision without execution")
print()
print(f"  Capabilities shown:")
print(f"    • Blast radius preview with breakdowns and risk flags")
print(f"    • Versioned YAML policy with deterministic decisions")
print(f"    • Deterministic canary subset selection (reproducible)")
print(f"    • 5 post-execution safety invariant checks")
print(f"    • Circuit breaker auto-halt on anomaly detection")
print(f"    • HMAC-SHA256 signed audit receipt (tamper-evident)")
print(f"    • Slack interactive approval with preview hash binding")
print(f"    • 3-line SDK integration")
print(f"    • Tool-agnostic connector interface")
print()
print(f"  View all actions: {UI_URL}")
print(f"  API docs:         {BASE_URL}/docs")
print()
print(f"  This is transaction governance:")
print(f"  Preview the diff. Enforce delegated authority. Canary the action.")
print(f"  Auto-stop if reality diverges. Emit audit-grade proof.")
print()