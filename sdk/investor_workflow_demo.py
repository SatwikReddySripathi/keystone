#!/usr/bin/env python3
"""
Guide a founder-led workflow demo for YC, a16z, and other investors.

This script is optimized for an end-to-end recording:
  1. Create an observe-only preview you can inspect in the UI
  2. Create an approval-required action
  3. Wait while you approve it in the UI or Slack
  4. Print the final detail and proof URLs once execution finishes
"""
from __future__ import annotations

import os
import time

import requests
from keystone import Action, ActionParams, Actor, Keystone

API_KEY = os.getenv("KEYSTONE_API_KEY", "ks_test_demo_key_001")
BASE_URL = os.getenv("KEYSTONE_BASE_URL", "http://localhost:8000")
UI_URL = os.getenv("KEYSTONE_UI_URL", "http://localhost:3000").rstrip("/")
POLL_SECONDS = int(os.getenv("KEYSTONE_APPROVAL_POLL_SECONDS", "180"))

ks = Keystone(base_url=BASE_URL, api_key=API_KEY)

ACTOR = Actor(
    id="incident-resolver-v2",
    name="Incident Resolver Agent",
    type="agent",
)


def heading(title: str) -> None:
    print("\n" + "-" * 78)
    print(title)
    print("-" * 78)


def main() -> int:
    heading("KEYSTONE INVESTOR WORKFLOW DEMO")
    try:
        requests.get(f"{BASE_URL}/health", timeout=3).raise_for_status()
        policy = ks.get_policy()
    except Exception as exc:
        print(f"Cannot reach Keystone at {BASE_URL}: {exc}")
        print("Start the backend first: cd backend && python -m uvicorn app.main:app --reload --port 8000")
        return 1

    print(f"Connected to Keystone. Active policy: {policy.get('policy_id')} v{policy.get('version')}")
    print(f"UI: {UI_URL}")
    print("Suggested tabs: /workspaces, /policies, /agents, /approvals, and the action detail pages printed below.")

    preview_action = Action(
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

    approval_action = Action(
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

    heading("STEP 1: OBSERVE-ONLY PREVIEW")
    preview_result = ks.run(preview_action, mode="observe_only")
    print(f"status       : {preview_result.status}")
    print(f"decision     : {preview_result.decision_value}")
    print(f"blast radius : {preview_result.blast_radius}")
    print(f"detail       : {preview_result.ui_urls.get('detail', f'{UI_URL}/actions/{preview_result.action_id}')}")
    print("Show the preview hash, policy reasons, and diff table on this page.")

    heading("STEP 2: HUMAN APPROVAL FLOW")
    approval_result = ks.run(approval_action, mode="enforce")
    print(f"status       : {approval_result.status}")
    print(f"decision     : {approval_result.decision_value}")
    print(f"blast radius : {approval_result.blast_radius}")
    print(f"detail       : {approval_result.ui_urls.get('detail', f'{UI_URL}/actions/{approval_result.action_id}')}")
    print(f"approvals    : {UI_URL}/approvals")

    if approval_result.status != "awaiting_approval":
        print("\nThe action did not land in awaiting_approval.")
        print("Reset backend/keystone.db and rerun if you want the clean investor workflow.")
        return 0

    heading("STEP 3: APPROVE WHILE RECORDING")
    print("Approve the action in the Approvals page or from Slack.")
    print("The script will watch for the final status and then print the proof URL.")
    print("Polling", end="", flush=True)

    detail_url = f"{UI_URL}/actions/{approval_result.action_id}"
    proof_url = f"{UI_URL}/actions/{approval_result.action_id}/proof"

    live_statuses = {"awaiting_approval", "approved", "canary_executing", "expanding"}
    for _ in range(POLL_SECONDS):
        time.sleep(1)
        print(".", end="", flush=True)
        detail = ks.get_action(approval_result.action_id)
        current_status = detail.get("action", {}).get("status")
        if current_status not in live_statuses:
            print("\n")
            heading("STEP 4: FINAL STATE")
            print(f"final status : {current_status}")
            print(f"detail       : {detail_url}")
            print(f"proof        : {proof_url}")
            print("After this, show the record timeline, safety checks, audit note, and proof verification page.")
            return 0

    print("\n")
    print("Timed out waiting for completion.")
    print(f"Keep recording from: {detail_url}")
    print("Once the action finishes, open the proof page and the audit trail.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
