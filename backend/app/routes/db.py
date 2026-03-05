"""
Keystone database layer.

10 tables that track the full lifecycle of every governed action.
Think of it as: an action flows through stages, and each stage
writes to its own table. At any point you can reconstruct
exactly what happened by joining them.
"""
import sqlite3
import os
import json
import hashlib
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DATABASE_PATH", "keystone.db")

# ── Schema ──────────────────────────────────────────
# Read through each table — they follow the action lifecycle:
#
#   action created → preview generated → policy decision made
#   → approval recorded (if needed) → canary executed
#   → checks run → breaker evaluated → proof signed
#   → events logged at every step

SCHEMA = """
-- 1. ORGS: multi-tenancy. Every action belongs to an org.
--    In production, each customer gets their own org_id.
CREATE TABLE IF NOT EXISTS orgs (
    org_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 2. API_KEYS: authentication. Keys are stored as SHA-256 hashes.
--    The raw key is never stored — same pattern as password hashing.
CREATE TABLE IF NOT EXISTS api_keys (
    key_hash TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    created_at TEXT DEFAULT (datetime('now'))
);

-- 3. ACTIONS: the core object. "An agent wants to do X."
--    This is the Action Object from the checklist — it captures
--    who (actor), what (tool + action_type + params), where (environment),
--    and how (mode: enforce or observe_only).
CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    tool TEXT NOT NULL,
    action_type TEXT NOT NULL,
    environment TEXT NOT NULL DEFAULT 'simulation',
    actor_json TEXT,
    params_json TEXT,
    idempotency_key TEXT,
    mode TEXT NOT NULL DEFAULT 'enforce',
    parent_action_id TEXT,
    child_action_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
-- Idempotency: if an agent retries the same request, we return
-- the existing action instead of creating a duplicate.
CREATE UNIQUE INDEX IF NOT EXISTS idx_actions_idempotency
    ON actions(org_id, idempotency_key);

-- 4. PREVIEWS: "what WOULD happen if we execute this action?"
--    blast_radius = how many records are affected
--    diffs = before/after for each record
--    flags = risk signals (P1 present, VIP present, etc.)
--    preview_hash = deterministic hash of the preview data.
--    This hash is what approvals bind to — if the data changes,
--    the hash changes, and old approvals are invalidated.
CREATE TABLE IF NOT EXISTS previews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT NOT NULL REFERENCES actions(action_id),
    preview_hash TEXT NOT NULL,
    blast_radius_json TEXT,
    diffs_json TEXT,
    flags_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 5. DECISIONS: "what does our policy say about this action?"
--    Links to the exact policy_id + version used.
--    decision = AUTO | CANARY | APPROVAL_REQUIRED | BLOCK
--    reasons = why (which rules matched)
--    This is the "Blocked because rule X matched" from the checklist.
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT NOT NULL REFERENCES actions(action_id),
    policy_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    decision TEXT NOT NULL,
    reasons_json TEXT,
    thresholds_json TEXT,
    required_checks_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 6. APPROVALS: "who approved this, and what exactly did they approve?"
--    Critically: preview_hash + policy_version are stored.
--    An approval is only valid if these match the current state.
--    This prevents "approve then swap the payload" attacks.
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT NOT NULL REFERENCES actions(action_id),
    approver_json TEXT NOT NULL,
    preview_hash TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    channel TEXT DEFAULT 'sdk',
    created_at TEXT DEFAULT (datetime('now'))
);

-- 7. EXECUTIONS: "what actually ran?"
--    phase = 'canary' (first 5 records) or 'expand' (the rest)
--    subset_ids = which specific record IDs were in this batch
--    results = per-record success/failure
--    error_rate = computed from results
CREATE TABLE IF NOT EXISTS executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT NOT NULL REFERENCES actions(action_id),
    phase TEXT NOT NULL,
    subset_ids_json TEXT,
    results_json TEXT,
    error_rate REAL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 8. CHECKS: post-execution verification.
--    "Did only the intended records change?"
--    "Did only the intended fields change?"
--    "Is the error rate acceptable?"
--    Each check is a row with passed=true/false + details.
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT NOT NULL REFERENCES actions(action_id),
    check_name TEXT NOT NULL,
    passed INTEGER NOT NULL,
    details_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 9. BREAKER: circuit breaker state.
--    If any check fails, tripped=1 and expansion is prevented.
--    The action ends in "contained" status instead of "completed".
CREATE TABLE IF NOT EXISTS breaker (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT NOT NULL REFERENCES actions(action_id),
    tripped INTEGER NOT NULL DEFAULT 0,
    reason TEXT,
    tripped_at TEXT
);

-- 10. PROOFS: the signed audit receipt.
--     Contains the entire action lifecycle as JSON.
--     signature = HMAC-SHA256 over the canonical JSON.
--     If anyone tampers with the receipt, verification fails.
CREATE TABLE IF NOT EXISTS proofs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT NOT NULL REFERENCES actions(action_id),
    receipt_json TEXT NOT NULL,
    signature TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 11. EVENTS: timeline of everything that happened.
--     Every state transition, every check, every decision.
--     This powers the timeline view in the UI.
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT NOT NULL REFERENCES actions(action_id),
    type TEXT NOT NULL,
    payload_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


def init_db():
    """Create all tables and seed the demo org + API key."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    # Seed default org
    org_id = os.getenv("DEFAULT_ORG_ID", "org_demo")
    conn.execute(
        "INSERT OR IGNORE INTO orgs (org_id, name) VALUES (?, ?)",
        (org_id, "Demo Organization")
    )

    # Seed default API key (stored as hash, never raw)
    api_key = os.getenv("DEFAULT_API_KEY", "ks_test_demo_key_001")
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    conn.execute(
        "INSERT OR IGNORE INTO api_keys (key_hash, org_id) VALUES (?, ?)",
        (key_hash, org_id)
    )

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


@contextmanager
def get_db():
    """Get a database connection with auto-commit."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_event(conn, action_id: str, event_type: str, payload: dict = None):
    """Record a timestamped event in the action timeline."""
    conn.execute(
        "INSERT INTO events (action_id, type, payload_json) VALUES (?, ?, ?)",
        (action_id, event_type, json.dumps(payload or {}))
    )