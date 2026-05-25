"""
Action Marshall database layer.

10 tables that track the full lifecycle of every governed action.
Think of it as: an action flows through stages, and each stage
writes to its own table. At any point you can reconstruct
exactly what happened by joining them.
"""
import sqlite3
import os
import json
import hashlib
import glob
from pathlib import Path
from contextlib import contextmanager
from dotenv import load_dotenv

# Import YAML for policy file loading
try:
    import yaml
except ImportError:
    yaml = None

load_dotenv()

# Always resolve relative to the backend/ directory so the DB lands in the
# right place regardless of which directory uvicorn is invoked from.
_BACKEND_DIR = Path(__file__).parent.parent
DB_PATH = os.getenv("DATABASE_PATH") or str(_BACKEND_DIR / "action_marshall.db")

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

-- 13. WORKSPACES: team-scoped governance spaces.
--     Each workspace has its own members, policies, and agent limits.
--     Org admins (authorized_tools='*') can view any workspace.
--     policy_id: if set, this workspace's actions evaluate against this policy
--     (unless an agent in the workspace has its own policy_id override).
CREATE TABLE IF NOT EXISTS workspaces (
    workspace_id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    name TEXT NOT NULL,
    description TEXT,
    owner_id TEXT REFERENCES approvers(employee_id),
    risk_posture TEXT DEFAULT 'healthy',
    policy_id TEXT REFERENCES policies(policy_id),
    created_at TEXT DEFAULT (datetime('now'))
);

-- 14. WORKSPACE_MEMBERS: who belongs to which workspace, with what role.
--     Roles: admin (manage workspace), approver (can approve actions), viewer (read-only)
CREATE TABLE IF NOT EXISTS workspace_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
    employee_id TEXT NOT NULL REFERENCES approvers(employee_id),
    role TEXT NOT NULL DEFAULT 'viewer',
    added_at TEXT DEFAULT (datetime('now')),
    UNIQUE(workspace_id, employee_id)
);

-- 15. CONNECTIONS: registered SaaS apps and tools an agent can operate on.
--     Each connection has a connector_type mapping to a CONNECTORS entry.
--     scopes_json captures what permissions the agent has on this system.
CREATE TABLE IF NOT EXISTS connections (
    connection_id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    workspace_id TEXT REFERENCES workspaces(workspace_id),
    name TEXT NOT NULL,
    connector_type TEXT NOT NULL,
    environment TEXT DEFAULT 'production',
    scopes_json TEXT,
    risk_level TEXT DEFAULT 'medium',
    status TEXT DEFAULT 'active',
    last_tested_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 16. AGENTS: registered AI agents that can propose actions.
--     agent_id matches actor.id on incoming actions — so linking is automatic.
--     permissions_json: {"tools":[...], "action_types":[...]}
--     status: active | paused | revoked
--     policy_id: optional override; if set, takes precedence over workspace policy
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    workspace_id TEXT REFERENCES workspaces(workspace_id),
    name TEXT NOT NULL,
    description TEXT,
    owner_employee_id TEXT REFERENCES approvers(employee_id),
    status TEXT NOT NULL DEFAULT 'active',
    permissions_json TEXT,
    rate_limit_per_hour INTEGER,
    policy_id TEXT REFERENCES policies(policy_id),
    created_at TEXT DEFAULT (datetime('now')),
    last_used_at TEXT
);

