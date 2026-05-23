# Demo Video Runbook

---

## 3-Minute Demo — Shot-by-Shot Script

### Pre-recording setup (5 min, not recorded)

**Terminal 1 — backend:**
```bash
cd keystone/backend
rm -f keystone.db
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — UI:**
```bash
cd keystone/ui
npm run dev
```

**Terminal 3 — seed the dashboard (run this BEFORE hitting record):**
```bash
cd keystone/sdk
python demo_3min.py
```
The script will pause and print the exact action URLs. Keep this terminal visible during recording.

**Log in as Sarah Chen** at `http://localhost:3000` (password: `sarah-admin`, OTP in Terminal 1).

**Open these tabs in order before recording:**

| Tab | URL | Purpose |
|---|---|---|
| 1 | `http://localhost:3000/` | Dashboard overview |
| 2 | Action detail — completed | Show full lifecycle |
| 3 | Action detail — contained | Show breaker |
| 4 | Action detail — blocked | Show policy |
| 5 | `http://localhost:3000/approvals` | Approval queue |
| 6 | Action detail — completed `/proof` | Proof receipt |
| 7 | `http://localhost:3000/audit` | Audit trail |

---

### Shot list (180 seconds)

| Time | Screen | What to do | Narration |
|---|---|---|---|
| **0:00–0:12** | Terminal 3 | Show the SDK call for Scenario 1 (`demo_3min.py` is mid-run) | *"This is an AI agent proposing a change to 20 production records. What happens next?"* |
| **0:12–0:22** | Tab 1 — Dashboard | Switch to browser. Stats visible: 4 actions, mix of statuses | *"Keystone is the governance layer between the agent and your systems. Every action goes through it."* |
| **0:22–0:50** | Tab 2 — Completed action | Click through: blast radius = 20, decision = CANARY, lifecycle steps, proof badge | *"Safe action. Twenty records, no critical flags. Policy: canary first. Five records executed. Safety checks pass. Expansion to all twenty. Signed receipt."* |
| **0:50–1:10** | Tab 4 — Blocked action | Show blast radius = 25, flags: has\_p1 checked, reasons panel, zero records touched | *"Same agent. Broader query. P1 critical incidents in the target set. Policy says Block. Zero records touched. The reason is versioned and logged."* |
| **1:10–1:45** | Tab 5 — Approvals | Show the pending approval card with blast radius and VIP flag. Click Approve. Watch status flip. | *"VIP-impacting action. Policy routes it to a human with full context — blast radius, diff, risk flags. The approval is cryptographically bound to this exact preview. If the data changes, the approval is void."* |
| **1:45–2:05** | Tab 3 — Contained action | Show canary executed, only\_intended\_fields FAIL, breaker TRIPPED, 5 of 20 records touched | *"Policy allowed this one. But during canary, ServiceNow's business rules modified unexpected fields. Keystone's circuit breaker caught it. Five records touched. Fifteen protected."* |
| **2:05–2:25** | Tab 6 — Proof receipt | Show the proof page: WHO / WHAT / WHEN / WHY, Cryptographically Verified badge | *"Every action ends with a tamper-evident receipt. HMAC-SHA256 signed. This is your compliance record for every AI decision — who proposed it, what policy decided, who approved, what changed."* |
| **2:25–2:40** | Tab 7 — Audit trail | Scroll through events. Filter to one action. | *"The audit trail captures every event in the lifecycle — immutable, org-scoped, exportable."* |
| **2:40–2:52** | Terminal 3 | Show the 7-line SDK integration code at the bottom of `demo_3min.py` | *"For the agent, it is one call. Keystone handles the rest."* |
| **2:52–3:00** | Tab 1 — Dashboard | Wide shot of dashboard with all four scenarios visible | *"Keystone. Transaction governance for AI agents."* |

---

### Narration — full script

Read this word-for-word for a clean first take:

> This is an AI agent proposing a change to twenty production records. What happens next?
>
> Keystone is the governance layer between the agent and your systems. Every action goes through it.
>
> Safe action. Twenty records, no critical flags. Policy evaluates: canary first. Five records execute. Safety checks pass. Expansion to all twenty. Proof signed.
>
> Same agent, broader query. P1 critical incidents in the target set. Policy blocks it. Zero records touched. The reason is versioned, logged, and tamper-evident.
>
> This action impacts VIP accounts. Keystone routes it to a human — blast radius, diffs, risk flags, all in context. The approval binds to the exact preview. If data changes before execution, the approval is void.
>
> Policy allowed this one. But during canary, the target system's business rules modified unexpected fields. Keystone's circuit breaker caught the divergence and halted. Five records touched. Fifteen protected.
>
> Every action ends with a tamper-evident receipt. HMAC-SHA256 signed. Who proposed it. What policy decided. Who approved. What actually changed.
>
> For the agent, this is one SDK call. Keystone handles the rest.
>
> Keystone. Transaction governance for AI agents.

