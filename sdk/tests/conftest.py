"""Shared pytest fixtures for the Action Marshall SDK tests."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from action_marshall import MarshallClient


class FakeResponse:
    """A minimal stand-in for requests.Response."""

    def __init__(self, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._payload = payload or {}
        self.text = "" if self.ok else str(self._payload.get("detail", "error"))

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def fake_session() -> MagicMock:
    """A requests.Session mock that lets each test program its responses."""
    session = MagicMock()
    session.headers = {}
    return session


@pytest.fixture
def ks(fake_session: MagicMock) -> MarshallClient:
    """A MarshallClient with its HTTP session swapped for the fake session."""
    client = MarshallClient(api_key="ks_test", base_url="http://localhost:8000")
    client._session = fake_session
    return client


def make_run_response(decision: str = "AUTO", status: str = "completed") -> dict:
    """Build a backend-shaped /v1/run response for tests."""
    return {
        "action_id": "act_test_123",
        "status": status,
        "preview": {
            "blast_radius": 3,
            "preview_hash": "ph_abc",
            "flags": {},
        },
        "decision": {
            "decision": decision,
            "policy_version": "1",
            "reasons": [],
        },
        "breaker": {"tripped": False, "reason": None},
        "proof_available": True,
        "proof_url": "/v1/actions/act_test_123/proof",
        "ui_urls": {},
    }
