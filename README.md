# Keystone

**Transaction governance for autonomous agent actions.**

Preview the diff. Enforce delegated authority. Canary the action. Auto-stop if reality diverges. Emit audit-grade proof.

---

## What Keystone Does

When an AI agent says "I want to bulk-update 20 ServiceNow incidents," Keystone sits between the intent and the execution:

1. **Preview** — Shows exactly which records would be affected, what fields would change, and what risks exist
2. **Policy** — Evaluates versioned YAML rules to decide: auto-approve, require canary, require human approval, or block
3. **Approval** — If required, pauses execution and notifies via Slack/UI. Only authorized employees can approve, verified against the org's employee directory
4. **Canary** — Executes on 5 records first (deterministically selected), then checks the results before touching the rest
5. **Circuit Breaker** — If the canary reveals unexpected changes (business rule side-effects, unauthorized field modifications, error spikes), automatically halts expansion
6. **Proof** — Generates an HMAC-SHA256 signed receipt of the entire lifecycle: who proposed, what was previewed, what policy decided, who approved, what happened, and why it stopped

---

## One-Liner

Keystone is a **release manager for agent actions** — like LaunchDarkly for autonomous agents, but instead of feature flags governing code releases, Keystone governs agent-initiated state changes in enterprise systems.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        SDK (Python)                         │
│   ks = Keystone(api_key="...")                              │
│   result = ks.run(Action(params=ActionParams(query, changes)))│
│   # 3 lines. That's the integration.                        │
└──────────────────────┬──────────────────────────────────────┘
                       │ POST /v1/run
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Preview   │→│ Policy    │→│ Approval  │→│ Canary    │   │
│  │ Engine    │  │ Engine    │  │ Gate      │  │ Executor  │   │
│  │           │  │           │  │           │  │           │   │
│  │ blast     │  │ YAML rules│  │ employee  │  │ 5 records │   │
│  │ radius    │  │ decision  │  │ validation│  │ first     │   │
│  │ diffs     │  │ reasons   │  │ Slack/UI  │  │ checks    │   │
│  │ flags     │  │ version   │  │ binding   │  │ breaker   │   │
│  │ hash      │  │           │  │           │  │           │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐  │
│  │ Circuit   │→│ Proof     │  │ Connectors               │  │
│  │ Breaker   │  │ Engine    │  │ ┌────────────────────┐   │  │
│  │           │  │           │  │ │ ServiceNow (sim)   │   │  │
│  │ auto-halt │  │ HMAC sign │  │ ├────────────────────┤   │  │
│  │ on anomaly│  │ receipt   │  │ │ Jira (stub)        │   │  │
│  │           │  │ verify    │  │ ├────────────────────┤   │  │
│  └──────────┘  └──────────┘  │ │ Any tool (interface)│   │  │
│                               │ └────────────────────┘   │  │
│  ┌──────────────────────┐    └──────────────────────────┘  │
│  │ SQLite (12 tables)    │                                  │
│  │ actions, previews,    │                                  │
│  │ decisions, approvals, │                                  │
│  │ executions, checks,   │                                  │
│  │ breaker, proofs,      │                                  │
│  │ events, approvers...  │                                  │
│  └──────────────────────┘                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ UI       │ │ Slack    │ │ SDK      │
   │ Next.js  │ │ Buttons  │ │ Response │
   │          │ │          │ │          │
   │ 3 pages: │ │ Approve  │ │ result.  │
   │ list     │ │ Deny     │ │ status   │
   │ detail   │ │ View     │ │ decision │
   │ proof    │ │          │ │ proof_url│
   └──────────┘ └──────────┘ └──────────┘
