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

---

<!--
Past releases will appear below this line. The first published release
will be 0.1.0 (the initial public alpha). Until then, the section above
captures everything that has landed in main.
-->
