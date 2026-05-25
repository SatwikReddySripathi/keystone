"""
Action Marshall command-line interface.

    action_marshall --help
    action_marshall init
    action_marshall preview examples/actions/servicenow_bulk_update.json
    action_marshall run     examples/actions/servicenow_bulk_update.json
    action_marshall receipts list
    action_marshall receipts verify <action_id>

Config resolution order (first match wins):

    1. command-line flags (--api-key, --base-url)
    2. environment variables MARSHALL_API_KEY, MARSHALL_BASE_URL
    3. ~/.marshall/config.json (created by ``action-marshall init``)
    4. defaults (base_url = http://localhost:8000)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import typer

from action_marshall import (
    Action,
    ActionParams,
    Actor,
    MarshallAPIError,
    MarshallClient,
    __version__,
)


CONFIG_PATH = Path.home() / ".action_marshall" / "config.json"
DEFAULT_BASE_URL = "http://localhost:8000"


app = typer.Typer(
    name="action_marshall",
    help="Action-level release control for AI agents.",
    no_args_is_help=True,
    add_completion=False,
)
receipts_app = typer.Typer(
    help="Audit-receipt commands: list and verify.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(receipts_app, name="receipts")


# ── Config helpers ────────────────────────────────────────────

def _load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _resolve_client(
    api_key: Optional[str], base_url: Optional[str]
) -> MarshallClient:
    cfg = _load_config()
    resolved_key = api_key or os.getenv("MARSHALL_API_KEY") or cfg.get("api_key", "")
    resolved_url = (
        base_url
        or os.getenv("MARSHALL_BASE_URL")
        or cfg.get("base_url")
        or DEFAULT_BASE_URL
    )
    if not resolved_key:
        typer.secho(
            "No API key set. Run `action-marshall init` or pass --api-key / set MARSHALL_API_KEY.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    return MarshallClient(api_key=resolved_key, base_url=resolved_url)


def _load_action(path: Path) -> Action:
    if not path.exists():
        typer.secho(f"Action file not found: {path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        typer.secho(f"Invalid JSON in {path}: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    actor_data = raw.get("actor") or {}
    params_data = raw.get("params") or {}
    return Action(
        tool=raw.get("tool", "servicenow"),
        action_type=raw.get("action_type", "bulk_update"),
        environment=raw.get("environment", "simulation"),
        actor=Actor(**actor_data) if actor_data else Actor(),
        params=ActionParams(**params_data) if params_data else ActionParams(),
        idempotency_key=raw.get("idempotency_key"),
        workspace_id=raw.get("workspace_id"),
        connection_id=raw.get("connection_id"),
    )


def _print_kv(rows: list[tuple[str, Any]]) -> None:
    width = max(len(k) for k, _ in rows)
    for k, v in rows:
        typer.echo(f"{k.ljust(width)}  {v}")


# ── Commands ──────────────────────────────────────────────────

@app.command()
def version() -> None:
    """Print the action-marshall version."""
    typer.echo(f"action-marshall {__version__}")


@app.command()
def init(
    api_key: Optional[str] = typer.Option(
        None, "--api-key", "-k", help="API key to store."
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", "-u", help="Backend URL to store."
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite an existing config."
    ),
) -> None:
    """Write your API key and base URL to ~/.marshall/config.json."""
    if CONFIG_PATH.exists() and not force:
        existing = _load_config()
        masked = (existing.get("api_key") or "")[:8]
        typer.echo(f"Config already exists at {CONFIG_PATH}")
        _print_kv(
            [
                ("base_url", existing.get("base_url") or "(unset)"),
                ("api_key", f"{masked}..." if masked else "(unset)"),
            ]
        )
        typer.echo("Pass --force to overwrite.")
        return

    if api_key is None:
        api_key = typer.prompt(
            "API key", default="am_test_demo_key_001", hide_input=True
        )
    if base_url is None:
        base_url = typer.prompt("Base URL", default=DEFAULT_BASE_URL)

    _save_config({"api_key": api_key, "base_url": base_url})
    typer.secho(f"Wrote {CONFIG_PATH}", fg=typer.colors.GREEN)
    typer.echo("Test the connection with:  action_marshall receipts list")


@app.command()
def preview(
    action_file: Path = typer.Argument(
        ..., exists=False, help="Path to a JSON action file."
    ),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
) -> None:
    """Preview an action without executing it."""
    ks = _resolve_client(api_key, base_url)
    action = _load_action(action_file)
    try:
        result = ks.preview(action)
    except MarshallAPIError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    _print_kv(
        [
            ("action_id", result.action_id),
            ("status", result.status),
            ("decision", result.decision_value),
            ("blast_radius", result.blast_radius),
            ("preview_hash", result.preview_hash or "-"),
            ("policy_version", result.policy_version or "-"),
        ]
    )
    reasons = (result.decision or {}).get("reasons") or []
    if reasons:
        typer.echo("reasons:")
        for r in reasons:
            label = r.get("reason") if isinstance(r, dict) else str(r)
            typer.echo(f"  - {label}")


@app.command()
def run(
    action_file: Path = typer.Argument(
        ..., exists=False, help="Path to a JSON action file."
    ),
    mode: str = typer.Option(
        "enforce",
        "--mode",
        "-m",
        help="enforce (run for real) or observe_only (preview and policy only).",
    ),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
) -> None:
    """Run an action through the full Action Marshall lifecycle."""
    ks = _resolve_client(api_key, base_url)
    action = _load_action(action_file)
    try:
        result = ks.run(action, mode=mode)
    except MarshallAPIError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    rows: list[tuple[str, Any]] = [
        ("action_id", result.action_id),
        ("status", result.status),
        ("decision", result.decision_value),
        ("blast_radius", result.blast_radius),
        ("breaker_tripped", result.breaker_tripped),
        ("proof_url", result.proof_url or "-"),
    ]
    dashboard = result.ui_urls.get("detail")
    if dashboard:
        rows.append(("dashboard", dashboard))
    _print_kv(rows)


@receipts_app.command("list")
def receipts_list(
    limit: int = typer.Option(20, "--limit", "-n", help="Max actions to list."),
    status: Optional[str] = typer.Option(
        None, "--status", "-s", help="Filter by status."
    ),
    tool: Optional[str] = typer.Option(None, "--tool", "-t", help="Filter by tool."),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
) -> None:
    """List recent actions and their decisions."""
    ks = _resolve_client(api_key, base_url)
    filters: dict[str, Any] = {"limit": limit}
    if status:
        filters["status"] = status
    if tool:
        filters["tool"] = tool

    try:
        actions = ks.list_actions(**filters)
    except MarshallAPIError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if not actions:
        typer.echo("(no actions found)")
        return

    header = f"{'ACTION_ID':<24} {'STATUS':<22} {'TOOL':<18} {'CREATED':<22}"
    typer.echo(header)
    typer.echo("-" * len(header))
    for a in actions:
        action_id = (a.get("action_id") or "")[:24]
        status_val = (a.get("status") or "")[:22]
        tool_val = (a.get("tool") or "")[:18]
        created = (a.get("created_at") or "")[:22]
        typer.echo(f"{action_id:<24} {status_val:<22} {tool_val:<18} {created:<22}")


@receipts_app.command("verify")
def receipts_verify(
    action_id: str = typer.Argument(..., help="Action ID to verify."),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
) -> None:
    """Fetch a signed receipt and verify its HMAC signature."""
    ks = _resolve_client(api_key, base_url)
    try:
        receipt = ks.verify_receipt(action_id)
    except MarshallAPIError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    color = typer.colors.GREEN if receipt.verified else typer.colors.RED
    typer.secho(f"verified  {receipt.verified}", fg=color, bold=True)
    sig_short = (receipt.signature or "")[:32]
    _print_kv(
        [
            ("action_id", receipt.action_id),
            ("signature", f"{sig_short}..." if sig_short else "(missing)"),
        ]
    )
    if not receipt.verified:
        raise typer.Exit(1)


def main() -> None:  # pragma: no cover - direct script entry
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
