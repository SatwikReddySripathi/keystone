# keystone-governance

Drop-in transaction governance for AI agent workflows.

Before your agent modifies records, sends emails, or executes bulk operations,
Keystone previews the blast radius, evaluates policy, requests human approval
when rules demand it, and generates a tamper-evident proof receipt.

## Install

```bash
pip install keystone-governance
```

## Quick start

```python
from keystone import Keystone, Action, ActionParams, Actor

ks = Keystone(api_key="your-api-key")

result = ks.run(Action(
    actor=Actor(id="my-agent", name="My Agent"),
    tool="email",
    action_type="send_email",
    params=ActionParams(
        connector="email_generic",
        query={"recipients": ["alice@team.com", "bob@team.com"]},
        changes={"subject": "Daily Report", "body_preview": "Summary..."}
    )
), mode="observe_only")

if result.decision_value == "AUTO":
    send_your_email()
elif result.decision_value == "APPROVAL_REQUIRED":
    print(f"Held for approval: {result.ui_urls.get('detail')}")
elif result.decision_value == "BLOCK":
    print("Blocked by policy")
```

## Decisions

| Value | Meaning |
|---|---|
| `AUTO` | Approved automatically — proceed |
| `CANARY` | Approved with canary-first execution |
| `APPROVAL_REQUIRED` | A human must approve in the UI before you proceed |
| `BLOCK` | Stopped by policy — do not execute |

## Modes

| mode | Use when |
|---|---|
| `observe_only` | Your agent handles execution (email, custom APIs) |
| `enforce` | Keystone handles execution (ServiceNow, Jira) |

## Connectors

| connector | Use for |
|---|---|
| `email_generic` | Any outbound email send |
| `servicenow_sim` | ServiceNow (demo / test) |
| `servicenow_real` | Live ServiceNow instance |
| `jira_real` | Jira Cloud (preview-only) |

## Result fields

```python
result.decision_value   # "AUTO" | "CANARY" | "APPROVAL_REQUIRED" | "BLOCK"
result.blast_radius     # number of records/recipients affected
result.action_id        # use to poll for approval status
result.is_blocked       # True if stopped for any reason
result.ui_urls          # {"detail": "https://..."}
result.proof_url        # tamper-evident receipt URL
```

## Documentation

Full documentation and self-hosting guide: https://github.com/YOUR_GITHUB_USERNAME/keystone
