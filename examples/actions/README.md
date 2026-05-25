# Example actions

JSON payloads you can feed to the Action Marshall CLI:

```bash
action-marshall preview examples/actions/servicenow_bulk_update.json
action-marshall run     examples/actions/servicenow_bulk_update.json
```

| File                             | Connector          | Expected decision (default policy) | Notes                                                |
|----------------------------------|--------------------|------------------------------------|------------------------------------------------------|
| `servicenow_bulk_update.json`    | `servicenow_sim`   | `CANARY` (≈ 20 P3/P4 records)      | Canary first, then expand. Generates a signed proof. |
| `servicenow_p1_blocked.json`     | `servicenow_sim`   | `BLOCK`                            | P1 in scope → policy stops it. No records change.    |
| `email_send.json`                | `email_generic`    | `AUTO` (small recipient list)      | Outbound email with two recipients.                  |

The schema mirrors the SDK's `Action` dataclass:

```jsonc
{
  "tool": "servicenow",
  "action_type": "bulk_update",
  "environment": "simulation",
  "actor":  { "id": "...", "name": "...", "type": "agent" },
  "params": {
    "connector": "servicenow_sim",
    "query":   { "...": "..." },
    "changes": { "...": "..." }
  },
  "workspace_id":   "optional",
  "connection_id":  "optional",
  "idempotency_key": "optional"
}
```
