"use client";
import { useEffect, useState, useMemo } from "react";
import { fetchActions, fetchStats } from "@/lib/api";
import { Badge, parseJson, timeAgo } from "@/lib/components";
import Link from "next/link";

const STATUS_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
  completed:         { label: "Passed",         color: "green",  dot: "bg-emerald-500" },
  blocked:           { label: "Blocked",         color: "red",    dot: "bg-red-500" },
  contained:         { label: "Contained",       color: "amber",  dot: "bg-amber-500" },
  observed:          { label: "Dry Run",         color: "sky",    dot: "bg-sky-500" },
  awaiting_approval: { label: "Pending Review",  color: "violet", dot: "bg-violet-500" },
  approved:          { label: "Approved",        color: "green",  dot: "bg-emerald-500" },
  pending:           { label: "Pending",         color: "gray",   dot: "bg-gray-400" },
};

const FILTER_TABS = [
  { key: "all",               label: "All" },
  { key: "completed",         label: "Passed" },
  { key: "blocked",           label: "Blocked" },
  { key: "contained",         label: "Contained" },
  { key: "awaiting_approval", label: "Pending" },
  { key: "observed",          label: "Dry Run" },
];

const LIVE_STATUSES = new Set(["awaiting_approval", "approved", "canary_executing", "expanding"]);

export default function ActionsPage() {
  const [actions, setActions] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  const load = () => {
    setLoading(true);
    return Promise.all([
      fetchActions().then(setActions),
      fetchStats().then(setStats).catch(() => setStats(null)),
    ]).finally(() => setLoading(false));
  };

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    const poll = () => {
      Promise.all([
        fetchActions().then(a => { setActions(a); return a; }),
        fetchStats().then(setStats).catch(() => {}),
      ]).then(([a]) => {
        const hasLive = a.some((x: any) => LIVE_STATUSES.has(x.status));
        if (!hasLive && timer) { clearInterval(timer); timer = null; }
      });
    };
    load().then(() => { timer = setInterval(poll, 2000); });
    return () => { if (timer) clearInterval(timer); };
  }, []);

  const filtered = useMemo(() =>
    filter === "all" ? actions : actions.filter(a => a.status === filter),
    [actions, filter]
  );

  const tabCounts = useMemo(() => {
    const counts: Record<string, number> = { all: actions.length };
    for (const a of actions) {
      counts[a.status] = (counts[a.status] || 0) + 1;
    }
    return counts;
  }, [actions]);

  const hasStats = stats && stats.total_actions > 0;

  return (
    <div>
      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-base font-semibold text-ks-text">Transactions</h1>
        <p className="text-sm text-ks-text2 mt-0.5">
          Every AI agent action intercepted, policy-evaluated, and governed before reaching your systems.
        </p>
      </div>

      {/* Stats strip */}
      {hasStats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          {[
            { n: stats.total_actions,     label: "Total",          sub: "all time",           color: "text-ks-text" },
            { n: stats.completed,         label: "Passed",         sub: "executed cleanly",   color: "text-emerald-600 dark:text-emerald-400" },
            { n: stats.blocked,           label: "Blocked",        sub: "policy prevented",   color: "text-red-600 dark:text-red-400" },
            { n: stats.awaiting_approval, label: "Pending Review", sub: "need human approval",color: "text-violet-600 dark:text-violet-400" },
          ].map((s, i) => (
            <div key={i} className="rounded-lg border border-ks-border bg-ks-surface px-4 py-3 shadow-sm dark:shadow-none">
              <div className={`text-2xl font-bold tabular-nums ${s.color}`}>{s.n}</div>
              <div className="text-xs font-medium text-ks-text mt-0.5">{s.label}</div>
              <div className="text-[11px] text-ks-text3 mt-0.5">{s.sub}</div>
            </div>
          ))}
        </div>
      )}

      {/* Operational metrics row */}
      {hasStats && (
        <div className="flex flex-wrap gap-x-6 gap-y-1.5 mb-6 px-1">
          {[
            { n: stats.records_governed?.toLocaleString(),  label: "Operations Governed" },
            { n: stats.records_protected?.toLocaleString(), label: "Operations Protected" },
            { n: stats.breaker_trips,                       label: "Breaker Trips" },
            { n: stats.last_24h_actions,                    label: "Last 24 Hours" },
            { n: stats.contained,                           label: "Contained" },
          ].map((s, i) => (
            <div key={i} className="flex items-center gap-1.5 text-xs">
              <span className="font-semibold text-ks-text tabular-nums">{s.n}</span>
              <span className="text-ks-text3">{s.label}</span>
              {i < 4 && <span className="ml-4 text-ks-border hidden sm:inline">·</span>}
            </div>
          ))}
        </div>
      )}

      {/* Filter tabs */}
      {actions.length > 0 && (
        <div className="flex items-center gap-0.5 mb-4 border-b border-ks-border">
          {FILTER_TABS.map(tab => {
            const count = tabCounts[tab.key] || 0;
            if (tab.key !== "all" && count === 0) return null;
            const active = filter === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setFilter(tab.key)}
                className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors border-b-2 -mb-px ${
                  active
                    ? "border-indigo-600 dark:border-indigo-400 text-indigo-600 dark:text-indigo-400"
                    : "border-transparent text-ks-text2 hover:text-ks-text"
                }`}
              >
                {tab.label}
                <span className={`px-1.5 py-0.5 rounded text-[10px] tabular-nums ${
                  active
                    ? "bg-indigo-100 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400"
                    : "bg-ks-surface-2 text-ks-text3"
                }`}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* Table */}
      {loading ? (
        <SkeletonRows />
      ) : actions.length === 0 ? (
        <EmptyState />
      ) : filtered.length === 0 ? (
        <div className="py-16 text-center text-ks-text2 text-sm">
          No {FILTER_TABS.find(t => t.key === filter)?.label.toLowerCase()} transactions.
        </div>
      ) : (
        <div className="rounded-lg border border-ks-border bg-ks-surface shadow-sm dark:shadow-none overflow-hidden">
          {/* Column headers */}
          <div className="grid gap-0 px-4 py-2 border-b border-ks-border bg-ks-surface-2"
            style={{ gridTemplateColumns: "1fr 130px 170px 72px 20px" }}>
            <div className="text-[11px] font-semibold text-ks-text3 uppercase tracking-wider">Transaction</div>
            <div className="text-[11px] font-semibold text-ks-text3 uppercase tracking-wider">Status</div>
            <div className="text-[11px] font-semibold text-ks-text3 uppercase tracking-wider">Agent</div>
            <div className="text-[11px] font-semibold text-ks-text3 uppercase tracking-wider text-right">Time</div>
            <div />
          </div>

          {/* Rows */}
          {filtered.map((a: any) => {
            const st = STATUS_CONFIG[a.status] || STATUS_CONFIG.pending;
            const actor = parseJson(a.actor_json);
            return (
              <Link
                key={a.action_id}
                href={`/actions/${a.action_id}`}
                className={`grid gap-0 px-4 py-2.5 border-b border-ks-border last:border-0 hover:bg-ks-hover transition-colors items-center group`}
                style={{ gridTemplateColumns: "1fr 130px 170px 72px 20px" }}
              >
                {/* Transaction name + ID */}
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${st.dot}`} />
                  <div className="min-w-0">
                    <span className="text-sm font-medium text-ks-text truncate block">
                      {a.tool}.{a.action_type}
                    </span>
                    <span className="text-[10px] font-mono text-ks-text3 truncate block">
                      {a.action_id.slice(0, 16)}…
                    </span>
                  </div>
                </div>

                {/* Status badge */}
                <div>
                  <Badge color={st.color}>{st.label}</Badge>
                </div>

                {/* Agent */}
                <div className="text-xs text-ks-text2 truncate">
                  {actor?.name || "Unknown Agent"}
                  {actor?.type && <span className="text-ks-text3 ml-1">({actor.type})</span>}
                </div>

                {/* Time */}
                <div className="text-[11px] text-ks-text3 text-right tabular-nums">
                  {timeAgo(a.created_at)}
                </div>

                {/* Chevron */}
                <div className="text-ks-text3 text-sm text-right group-hover:text-ks-text2 transition-colors">›</div>
              </Link>
            );
          })}
        </div>
      )}

      {/* Auto-refresh notice */}
      {actions.length > 0 && (
        <p className="mt-4 text-center text-[11px] text-ks-text3">
          Auto-refreshing every 2 seconds
        </p>
      )}
    </div>
  );
}

