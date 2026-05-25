"""MarshallClient method tests: run, preview, verify_receipt."""
import pytest

from action_marshall import (
    Action,
    ActionResult,
    MarshallAPIError,
    PreviewResult,
    Receipt,
)
from tests.conftest import FakeResponse, make_run_response


def test_client_sets_api_key_header():
    from action_marshall import MarshallClient

    ks = MarshallClient(api_key="ks_secret")
    assert ks._session.headers.get("X-API-Key") == "ks_secret"


def test_run_returns_action_result(ks, fake_session):
    fake_session.post.return_value = FakeResponse(200, make_run_response())

    result = ks.run(Action())

    assert isinstance(result, ActionResult)
    assert result.action_id == "act_test_123"
    assert result.decision_value == "AUTO"
    assert result.blast_radius == 3
    assert result.preview_hash == "ph_abc"
    assert result.policy_version == "1"
    assert result.breaker_tripped is False

    # Posted to the right URL with mode=enforce
    call = fake_session.post.call_args
    assert call.args[0] == "http://localhost:8000/v1/run"
    assert call.kwargs["json"]["mode"] == "enforce"


def test_preview_uses_observe_only(ks, fake_session):
    fake_session.post.return_value = FakeResponse(
        200, make_run_response(decision="AUTO", status="observed")
    )

    result = ks.preview(Action())

    assert isinstance(result, PreviewResult)
    # PreviewResult is also an ActionResult
    assert isinstance(result, ActionResult)

    call = fake_session.post.call_args
    assert call.kwargs["json"]["mode"] == "observe_only"


def test_run_raises_on_api_error(ks, fake_session):
    fake_session.post.return_value = FakeResponse(403, {"detail": "agent revoked"})

    with pytest.raises(MarshallAPIError) as exc_info:
        ks.run(Action())

    assert exc_info.value.status_code == 403
    assert "agent revoked" in str(exc_info.value)


def test_verify_receipt(ks, fake_session):
    fake_session.get.return_value = FakeResponse(
        200,
        {
            "action_id": "act_x",
            "receipt": {"action": {"action_id": "act_x"}, "decision": "AUTO"},
            "signature": "sig_abc",
            "verified": True,
        },
    )

    receipt = ks.verify_receipt("act_x")

    assert isinstance(receipt, Receipt)
    assert receipt.verified is True
    assert receipt.signature == "sig_abc"
    fake_session.get.assert_called_once_with(
        "http://localhost:8000/v1/actions/act_x/proof", timeout=30.0
    )
