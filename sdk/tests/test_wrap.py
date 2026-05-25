"""Tests for ks.wrap_function / wrap / wrap_tool."""
import pytest

from action_marshall import (
    ActionResult,
    MarshallApprovalRequired,
    MarshallDenied,
    MarshallError,
)
from tests.conftest import FakeResponse, make_run_response


def test_wrap_function_calls_through_on_auto(ks, fake_session):
    fake_session.post.return_value = FakeResponse(200, make_run_response(decision="AUTO"))
    call_log: list[dict] = []

    @ks.wrap_function(tool="t", action_type="a", connector="servicenow_sim", agent_id="ag")
    def update(payload):
        call_log.append(payload)
        return {"applied": True, "payload": payload}

    out = update({"incident_id": "INC001", "status": "resolved"})

    assert out == {"applied": True, "payload": {"incident_id": "INC001", "status": "resolved"}}
    assert call_log == [{"incident_id": "INC001", "status": "resolved"}]

    # The wrapper used preview (observe_only) to ask, not enforce
    posted = fake_session.post.call_args.kwargs["json"]
    assert posted["mode"] == "observe_only"
    assert posted["tool"] == "t"
    assert posted["actor"]["id"] == "ag"
    assert posted["params"]["changes"] == {"incident_id": "INC001", "status": "resolved"}


def test_wrap_function_raises_on_block(ks, fake_session):
    fake_session.post.return_value = FakeResponse(200, make_run_response(decision="BLOCK", status="blocked"))
    called = False

    @ks.wrap_function(tool="t", action_type="a", connector="servicenow_sim")
    def update(payload):
        nonlocal called
        called = True
        return "should not happen"

    with pytest.raises(MarshallDenied) as exc_info:
        update({"x": 1})

    assert called is False
    assert exc_info.value.result.decision_value == "BLOCK"


def test_wrap_function_raises_on_approval_required(ks, fake_session):
    fake_session.post.return_value = FakeResponse(
        200, make_run_response(decision="APPROVAL_REQUIRED", status="awaiting_approval")
    )
    called = False

    @ks.wrap_function(tool="t", action_type="a", connector="servicenow_sim")
    def update(payload):
        nonlocal called
        called = True

    with pytest.raises(MarshallApprovalRequired):
        update({"x": 1})

    assert called is False


def test_on_denied_callback_runs_instead_of_raising(ks, fake_session):
    fake_session.post.return_value = FakeResponse(200, make_run_response(decision="BLOCK"))
    captured = {}

    def handle(err: MarshallDenied):
        captured["seen"] = err.result.decision_value
        return "fallback"

    @ks.wrap_function(
        tool="t", action_type="a", connector="servicenow_sim",
        on_denied=handle,
    )
    def update(payload):
        return "real"

    assert update({"x": 1}) == "fallback"
    assert captured["seen"] == "BLOCK"


def test_wrap_function_return_action_marshall_result_true(ks, fake_session):
    fake_session.post.return_value = FakeResponse(200, make_run_response(decision="AUTO"))

    @ks.wrap_function(
        tool="t", action_type="a", connector="servicenow_sim",
        return_action_marshall_result=True,
    )
    def update(payload):
        return "ignored"

    out = update({"x": 1})
    assert isinstance(out, ActionResult)
    assert out.decision_value == "AUTO"


def test_wrap_function_observe_only_does_not_call_fn(ks, fake_session):
    fake_session.post.return_value = FakeResponse(200, make_run_response(decision="AUTO", status="observed"))
    called = False

    @ks.wrap_function(
        tool="t", action_type="a", connector="servicenow_sim",
        mode="observe_only",
    )
    def update(payload):
        nonlocal called
        called = True
        return "ran"

    out = update({"x": 1})
    assert called is False
    assert out is None


def test_wrap_function_unexpected_decision_raises(ks, fake_session):
    fake_session.post.return_value = FakeResponse(200, make_run_response(decision="WAT"))

    @ks.wrap_function(tool="t", action_type="a", connector="servicenow_sim")
    def update(payload):
        return "x"

    with pytest.raises(MarshallError):
        update({"x": 1})


def test_wrap_dispatches_to_wrap_function_for_callables(ks, fake_session):
    fake_session.post.return_value = FakeResponse(200, make_run_response(decision="AUTO"))

    def fn(payload):
        return "ok"

    wrapped = ks.wrap(fn, tool="t", action_type="a", connector="servicenow_sim")
    assert wrapped({"x": 1}) == "ok"


def test_wrap_function_extracts_kwargs_when_no_dict_positional(ks, fake_session):
    fake_session.post.return_value = FakeResponse(200, make_run_response(decision="AUTO"))

    @ks.wrap_function(tool="t", action_type="a", connector="servicenow_sim")
    def update(*, incident_id, status):
        return {"id": incident_id, "status": status}

    out = update(incident_id="INC001", status="resolved")
    assert out == {"id": "INC001", "status": "resolved"}

    posted = fake_session.post.call_args.kwargs["json"]
    assert posted["params"]["changes"] == {"incident_id": "INC001", "status": "resolved"}
