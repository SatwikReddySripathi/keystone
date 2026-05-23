#!/usr/bin/env python3
"""
Keystone — Demo Recording Director

Interactive terminal-based teleprompter that walks you through
a 3-minute video recording session, segment by segment.

At each segment it shows:
  - What screen to be on (live UI or this terminal)
  - The visual cue (where to look, what to click)
  - The exact narration to speak
  - Target timing

Some segments execute SDK calls live so the UI populates while
you narrate. Press ENTER to advance. Use Ctrl-C to abort.

Prerequisites:
  Terminal 1 :  cd backend  &&  del keystone.db  &&  uvicorn app.main:app --reload --port 8000
  Terminal 2 :  cd ui       &&  npm run dev
  Browser    :  log in as sarah.chen@keystone.org (OTP in Terminal 1)
                Open 3 tabs: localhost:3000 / localhost:3000/approvals / localhost:3000/audit
  Recording  :  start OBS or your screen recorder, then run THIS script
"""
import os
import sys
import time
from keystone import Keystone, Action, ActionParams, Actor

# ─── Config ──────────────────────────────────────────────────────────────────
BASE_URL = "http://localhost:8000"
UI_URL   = "http://localhost:3000"
API_KEY  = "ks_test_demo_key_001"

ks = Keystone(base_url=BASE_URL, api_key=API_KEY)
ACTOR = Actor(id="triage-agent-v2", name="IT Triage Agent")

# ─── Colors ──────────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
VIOLET = "\033[95m"
GREEN  = "\033[92m"
AMBER  = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
RED    = "\033[91m"
WHITE  = "\033[97m"
GREY   = "\033[90m"

def clear():
    os.system("cls" if os.name == "nt" else "clear")


# ─── Demo action runners ─────────────────────────────────────────────────────
# These run during the appropriate segments so the UI populates live.

def run_needs_registration():
    print(f"\n  {DIM}running: new unknown agent fires its first SDK call...{RESET}")
    r = ks.run(Action(
        actor=Actor(id="crm-sync-agent-new", name="CRM Sync Agent"),
        tool="servicenow",
        action_type="bulk_update",
        params=ActionParams(
            connector="servicenow_sim",
            query={"state": "open", "priority": "P3"},
            changes={"assignment_group": "CRM Team"},
        ),
        workspace_id="ws_platform",
        connection_id="conn_snow",
    ), mode="observe_only")
    print(f"  {AMBER}⚠ PENDING REGISTRATION{RESET}  agent=crm-sync-agent-new  auto-discovered")
    print(f"  {DIM}→ Go to Agents page to see the pending registration stub.{RESET}")
    return r


def run_observe():
    print(f"\n  {DIM}running: observe_only — reassign 20 P3/P4 incidents to Triage Team...{RESET}")
    r = ks.run(Action(
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
    ), mode="observe_only")
    print(f"  {CYAN}● OBSERVE ONLY{RESET}  blast={r.blast_radius}  decision={r.decision_value}  no records touched")
    print(f"  {DIM}action_id: {r.action_id}{RESET}")
    print(f"  {CYAN}→ Now click 'Run for Real' in the UI to execute.{RESET}")
    return r


