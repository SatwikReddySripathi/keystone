# Keystone

**Transaction governance for AI agents.**

Keystone sits between an AI agent's *intent* and its *execution*. Before any agent-initiated change reaches your production systems, Keystone previews the blast radius, enforces policy, gates on human approval when required, runs a canary, trips a circuit breaker if reality diverges from the preview, and emits a signed audit receipt — all in a single SDK call.

---

## The Problem

AI agents are increasingly trusted to take real actions in enterprise systems — updating tickets, reassigning workloads, closing incidents, modifying records at scale. The problem isn't capability. The problem is **trust infrastructure**.

When an agent bulk-updates 200 records and something goes wrong, who approved it? What policy allowed it? What exactly changed vs. what was previewed? Was there a way to stop it mid-execution? Is there a tamper-evident log?

Most teams answer these questions with manual processes, post-hoc logging, or by simply not giving agents write access at all. Keystone makes governed execution the default.

---

## How It Works

```
Agent intent ──► Keystone ──► Connector ──► Your system
```

Six stages run automatically on every `ks.run()` call:

| Stage | What it does |
|---|---|
| **Preview** | Queries affected records, computes diffs, measures blast radius, generates a content hash |
| **Policy** | Evaluates versioned YAML rules → `AUTO` / `CANARY` / `APPROVAL_REQUIRED` / `BLOCK` |
| **Approval Gate** | If required, pauses and notifies via Slack or web UI. Only verified employees can approve. |
| **Canary** | Executes on a deterministic subset (default: 5 records). Checks results before expanding. |
| **Circuit Breaker** | If canary reveals unexpected side-effects, unauthorized field mutations, or error spikes — halts immediately |
| **Proof** | HMAC-SHA256 signed receipt covering the full lifecycle: who proposed, what was previewed, what policy decided, who approved, what changed |

---

## Quick Start

**Prerequisites:** Python 3.11+, Node 18+

```bash
git clone https://github.com/your-handle/keystone.git
cd keystone

# Backend
cd backend
cp .env.example .env          # fill in your values
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# UI (new terminal)
cd ui
cp .env.example .env.local
npm install && npm run dev

# Run demo (new terminal)
cd sdk
pip install -e .
python demo.py
```

