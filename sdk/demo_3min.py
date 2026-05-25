#!/usr/bin/env python3
"""
Action Marshall — 3-Minute Demo Setup Script

Runs 4 scenarios in order, pausing between each so you can
switch to the browser and show the result live.

Usage (while screen-recording):
  Terminal 1:  cd backend && rm action_marshall.db && uvicorn app.main:app --reload --port 8000
  Terminal 2:  cd ui && npm run dev
  Terminal 3:  cd sdk && python demo_3min.py   ← run this one on camera

Scenarios seeded:
  1. COMPLETED      — Safe bulk reassignment, full lifecycle, proof signed
  2. CONTAINED      — Breaker catches business-rule side-effect mid-canary
  3. BLOCKED        — P1 incidents in target set, stopped before execution
  4. AWAITING       — VIP-impacting action waiting for human approval

Open these tabs BEFORE recording:
  http://localhost:3000/               — dashboard
  http://localhost:3000/approvals      — approval queue
  http://localhost:3000/audit          — audit trail
"""
import time
import sys
from action_marshall import MarshallClient, Action, ActionParams, Actor

BASE_URL = "http://localhost:8000"
UI_URL   = "http://localhost:3000"
API_KEY  = "am_test_demo_key_001"

ks = MarshallClient(base_url=BASE_URL, api_key=API_KEY)

ACTOR = Actor(id="incident-resolver-v2", name="Incident Resolver Agent")


def banner(n, title, subtitle):
    print(f"\n{'━' * 60}")
    print(f"  SCENARIO {n}: {title}")
    print(f"  {subtitle}")
    print(f"{'━' * 60}")


def show(result, label=""):
    icon = {"completed": "✓", "blocked": "✗", "contained": "⚡", "awaiting_approval": "⏳"}.get(result.status, "?")
    print(f"  {icon}  {label or result.status.upper()}")
    print(f"     Blast radius : {result.blast_radius} records")
    print(f"     Decision     : {result.decision_value}")
    print(f"     Status       : {result.status}")
    if result.breaker_tripped:
        print(f"     Breaker      : TRIPPED — expansion halted")
    if result.proof_available:
        print(f"     Proof        : Signed ✓")
    print(f"     Browser      : {result.ui_urls.get('detail', '')}")


def wait(msg, secs=0):
    if secs:
        for i in range(secs, 0, -1):
            print(f"\r  [{i}s] Switching to browser — show the result...", end="", flush=True)
            time.sleep(1)
        print("\r" + " " * 55 + "\r", end="")
    else:
        input(f"\n  ↵  {msg}")


# ─── Pre-flight ───────────────────────────────────────────────────────────────
print("\n  Action Marshall 3-Minute Demo")
print("  ─────────────────────────────────────────")
print("  Checking backend...")
try:
    p = ks.get_policy()
    print(f"  ✓ Connected  |  Policy: {p['policy_id']} v{p['version']}")
    print(f"  ✓ UI: {UI_URL}")
except Exception as e:
    print(f"  ✗ Cannot reach backend at {BASE_URL}")
    print(f"    Start it: cd backend && uvicorn app.main:app --reload --port 8000")
    sys.exit(1)

wait("Ready to record? Hit Enter to run Scenario 1...")


# ─── SCENARIO 1: COMPLETED ───────────────────────────────────────────────────
banner(1, "COMPLETED", "Safe bulk reassignment — canary → checks → expand → proof")

print("\n  Running: reassign 20 P3/P4 incidents to Triage Team...")

