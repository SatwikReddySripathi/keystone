"""
Pre-flight checks for cutting an Action Marshall release.

Run before tagging:

    python scripts/release_check.py v0.2.0

Verifies, in order:

  1. Tag argument is a valid semver vX.Y.Z
  2. Working tree is clean (no uncommitted changes)
  3. On the main branch and synced with origin/main
  4. sdk/pyproject.toml version matches the tag
  5. CHANGELOG.md has a heading matching the tag's version
  6. SDK tests pass (pytest)
  7. SDK package builds (python -m build)
  8. twine check passes on the built artifacts

Exits 0 if everything passes, 1 otherwise. Designed to be cross-platform
(POSIX + Windows) and to not modify the repo -- only inspect.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SDK_DIR = REPO_ROOT / "sdk"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
PYPROJECT = SDK_DIR / "pyproject.toml"

TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)(?:[-+][\w.\-+]+)?$")


# ── ANSI colours (skip on Windows cmd that doesn't support them) ──
def _supports_color() -> bool:
    return sys.stdout.isatty()


_C = {
    "g": "\033[32m" if _supports_color() else "",
    "r": "\033[31m" if _supports_color() else "",
    "y": "\033[33m" if _supports_color() else "",
    "b": "\033[1m" if _supports_color() else "",
    "0": "\033[0m" if _supports_color() else "",
}


def ok(msg: str) -> None:
    print(f"{_C['g']}OK  {_C['0']}{msg}")


def warn(msg: str) -> None:
    print(f"{_C['y']}!!  {_C['0']}{msg}")


def fail(msg: str) -> None:
    print(f"{_C['r']}FAIL{_C['0']}  {msg}")


def run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess:
    """Run a command and return its CompletedProcess."""
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=check,
    )


# ── Individual checks ──

def check_tag_format(tag: str) -> tuple[bool, str]:
    m = TAG_RE.match(tag)
    if not m:
        return False, f"tag {tag!r} is not vX.Y.Z (got {tag})"
    version = ".".join(m.groups()[:3])
    return True, version


def check_working_tree_clean() -> bool:
    result = run(["git", "status", "--porcelain"], cwd=REPO_ROOT)
    if result.returncode != 0:
        fail(f"git status failed: {result.stderr.strip()}")
        return False
    if result.stdout.strip():
        fail("working tree is dirty -- commit or stash before releasing")
        for line in result.stdout.strip().splitlines()[:10]:
            print(f"   {line}")
        return False
    ok("working tree clean")
    return True


def check_on_main() -> bool:
    result = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT)
    if result.returncode != 0:
        fail(f"git rev-parse failed: {result.stderr.strip()}")
        return False
    branch = result.stdout.strip()
    if branch != "main":
        fail(f"current branch is {branch!r}, expected 'main'")
        return False
    ok("on main branch")
    return True


def check_synced_with_origin() -> bool:
    fetch = run(["git", "fetch", "origin"], cwd=REPO_ROOT)
    if fetch.returncode != 0:
        warn("git fetch origin failed -- skipping sync check")
        return True
    rev_local = run(["git", "rev-parse", "main"], cwd=REPO_ROOT).stdout.strip()
    rev_remote = run(["git", "rev-parse", "origin/main"], cwd=REPO_ROOT).stdout.strip()
    if rev_local != rev_remote:
        fail(f"local main ({rev_local[:8]}) != origin/main ({rev_remote[:8]}) -- pull before releasing")
        return False
    ok(f"synced with origin/main ({rev_local[:8]})")
    return True


def check_pyproject_version(expected: str) -> bool:
    if not PYPROJECT.exists():
        fail(f"{PYPROJECT.relative_to(REPO_ROOT)} not found")
        return False
    text = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    if not m:
        fail(f"no version line in {PYPROJECT.relative_to(REPO_ROOT)}")
        return False
    found = m.group(1)
    if found != expected:
        fail(f"pyproject.toml version is {found!r}, tag says {expected!r}")
        return False
    ok(f"pyproject.toml version = {found}")
    return True


def check_changelog(expected: str) -> bool:
    if not CHANGELOG.exists():
        fail(f"{CHANGELOG.relative_to(REPO_ROOT)} not found")
        return False
    text = CHANGELOG.read_text(encoding="utf-8")
    # Look for either `## [X.Y.Z]` or `## X.Y.Z` or `## vX.Y.Z`
    patterns = [
        rf"^##\s*\[?v?{re.escape(expected)}\]?\b",
    ]
    for pat in patterns:
        if re.search(pat, text, flags=re.MULTILINE):
            ok(f"CHANGELOG.md has section for {expected}")
            return True
    # If we only see [Unreleased], remind the user to roll it over.
    if re.search(r"^##\s*\[?Unreleased\]?", text, flags=re.MULTILINE):
        fail(
            f"no `## [{expected}]` heading in CHANGELOG.md -- "
            f"roll [Unreleased] entries under the new version"
        )
    else:
        fail(f"no `## [{expected}]` heading in CHANGELOG.md")
    return False


def check_pytest() -> bool:
    if not (SDK_DIR / "tests").exists():
        warn("sdk/tests not found -- skipping pytest")
        return True
    print("   running pytest (this is the slowest step) ...")
    result = run([sys.executable, "-m", "pytest", "-q"], cwd=SDK_DIR)
    if result.returncode != 0:
        fail("SDK pytest failed")
        sys.stdout.write(result.stdout[-2000:])
        sys.stderr.write(result.stderr[-1000:])
        return False
    # Pull the summary line for a friendly success message
    summary = ""
    for line in result.stdout.splitlines()[::-1]:
        if "passed" in line or "failed" in line:
            summary = line.strip()
            break
    ok(f"SDK pytest: {summary or 'passed'}")
    return True


def check_build_and_twine() -> bool:
    dist_dir = SDK_DIR / "dist"
    # Wipe any prior dist artefacts so twine check only sees what we just built.
    if dist_dir.exists():
        for f in dist_dir.iterdir():
            try:
                f.unlink()
            except OSError:
                pass

    print("   running python -m build ...")
    result = run([sys.executable, "-m", "build"], cwd=SDK_DIR)
    if result.returncode != 0:
        fail("python -m build failed")
        sys.stdout.write(result.stdout[-2000:])
        sys.stderr.write(result.stderr[-1000:])
        return False

    artefacts = list(dist_dir.glob("*"))
    if not artefacts:
        fail("build produced no artefacts in sdk/dist/")
        return False
    ok(f"build produced: {', '.join(a.name for a in artefacts)}")

    print("   running twine check ...")
    result = run(
        [sys.executable, "-m", "twine", "check", *(str(a) for a in artefacts)],
        cwd=SDK_DIR,
    )
    if result.returncode != 0:
        fail("twine check failed")
        sys.stdout.write(result.stdout[-2000:])
        return False
    ok("twine check passed")
    return True


# ── Main ──

def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/release_check.py vX.Y.Z", file=sys.stderr)
        return 2

    tag = sys.argv[1]
    print(f"{_C['b']}Pre-release checks for {tag}{_C['0']}\n")

    valid, version = check_tag_format(tag)
    if not valid:
        fail(version)
        return 1
    ok(f"tag format valid: {tag} -> version {version}")

    checks = [
        check_working_tree_clean,
        check_on_main,
        check_synced_with_origin,
        lambda: check_pyproject_version(version),
        lambda: check_changelog(version),
        check_pytest,
        check_build_and_twine,
    ]

    failed = 0
    for c in checks:
        if not c():
            failed += 1

    print()
    if failed:
        fail(f"{failed} check(s) failed -- do not tag yet.")
        return 1
    ok(f"{_C['b']}All pre-release checks passed. Safe to tag {tag}.{_C['0']}")
    print(f"\n    git tag -a {tag} -m \"{tag}\"")
    print(f"    git push origin {tag}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
