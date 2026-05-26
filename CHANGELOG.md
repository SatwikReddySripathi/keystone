# Changelog

All notable changes to this project are recorded here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Pre-1.0 caveat:** while we are below `1.0.0`, **minor** version bumps may include breaking changes. Pin to a specific minor (`action-marshall ~= 0.1.0`) if you cannot tolerate that. Patch bumps are always non-breaking.

Sections used per release:
- **Added** — new features
- **Changed** — changes in existing functionality
- **Deprecated** — soon-to-be removed features
- **Removed** — removed features
- **Fixed** — bug fixes
- **Security** — vulnerability fixes

---

## [Unreleased]

Tracks work merged to `main` but not yet tagged for release. When cutting a release, move these entries under a new `## [X.Y.Z] - YYYY-MM-DD` heading and reset this section.

### Added

- *(populate as PRs land)*

### Changed

- *(populate as PRs land)*

### Fixed

- *(populate as PRs land)*

---

## [0.1.0] - 2026-05-25

Initial public alpha. Everything below is fresh — there is no prior public release.

### Added

#### SDK (`action-marshall` on PyPI)

- `MarshallClient` with `run()`, `preview()`, `wrap()`, `wrap_function()`, `wrap_tool()`, `verify_receipt()`, plus convenience accessors (`get_action`, `get_proof`, `list_actions`, `execute`, `get_policy`).
- Action types: `Action`, `ActionParams`, `Actor`, `Approval`, `Approver`.
- Result types: `ActionResult`, `PreviewResult`, `Receipt`.
- Exception hierarchy: `MarshallError` → `MarshallAPIError` / `MarshallDenied` / `MarshallApprovalRequired`.
- `wrap_function()` decorator that intercepts function calls, asks the backend for a policy decision, and either calls the underlying function (on `AUTO` / `CANARY`) or raises (on `BLOCK` / `APPROVAL_REQUIRED`). Supports `on_denied` / `on_approval_required` callbacks for non-exceptional handling.
- LangChain adapter (`action_marshall.adapters.langchain.wrap_langchain_tool`) — `available now` *(experimental)*. Adapters package is structured so adding new framework integrations does not bloat the base install.
- `py.typed` marker shipped in the wheel; mypy / pyright pick up annotations automatically.
- Optional installs for `[langchain]`, `[langgraph]`, `[crewai]`, `[autogen]`, `[mcp]`, `[llamaindex]`, `[openai]`, `[dev]`, `[all]`.

#### CLI (`action-marshall` binary)

- `action-marshall init` — write `~/.marshall/config.json` (API key + base URL).
- `action-marshall preview <action.json>` — submit an action in `observe_only` mode and print the decision.
- `action-marshall run <action.json> [--mode]` — full lifecycle run, prints status / decision / proof URL.
- `action-marshall receipts list [--limit] [--status] [--tool]` — table of recent actions.
- `action-marshall receipts verify <action_id>` — fetch and HMAC-verify a signed receipt; non-zero exit if signature fails.
- `action-marshall version` — prints the installed package version.
- Config resolution order: flags → env vars (`MARSHALL_API_KEY`, `MARSHALL_BASE_URL`) → `~/.marshall/config.json` → defaults.

#### Backend (`docker pull ghcr.io/satwikreddysripathi/action-marshall-backend:0.1.0`)

- Six-stage action lifecycle: preview → policy → approval → canary → circuit breaker → signed proof.
- `POST /v1/run` orchestrator with `enforce` and `observe_only` modes.
- Policy engine reading versioned YAML from `backend/app/policies/`. Content-hashed decisions, escalation hierarchy (`BLOCK > APPROVAL_REQUIRED > CANARY > AUTO`), structured reasons.
- Pluggable connector interface (`base.py`) with three shipped implementations: `servicenow_sim`, `servicenow_real`, `email_generic`.
- Deterministic canary subset selection (SHA-256 of `action_id:sys_id`).
- Five post-execution safety checks: `no_out_of_scope`, `only_intended_fields`, `error_rate_ok`, `no_vip_state_change`, `no_p1_state_change`.
- HMAC-SHA256 signed audit receipts bound to `preview_hash + policy_version`. `verify_proof()` uses `hmac.compare_digest()` for constant-time comparison.
- Slack interactive-message approval flow with employee 2FA (email + password + 6-digit OTP, account lockout, per-IP rate limit).
- `GET /health` (liveness) and `GET /ready` (DB connectivity + signing-key presence; returns 503 if either fails).
- Multi-tenant model: org-scoped API keys (SHA-256 hashed), workspaces with member roles, agent registry with auto-registration, connection registry.
- Approval permission model: workspace-scoped admin role, agent owner / collaborator paths, never org-wide admin bypass.
- Idempotency-key support on `POST /v1/run`.

#### Frontend (`docker pull ghcr.io/satwikreddysripathi/action-marshall-ui:0.1.0`)

- Next.js 14 dashboard pages: action list, action detail, signed-proof viewer, approvals queue, agent list + detail, audit log + filters, login, policies, systems, workspaces (list + detail + members).
- Auto-refresh hook to poll action status.
- Dark mode.

#### Self-hosting

