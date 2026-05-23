"use client";

import { useCallback, useEffect, useState } from "react";
import { Box, Network, CheckSquare, FileSearch, ArrowLeft, MoreHorizontal, Users, Shield, Download, UserPlus, XCircle, CheckCircle2, Trash2 } from "lucide-react";
import Link from "next/link";
import { Badge, timeAgo } from "@/lib/components";
import { motion } from "framer-motion";
import {
  fetchWorkspace, downloadAuditExport,
  listWorkspaceRequests, approveAccessRequest, denyAccessRequest,
  fetchEmployees, addWorkspaceMember, removeWorkspaceMember,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

type WorkspaceDetail = {
  workspace_id: string;
  name: string;
  description: string | null;
  owner_id: string | null;
  risk_posture: string;
  owner: { name: string; designation: string; department: string; email: string } | null;
  members: Array<{ employee_id: string; role: string; name: string; email: string; designation: string; department: string }>;
  connections: Array<{ connection_id: string; name: string; connector_type: string; risk_level: string; scopes: string[] }>;
  agents: Array<{ agent_id: string; name: string; description: string | null; status: string; rate_limit_per_hour: number | null; permissions: { tools?: string[] }; last_used_at: string | null }>;
  recent_runs: Array<{ action_id: string; status: string; tool: string; action_type: string; actor: { name?: string; id?: string }; created_at: string; mode: string }>;
  stats: {
    total_runs: number;
    completed: number;
    blocked: number;
    contained: number;
    awaiting_approval: number;
    members: number;
    connections: number;
    agents: number;
  };
};

type Tab = "overview" | "agents" | "connections" | "members" | "runs";

type AccessRequest = {
  id: number;
  workspace_id: string;
  employee_id: string;
  role: string;
  note: string | null;
  status: string;
  requested_at: string;
  employee: { name: string; email: string; designation: string; department: string } | null;
};

export default function WorkspaceDetailPage({ params }: { params: { id: string } }) {
  const [data, setData] = useState<WorkspaceDetail | null>(null);
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [downloading, setDownloading] = useState(false);
  const [busy, setBusy] = useState<Record<number, boolean>>({});
  const { me } = useAuth();

  // Can the signed-in user admin this workspace (approve access requests)?
  const canAdmin = !!me && (me.is_admin ||
    me.memberships.some((m) => m.workspace_id === params.id && m.role === "admin"));

  const load = useCallback(async () => {
    try {
      const d = await fetchWorkspace(params.id);
      setData(d);
      if (canAdmin) {
        try {
          const reqs = await listWorkspaceRequests(params.id, "pending");
          setRequests(reqs);
        } catch { /* non-fatal */ }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  }, [params.id, canAdmin]);

  useEffect(() => { load(); }, [load]);

  async function decide(requestId: number, action: "approve" | "deny") {
    setBusy((b) => ({ ...b, [requestId]: true }));
    try {
      if (action === "approve") await approveAccessRequest(params.id, requestId);
      else await denyAccessRequest(params.id, requestId);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy((b) => ({ ...b, [requestId]: false }));
    }
  }

  // ── Admin: add members directly ─────────────────────
  const [allEmployees, setAllEmployees] = useState<Array<{ employee_id: string; name: string; email: string; designation: string }>>([]);
  const [inviteBusy, setInviteBusy] = useState(false);

  useEffect(() => {
    if (canAdmin) {
      fetchEmployees().then(setAllEmployees).catch(() => {});
    }
  }, [canAdmin]);

  async function handleAddMember(employeeId: string, role: string) {
    setInviteBusy(true);
    try {
      await addWorkspaceMember(params.id, employeeId, role);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed");
    } finally {
      setInviteBusy(false);
    }
  }

  async function handleRemoveMember(employeeId: string) {
    if (!confirm("Remove this member from the workspace?")) return;
    setInviteBusy(true);
    try {
      await removeWorkspaceMember(params.id, employeeId);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed");
    } finally {
      setInviteBusy(false);
    }
  }

  const candidateEmployees = (allEmployees || []).filter((e) =>
    !data?.members.some((m) => m.employee_id === e.employee_id)
  );

  async function handleExport() {
    setDownloading(true);
    try {
      await downloadAuditExport("csv", { workspace_id: params.id });
    } catch (e) {
      alert(e instanceof Error ? e.message : "Export failed");
    } finally {
      setDownloading(false);
    }
  }

  if (error) {
    return (
      <div className="max-w-5xl mx-auto pt-12">
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-6 text-sm text-red-500">
          {error}
          <div className="mt-3">
            <Link href="/workspaces" className="text-ks-primary hover:underline inline-flex items-center gap-1">
              <ArrowLeft className="w-4 h-4" /> Back to workspaces
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="max-w-7xl mx-auto">
        <div className="h-8 w-48 bg-ks-surface-2 rounded mb-6 animate-pulse" />
        <div className="h-20 bg-ks-surface-2 rounded-xl mb-6 animate-pulse" />
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-24 rounded-xl bg-ks-surface-2 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  const postureColor =
    data.risk_posture === "critical" ? "red" : data.risk_posture === "warning" ? "amber" : "green";

  return (
    <div className="animate-in fade-in duration-500 pb-16 max-w-7xl mx-auto">
      {/* Breadcrumb */}
      <div className="mb-8">
        <div className="flex items-center gap-2 text-[12px] font-mono text-ks-text3 mb-4 uppercase tracking-widest">
          <Link href="/workspaces" className="hover:text-ks-text transition-colors flex items-center gap-1">
            <ArrowLeft className="w-3 h-3" /> Workspaces
          </Link>
          <span>/</span>
          <span className="text-ks-text2">{data.workspace_id}</span>
        </div>

        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-ks-text">{data.name}</h1>
            {data.description && (
              <p className="text-sm text-ks-text2 mt-2 max-w-2xl">{data.description}</p>
            )}
            <div className="flex items-center gap-4 mt-3 flex-wrap">
              {data.owner && (
                <span className="text-sm text-ks-text2">
                  Owner: <span className="font-mono text-ks-text">{data.owner.name}</span>
                  <span className="text-ks-text3"> · {data.owner.designation}</span>
                </span>
              )}
              <Badge color={postureColor}>{data.risk_posture} posture</Badge>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="p-2 rounded-lg bg-ks-surface-2 border border-ks-border text-ks-text2 hover:text-ks-text hover:bg-ks-hover transition-colors">
              <MoreHorizontal className="w-5 h-5" />
            </button>
            <button
              onClick={handleExport}
              disabled={downloading}
              className="flex items-center gap-2 px-4 py-2 bg-ks-surface border border-ks-border rounded-lg text-sm font-medium text-ks-text hover:bg-ks-hover transition-colors disabled:opacity-50"
            >
              <Download className="w-4 h-4" />
              {downloading ? "Exporting…" : "Export Audit"}
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-6 border-b border-ks-border mb-8 overflow-x-auto">
        {([
          { id: "overview", label: "Overview" },
          { id: "agents", label: `Agents (${data.stats.agents})` },
          { id: "connections", label: `Connected Systems (${data.stats.connections})` },
          { id: "members", label: `Members (${data.stats.members})` },
          { id: "runs", label: `Recent Runs (${data.stats.total_runs})` },
        ] as const).map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`pb-3 text-sm font-medium transition-colors border-b-2 whitespace-nowrap ${
              tab === t.id
                ? "border-ks-primary text-ks-primary"
                : "border-transparent text-ks-text2 hover:text-ks-text"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Pending access requests — only visible to admins of this workspace */}
      {canAdmin && requests.length > 0 && (
        <div className="mb-6 rounded-xl border border-violet-500/30 bg-violet-500/5 overflow-hidden">
          <div className="px-5 py-3 border-b border-violet-500/20 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <UserPlus className="w-4 h-4 text-violet-500" />
              <h3 className="text-sm font-semibold text-ks-text">
                Access requests
                <span className="ml-2 text-[11px] font-mono bg-violet-500/20 text-violet-500 px-1.5 py-0.5 rounded">
                  {requests.length}
                </span>
              </h3>
            </div>
            <span className="text-[11px] text-ks-text3">Approve to grant workspace access</span>
          </div>
          <div className="divide-y divide-violet-500/20">
            {requests.map((r) => (
              <div key={r.id} className="px-5 py-4 flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-ks-text">{r.employee?.name || r.employee_id}</span>
                    <Badge color="violet">{r.role}</Badge>
                    {r.employee && <span className="text-[11px] text-ks-text3">· {r.employee.designation}</span>}
                  </div>
                  <div className="text-[11px] text-ks-text3 mt-0.5 font-mono">
                    {r.employee?.email || r.employee_id}
                  </div>
                  {r.employee?.department && (
                    <div className="text-[11px] text-ks-text3 mt-0.5">Department: {r.employee.department}</div>
                  )}
                  {r.note && (
                    <div className="text-[12px] text-ks-text2 mt-1.5 italic">"{r.note}"</div>
                  )}
                  <div className="text-[10px] text-ks-text3 mt-1 font-mono">
                    Requested {timeAgo(r.requested_at.replace("Z", ""))}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => decide(r.id, "deny")}
                    disabled={busy[r.id]}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-red-500 border border-ks-border rounded hover:bg-red-500/10 hover:border-red-500/30 transition-colors disabled:opacity-50"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    Deny
                  </button>
                  <button
                    onClick={() => decide(r.id, "approve")}
                    disabled={busy[r.id]}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-white bg-emerald-500 rounded hover:bg-emerald-600 transition-colors disabled:opacity-50"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    {busy[r.id] ? "…" : "Approve"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "overview" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <Stat label="Active Agents" value={data.stats.agents} icon={Box} />
              <Stat label="Connected Systems" value={data.stats.connections} icon={Network} />
              <Stat label="Total Runs" value={data.stats.total_runs} icon={FileSearch} />
              <Stat label="Pending Approvals" value={data.stats.awaiting_approval} icon={CheckSquare} accent={data.stats.awaiting_approval > 0 ? "amber" : undefined} />
            </div>

            <div className="bg-ks-surface border border-ks-border rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-ks-text">Recent Agent Runs</h3>
                <button onClick={() => setTab("runs")} className="text-sm text-ks-primary hover:underline">
                  View all →
                </button>
              </div>
              <div className="space-y-3">
                {data.recent_runs.length === 0 && (
                  <div className="py-8 text-center text-sm text-ks-text3">
                    No runs yet. Actions invoked by this workspace will appear here.
                  </div>
                )}
                {data.recent_runs.slice(0, 5).map((run) => {
                  const statusColor =
                    run.status === "completed" ? "green" :
                    run.status === "blocked" ? "red" :
                    run.status === "contained" ? "amber" :
                    run.status === "awaiting_approval" ? "violet" : "gray";
                  return (
                    <Link
                      key={run.action_id}
                      href={`/actions/${run.action_id}`}
                      className="flex items-center justify-between py-2.5 border-b border-ks-border/50 last:border-0 hover:bg-ks-hover/40 -mx-2 px-2 rounded transition-colors"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-2 h-2 rounded-full bg-emerald-500" />
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-ks-text truncate">
                            {run.tool} · {run.action_type}
                          </div>
                          <div className="text-[11px] font-mono text-ks-text3 truncate">
                            Agent: {run.actor?.name || run.actor?.id || "—"}
                          </div>
                        </div>
                      </div>
                      <div className="text-right shrink-0 ml-3">
                        <Badge color={statusColor}>{run.status.toUpperCase()}</Badge>
                        <div className="text-[10px] text-ks-text3 mt-1 font-mono">
                          {timeAgo(run.created_at.replace("Z", ""))}
                        </div>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="bg-ks-surface-2/50 border border-ks-border rounded-xl p-6">
              <h3 className="text-sm font-bold text-ks-text mb-4 uppercase tracking-widest flex items-center gap-2">
                <Shield className="w-4 h-4" />
                Governance Posture
              </h3>
              <div className="space-y-3">
                <Row label="Completed" value={data.stats.completed.toString()} />
                <Row label="Contained" value={data.stats.contained.toString()} color={data.stats.contained > 0 ? "amber" : undefined} />
                <Row label="Blocked" value={data.stats.blocked.toString()} color={data.stats.blocked > 0 ? "red" : undefined} />
                <Row label="Pending" value={data.stats.awaiting_approval.toString()} color={data.stats.awaiting_approval > 0 ? "violet" : undefined} />
              </div>
            </div>

            <div className="bg-ks-surface-2/50 border border-ks-border rounded-xl p-6">
              <h3 className="text-sm font-bold text-ks-text mb-4 uppercase tracking-widest flex items-center gap-2">
                <Users className="w-4 h-4" />
                Team
              </h3>
              <div className="space-y-2">
                {data.members.slice(0, 4).map((m) => (
                  <div key={m.employee_id} className="flex items-center justify-between py-1.5 text-sm">
                    <div className="min-w-0">
                      <div className="text-ks-text truncate">{m.name}</div>
                      <div className="text-[11px] text-ks-text3 truncate">{m.designation}</div>
                    </div>
                    <Badge color={m.role === "admin" ? "violet" : m.role === "approver" ? "blue" : "gray"}>
                      {m.role}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === "agents" && (
        <div className="rounded-xl border border-ks-border bg-ks-surface shadow-sm overflow-hidden">
          {data.agents.length === 0 ? (
            <div className="px-6 py-16 text-center text-sm text-ks-text3">
              No agents registered in this workspace.
            </div>
          ) : (
            <div className="divide-y divide-ks-border/50">
              {data.agents.map((a) => (
                <Link
                  key={a.agent_id}
                  href={`/agents/${a.agent_id}`}
                  className="grid grid-cols-[auto_1fr_150px_150px_100px] gap-4 items-center px-6 py-4 hover:bg-ks-hover transition-colors"
                >
                  <div className="w-9 h-9 rounded-lg bg-ks-surface-2 border border-ks-border flex items-center justify-center">
                    <Box className="w-4 h-4 text-ks-text2" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-ks-text">{a.name}</div>
                    <div className="text-[11px] font-mono text-ks-text3 mt-0.5">{a.agent_id}</div>
                    {a.description && (
                      <div className="text-[12px] text-ks-text2 mt-1 truncate">{a.description}</div>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {(a.permissions.tools || []).map((t) => (
                      <span key={t} className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-ks-surface-2 text-ks-text2 border border-ks-border">
                        {t}
                      </span>
                    ))}
                  </div>
                  <div className="text-[11px] font-mono text-ks-text3">
                    {a.rate_limit_per_hour ? `${a.rate_limit_per_hour}/hr limit` : "No limit"}
                  </div>
                  <div>
                    <Badge color={a.status === "active" ? "green" : a.status === "paused" ? "amber" : "red"}>
                      {a.status}
                    </Badge>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "connections" && (
        <div className="rounded-xl border border-ks-border bg-ks-surface shadow-sm overflow-hidden">
          {data.connections.length === 0 ? (
            <div className="px-6 py-16 text-center text-sm text-ks-text3">
              No systems connected to this workspace.
            </div>
          ) : (
            <div className="divide-y divide-ks-border/50">
              {data.connections.map((c) => (
                <div key={c.connection_id} className="grid grid-cols-[auto_1fr_120px_1fr] gap-4 items-center px-6 py-4 hover:bg-ks-hover transition-colors">
                  <div className="w-9 h-9 rounded-lg bg-ks-surface-2 border border-ks-border flex items-center justify-center">
                    <Network className="w-4 h-4 text-ks-text2" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-ks-text">{c.name}</div>
                    <div className="text-[11px] font-mono text-ks-text3 mt-0.5">{c.connector_type}</div>
                  </div>
                  <Badge color={c.risk_level === "high" ? "red" : c.risk_level === "medium" ? "amber" : "green"}>
                    {c.risk_level} risk
                  </Badge>
                  <div className="flex flex-wrap gap-1 justify-end">
                    {c.scopes.slice(0, 5).map((s) => (
                      <span key={s} className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-ks-surface-2 text-ks-text2 border border-ks-border">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "members" && (
        <div className="rounded-xl border border-ks-border bg-ks-surface shadow-sm overflow-hidden">
          {canAdmin && (
            <div className="px-5 py-3 border-b border-ks-border bg-ks-surface-2/40 flex items-center justify-between">
              <div className="text-[12px] text-ks-text3">
                Invite employees directly — they'll have access immediately, no approval needed.
              </div>
              <AddMemberControl
                employees={candidateEmployees}
                busy={inviteBusy}
                onAdd={handleAddMember}
              />
            </div>
          )}
          <div className="divide-y divide-ks-border/50">
            {data.members.map((m) => {
              const isOwner = data.owner_id === m.employee_id;
              return (
                <div key={m.employee_id} className="grid grid-cols-[auto_1fr_200px_120px_40px] gap-4 items-center px-6 py-4">
                  <div className="w-9 h-9 rounded-full bg-ks-surface-2 border border-ks-border flex items-center justify-center text-sm font-semibold text-ks-text">
                    {m.name.split(" ").map(n => n[0]).join("").slice(0, 2)}
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-ks-text flex items-center gap-2">
                      {m.name}
                      {isOwner && <span className="text-[9px] font-bold uppercase tracking-widest text-amber-500 bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 rounded">Owner</span>}
                    </div>
                    <div className="text-[11px] text-ks-text3 mt-0.5 font-mono">{m.email}</div>
                  </div>
                  <div className="text-[12px] text-ks-text2">
                    {m.designation} · {m.department}
                  </div>
                  <Badge color={m.role === "admin" ? "violet" : m.role === "approver" ? "blue" : "gray"}>
                    {m.role}
                  </Badge>
                  <div className="flex justify-end">
                    {canAdmin && !isOwner && (
                      <button
                        onClick={() => handleRemoveMember(m.employee_id)}
                        disabled={inviteBusy}
                        className="p-1.5 text-ks-text3 hover:text-red-500 hover:bg-red-500/10 rounded transition-colors disabled:opacity-50"
                        title="Remove member"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {tab === "runs" && (
        <div className="rounded-xl border border-ks-border bg-ks-surface shadow-sm overflow-hidden">
          {data.recent_runs.length === 0 ? (
            <div className="px-6 py-16 text-center text-sm text-ks-text3">
              No runs yet.
            </div>
          ) : (
            <div className="divide-y divide-ks-border/50">
              {data.recent_runs.map((run) => {
                const statusColor =
                  run.status === "completed" ? "green" :
                  run.status === "blocked" ? "red" :
                  run.status === "contained" ? "amber" :
                  run.status === "awaiting_approval" ? "violet" : "gray";
                return (
                  <Link
                    key={run.action_id}
                    href={`/actions/${run.action_id}`}
                    className="grid grid-cols-[1fr_120px_140px_100px] gap-4 items-center px-6 py-4 hover:bg-ks-hover transition-colors"
                  >
                    <div>
                      <div className="text-sm font-semibold text-ks-text">{run.tool} · {run.action_type}</div>
                      <div className="text-[11px] font-mono text-ks-text3 mt-0.5">
                        {run.action_id} · Agent: {run.actor?.name || run.actor?.id || "—"}
                      </div>
                    </div>
                    <Badge color="gray">{run.mode}</Badge>
                    <Badge color={statusColor}>{run.status}</Badge>
                    <div className="text-[11px] text-ks-text3 text-right font-mono">
                      {timeAgo(run.created_at.replace("Z", ""))}
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AddMemberControl({
  employees, busy, onAdd,
}: {
  employees: Array<{ employee_id: string; name: string; email: string; designation: string }>;
  busy: boolean;
  onAdd: (empId: string, role: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [role, setRole] = useState<"viewer" | "approver" | "admin">("viewer");
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        disabled={busy}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-ks-primary text-white text-xs font-semibold rounded hover:opacity-90 transition-opacity disabled:opacity-50"
      >
        <UserPlus className="w-3.5 h-3.5" />
        Invite member
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-96 z-10 rounded-lg border border-ks-border bg-ks-surface shadow-lg">
          <div className="px-3 py-2 border-b border-ks-border bg-ks-surface-2/60">
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest mb-1.5">Role in workspace</div>
            <div className="flex gap-1">
              {([
                { v: "viewer",   label: "Viewer",   sub: "Read-only" },
                { v: "approver", label: "Approver", sub: "Can approve actions" },
                { v: "admin",    label: "Admin",    sub: "Manage members" },
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
              <div className="px-3 py-3 text-[12px] text-ks-text3">Every employee is already in this workspace.</div>
            ) : (
              employees.map((e) => (
                <button
                  key={e.employee_id}
                  onClick={() => { setOpen(false); onAdd(e.employee_id, role); }}
                  className="w-full flex items-center gap-2 px-3 py-2 hover:bg-ks-hover transition-colors text-left"
                >
                  <div className="w-7 h-7 rounded-full bg-ks-surface-2 border border-ks-border text-[10px] font-semibold text-ks-text2 flex items-center justify-center">
                    {e.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-[12px] font-medium text-ks-text truncate">{e.name}</div>
                    <div className="text-[10px] text-ks-text3 truncate">{e.designation} · {e.email}</div>
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

function Stat({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  accent?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-ks-surface/50 border border-ks-border rounded-xl p-5 backdrop-blur-sm"
    >
      <div className="flex justify-between items-start mb-2">
        <div className={`text-3xl font-bold ${accent === "amber" ? "text-amber-500" : "text-ks-text"}`}>
          {value}
        </div>
        <Icon className="w-5 h-5 text-ks-text3" />
      </div>
      <div className="text-[12px] font-bold text-ks-text3 uppercase tracking-widest">{label}</div>
    </motion.div>
  );
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex justify-between items-center text-sm">
      <span className="text-ks-text2">{label}</span>
      <span className={`font-mono font-bold ${color === "amber" ? "text-amber-500" : color === "red" ? "text-red-500" : color === "violet" ? "text-violet-500" : "text-ks-text"}`}>
        {value}
      </span>
    </div>
  );
}