```

---

## Action Lifecycle

```
Agent proposes action
        │
        ▼
   ┌─────────┐
   │ PREVIEW  │ Blast radius, diffs, flags, preview_hash
   └────┬────┘
        ▼
   ┌─────────┐
   │ POLICY   │ Evaluate YAML rules → AUTO / CANARY / APPROVAL_REQUIRED / BLOCK
   └────┬────┘
        │
        ├── BLOCK ──────────────────────────────── status: blocked
        │                                           (zero records touched)
        │
        ├── APPROVAL_REQUIRED ──┐
        │                       ▼
        │               ┌──────────────┐
        │               │ WAIT         │ Slack message + UI panel
        │               │ for human    │ Employee ID validated
        │               └──────┬───────┘
        │                      │
        │            ┌─────────┼─────────┐
        │            ▼                   ▼
        │         APPROVED            DENIED ──── status: blocked
        │            │
        ├────────────┘
        │
        ▼
   ┌─────────┐
   │ CANARY   │ Execute on 5 deterministic records
   └────┬────┘
        ▼
   ┌─────────┐
   │ CHECKS   │ 5 safety invariants verified
   └────┬────┘
        │
        ├── ANY FAIL ──┐
        │              ▼
        │     ┌──────────────┐
        │     │ BREAKER TRIP │ status: contained
        │     │ Halt expand  │ (only 5 records touched)
        │     └──────────────┘
        │
        ▼
   ┌─────────┐
   │ EXPAND   │ Execute on remaining records
   └────┬────┘
        ▼
   ┌─────────┐
   │ PROOF    │ HMAC-SHA256 signed receipt
   └────┬────┘
        ▼
   status: completed
```

---

## Database Schema (12 tables)

| Table | Purpose | Key Fields |
|-------|---------|------------|
| **orgs** | Multi-tenancy | org_id, name |
| **api_keys** | Authentication (SHA-256 hashed) | key_hash, org_id |
| **actions** | Core Action Object | action_id, org_id, status, tool, action_type, actor, params, mode |
| **previews** | Blast radius + diffs + flags | preview_hash, blast_radius, diffs, flags |
| **decisions** | Policy evaluation results | policy_id, policy_version, decision, reasons |
| **approvals** | Who approved, bound to hash + version | approver (name, designation, dept), preview_hash, policy_version |
| **executions** | Canary + expand phase results | phase, subset_ids, results, error_rate |
| **checks** | Post-execution safety invariants | check_name, passed, details |
| **breaker** | Circuit breaker state | tripped, reason |
| **proofs** | Signed audit receipts | receipt_json, HMAC signature |
| **events** | Full lifecycle timeline | type, payload, timestamp |
| **approvers** | Authorized employees per org | employee_id, name, designation, department, authorized_tools |

---

## API Endpoints

### Core
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/run` | Full action lifecycle (preview → policy → canary → proof) |
| GET | `/v1/actions` | List actions (filtered by org, status, tool) |
| GET | `/v1/actions/{id}` | Full detail (joined across all tables) |
| GET | `/v1/actions/{id}/proof` | Signed proof receipt + verification |
| GET | `/v1/policies/current` | Current policy YAML + version + hash |

### Approval
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/actions/{id}/approve` | Approve (validates employee_id) |
| POST | `/v1/actions/{id}/deny` | Deny (validates employee_id) |
| POST | `/v1/actions/{id}/execute` | Execute after approval |
| GET | `/v1/approvers` | List authorized approvers |

### Execution
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/actions/{id}/execute-from-dry-run` | Run a dry-run action for real (one-time) |