function SkeletonRows() {
  return (
    <div className="rounded-lg border border-ks-border bg-ks-surface shadow-sm dark:shadow-none overflow-hidden">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="flex items-center gap-3 px-4 py-3 border-b border-ks-border last:border-0 animate-pulse">
          <div className="w-1.5 h-1.5 rounded-full bg-ks-border shrink-0" />
          <div className="h-3.5 bg-ks-border rounded w-48" />
          <div className="h-5 bg-ks-border rounded w-20 ml-auto" />
          <div className="h-3 bg-ks-border rounded w-24" />
          <div className="h-3 bg-ks-border rounded w-12" />
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-dashed border-ks-border bg-ks-surface py-16 text-center">
      <div className="w-8 h-8 rounded-lg bg-ks-surface-2 border border-ks-border flex items-center justify-center mx-auto mb-3">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-ks-text3">
          <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2" />
          <rect x="9" y="3" width="6" height="4" rx="1" />
          <path d="M9 12h6M9 16h4" />
        </svg>
      </div>
      <p className="text-sm font-medium text-ks-text mb-1">No transactions yet</p>
      <p className="text-xs text-ks-text2 mb-4">Run the demo script to see Keystone in action.</p>
      <code className="text-xs bg-ks-surface-2 border border-ks-border px-3 py-1.5 rounded font-mono text-ks-text2">
        python demo_real.py
      </code>
    </div>
  );
}
