# Contributing to Keystone

Thanks for your interest in Keystone. Keystone is action-level release control for AI agents, and we want it to be easy to adopt, easy to extend, and honest about what works today.

This guide explains how to set up a development environment, how to propose changes, and how we run releases.

## Code of Conduct

Participation in this project is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). By contributing you agree to uphold it.

## Ways to Contribute

- **Report a bug.** Open an issue with steps to reproduce and what you expected to happen.
- **Request a feature.** Open an issue describing the use case and why existing options do not work.
- **Improve the docs.** Documentation lives in `docs/` and in the README. Small docs PRs are very welcome.
- **Add a connector.** Connectors live under `backend/app/connectors/`. See `base.py` for the abstract interface.
- **Add a framework adapter.** Adapters live under `sdk/keystone/adapters/`. Each must declare its framework dependency as an optional extra.
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

This installs the `keystone` package in editable mode. You can then `from keystone import Keystone, Action` in any Python script.

## Tests

Backend tests are runnable scripts at `backend/test_*.py`:

```bash
cd backend
python test_db.py
python test_preview.py
python test_policy.py
# ...etc
```

Frontend checks:

```bash
cd ui
npm run lint
npx tsc --noEmit
npm run build
```

CI runs the same commands on every push and pull request. A change that breaks CI will not merge.

We are migrating tests to `pytest` and adding SDK and CLI tests as part of the public-launch checklist. New tests should prefer `pytest` style where practical.

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

Example: `feat(sdk): add ks.wrap() for plain Python tools`

## Honest Documentation

Keystone documentation uses an explicit labeling convention. When you write or update docs, please use one of:

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

Releases are tagged and published from `main`. The current release process is documented in [RELEASE.md](RELEASE.md) (planned). For now:

1. Bump the version in `sdk/setup.py` (later: `pyproject.toml`).
2. Update `CHANGELOG.md`.
3. Tag the commit `vX.Y.Z`.
4. Push the tag. The publish workflow (planned) will build and upload to PyPI.

## Questions

If you're not sure whether a contribution is wanted, open an issue first to discuss. We would rather agree on the shape of a change before you spend time on it.