Open [http://localhost:3000](http://localhost:3000) to see the transaction governance dashboard.

---

## SDK

Three lines to integrate any agent:

```python
from keystone import Keystone, Action, ActionParams, Actor

ks = Keystone(api_key="ks_...", base_url="https://your-keystone.internal")

result = ks.run(Action(
    tool="servicenow",
    environment="production",
    actor=Actor(name="IncidentTriageAgent", type="autonomous"),
    params=ActionParams(
        connector="servicenow_real",
        query={"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}},
        changes={"assignment_group": "Tier-2 Support"},
    ),
))

print(result.status)          # completed / contained / blocked / pending_approval
print(result.decision)        # AUTO / CANARY / APPROVAL_REQUIRED / BLOCK
print(result.proof_id)        # signed receipt ID
```

If `status` is `pending_approval`, Keystone has already posted a Slack message with Approve / Deny buttons to the authorized approvers for that tool. Execution resumes when approved.

---

## Demo Scenarios

`sdk/demo.py` runs five end-to-end scenarios against the built-in simulator:

| Scenario | What happens |
|---|---|
| **Completed** | 20 P3/P4 tickets → canary passes → full expansion → signed proof |
| **Contained** | Canary exposes a business rule side-effect → circuit breaker trips → 15 records protected |
| **Blocked** | P1 tickets in scope → policy BLOCK → zero records touched |
| **Approval** | P2 + VIP caller → Slack notification → human approves → execution resumes |
| **Dry Run** | Observe-only mode → full preview + policy decision, no writes, "Run for Real" button in UI |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  SDK  ks.run(Action(...))                                           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ POST /v1/run
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Backend (FastAPI + SQLite)                                         │
│                                                                     │
│  Preview ──► Policy ──► Approval Gate ──► Canary ──► Breaker ──► Proof │
│     │            │             │             │           │          │
│  blast        YAML          Slack /       5 records  any fail    HMAC  │
│  radius       rules          web UI       first      → halt    -SHA256 │
│  diffs        version        employee     checks              receipt  │
│  hash         reasons        validation   expand                       │
└────────────────────────────────────┬────────────────────────────────┘
                                     │
                        ┌────────────▼────────────┐
                        │  Connector Interface     │
                        │  (tool-agnostic)         │
                        │                         │
                        │  query()                │
                        │  compute_diffs()        │
                        │  execute_update()       │
                        │  get_record()           │
                        └────────┬────────────────┘
                                 │
               ┌─────────────────┼──────────────────┐
               ▼                 ▼                  ▼
        ServiceNow           Jira / Salesforce    Your tool
        (sim + real)         (implement 4 methods)
```

The UI (Next.js) connects to the same backend and shows every transaction with full lifecycle detail, policy reasoning, canary results, and proof verification.

---

## Adding a Connector

Keystone is tool-agnostic. Implement four methods to add any system:

```python
# backend/app/connectors/my_tool.py
from app.connectors.base import BaseConnector

class MyToolConnector(BaseConnector):
    def query(self, filters: dict) -> list[dict]:
        # fetch records matching filters
        # return [{"sys_id": "...", ...}, ...]

    def compute_diffs(self, records: list[dict], changes: dict) -> list[dict]:
        # return [{"sys_id": "...", "field": "...", "from": ..., "to": ...}, ...]

    def execute_update(self, sys_ids: list[str], changes: dict, metadata=None) -> list[dict]:
        # apply changes, return [{"sys_id": "...", "success": True, "changes_applied": [...]}]

    def get_record(self, sys_id: str) -> dict | None:
        # fetch a single record
```

Register it in one line:

```python
# backend/app/routes/actions.py
CONNECTORS = {
    "servicenow_sim": get_snow,
    "my_tool": lambda: MyToolConnector(),   # ← add this
}
```

That's it. Preview, policy, canary, circuit breaker, approval, and proof all work without any changes.

---

## Policy Engine

Policies are versioned YAML files. The engine evaluates rules in priority order and takes the strictest decision:

```yaml
# backend/app/policies/default_policy.yaml
policy_id: default
version: "1.1.0"
thresholds:
  max_blast_radius: 50
  canary_size: 5
  canary_max_error_rate: 0.0

rules:
  - name: blast_radius_limit
    condition: { field: blast_radius, op: gt, value: 50 }
    decision: BLOCK

  - name: no_p1_incidents
    condition: { flag: has_p1, op: eq, value: true }
    decision: BLOCK

  - name: p2_approval_required
    condition: { flag: has_p2, op: eq, value: true }
    decision: APPROVAL_REQUIRED

  - name: canary_for_medium_blast
    condition: { field: blast_radius, op: gte, value: 10 }
    decision: CANARY

  - name: auto_small_changes
    condition: { field: blast_radius, op: lte, value: 10 }
    decision: AUTO
```

Decisions follow a strict hierarchy: `BLOCK > APPROVAL_REQUIRED > CANARY > AUTO`. Multiple matching rules escalate, never de-escalate.

---

## Audit Proof

Every completed (or halted) transaction generates a signed receipt:

```json
{
  "receipt": {
    "action": { "action_id": "act_...", "tool": "servicenow", "actor": { "name": "IncidentTriageAgent" } },
    "policy": { "decision": "CANARY", "version": "1.1.0", "reasons": [...] },
    "preview": { "blast_radius": 20, "preview_hash": "sha256:..." },
    "execution": {
      "phase": "canary",
      "checks": [
        { "check_name": "no_out_of_scope", "passed": true },
        { "check_name": "only_intended_fields", "passed": false }
      ],
      "breaker": { "tripped": true, "reason": "only_intended_fields failed" }
    },
    "approvals": [],
    "timeline": [...]
  },
  "signature": "hmac-sha256:...",
  "verified": true
}
```

Receipts are verifiable offline. The `/proof` endpoint re-checks the signature and renders a formatted audit view.

---

## Why Not Just Log Everything?

Logging records *what happened*. Keystone governs *what is allowed to happen* — before it happens.

| | Logging / Observability | Keystone |
|---|---|---|
| Timing | After execution | Before + during |
| Blast radius | Reconstructed from logs | Computed pre-execution |
| Human approval | Out-of-band (email/ticket) | Built-in, cryptographically bound to receipt |
| Partial execution | Hard to detect | Circuit breaker halts mid-execution |
| Audit trail | Log files | Signed, tamper-evident receipt per transaction |

---

## Stack

| Layer | Technology |
|---|---|
| SDK | Python 3.11+ |
| Backend | FastAPI, SQLite, Python 3.11+ |
| UI | Next.js 14, TypeScript, Tailwind CSS |
| Auth | HMAC API keys, per-org scoping |
| Approval notifications | Slack interactive messages |
| Proof signing | HMAC-SHA256 |
| Deployment | Docker Compose |

---

## Self-Hosting

```bash
docker compose up
```

Three containers: `backend` (port 8000), `ui` (port 3000), ready to connect to your tools. No external dependencies. SQLite by default; swap in Postgres by updating the connection string.

---

## Project Status

Keystone is a working MVP. The core governance pipeline — preview, policy, approval, canary, circuit breaker, proof — is implemented and tested end-to-end.

**Built and working:**
- [x] Full 6-stage governance pipeline
- [x] SDK (3-line integration)
- [x] Policy engine with versioned YAML rules
- [x] Slack approval flow with employee validation
- [x] Circuit breaker with 5 post-execution safety checks
- [x] HMAC-SHA256 signed audit receipts
- [x] ServiceNow connector (simulator + real REST API)
- [x] Web UI: transaction list, detail view, proof verification
- [x] Docker Compose deployment
- [x] Multi-tenant (org-scoped API keys)

**On the roadmap:**
- [ ] Jira, Salesforce, GitHub connectors
- [ ] Webhook-based approval (not just Slack)
- [ ] Policy dry-run diff: "what would change if we switched to strict policy?"
- [ ] Prometheus metrics endpoint
- [ ] Agent SDK for LangChain / LlamaIndex / custom agents
- [ ] Postgres support
- [ ] Role-based access to the UI

---

## Contributing

Issues, pull requests, and connector implementations welcome.

```bash
# Run backend tests
cd backend && python test_api.py && python test_canary.py && python test_proof.py

# Run full demo
cd sdk && python demo.py
```

---

## License

MIT