- `docker compose up` brings backend + UI with `restart: unless-stopped`, healthcheck on `/ready`, UI waiting for backend `service_healthy`.
- Backend Dockerfile: non-root `marshall` user (UID 1001), `HEALTHCHECK` directive hitting `/ready`, single-worker rationale documented in-file.
- UI Dockerfile: non-root `nextjs:nodejs` user, `npm ci` for reproducible installs.
- Top-level `.env.example` consolidating every backend + UI env var.

#### Docs

- `docs/repo-audit.md` — initial gap analysis with P0/P1/P2 prioritisation.
- `docs/self-hosting.md` — 5-minute quickstart, env vars table, persistent data, Slack + ServiceNow setup, HTTPS, upgrade workflow, common issues.
- `docs/deployment.md` — production hardening: TLS, secrets management with `PROOF_SECRET` rotation cost flagged, operational characteristics, sizing benchmarks, backup recipe, capacity thresholds, honest "what's not yet supported" list.
- `docs/hosted.md` — self-hosted vs hosted comparison, what hosted will and won't do, design-partner selection criteria. Every hosted feature labeled `planned`.
- `docs/security.md` — full threat model (what we defend, what's out of scope), per-stage controls walkthrough, cryptographic inventory with rotation costs, auth + approval permission model, rate-limiting and lockout, safe defaults audited against actual code, audit-receipt format with offline-verify recipe, self-host security checklist, honest known-weaknesses list with `planned` fixes (unsalted SHA-256 password hashing, single-worker state, no `PROOF_SECRET` rotation path, long-lived API keys).
- `docs/cli.md` — full CLI reference with example output and exit codes.
- `docs/release.md` — one-time PyPI Trusted Publisher setup walkthrough, GHCR permissions, release checklist, rollback procedure.
- `docs/migrations/README.md` — historical record of the `keystone` → `action-marshall` rename.
- `CHANGELOG.md`, `RELEASE.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE` (MIT).

#### CI / Release infrastructure

- `.github/workflows/backend-ci.yml` — pure-Python unit tests, SDK pytest suite, integration phase with a live uvicorn for HTTP-based tests.
- `.github/workflows/ui-ci.yml` — npm ci, eslint, `tsc --noEmit`, `next build`.
- `.github/workflows/publish-python.yml` — tag-gated PyPI publish via OIDC Trusted Publishing (no API tokens). Tag-vs-pyproject version-match guard.
- `.github/workflows/docker.yml` — backend + UI image builds with GHA cache, GHCR push **only on `v*` tags** so the registry stays clean of unreleased builds.
- `.github/workflows/secret-scan.yml` — gitleaks on every PR + push to main, with full-history fetch.
- `.github/dependabot.yml` — weekly updates for actions, pip, npm, docker. Grouped updates + `ignore` rules for major bumps on the Next.js + React + TypeScript + Python + Node + ESLint stack.
- `scripts/release_check.py` — cross-platform pre-flight verifier (tag format, working tree clean, on main, synced with origin, pyproject version matches, CHANGELOG has heading, pytest passes, build + twine check pass).
- `scripts/dev/` — manual dev utilities: `dump_actions.py`, `list_routes.py`, `approve_direct.py`.

#### Testing

- 23 backend pytest tests under `backend/tests/` using FastAPI's `TestClient` (health, action lifecycle, approvals, proof signing + tamper detection).
- 34 SDK pytest tests under `sdk/tests/` (imports, action serialization, client methods, wrap behavior, adapter graceful failure, CLI commands).
- Legacy backend `test_*.py` script tests kept and exercised in CI's integration phase.
- Branch protection on `main`: PR-only, force-push blocked, deletion blocked, status checks tracked.

### Honest known weaknesses (planned to address)

- Password hashing is unsalted SHA-256 — argon2id migration is `planned`. Today's only mitigation is mandatory OTP 2FA.
- Backend runs single-worker (rate-limit + approval state are in-process). Multi-worker requires Redis-backed state — `planned`.
- No `PROOF_SECRET` rotation path — rotating today invalidates past-receipt verification by design. Multi-key signing is `planned`.
- No structured metrics export (no Prometheus / OTel). `planned`.
- No SSO / SAML — `planned`.
- No bulk audit-receipt export endpoint — `planned`.

---

## How to update this file

When you open a PR that changes user-visible behaviour, add an entry under `[Unreleased]` in the appropriate section. Keep the description in **past tense, user-facing terms** — describe the impact, not the implementation:

```md
### Added
- New `/ready` endpoint returns 503 until the database is reachable and
  `PROOF_SECRET` is configured. Use for load-balancer readiness probes.

### Fixed
- `ks.wrap_function()` no longer raises `KeyError` when the wrapped
  function takes no positional arguments.
```

Skip the changelog for internal-only changes (CI tweaks, test refactors, comment-only edits).

At release time:

1. Replace `[Unreleased]` with `## [0.X.0] - YYYY-MM-DD`.
2. Move all entries from the previous Unreleased section under it.
3. Recreate an empty `## [Unreleased]` block at the top for future work.
4. See [RELEASE.md](RELEASE.md) for the full release workflow.
