# Developer utilities

Small command-line helpers for poking at a running Action Marshall backend during local development. None of these are part of the test suite or shipped to users — they are hand-run diagnostics.

| Script                      | What it does                                                                 |
|-----------------------------|------------------------------------------------------------------------------|
| `dump_actions.py`           | Print every row in the local `actions` table. Useful when something is in the DB but not surfacing in the UI. |
| `list_routes.py`            | Print every route the FastAPI app registers. Useful when adding a new router and confirming it loaded. |
| `approve_direct.py`         | Hit `POST /v1/actions/<id>/approve` directly without going through Slack. Edit the hardcoded `action_id` and `BASE` before running. |

## Run

All three assume the backend is running on `http://localhost:8000` and that you can reach it from your shell.

```bash
# From the repo root, with the backend running:
python scripts/dev/dump_actions.py
python scripts/dev/list_routes.py
python scripts/dev/approve_direct.py
```

`dump_actions.py` and `list_routes.py` import from `backend.app.*`, so run them with `PYTHONPATH=backend` if Python can't find the modules:

```bash
PYTHONPATH=backend python scripts/dev/dump_actions.py
```
