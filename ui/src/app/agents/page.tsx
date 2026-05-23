"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Search, Box, ArrowRight, User, PauseCircle, XCircle, CheckCircle2 } from "lucide-react";
import { Badge, timeAgo } from "@/lib/components";
import { fetchAgents } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAutoRefresh, RefreshControl } from "@/lib/useAutoRefresh";

type Agent = {
  agent_id: string;
  name: string;
  description: string | null;
  workspace_id: string | null;
  workspace_name: string | null;
  status: string;
  permissions: { tools?: string[]; action_types?: string[] };
  rate_limit_per_hour: number | null;
  last_used_at: string | null;
  owner: { name: string; designation: string; department: string; email: string } | null;
  total_runs: number;
  last_run_at: string | null;
};

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const { me, canSeeWorkspace } = useAuth();

  const load = useCallback(async () => {
    try {
      setAgents(await fetchAgents());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  }, []);

  const { refreshing, lastUpdatedAt, paused, togglePause, refresh } = useAutoRefresh(load, 10000);

  // Non-admins: only see agents in their workspaces OR agents they own
  const scoped = (agents || []).filter((a) => {
    if (!me) return false;
    if (me.is_admin) return true;
    if (canSeeWorkspace(a.workspace_id)) return true;
    if (me.owned_agents.some(oa => oa.agent_id === a.agent_id)) return true;
    return false;
  });

  const filtered = scoped.filter((a) => {
    if (statusFilter !== "all" && a.status !== statusFilter) return false;
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      a.agent_id.toLowerCase().includes(q) ||
      a.name.toLowerCase().includes(q) ||
      (a.workspace_name || "").toLowerCase().includes(q) ||
      (a.owner?.name || "").toLowerCase().includes(q)
    );
  });

  const stats = scoped.reduce(
    (acc, a) => {
      acc.total++;
      if (a.status === "active") acc.active++;
      if (a.status === "paused") acc.paused++;
      if (a.status === "revoked") acc.revoked++;
      if (a.status === "pending_registration") acc.pending++;
      return acc;
    },
    { total: 0, active: 0, paused: 0, revoked: 0, pending: 0 }
  );

  return (
    <div className="animate-in fade-in duration-500 pb-16 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ks-text">Agents</h1>
          <p className="text-[13px] text-ks-text2 mt-1.5 max-w-2xl leading-relaxed">
            Registered AI agents authorized to propose actions through Keystone.
            Each agent has an owner, permissions, and a rate limit that governs what it can do.
          </p>
        </div>
        <RefreshControl
          refreshing={refreshing}
          lastUpdatedAt={lastUpdatedAt}
          paused={paused}
          togglePause={togglePause}
          refresh={refresh}
          intervalLabel="10s"
        />
      </div>

      {/* Pending registration banner — visible when any agents need admin review */}
      {stats.pending > 0 && (
        <div className="mb-6 flex items-center justify-between rounded-xl border border-violet-500/30 bg-violet-500/5 px-5 py-3.5">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-violet-500/15 border border-violet-500/30 flex items-center justify-center">
              <Box className="w-4 h-4 text-violet-500" />
            </div>
            <div>
              <div className="text-sm font-semibold text-ks-text">
                {stats.pending} agent{stats.pending !== 1 ? "s" : ""} waiting for registration
              </div>
              <div className="text-[11px] text-ks-text3 mt-0.5">
                Auto-discovered from the SDK. Assign a workspace, owner, and permissions to activate them.
              </div>
            </div>
          </div>
          <button
            onClick={() => setStatusFilter("pending_registration")}
            className="text-[11px] font-semibold px-3 py-1.5 rounded bg-violet-500 text-white hover:opacity-90 transition-opacity"
          >
            Review
          </button>
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-5 gap-4 mb-8">
        <StatCard label="Total Agents" value={stats.total} />
        <StatCard label="Active" value={stats.active} color="emerald" />
        <StatCard label="Needs Registration" value={stats.pending} color="violet" />
        <StatCard label="Paused" value={stats.paused} color="amber" />
        <StatCard label="Revoked" value={stats.revoked} color="red" />
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between mb-4 p-1 bg-ks-surface-2/50 backdrop-blur-sm rounded-lg border border-ks-border">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ks-text3" />
          <input
            type="text"
            placeholder="Search by agent ID, name, workspace, or owner..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-transparent border-none focus:ring-0 text-sm text-ks-text pl-9 py-2 placeholder:text-ks-text3 outline-none"
          />
        </div>
        <div className="flex items-center gap-1 px-2">
          {(["all", "active", "pending_registration", "paused", "revoked"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                statusFilter === s
                  ? "bg-ks-surface border border-ks-border text-ks-text"
                  : "text-ks-text3 hover:text-ks-text"
              }`}
            >
              {s === "pending_registration" ? "Pending" : s[0].toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
        <div className="px-3 border-l border-ks-border/50 text-[11px] font-mono text-ks-text3 uppercase tracking-wider">
          {filtered.length} Shown
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-500 mb-6">
          {error}
        </div>
      )}

      {!agents && !error && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-44 rounded-xl border border-ks-border bg-ks-surface/40 animate-pulse" />
          ))}
        </div>
      )}

      {agents && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filtered.map((a, i) => {
            const statusIcon =
              a.status === "active" ? <CheckCircle2 className="w-3 h-3" /> :
              a.status === "paused" ? <PauseCircle className="w-3 h-3" /> :
              a.status === "pending_registration" ? <Box className="w-3 h-3" /> :
              <XCircle className="w-3 h-3" />;
            const statusColor =
              a.status === "active" ? "green" :
              a.status === "paused" ? "amber" :
              a.status === "pending_registration" ? "violet" :
              "red";
            const statusLabel = a.status === "pending_registration" ? "needs registration" : a.status;

            return (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                key={a.agent_id}
              >
                <Link
                  href={`/agents/${a.agent_id}`}
                  className="block rounded-xl border border-ks-border bg-ks-surface/50 hover:bg-ks-hover/40 hover:border-ks-border-sub transition-all p-5 group"
                >
                  {/* Top row */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-start gap-3 min-w-0">
                      <div className="w-10 h-10 rounded-lg bg-ks-surface-2 border border-ks-border flex items-center justify-center shrink-0 group-hover:border-ks-primary/50 transition-colors">
                        <Box className="w-5 h-5 text-ks-text2 group-hover:text-ks-primary" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-base font-semibold text-ks-text truncate group-hover:text-ks-primary transition-colors">
                          {a.name}
                        </div>
                        <div className="text-[11px] font-mono text-ks-text3 mt-0.5 truncate">
                          {a.agent_id}
                        </div>
                      </div>
                    </div>
                    <span title={statusLabel}>
                      <Badge color={statusColor} className="gap-1 shrink-0">
                        {statusIcon}
                        {statusLabel}
                      </Badge>
                    </span>
                  </div>

                  {a.description && (
                    <p className="text-[12px] text-ks-text2 mb-4 line-clamp-2">{a.description}</p>
                  )}

                  {/* Owner + workspace */}
                  <div className="flex items-center gap-4 mb-4 text-[11px] text-ks-text3">
                    {a.owner && (
                      <div className="flex items-center gap-1.5 min-w-0">
                        <User className="w-3.5 h-3.5" />
                        <span className="truncate">{a.owner.name}</span>
                      </div>
                    )}
                    {a.workspace_name && (
                      <div className="min-w-0 truncate">
                        · {a.workspace_name}
                      </div>
                    )}
                  </div>

                  {/* Metrics grid */}
                  <div className="grid grid-cols-3 gap-3 py-3 border-t border-ks-border/50">
                    <div>
                      <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest mb-1">Tools</div>
                      <div className="flex flex-wrap gap-1">
                        {(a.permissions.tools || []).slice(0, 3).map((t) => (
                          <span
                            key={t}
                            className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-ks-surface-2 text-ks-text2 border border-ks-border"
                          >
                            {t}
                          </span>
                        ))}
                        {(a.permissions.tools || []).length === 0 && (
                          <span className="text-[10px] text-ks-text3 italic">all</span>
                        )}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest mb-1">Runs</div>
                      <div className="text-[13px] font-bold text-ks-text tabular-nums">{a.total_runs}</div>
                    </div>
                    <div>
                      <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest mb-1">Rate Limit</div>
                      <div className="text-[13px] font-bold text-ks-text tabular-nums">
                        {a.rate_limit_per_hour ? `${a.rate_limit_per_hour}/hr` : "—"}
                      </div>
                    </div>
                  </div>

                  {/* Last used + arrow */}
                  <div className="flex justify-between items-center mt-3 text-[11px] text-ks-text3">
                    <span>
                      {a.last_run_at
                        ? <>Last run <span className="font-mono">{timeAgo(a.last_run_at.replace("Z", ""))}</span></>
                        : "No runs yet"}
                    </span>
                    <ArrowRight className="w-4 h-4 group-hover:text-ks-primary group-hover:translate-x-1 transition-all" />
                  </div>
                </Link>
              </motion.div>
            );
          })}
          {filtered.length === 0 && (
            <div className="col-span-full px-6 py-16 text-center text-sm text-ks-text3 border border-ks-border rounded-xl bg-ks-surface/40">
              No agents match your filter.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color?: string }) {
  const colorClass =
    color === "emerald" ? "text-emerald-500" :
    color === "amber" ? "text-amber-500" :
    color === "red" ? "text-red-500" : "text-ks-text";
  return (
    <div className="bg-ks-surface/50 border border-ks-border rounded-xl p-5">
      <div className={`text-3xl font-bold tabular-nums ${colorClass}`}>{value}</div>
      <div className="text-[12px] font-bold text-ks-text3 uppercase tracking-widest mt-1">{label}</div>
    </div>
  );
}
