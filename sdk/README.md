# action-marshall

> Action-level release control for AI agents. Preview, approve, canary, halt, and audit tool actions before they touch production.

`action-marshall` is the Python SDK for [Action Marshall](https://github.com/SatwikReddySripathi/action_marshall). Wrap the tools or functions your agent already calls, and Action Marshall runs preview, policy, approval, canary, breaker, and signed audit before the action is released.

**Status:** `0.1.0` — pre-1.0 alpha. The API may change before `1.0.0`.

## Install

```bash
pip install action-marshall
```

Optional framework adapters (install only what you use):

```bash
pip install "action-marshall[langchain]"     # available now (experimental)
pip install "action-marshall[langgraph]"     # planned
pip install "action-marshall[crewai]"        # planned
pip install "action-marshall[autogen]"       # planned
pip install "action-marshall[mcp]"           # planned
pip install "action-marshall[llamaindex]"    # planned
pip install "action-marshall[openai]"        # planned
pip install "action-marshall[all]"
```

## Quickstart

```python
from action_marshall import MarshallClient, Action, ActionParams

ks = MarshallClient(
    api_key="am_test_demo_key_001",
    base_url="http://localhost:8000",
)

result = ks.run(Action(
    tool="servicenow",
    action_type="bulk_update",
    params=ActionParams(
        connector="servicenow_sim",
        query={"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}},
        changes={"state": "in_progress"},
    ),
))

print(result.decision_value)   # AUTO | CANARY | BLOCK | APPROVAL_REQUIRED
print(result.status)           # completed | contained | blocked | awaiting_approval | observed
print(result.blast_radius)     # 17
print(result.proof_url)        # /v1/actions/<id>/proof
```

## Preview without executing

```python
preview = ks.preview(Action(...))
print(preview.decision_value, preview.blast_radius)
```

## Wrap an existing function

```python
@ks.wrap_function(
    tool="servicenow",
    action_type="update_incident",
    connector="servicenow_sim",
    agent_id="incident-triage",
)
def update_incident(payload: dict) -> dict:
    # your existing implementation
    ...

# Each call is now governed: Action Marshall evaluates policy before update_incident runs.
result = update_incident({"incident_id": "INC001", "status": "resolved"})
```

If the policy decides `BLOCK`, the wrapped function is **not** called and a `MarshallDenied` is raised. If it decides `APPROVAL_REQUIRED`, a `MarshallApprovalRequired` is raised. Pass `on_denied=...` / `on_approval_required=...` callbacks instead if you do not want exceptions.

## Wrap a LangChain tool

`available now` (experimental).

```python
from langchain_core.tools import tool
from action_marshall import MarshallClient
from action_marshall.adapters.langchain import wrap_langchain_tool

@tool
def update_incident(payload: dict) -> dict:
    ...

ks = MarshallClient(api_key="...", base_url="http://localhost:8000")

protected = wrap_langchain_tool(
    update_incident,
    ks=ks,
    tool="servicenow",
    action_type="update_incident",
    connector="servicenow_sim",
    agent_id="incident-triage",
)

# protected.invoke(...) is now governed.
```

## Verify a signed receipt

```python
receipt = ks.verify_receipt("act_abc123")
print(receipt.verified)   # True if the HMAC signature matches
print(receipt.signature)
```

## Decisions

| Decision              | Meaning                                                          |
|-----------------------|------------------------------------------------------------------|
| `AUTO`                | Allowed without approval. The wrapped function runs.             |
| `CANARY`              | Allowed, but a canary subset runs first and breaker can halt.    |
| `APPROVAL_REQUIRED`   | Human approval needed before execution.                          |
| `BLOCK`               | Disallowed. The wrapped function is not called.                  |

## Connectors

| Connector            | Use for                                       | Status         |
|----------------------|-----------------------------------------------|----------------|
| `servicenow_sim`     | Simulated ServiceNow incidents (demo / dev)   | available now  |
| `servicenow_real`    | Live ServiceNow instance                      | available now  |
| `email_generic`      | Outbound email actions                        | available now  |
| `jira_real`          | Live Jira Cloud                               | planned        |

## Public API

```python
from action_marshall import (
    MarshallClient,
    Action, ActionParams, Actor, Approval, Approver,
    ActionResult, PreviewResult, Receipt,
    MarshallError, MarshallAPIError, MarshallDenied, MarshallApprovalRequired,
)
```

## Local development

```bash
git clone https://github.com/SatwikReddySripathi/action_marshall
cd action_marshall/sdk
pip install -e ".[dev]"
pytest
```

## License

MIT. See [LICENSE](../LICENSE).
