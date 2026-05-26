"""
Action Marshall MVP — FastAPI application entry point.

Start with:
  uvicorn app.main:app --reload --port 8000
"""
import os
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

from app.db import init_db
from app.routes.actions import router as actions_router
from app.routes.policies import router as policies_router
from app.routes.approve import router as approve_router
from app.routes.slack import router as slack_router
from app.routes.stats import router as stats_router
from app.routes.workspaces import router as workspaces_router
from app.routes.connections import router as connections_router
from app.routes.audit import router as audit_router
from app.routes.agents import router as agents_router
from app.routes.auth import router as auth_router
from app.routes.access import router as access_router

app = FastAPI(
    title="Action Marshall",
    description="Transaction governance for agent actions",
    version="0.1.0",
)

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(actions_router)
app.include_router(policies_router)
app.include_router(approve_router)
app.include_router(slack_router)
app.include_router(stats_router)
app.include_router(workspaces_router)
app.include_router(connections_router)
app.include_router(audit_router)
app.include_router(agents_router)
app.include_router(auth_router)
app.include_router(access_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log and return detail for any unhandled 500 so the cause is visible."""
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {str(exc)}"},
    )


@app.on_event("startup")
def startup():
    try:
        init_db()
    except Exception as e:
        import traceback
        print("FATAL: init_db() failed — server will not work correctly")
        traceback.print_exc()
        raise


@app.get("/health")
def health():
    """Liveness probe.

    Returns 200 as long as the process is up. Use this for load balancer
    /  k8s liveness checks where you only want to know if the server should
    be restarted.
    """
    return {"status": "ok", "service": "action_marshall"}


@app.get("/ready")
def ready():
    """Readiness probe.

    Returns 200 only if the server can actually serve traffic:
      - the database is reachable and has the expected schema
      - the proof-signing secret is configured (PROOF_SECRET env var)

    Use this for load-balancer / k8s readiness gates and for healthcheck
    blocks in docker-compose, so a half-initialised process is not added
    to the rotation.

    Returns HTTP 503 with the failing check if anything is wrong.
    """
    checks: dict[str, object] = {}

    # ── DB connectivity + schema sanity ─────────────
    try:
        from app.db import get_db

        with get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table' AND name='orgs'"
            ).fetchone()
            if row["n"] == 1:
                checks["database"] = "ok"
            else:
                checks["database"] = "schema missing — init_db did not run"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}: {exc}"

    # ── Proof signing key present ───────────────────
    # An unsigned proof is a silent integrity failure, so refuse to serve
    # if the signing key is missing.
    if os.getenv("PROOF_SECRET"):
        checks["proof_secret"] = "ok"
    else:
        checks["proof_secret"] = "missing (set PROOF_SECRET env var)"

    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status": "ready" if ok else "not_ready",
            "service": "action_marshall",
            "checks": checks,
        },
    )