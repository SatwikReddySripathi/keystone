# Action Marshall Repo Audit

> Audit date: 2026-05-22
> Auditor: Claude Code (acting as senior open-source infra engineer)
> Scope: full read of `action_marshall/` at HEAD on 2026-05-22
> Output of: Phase 1 in `CLAUDE.md`

---

## Executive Summary

Action Marshall is a working MVP of action-level release control for AI agents, built around a real action lifecycle (preview → policy → approval → canary → checks → proof). The backend is competent: FastAPI + SQLite, ~17-table schema, HMAC-signed proof receipts, pluggable connector interface, working Slack approval flow, a Next.js approval/audit dashboard, and runnable demo scripts.

It is not yet a public-grade open-source infrastructure project. The biggest blockers are not engineering depth — they are repo hygiene and SDK shape:

1. **Real secrets are committed.** `backend/.env` contains a live Slack webhook URL and live ServiceNow admin credentials (instance name, user, plaintext password — values redacted from this document). These must be rotated and purged from the repo before this can go public.
2. **The SDK shape does not match the positioning.** The product positioning is "wrap actions, not rebuild agents." Today the SDK exposes a `Action Marshall` client and dataclass-based `Action`, with no `ks.wrap(...)`, no `wrap_function`, no `wrap_tool`, no framework adapters (LangChain, LangGraph, CrewAI, AutoGen, MCP, LlamaIndex, OpenAI). The drop-in story doesn't exist yet.
3. **Packaging is on `setup.py` only** with package name `action-marshall`. The CLAUDE.md target is `action-marshall` (or `action_marshall-agent-control`) with `pyproject.toml`, `py.typed`, and optional extras for each framework.
4. **No CLI, no LICENSE, no CONTRIBUTING.md, no SECURITY.md, no CHANGELOG.md, no `docs/`** (this file creates the folder). Several stale or sensitive files are committed: `venv/`, `action_marshall.db` (250 KB), `pitch_deck.pptx/.html`, `build_pitch_deck.py`, `CLAUDE_v1.md`.
5. **Tests are runnable scripts, not pytest.** They work and CI runs them, but they don't feel like a project a contributor would extend.

Once these are addressed, Action Marshall has a credible Level 1 (Public-Demo Ready) story and most of a Level 2 (Self-Host Ready) story. It is **not** Level 3 (Package Ready) and is far from Level 4 (Hosted SaaS Ready).

Recommended public-readiness score (today): **4 / 10.** With Phase 2–6 work as described in `CLAUDE.md`, it can reach 7–8 / 10 — enough to publish, demo, and onboard early users.

---

## Current Repo Structure

```text
action_marshall/
├── CLAUDE.md                       # current build instructions (this audit's source of truth)
├── CLAUDE_v1.md                    # previous version of instructions — stale, gitignored
├── README.md                       # product README, accurate to current impl
├── DEMO_VIDEO_RUNBOOK.md           # demo script for video recording
├── VIDEO_RECORDING.md              # recording notes
├── docker-compose.yaml             # backend + ui (no DB service — sqlite)
├── pitch_deck.html / .pptx         # 51 KB + 64 KB demo artifacts
├── build_pitch_deck.py             # 36 KB script that builds the deck
├── venv/                           # COMMITTED virtualenv (stale, should be deleted)
├── backend/
│   ├── .env                        # CONTAINS REAL SECRETS (Slack webhook, SNOW creds)
│   ├── .env.example
│   ├── Dockerfile                  # python:3.11-slim + gunicorn/uvicorn
│   ├── requirements.txt
│   ├── action_marshall.db                 # 250 KB committed sqlite database
│   ├── test_*.py                   # 14 script-style tests at root
│   └── app/
│       ├── main.py                 # FastAPI app, CORS, 8 routers, /health
│       ├── db.py                   # ~644 lines: schema + lifecycle helpers
│       ├── models.py               # Pydantic models for ActionInput, etc.
│       ├── auth.py                 # API key (X-API-Key) auth
│       ├── slack.py                # Slack approval messages + buttons
│       ├── rate_limit.py           # in-memory sliding window + lockout
│       ├── connectors/             # base + servicenow_sim + servicenow_real + email_generic
│       ├── engine/                 # policy.py, preview.py, canary.py, breaker.py, proof.py
│       ├── policies/               # YAML policy files (loaded at startup)
│       └── routes/                 # actions, approve, audit, policies, auth, workspaces,
│                                   # agents, connections, slack, stats, access, db
├── sdk/
│   ├── setup.py                    # package = action-marshall, v0.1.0
│   ├── README.md                   # SDK usage
│   ├── action_marshall/                   # importable package
│   │   ├── __init__.py             # exports Action Marshall, Action, ActionParams, Actor, Approver,
│   │   │                           # Approval, MarshallResult
│   │   └── client.py               # Action Marshall client wrapping requests
│   ├── demo.py                     # 4-scenario product demo
│   ├── demo_3min.py / demo_recording.py / demo_real.py / launch_demo.py
│   ├── investor_workflow_demo.py
│   └── onboarding_example.py
├── ui/                             # Next.js 14 + TS + Tailwind
│   ├── Dockerfile
│   ├── package.json
│   └── src/app/
│       ├── page.tsx (dashboard)
│       ├── actions/[id]/page.tsx + proof
│       ├── approvals/, agents/, audit/, login/, policies/, systems/,
│       │   workspaces/ (+ [id] detail pages)
│       └── lib/ + components/
├── website/                        # separate Next.js marketing site
└── .github/workflows/
    ├── backend-ci.yml              # lint + unit tests + uvicorn smoke
    └── ui-ci.yml                   # lint + tsc --noEmit + build
```