-- 17. POLICIES: registered policies loaded from YAML files on disk.
--     content_json holds the fully parsed YAML. hash detects edits.
--     Exactly one policy has is_default=1.
CREATE TABLE IF NOT EXISTS policies (
    policy_id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES orgs(org_id),
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    source_file TEXT NOT NULL,
    hash TEXT NOT NULL,
    content_json TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
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
    workspace_id TEXT REFERENCES workspaces(workspace_id),
    connection_id TEXT REFERENCES connections(connection_id),
    client_ip TEXT,
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

-- 12. APPROVERS: who is authorized to approve actions + sign in to the console.
--     Each approver has an employee_id, name, designation, department.
--     authorized_tools controls which tools they can approve for.
--     is_admin: 1 means this employee can see all workspaces / all actions.
--     Non-admins only see data for workspaces they're a member of.
--     If authorized_tools is NULL or '*', they can approve anything.
CREATE TABLE IF NOT EXISTS approvers (
    employee_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    password_hash TEXT,
    designation TEXT,
    department TEXT,
    authorized_tools TEXT DEFAULT '*',
    is_admin INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    slack_user_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 18. OTP_CODES: one-time codes for signup verification and 2FA login.
--     purpose: 'signup' | 'login'
--     Codes expire after 10 minutes. A new request for the same (email, purpose)
--     deletes any previous code — only one active code at a time.
CREATE TABLE IF NOT EXISTS otp_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    purpose TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_otp_email_purpose ON otp_codes(email, purpose);

-- 19. PENDING_SIGNUPS: email/password/name for accounts that haven't yet
--     verified their email via OTP. Moved into `approvers` on verification.
--     requested_workspace_id: if set, a workspace access request is auto-created
--     on OTP verification so the new employee shows up in the admin queue.
CREATE TABLE IF NOT EXISTS pending_signups (
    email TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    designation TEXT,
    department TEXT,
    requested_workspace_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 20. WORKSPACE_ACCESS_REQUESTS: pending requests from employees to join
--     a workspace. Approved by a workspace admin. Until approved, the
--     requester has no membership and cannot see workspace data.
CREATE TABLE IF NOT EXISTS workspace_access_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
    employee_id TEXT NOT NULL REFERENCES approvers(employee_id),
    role TEXT DEFAULT 'viewer',
    note TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    requested_at TEXT DEFAULT (datetime('now')),
    decided_by_employee_id TEXT REFERENCES approvers(employee_id),
    decided_at TEXT,
    UNIQUE(workspace_id, employee_id)
);

-- 21. AGENT_COLLABORATORS: employees granted collaborator access to an agent
--     by a workspace admin. Distinct from agents.owner_employee_id (the
--     primary owner). Collaborators can approve the agent's actions.
CREATE TABLE IF NOT EXISTS agent_collaborators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
    employee_id TEXT NOT NULL REFERENCES approvers(employee_id),
    role TEXT DEFAULT 'collaborator',
    added_at TEXT DEFAULT (datetime('now')),
    added_by_employee_id TEXT REFERENCES approvers(employee_id),
    UNIQUE(agent_id, employee_id)
);
"""


def _migrate_db(conn):
    """Add columns/tables that may be missing from older DB versions."""
    migrations = [
        "ALTER TABLE actions ADD COLUMN workspace_id TEXT",
        "ALTER TABLE actions ADD COLUMN client_ip TEXT",
        "ALTER TABLE actions ADD COLUMN connection_id TEXT",
        "ALTER TABLE workspaces ADD COLUMN policy_id TEXT",
        "ALTER TABLE agents ADD COLUMN policy_id TEXT",
        "ALTER TABLE approvers ADD COLUMN is_admin INTEGER DEFAULT 0",
        "ALTER TABLE approvers ADD COLUMN password_hash TEXT",
        "ALTER TABLE approvers ADD COLUMN slack_user_id TEXT",
        "ALTER TABLE pending_signups ADD COLUMN requested_workspace_id TEXT",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except Exception:
            pass  # Column already exists


def init_db():
    """Create all tables and seed the demo org + API key."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    _migrate_db(conn)

    org_id = os.getenv("DEFAULT_ORG_ID", "org_demo")
    conn.execute(
        "INSERT OR IGNORE INTO orgs (org_id, name) VALUES (?, ?)",
        (org_id, "Demo Organization")
    )

    api_key = os.getenv("DEFAULT_API_KEY", "am_test_demo_key_001")
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    conn.execute(
        "INSERT OR IGNORE INTO api_keys (key_hash, org_id) VALUES (?, ?)",
        (key_hash, org_id)
    )

    # Demo credentials — documented on the login page.
    # In production these would be bcrypt + real identity provider.
    # slack_user_id: in production, populated via Slack users.info; demo leaves
    # it null so the mapping falls back to email.
    approvers = [
        # employee_id, name, email, password, designation, department, authorized_tools, is_admin, slack_user_id
        ("EMP001", "Sarah Chen",      "sarah.chen@action_marshall.org", "sarah-admin",   "Senior Operations Lead", "Platform Engineering", "*",                1, None),
        ("EMP002", "James Rodriguez", "james.r@action_marshall.org",    "james-admin",   "VP of Engineering",      "Engineering",          "*",                1, None),
        ("EMP003", "Priya Patel",     "priya.p@action_marshall.org",    "priya-demo",    "IT Service Manager",     "IT Operations",        "servicenow",       0, None),
        ("EMP004", "Michael Kim",     "michael.k@action_marshall.org",  "michael-demo",  "Security Analyst",       "Security",             "servicenow,jira",  0, None),
        ("EMP005", "Lisa Wang",       "lisa.w@action_marshall.org",     "lisa-demo",     "Change Manager",         "Change Management",    "*",                0, None),
    ]
    for emp_id, name, email, password, designation, department, tools, is_admin, slack_id in approvers:
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        conn.execute(
            """INSERT INTO approvers
               (employee_id, name, email, password_hash, designation, department, authorized_tools, is_admin, slack_user_id)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(employee_id) DO UPDATE SET
                   email = excluded.email,
                   password_hash = excluded.password_hash,
                   is_admin = excluded.is_admin,
                   slack_user_id = COALESCE(excluded.slack_user_id, approvers.slack_user_id)""",
            (emp_id, name, email, pw_hash, designation, department, tools, is_admin, slack_id)
        )

    # Seed demo workspaces
    workspaces = [
        ("ws_platform", org_id, "Platform Engineering", "Core infrastructure agents and deployment automation", "EMP001", "healthy"),
        ("ws_customer", org_id, "Customer Support", "Support ticket triage and routing agents", "EMP003", "warning"),
        ("ws_sales",    org_id, "Sales Ops",          "CRM sync, pipeline update, and outreach agents",    "EMP005", "healthy"),
        ("ws_security", org_id, "Security Ops",       "Threat response, IAM, and compliance agents",       "EMP004", "critical"),
    ]
    for ws_id, o_id, name, desc, owner, posture in workspaces:
        conn.execute(
            """INSERT OR IGNORE INTO workspaces
               (workspace_id, org_id, name, description, owner_id, risk_posture)
               VALUES (?,?,?,?,?,?)""",
            (ws_id, o_id, name, desc, owner, posture)
        )

    # Seed workspace members
    members = [
        ("ws_platform", "EMP001", "admin"),
        ("ws_platform", "EMP002", "approver"),
        ("ws_customer", "EMP003", "admin"),
        ("ws_customer", "EMP005", "approver"),
        ("ws_sales",    "EMP005", "admin"),
        ("ws_sales",    "EMP002", "viewer"),
        ("ws_security", "EMP004", "admin"),
        ("ws_security", "EMP001", "approver"),
    ]
    for ws_id, emp_id, role in members:
        conn.execute(
            """INSERT OR IGNORE INTO workspace_members
               (workspace_id, employee_id, role) VALUES (?,?,?)""",
            (ws_id, emp_id, role)
        )

    # Seed demo agents — agent_id matches actor.id from the SDK
    agents = [
        # ws_platform — triage-agent-v2 is the demo actor used by the demo scripts
        ("triage-agent-v2",      org_id, "ws_platform", "IT Triage Agent",
         "Bulk ServiceNow incident triage, reassignment, and resolution",
         "EMP001", "active", '{"tools":["servicenow"]}', 200),
        ("incident-resolver-v2", org_id, None, "Incident Resolver Agent",
         "Bulk ServiceNow incident classification, reassignment, and resolution",
         None, "pending_registration", '{}', None),
        ("ticket-triage-bot",    org_id, "ws_platform", "Ticket Triage Bot",
         "Auto-classification and routing for incoming incidents",
         "EMP002", "active", '{"tools":["servicenow","jira"]}', 50),
        ("deploy-verifier",      org_id, "ws_platform", "Deploy Verifier",
         "Post-deployment ServiceNow change record verification",
         "EMP001", "active", '{"tools":["servicenow"]}', 30),
        # ws_customer
        ("support-classifier",   org_id, "ws_customer", "Support Classifier",
         "Zendesk ticket classification and priority assignment",
         "EMP003", "active", '{"tools":["zendesk"]}', 200),
        ("slack-responder",      org_id, "ws_customer", "Slack Responder Bot",
         "Automated first-response for #support channels",
         "EMP003", "paused", '{"tools":["slack"]}', 30),
        # ws_sales
        ("crm-sync-agent",       org_id, "ws_sales",    "CRM Sync Agent",
         "Salesforce opportunity stage sync from marketing signals",
         "EMP005", "active", '{"tools":["salesforce"]}', 100),
        # ws_security
        ("iam-reviewer",         org_id, "ws_security", "IAM Reviewer",
         "AWS IAM policy review and drift detection",
         "EMP004", "paused", '{"tools":["aws_iam"]}', 20),
        ("compliance-scanner",   org_id, "ws_security", "Compliance Scanner",
         "Cross-system compliance audit (SOC2 controls)",
         "EMP004", "active", '{"tools":["aws_iam","servicenow"]}', 50),
    ]
    for aid, o_id, ws_id, name, desc, owner, status, perms, rate in agents:
        conn.execute(
            """INSERT INTO agents
               (agent_id, org_id, workspace_id, name, description,
                owner_employee_id, status, permissions_json, rate_limit_per_hour)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(agent_id) DO UPDATE SET
                   name               = excluded.name,
                   workspace_id       = excluded.workspace_id,
                   description        = excluded.description,
                   owner_employee_id  = excluded.owner_employee_id,
                   status             = excluded.status,
                   permissions_json   = excluded.permissions_json,
                   rate_limit_per_hour = excluded.rate_limit_per_hour""",
            (aid, o_id, ws_id, name, desc, owner, status, perms, rate)
        )

    # Seed policies by scanning the backend/app/policies/*.yaml files.
    # Each YAML file becomes a row in the policies table so the UI can list
    # them, show rules, and show which workspaces/agents use each one.
    _seed_policies(conn, org_id)

    # Bind workspaces to policies. Security gets the strict policy;
    # everyone else uses the default.
    workspace_policy_bindings = [
        ("ws_platform",  "policy_default"),
        ("ws_customer",  "policy_default"),
        ("ws_sales",     "policy_default"),
        ("ws_security",  "policy_strict"),
    ]
    for ws_id, policy_id in workspace_policy_bindings:
        conn.execute(
            "UPDATE workspaces SET policy_id = ? WHERE workspace_id = ? AND org_id = ?",
            (policy_id, ws_id, org_id)
        )

    # Bind specific agents to stricter policies (override their workspace default).
    # compliance-scanner in ws_security — already strict, but make it explicit.
    # iam-reviewer deals with IAM, gets strict override.
    agent_policy_bindings = [
        ("compliance-scanner", "policy_strict"),
        ("iam-reviewer",       "policy_strict"),
    ]
    for agent_id, policy_id in agent_policy_bindings:
        conn.execute(
            "UPDATE agents SET policy_id = ? WHERE agent_id = ? AND org_id = ?",
            (policy_id, agent_id, org_id)
        )

    # Seed demo connections
    connections = [
        ("conn_snow",  org_id, "ws_platform", "ServiceNow",  "servicenow", "production", '["incident.read","incident.write","incident.resolve"]',     "medium"),
        ("conn_jira",  org_id, "ws_platform", "Jira",        "jira",       "production", '["issue.read","issue.write","project.admin"]',               "medium"),
        ("conn_sfdc",  org_id, "ws_sales",    "Salesforce",  "salesforce", "production", '["opportunity.write","account.read","lead.create"]',          "high"),
        ("conn_aws",   org_id, "ws_security", "AWS IAM",     "aws_iam",    "production", '["iam.put","iam.delete","sts.assume","s3.put"]',              "high"),
        ("conn_slack", org_id, "ws_customer", "Slack",       "slack",      "production", '["channels.read","chat.write"]',                             "low"),
        ("conn_gh",    org_id, "ws_platform", "GitHub",      "github",     "production", '["repo.write","actions.write","pr.merge"]',                   "medium"),
        ("conn_zd",    org_id, "ws_customer", "Zendesk",     "zendesk",    "production", '["ticket.read","ticket.update","user.read"]',                 "medium"),
    ]
    for c_id, o_id, ws_id, name, ctype, env, scopes, risk in connections:
        conn.execute(
            """INSERT OR IGNORE INTO connections
               (connection_id, org_id, workspace_id, name, connector_type,
                environment, scopes_json, risk_level)
               VALUES (?,?,?,?,?,?,?,?)""",
            (c_id, o_id, ws_id, name, ctype, env, scopes, risk)
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


def _seed_policies(conn, org_id: str):
    """
    Scan backend/app/policies/*.yaml and upsert each into the policies table.

    policy_id is derived from the filename (e.g. default_policy.yaml → policy_default).
    Content is stored as JSON; hash detects when YAML files have been edited.
    The file flagged is_default=1 controls the fallback policy used when an
    action has no workspace or agent binding.
    """
    if yaml is None:
        print("WARNING: yaml module not available, skipping policy seed")
        return

    policies_dir = Path(__file__).parent / "policies"
    if not policies_dir.exists():
        return

    # Map filename → (policy_id, is_default, description)
    known = {
        "default_policy.yaml": ("policy_default", 1,
            "The baseline policy applied when no workspace or agent override is set. "
            "Balanced thresholds suitable for most enterprise automation."),
        "strict_policy.yaml":  ("policy_strict",  0,
            "Tighter thresholds and hard blocks on P1/P2/VIP. Used for security-sensitive "
            "workspaces and high-privilege agents like IAM reviewers."),
    }

    for path in sorted(policies_dir.glob("*.yaml")):
        name = path.name
        try:
            with open(path, "r") as f:
                parsed = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"WARNING: could not parse {name}: {e}")
            continue

        content_json = json.dumps(parsed, sort_keys=True)
        file_hash = hashlib.sha256(content_json.encode()).hexdigest()[:16]

        pid, is_default, desc = known.get(name, (
            f"policy_{path.stem}",
            0,
            "Loaded from YAML file."
        ))
        display_name = parsed.get("policy_id") or path.stem.replace("_", " ").title()
        version = parsed.get("version") or "1.0.0"

        conn.execute(
            """INSERT INTO policies
                  (policy_id, org_id, name, version, source_file, hash,
                   content_json, is_default, description)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(policy_id) DO UPDATE SET
                   name         = excluded.name,
                   version      = excluded.version,
                   source_file  = excluded.source_file,
                   hash         = excluded.hash,
                   content_json = excluded.content_json,
                   description  = excluded.description,
                   updated_at   = datetime('now')""",
            (pid, org_id, display_name, version, name, file_hash,
             content_json, is_default, desc)
        )