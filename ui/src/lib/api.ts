const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const KEY = process.env.NEXT_PUBLIC_API_KEY || "ks_test_demo_key_001";

const EMPLOYEE_KEY = "ks_employee_id";

function buildHeaders(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = {
    "X-API-Key": KEY,
    "Content-Type": "application/json",
    ...(extra || {}),
  };
  if (typeof window !== "undefined") {
    const emp = window.localStorage.getItem(EMPLOYEE_KEY);
    if (emp) h["X-Employee-Id"] = emp;
  }
  return h;
}

// Kept for code that doesn't need a fresh lookup per call — reads once at module load.
const headers: Record<string, string> = {
  "X-API-Key": KEY,
  "Content-Type": "application/json",
};

export function getStoredEmployeeId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(EMPLOYEE_KEY);
}

export function setStoredEmployeeId(id: string | null) {
  if (typeof window === "undefined") return;
  if (id) window.localStorage.setItem(EMPLOYEE_KEY, id);
  else window.localStorage.removeItem(EMPLOYEE_KEY);
}

async function _authPost(path: string, body: object) {
  const res = await fetch(`${BASE}/v1/auth/${path}`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export async function authLoginStart(email: string, password: string) {
  // Step 1: verify password, triggers OTP. Returns { requires_otp, demo_otp? }
  return _authPost("login", { email, password });
}

export async function authLoginVerify(email: string, code: string) {
  // Step 2: verify OTP, returns full profile
  return _authPost("verify-login", { email, code });
}

export async function authSignupStart(
  email: string, name: string, password: string,
  designation?: string, department?: string, workspace_id?: string,
) {
  return _authPost("signup", { email, name, password, designation, department, workspace_id });
}

export async function authSignupVerify(email: string, code: string) {
  return _authPost("verify-signup", { email, code });
}

export async function authResendOtp(email: string, purpose: "signup" | "login") {
  return _authPost("resend-otp", { email, purpose });
}

export async function checkCanApprove(actionId: string): Promise<{ allowed: boolean; reason: string }> {
  const h = buildHeaders();
  if (!h["X-Employee-Id"]) return { allowed: false, reason: "Not signed in" };
  const res = await fetch(`${BASE}/v1/auth/can-approve/${actionId}`, { headers: h, cache: "no-store" });
  if (!res.ok) return { allowed: false, reason: "Permission check failed" };
  return res.json();
}

export async function authMe() {
  const h = buildHeaders();
  if (!h["X-Employee-Id"]) return null;
  const res = await fetch(`${BASE}/v1/auth/me`, { headers: h, cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}

export async function fetchEmployees() {
  const res = await fetch(`${BASE}/v1/auth/employees`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch employees");
  return res.json();
}

export async function pingHealth(): Promise<{ ok: boolean; service?: string }> {
  try {
    const res = await fetch(`${BASE}/health`, { cache: "no-store" });
    if (!res.ok) return { ok: false };
    const json = await res.json();
    return { ok: json.status === "ok", service: json.service };
  } catch {
    return { ok: false };
  }
}

export async function fetchPolicies() {
  const res = await fetch(`${BASE}/v1/policies`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch policies");
  return res.json();
}

export async function fetchPolicyById(id: string) {
  const res = await fetch(`${BASE}/v1/policies/${id}`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch policy detail");
  return res.json();
}

export async function fetchActions() {
  const res = await fetch(`${BASE}/v1/actions`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch actions");
  return res.json();
}

export async function fetchAction(id: string) {
  const res = await fetch(`${BASE}/v1/actions/${id}`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch action");
  return res.json();
}

export async function fetchProof(id: string) {
  const res = await fetch(`${BASE}/v1/actions/${id}/proof`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch proof");
  return res.json();
}

export async function approveAction(id: string, employeeId: string) {
  const res = await fetch(`${BASE}/v1/actions/${id}/approve`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      employee_id: employeeId,
      channel: "ui",
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to approve");
  }
  return res.json();
}

export async function executeAction(id: string) {
  const res = await fetch(`${BASE}/v1/actions/${id}/execute`, {
    method: "POST",
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to execute");
  }
  return res.json();
}

export async function denyAction(id: string, employeeId: string) {
  const res = await fetch(`${BASE}/v1/actions/${id}/deny`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      employee_id: employeeId,
      channel: "ui",
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to deny");
  }
  return res.json();
}

export async function fetchApprovers() {
  const res = await fetch(`${BASE}/v1/approvers`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch approvers");
  return res.json();
}

export async function comparePolicy(actionId: string, policyFile = "strict_policy.yaml") {
  const res = await fetch(`${BASE}/v1/policies/compare`, {
    method: "POST",
    headers,
    body: JSON.stringify({ action_id: actionId, policy_file: policyFile }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to compare policies");
  }
  return res.json();
}

export async function fetchStats() {
  const res = await fetch(`${BASE}/v1/stats`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function fetchConnectorUrl(): Promise<{ servicenow_url: string | null }> {
  const res = await fetch(`${BASE}/v1/system/connector-url`, { headers, cache: "no-store" });
  if (!res.ok) return { servicenow_url: null };
  return res.json();
}

export async function fetchTargets(id: string) {
  const res = await fetch(`${BASE}/v1/actions/${id}/targets`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch targets");
  return res.json();
}

export async function fetchRecordTimeline(id: string) {
  const res = await fetch(`${BASE}/v1/actions/${id}/record-timeline`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch record timeline");
  return res.json();
}

export async function rerunAction(id: string) {
  const res = await fetch(`${BASE}/v1/actions/${id}/execute-from-dry-run`, {
    method: "POST",
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to run action");
  }
  return res.json();
}

// ── Workspaces ────────────────────────────────────────
export async function fetchWorkspaces() {
  const res = await fetch(`${BASE}/v1/workspaces`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch workspaces");
  return res.json();
}

export async function fetchWorkspace(id: string) {
  const res = await fetch(`${BASE}/v1/workspaces/${id}`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch workspace");
  return res.json();
}

export async function createWorkspace(body: { name: string; description?: string; owner_id?: string; risk_posture?: string }) {
  const res = await fetch(`${BASE}/v1/workspaces`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create workspace");
  }
  return res.json();
}

// ── Connections ───────────────────────────────────────
export async function fetchConnections(workspaceId?: string) {
  const url = workspaceId ? `${BASE}/v1/connections?workspace_id=${workspaceId}` : `${BASE}/v1/connections`;
  const res = await fetch(url, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch connections");
  return res.json();
}

export async function fetchConnection(id: string) {
  const res = await fetch(`${BASE}/v1/connections/${id}`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch connection");
  return res.json();
}

export async function createConnection(body: {
  name: string;
  connector_type: string;
  workspace_id?: string;
  environment?: string;
  scopes?: string[];
  risk_level?: string;
}) {
  const res = await fetch(`${BASE}/v1/connections`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create connection");
  }
  return res.json();
}

export async function testConnection(id: string) {
  const res = await fetch(`${BASE}/v1/connections/${id}/test`, { method: "POST", headers });
  if (!res.ok) throw new Error("Failed to test connection");
  return res.json();
}

// ── Audit ─────────────────────────────────────────────
export async function fetchAuditList(filters: Record<string, string> = {}) {
  const q = new URLSearchParams(filters).toString();
  const res = await fetch(`${BASE}/v1/audit${q ? "?" + q : ""}`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch audit list");
  return res.json();
}

export async function fetchAuditEntry(actionId: string) {
  const res = await fetch(`${BASE}/v1/audit/entry/${actionId}`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch audit entry");
  return res.json();
}

export function auditCSVUrl(filters: Record<string, string> = {}) {
  const q = new URLSearchParams(filters).toString();
  return `${BASE}/v1/audit/export/csv${q ? "?" + q : ""}`;
}

export function auditJSONProofsUrl(filters: Record<string, string> = {}) {
  const q = new URLSearchParams(filters).toString();
  return `${BASE}/v1/audit/export/json-proofs${q ? "?" + q : ""}`;
}

export async function downloadAuditExport(kind: "csv" | "json", filters: Record<string, string> = {}) {
  const url = kind === "csv" ? auditCSVUrl(filters) : auditJSONProofsUrl(filters);
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const filename = `keystone_audit_${Date.now()}.${kind === "csv" ? "csv" : "json"}`;
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href; a.download = filename; a.click();
  URL.revokeObjectURL(href);
}

// ── Workspace access requests ─────────────────────────
export async function requestWorkspaceAccess(workspaceId: string, body: { role?: string; note?: string } = {}) {
  const res = await fetch(`${BASE}/v1/workspaces/${workspaceId}/requests`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to request access");
  }
  return res.json();
}

export async function listWorkspaceRequests(workspaceId: string, status: string = "pending") {
  const res = await fetch(
    `${BASE}/v1/workspaces/${workspaceId}/requests?status=${status}`,
    { headers: buildHeaders(), cache: "no-store" }
  );
  if (!res.ok) throw new Error("Failed to fetch access requests");
  return res.json();
}

export async function approveAccessRequest(workspaceId: string, requestId: number, role?: string) {
  const res = await fetch(
    `${BASE}/v1/workspaces/${workspaceId}/requests/${requestId}/approve`,
    {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify(role ? { role } : {}),
    }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to approve");
  }
  return res.json();
}

export async function denyAccessRequest(workspaceId: string, requestId: number) {
  const res = await fetch(
    `${BASE}/v1/workspaces/${workspaceId}/requests/${requestId}/deny`,
    { method: "POST", headers: buildHeaders() }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to deny");
  }
  return res.json();
}

export async function addWorkspaceMember(workspaceId: string, employeeId: string, role: string = "viewer") {
  const res = await fetch(`${BASE}/v1/workspaces/${workspaceId}/members`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({ employee_id: employeeId, role }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to add member");
  }
  return res.json();
}

export async function removeWorkspaceMember(workspaceId: string, employeeId: string) {
  const res = await fetch(`${BASE}/v1/workspaces/${workspaceId}/members/${employeeId}`, {
    method: "DELETE",
    headers: buildHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to remove member");
  }
  return res.json();
}

export async function pendingRequestsAsAdmin() {
  const res = await fetch(`${BASE}/v1/access-requests/pending-as-admin`, {
    headers: buildHeaders(),
    cache: "no-store",
  });
  if (!res.ok) return [];
  return res.json();
}

// ── Agent ownership + collaborators ─────────────────────────
export async function transferAgentOwnership(agentId: string, newOwnerEmployeeId: string) {
  const res = await fetch(`${BASE}/v1/agents/${agentId}/transfer-ownership`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({ new_owner_employee_id: newOwnerEmployeeId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to transfer ownership");
  }
  return res.json();
}

export async function fetchAgentCollaborators(agentId: string) {
  const res = await fetch(`${BASE}/v1/agents/${agentId}/collaborators`, {
    headers: buildHeaders(),
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch collaborators");
  return res.json();
}

export async function addAgentCollaborator(agentId: string, employeeId: string, role: string = "collaborator") {
  const res = await fetch(`${BASE}/v1/agents/${agentId}/collaborators`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({ employee_id: employeeId, role }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to add collaborator");
  }
  return res.json();
}

export async function removeAgentCollaborator(agentId: string, employeeId: string) {
  const res = await fetch(`${BASE}/v1/agents/${agentId}/collaborators/${employeeId}`, {
    method: "DELETE",
    headers: buildHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to remove collaborator");
  }
  return res.json();
}

// ── Agents ────────────────────────────────────────────
export async function fetchAgents(workspaceId?: string) {
  const url = workspaceId ? `${BASE}/v1/agents?workspace_id=${workspaceId}` : `${BASE}/v1/agents`;
  const res = await fetch(url, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch agents");
  return res.json();
}

export async function fetchAgent(id: string) {
  const res = await fetch(`${BASE}/v1/agents/${id}`, { headers, cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch agent");
  return res.json();
}

export async function updateAgent(id: string, body: Record<string, unknown>) {
  const res = await fetch(`${BASE}/v1/agents/${id}`, {
    method: "PATCH",
    headers: buildHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to update agent");
  }
  return res.json();
}

export async function registerAgent(id: string, body: {
  workspace_id: string;
  owner_employee_id: string;
  permissions?: { tools?: string[]; action_types?: string[] };
  rate_limit_per_hour?: number;
  description?: string;
}) {
  const res = await fetch(`${BASE}/v1/agents/${id}/register`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to register agent");
  }
  return res.json();
}