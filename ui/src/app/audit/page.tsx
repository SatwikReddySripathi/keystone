"use client";

import { useCallback, useState } from "react";
import { Search, Filter, Download, FileSearch, ArrowRight, ShieldCheck, CheckCircle2, Cloud } from "lucide-react";
import { Badge, timeAgo } from "@/lib/components";
import Link from "next/link";
import { motion } from "framer-motion";
import { fetchAuditList, downloadAuditExport } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAutoRefresh, RefreshControl } from "@/lib/useAutoRefresh";

type AuditEntry = {
  action_id: string;
  timestamp: string;
  status: string;
  tool: string;
  action_type: string;
  mode: string;
  environment: string;
  workspace_id: string | null;
  workspace_name: string | null;
  client_ip: string | null;
  agent: { id: string | null; name: string | null; type: string | null };
  governance: {
    decision: string | null;
    policy_id: string | null;
    policy_version: string | null;
    reasons: unknown[];
    blast_radius: number;
  };
  approver: { id: string; name: string; designation: string; department: string; channel: string | null; approved_at: string | null } | null;
  objects_touched: string[];
  proof_signature: string | null;
};

export default function AuditTrailPage() {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [downloading, setDownloading] = useState<"csv" | "json" | null>(null);
  const { me, canSeeWorkspace } = useAuth();

  const load = useCallback(async () => {
    try {
      const data = await fetchAuditList();
      setEntries(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  }, []);

  const { refreshing, lastUpdatedAt, paused, togglePause, refresh } = useAutoRefresh(load, 5000);

  async function handleExport(kind: "csv" | "json") {
    setDownloading(kind);
    try {
      await downloadAuditExport(kind);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Export failed");
    } finally {
      setDownloading(null);
    }
  }

  const scoped = (entries || []).filter((e) => {
    if (!me) return false;
    if (me.is_admin) return true;
    return canSeeWorkspace(e.workspace_id);
  });

  const filtered = scoped.filter((e) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      e.action_id.toLowerCase().includes(q) ||
      (e.agent.name || e.agent.id || "").toLowerCase().includes(q) ||
      e.action_type.toLowerCase().includes(q) ||
      e.tool.toLowerCase().includes(q)
    );
  });

  return (
    <div className="animate-in fade-in duration-500 pb-16 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ks-text">Execution Audit Trail</h1>
          <p className="text-[13px] text-ks-text2 mt-1.5 max-w-2xl leading-relaxed">
            Immutable ledger of all agent executions across connected systems.
            Export cryptographically signed receipts for compliance and security reviews.
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <RefreshControl
            refreshing={refreshing}
            lastUpdatedAt={lastUpdatedAt}
            paused={paused}
            togglePause={togglePause}
            refresh={refresh}
            intervalLabel="5s"
          />
          <button className="flex items-center gap-2 px-4 py-2 bg-ks-surface border border-ks-border rounded-lg text-sm font-medium text-ks-text hover:bg-ks-hover transition-colors shadow-sm">
            <Filter className="w-4 h-4" />
            Date Range
          </button>
          <button
            onClick={() => handleExport("csv")}
            disabled={downloading !== null}
            className="flex items-center gap-2 px-4 py-2 bg-ks-surface border border-ks-border rounded-lg text-sm font-medium text-ks-text hover:bg-ks-hover transition-colors shadow-sm disabled:opacity-50"
          >
            <Download className="w-4 h-4" />
            {downloading === "csv" ? "Exporting…" : "Export CSV"}
          </button>
          <button
            onClick={() => handleExport("json")}
            disabled={downloading !== null}
            className="flex items-center gap-2 px-4 py-2 bg-ks-primary border border-ks-primary rounded-lg text-sm font-medium text-white shadow-[0_0_15px_rgba(79,70,229,0.3)] hover:shadow-[0_0_20px_rgba(79,70,229,0.5)] transition-all disabled:opacity-50"
          >
            <FileSearch className="w-4 h-4" />
            {downloading === "json" ? "Exporting…" : "Export JSON Proofs"}
          </button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between mb-4 p-1 bg-ks-surface-2/50 backdrop-blur-sm rounded-lg border border-ks-border">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ks-text3" />
          <input
            type="text"
            placeholder="Search by Run ID, Agent, or Action..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-transparent border-none focus:ring-0 text-sm text-ks-text pl-9 py-2 placeholder:text-ks-text3 outline-none"
          />
        </div>
        <div className="px-3 border-l border-ks-border/50 text-[11px] font-mono text-ks-text3 uppercase tracking-wider">
          {filtered.length} Records
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-500 mb-6">
          {error}
        </div>
      )}

      {!entries && !error && (
        <div className="rounded-xl border border-ks-border bg-ks-surface shadow-sm overflow-hidden">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-20 border-b border-ks-border/50 animate-pulse bg-ks-surface-2/40" />
          ))}
        </div>
      )}

      {entries && (
        <div className="rounded-xl border border-ks-border bg-ks-surface shadow-sm overflow-hidden backdrop-blur-md">
          <div
            className="grid gap-4 px-6 py-3 border-b border-ks-border bg-ks-surface-2/80"
            style={{ gridTemplateColumns: "100px 1.5fr 1fr 1fr 120px 100px 24px" }}
          >
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Timestamp</div>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Run ID & Agent</div>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Target System</div>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Policy & Decision</div>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Approver</div>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Status</div>
            <div />
          </div>

          <div className="divide-y divide-ks-border/50">
            {filtered.map((e, i) => {
              const modeBadge = e.mode === "observe_only" ? "OBSERVED" : e.governance.decision || "—";
              const statusLabel = e.status === "completed" ? "PASSED" : e.status.toUpperCase();
              const statusColor =
                e.status === "completed" ? "green" :
                e.status === "contained" ? "amber" :
                e.status === "blocked" ? "red" :
                e.status === "awaiting_approval" ? "violet" : "gray";

              return (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.03 }}
                  key={e.action_id}
                >
                  <Link
                    href={`/audit/${e.action_id}`}
                    className="grid gap-4 px-6 py-4 items-center group hover:bg-ks-hover/80 transition-colors"
                    style={{ gridTemplateColumns: "100px 1.5fr 1fr 1fr 120px 100px 24px" }}
                  >
                    <div className="text-[11px] font-mono text-ks-text2">
                      {timeAgo(e.timestamp.replace("Z", ""))}
                    </div>

                    <div className="min-w-0">
                      <div className="text-[13px] font-mono font-bold text-ks-text group-hover:text-ks-primary transition-colors flex items-center gap-2">
                        <FileSearch className="w-3.5 h-3.5 text-ks-text3" />
                        {e.action_id}
                      </div>
                      <div className="text-[12px] text-ks-text3 truncate mt-0.5">
                        Agent: <span className="text-ks-text2">{e.agent.name || e.agent.id || "—"}</span>
                      </div>
                      {e.workspace_name && (
                        <div className="text-[10px] text-ks-text3 truncate mt-0.5 uppercase tracking-wider">
                          {e.workspace_name}
                        </div>
                      )}
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 text-[13px] font-semibold text-ks-text truncate">
                        <Cloud className="w-3.5 h-3.5 text-ks-text3" />
                        {e.tool}
                      </div>
                      <div className="text-[11px] font-mono text-ks-text3 mt-0.5 truncate bg-ks-surface-2 px-1.5 py-0.5 rounded inline-block">
                        {e.action_type}
                      </div>
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 text-[12px] text-ks-text2 truncate mb-1">
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                        {e.governance.policy_id || "—"}
                        {e.governance.policy_version && (
                          <span className="font-mono text-[10px] text-ks-text3">v{e.governance.policy_version}</span>
                        )}
                      </div>
                      <Badge color={modeBadge === "CANARY" ? "amber" : modeBadge === "OBSERVED" ? "sky" : modeBadge === "BLOCK" ? "red" : modeBadge === "APPROVAL_REQUIRED" ? "violet" : "gray"}>
                        {modeBadge}
                      </Badge>
                    </div>

                    <div className="text-[11px] text-ks-text2 truncate">
                      {e.approver ? (
                        <div>
                          <div className="text-ks-text">{e.approver.name}</div>
                          <div className="text-[10px] text-ks-text3 truncate">{e.approver.designation}</div>
                        </div>
                      ) : (
                        <span className="flex items-center gap-1 text-emerald-500">
                          <CheckCircle2 className="w-3 h-3" /> Auto
                        </span>
                      )}
                    </div>

                    <div>
                      <Badge color={statusColor}>{statusLabel}</Badge>
                    </div>

                    <div className="flex justify-end">
                      <ArrowRight className="w-4 h-4 text-ks-text3 group-hover:text-ks-primary group-hover:translate-x-1 transition-transform" />
                    </div>
                  </Link>
                </motion.div>
              );
            })}
            {filtered.length === 0 && (
              <div className="px-6 py-16 text-center text-sm text-ks-text3">
                No entries match your search.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