Notable absences:

- No `docs/` (this audit creates it).
- No `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `RELEASE.md`.
- No top-level `.env.example`.
- No `pyproject.toml` (anywhere).
- No `action-marshall` CLI entry point.
- No framework adapters under `sdk/action_marshall/adapters/`.
- No Alembic / migrations — `db.py` creates tables in-process on startup.

---

## What Already Works

The substantive product features that exist and run today:

**Action lifecycle (end-to-end).**

- `POST /v1/run` accepts an action, generates a preview, evaluates policy, optionally requires approval, runs canary on a deterministic 5-record subset, runs post-execution checks, evaluates the circuit breaker, and emits a signed proof receipt. Each step is persisted to its own table.
- Decision priority is `BLOCK > APPROVAL_REQUIRED > CANARY > AUTO`.
- Canary subset selection is hash-deterministic — same `action_id + targets` always picks the same 5 records.
- Breaker trips on failed post-execution checks and is recorded.
- Proofs are HMAC-SHA256 signed against `PROOF_SECRET` and bind to the `preview_hash + policy_version` so an approval cannot be reused against a swapped payload.

**Connectors.**

- `base.py` defines a clean abstract interface: `query`, `compute_diffs`, `execute_update`, `get_record`, optional `extra_flags`.
- `servicenow_sim.py` simulates 25 seeded incidents (P3/P4 safe, P1/P2/VIP dangerous), including realistic side-effects like `resolved_at` and `work_notes` being auto-populated on state transitions.
- `servicenow_real.py` talks to a real ServiceNow Table REST API with field normalization (P1–P5 priority, state vocabulary).
- `email_generic.py` governs outbound email with flags for `has_large_send`, `has_external_recipients`, `has_sensitive_keywords`, `has_all_staff`.

**Policy engine.**

- YAML-based policies in `backend/app/policies/`.
- `evaluate_policy()` matches rules against preview flags and returns a decision with reasons and thresholds.
- Policies are versioned (content hash) and persisted in the `policies` table.

**Approvals.**

- Slack rich-message approvals with buttons (`POST /v1/slack/interact`).
- Web approval UI under `/approvals` and `/actions/[id]`.
- Approver identity, role check, and permission scope are enforced server-side.

**Multi-tenancy / RBAC primitives.**

- `orgs`, `api_keys` (SHA-256 hashed, never raw), `workspaces`, `workspace_members` (admin / approver / viewer), `agents`, `connections`.

**Employee auth.**

- Email + password (SHA-256 hashed), 6-digit OTP with 10-minute expiry, 5-attempt cap, account lockout after 5 failed logins, per-IP and per-email rate limits, SMTP optional with console-log fallback for OTPs.

**Frontend.**

- Pages: dashboard, actions list, action detail, signed-proof viewer, approvals queue, agents (list + detail), audit (list + detail + filters), login, policies, systems, workspaces (list + detail + members).
- Auto-refresh hook to poll action status.

**Backend health.**

- `/health` endpoint is wired up and exercised by CI smoke.

**CI.**

- `backend-ci.yml`: pip install, ruff lint (syntax only), run nine `test_*.py` scripts, start uvicorn, curl `/health`.
- `ui-ci.yml`: npm ci, lint, `tsc --noEmit`, `next build`.

**Docker.**

- Backend Dockerfile is clean and uses gunicorn + uvicorn workers.
- UI Dockerfile builds the Next.js app.
- `docker-compose.yaml` wires both with a persistent volume for the sqlite DB.

**SDK (current shape).**

- Importable as `from action_marshall import Action Marshall, Action, ActionParams, Actor, Approver, Approval, MarshallResult`.
- `Action Marshall(api_key, base_url).run(Action(...))` hits the backend.
- `MarshallResult` exposes `action_id`, `status`, `preview`, `decision`, `breaker`, `proof_available`, `proof_url`, `ui_urls`, `is_blocked`, etc.

---

## What Is Missing

Relative to the public-launch target in `CLAUDE.md`:

**SDK shape.** No `ks.wrap()`, `wrap_function`, `wrap_tool`, `preview`, or `verify_receipt`. Client class is `Action Marshall`, target is `MarshallClient` (or alias both). No mode flags (`enforce` vs `preview`). No `risk_level`, `require_approval`, `on_denied` knobs documented.

**Packaging.** No `pyproject.toml`. Package name is `action-marshall`; target is `action-marshall`. No `py.typed`. No optional extras for frameworks. No PyPI publish workflow. Local install path (`pip install -e .`) and build (`python -m build`) are not documented.

**Framework adapters.** None exist for LangChain, LangGraph, CrewAI, AutoGen, MCP, LlamaIndex, or raw OpenAI tool calling. This is the single biggest gap between current state and the "wrap actions, not rebuild agents" positioning.

**CLI.** No `action-marshall` command. No `action-marshall init`, `action-marshall preview`, `action-marshall run`, `action-marshall receipts list / verify`.

**Migrations.** No Alembic, no migration files. Schema is created in-process at startup from `db.py`. This is OK for sqlite demos but blocks any serious Postgres path.

**Postgres support.** Code is sqlite-only. `docker-compose.yaml` has no Postgres service. `db.py` is full of sqlite-idiomatic `?` placeholders and `conn.execute` calls — switching is not a one-liner.

**`/ready` endpoint.** Only `/health` exists.

**Examples folder.** No `examples/` directory. The runnable scripts in `sdk/` (`demo.py`, `demo_3min.py`, etc.) overlap and aren't organized as labeled scenarios.

**Docs.** No `docs/` folder. No `quickstart.md`, `self-hosting.md`, `architecture.md`, `sdk.md`, `cli.md`, `policies.md`, `connectors.md`, `approvals.md`, `canary.md`, `circuit-breakers.md`, `audit-receipts.md`, `deployment.md`, `hosted.md`, `security.md`, `faq.md`, `public-launch-checklist.md`, `launch-copy.md`.

**Repo hygiene.** No `LICENSE`, no `CONTRIBUTING.md`, no `SECURITY.md`, no `CODE_OF_CONDUCT.md`, no `CHANGELOG.md`, no `RELEASE.md`, no issue templates, no PR template, no Dependabot config.

**Tests.** No pytest harness, no test discovery, no coverage. The 14 `test_*.py` scripts are smoke-style with raw `assert`. No SDK tests (only one onboarding example). No CLI tests (no CLI exists).

**CI.** No Docker build workflow, no Docker Compose validation workflow, no PyPI publish workflow, no release workflow, no Dependabot.

**Hosted positioning.** README does not currently say "join the hosted waitlist." There is no `docs/hosted.md`. No `Hosted vs Self-Hosted` framing.

**Honesty markers.** No "available now / experimental / planned / roadmap" labeling in docs.

---

## Public Launch Blockers

These must be resolved before the repo is publicly visible:

1. **Rotate and remove committed secrets.** `backend/.env` is committed with a real Slack webhook URL, real ServiceNow instance name, and real admin credentials. Rotate every one of these, delete the file, and confirm `.gitignore` keeps it out. Because git history likely contains them, rewriting history or treating those credentials as permanently compromised is required.
2. **Add a `LICENSE`.** No OSS project is publishable without one. MIT or Apache-2.0 are both reasonable; Apache-2.0 gives explicit patent grant which is usually preferred for infra.
3. **Delete `venv/` from the repo** and verify `.gitignore` covers it.
4. **Delete `action_marshall.db` from the repo** (regenerate on first run) and gitignore `*.db`.
5. **Decide whether the pitch deck files belong in the public repo.** If not, move them to a private location. If yes, at least move them under `assets/` or `docs/pitch/` and remove `build_pitch_deck.py` if it's purely internal.
6. **Delete `CLAUDE_v1.md`** — it's marked internal and is stale.
7. **Cut the README claims down to what actually works.** The current README is broadly honest, but it should be updated to reflect the new SDK shape after Phase 4 and to clearly label what's implemented vs roadmap.

After these, the repo is publishable. The remaining gaps (SDK shape, adapters, CLI, docs) are launch-quality concerns, not "do not publish" concerns — but they materially affect first-impression quality and should be done before any external announcement.

---

## SDK and Package Readiness

**Level today:** Pre-Level 3. The SDK works but doesn't look or feel like a serious package.

| Item | Current | Target |
|------|---------|--------|
| Package manifest | `setup.py` only | `pyproject.toml` with PEP 621 metadata |
| Package name | `action-marshall` | `action-marshall` (or `action_marshall-agent-control`) |
| Import name | `action-marshall` | `action-marshall` ✓ |
| Version | `0.1.0` | `0.1.0` ✓ |
| Client class | `Action Marshall` | `MarshallClient` (keep `Action Marshall` as alias) |
| `wrap`, `wrap_tool`, `wrap_function` | not implemented | implement |
| `preview()` method | not implemented | implement |
| `verify_receipt()` | not implemented | implement |
| Type hints | partial | full; add `py.typed` |
| Optional extras | none | `[langchain]`, `[langgraph]`, `[crewai]`, `[autogen]`, `[mcp]`, `[llamaindex]`, `[openai]`, `[dev]`, `[all]` |
| Framework adapters | none | at least one (LangChain) before launch; document the rest as roadmap |
| Local install | `pip install -e ./sdk` | `pip install -e ".[dev]"` from repo root or `packages/python-sdk` |
| Build | not exercised | `python -m build` produces both sdist + wheel |
| Publish | none | `pypa/gh-action-pypi-publish` via trusted publishing, tag-gated |
| Tests | none | client init, action serialization, `preview`, `run`, wrapper, adapter import behavior, receipt verification |

The single highest-leverage SDK change is adding `ks.wrap(existing_tool)` with sensible defaults. Even before any framework adapter exists, that one method delivers the positioning.

---

## Self-Hosting Readiness

**Level today:** Most of Level 2.

| Item | Status |
|------|--------|
| Docker Compose runs | yes (backend + ui, sqlite-backed) |
| Backend Dockerfile | clean, production-ish (gunicorn + uvicorn workers) |
| UI Dockerfile | works |
| `.env.example` | exists for backend and UI; no top-level one |
| `/health` | exists |
| `/ready` | does not exist |
| Postgres option | no — sqlite only |
| Migrations | no — in-process schema creation |
| Self-hosting doc | missing (`docs/self-hosting.md`) |
| Deployment doc | missing (`docs/deployment.md`) |
| Worker process | not needed yet — all synchronous |
| Persistent volume | yes (`action-marshall-data`) |
| Secrets via env | yes for backend; UI uses `NEXT_PUBLIC_*` which is correct for client-side |

The biggest self-hosting gap is the lack of Postgres support. For a Level 2 launch, that's acceptable as long as it's flagged honestly: "Self-host on sqlite for local and small teams. Postgres support is planned."

---

## Hosted SaaS Readiness

**Level today:** Pre-Level 4. Foundational pieces exist (multi-tenant `orgs`, API-key auth, workspace/RBAC, signed proofs) but no hosted control plane, no billing, no production datastore, no SSO, no audit export.

Decision in `CLAUDE.md` is correct: do not overbuild Level 4 yet. The repo should:

- Add a `docs/hosted.md` explaining the hosted option and a `[Join the hosted waitlist](#)` placeholder link in README.
- Avoid any language implying hosted Action Marshall exists as a service.

That is sufficient for now.

---

## Security Review

**Critical findings.**

1. `backend/.env` is committed with real secrets: a live Slack webhook URL, a real ServiceNow instance, and real admin credentials (values redacted from this document). These must be treated as compromised, rotated, and purged.
2. `action_marshall.db` (250 KB) is committed. It contains seeded data — review for any PII before public release; assume it's compromised even if seed-only.
3. `venv/` is committed. No secrets there directly, but it pollutes the repo and could leak local-machine paths.

**Positive practices observed.**

- API keys stored only as SHA-256 hashes, scoped to `org_id`.
- Passwords stored as hashes.
- OTPs hashed at rest, 10-minute expiry, 5-attempt cap.
- HMAC-SHA256 proof signatures bound to `preview_hash + policy_version`, which defeats approve-then-swap attacks.
- Sliding-window rate limits + account lockout (in-memory, single-worker only).
- Unified error messages on auth (`invalid email or password`) — prevents enumeration.
- Parameterized SQL throughout (no string-formatted queries observed).
- CORS middleware respects `ALLOWED_ORIGINS`.

**Gaps.**

- No `SECURITY.md` — no disclosure path.
- Rate limit is in-memory, so multi-worker `gunicorn` (which the Dockerfile uses, `--workers 2`) gives inconsistent enforcement. Should be `--workers 1` until backed by Redis, or move to Redis.
- `PROOF_SECRET` defaults to `action_marshall-dev-secret-change-in-production` in `.env.example`. Fail-loud behavior if it's left at default in non-dev would be safer than fail-silent.
- No threat model in docs.
- No secret-scanning config (no `.gitleaks` / `trufflehog` workflow).

---

## Documentation Review

The current README is broadly honest and useful, but the repo as a whole lacks the documentation layer expected of a serious infra project.

**What exists.**

- `README.md` (root) — problem, 6-stage workflow, quickstart, SDK usage, modes, connectors, result fields. Accurate to current implementation.
- `sdk/README.md` — install, three-line example, decisions, modes, connectors.
- `DEMO_VIDEO_RUNBOOK.md`, `VIDEO_RECORDING.md` — internal demo notes.
- `CLAUDE.md` (this audit's source).

**What does not exist.**

- `docs/` folder (this file creates it).
- `docs/quickstart.md`, `docs/self-hosting.md`, `docs/architecture.md`, `docs/sdk.md`, `docs/cli.md`, `docs/policies.md`, `docs/connectors.md`, `docs/approvals.md`, `docs/canary.md`, `docs/circuit-breakers.md`, `docs/audit-receipts.md`, `docs/security.md`, `docs/deployment.md`, `docs/hosted.md`, `docs/faq.md`.
- `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `RELEASE.md`.

The README also needs an explicit "Works with your existing agent stack" section per the Phase 3 spec — that section is the heart of the positioning and is currently missing.

---

## CI/CD Review

**What works.**

- `backend-ci.yml` runs on push/PR to `backend/` or `sdk/`, installs deps, lints with `ruff` (syntax-error level only — E9/F63/F7/F82), runs nine of the script tests, and smokes uvicorn + `/health`.
- `ui-ci.yml` runs on push/PR to `ui/`, lints, type-checks with `tsc --noEmit`, builds.

**What does not exist.**

- No PyPI publish workflow.
- No Docker build / push workflow.
- No Docker Compose validation workflow.
- No release workflow.
- No Dependabot config.
- No secret scanning workflow.
- Ruff is configured for syntax errors only, not style. Reasonable for a moving target; should probably tighten before launch.

---

## Testing Review

14 test scripts under `backend/` root, each is a Python script (`python test_foo.py`) using raw `assert`. Coverage is decent for backend lifecycle:

- `test_db.py`, `test_simulator.py`, `test_preview.py`, `test_policy.py`, `test_canary.py`, `test_proof.py`, `test_side_effect.py`, `test_api.py`, `test_approval_flow.py`, `test_approve_direct.py`, `test_auth.py`, `test_slack_buttons.py`, `test_routes.py`, `test_debug.py`.

**Gaps.**

- Not pytest — no test discovery, no fixtures, no coverage.
- No SDK tests at all.
- No CLI tests (no CLI exists).
- No UI tests beyond `next build` succeeding.
- Tests live at `backend/` root rather than `backend/tests/` — `.gitignore` even has a rule excluding them, which suggests they're treated as dev-only.

Migrating to `pytest` with a real `tests/` folder is high-value, but per `CLAUDE.md` Phase 9 the bar is "meaningful smoke tests and core behavior," which is mostly already met.

---

## Framework Compatibility Review

**Status: zero adapters implemented.**

No code exists for:

- LangChain
- LangGraph
- CrewAI
- AutoGen
- MCP (Model Context Protocol)
- LlamaIndex
- OpenAI tool / function calling

The SDK's integration story today is "construct an `Action` and call `ks.run()` inside your agent's tool handler." That works with plain Python and any framework that exposes a callable, but it's not the drop-in story the positioning promises.

**Minimum viable adapter set for launch:** plain-Python `ks.wrap()` + a working LangChain adapter. Everything else can ship as documented roadmap with a clearly labeled status.

---

## Recommended Implementation Order

This is the recommended ordering of `CLAUDE.md`'s phases for this specific repo state. It is **not** a request to implement them now — Phase 1 ends with this audit.

1. **Phase 1 (this document).** Complete.
2. **P0 hygiene burst** (small, fast — see P0 list below). Do this immediately after the audit. This is the prerequisite to the repo being safe to make public, and it's blockingly small.
3. **Phase 2 — repo structure.** Add `docs/`, `examples/`, `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`, `RELEASE.md`, top-level `.env.example`. Decide whether to move `sdk/` to `packages/python-sdk/` (likely yes, but only if every import path and the GitHub Action paths are updated atomically).
4. **Phase 4 — SDK / package.** This is the highest-leverage product change. Add `pyproject.toml`, rename to `action-marshall`, add `ks.wrap()` + `wrap_function()` + `preview()` + `verify_receipt()`, add `py.typed`, add optional extras structure (the extras can declare deps without an adapter file yet). Add SDK tests.
5. **Phase 3 — README rewrite.** Once the SDK shape is right, rewrite the README to match it. Doing this before Phase 4 means rewriting twice.
6. **Phase 5 — CLI.** `action-marshall init`, `action-marshall preview`, `action-marshall run`, `action-marshall receipts list`, `action-marshall receipts verify`. Typer or Click. Small surface.
7. **Phase 6 — Docker / self-hosting.** Mostly already works; add `/ready`, top-level `.env.example`, `docs/self-hosting.md`, `docs/deployment.md`. Decide on Postgres path (probably defer to roadmap with a clear note).
8. **Phase 7 — GitHub Actions.** Add `publish-python.yml` (tag-gated, trusted publishing), `docker.yml`, `dependabot.yml`.
9. **Phase 8 — versioning / release process.** `CHANGELOG.md`, `RELEASE.md`, conventional commits + semver guidance.
10. **Phase 9 — testing.** Move tests to `pytest`. Add SDK + CLI tests.
11. **Phase 10 — security.** `SECURITY.md`, threat model, fail-loud `PROOF_SECRET` default, secret-scanning workflow.
12. **Phase 11 — hosted positioning.** `docs/hosted.md`, README waitlist section.
13. **Phase 12 — examples.** Create `examples/` and label each as "available now" / "planned."
14. **Phase 13 — docs polish.** Fill in every `docs/*.md`.
15. **Phase 14 — public launch readiness.** Checklist + launch copy.
16. **Phase 15–16 — final.**

Adapter work (LangChain, LangGraph, etc.) is interleaved into Phase 4 and Phase 12 — ship at least LangChain and document the rest.

---

## P0 Tasks

Must fix before the repo goes public.

- **P0-1.** Rotate the committed Slack webhook URL. Treat as compromised.
- **P0-2.** Rotate the committed ServiceNow admin password and rebuild the dev instance if needed. Treat as compromised.
- **P0-3.** Delete `backend/.env` from the working tree, confirm `.gitignore` covers `**/.env`, and remove `.env` from git history (or commit a fresh history, depending on how much history needs to survive).
- **P0-4.** Delete `backend/action_marshall.db`. Gitignore `*.db`. Regenerate on first run.
- **P0-5.** Delete `venv/`. Confirm `.gitignore` covers it.
- **P0-6.** Add a `LICENSE` (Apache-2.0 recommended for infra; MIT also fine).
- **P0-7.** Delete `CLAUDE_v1.md`.
- **P0-8.** Move `pitch_deck.pptx`, `pitch_deck.html`, `build_pitch_deck.py` out of the repo root (either delete, move to `assets/pitch/` and gitignore, or move to a separate private location).
- **P0-9.** Add `SECURITY.md` with a disclosure email and supported-version policy.
- **P0-10.** Add a minimal `CONTRIBUTING.md`.
- **P0-11.** Add `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1 is the standard pick).
- **P0-12.** Add `docs/` with at minimum `quickstart.md`, `self-hosting.md`, `architecture.md`, `security.md`. (This audit creates `docs/repo-audit.md`; the rest are Phase 13.)
- **P0-13.** Switch Dockerfile to `--workers 1` (or document that multi-worker rate-limit is best-effort until Redis is wired). Current setting silently degrades the in-memory limiter.
- **P0-14.** Add `pyproject.toml` and rename the package to `action-marshall`. Add `py.typed`. (This is also Phase 4 — listed here because the current name + manifest will confuse anyone who finds the repo before Phase 4 lands.)
- **P0-15.** Add `ks.wrap()` and `ks.wrap_function()` to the SDK with sensible defaults. Without this, the positioning does not match the package. (Also Phase 4.)
- **P0-16.** Add a "Works with your existing agent stack" section to the README. (Also Phase 3.)
- **P0-17.** Add an explicit "available now / experimental / planned / roadmap" labeling convention to every features table in the README and docs.

---

## P1 Tasks

Should fix soon after public launch.

- **P1-1.** Add `action-marshall` CLI (Phase 5).
- **P1-2.** Add `/ready` endpoint.
- **P1-3.** Add at least one framework adapter — LangChain first.
- **P1-4.** Add `examples/` with `minimal-agent/`, `servicenow-demo/`, `langchain-demo/`, `denied-action/`, `safe-action/`, each with its own README + sample action JSON + expected output.
- **P1-5.** Convert backend tests to pytest, move to `backend/tests/`, add SDK tests under `sdk/tests/`.
- **P1-6.** Add `publish-python.yml` workflow (trusted publishing, tag-gated).
- **P1-7.** Add `docker.yml` workflow (build + validate compose).
- **P1-8.** Add `dependabot.yml` for Python, GitHub Actions, npm.
- **P1-9.** Add `CHANGELOG.md` and `RELEASE.md`.
- **P1-10.** Add a fail-loud check for `PROOF_SECRET` when not in dev mode.
- **P1-11.** Add a secret-scanning workflow (gitleaks or similar).
- **P1-12.** Fill out `docs/sdk.md`, `docs/cli.md`, `docs/policies.md`, `docs/connectors.md`, `docs/approvals.md`, `docs/canary.md`, `docs/circuit-breakers.md`, `docs/audit-receipts.md`, `docs/hosted.md`, `docs/faq.md`.
- **P1-13.** Add `docs/public-launch-checklist.md` and `docs/launch-copy.md`.

---

## P2 Tasks

Nice to have.

- **P2-1.** Postgres support behind a `DATABASE_URL` env var; Alembic migrations.
- **P2-2.** Redis-backed rate limiting and approval state.
- **P2-3.** Worker process if any future async work appears (canary expand, retries, audit export).
- **P2-4.** Additional framework adapters: LangGraph, CrewAI, AutoGen, LlamaIndex, MCP, OpenAI tool wrapping.
- **P2-5.** Jira and Salesforce connectors.
- **P2-6.** Audit export (JSON / CSV) endpoint and CLI.
- **P2-7.** SSO / SAML for the dashboard.
- **P2-8.** Teams approvals (in addition to Slack).
- **P2-9.** Policy templates library.
- **P2-10.** Coverage report + badge.

---

## What We Should Not Claim Yet

These are honesty-marker rules. The README and docs must not state any of the following as currently true:

- "Production-ready." Today: public-demo ready, almost self-host ready.
- "Hosted Action Marshall is live." Today: waitlist only, placeholder link.
- "Works with LangChain / LangGraph / CrewAI / AutoGen / MCP / LlamaIndex." Today: works with raw Python only. Frameworks are roadmap until adapters ship and have at least one example.
- "Postgres supported." Today: sqlite only.
- "Battle-tested" / "Trusted by N companies" / any specific customer logo. Today: no customers, no production deployments.
- "Multi-worker safe." Today: in-memory rate limiter + in-process state means single-worker only is the supported config.
- "Audit export." Today: receipts can be fetched per-action; there is no bulk export endpoint.
- "Policy templates included." Today: a few YAML policies ship as examples; not a template library.
- "Stable SDK API." Today: 0.1.0 — pre-1.0 means the SDK shape can and will change. Say so.
- "Compliance-ready / SOC 2 / ISO 27001." Today: no.

Use the labeling convention: **`available now`**, **`experimental`**, **`planned`**, **`roadmap`**. Do not blur these.
