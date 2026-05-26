# action-marshall

> Action-level release control for AI agents. Preview, approve, canary, halt, and audit tool actions before they touch production.

`action-marshall` is the Python SDK for [Action Marshall](https://github.com/SatwikReddySripathi/action-marshall). Wrap the tools or functions your agent already calls — Action Marshall runs preview, policy, approval, canary, breaker, and signed audit before the action is released.

**Status:** `0.1.0` — pre-1.0 alpha. The API may change before `1.0.0`.

---

## Install

```bash
pip install action-marshall
```

Python 3.9+.

### You also need a backend

`action-marshall` is the client SDK. It talks to an Action Marshall backend that runs the policy engine, signs receipts, and stores audit history. To try it end-to-end you have two paths:

**Option A — local backend via Docker (recommended for evaluation)**

```bash
git clone https://github.com/SatwikReddySripathi/action-marshall.git
cd action-marshall
docker compose up --build
```

Backend lives at `http://localhost:8000`, dashboard at `http://localhost:3000`. Wait until `curl http://localhost:8000/ready` returns `200`. Default API key is `am_test_demo_key_001`.

**Option B — point at a hosted backend** *(planned — hosted Action Marshall is not live yet)*

Once hosted Action Marshall opens, you'll get an API key and a `base_url`. [Join the waitlist](https://github.com/SatwikReddySripathi/action-marshall#self-host-or-hosted).

Optional framework adapters:

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

---

## Quickstart

Assuming the backend is up at `http://localhost:8000`:

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

Open `result.ui_urls["detail"]` in your browser to see the full action in the dashboard.

---

## Wrap an existing function

The killer pattern — every call becomes a governed action:

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

result = update_incident({"incident_id": "INC001", "status": "resolved"})
```

- `AUTO` → the wrapped function runs normally.
- `BLOCK` → wrapped function is **not** called; `MarshallDenied` is raised.
- `APPROVAL_REQUIRED` → wrapped function is **not** called; `MarshallApprovalRequired` is raised. Approve in Slack or the web UI, the next call goes through.

Pass `on_denied=...` / `on_approval_required=...` callbacks if you want to handle these without exceptions:

```python
@ks.wrap_function(
    tool="servicenow", action_type="update_incident",
    connector="servicenow_sim", agent_id="incident-triage",
    on_denied=lambda err: {"status": "blocked-by-policy", "reasons": err.result.decision.get("reasons")},
)
def update_incident(payload: dict) -> dict: ...
```

---

## Preview without executing

```python
preview = ks.preview(Action(...))
print(preview.decision_value, preview.blast_radius, preview.preview_hash)
```

Same lifecycle as `run` but no writes happen — the policy and canary phases evaluate and a receipt is signed for the dry run.

---

## Wrap a LangChain tool

`available now` *(experimental)*. Requires `pip install "action-marshall[langchain]"`.

```python
from langchain_core.tools import tool
from action_marshall import MarshallClient
from action_marshall.adapters.langchain import wrap_langchain_tool

@tool
def update_incident(payload: dict) -> dict:
    ...

ks = MarshallClient(api_key="am_...", base_url="http://localhost:8000")

protected = wrap_langchain_tool(
    update_incident, ks=ks,
    tool="servicenow", action_type="update_incident",
    connector="servicenow_sim", agent_id="incident-triage",
)
# protected.invoke({...}) is now governed.
```

---

## Verify a signed receipt

```python
receipt = ks.verify_receipt("act_abc123")
print(receipt.verified)   # True if the HMAC signature matches
print(receipt.signature)
```

Server-side verification — the backend re-signs the receipt body and compares with constant-time HMAC. For fully offline verification with a local `PROOF_SECRET`, see the [security docs](https://github.com/SatwikReddySripathi/action-marshall/blob/main/docs/security.md#verifying-receipts-offline).

---

## Decisions

| Decision              | Meaning                                                          |
|-----------------------|------------------------------------------------------------------|
| `AUTO`                | Allowed without approval. The wrapped function runs.             |
| `CANARY`              | Allowed, but a canary subset runs first; the breaker can halt.   |
| `APPROVAL_REQUIRED`   | Human approval needed before execution.                          |
| `BLOCK`               | Disallowed. The wrapped function is not called.                  |

Decision hierarchy: `BLOCK > APPROVAL_REQUIRED > CANARY > AUTO`. Policies escalate, never de-escalate.

## Connectors

| Connector            | Use for                                       | Status         |
|----------------------|-----------------------------------------------|----------------|
| `servicenow_sim`     | Simulated ServiceNow incidents (demo / dev)   | available now  |
| `servicenow_real`    | Live ServiceNow instance                      | available now  |
| `email_generic`      | Outbound email actions                        | available now  |
| `jira_real`          | Live Jira Cloud                               | planned        |

---

## Public API

```python
from action_marshall import (
    MarshallClient,
    Action, ActionParams, Actor, Approval, Approver,
    ActionResult, PreviewResult, Receipt,
    MarshallError, MarshallAPIError, MarshallDenied, MarshallApprovalRequired,
)
```

The type-checker-friendly `py.typed` marker ships in the wheel — mypy and pyright will pick up our annotations automatically.

---

## CLI

`action-marshall` is also installed as a CLI binary. Useful for one-off operations, CI smoke checks, and tools that aren't easily called from Python.

```bash
action-marshall --help
action-marshall init                            # write ~/.marshall/config.json
action-marshall preview action.json
action-marshall run action.json
action-marshall receipts list
action-marshall receipts verify act_abc123
```

Full reference: [docs/cli.md](https://github.com/SatwikReddySripathi/action-marshall/blob/main/docs/cli.md).

---

## Local development

```bash
git clone https://github.com/SatwikReddySripathi/action-marshall.git
cd action-marshall/sdk
pip install -e ".[dev]"
pytest
```

## License

MIT. See [LICENSE](https://github.com/SatwikReddySripathi/action-marshall/blob/main/LICENSE).
