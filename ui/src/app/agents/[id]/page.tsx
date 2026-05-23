"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Box, User, Workflow, Clock, PauseCircle, Play, XCircle, Users, UserPlus, Crown, Trash2 } from "lucide-react";
import { Badge, timeAgo } from "@/lib/components";
import {
  fetchAgent, updateAgent, registerAgent,
  fetchAgentCollaborators, addAgentCollaborator, removeAgentCollaborator,
  transferAgentOwnership, fetchEmployees, fetchWorkspaces,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

type AgentDetail = {
  agent_id: string;
  name: string;
  description: string | null;
  workspace_id: string | null;
  workspace_name: string | null;
  owner_employee_id: string | null;
  status: string;
  permissions: { tools?: string[]; action_types?: string[] };
  rate_limit_per_hour: number | null;
  created_at: string;
  last_used_at: string | null;
  owner: { name: string; designation: string; department: string; email: string } | null;
  stats: {
    total_runs: number;
    completed: number;
    blocked: number;
    contained: number;
    awaiting_approval: number;
  };
  recent_runs: Array<{ action_id: string; status: string; tool: string; action_type: string; created_at: string }>;
  can_manage_lifecycle: boolean;
  lifecycle_permission_reason: string;
};

type CollabInfo = {
  owner: { employee_id: string; name: string; designation: string; department: string; email: string } | null;
  collaborators: Array<{
    id: number; employee_id: string; role: string;
    name: string; email: string; designation: string; department: string;
    added_at: string;
  }>;
};

type EmployeeLite = {
  employee_id: string;
  name: string;
  email: string;
  designation: string;
  is_admin: boolean;
};

export default function AgentDetailPage({ params }: { params: { id: string } }) {
  const [data, setData] = useState<AgentDetail | null>(null);
  const [collab, setCollab] = useState<CollabInfo | null>(null);
  const [employees, setEmployees] = useState<EmployeeLite[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);
  const [collabBusy, setCollabBusy] = useState(false);

  const { me } = useAuth();

  // Can manage ownership/collaborators = admin of the agent's workspace
  const canManage = !!me && (
    me.is_admin ||
    (data?.workspace_id
      ? me.memberships.some((m) => m.workspace_id === data.workspace_id && m.role === "admin")
      : false)
  );

  const load = useCallback(async () => {
    try {
      const [agent, collabRes, emps] = await Promise.all([
        fetchAgent(params.id),
        fetchAgentCollaborators(params.id).catch(() => null),
        fetchEmployees().catch(() => []),
      ]);
      setData(agent);
      setCollab(collabRes);
      setEmployees(emps);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  }, [params.id]);

  useEffect(() => { load(); }, [load]);

  async function handleTransfer(newOwnerId: string) {
    if (!confirm(`Transfer ownership of ${data?.name} to this employee?`)) return;
    setCollabBusy(true);
    try {
      await transferAgentOwnership(params.id, newOwnerId);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed");
    } finally {
      setCollabBusy(false);
    }
  }

  async function handleAddCollaborator(emp: EmployeeLite, role: string = "collaborator") {
    setCollabBusy(true);
    try {
      await addAgentCollaborator(params.id, emp.employee_id, role);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed");
    } finally {
      setCollabBusy(false);
    }
  }

  async function handleRemoveCollaborator(emp_id: string) {
    if (!confirm("Remove this collaborator?")) return;
    setCollabBusy(true);
    try {
      await removeAgentCollaborator(params.id, emp_id);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed");
    } finally {
      setCollabBusy(false);
    }
  }

  // Register-agent flow (admin action for pending_registration agents)
  const [workspaces, setWorkspaces] = useState<Array<{ workspace_id: string; name: string }>>([]);
  const [registerOpen, setRegisterOpen] = useState(false);
  const [regWorkspaceId, setRegWorkspaceId] = useState("");
  const [regOwnerId, setRegOwnerId] = useState("");
  const [regTools, setRegTools] = useState("");
  const [regBusy, setRegBusy] = useState(false);

  useEffect(() => {
    fetchWorkspaces().then(setWorkspaces).catch(() => {});
  }, []);

  async function handleRegister() {
    if (!regWorkspaceId) return alert("Choose a workspace");
    if (!regOwnerId) return alert("Choose an owner");
    setRegBusy(true);
    try {
      const tools = regTools.split(",").map((s) => s.trim()).filter(Boolean);
      await registerAgent(params.id, {
        workspace_id: regWorkspaceId,
        owner_employee_id: regOwnerId,
        permissions: tools.length ? { tools } : {},
      });
      setRegisterOpen(false);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed");
    } finally {
      setRegBusy(false);
    }
  }

  async function toggleStatus(next: string) {
    setUpdating(true);
    try {
      await updateAgent(params.id, { status: next });
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed");
    } finally {
      setUpdating(false);
    }
  }

  if (error) {
    return (
      <div className="max-w-5xl mx-auto pt-12">
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-6 text-sm text-red-500">
          {error}
          <div className="mt-3">
            <Link href="/agents" className="text-ks-primary hover:underline inline-flex items-center gap-1">
              <ArrowLeft className="w-4 h-4" /> Back to agents
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="max-w-5xl mx-auto pt-8 space-y-6">
        <div className="h-8 w-48 bg-ks-surface-2 rounded animate-pulse" />
        <div className="h-32 bg-ks-surface-2 rounded-xl animate-pulse" />
        <div className="grid grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-24 rounded-xl bg-ks-surface-2 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  const statusColor =
    data.status === "active" ? "green" :
    data.status === "paused" ? "amber" :
    data.status === "pending_registration" ? "violet" :
    "red";
  const statusLabel = data.status === "pending_registration" ? "needs registration" : data.status;

  return (
    <div className="animate-in fade-in duration-500 pb-16 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-[12px] font-mono text-ks-text3 mb-6 uppercase tracking-widest">
        <Link href="/agents" className="hover:text-ks-text transition-colors flex items-center gap-1">
          <ArrowLeft className="w-3 h-3" /> Agents
        </Link>
        <span>/</span>
        <span className="text-ks-text2">{data.agent_id}</span>
      </div>

      {/* Auto-registered agent banner */}
      {data.status === "pending_registration" && (
        <div className="mb-6 rounded-xl border border-violet-500/30 bg-violet-500/5 overflow-hidden">
          <div className="px-5 py-4 flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <Box className="w-4 h-4 text-violet-500" />
                <h3 className="text-sm font-semibold text-ks-text">Pending registration</h3>
              </div>
              <p className="text-[12px] text-ks-text2 leading-relaxed max-w-xl">
                This agent was auto-discovered on first SDK call.
                An admin must assign a workspace, owner, and permission scope
                before it can run under normal governance.
              </p>
            </div>
            {canManage && !registerOpen && (
              <button
                onClick={() => setRegisterOpen(true)}
                className="px-3 py-1.5 bg-violet-500 text-white text-xs font-semibold rounded hover:opacity-90 transition-opacity shrink-0"
              >
                Register agent
              </button>
            )}
          </div>
          {registerOpen && (
            <div className="px-5 py-4 border-t border-violet-500/20 bg-ks-surface-2/40 space-y-3">
              <div>
                <label className="block text-[10px] font-bold text-ks-text3 uppercase tracking-widest mb-1.5">
                  Assign to workspace
                </label>
                <select
                  value={regWorkspaceId}
                  onChange={(e) => setRegWorkspaceId(e.target.value)}
                  className="w-full bg-ks-surface border border-ks-border rounded text-sm text-ks-text px-2 py-1.5 outline-none focus:border-ks-primary"
                >
                  <option value="">— Choose a workspace —</option>
                  {workspaces.map((w) => (
                    <option key={w.workspace_id} value={w.workspace_id}>{w.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-bold text-ks-text3 uppercase tracking-widest mb-1.5">
                  Primary owner
                </label>
                <select
                  value={regOwnerId}
                  onChange={(e) => setRegOwnerId(e.target.value)}
                  className="w-full bg-ks-surface border border-ks-border rounded text-sm text-ks-text px-2 py-1.5 outline-none focus:border-ks-primary"
                >
                  <option value="">— Choose an owner —</option>
                  {employees.map((emp) => (
                    <option key={emp.employee_id} value={emp.employee_id}>
                      {emp.name} ({emp.designation})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-bold text-ks-text3 uppercase tracking-widest mb-1.5">
                  Allowed tools (comma-separated, blank = all)
                </label>
                <input
                  type="text"
                  value={regTools}
                  onChange={(e) => setRegTools(e.target.value)}
                  placeholder="servicenow, jira"
                  className="w-full bg-ks-surface border border-ks-border rounded text-sm text-ks-text px-2 py-1.5 outline-none focus:border-ks-primary font-mono"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  onClick={() => setRegisterOpen(false)}
                  disabled={regBusy}
                  className="px-3 py-1.5 text-xs font-medium text-ks-text2 hover:text-ks-text transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleRegister}
                  disabled={regBusy || !regWorkspaceId || !regOwnerId}
                  className="px-4 py-1.5 bg-emerald-500 text-white text-xs font-semibold rounded hover:bg-emerald-600 transition-colors disabled:opacity-50"
                >
                  {regBusy ? "Registering…" : "Register & activate"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Header */}
      <div className="bg-ks-surface border border-ks-border rounded-xl p-6 shadow-sm mb-8">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-4 min-w-0">
            <div className="w-12 h-12 rounded-xl bg-ks-surface-2 border border-ks-border flex items-center justify-center shrink-0">
              <Box className="w-6 h-6 text-ks-text2" />
            </div>
            <div className="min-w-0">
              <h1 className="text-2xl font-bold tracking-tight text-ks-text">{data.name}</h1>
              <div className="text-[12px] font-mono text-ks-text3 mt-1">{data.agent_id}</div>
              {data.description && <p className="text-sm text-ks-text2 mt-2 max-w-xl">{data.description}</p>}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Badge color={statusColor} className="text-sm px-3 py-1">{statusLabel}</Badge>
            {data.can_manage_lifecycle ? (
              <>
                {data.status === "active" && (
                  <button
                    onClick={() => toggleStatus("paused")}
                    disabled={updating}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-ks-surface-2 border border-ks-border rounded text-xs font-medium text-ks-text2 hover:text-ks-text hover:bg-ks-hover transition-colors disabled:opacity-50"
                    title="Pause — designated managers and owners only"
                  >
                    <PauseCircle className="w-3.5 h-3.5" />
                    Pause
                  </button>
                )}
                {data.status === "paused" && (
                  <button
                    onClick={() => toggleStatus("active")}
                    disabled={updating}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/30 rounded text-xs font-medium text-emerald-500 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
                  >
                    <Play className="w-3.5 h-3.5" />
                    Resume
                  </button>
                )}
                {data.status !== "revoked" && (
                  <button
                    onClick={() => {
                      if (confirm(`Revoke agent ${data.agent_id}? This cannot be undone from the UI.`)) {
                        toggleStatus("revoked");
                      }
                    }}
                    disabled={updating}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-ks-surface-2 border border-ks-border rounded text-xs font-medium text-red-500 hover:bg-red-500/10 hover:border-red-500/30 transition-colors disabled:opacity-50"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    Revoke
                  </button>
                )}
              </>
            ) : (
              <span
                className="text-[11px] text-ks-text3 italic px-3 py-1.5 rounded bg-ks-surface-2 border border-ks-border"
                title={data.lifecycle_permission_reason}
              >
                Lifecycle controls require manager role
              </span>
            )}
          </div>
        </div>

        {/* Owner + workspace strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-6 border-t border-ks-border/50">
          <div className="flex items-center gap-2 min-w-0">
            <User className="w-4 h-4 text-ks-text3 shrink-0" />
            <div className="min-w-0">
              <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Owner</div>
              <div className="text-[13px] text-ks-text truncate">{data.owner?.name || "—"}</div>
              {data.owner?.designation && (
                <div className="text-[11px] text-ks-text3 truncate">{data.owner.designation}</div>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 min-w-0">
            <Workflow className="w-4 h-4 text-ks-text3 shrink-0" />
            <div className="min-w-0">
              <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Workspace</div>
              {data.workspace_id && data.workspace_name ? (
                <Link href={`/workspaces/${data.workspace_id}`} className="text-[13px] text-ks-text hover:text-ks-primary transition-colors truncate block">
                  {data.workspace_name}
                </Link>
              ) : (
                <div className="text-[13px] text-ks-text3">Unassigned</div>
              )}
            </div>
          </div>
          <div>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Rate Limit</div>
            <div className="text-[13px] font-mono text-ks-text">
              {data.rate_limit_per_hour ? `${data.rate_limit_per_hour}/hour` : "No limit"}
            </div>
          </div>
          <div>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Last Used</div>
            <div className="text-[13px] font-mono text-ks-text">
              {data.last_used_at ? timeAgo(data.last_used_at.replace("Z", "")) : "Never"}
            </div>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-5 gap-3 mb-8">
        <Stat label="Total Runs" value={data.stats.total_runs} />
        <Stat label="Completed" value={data.stats.completed} color="emerald" />
        <Stat label="Contained" value={data.stats.contained} color="amber" />
        <Stat label="Blocked" value={data.stats.blocked} color="red" />
        <Stat label="Pending" value={data.stats.awaiting_approval} color="violet" />
      </div>

      {/* Permissions */}
      <div className="bg-ks-surface border border-ks-border rounded-xl p-6 mb-8">
        <h3 className="text-[11px] font-bold text-ks-text3 uppercase tracking-widest mb-4">Permissions</h3>
        <div className="grid grid-cols-2 gap-6">
          <div>
            <div className="text-[11px] text-ks-text3 mb-2">Allowed Tools</div>
            <div className="flex flex-wrap gap-1.5">
              {(data.permissions.tools || []).length === 0 ? (
                <span className="text-sm text-ks-text3 italic">All tools</span>
              ) : (
                (data.permissions.tools || []).map((t) => (
                  <span key={t} className="px-2 py-0.5 rounded text-[11px] font-mono bg-ks-surface-2 text-ks-text border border-ks-border">
                    {t}
                  </span>
                ))
              )}
            </div>
          </div>
          <div>
            <div className="text-[11px] text-ks-text3 mb-2">Allowed Action Types</div>
            <div className="flex flex-wrap gap-1.5">
              {(data.permissions.action_types || []).length === 0 ? (
                <span className="text-sm text-ks-text3 italic">All action types</span>
              ) : (
                (data.permissions.action_types || []).map((t) => (
                  <span key={t} className="px-2 py-0.5 rounded text-[11px] font-mono bg-ks-surface-2 text-ks-text border border-ks-border">
                    {t}
                  </span>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Ownership + collaborators */}
      <div className="bg-ks-surface border border-ks-border rounded-xl p-6 mb-8">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[11px] font-bold text-ks-text3 uppercase tracking-widest flex items-center gap-2">
            <Users className="w-4 h-4" />
            Ownership & Collaborators
          </h3>
          {!canManage && (
            <span className="text-[11px] text-ks-text3">Read-only — requires workspace admin</span>
          )}
        </div>

        {/* Primary owner */}
        <div className="mb-4">
          <div className="text-[11px] text-ks-text3 mb-2">Primary owner</div>
          <div className="flex items-center justify-between gap-3 p-3 rounded-lg bg-ks-surface-2 border border-ks-border">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-9 h-9 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-500 flex items-center justify-center">
                <Crown className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                {collab?.owner ? (
                  <>
                    <div className="text-sm font-semibold text-ks-text">{collab.owner.name}</div>
                    <div className="text-[11px] text-ks-text3">
                      {collab.owner.designation} · <span className="font-mono">{collab.owner.email}</span>
                    </div>
                  </>
                ) : (
                  <div className="text-[12px] text-ks-text3 italic">No primary owner assigned</div>
                )}
              </div>
            </div>
            {canManage && (
              <OwnerTransferControl
                employees={employees}
                currentOwnerId={collab?.owner?.employee_id}
                busy={collabBusy}
                onTransfer={handleTransfer}
              />
            )}
          </div>
        </div>

        {/* Collaborators */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="text-[11px] text-ks-text3">
              Collaborators ({collab?.collaborators.length ?? 0})
            </div>
            {canManage && (
              <AddCollaboratorControl
                employees={employees.filter((e) =>
                  e.employee_id !== collab?.owner?.employee_id &&
                  !collab?.collaborators.some((c) => c.employee_id === e.employee_id)
                )}
                busy={collabBusy}
                onAdd={handleAddCollaborator}
              />
            )}
          </div>
          {!collab || collab.collaborators.length === 0 ? (
            <div className="px-3 py-4 text-[12px] text-ks-text3 text-center border border-dashed border-ks-border rounded-lg">
              No collaborators. {canManage ? "Click 'Add collaborator' to grant approval rights." : "Admin can grant access."}
            </div>
          ) : (
            <div className="space-y-2">
              {collab.collaborators.map((c) => (
                <div key={c.id} className="flex items-center justify-between gap-3 p-2.5 rounded-lg bg-ks-surface-2 border border-ks-border">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-full bg-ks-surface border border-ks-border text-ks-text2 flex items-center justify-center text-[11px] font-semibold">
                      {c.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                    </div>
                    <div className="min-w-0">
                      <div className="text-[13px] font-medium text-ks-text">{c.name}</div>
                      <div className="text-[11px] text-ks-text3">
                        {c.designation} · <span className="font-mono">{c.email}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge color={c.role === "manager" ? "violet" : "blue"}>
                      {c.role}
                    </Badge>
                    {canManage && (
                      <button
                        onClick={() => handleRemoveCollaborator(c.employee_id)}
                        disabled={collabBusy}
                        className="p-1.5 text-ks-text3 hover:text-red-500 hover:bg-red-500/10 rounded transition-colors disabled:opacity-50"
                        title="Remove collaborator"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent runs */}
      <div className="bg-ks-surface border border-ks-border rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-ks-border bg-ks-surface-2/50 flex items-center justify-between">
          <h3 className="text-[11px] font-bold text-ks-text3 uppercase tracking-widest flex items-center gap-2">
            <Clock className="w-4 h-4" />
            Recent Runs
          </h3>
          <span className="text-[11px] font-mono text-ks-text3">{data.recent_runs.length}</span>
        </div>
        {data.recent_runs.length === 0 ? (
          <div className="px-6 py-12 text-center text-sm text-ks-text3">
            No runs yet. When this agent proposes actions through Keystone, they will appear here.
          </div>
        ) : (
          <div className="divide-y divide-ks-border/50">
            {data.recent_runs.map((run) => {
              const sc = run.status === "completed" ? "green" : run.status === "blocked" ? "red" : run.status === "contained" ? "amber" : run.status === "awaiting_approval" ? "violet" : "gray";
              return (
                <Link
                  key={run.action_id}
                  href={`/actions/${run.action_id}`}
                  className="grid grid-cols-[auto_1fr_100px_100px] gap-4 items-center px-6 py-3.5 hover:bg-ks-hover transition-colors"
                >
                  <div className="font-mono text-[11px] text-ks-text3 truncate">{run.action_id}</div>
                  <div className="text-sm text-ks-text truncate">{run.tool} · {run.action_type}</div>
                  <Badge color={sc}>{run.status}</Badge>
                  <div className="text-[11px] text-ks-text3 text-right font-mono">
                    {timeAgo(run.created_at.replace("Z", ""))}
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function OwnerTransferControl({
  employees, currentOwnerId, busy, onTransfer,
}: {
  employees: EmployeeLite[];
  currentOwnerId: string | undefined;
  busy: boolean;
  onTransfer: (empId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const candidates = employees.filter((e) => e.employee_id !== currentOwnerId);
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        disabled={busy}
        className="text-[11px] font-medium px-2.5 py-1.5 rounded border border-ks-border text-ks-text2 hover:text-ks-text hover:bg-ks-hover transition-colors disabled:opacity-50"
      >
        Transfer
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-72 z-10 rounded-lg border border-ks-border bg-ks-surface shadow-lg max-h-64 overflow-y-auto">
          {candidates.length === 0 ? (
            <div className="px-3 py-2 text-[12px] text-ks-text3">No other employees.</div>
          ) : (
            candidates.map((e) => (
              <button
                key={e.employee_id}
                onClick={() => { setOpen(false); onTransfer(e.employee_id); }}
                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-ks-hover transition-colors text-left"
              >
                <div className="w-7 h-7 rounded-full bg-ks-surface-2 border border-ks-border text-[10px] font-semibold text-ks-text2 flex items-center justify-center">
                  {e.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[12px] font-medium text-ks-text truncate">{e.name}</div>
                  <div className="text-[10px] text-ks-text3 truncate">{e.designation}</div>
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function AddCollaboratorControl({
  employees, busy, onAdd,
}: {
  employees: EmployeeLite[];
  busy: boolean;
  onAdd: (emp: EmployeeLite, role: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [role, setRole] = useState<"collaborator" | "manager">("collaborator");
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        disabled={busy}
        className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-1.5 rounded bg-ks-surface-2 border border-ks-border text-ks-text2 hover:text-ks-text hover:bg-ks-hover transition-colors disabled:opacity-50"
      >
        <UserPlus className="w-3.5 h-3.5" />
        Add collaborator
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-80 z-10 rounded-lg border border-ks-border bg-ks-surface shadow-lg">
          <div className="px-3 py-2 border-b border-ks-border bg-ks-surface-2/60">
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest mb-1.5">Role</div>
            <div className="flex gap-1">
              {([
                { v: "collaborator", label: "Collaborator", sub: "Can approve actions" },
                { v: "manager",      label: "Manager",      sub: "Can also pause / revoke" },
              ] as const).map((opt) => (
                <button
                  key={opt.v}
                  onClick={() => setRole(opt.v)}
                  className={`flex-1 text-left rounded px-2 py-1.5 border text-[11px] transition-colors ${
                    role === opt.v
                      ? "bg-ks-primary/10 border-ks-primary text-ks-primary"
                      : "bg-ks-surface border-ks-border text-ks-text2 hover:bg-ks-hover"
                  }`}
                >
                  <div className="font-semibold">{opt.label}</div>
                  <div className="text-[10px] opacity-80">{opt.sub}</div>
                </button>
              ))}
            </div>
          </div>
          <div className="max-h-64 overflow-y-auto">
            {employees.length === 0 ? (
              <div className="px-3 py-2 text-[12px] text-ks-text3">Everyone is already on this agent.</div>
            ) : (
              employees.map((e) => (
                <button
                  key={e.employee_id}
                  onClick={() => { setOpen(false); onAdd(e, role); }}
                  className="w-full flex items-center gap-2 px-3 py-2 hover:bg-ks-hover transition-colors text-left"
                >
                  <div className="w-7 h-7 rounded-full bg-ks-surface-2 border border-ks-border text-[10px] font-semibold text-ks-text2 flex items-center justify-center">
                    {e.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-[12px] font-medium text-ks-text truncate">{e.name}</div>
                    <div className="text-[10px] text-ks-text3 truncate">{e.designation}</div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color?: string }) {
  const colorClass =
    color === "emerald" ? "text-emerald-500" :
    color === "amber" ? "text-amber-500" :
    color === "red" ? "text-red-500" :
    color === "violet" ? "text-violet-500" : "text-ks-text";
  return (
    <div className="bg-ks-surface-2/50 border border-ks-border rounded-xl p-4">
      <div className={`text-2xl font-bold tabular-nums ${colorClass}`}>{value}</div>
      <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest mt-1">{label}</div>
    </div>
  );
}
