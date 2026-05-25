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
    return {"status": "ok", "service": "action_marshall"}