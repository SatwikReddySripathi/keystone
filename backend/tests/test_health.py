"""Health and readiness probe tests."""
from __future__ import annotations

import importlib
import sys

import pytest


def test_health_returns_ok(client):
    """/health is liveness only -- 200 as long as the process is up."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "action_marshall"


def test_ready_returns_200_when_configured(client):
    """/ready should pass when DB is reachable and PROOF_SECRET is set."""
    resp = client.get("/ready")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["proof_secret"] == "ok"


def test_ready_returns_503_without_proof_secret(tmp_path, monkeypatch):
    """
    /ready must refuse to serve traffic when PROOF_SECRET is missing.
    A missing signing key is a silent integrity failure if we let it
    through -- audit receipts would not verify.
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.delenv("PROOF_SECRET", raising=False)
    monkeypatch.setenv("DEFAULT_ORG_ID", "org_demo")
    monkeypatch.setenv("DEFAULT_API_KEY", "am_test_demo_key_001")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "")

    for mod_name in list(sys.modules):
        if mod_name == "app" or mod_name.startswith("app."):
            del sys.modules[mod_name]

    from fastapi.testclient import TestClient

    app_main = importlib.import_module("app.main")
    with TestClient(app_main.app) as tc:
        resp = tc.get("/ready")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert "missing" in body["checks"]["proof_secret"]
