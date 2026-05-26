"""
Shared pytest fixtures for the backend test suite.

The backend reads its config from environment variables at *import time*
(`DATABASE_PATH`, `PROOF_SECRET`, etc.). Tests therefore set those env
vars in a session-scoped fixture and only then import `app.main` --
each test gets a clean, isolated database file under pytest's tmp_path.

Fixtures provided:
    api_key        the seeded demo API key
    org_id         the seeded demo org
    client         a starlette TestClient with the X-API-Key header set
                   and `init_db()` already run against a temp SQLite file
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest


DEMO_API_KEY = "am_test_demo_key_001"
DEMO_ORG_ID = "org_demo"
PROOF_SECRET = "pytest-action-marshall-secret"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Return a TestClient with a freshly-initialised temp database.

    Every test gets its own database file so tests are fully isolated
    and order-independent. Slack is disabled so we never make outbound
    calls during the suite.
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("PROOF_SECRET", PROOF_SECRET)
    monkeypatch.setenv("DEFAULT_ORG_ID", DEMO_ORG_ID)
    monkeypatch.setenv("DEFAULT_API_KEY", DEMO_API_KEY)
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000")

    # Force a clean reload so DB_PATH and any other module-level config
    # picks up the env we just set.
    for mod_name in list(sys.modules):
        if mod_name == "app" or mod_name.startswith("app."):
            del sys.modules[mod_name]

    from fastapi.testclient import TestClient

    app_main = importlib.import_module("app.main")

    # FastAPI startup events fire when TestClient enters its context
    # manager -- that's when init_db() runs.
    with TestClient(app_main.app) as tc:
        tc.headers.update({"X-API-Key": DEMO_API_KEY})
        yield tc


@pytest.fixture
def api_key() -> str:
    return DEMO_API_KEY


@pytest.fixture
def org_id() -> str:
    return DEMO_ORG_ID
