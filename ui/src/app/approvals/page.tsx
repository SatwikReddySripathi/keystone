"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { CheckSquare, Search, ArrowUpDown, CheckCircle2, XCircle, Clock, AlertTriangle, ExternalLink } from "lucide-react";
import { Badge, timeAgo } from "@/lib/components";
import { fetchAuditList, approveAction, denyAction, executeAction } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAutoRefresh, RefreshControl } from "@/lib/useAutoRefresh";

type PendingAction = {
  action_id: string;
  timestamp: string;
  status: string;
  tool: string;
  action_type: string;
  mode: string;
  workspace_id: string | null;
  workspace_name: string | null;
  agent: { id: string | null; name: string | null };
  governance: {
    decision: string | null;
    policy_id: string | null;
    policy_version: string | null;
    blast_radius: number;
    reasons: Array<{ rule?: string; reason?: string } | string>;
  };
};

type SortKey = "newest" | "oldest" | "blast_desc" | "blast_asc" | "agent" | "workspace";

export default function ApprovalsPage() {
  const [pending, setPending] = useState<PendingAction[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("newest");
  const [workspaceFilter, setWorkspaceFilter] = useState<string>("all");

  const { me, canSeeWorkspace, canApprove } = useAuth();

  const loadAll = useCallback(async () => {
    try {
      const pendingRes = await fetchAuditList({ status: "awaiting_approval", limit: "200" });
      setPending(pendingRes);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  const { refreshing, lastUpdatedAt, paused, togglePause, refresh } = useAutoRefresh(loadAll, 5000);

  // Approver identity is the signed-in user. No impersonation.
  const signedInId = me?.employee_id || "";

  const handleApprove = async (actionId: string) => {
    if (!signedInId) return alert("Not signed in");
    setBusy((b) => ({ ...b, [actionId]: true }));
    try {
      await approveAction(actionId, signedInId);
      await executeAction(actionId);
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setBusy((b) => ({ ...b, [actionId]: false }));
    }
  };

  const handleDeny = async (actionId: string) => {
    if (!signedInId) return alert("Not signed in");
    if (!confirm(`Deny ${actionId}? This blocks the action permanently.`)) return;
    setBusy((b) => ({ ...b, [actionId]: true }));
    try {
      await denyAction(actionId, signedInId);
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Deny failed");
    } finally {
      setBusy((b) => ({ ...b, [actionId]: false }));
    }
  };

  // Scope for non-admins
  const scopedPending = useMemo(() => {
    if (!me) return [];
    if (me.is_admin) return pending || [];
    return (pending || []).filter((p) => canSeeWorkspace(p.workspace_id));
  }, [pending, me, canSeeWorkspace]);

  const workspaces = useMemo(() => {
    const set = new Map<string, string>();
    scopedPending.forEach((p) => {
      if (p.workspace_id && p.workspace_name) set.set(p.workspace_id, p.workspace_name);
    });
    return Array.from(set.entries()).map(([id, name]) => ({ id, name }));
  }, [scopedPending]);

  const filtered = useMemo(() => {
    let arr = [...scopedPending];
    if (workspaceFilter !== "all") arr = arr.filter((p) => p.workspace_id === workspaceFilter);
    if (search) {
      const q = search.toLowerCase();
      arr = arr.filter(
        (p) =>
          p.action_id.toLowerCase().includes(q) ||
          (p.agent.name || "").toLowerCase().includes(q) ||
          (p.agent.id || "").toLowerCase().includes(q) ||
          p.tool.toLowerCase().includes(q) ||
          p.action_type.toLowerCase().includes(q)
      );
    }
    arr.sort((a, b) => {
      switch (sortKey) {
        case "oldest":      return a.timestamp.localeCompare(b.timestamp);
        case "blast_desc":  return b.governance.blast_radius - a.governance.blast_radius;
        case "blast_asc":   return a.governance.blast_radius - b.governance.blast_radius;
        case "agent":       return (a.agent.name || a.agent.id || "").localeCompare(b.agent.name || b.agent.id || "");
        case "workspace":   return (a.workspace_name || "").localeCompare(b.workspace_name || "");
        case "newest":
        default:            return b.timestamp.localeCompare(a.timestamp);
      }
    });
    return arr;
  }, [scopedPending, workspaceFilter, search, sortKey]);

  const stats = useMemo(() => {
    const list = scopedPending;
    const totalBlast = list.reduce((acc, p) => acc + p.governance.blast_radius, 0);
    const oldestMs = list.reduce((min, p) => {
      const ts = Date.parse(p.timestamp.replace(" ", "T") + "Z");
      return isNaN(ts) ? min : Math.min(min, ts);
    }, Date.now());
    const oldestAge = list.length ? Math.floor((Date.now() - oldestMs) / 60000) : 0;
    return { count: list.length, totalBlast, oldestAge };
  }, [scopedPending]);

  return (
    <div className="animate-in fade-in duration-500 pb-16 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ks-text flex items-center gap-3">
            Pending Approvals
            {scopedPending.length > 0 && (
              <span className="text-[11px] font-mono bg-violet-500/10 text-violet-500 border border-violet-500/30 px-2 py-0.5 rounded-full">
                {scopedPending.length}
              </span>
            )}
          </h1>
          <p className="text-[13px] text-ks-text2 mt-1.5 max-w-2xl leading-relaxed">
            Actions awaiting human sign-off. Each approval is bound to the exact preview hash and policy version that was evaluated.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <RefreshControl
            refreshing={refreshing}
            lastUpdatedAt={lastUpdatedAt}
            paused={paused}
            togglePause={togglePause}
            refresh={refresh}
            intervalLabel="5s"
          />
        </div>
      </div>

      {/* Signed-in approver badge — no impersonation */}
      {me && (
        <div className="flex items-center gap-2 text-[11px] text-ks-text3 mb-6 px-1">
          <span>
            Approving as <span className="font-semibold text-ks-text">{me.name}</span>{" "}
            <span className="text-ks-text3">· {me.designation}</span>
          </span>
          <span className="text-ks-text3">·</span>
          <span>
            Tool scope: <span className="font-mono text-ks-text2">{me.authorized_tools}</span>
          </span>
          {!me.is_admin && (
            <>
              <span className="text-ks-text3">·</span>
              <span>
                {me.memberships.length} workspace{me.memberships.length !== 1 ? "s" : ""}
              </span>
            </>
          )}
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatCard label="Pending Actions" value={stats.count} icon={CheckSquare} color={stats.count > 0 ? "violet" : undefined} />
        <StatCard label="Total Blast Radius" value={stats.totalBlast} sub="records affected if all approved" />
        <StatCard
          label="Oldest Pending"
          value={stats.oldestAge}
          sub={stats.oldestAge === 0 ? "no pending actions" : "minutes old"}
          icon={Clock}
          color={stats.oldestAge > 60 ? "amber" : undefined}
        />
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-500 mb-6">{error}</div>
      )}

      {/* Toolbar */}
      <div className="flex items-center justify-between mb-4 p-1 bg-ks-surface-2/50 rounded-lg border border-ks-border gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ks-text3" />
          <input
            type="text"
            placeholder="Search by action, agent, tool..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-transparent border-none focus:ring-0 text-sm text-ks-text pl-9 py-2 placeholder:text-ks-text3 outline-none"
          />
        </div>

        <div className="flex items-center gap-2 px-2">
          <span className="text-[10px] uppercase tracking-widest text-ks-text3 font-semibold">Workspace</span>
          <select
            value={workspaceFilter}
            onChange={(e) => setWorkspaceFilter(e.target.value)}
            className="bg-ks-surface border border-ks-border rounded text-xs text-ks-text px-2 py-1 outline-none"
          >
            <option value="all">All ({scopedPending.length})</option>
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2 px-2 border-l border-ks-border/50">
          <ArrowUpDown className="w-3.5 h-3.5 text-ks-text3" />
          <select
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
            className="bg-ks-surface border border-ks-border rounded text-xs text-ks-text px-2 py-1 outline-none"
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="blast_desc">Blast radius high to low</option>
            <option value="blast_asc">Blast radius low to high</option>
            <option value="agent">Agent A-Z</option>
            <option value="workspace">Workspace A-Z</option>
          </select>
        </div>

        <div className="px-3 text-[11px] font-mono text-ks-text3 uppercase tracking-wider">
          {filtered.length} shown
        </div>
      </div>

      {!pending && !error && (
        <div className="rounded-xl border border-ks-border bg-ks-surface shadow-sm overflow-hidden">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-24 border-b border-ks-border/50 animate-pulse bg-ks-surface-2/40" />
          ))}
        </div>
      )}

      {pending && filtered.length === 0 && (
        <div className="rounded-xl border border-ks-border bg-ks-surface/40 px-6 py-16 text-center">
          <div className="w-12 h-12 rounded-2xl bg-ks-surface-2 border border-ks-border flex items-center justify-center mx-auto mb-4">
            <CheckCircle2 className="w-6 h-6 text-emerald-500" />
          </div>
          <div className="text-sm font-medium text-ks-text">Nothing pending</div>
          <div className="text-[12px] text-ks-text3 mt-1">
            {scopedPending.length === 0 ? "No actions currently awaiting approval." : "No matches for your filters."}
          </div>
        </div>
      )}

      {pending && filtered.length > 0 && (
        <div className="space-y-3">
          {filtered.map((p) => {
            const perm = canApprove({
              workspace_id: p.workspace_id,
              agent_id: p.agent.id,
              tool: p.tool,
            });
            return (
              <ApprovalCard
                key={p.action_id}
                action={p}
                onApprove={() => handleApprove(p.action_id)}
                onDeny={() => handleDeny(p.action_id)}
                busy={!!busy[p.action_id]}
                canAct={perm.allowed}
                reason={perm.reason}
              />
            );
          })}
        </div>
      )}

    </div>
  );
}

function ApprovalCard({
  action,
  onApprove,
  onDeny,
  busy,
  canAct,
  reason,
}: {
  action: PendingAction;
  onApprove: () => void;
  onDeny: () => void;
  busy: boolean;
  canAct: boolean;
  reason: string;
}) {
  const reasons = action.governance.reasons || [];
  const blastRadius = action.governance.blast_radius;
  const isHighBlast = blastRadius > 20;

  return (
    <div className="rounded-xl border border-ks-border bg-ks-surface shadow-sm hover:border-ks-border-sub transition-colors overflow-hidden">
      <div className="p-5">
        <div className="flex items-start justify-between gap-4 mb-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <Link
                href={`/actions/${action.action_id}`}
                className="text-[13px] font-mono font-semibold text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1"
              >
                {action.action_id}
                <ExternalLink className="w-3 h-3" />
              </Link>
              <Badge color="violet">APPROVAL_REQUIRED</Badge>
              {isHighBlast && (
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 border border-amber-500/30">
                  <AlertTriangle className="w-3 h-3" />
                  High blast radius
                </span>
              )}
            </div>
            <div className="mt-1 text-sm font-semibold text-ks-text">
              {action.tool} · {action.action_type}
            </div>
            <div className="text-[11px] text-ks-text3 mt-0.5 flex items-center gap-2 flex-wrap">
              <span>Agent: <span className="text-ks-text2">{action.agent.name || action.agent.id || "—"}</span></span>
              {action.workspace_name && (
                <>
                  <span>·</span>
                  <Link href={`/workspaces/${action.workspace_id}`} className="text-ks-text2 hover:text-ks-primary transition-colors">
                    {action.workspace_name}
                  </Link>
                </>
              )}
              <span>·</span>
              <span className="font-mono">{timeAgo(action.timestamp.replace("Z", ""))}</span>
            </div>
          </div>

          <div className="text-right shrink-0">
            <div className="text-3xl font-bold tabular-nums text-ks-text">{blastRadius}</div>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">
              records affected
            </div>
          </div>
        </div>

        {reasons.length > 0 && (
          <div className="bg-ks-surface-2 border border-ks-border rounded-lg px-3 py-2 mb-4">
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest mb-1.5">
              Policy reasons
            </div>
            <ul className="space-y-1">
              {reasons.slice(0, 3).map((r, i) => {
                const text = typeof r === "string" ? r : (r.reason || r.rule || JSON.stringify(r));
                return (
                  <li key={i} className="text-[12px] text-ks-text2 flex items-start gap-1.5">
                    <span className="text-ks-text3 font-mono text-[10px] mt-0.5">{String(i + 1).padStart(2, "0")}</span>
                    <span>{text}</span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="text-[11px] text-ks-text3">
            Policy: <span className="font-mono text-ks-text2">{action.governance.policy_id}</span>
            {action.governance.policy_version && <span> v{action.governance.policy_version}</span>}
          </div>
          <div className="flex items-center gap-2">
            {!canAct && (
              <span
                className="text-[11px] text-amber-600 dark:text-amber-500 bg-amber-500/10 border border-amber-500/30 rounded px-2 py-1"
                title={reason}
              >
                {reason}
              </span>
            )}
            <button
              onClick={onDeny}
              disabled={busy || !canAct}
              title={!canAct ? reason : "Deny"}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-ks-surface-2 border border-ks-border rounded text-xs font-medium text-red-500 hover:bg-red-500/10 hover:border-red-500/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-ks-surface-2 disabled:hover:border-ks-border"
            >
              <XCircle className="w-3.5 h-3.5" />
              Deny
            </button>
            <button
              onClick={onApprove}
              disabled={busy || !canAct}
              title={!canAct ? reason : "Approve"}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-emerald-500 border border-emerald-500 rounded text-xs font-medium text-white hover:bg-emerald-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:bg-zinc-400 disabled:border-zinc-400 disabled:hover:bg-zinc-400"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              {busy ? "Processing…" : "Approve & Execute"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  color,
}: {
  label: string;
  value: number;
  sub?: string;
  icon?: React.ComponentType<{ className?: string }>;
  color?: string;
}) {
  const colorClass =
    color === "violet" ? "text-violet-500" :
    color === "amber" ? "text-amber-500" : "text-ks-text";
  return (
    <div className="bg-ks-surface/50 border border-ks-border rounded-xl p-5">
      <div className="flex items-start justify-between mb-1">
        <div className={`text-3xl font-bold tabular-nums ${colorClass}`}>{value}</div>
        {Icon && <Icon className="w-5 h-5 text-ks-text3" />}
      </div>
      <div className="text-[12px] font-bold text-ks-text3 uppercase tracking-widest mt-1">{label}</div>
      {sub && <div className="text-[11px] text-ks-text3 mt-1">{sub}</div>}
    </div>
  );
}
