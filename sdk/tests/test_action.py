"""Action serialization tests."""
from action_marshall import Action, ActionParams, Actor, Approval, Approver


def test_action_to_dict_minimal():
    a = Action()
    d = a.to_dict()

    assert d["tool"] == "servicenow"
    assert d["action_type"] == "bulk_update"
    assert d["environment"] == "simulation"
    assert d["actor"]["id"] == "agent-001"
    assert d["params"]["connector"] == "servicenow_sim"

    # Optional fields default to None and are dropped from the payload
    for k in ("approval", "idempotency_key", "workspace_id", "connection_id"):
        assert k not in d, f"{k} should be omitted when None"


def test_action_to_dict_full():
    a = Action(
        tool="servicenow",
        action_type="update_incident",
        environment="production",
        actor=Actor(id="incident-agent", name="Triage Bot"),
        params=ActionParams(
            connector="servicenow_real",
            query={"state": "open", "priority": "P3"},
            changes={"state": "resolved"},
        ),
        idempotency_key="key-1",
        approval=Approval(
            approver=Approver(id="emp-42", name="Sam"),
            preview_hash="ph_1",
            policy_version="2",
        ),
        workspace_id="ws_demo",
        connection_id="conn_snow",
    )

    d = a.to_dict()
    assert d["actor"]["name"] == "Triage Bot"
    assert d["params"]["query"]["priority"] == "P3"
    assert d["idempotency_key"] == "key-1"
    assert d["workspace_id"] == "ws_demo"
    assert d["connection_id"] == "conn_snow"
    assert d["approval"]["approver"]["id"] == "emp-42"
    assert d["approval"]["preview_hash"] == "ph_1"
