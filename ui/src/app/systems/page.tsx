"use client";

import { useEffect, useState } from "react";
import { Search, Filter, ShieldAlert, CheckCircle2, Cloud, Settings2, Box } from "lucide-react";
import { Badge, timeAgo } from "@/lib/components";
import { motion } from "framer-motion";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { fetchConnections, createConnection } from "@/lib/api";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

type Connection = {
  connection_id: string;
  name: string;
  connector_type: string;
  workspace_id: string | null;
  workspace_name: string | null;
  environment: string;
  scopes: string[];
  risk_level: string;
  status: string;
  last_tested_at: string | null;
  created_at: string;
  active_agents: number;
  total_runs: number;
};

export default function ConnectedSystemsPage() {
  const [connections, setConnections] = useState<Connection[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);

  async function load() {
    try {
      setConnections(await fetchConnections());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }

  useEffect(() => { load(); }, []);

  async function handleConnect() {
    const name = window.prompt("System name (e.g., 'Production Jira')?");
    if (!name) return;
    const connectorType = window.prompt("Connector type (servicenow, jira, salesforce, aws_iam, slack, github, zendesk)?");
    if (!connectorType) return;
    const scopesStr = window.prompt("Scopes (comma-separated, optional)?", "read,write");
    const scopes = scopesStr ? scopesStr.split(",").map(s => s.trim()).filter(Boolean) : [];
    setCreating(true);
    try {
      await createConnection({ name, connector_type: connectorType, scopes });
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed");
    } finally {
      setCreating(false);
    }
  }

  const filtered = (connections || []).filter((c) => {
    const q = search.toLowerCase();
    return (
      c.name.toLowerCase().includes(q) ||
      (c.workspace_name || "").toLowerCase().includes(q) ||
      c.scopes.some((s) => s.toLowerCase().includes(q))
    );
  });

  return (
    <div className="animate-in fade-in duration-500 pb-16 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ks-text">Connected Systems</h1>
          <p className="text-[13px] text-ks-text2 mt-1.5 max-w-2xl leading-relaxed">
            Global directory of all SaaS platforms and internal tools connected to Action Marshall.
            Monitor scopes, audit agent access, and identify over-privileged or high-risk connections.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 px-4 py-2 bg-ks-surface border border-ks-border rounded-lg text-sm font-medium text-ks-text hover:bg-ks-hover transition-colors shadow-sm">
            <Filter className="w-4 h-4" />
            Advanced Filters
          </button>
          <button
            onClick={handleConnect}
            disabled={creating}
            className="flex items-center gap-2 px-4 py-2 bg-ks-primary border border-ks-primary rounded-lg text-sm font-medium text-white shadow-[0_0_15px_rgba(79,70,229,0.3)] hover:shadow-[0_0_20px_rgba(79,70,229,0.5)] transition-all disabled:opacity-50"
          >
            <Cloud className="w-4 h-4" />
            {creating ? "Connecting…" : "Connect System"}
          </button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between mb-4 p-1 bg-ks-surface-2/50 backdrop-blur-sm rounded-lg border border-ks-border">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ks-text3" />
          <input
            type="text"
            placeholder="Search systems, workspaces, or scopes..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-transparent border-none focus:ring-0 text-sm text-ks-text pl-9 py-2 placeholder:text-ks-text3 outline-none"
          />
        </div>
        <div className="px-3 border-l border-ks-border/50 text-[11px] font-mono text-ks-text3 uppercase tracking-wider">
          {filtered.length} Systems
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-500 mb-6">
          {error}
        </div>
      )}

      {!connections && !error && (
        <div className="rounded-xl border border-ks-border bg-ks-surface shadow-sm overflow-hidden">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-16 border-b border-ks-border/50 animate-pulse bg-ks-surface-2/40" />
          ))}
        </div>
      )}

      {connections && (
        <div className="rounded-xl border border-ks-border bg-ks-surface shadow-sm overflow-hidden backdrop-blur-md">
          <div
            className="grid gap-4 px-6 py-3 border-b border-ks-border bg-ks-surface-2/80"
            style={{ gridTemplateColumns: "1.5fr 1fr 1fr 2fr 100px" }}
          >
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">System & Workspace</div>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Governance Posture</div>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Active Agents</div>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">Permissions / Scopes</div>
            <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest text-right">Last Tested</div>
          </div>

          <div className="divide-y divide-ks-border/50">
            {filtered.map((sys, i) => (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                key={sys.connection_id}
                className="grid gap-4 px-6 py-4 items-center group hover:bg-ks-hover/80 transition-colors"
                style={{ gridTemplateColumns: "1.5fr 1fr 1fr 2fr 100px" }}
              >
                <div className="flex items-start gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-ks-surface-2 border border-ks-border flex items-center justify-center shrink-0 group-hover:border-ks-primary/50 transition-colors">
                    <Cloud className="w-4 h-4 text-ks-text2 group-hover:text-ks-primary" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-[14px] font-semibold text-ks-text truncate flex items-center gap-2">
                      {sys.name}
                      {sys.status === "active" ? (
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_5px_rgba(16,185,129,0.8)]" />
                      ) : (
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shadow-[0_0_5px_rgba(245,158,11,0.8)] animate-pulse" />
                      )}
                    </div>
                    <div className="text-[12px] text-ks-text3 truncate mt-0.5">
                      {sys.workspace_name ? (
                        <>Workspace: <span className="text-ks-text2">{sys.workspace_name}</span></>
                      ) : (
                        <span className="italic text-ks-text3">Unassigned</span>
                      )}
                    </div>
                    <div className="text-[10px] text-ks-text3 mt-0.5 font-mono">
                      {sys.connector_type} · {sys.environment}
                    </div>
                  </div>
                </div>

                <div>
                  {sys.risk_level === "high" ? (
                    <Badge color="red" className="gap-1.5">
                      <ShieldAlert className="w-3 h-3" />
                      High Risk
                    </Badge>
                  ) : sys.risk_level === "medium" ? (
                    <Badge color="amber" className="gap-1.5">
                      <Settings2 className="w-3 h-3" />
                      Medium Risk
                    </Badge>
                  ) : (
                    <Badge color="green" className="gap-1.5">
                      <CheckCircle2 className="w-3 h-3" />
                      Low Risk
                    </Badge>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <div className="flex -space-x-2">
                    {[...Array(Math.min(sys.active_agents, 3))].map((_, i) => (
                      <div
                        key={i}
                        className="w-6 h-6 rounded-full bg-ks-surface-2 border-2 border-ks-surface flex items-center justify-center z-10"
                      >
                        <Box className="w-3 h-3 text-ks-text3" />
                      </div>
                    ))}
                    {sys.active_agents > 3 && (
                      <div className="w-6 h-6 rounded-full bg-ks-surface-2 border-2 border-ks-surface flex items-center justify-center z-0 text-[9px] font-mono font-bold text-ks-text3">
                        +{sys.active_agents - 3}
                      </div>
                    )}
                    {sys.active_agents === 0 && (
                      <span className="text-[11px] text-ks-text3 italic">No activity</span>
                    )}
                  </div>
                  <div className="text-[11px] font-mono text-ks-text3 ml-2">
                    {sys.total_runs.toLocaleString()} run{sys.total_runs !== 1 ? "s" : ""}
                  </div>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  {sys.scopes.map((scope) => {
                    const isHighPriv =
                      scope.toLowerCase().includes("write") ||
                      scope.toLowerCase().includes("create") ||
                      scope.toLowerCase().includes("put") ||
                      scope.toLowerCase().includes("delete") ||
                      scope.toLowerCase().includes("admin") ||
                      scope.toLowerCase().includes("assume");
                    return (
                      <span
                        key={scope}
                        className={cn(
                          "px-1.5 py-0.5 rounded text-[10px] font-mono tracking-tight border",
                          isHighPriv
                            ? "bg-red-500/5 text-red-400 border-red-500/20"
                            : "bg-ks-surface-2 text-ks-text2 border-ks-border"
                        )}
                      >
                        {scope}
                      </span>
                    );
                  })}
                </div>

                <div className="text-[12px] text-ks-text3 text-right font-mono tracking-tight">
                  {sys.last_tested_at ? timeAgo(sys.last_tested_at.replace("Z", "")) : "—"}
                </div>
              </motion.div>
            ))}
            {filtered.length === 0 && (
              <div className="px-6 py-16 text-center text-sm text-ks-text3">
                No systems match your search.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