r1 = ks.run(Action(
    actor=ACTOR,
    tool="servicenow",
    action_type="bulk_update",
    params=ActionParams(
        connector="servicenow_sim",
        query={"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}},
        changes={"assignment_group": "Triage Team"},
    ),
    workspace_id="ws_platform",
    connection_id="conn_snow",
), mode="enforce")

show(r1, "COMPLETED — All records updated, proof signed")
wait("Show action detail in browser, then hit Enter for Scenario 2...", secs=8)


# ─── SCENARIO 2: CONTAINED ───────────────────────────────────────────────────
banner(2, "CONTAINED", "Circuit breaker catches unexpected side-effect during canary")

print("\n  Running: resolve the same incidents (triggers business rule)...")

r2 = ks.run(Action(
    actor=ACTOR,
    tool="servicenow",
    action_type="bulk_update",
    params=ActionParams(
        connector="servicenow_sim",
        query={"assignment_group": "Triage Team"},
        changes={"state": "resolved"},
    ),
    workspace_id="ws_platform",
    connection_id="conn_snow",
), mode="enforce")

show(r2, "CONTAINED — Breaker tripped, only canary records touched")
wait("Show contained action + breaker in browser, then hit Enter for Scenario 3...", secs=8)


# ─── SCENARIO 3: BLOCKED ─────────────────────────────────────────────────────
banner(3, "BLOCKED", "Policy stops dangerous action before any execution")

print("\n  Running: resolve ALL open incidents (includes P1 + VIP)...")

r3 = ks.run(Action(
    actor=ACTOR,
    tool="servicenow",
    action_type="bulk_update",
    params=ActionParams(
        connector="servicenow_sim",
        query={"state": "open"},
        changes={"state": "resolved"},
    ),
    workspace_id="ws_platform",
    connection_id="conn_snow",
), mode="enforce")

show(r3, "BLOCKED — Zero records modified, reason logged")
wait("Show blocked action + policy reasons in browser, then hit Enter for Scenario 4...", secs=8)


# ─── SCENARIO 4: APPROVAL REQUIRED ───────────────────────────────────────────
banner(4, "AWAITING APPROVAL", "VIP-impacting action held for human review")

print("\n  Running: reassign P2 (VIP) incidents to Executive Support...")

r4 = ks.run(Action(
    actor=ACTOR,
    tool="servicenow",
    action_type="bulk_update",
    params=ActionParams(
        connector="servicenow_sim",
        query={"state": "open", "priority": "P2"},
        changes={"assignment_group": "Executive Support"},
    ),
    workspace_id="ws_platform",
    connection_id="conn_snow",
), mode="enforce")

show(r4, "AWAITING APPROVAL — VIP flag → routed to human")


# ─── SUMMARY ─────────────────────────────────────────────────────────────────
print(f"\n{'━' * 60}")
print(f"  DEMO READY — Switch to browser")
print(f"{'━' * 60}\n")

rows = [
    ("1 COMPLETED",        r1.action_id, r1.blast_radius, "canary → proof"),
    ("2 CONTAINED",        r2.action_id, r2.blast_radius, "breaker tripped"),
    ("3 BLOCKED",          r3.action_id, r3.blast_radius, "policy stopped"),
    ("4 AWAITING APPROVAL",r4.action_id, r4.blast_radius, "VIP flag"),
]

print(f"  {'Scenario':<22} {'Records':>7}  {'Story'}")
print(f"  {'─'*22} {'─'*7}  {'─'*20}")
for label, aid, br, story in rows:
    print(f"  {label:<22} {br:>7}  {story}")

print(f"\n  Browser tabs to show (in order during recording):")
print(f"  1.  {UI_URL}/                          ← dashboard overview")
print(f"  2.  {UI_URL}/actions/{r1.action_id}    ← completed lifecycle")
print(f"  3.  {UI_URL}/actions/{r2.action_id}    ← breaker + checks")
print(f"  4.  {UI_URL}/actions/{r3.action_id}    ← blocked + policy")
print(f"  5.  {UI_URL}/approvals                 ← approval queue")
print(f"  6.  {UI_URL}/actions/{r1.action_id}/proof  ← proof receipt")
print(f"  7.  {UI_URL}/audit                     ← full audit trail")
print()