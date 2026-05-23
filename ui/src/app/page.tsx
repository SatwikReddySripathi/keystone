"use client";
import { useCallback, useEffect, useState, useMemo } from "react";
import { fetchActions, fetchStats } from "@/lib/api";
import { Badge, parseJson, timeAgo } from "@/lib/components";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronRight, Database, ShieldAlert, Zap, Box, Activity } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { useAutoRefresh, RefreshControl } from "@/lib/useAutoRefresh";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const STATUS_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
  completed:         { label: "Passed",          color: "green",  dot: "bg-emerald-500 shadow-[0_0_5px_rgba(16,185,129,0.8)]" },
  blocked:           { label: "Blocked",         color: "red",    dot: "bg-red-500 shadow-[0_0_5px_rgba(239,68,68,0.8)]" },
  contained:         { label: "Contained",       color: "amber",  dot: "bg-amber-500 shadow-[0_0_5px_rgba(245,158,11,0.8)]" },
  observed:          { label: "Dry Run",         color: "sky",    dot: "bg-sky-500 shadow-[0_0_5px_rgba(14,165,233,0.8)]" },
  awaiting_approval: { label: "Pending Review",  color: "violet", dot: "bg-violet-500 shadow-[0_0_5px_rgba(139,92,246,0.8)] animate-pulse" },
  approved:          { label: "Approved",        color: "green",  dot: "bg-emerald-500 shadow-[0_0_5px_rgba(16,185,129,0.8)]" },
  pending:           { label: "Pending",         color: "gray",   dot: "bg-zinc-400" },
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
  const [filter, setFilter] = useState("all");

  const load = useCallback(async () => {
    const [a] = await Promise.all([
      fetchActions().then((a) => { setActions(a); return a; }),
      fetchStats().then(setStats).catch(() => setStats(null)),
    ]);
    return a;
  }, []);

  // Fast tick (2s) while any action is live; regular tick (5s) otherwise.
  // The hook decides visibility-awareness; we just pick a sensible cadence.
  const hasLive = actions.some((x: any) => LIVE_STATUSES.has(x.status));
  const interval = hasLive ? 2000 : 5000;
  const { loading, refreshing, lastUpdatedAt, paused, togglePause, refresh } = useAutoRefresh(load, interval);

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
    <div className="animate-in fade-in duration-500 pb-16">
      {/* Page header */}
      <div className="mb-8 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-ks-text">Transaction Ledgers</h1>
          <p className="text-[13px] text-ks-text2 mt-1 max-w-2xl">
            Real-time oversight of all AI agent operations. Every action is intercepted, evaluated against policy, and governed before touching production systems.
          </p>
        </div>
        <RefreshControl
          refreshing={refreshing}
          lastUpdatedAt={lastUpdatedAt}
          paused={paused}
          togglePause={togglePause}
          refresh={refresh}
          intervalLabel={hasLive ? "2s" : "5s"}
        />
      </div>

      {/* Stats strip */}
      {hasStats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          {[
            { n: stats.total_actions,     label: "Total Operations", sub: "all time",         color: "text-ks-text",           icon: Database },
            { n: stats.completed,         label: "Passed cleanly",   sub: "executed safely",  color: "text-emerald-500",       icon: Zap },
            { n: stats.blocked,           label: "Blocked",          sub: "policy prevented", color: "text-red-500",           icon: ShieldAlert },
            { n: stats.awaiting_approval, label: "Pending Review",   sub: "need approval",    color: "text-violet-500",        icon: Activity },
          ].map((s, i) => (
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              key={i} 
              className="relative overflow-hidden rounded-xl border border-ks-border bg-ks-surface/50 backdrop-blur-sm p-5 shadow-sm group hover:border-ks-border-sub transition-colors"
            >
              <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-transparent via-ks-border to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="flex justify-between items-start mb-2">
                <div className={cn("text-3xl font-bold tracking-tighter tabular-nums", s.color)}>{s.n}</div>
                <s.icon className={cn("w-5 h-5 opacity-50", s.color)} />
              </div>
              <div className="text-[13px] font-semibold text-ks-text">{s.label}</div>
              <div className="text-[11px] font-mono text-ks-text3 mt-1 uppercase tracking-wider">{s.sub}</div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Operational metrics row */}
      {hasStats && (
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3 mb-8 px-2 py-3 bg-ks-surface-2/30 rounded-lg border border-ks-border/50 text-[11px] font-mono uppercase tracking-wider">
          <div className="flex items-center gap-2 text-ks-text2">
            <Activity className="w-3.5 h-3.5 text-ks-primary" />
            System Metrics
          </div>
          {[
            { n: stats.records_governed?.toLocaleString(),  label: "Instances Governed" },
            { n: stats.records_protected?.toLocaleString(), label: "Instances Protected" },
            { n: stats.breaker_trips,                       label: "Breaker Trips", color: "text-red-500" },
            { n: stats.last_24h_actions,                    label: "Last 24h" },
            { n: stats.contained,                           label: "Contained", color: "text-amber-500" },
          ].map((s, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="text-ks-border/50">|</span>
              <span className={cn("font-bold text-ks-text tabular-nums", s.color)}>{s.n}</span>
              <span className="text-ks-text3">{s.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Filter tabs */}
      {actions.length > 0 && (
        <div className="flex items-center gap-1 mb-6 p-1 bg-ks-surface-2/50 backdrop-blur-sm rounded-lg border border-ks-border inline-flex">
          {FILTER_TABS.map(tab => {
            const count = tabCounts[tab.key] || 0;
            if (tab.key !== "all" && count === 0) return null;
            const active = filter === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setFilter(tab.key)}
                className={cn(
                  "relative flex items-center gap-2 px-4 py-1.5 rounded-md text-[13px] font-medium transition-colors z-10",
                  active ? "text-ks-text" : "text-ks-text2 hover:text-ks-text hover:bg-ks-surface/50"
                )}
              >
                {active && (
                  <motion.div
                    layoutId="activeTab"
                    className="absolute inset-0 bg-ks-surface rounded-md border border-ks-border shadow-sm -z-10"
                    transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                  />
                )}
                {tab.label}
                <span className={cn(
                  "px-1.5 py-0.5 rounded font-mono text-[10px] tabular-nums transition-colors",
                  active ? "bg-ks-primary/10 text-ks-primary" : "bg-ks-border/50 text-ks-text3"
                )}>
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
        <div className="py-24 text-center border border-ks-border border-dashed rounded-xl bg-ks-surface-2/30">
          <p className="text-ks-text2 text-sm font-medium">No {FILTER_TABS.find(t => t.key === filter)?.label.toLowerCase()} transactions.</p>
        </div>
      ) : (
        <div className="rounded-xl border border-ks-border bg-ks-surface shadow-sm overflow-hidden backdrop-blur-md">
          {/* Column headers */}
          <div className="grid gap-4 px-6 py-3 border-b border-ks-border bg-ks-surface-2/80"
            style={{ gridTemplateColumns: "1.5fr 140px 180px 100px 24px" }}>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Transaction Signature</div>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Status</div>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Executing Agent</div>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest text-right">Timestamp</div>
            <div />
          </div>

          {/* Rows */}
          <div className="divide-y divide-ks-border/50">
            <AnimatePresence initial={false}>
              {filtered.map((a: any) => {
                const st = STATUS_CONFIG[a.status] || STATUS_CONFIG.pending;
                const actor = parseJson(a.actor_json);
                return (
                  <motion.div
                    layout
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    key={a.action_id}
                  >
                    <Link
                      href={`/actions/${a.action_id}`}
                      className="grid gap-4 px-6 py-4 items-center group hover:bg-ks-hover/80 transition-colors"
                      style={{ gridTemplateColumns: "1.5fr 140px 180px 100px 24px" }}
                    >
                      {/* Transaction name + ID */}
                      <div className="flex items-center gap-4 min-w-0">
                        <div className="relative flex items-center justify-center">
                          <span className={cn("w-2 h-2 rounded-full z-10", st.dot)} />
                          {st.dot.includes("pulse") && (
                            <span className={cn("absolute w-4 h-4 rounded-full opacity-30 animate-ping", st.dot)} />
                          )}
                        </div>
                        <div className="min-w-0">
                          <span className="text-[14px] font-semibold text-ks-text truncate block group-hover:text-ks-primary transition-colors">
                            {a.tool}.{a.action_type}
                          </span>
                          <span className="text-[11px] font-mono text-ks-text3 truncate block mt-0.5 group-hover:text-ks-text2 transition-colors">
                            id_{a.action_id.slice(0, 16)}…
                          </span>
                        </div>
                      </div>

                      {/* Status badge */}
                      <div>
                        <Badge color={st.color}>{st.label}</Badge>
                      </div>

                      {/* Agent */}
                      <div className="flex items-center gap-2 min-w-0">
                        <div className="w-6 h-6 rounded bg-ks-surface-2 border border-ks-border flex items-center justify-center shrink-0">
                          <Box className="w-3.5 h-3.5 text-ks-text2" />
                        </div>
                        <div className="truncate">
                          <div className="text-[13px] font-medium text-ks-text truncate">
                            {actor?.name || "Unknown Agent"}
                          </div>
                          {actor?.type && (
                            <div className="text-[10px] font-mono text-ks-text3 truncate mt-0.5">
                              {actor.type}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Time */}
                      <div className="text-[12px] text-ks-text3 text-right font-mono tracking-tight">
                        {timeAgo(a.created_at)}
                      </div>

                      {/* Chevron */}
                      <div className="flex justify-end">
                        <ChevronRight className="w-4 h-4 text-ks-text3 group-hover:text-ks-primary group-hover:translate-x-1 transition-all" />
                      </div>
                    </Link>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        </div>
      )}

      {/* Auto-refresh notice — only when actively polling pending/live actions */}
      {actions.length > 0 && actions.some((a: any) => LIVE_STATUSES.has(a.status)) && (
        <div className="mt-6 flex items-center justify-center gap-2 text-[10px] text-ks-text3 font-mono uppercase tracking-widest">
          <Activity className="w-3 h-3 text-emerald-500 animate-pulse" />
          Auto-refreshing · {actions.filter((a: any) => LIVE_STATUSES.has(a.status)).length} live
        </div>
      )}
    </div>
  );
}

function SkeletonRows() {
  return (
    <div className="rounded-xl border border-ks-border bg-ks-surface shadow-sm overflow-hidden">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="flex items-center gap-6 px-6 py-4 border-b border-ks-border/50 last:border-0">
          <div className="w-2 h-2 rounded-full bg-ks-border shrink-0 animate-pulse" />
          <div className="space-y-2 flex-1">
            <div className="h-4 bg-ks-surface-2 rounded w-48 animate-pulse" />
            <div className="h-3 bg-ks-surface-2 rounded w-32 animate-pulse" />
          </div>
          <div className="h-6 bg-ks-surface-2 rounded-full w-24 animate-pulse" />
          <div className="h-8 bg-ks-surface-2 rounded w-32 animate-pulse" />
          <div className="h-3 bg-ks-surface-2 rounded w-16 animate-pulse" />
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-xl border border-dashed border-ks-border bg-ks-surface-2/30 py-24 text-center">
      <div className="w-12 h-12 rounded-xl bg-ks-surface border border-ks-border flex items-center justify-center mx-auto mb-4 shadow-sm relative">
        <Database className="w-6 h-6 text-ks-text3" />
        <div className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-emerald-500 border-2 border-ks-surface animate-ping opacity-75" />
      </div>
      <h3 className="text-base font-semibold text-ks-text mb-1 tracking-tight">No governance records yet</h3>
      <p className="text-[13px] text-ks-text2 mb-6 max-w-sm mx-auto">
        Waiting for AI agents to initiate actions. Run the demo script to simulate traffic.
      </p>
      <div className="inline-block bg-ks-surface border border-ks-border px-4 py-2 rounded-lg shadow-sm">
        <code className="text-xs font-mono text-ks-text">
          <span className="text-ks-primary select-none">$ </span>
          cd sdk && python demo.py
        </code>
      </div>
    </div>
  );
}
