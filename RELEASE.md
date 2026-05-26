# Release process

One-page checklist for cutting an Action Marshall release.

The **full runbook** (one-time PyPI Trusted Publisher setup, GHCR permissions, rollback procedure, etc.) lives in [docs/release.md](docs/release.md). This file is the quick reference for someone who already has the setup done and wants to ship a new version.

## Versioning

[Semantic Versioning](https://semver.org/) with one caveat: while we are pre-1.0, **minor version bumps may include breaking changes**. Patch bumps are always non-breaking.

Tag format is always `v<MAJOR>.<MINOR>.<PATCH>` — the leading `v` is part of the tag, not the version in `pyproject.toml`.

## Conventional commits

PR titles and commit messages on `main` use [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) prefixes so changelogs are easier to assemble:

| Prefix | When to use |
|---|---|
| `feat:` | New user-visible feature |
| `fix:` | Bug fix |
| `perf:` | Performance improvement |
| `refactor:` | Code change with no behavior change |
| `docs:` | Documentation only |
| `test:` | Test-only changes |
| `chore:` | Tooling, dependencies, config |
| `ci:` | CI / workflow changes |
| `build:` | Build system changes |

Add a scope in parens when useful: `feat(sdk):`, `fix(ci):`, `docs(self-hosting):`.

Breaking changes are flagged with a `!` after the prefix or a `BREAKING CHANGE:` footer:

```
feat(sdk)!: rename MarshallClient.run() second positional arg to `mode`
```

## Release checklist

For a release `vX.Y.Z`:

### 1. Update the version + changelog

```powershell
# Edit sdk/pyproject.toml
#   version = "X.Y.Z"

# Edit CHANGELOG.md
#   - Move all entries from [Unreleased] under a new [X.Y.Z] - YYYY-MM-DD heading
#   - Recreate an empty [Unreleased] block at the top
```

### 2. Run the pre-flight check

```powershell
python scripts/release_check.py vX.Y.Z
```

This verifies the working tree is clean, you're on `main`, `pyproject.toml` matches the tag, `CHANGELOG.md` has a matching heading, all tests pass, and the package builds cleanly.

If anything fails, fix and re-run.

### 3. Commit and open the release PR

```powershell
git checkout -b release/vX.Y.Z
git add sdk/pyproject.toml CHANGELOG.md
git commit -m "chore: release vX.Y.Z"
git push origin release/vX.Y.Z
```

Open the PR, wait for green CI, merge.

### 4. Tag and push

```powershell
git checkout main
git pull origin main
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

Pushing the tag fires:

- **`.github/workflows/publish-python.yml`** — builds sdist + wheel, runs `twine check`, publishes to PyPI via OIDC Trusted Publishing.
- **`.github/workflows/docker.yml`** — builds and pushes `ghcr.io/satwikreddysripathi/action-marshall-{backend,ui}:X.Y.Z`.

If you enabled "Required reviewers" on the `pypi` GitHub environment, the publish job pauses for your approval click before pushing to PyPI.

### 5. Verify

```powershell
# PyPI
pip install action-marshall==X.Y.Z
action-marshall version          # → action-marshall X.Y.Z

# Docker images
docker pull ghcr.io/satwikreddysripathi/action-marshall-backend:X.Y.Z
docker pull ghcr.io/satwikreddysripathi/action-marshall-ui:X.Y.Z
```

### 6. Cut a GitHub Release *(optional but recommended)*

Go to https://github.com/SatwikReddySripathi/action-marshall/releases/new:

- Tag: `vX.Y.Z` (existing)
- Title: `vX.Y.Z`
- Body: paste the changelog section for this version
- Publish

## Rollback

PyPI does **not** allow re-uploading the same version. If something is broken:

1. Yank the release on PyPI: https://pypi.org/manage/project/action-marshall/release/X.Y.Z/ → **Options → Yank**. This hides it from `pip install` but preserves it for users who pinned that version.
2. Cut a patch release (`X.Y.Z+1`) with the fix.

Docker image rollback is easier — your old tag is still on GHCR. Just point your deployment at `:X.Y.(Z-1)` again.

## What can break during release

| Symptom | Cause | Fix |
|---|---|---|
| `publish-python.yml` 403 on OIDC step | PyPI Trusted Publisher not configured or environment name mismatch | Verify https://pypi.org/manage/project/action-marshall/settings/publishing/ matches our `publish-python.yml` (repo + workflow + environment = `pypi`) |
| `publish-python.yml` fails on `tag vs pyproject.toml mismatch` | You tagged `vX.Y.Z` but `pyproject.toml` still says the old version | Delete the tag, fix the version, retag |
| `docker.yml` 403 on push to GHCR | "Workflow permissions" set to read-only | Repo Settings → Actions → "Workflow permissions" → Read and write |
| GitHub Release isn't auto-created | We don't auto-create one — do it manually in Step 6 | n/a |

## Full reference

- [docs/release.md](docs/release.md) — one-time setup, deeper detail on each step, rollback, manual fallback
- [CHANGELOG.md](CHANGELOG.md) — what changed in each version
- [CONTRIBUTING.md](CONTRIBUTING.md) — conventional commit prefixes, dev setup
