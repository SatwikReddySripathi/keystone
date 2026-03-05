"""
Keystone MVP — FastAPI application entry point.

Start with:
  uvicorn app.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.db import init_db
from app.routes.actions import router as actions_router
from app.routes.policies import router as policies_router
from app.routes.approve import router as approve_router
from app.routes.slack import router as slack_router

app = FastAPI(
    title="Keystone",
    description="Transaction governance for agent actions",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(actions_router)
app.include_router(policies_router)
app.include_router(approve_router)
app.include_router(slack_router)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "service": "keystone"}