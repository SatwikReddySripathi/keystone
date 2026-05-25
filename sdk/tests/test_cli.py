"""Tests for the `action-marshall` CLI."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from action_marshall import ActionResult, Receipt
from action_marshall import cli as cli_module
from action_marshall.cli import app

runner = CliRunner()


def _combined_output(result) -> str:
    """Return stdout + stderr in a way that works across Click 8.0–8.2.

    Click 8.2 made stderr separate by default; older versions mix it into
    output. We try both and ignore failures.
    """
    out = result.output or ""
    try:
        err = result.stderr or ""
    except (ValueError, AttributeError):
        err = ""
    return out + err


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point the CLI's config file at an empty tmp dir for every test."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_config = fake_home / ".action_marshall" / "config.json"
    monkeypatch.setattr(cli_module, "CONFIG_PATH", fake_config)
    # Strip any inherited env so resolution falls through to "no key set".
    monkeypatch.delenv("MARSHALL_API_KEY", raising=False)
    monkeypatch.delenv("MARSHALL_BASE_URL", raising=False)
    return fake_config


@pytest.fixture
def example_action(tmp_path):
    """A minimal action JSON on disk."""
    payload = {
        "tool": "servicenow",
        "action_type": "bulk_update",
        "actor": {"id": "test-agent", "name": "Test Agent", "type": "agent"},
        "params": {
            "connector": "servicenow_sim",
            "query": {"state": "open"},
            "changes": {"state": "in_progress"},
        },
    }
    path = tmp_path / "action.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ── Top-level commands ─────────────────────────────────────

def test_help_runs():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Action-level release control" in result.output
    # Sub-apps show up in the help output
    assert "receipts" in result.output


def test_version_prints_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "action-marshall" in result.output


# ── init ───────────────────────────────────────────────────

def test_init_writes_config(isolated_config):
    result = runner.invoke(
        app, ["init", "--api-key", "ks_xyz", "--base-url", "http://example.local"]
    )
    assert result.exit_code == 0, result.output
    assert isolated_config.exists()
    cfg = json.loads(isolated_config.read_text())
    assert cfg == {"api_key": "ks_xyz", "base_url": "http://example.local"}


def test_init_does_not_overwrite_without_force(isolated_config):
    isolated_config.parent.mkdir(parents=True, exist_ok=True)
    isolated_config.write_text(json.dumps({"api_key": "old", "base_url": "http://old"}))

    result = runner.invoke(
        app, ["init", "--api-key", "new", "--base-url", "http://new"]
    )
    assert result.exit_code == 0
    cfg = json.loads(isolated_config.read_text())
    assert cfg["api_key"] == "old"
    assert "Pass --force" in result.output


def test_init_force_overwrites(isolated_config):
    isolated_config.parent.mkdir(parents=True, exist_ok=True)
    isolated_config.write_text(json.dumps({"api_key": "old", "base_url": "http://old"}))

    result = runner.invoke(
        app,
        ["init", "--api-key", "new", "--base-url", "http://new", "--force"],
    )
    assert result.exit_code == 0
    cfg = json.loads(isolated_config.read_text())
    assert cfg == {"api_key": "new", "base_url": "http://new"}


# ── preview / run ──────────────────────────────────────────

def test_preview_requires_api_key(isolated_config, example_action):
    result = runner.invoke(app, ["preview", str(example_action)])
    assert result.exit_code == 1
    # Click writes to stderr by default but typer.testing merges streams.
    combined = _combined_output(result)
    assert "No API key set" in combined


def test_preview_missing_file_exits_with_error(isolated_config, tmp_path, monkeypatch):
    monkeypatch.setenv("MARSHALL_API_KEY", "ks_x")
    result = runner.invoke(app, ["preview", str(tmp_path / "nope.json")])
    assert result.exit_code == 1
    combined = _combined_output(result)
    assert "not found" in combined


def test_preview_happy_path(isolated_config, example_action, monkeypatch):
    monkeypatch.setenv("MARSHALL_API_KEY", "ks_x")

    fake_result = ActionResult(
        {
            "action_id": "act_123",
            "status": "observed",
            "preview": {"blast_radius": 7, "preview_hash": "ph_abc"},
            "decision": {
                "decision": "CANARY",
                "policy_version": "1",
                "reasons": [{"reason": "blast_radius >= 10"}],
            },
            "breaker": None,
        }
    )
    fake_client = MagicMock()
    fake_client.preview.return_value = fake_result

    with patch.object(cli_module, "MarshallClient", return_value=fake_client):
        result = runner.invoke(app, ["preview", str(example_action)])

    assert result.exit_code == 0, result.output
    assert "act_123" in result.output
    assert "CANARY" in result.output
    assert "blast_radius >= 10" in result.output

    fake_client.preview.assert_called_once()


def test_run_happy_path(isolated_config, example_action, monkeypatch):
    monkeypatch.setenv("MARSHALL_API_KEY", "ks_x")

    fake_result = ActionResult(
        {
            "action_id": "act_run",
            "status": "completed",
            "preview": {"blast_radius": 3, "preview_hash": "ph_run"},
            "decision": {"decision": "AUTO", "policy_version": "1", "reasons": []},
            "breaker": {"tripped": False, "reason": None},
            "proof_url": "/v1/actions/act_run/proof",
            "ui_urls": {"detail": "http://localhost:3000/actions/act_run"},
        }
    )
    fake_client = MagicMock()
    fake_client.run.return_value = fake_result

    with patch.object(cli_module, "MarshallClient", return_value=fake_client):
        result = runner.invoke(app, ["run", str(example_action), "--mode", "enforce"])

    assert result.exit_code == 0, result.output
    assert "act_run" in result.output
    assert "completed" in result.output
    assert "AUTO" in result.output
    fake_client.run.assert_called_once()
    _action_arg, kwargs = fake_client.run.call_args.args, fake_client.run.call_args.kwargs
    assert kwargs.get("mode") == "enforce"


# ── receipts ───────────────────────────────────────────────

def test_receipts_list_renders_table(isolated_config, monkeypatch):
    monkeypatch.setenv("MARSHALL_API_KEY", "ks_x")

    fake_client = MagicMock()
    fake_client.list_actions.return_value = [
        {
            "action_id": "act_1",
            "status": "completed",
            "tool": "servicenow",
            "created_at": "2026-05-22T10:00:00",
        },
        {
            "action_id": "act_2",
            "status": "blocked",
            "tool": "email",
            "created_at": "2026-05-22T10:05:00",
        },
    ]
    with patch.object(cli_module, "MarshallClient", return_value=fake_client):
        result = runner.invoke(app, ["receipts", "list", "--limit", "5"])

    assert result.exit_code == 0, result.output
    assert "ACTION_ID" in result.output
    assert "act_1" in result.output
    assert "act_2" in result.output
    fake_client.list_actions.assert_called_once_with(limit=5)


def test_receipts_list_empty(isolated_config, monkeypatch):
    monkeypatch.setenv("MARSHALL_API_KEY", "ks_x")
    fake_client = MagicMock()
    fake_client.list_actions.return_value = []
    with patch.object(cli_module, "MarshallClient", return_value=fake_client):
        result = runner.invoke(app, ["receipts", "list"])
    assert result.exit_code == 0
    assert "(no actions found)" in result.output


def test_receipts_verify_success(isolated_config, monkeypatch):
    monkeypatch.setenv("MARSHALL_API_KEY", "ks_x")
    fake_client = MagicMock()
    fake_client.verify_receipt.return_value = Receipt(
        action_id="act_v",
        receipt={"action": {"action_id": "act_v"}},
        signature="abc" * 20,
        verified=True,
    )
    with patch.object(cli_module, "MarshallClient", return_value=fake_client):
        result = runner.invoke(app, ["receipts", "verify", "act_v"])
    assert result.exit_code == 0, result.output
    assert "verified" in result.output
    assert "True" in result.output


def test_receipts_verify_failure_exits_nonzero(isolated_config, monkeypatch):
    monkeypatch.setenv("MARSHALL_API_KEY", "ks_x")
    fake_client = MagicMock()
    fake_client.verify_receipt.return_value = Receipt(
        action_id="act_v",
        receipt={},
        signature="xx",
        verified=False,
    )
    with patch.object(cli_module, "MarshallClient", return_value=fake_client):
        result = runner.invoke(app, ["receipts", "verify", "act_v"])
    assert result.exit_code == 1
    assert "False" in result.output