### Slack
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/slack/interact` | Handle Slack button clicks |

---

## Policy Engine

**File:** `backend/app/policies/default_policy.yaml`

Rules evaluated in order. Strictest decision wins: BLOCK > APPROVAL_REQUIRED > CANARY > AUTO.

| Rule | Condition | Decision |
|------|-----------|----------|
| blast_radius_limit | blast_radius > 50 | BLOCK |
| no_p1_incidents | P1 flag = true | BLOCK |
| vip_approval_required | VIP flag = true | APPROVAL_REQUIRED |
| canary_for_medium_blast | blast_radius > 10 | CANARY |
| auto_small_changes | blast_radius <= 10 | AUTO |

All matched rules are collected as reasons. Policy version is tracked. Decisions are deterministic — same preview data + same policy always produces the same decision.

---

## Safety Invariants (Post-Checks)

After canary execution, 5 checks verify the results:

| Check | What it verifies |
|-------|-----------------|
| no_out_of_scope | Only targeted record IDs were modified |
| only_intended_fields | Only specified fields were changed (catches business rule side-effects) |
| no_vip_state_change | No VIP records had their state changed |
| no_p1_state_change | No P1 records had their state changed |
| error_rate_ok | Error rate is within threshold (0% for canary) |

If **any** check fails → circuit breaker trips → expansion halted → status: contained.

---

## Connector Interface

Any tool implements 4 methods:

```python
class BaseConnector(ABC):
    def query(self, filters: dict) -> list[dict]           # Find matching records
    def compute_diffs(self, records, changes) -> list[dict] # Preview changes (read-only)
    def execute_update(self, sys_ids, changes) -> list[dict] # Apply changes
    def get_record(self, sys_id) -> dict | None             # Fetch single record
```

Currently implemented:
- **ServiceNow Simulator** — 25 seeded incidents, business rule simulation
- **Jira Stub** — preview-only, demonstrates interface extensibility

To add a new tool: implement these 4 methods, register in the connector map. Keystone's engines (preview, canary, breaker, proof) work unchanged.

---

## SDK Integration

```python
from keystone import Keystone, Action, ActionParams

# Initialize (once)
ks = Keystone(base_url="https://keystone.yourcompany.com", api_key="ks_prod_xxx")

