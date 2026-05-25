from action_marshall import MarshallClient, Action, ActionParams, Actor

ks = MarshallClient(
    base_url="https://your-action_marshall-instance.com",
    api_key="ks_your_api_key",
)

action = Action(
    actor=Actor(id="my-agent-v1", name="My Agent"),
    tool="servicenow",
    action_type="bulk_update",
    params=ActionParams(
        connector="servicenow_sim",
        query={"state": "open", "priority": "P3"},
        changes={"assignment_group": "Triage Team"},
    ),
)

# Step 1: Preview — see blast radius and policy decision, nothing changes
preview = ks.run(action, mode="observe_only")
print(f"Blast radius : {preview.blast_radius} records")
print(f"Policy says  : {preview.decision_value}")

result = ks.execute(preview.action_id)
print(f"Status       : {result.status}")
print(f"Proof        : {result.proof_url}")
