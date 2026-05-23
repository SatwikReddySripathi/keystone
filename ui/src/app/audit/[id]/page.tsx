"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, Cloud, Box, UserCheck, ShieldAlert, ArrowLeft, FileSearch, Globe, Workflow, Hash } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/lib/components";
import { fetchAuditEntry } from "@/lib/api";

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
    reasons: Array<{ rule?: string; reason?: string } | string>;
    blast_radius: number;
  };
  approver: {
    id: string; name: string; designation: string; department: string;
    channel: string | null; approved_at: string | null;
  } | null;
  objects_touched: string[];
  proof_signature: string | null;
};

export default function AuditDetailPage({ params }: { params: { id: string } }) {
  const [data, setData] = useState<AuditEntry | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAuditEntry(params.id)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  }, [params.id]);

  if (error) {
    return (
      <div className="max-w-5xl mx-auto pt-12">
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-6 text-sm text-red-500">
          {error}
          <div className="mt-3">
            <Link href="/audit" className="text-ks-primary hover:underline inline-flex items-center gap-1">
              <ArrowLeft className="w-4 h-4" /> Back to audit trail
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
        <div className="h-48 bg-ks-surface-2 rounded-xl animate-pulse" />
        <div className="grid grid-cols-2 gap-6">
          <div className="h-56 bg-ks-surface-2 rounded-xl animate-pulse" />
          <div className="h-56 bg-ks-surface-2 rounded-xl animate-pulse" />
        </div>
      </div>
    );
  }

  const statusColor =
    data.status === "completed" ? "green" :
    data.status === "contained" ? "amber" :
    data.status === "blocked" ? "red" :
    data.status === "awaiting_approval" ? "violet" : "gray";

  const statusLabel = data.status === "completed" ? "PASSED · COMMITTED" : data.status.toUpperCase();

  return (
    <div className="animate-in fade-in duration-500 pb-16 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-[12px] font-mono text-ks-text3 mb-6 uppercase tracking-widest">
        <Link href="/audit" className="hover:text-ks-text transition-colors flex items-center gap-1">
          <ArrowLeft className="w-3 h-3" /> Audit Trail
        </Link>
        <span>/</span>
        <span className="text-ks-text2">Ledger: {data.action_id}</span>
      </div>

      {/* Receipt header */}
      <div className="bg-ks-surface border border-ks-border rounded-xl p-8 shadow-sm mb-8 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-[repeating-linear-gradient(90deg,transparent,transparent_10px,rgba(255,255,255,0.05)_10px,rgba(255,255,255,0.05)_20px)]" />
        <div className="absolute top-0 right-0 w-32 h-32 bg-ks-primary/5 blur-3xl rounded-full" />

        <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 relative z-10">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <FileSearch className="w-5 h-5 text-ks-primary" />
              <h1 className="text-2xl font-bold font-mono tracking-tight text-ks-text uppercase">
                Execution Receipt
              </h1>
            </div>
            <div className="text-[13px] font-mono text-ks-text2 mt-2">
              ID: <span className="text-ks-text select-all">{data.action_id}</span>
            </div>
            <div className="text-[13px] font-mono text-ks-text2 mt-1">
              Timestamp: <span className="text-ks-text">{data.timestamp}</span>
            </div>
            {data.proof_signature && (
              <div className="text-[13px] font-mono text-ks-text2 mt-1">
                Signature: <span className="text-emerald-500">Verified · {data.proof_signature.slice(0, 8)}…{data.proof_signature.slice(-4)}</span>
              </div>
            )}
            <Link
              href={`/actions/${data.action_id}/proof`}
              className="text-[12px] text-ks-primary hover:underline inline-flex items-center gap-1 mt-2"
            >
              View signed proof →
            </Link>
          </div>
          <div className="text-right">
            <div className="text-[11px] font-bold text-ks-text3 uppercase tracking-widest mb-2">Final Status</div>
            <Badge color={statusColor} className="text-base px-4 py-1.5">
              {statusLabel}
            </Badge>
          </div>
        </div>
      </div>

      {/* Context + Governance */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="bg-ks-surface-2/50 border border-ks-border rounded-xl p-6">
          <h3 className="text-[11px] font-bold text-ks-text3 uppercase tracking-widest mb-4">
            Execution Context
          </h3>
          <div className="space-y-3">
            <KV
              icon={Box}
              label="Agent"
              value={data.agent.name || data.agent.id || "—"}
              sub={data.agent.id && data.agent.name ? data.agent.id : undefined}
              href={data.agent.id ? `/agents/${data.agent.id}` : undefined}
            />
            <KV
              icon={Workflow}
              label="Workspace"
              value={data.workspace_name || "—"}
              href={data.workspace_id ? `/workspaces/${data.workspace_id}` : undefined}
            />
            <KV icon={Cloud} label="Target System" value={data.tool} />
            <KV
              label="Action Type"
              value={data.action_type}
              mono
            />
            <KV
              label="Environment"
              value={data.environment}
            />
            {data.client_ip && (
              <KV icon={Globe} label="Client IP" value={data.client_ip} mono />
            )}
          </div>
        </div>

        <div className="bg-ks-surface-2/50 border border-ks-border rounded-xl p-6">
          <h3 className="text-[11px] font-bold text-ks-text3 uppercase tracking-widest mb-4">
            Governance Decisions
          </h3>
          <div className="space-y-3">
            <KV
              icon={ShieldCheck}
              label="Policy Matched"
              value={`${data.governance.policy_id || "—"}${data.governance.policy_version ? ` v${data.governance.policy_version}` : ""}`}
              mono
            />
            <KV
              label="Decision"
              value={data.governance.decision || "—"}
              badge={data.governance.decision}
            />
            <KV
              label="Blast Radius"
              value={`${data.governance.blast_radius} record${data.governance.blast_radius !== 1 ? "s" : ""}`}
            />
            <KV
              icon={UserCheck}
              label="Approver"
              value={data.approver?.name || "Auto-approved by policy"}
              sub={data.approver?.designation}
            />
            {data.approver?.channel && (
              <KV label="Approval Channel" value={data.approver.channel} mono />
            )}
            <KV
              label="Execution Mode"
              value={data.mode}
              badge={data.mode}
            />
          </div>
        </div>
      </div>

      {/* Reasons */}
      {data.governance.reasons && data.governance.reasons.length > 0 && (
        <div className="bg-ks-surface border border-ks-border rounded-xl p-6 mb-8">
          <h3 className="text-[11px] font-bold text-ks-text3 uppercase tracking-widest mb-4 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4" />
            Policy Reasons
          </h3>
          <ul className="space-y-2">
            {data.governance.reasons.map((r, i) => {
              const text = typeof r === "string" ? r : (r.reason || r.rule || JSON.stringify(r));
              return (
                <li key={i} className="text-[13px] text-ks-text2 flex items-start gap-2">
                  <span className="text-ks-text3 font-mono text-[10px] mt-0.5">{String(i + 1).padStart(2, "0")}</span>
                  <span>{text}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* Objects touched */}
      {data.objects_touched.length > 0 && (
        <div className="bg-ks-surface border border-ks-border rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-ks-border bg-ks-surface-2/50">
            <h3 className="text-[11px] font-bold text-ks-text3 uppercase tracking-widest flex items-center gap-2">
              <Hash className="w-4 h-4" />
              Objects Touched ({data.objects_touched.length})
            </h3>
          </div>
          <div className="p-4 max-h-96 overflow-y-auto">
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-1.5">
              {data.objects_touched.map((id) => (
                <span
                  key={id}
                  className="px-2 py-1 rounded text-[11px] font-mono bg-ks-surface-2 text-ks-text2 border border-ks-border truncate"
                >
                  {id}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function KV({
  icon: Icon,
  label,
  value,
  sub,
  mono,
  badge,
  href,
}: {
  icon?: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  sub?: string;
  mono?: boolean;
  badge?: string | null;
  href?: string;
}) {
  const Content = (
    <>
      <span className="text-sm text-ks-text2 flex items-center gap-2">
        {Icon && <Icon className="w-4 h-4" />}
        {label}
      </span>
      <div className="text-right">
        {badge ? (
          <Badge color={
            badge === "BLOCK" || badge === "BLOCKED" ? "red" :
            badge === "CANARY" ? "amber" :
            badge === "APPROVAL_REQUIRED" ? "violet" :
            badge === "AUTO" ? "green" :
            badge === "observe_only" ? "sky" : "gray"
          }>
            {badge}
          </Badge>
        ) : (
          <span className={`text-sm ${mono ? "font-mono" : "font-semibold"} text-ks-text`}>
            {value}
          </span>
        )}
        {sub && <div className="text-[11px] text-ks-text3 mt-0.5">{sub}</div>}
      </div>
    </>
  );

  if (href) {
    return (
      <Link href={href} className="flex justify-between items-center border-b border-ks-border/50 pb-2 last:border-0 hover:bg-ks-hover/40 -mx-2 px-2 rounded transition-colors">
        {Content}
      </Link>
    );
  }
  return (
    <div className="flex justify-between items-center border-b border-ks-border/50 pb-2 last:border-0">
      {Content}
    </div>
  );
}