---

### Recording tips

- Move the cursor slowly and deliberately — hesitation reads as confidence.
- Add captions in post: `Preview`, `Policy`, `Canary`, `Breaker`, `Proof` at each moment.
- Do NOT narrate while clicking — let the visual land, then speak.
- If a take breaks down, delete `keystone.db`, restart the backend, and re-run `demo_3min.py`.
- Use 1920×1080. Zoom the browser to 110% so text is readable at compressed video size.

---

Keystone is strongest on video when it is framed as infrastructure for trust, not just another dashboard.
Across the codebase, the product story is consistent:

- The SDK sends a normalized action object into `POST /v1/run`.
- Keystone previews the blast radius and generates a deterministic `preview_hash`.
- Policy decides `AUTO`, `CANARY`, `APPROVAL_REQUIRED`, or `BLOCK`.
- High-risk actions wait for a human.
- Medium-risk actions canary first.
- Post-checks and the circuit breaker stop rollout if reality diverges from intent.
- Every action ends with an audit trail and a signed proof receipt.

That means your best videos are not generic UI tours. They should feel like:

1. "This is the missing safety layer for autonomous agents."
2. "Here is exactly how a team would use it."

## Recording Setup

Use a fresh database for every take:

```bash
cd keystone/backend
del keystone.db
python -m uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```bash
cd keystone/ui
npm run dev
```

In a third terminal:

```bash
cd keystone/sdk
pip install -e .
```

Demo logins already seeded in the backend:

- `sarah.chen@keystone.org` / `sarah-admin` - global admin
- `james.r@keystone.org` / `james-admin` - global admin
- `priya.p@keystone.org` / `priya-demo` - standard user
- `michael.k@keystone.org` / `michael-demo` - security approver
- `lisa.w@keystone.org` / `lisa-demo` - change manager

OTP codes print in the backend terminal.

Recommended tabs before recording:

- `http://localhost:3000/`
- `http://localhost:3000/workspaces`
- `http://localhost:3000/policies`
- `http://localhost:3000/agents`
- `http://localhost:3000/approvals`
- `http://localhost:3000/audit`

## Video 1: Launch Video

Goal: a tight 60-90 second launch reel.

Audience: builders, platform teams, security buyers, and social viewers who need to understand the product in one pass.

Best structure:

1. Hook with the problem.
2. Show the governed action lifecycle.
3. Show that Keystone both speeds up safe actions and stops unsafe ones.
4. End on the SDK and proof receipt.

Seed the dashboard first:

```bash
cd keystone/sdk
python launch_demo.py
```

### Shot list

| Time | What to show | Voiceover / on-screen line |
|---|---|---|
| 0:00-0:07 | Website hero or a title card | "AI agents can take action. The missing piece is governance." |
| 0:07-0:18 | Dashboard with passed, contained, blocked, and pending actions visible | "Keystone sits between agent intent and production systems." |
| 0:18-0:30 | Open the passed action detail and linger on blast radius, lifecycle, and canary | "Every action is previewed before it runs." |
| 0:30-0:42 | Open the contained action and show the circuit breaker and unexpected fields | "If reality diverges from the preview, Keystone halts expansion automatically." |
| 0:42-0:52 | Open the blocked action and show policy reasons | "Dangerous actions never execute." |
| 0:52-1:02 | Open the proof page and show `Cryptographically Verified` | "Every decision ends with a signed audit receipt." |
| 1:02-1:12 | Show the SDK snippet in `README.md` or `sdk/demo.py` | "For the agent, this is one SDK call." |
| 1:12-1:20 | Return to the dashboard or brand card | "Keystone is transaction governance for AI agents." |

### Launch video narration

Use this almost verbatim if you want a clean first take:

> AI agents are finally capable of taking real actions in enterprise systems.  
> The problem is not capability. The problem is trust.  
> Keystone sits between agent intent and execution.  
> Before anything touches production, Keystone previews the blast radius, evaluates policy, canaries the action, pauses for approval when needed, trips a circuit breaker if reality diverges, and emits a signed audit receipt.  
> Safe actions move fast. Risky actions get contained. Dangerous actions are blocked.  
> This is transaction governance for AI agents.