# Govern any action (3 lines)
result = ks.run(Action(
    params=ActionParams(
        connector="servicenow_sim",
        query={"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}},
        changes={"state": "in_progress"},
    )
))

# Handle result
if result.status == "completed":
    print(f"Done. {result.blast_radius} records. Proof: {result.proof_url}")
elif result.status == "contained":
    print(f"Halted. Breaker: {result.breaker['reason']}")
elif result.status == "blocked":
    print(f"Blocked: {result.decision['reasons']}")
elif result.status == "awaiting_approval":
    print(f"Needs approval: {result.ui_urls['detail']}")
```

---

## Approval System

### How it works
1. Organization admin adds employees to the `approvers` table with their authorized tools
2. When an action requires approval, Keystone notifies via Slack and/or shows an approval panel in the UI
3. Approver enters their Employee ID — Keystone validates against the database
4. Approval is recorded with full identity (name, designation, department) and bound to the preview_hash + policy_version
5. If the underlying data changes after approval, the hash changes and the approval is invalid

### Seeded approvers (demo)

| Employee ID | Name | Designation | Department | Authorized Tools |
|-------------|------|-------------|------------|-----------------|
| EMP001 | Sarah Chen | Senior Operations Lead | Platform Engineering | All |
| EMP002 | James Rodriguez | VP of Engineering | Engineering | All |
| EMP003 | Priya Patel | IT Service Manager | IT Operations | ServiceNow |
| EMP004 | Michael Kim | Security Analyst | Security | ServiceNow, Jira |
| EMP005 | Lisa Wang | Change Manager | Change Management | All |

---

## Demo Scenarios

The `demo.py` script runs 5 scenarios that demonstrate every capability:

### Scenario 1: COMPLETED — Safe bulk reassignment
- Agent reassigns 20 P3/P4 incidents to Triage Team
- Policy: CANARY (blast radius > 10)
- Canary: 5 records updated, all checks pass
- Expand: remaining 15 records updated
- Result: **completed**, proof signed

### Scenario 2: CONTAINED — Business rule side-effect caught
- Agent resolves the same incidents (state → "resolved")
- Policy: CANARY (allows it — no P1/VIP)
- Canary: 5 records updated, but ServiceNow business rule auto-populates `resolved_at` and `work_notes`
- Check `only_intended_fields`: **FAILED** (3 fields changed, only 1 intended)
- Breaker: **TRIPPED** — expansion halted
- Result: **contained**, only 5 of 20 records touched, 15 protected

### Scenario 3: BLOCKED — P1/VIP detected by policy
- Agent tries to resolve ALL open incidents including P1 + VIP
- Policy: BLOCK (P1 present) + APPROVAL_REQUIRED (VIP present) — strictest wins
- Result: **blocked**, zero records touched, proof documents why

### Scenario 4: APPROVAL REQUIRED — Slack + UI approval
- Agent reassigns P2 incidents (includes VIP callers)
- Policy: APPROVAL_REQUIRED (VIP flag)
- Slack message posted with blast radius, flags, diffs, approve/deny buttons
- UI shows approval panel with employee ID validation
- Authorized employee approves → canary → expand → completed
- Result: **completed** after human oversight

### Scenario 5: DRY RUN — Observe only
- Same action as Scenario 1 but in observe_only mode
- Preview and policy evaluated, no execution
- UI shows "What would happen" summary with option to "Run for Real"
- Result: **observed**, zero records touched

---

## UI Pages

### 1. Actions List (`/`)
- Summary stats: total, completed, contained, blocked
- Each action shows: tool.action_type, status badge, actor, time ago
- Click to view detail

### 2. Action Detail (`/actions/{id}`)
- **Alert banners**: Contained (amber), Blocked (red), Dry Run (blue), Approval Required (purple)
- **Lifecycle stepper**: Preview → Policy → Approval → Canary → Expand → Receipt (colored dots)
- **Key numbers**: Records Matched, Records Changed, Safety Checks passed/failed
- **Policy decision**: Decision badge + matched rules + reasons
- **Approval panel** (if awaiting): Employee ID input, authorized approvers list, Approve/Deny buttons
- **Changes**: Field-level summary + expandable raw diffs + unexpected field detection
- **Execution phases**: Phase 1 Canary Test (per-record results) + Phase 2 Full Execution (or Halted)
- **Safety checks**: Pass/fail list
- **Blast radius breakdown**: Bar charts by priority, assignment group, etc.
- **Event timeline**: Vertical line with colored circles, human-readable labels, data summaries
- **Dry run**: "Would affect / Would change / Policy would decide" + "Run for Real" button (one-time, linked)

### 3. Proof Page (`/actions/{id}/proof`)
- Cryptographic verification banner (green = authentic, red = tampered)
- Signature display (HMAC-SHA256)
- WHO / WHAT / WHEN summary cards
- Formatted view + Raw JSON tabs
- Copy JSON + Export Receipt buttons

---

## Repo Structure

```
keystone/
├── backend/
│   ├── app/
│   │   ├── main.py                 FastAPI entry point
│   │   ├── db.py                   SQLite schema + helpers (12 tables)
│   │   ├── auth.py                 API key → org_id authentication
│   │   ├── models.py               Pydantic request/response models
│   │   ├── slack.py                Slack message posting
│   │   ├── routes/
│   │   │   ├── actions.py          POST /v1/run + GET endpoints + dry-run execution
│   │   │   ├── policies.py         GET /v1/policies/current
│   │   │   ├── approve.py          Approve/deny/execute with employee validation
│   │   │   └── slack.py            Slack button interaction handler
│   │   ├── engine/
│   │   │   ├── preview.py          Blast radius + diffs + flags + hash
│   │   │   ├── policy.py           YAML rule evaluation
│   │   │   ├── canary.py           Deterministic subset + post-checks
│   │   │   ├── breaker.py          Auto-halt on check failures
│   │   │   └── proof.py            HMAC-SHA256 signed receipts
│   │   ├── connectors/
│   │   │   ├── base.py             Tool-agnostic interface (4 methods)
│   │   │   └── servicenow_sim.py   25 seeded incidents + business rules
│   │   └── policies/
│   │       └── default_policy.yaml 5 rules, versioned
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env
├── sdk/
│   ├── keystone/
│   │   ├── __init__.py
│   │   └── client.py               Keystone + Action + KeystoneResult
│   ├── setup.py
│   └── demo.py                     5-scenario full product demo
├── ui/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── globals.css
│   │   │   ├── page.tsx            Actions list
│   │   │   └── actions/[id]/
│   │   │       ├── page.tsx        Action detail
│   │   │       └── proof/page.tsx  Proof page
│   │   └── lib/
│   │       ├── api.ts              Backend API helpers
│   │       └── components.tsx      Shared UI components
│   ├── Dockerfile
│   └── .env.local
└── docker-compose.yml
```

---

## Quickstart

### Local Development

```bash
# 1. Backend
cd backend
python -m venv venv && venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --port 8000

# 2. UI (new terminal)
cd ui
npm install
cp .env.example .env.local
npm run dev

# 3. Demo (new terminal)
cd sdk
pip install -e .
python demo.py
```

### Docker

```bash
docker compose up --build
# Backend: http://localhost:8000
# UI: http://localhost:3000
# Then: cd sdk && pip install -e . && python demo.py
```

---

## Demo Video Script (3 minutes)

### Opening (15 sec)
"Keystone is transaction governance for autonomous agents. When an agent wants to change records in your enterprise systems, Keystone previews the blast radius, enforces policy, canary-tests the change, and auto-stops if something unexpected happens."

### Scene 1: The SDK (20 sec)
Show terminal. Run `python demo.py`. Highlight: "3 lines of code to integrate. The agent proposes an action, Keystone governs it."

### Scene 2: Completed — Happy Path (30 sec)
Open UI. Click the completed action. Walk through: "20 records matched. Policy said canary. 5 records tested first. All safety checks passed. Expanded to all 20. Signed proof."

### Scene 3: Contained — The Hero Moment (45 sec)
Click the contained action. Highlight the amber banner: "Same agent, same records, but this time the change triggers a ServiceNow business rule. Keystone catches the unexpected field changes during canary and HALTS expansion. Only 5 of 20 records touched. This is what makes Keystone different — it doesn't just say no, it says yes and then catches reality diverging."

### Scene 4: Blocked — Policy Protection (20 sec)
Click the blocked action: "When the agent tries to touch P1 incidents, policy blocks it before any execution. Zero records modified."

### Scene 5: Approval — Human Oversight (30 sec)
Show Slack message arriving. Click Approve. Show the action proceeding in the UI. "VIP records require human approval. The approval is cryptographically bound to the exact preview — if the data changes, the approval is invalidated."

### Scene 6: Proof — Audit Grade (15 sec)
Open the proof page: "Every action produces a signed receipt. HMAC-SHA256. Tamper-evident. Who proposed, what happened, why it stopped. Export JSON."

### Closing (15 sec)
"Keystone is a release manager for agent actions. Preview, canary, contain, prove. That's transaction governance."

---

## What Makes This Different

| Category | Guardrails / Observability | Keystone |
|----------|---------------------------|----------|
| **Governs** | LLM calls, prompts, traces | External system state changes |
| **Preview** | Token limits, content filters | Blast radius, record diffs, risk flags |
| **Decision** | Allow/deny | AUTO / CANARY / APPROVAL_REQUIRED / BLOCK with reasons |
| **Execution** | Pass-through | Canary 5 → check → expand (or halt) |
| **Side-effects** | Not tracked | Detected by post-checks, halts expansion |
| **Approval** | Not applicable | Bound to preview_hash + policy_version + employee identity |
| **Audit** | Logs | HMAC-signed receipt with full lifecycle |
| **Integration** | Agent framework plugins | 3-line SDK, tool-agnostic connector interface |

---

## Key Technical Properties

- **Deterministic preview_hash**: SHA-256 of (query + sorted target IDs + changes). Same input = same hash. Approvals bind to this.
- **Deterministic canary selection**: hash(action_id + sys_id) sort. Same action = same 5 records. Reproducible for audit.
- **Versioned policy**: Policy file has version + hash. Decisions record which version was used. Old approvals don't apply to new policy.
- **Tool-agnostic**: Connector interface (4 methods). Add any tool without changing engines.
- **Multi-tenant**: Every query scoped by org_id via API key authentication.
- **Tamper-evident**: HMAC-SHA256 signed proof receipts. Any field change = verification fails.
