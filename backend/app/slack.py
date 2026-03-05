"""
Slack integration — post approval requests, handle button clicks.

When an action hits APPROVAL_REQUIRED, we post a rich message to Slack
with blast radius, flags, preview hash, sample diffs, and Approve/Deny buttons.

When someone clicks a button, Slack sends a POST to /v1/slack/interact
with the action details. We record the approval and execute the action.
"""
import os
import json
import requests

SLACK_WEBHOOK_URL = os.getenv(
    "SLACK_WEBHOOK_URL",
    "https://hooks.slack.com/services/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"
)


def post_approval_request(
    action_id: str,
    blast_radius: int,
    preview_hash: str,
    policy_version: str,
    flags: dict,
    reasons: list[dict],
    diffs_sample: list[dict],
    actor: dict,
    tool: str,
    action_type: str,
    ui_url: str,
) -> bool:
    """
    Post an approval request to Slack.
    Returns True if the message was sent successfully.
    """
    # Build flag badges
    flag_parts = []
    if flags.get("has_p1"):
        flag_parts.append(":red_circle: P1 Present")
    if flags.get("has_p2"):
        flag_parts.append(":large_orange_circle: P2 Present")
    if flags.get("has_vip"):
        flag_parts.append(":star: VIP Caller")
    if flags.get("cross_group"):
        flag_parts.append(":arrows_counterclockwise: Cross-Group")
    if flags.get("state_transition"):
        flag_parts.append(":arrow_right: State Transition")
    flags_text = "  ".join(flag_parts) if flag_parts else "None"

    # Build reasons text
    reasons_text = "\n".join(
        f"• `{r['rule']}`: {r['reason']}" for r in reasons
    )

    # Build diffs sample
    diffs_text = ""
    for d in diffs_sample[:3]:
        fields = d.get("fields", {})
        changes = []
        for field, val in fields.items():
            changes.append(f"`{field}`: {val['before']} → {val['after']}")
        if changes:
            diffs_text += f"*{d.get('number', d.get('sys_id', '?'))}*: {', '.join(changes)}\n"
    if not diffs_text:
        diffs_text = "No field changes to show"

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": ":shield: Keystone — Approval Required",
                    "emoji": True,
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Action ID*\n`{action_id}`"},
                    {"type": "mrkdwn", "text": f"*Blast Radius*\n:boom: {blast_radius} records"},
                    {"type": "mrkdwn", "text": f"*Tool*\n{tool}.{action_type}"},
                    {"type": "mrkdwn", "text": f"*Proposed by*\n{actor.get('name', 'Unknown')} ({actor.get('type', 'agent')})"},
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Risk Flags*\n{flags_text}",
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Policy Decision*\n{reasons_text}",
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Sample Diffs*\n{diffs_text}",
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Preview Hash*\n`{preview_hash[:16]}...`"},
                    {"type": "mrkdwn", "text": f"*Policy Version*\n`{policy_version}`"},
                ]
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":white_check_mark: Approve", "emoji": True},
                        "style": "primary",
                        "action_id": "keystone_approve",
                        "value": json.dumps({
                            "action_id": action_id,
                            "preview_hash": preview_hash,
                            "policy_version": policy_version,
                        }),
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":x: Deny", "emoji": True},
                        "style": "danger",
                        "action_id": "keystone_deny",
                        "value": json.dumps({
                            "action_id": action_id,
                        }),
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":mag: View Details", "emoji": True},
                        "url": ui_url,
                        "action_id": "keystone_view",
                    },
                ]
            },
        ]
    }

    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        return resp.status_code == 200
    except Exception as e:
        print(f"Slack notification failed: {e}")
        return False


def post_approval_result(action_id: str, approver: str, approved: bool, status: str):
    """Post a follow-up message showing the approval result."""
    if approved:
        emoji = ":white_check_mark:"
        text = f"{emoji} *Action `{action_id}` approved* by {approver}\nStatus: `{status}`"
    else:
        emoji = ":x:"
        text = f"{emoji} *Action `{action_id}` denied* by {approver}\nStatus: `blocked`"

    payload = {
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
            }
        ]
    }

    try:
        requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
    except Exception:
        pass