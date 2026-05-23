"use client";

import { useCallback, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { Users, ShieldAlert, CheckCircle2, Box, Network, FileCheck, ArrowRight } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { fetchWorkspaces, createWorkspace, requestWorkspaceAccess } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAutoRefresh, RefreshControl } from "@/lib/useAutoRefresh";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

type Workspace = {
  workspace_id: string;
  name: string;
  description: string | null;
  owner_id: string | null;
  risk_posture: string;
  owner: { name: string; designation: string; department: string } | null;
  stats: {
    members: number;
    connections: number;
    agents: number;
    total_runs: number;
    pending_approvals: number;
  };
};

export default function WorkspacesPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const { me, canSeeWorkspace } = useAuth();

  const load = useCallback(async () => {
    try {
      const data = await fetchWorkspaces();
      setWorkspaces(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  const { refreshing, lastUpdatedAt, paused, togglePause, refresh } = useAutoRefresh(load, 10000);

  async function handleCreate() {
    const name = window.prompt("Workspace name?");
    if (!name) return;
    setCreating(true);
    try {
      await createWorkspace({ name });
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="animate-in fade-in duration-500 pb-16 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ks-text">Workspaces</h1>
          <p className="text-[13px] text-ks-text2 mt-1.5 max-w-2xl leading-relaxed">
            Logical boundaries for teams to govern their own AI agents. Each workspace maintains its own members, connected systems, and agents.
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <RefreshControl
            refreshing={refreshing}
            lastUpdatedAt={lastUpdatedAt}
            paused={paused}
            togglePause={togglePause}
            refresh={refresh}
            intervalLabel="10s"
          />
          {me?.is_admin && (
            <button
              onClick={handleCreate}
              disabled={creating}
              className="flex items-center gap-2 px-4 py-2 bg-ks-primary border border-ks-primary rounded-lg text-sm font-medium text-white shadow-[0_0_15px_rgba(79,70,229,0.3)] hover:shadow-[0_0_20px_rgba(79,70,229,0.5)] transition-all disabled:opacity-50"
            >
              <Users className="w-4 h-4" />
              {creating ? "Creating…" : "New Workspace"}
            </button>
          )}
        </div>
      </div>

      {/* Non-admin scope notice */}
      {me && !me.is_admin && (
        <div className="rounded-lg border border-ks-border bg-ks-surface-2/40 p-3 text-[12px] text-ks-text3 mb-6">
          You have access to {me.memberships.length} workspace{me.memberships.length !== 1 ? "s" : ""}.
          Click <strong className="text-ks-text2">Request access</strong> on any other workspace to ask an admin to let you in.
        </div>
      )}

      {/* Loading / Error */}
      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-500 mb-6">
          {error}
        </div>
      )}
      {!workspaces && !error && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-56 rounded-xl border border-ks-border bg-ks-surface/40 animate-pulse" />
          ))}
        </div>
      )}

      {/* Grid — show all workspaces. Members get full access; others see a
         read-only card with a Request Access button. */}
      {workspaces && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {workspaces.map((ws, i) => {
            const isMember = canSeeWorkspace(ws.workspace_id);
            const pendingRequest = me?.my_pending_requests?.find(
              (r) => r.workspace_id === ws.workspace_id
            );
            return (
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07 }}
                key={ws.workspace_id}
              >
                <WorkspaceCard
                  ws={ws}
                  isMember={isMember}
                  pendingRequest={pendingRequest}
                  onRequestAccess={async () => {
                    try {
                      await requestWorkspaceAccess(ws.workspace_id);
                      await refresh();
                      // The profile also needs to reload so my_pending_requests updates
                      window.location.reload();
                    } catch (e) {
                      alert(e instanceof Error ? e.message : "Failed");
                    }
                  }}
                />
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function WorkspaceCard({
  ws, isMember, pendingRequest, onRequestAccess,
}: {
  ws: Workspace;
  isMember: boolean;
  pendingRequest?: { status: string; requested_at: string };
  onRequestAccess: () => void;
}) {
  const postureDot = cn(
    "absolute top-0 left-0 w-full h-1",
    ws.risk_posture === "critical" ? "bg-red-500"
      : ws.risk_posture === "warning" ? "bg-amber-500"
      : "bg-emerald-500"
  );
  const postureBadge = cn(
    "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border backdrop-blur-sm",
    ws.risk_posture === "critical" ? "bg-red-500/10 text-red-600 border-red-500/20"
      : ws.risk_posture === "warning" ? "bg-amber-500/10 text-amber-600 border-amber-500/20"
      : "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
  );

  const cardBase = "block rounded-xl border bg-ks-surface/50 shadow-sm p-6 relative overflow-hidden backdrop-blur-md";
  const cardInteractive = isMember
    ? "border-ks-border hover:shadow-md hover:border-ks-border-sub hover:bg-ks-hover/50 transition-all group"
    : "border-ks-border opacity-90";

  const body = (
    <>
      <div className={postureDot} />
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-bold text-ks-text flex items-center gap-2">
            {ws.name}
          </h3>
          <div className="text-[12px] font-mono text-ks-text3 mt-1">
            Owner: {ws.owner?.name || "—"}
            {ws.owner?.designation && <span className="text-ks-text3"> · {ws.owner.designation}</span>}
          </div>
        </div>
        <div className={postureBadge}>
          {ws.risk_posture === "healthy"
            ? <CheckCircle2 className="w-3 h-3" />
            : <ShieldAlert className="w-3 h-3" />}
          {ws.risk_posture.charAt(0).toUpperCase() + ws.risk_posture.slice(1)} posture
        </div>
      </div>

      {ws.description && (
        <p className="text-[13px] text-ks-text2 mb-6 line-clamp-2">{ws.description}</p>
      )}

      <div className="grid grid-cols-4 gap-4 py-4 border-t border-b border-ks-border/50 mb-4">
        <Metric label="Agents" value={ws.stats.agents} icon={Box} />
        <Metric label="Systems" value={ws.stats.connections} icon={Network} />
        <Metric label="Members" value={ws.stats.members} icon={FileCheck} />
        <Metric label="Runs" value={ws.stats.total_runs} tabular />
      </div>

      {isMember ? (
        <div className="flex justify-between items-center text-[12px] font-medium text-ks-text3">
          {ws.stats.pending_approvals > 0 ? (
            <span className="text-amber-500">
              {ws.stats.pending_approvals} pending approval{ws.stats.pending_approvals !== 1 ? "s" : ""}
            </span>
          ) : (
            <span />
          )}
          <span className="flex items-center">
            Enter workspace
            <ArrowRight className="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
          </span>
        </div>
      ) : pendingRequest ? (
        <div className="flex items-center justify-between gap-2 text-[12px]">
          <span className="text-violet-500 font-medium">Access request pending admin review</span>
        </div>
      ) : (
        <div className="flex items-center justify-end">
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onRequestAccess();
            }}
            className="text-[12px] font-medium px-3 py-1.5 rounded bg-ks-primary text-white hover:opacity-90 transition-opacity"
          >
            Request access
          </button>
        </div>
      )}
    </>
  );

  return isMember ? (
    <Link href={`/workspaces/${ws.workspace_id}`} className={`${cardBase} ${cardInteractive}`}>
      {body}
    </Link>
  ) : (
    <div className={`${cardBase} ${cardInteractive}`}>{body}</div>
  );
}

function Metric({
  label,
  value,
  icon: Icon,
  tabular,
}: {
  label: string;
  value: number;
  icon?: React.ComponentType<{ className?: string }>;
  tabular?: boolean;
}) {
  const display = tabular && value >= 1000 ? `${(value / 1000).toFixed(1)}k` : String(value);
  return (
    <div className="flex flex-col">
      <span className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest mb-1">{label}</span>
      <div className="flex items-center gap-1.5 text-ks-text font-bold">
        {Icon && <Icon className="w-3.5 h-3.5 text-ks-text3" />}
        <span className={tabular ? "tabular-nums" : ""}>{display}</span>
      </div>
    </div>
  );
}