def run_blocked():
    print(f"\n  {DIM}running: resolve ALL open incidents (includes P1 + VIP)...{RESET}")
    r = ks.run(Action(
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
    print(f"  {RED}✗ BLOCKED{RESET}  blast={r.blast_radius}  decision={r.decision_value}  records touched: 0")
    return r


def run_approval():
    print(f"\n  {DIM}running: reassign P2 VIP incidents to Executive Support...{RESET}")
    r = ks.run(Action(
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
    print(f"  {AMBER}⏳ AWAITING APPROVAL{RESET}  blast={r.blast_radius}  decision={r.decision_value}")
    return r


def run_contained():
    print(f"\n  {DIM}running: resolve the reassigned incidents (triggers business rule)...{RESET}")
    r = ks.run(Action(
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
    tripped = r.breaker_tripped
    label = f"{AMBER}⚡ CONTAINED (breaker TRIPPED){RESET}" if tripped else f"{GREEN}✓ COMPLETED{RESET}"
    print(f"  {label}  blast={r.blast_radius}  decision={r.decision_value}")
    return r


# Action registry — segments reference these by key.
ACTIONS = {
    "needs_registration": run_needs_registration,
    "observe":            run_observe,
    "blocked":            run_blocked,
    "approval":           run_approval,
    "contained":          run_contained,
}


# ─── Segment definitions — the 3-minute script ──────────────────────────────
# Target: 180 seconds total. Each segment has a hard timing target so you
# can pace to the clock (but the script itself never auto-advances —
# ENTER is always manual so you control the take).
SEGMENTS = [
    {
        "idx": 1,
        "time": "0:00 — 0:15",
        "secs": 15,
        "screen": "BROWSER · Dashboard (localhost:3000) — clean, no actions yet",
        "cue": "Dashboard open, zero actions. Cursor still.",
        "narration": (
            "AI agents are making real writes into enterprise systems — "
            "ServiceNow, Salesforce, Jira — with no governance layer in between. "
            "Keystone sits between the agent and your systems. "
            "Let me show you how it works."
        ),
    },
    {
        "idx": 2,
        "time": "0:15 — 0:32",
        "secs": 17,
        "screen": "BROWSER · Agents page (localhost:3000/agents)",
        "cue": "Navigate to the Agents page. Page is mostly empty or has seeded agents. "
               "Stay here — a new pending registration is about to appear.",
        "narration": (
            "When any new agent connects for the first time, "
            "Keystone auto-discovers it — no manual setup required. "
            "Watch what happens when a brand new agent fires its first call."
        ),
        "action": "needs_registration",
        "action_label": "New unknown agent fires first SDK call → pending registration created",
    },
    {
        "idx": 3,
        "time": "0:32 — 0:48",
        "secs": 16,
        "screen": "BROWSER · Agents page — pending registration badge visible",
        "cue": "Refresh the agents page if needed. "
               "Point at the 'CRM Sync Agent' row with the NEEDS REGISTRATION badge. "
               "Hover over it to show the tooltip or detail.",
        "narration": (
            "Keystone created a stub automatically — agent ID, first-seen timestamp, "
            "which tool it called, what workspace it hit. "
            "An admin can now assign it a policy, set rate limits, and activate it. "
            "Until then it still runs, but flagged."
        ),
    },
    {
        "idx": 4,
        "time": "0:48 — 1:05",
        "secs": 17,
        "screen": "VS CODE · sdk/onboarding_example.py",
        "cue": "Switch to VS Code. Draw cursor from 'ks.run(..., mode=observe_only)' "
               "down to 'ks.execute(preview.action_id)'.",
        "narration": (
            "For registered agents, onboarding is one pip install. "
            "First call: observe only — see blast radius and policy decision "
            "without touching a single record. "
            "Second call: run for real."
        ),
        "action": "observe",
        "action_label": "Run OBSERVE ONLY — 20 P3/P4 records, no execution yet",
    },
    {
        "idx": 5,
        "time": "1:05 — 1:23",
        "secs": 18,
        "screen": "BROWSER · Dashboard → click the observe action",
        "cue": "Switch to browser Tab 1 (dashboard). Action appeared with OBSERVE badge. "
               "Click it open. Point at: blast radius → policy decision → 'Run for Real' button. "
               "Pause 2 seconds on the button.",
        "narration": (
            "Blast radius: twenty records. Policy says canary. "
            "Nothing has been touched. "
            "The agent reviews this, decides it looks right, and clicks Run for Real."
        ),
    },
    {
        "idx": 6,
        "time": "1:23 — 1:42",
        "secs": 19,
        "screen": "BROWSER · Click 'Run for Real' → watch it execute",
        "cue": "Click Run for Real. Watch status update live. Scroll as lifecycle fills. "
               "Point at: canary records → all checks passed → COMPLETED → proof badge.",
        "narration": (
            "Canary on five records — five invariants checked — all pass. "
            "Keystone expands to all twenty. "
            "The agent did not touch production until every check cleared. "
            "Proof receipt signed automatically."
        ),
        "action": "blocked",
        "action_label": "Run BLOCKED scenario in background (fires while you narrate Run for Real)",
    },
    {
        "idx": 7,
        "time": "1:42 — 1:54",
        "secs": 12,
        "screen": "BROWSER · Dashboard — blocked action appeared",
        "cue": "Navigate back to dashboard. Blocked action is already there. Click into it. "
               "Point at Policy Reasons → 'has_p1' flag.",
        "narration": (
            "Same agent, broader query — P1 critical incidents included. "
            "Policy blocks it. Zero records modified. "
            "Reason logged, versioned, cryptographically bound."
        ),
    },
    {
        "idx": 8,
        "time": "1:54 — 2:06",
        "secs": 12,
        "screen": "BROWSER · Dashboard — approval action appears",
        "cue": "Back to dashboard. Trigger approval from second monitor. "
               "AWAITING APPROVAL badge appears. Point at it.",
        "narration": (
            "This one touches VIP accounts. "
            "Policy routes it to a human before a single record is modified."
        ),
        "action": "approval",
        "action_label": "Run APPROVAL scenario in background (P2 VIP — awaiting human gate)",
    },
    {
        "idx": 9,
        "time": "2:06 — 2:28",
        "secs": 22,
        "screen": "BROWSER · /approvals → approve → back to action",
        "cue": "Click Approvals tab. Show pending card — blast radius, VIP flag, diff. "
               "Click Approve. Wait for status flip. Back to action — Approved → Executed.",
        "narration": (
            "Full context in band — blast radius, risk flags, diff of every record. "
            "Approval is cryptographically bound to this exact preview. "
            "If data changes before execution, the approval is void. "
            "You cannot approve one thing and execute another."
        ),
    },
    {
        "idx": 10,
        "time": "2:28 — 2:43",
        "secs": 15,
        "screen": "BROWSER · Contained action — breaker badge",
        "cue": "Back to dashboard. Trigger contained from second monitor. Click action. "
               "Point at BREAKER TRIPPED badge → 'only_intended_fields' FAIL row.",
        "narration": (
            "Policy allowed this one. But the system's business rules "
            "modified fields the agent never asked to touch. "
            "Circuit breaker tripped. Five records modified. Fifteen protected."
        ),
        "action": "contained",
        "action_label": "Run CONTAINED scenario in background (breaker trips on side-effect)",
    },
    {
        "idx": 11,
        "time": "2:43 — 3:00",
        "secs": 17,
        "screen": "BROWSER · Proof receipt → back to Dashboard overview",
        "cue": "Open the completed action from segment 6. Click View Proof. "
               "Point at HMAC signature → Cryptographically Verified badge. "
               "Then navigate back to dashboard — all actions visible. Hold.",
        "narration": (
            "Every action: signed proof receipt. HMAC SHA-256. "
            "Who proposed it, what policy decided, who approved, what changed. "
            "Automatic. Every action. Every tool. "
            "Keystone — pip install keystone-governance."
        ),
    },
]


# ─── Render ──────────────────────────────────────────────────────────────────
def render(seg, elapsed_target):
    w = 78
    bar = "━" * w

    clear()
    print()
    print(f"  {VIOLET}{bar}{RESET}")
    print(f"  {VIOLET}  SEGMENT {seg['idx']}/{len(SEGMENTS)}   ·   {seg['time']}   ·   target {seg['secs']}s   ·   elapsed {elapsed_target}s{RESET}")
    print(f"  {VIOLET}{bar}{RESET}\n")

    print(f"  {DIM}{GREY}screen{RESET}")
    print(f"  {CYAN}{BOLD}{seg['screen']}{RESET}\n")

    print(f"  {DIM}{GREY}visual cue{RESET}")
    for line in _wrap(seg["cue"], w - 4):
        print(f"  {AMBER}{line}{RESET}")
    print()

    print(f"  {DIM}{GREY}narration  ──  read aloud{RESET}")
    for line in _wrap(seg["narration"], w - 4):
        print(f"  {WHITE}{BOLD}{line}{RESET}")
    print()

    if seg.get("action"):
        print(f"  {DIM}{GREY}live action{RESET}")
        print(f"  {GREEN}▶  {seg['action_label']}{RESET}")
        print(f"  {GREEN}   (runs when you press ENTER below){RESET}\n")

    print(f"  {VIOLET}{bar}{RESET}")
    if seg.get("action"):
        print(f"  {BOLD}↵  ENTER  →  run action + mark segment complete{RESET}")
    else:
        print(f"  {BOLD}↵  ENTER  →  mark segment complete{RESET}")
    print(f"  {DIM}Ctrl-C to abort.{RESET}")


def _wrap(text, width):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


# ─── Pre-flight ──────────────────────────────────────────────────────────────
def preflight():
    clear()
    print()
    print(f"  {VIOLET}{BOLD}╔══════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"  {VIOLET}{BOLD}║              KEYSTONE  ·  DEMO RECORDING DIRECTOR               ║{RESET}")
    print(f"  {VIOLET}{BOLD}╚══════════════════════════════════════════════════════════════════╝{RESET}")
    print()
    print(f"  {CYAN}Target length : 180 seconds (3:00){RESET}")
    print(f"  {CYAN}Segments      : {len(SEGMENTS)}{RESET}")
    print(f"  {CYAN}Live actions  : 4  (runs SDK calls while you narrate){RESET}")
    print()

    print(f"  {GREY}Preflight check ...{RESET}")
    try:
        p = ks.get_policy()
        print(f"  {GREEN}✓{RESET}  Backend connected  ·  policy: {p['policy_id']} v{p['version']}")
    except Exception as e:
        print(f"  {RED}✗  Cannot reach backend at {BASE_URL}{RESET}")
        print(f"  {RED}   Start it:  cd backend && uvicorn app.main:app --reload --port 8000{RESET}")
        sys.exit(1)
    print(f"  {GREEN}✓{RESET}  UI expected at  {UI_URL}")
    print()

    print(f"  {BOLD}Before you press ENTER:{RESET}")
    print(f"    1.  Main monitor (recorded):")
    print(f"        · Browser at {UI_URL}, logged in as sarah.chen@keystone.org")
    print(f"          Tabs: {UI_URL}  |  {UI_URL}/agents  |  {UI_URL}/approvals")
    print(f"        · VS Code open — sdk/onboarding_example.py, font ~18pt, file fills screen")
    print(f"        · Notifications OFF. Bookmark bar HIDDEN.")
    print(f"    2.  Second monitor (hidden — this script):")
    print(f"        · This terminal. You'll press ENTER here to trigger each live action.")
    print(f"    3.  Start your screen recorder ({GREEN}OBS{RESET} / {GREEN}Loom{RESET} / etc.) — capture main monitor only")
    print(f"    4.  Mic check: speak one line — confirm levels")
    print()
    print(f"  {AMBER}{BOLD}↵  Press ENTER to start the take.{RESET}")
    input()


# ─── Main loop ───────────────────────────────────────────────────────────────
def main():
    preflight()

    start = time.time()
    total_target = 0

    for seg in SEGMENTS:
        total_target += seg["secs"]
        render(seg, total_target)

        try:
            input()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n  {RED}Take aborted.{RESET}\n")
            sys.exit(0)

        if seg.get("action"):
            ACTIONS[seg["action"]]()
            # Small breath after the SDK call so the narrator can mention it
            time.sleep(0.8)

    # ─── Wrap ───
    elapsed = int(time.time() - start)
    clear()
    print()
    print(f"  {GREEN}{BOLD}╔══════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"  {GREEN}{BOLD}║                        TAKE COMPLETE                             ║{RESET}")
    print(f"  {GREEN}{BOLD}╚══════════════════════════════════════════════════════════════════╝{RESET}")
    print()
    print(f"  {CYAN}Target length : 180s{RESET}")
    print(f"  {CYAN}Actual length : {elapsed}s   ({'on pace' if abs(elapsed-180) < 20 else 'review pacing'}){RESET}")
    print()
    print(f"  {BOLD}Now:{RESET}")
    print(f"    ·  Stop the screen recorder.")
    print(f"    ·  Watch the take back once before editing.")
    print(f"    ·  If any segment felt off, delete {GREY}keystone.db{RESET} and re-run this script.")
    print()
    print(f"  {DIM}Review actions in UI:  {UI_URL}{RESET}\n")


if __name__ == "__main__":
    main()