const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const KEY = process.env.NEXT_PUBLIC_API_KEY || "ks_test_demo_key_001";

const headers: Record<string, string> = {
  "X-API-Key": KEY,
  "Content-Type": "application/json",
};

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