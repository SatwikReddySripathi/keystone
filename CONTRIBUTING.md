# Contributing to Action Marshall

Thanks for your interest in Action Marshall. Action Marshall is action-level release control for AI agents, and we want it to be easy to adopt, easy to extend, and honest about what works today.

This guide explains how to set up a development environment, how to propose changes, and how we run releases.

## Code of Conduct

Participation in this project is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). By contributing you agree to uphold it.

## Ways to Contribute

- **Report a bug.** Open an issue with steps to reproduce and what you expected to happen.
- **Request a feature.** Open an issue describing the use case and why existing options do not work.
- **Improve the docs.** Documentation lives in `docs/` and in the README. Small docs PRs are very welcome.
- **Add a connector.** Connectors live under `backend/app/connectors/`. See `base.py` for the abstract interface.
- **Add a framework adapter.** Adapters live under `sdk/action_marshall/adapters/`. Each must declare its framework dependency as an optional extra.
- **Fix a bug, write a test, or polish a rough edge.**

For security vulnerabilities, please follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker and Docker Compose (optional, but useful for self-host parity)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env         # then edit values
uvicorn app.main:app --reload --port 8000
```

The API listens on `http://localhost:8000`. Health check: `GET /health`.

### Frontend

```bash
cd ui
npm ci
cp .env.example .env.local   # then edit values
npm run dev
```

The UI listens on `http://localhost:3000`.

### SDK

```bash
cd sdk
pip install -e .
```

This installs the `action-marshall` package in editable mode. You can then `from action_marshall import Action Marshall, Action` in any Python script.

## Tests

Three test surfaces, three runners. CI runs all of them on every push and PR — a change that breaks any of them will not merge.

### Backend — pytest suite (preferred for new tests)

Fast, in-process tests using FastAPI's `TestClient`. No server needed. Each test gets a fresh temp SQLite DB.

```bash
cd backend
python -m pytest -v
```

Lives in `backend/tests/`. Add new tests here. The `client` fixture in `backend/tests/conftest.py` provides an authenticated `TestClient` with a clean DB.

### Backend — legacy script-style tests

Older module-level scripts. Useful for integration coverage that hits a live uvicorn (canary side-effects, end-to-end API + approval flow). CI runs them in two phases:

```bash
cd backend
# Phase 1: pure-Python tests
python test_db.py
python test_simulator.py
python test_preview.py
python test_policy.py
python test_canary.py
python test_proof.py
python test_side_effect.py

# Phase 2: HTTP-based tests (start uvicorn first)
uvicorn app.main:app --port 8000 &
python test_api.py
python test_approval_flow.py
kill %1
```

New tests should land in the pytest suite, not as new `backend/test_*.py` scripts.

### SDK — pytest suite

```bash
cd sdk
python -m pytest -v
```

34+ tests covering imports, action serialization, the `MarshallClient` HTTP methods, the `wrap_function` decorator, framework adapter graceful failure, and the CLI.

### Frontend checks

```bash
cd ui
npm ci
npm run lint
npx tsc --noEmit
npm run build
```

UI doesn't have unit tests yet (Next.js build + lint + type-check is the smoke test). Component-level testing is `planned`.

## Pull Requests

1. Fork the repo and create a feature branch off `main`.
2. Keep changes focused. One PR per logical change. Refactors and feature work should be separate PRs.
3. Update or add tests for behavior you change.
4. Update relevant docs (`README.md`, `docs/`, code comments where genuinely helpful).
5. Run the backend tests and the frontend build locally before pushing.
6. Open the PR. Describe what changed, why, and how to verify.

We use **conventional commit** prefixes in PR titles to make changelogs easier:

- `feat:` new functionality
- `fix:` bug fix
- `docs:` documentation only
- `refactor:` no behavior change
- `test:` test-only changes
- `chore:` tooling, deps, config
- `perf:` performance
- `ci:` CI / workflow changes
- `build:` build system or packaging changes

Add a scope in parens when useful: `feat(sdk):`, `fix(ci):`, `docs(self-hosting):`.

Flag breaking changes with a `!` after the prefix or a `BREAKING CHANGE:` footer:

```
feat(sdk)!: rename MarshallClient.run() second positional arg to `mode`
```

Example: `feat(sdk): add ks.wrap() for plain Python tools`

### Changelog

If your PR changes user-visible behavior, add an entry to [CHANGELOG.md](CHANGELOG.md) under the `[Unreleased]` section. Describe the impact in past tense, user-facing terms — not the implementation. Skip the changelog for internal-only changes (CI tweaks, test refactors, comment-only edits).

### Versioning

We follow [Semantic Versioning](https://semver.org/) with one caveat: while we are pre-1.0, **minor version bumps may include breaking changes**. Patch bumps are always non-breaking. Pin to a specific minor (`action-marshall ~= 0.1.0`) if you cannot tolerate that.

## Honest Documentation

Action Marshall documentation uses an explicit labeling convention. When you write or update docs, please use one of:

- `available now` — works in the current release.
- `experimental` — works but the API may change without notice.
- `planned` — committed for an upcoming release.
- `roadmap` — wanted, no committed timeline.

Do not blur these. A feature that does not actually work is `planned`, not `available now`.

## Style

- **Python**: follow `ruff` defaults. Type hints encouraged on public APIs.
- **TypeScript / React**: follow the configured eslint + tsconfig settings.
- **Comments**: write a comment only when the *why* is non-obvious. Do not narrate what the code already says.
- **No unused or speculative code**: do not add abstractions for hypothetical future requirements.

## Release Process

Releases are tagged and published from `main`. The one-page checklist is [RELEASE.md](RELEASE.md); the full runbook (PyPI Trusted Publisher setup, GHCR permissions, rollback) is [docs/release.md](docs/release.md).

Short version:

1. Bump `version` in [sdk/pyproject.toml](sdk/pyproject.toml).
2. Move `[Unreleased]` entries in [CHANGELOG.md](CHANGELOG.md) under a new `[X.Y.Z]` heading.
3. Run `python scripts/release_check.py vX.Y.Z` to verify everything is consistent.
4. Open a `release/vX.Y.Z` PR, merge.
5. `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`.

The tag push triggers PyPI + Docker publish via GitHub Actions.

## Questions

If you're not sure whether a contribution is wanted, open an issue first to discuss. We would rather agree on the shape of a change before you spend time on it.