### Editing notes

- Keep cursor movement deliberate and slow.
- Use punchy captions: `Preview`, `Policy`, `Canary`, `Approval`, `Breaker`, `Proof`.
- Cut aggressively. The launch video should feel inevitable, not explanatory.
- Do not spend more than a few seconds on workspace administration.

## Video 2: YC / a16z Workflow Demo

Goal: a 3-5 minute founder-led workflow demo.

Audience: investors who want to understand the product, the user journey, and why the workflow matters.

This should answer:

1. Who uses Keystone?
2. What does setup look like?
3. What happens when an agent actually runs?
4. Why is this hard to replicate with logging alone?

Start the guided workflow:

```bash
cd keystone/sdk
python investor_workflow_demo.py
```

### Story arc

1. Show the control plane.
2. Show the policy surface.
3. Show the governed action.
4. Show human approval.
5. Show record-level verification and proof.

### Shot list

| Time | What to show | Talk track |
|---|---|---|
| 0:00-0:20 | Workspaces page | "Teams use Keystone through workspaces. Each workspace has its own agents, members, systems, and governance posture." |
| 0:20-0:40 | Workspace detail for `Platform Engineering` | "This is the operating boundary around a team and its production systems." |
| 0:40-1:00 | Policies page | "Policies are versioned YAML. The system resolves the active policy by agent override, then workspace, then default." |
| 1:00-1:20 | Agents page | "Agents are first-class entities with owners, permissions, and rate limits." |
| 1:20-1:45 | Observe-only action detail from `investor_workflow_demo.py` | "Here an agent proposes a change. Keystone computes blast radius, diffs, risk flags, and a preview hash before any execution." |
| 1:45-2:15 | Pending approval action detail plus `/approvals` | "Because this action touches P2 and VIP records, Keystone pauses and routes it for approval with full context." |
| 2:15-2:45 | Approve in UI or Slack | "Approval is bound to the exact preview hash and policy version, so you cannot approve one thing and execute another." |
| 2:45-3:15 | Returned action detail showing canary, rollout, checks, or containment | "Execution resumes under controlled conditions: canary first, then post-checks, then expansion if clean." |
| 3:15-3:45 | Record timeline and audit notes written to ServiceNow | "You can inspect exactly what changed at the record level, including unexpected side effects." |
| 3:45-4:15 | Proof page and audit trail | "Every lifecycle event is written into a signed proof receipt and audit ledger." |
| 4:15-4:30 | SDK snippet | "From the agent's point of view, integration is just one call." |

### Investor narration

Use this structure:

> The core problem is that enterprises want agents to act, but they do not want to hand them unchecked write access.  
> Keystone gives them a control plane between the model and the system of record.  
> Each team gets its own workspace, policies, members, and connected systems.  
> When an agent proposes an action, Keystone previews the blast radius, computes diffs, generates a deterministic preview hash, and evaluates policy.  
> Low-risk actions can run automatically, medium-risk actions canary first, and sensitive actions route to a human with full context.  
> If execution behaves differently than the preview, the circuit breaker contains the rollout.  
> At the end, Keystone emits a tamper-evident receipt covering who proposed the action, what policy decided, who approved it, and what actually changed.

### What to emphasize to investors

- This is a system of control, not just observability.
- The product already spans SDK, policy engine, approval UI, audit, and proof.
- The workflow is tool-agnostic. ServiceNow is the demo surface, not the product boundary.
- The strongest moat signal is the full lifecycle: preview, policy, approval binding, canary, breaker, proof.

## Best Pages To Show

If you have limited time, prioritize these pages in this order:

1. `/actions/<id>` for the full lifecycle
2. `/actions/<id>/proof` for the signed receipt
3. `/approvals` for the human gate
4. `/policies` for the governance model
5. `/workspaces/<id>` for enterprise setup
6. `/audit` for the cross-system ledger

## Suggested Titles

Launch video title:

- `Keystone: Transaction Governance for AI Agents`

Investor workflow title:

- `How Keystone Governs an AI Agent Action End-to-End`

## Final Recording Tips

- Log in as `Sarah Chen` for the broadest surface area.
- Record the terminal and browser separately so you can cut between them.
- For the investor demo, use the UI approval flow unless your Slack setup is already polished.
- Keep one browser window for the main app and one for the proof page so you can cut quickly.
- If a take gets messy, reset `backend/keystone.db` and start over instead of trying to clean the state manually.
