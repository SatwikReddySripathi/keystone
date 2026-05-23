#!/usr/bin/env python3
"""
Seed a concise set of actions for a launch video.

This script is optimized for a short, high-signal product reel:
  1. A safe action completes with canary-first execution
  2. A risky action is contained by the circuit breaker
  3. A dangerous action is blocked by policy
  4. A sensitive action waits for human approval

Run this after starting the backend and UI on a fresh database.
"""
from __future__ import annotations

import os
import time

import requests
from keystone import Action, ActionParams, Actor, Keystone

API_KEY = os.getenv("KEYSTONE_API_KEY", "ks_test_demo_key_001")
BASE_URL = os.getenv("KEYSTONE_BASE_URL", "http://localhost:8000")
UI_URL = os.getenv("KEYSTONE_UI_URL", "http://localhost:3000").rstrip("/")

ks = Keystone(base_url=BASE_URL, api_key=API_KEY)

ACTOR = Actor(
    id="incident-resolver-v2",
    name="Incident Resolver Agent",
    type="agent",
)


def section(title: str, subtitle: str = "") -> None:
    print("\n" + "=" * 78)
    print(title)
    if subtitle:
        print(subtitle)
    print("=" * 78)


def run_scene(label: str, action: Action, mode: str = "enforce") -> str:
    print(f"\n[{label}]")
    result = ks.run(action, mode=mode)
    print(f"status       : {result.status}")
    print(f"decision     : {result.decision_value}")
    print(f"blast radius : {result.blast_radius}")
    print(f"detail       : {result.ui_urls.get('detail', f'{UI_URL}/actions/{result.action_id}')}")
    if result.proof_available:
        print(f"proof        : {UI_URL}/actions/{result.action_id}/proof")
    return result.action_id


def main() -> int:
    section(
        "KEYSTONE LAUNCH DEMO SEED",
        "Creating the four statuses that look best in a short launch video.",
    )

    try:
        requests.get(f"{BASE_URL}/health", timeout=3).raise_for_status()
        policy = ks.get_policy()
    except Exception as exc:
        print(f"Cannot reach Keystone at {BASE_URL}: {exc}")
        print("Start the backend first: cd backend && python -m uvicorn app.main:app --reload --port 8000")
        return 1

    print(f"Connected to Keystone. Active policy: {policy.get('policy_id')} v{policy.get('version')}")
    print(f"UI: {UI_URL}")
    print("Tip: reset backend/keystone.db before recording for the cleanest run.")

    safe_reassign = Action(
        tool="servicenow",
        action_type="bulk_update",
        environment="simulation",
        actor=ACTOR,
        params=ActionParams(
            connector="servicenow_sim",
            query={"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}},
            changes={"assignment_group": "Triage Team"},
        ),
        workspace_id="ws_platform",
        connection_id="conn_snow",
    )

    contained_resolve = Action(
        tool="servicenow",
        action_type="bulk_update",
        environment="simulation",
        actor=ACTOR,
        params=ActionParams(
            connector="servicenow_sim",
            query={"assignment_group": "Triage Team"},
            changes={"state": "resolved"},
        ),
        workspace_id="ws_platform",
        connection_id="conn_snow",
    )

    blocked_resolve = Action(
        tool="servicenow",
        action_type="bulk_update",
        environment="simulation",
        actor=ACTOR,
        params=ActionParams(
            connector="servicenow_sim",
            query={"state": "open"},
            changes={"state": "resolved"},
        ),
        workspace_id="ws_platform",
        connection_id="conn_snow",
    )

    approval_flow = Action(
        tool="servicenow",
        action_type="bulk_update",
        environment="simulation",
        actor=ACTOR,
        params=ActionParams(
            connector="servicenow_sim",
            query={"state": "open", "priority": "P2"},
            changes={"assignment_group": "Executive Support"},
        ),
        workspace_id="ws_platform",
        connection_id="conn_snow",
    )

    action_ids: list[str] = []
    action_ids.append(run_scene("PASSED", safe_reassign))
    time.sleep(1)
    action_ids.append(run_scene("CONTAINED", contained_resolve))
    time.sleep(1)
    action_ids.append(run_scene("BLOCKED", blocked_resolve))
    time.sleep(1)
    action_ids.append(run_scene("PENDING APPROVAL", approval_flow))

    section("RECORDING CHECKLIST")
    print(f"1. Open {UI_URL} and show the dashboard with all four statuses present.")
    print(f"2. Open the contained action detail: {UI_URL}/actions/{action_ids[1]}")
    print(f"3. Open the blocked action detail:   {UI_URL}/actions/{action_ids[2]}")
    print(f"4. Open the proof page:              {UI_URL}/actions/{action_ids[1]}/proof")
    print(f"5. Open the pending approval page:   {UI_URL}/actions/{action_ids[3]}")
    print("\nIf you want the approval status to resolve on-screen, approve it in the UI or Slack while recording.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
