"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  fetchAction, approveAction, executeAction, denyAction,
  rerunAction, fetchApprovers, comparePolicy,
  fetchConnectorUrl, fetchRecordTimeline, fetchTargets
} from "@/lib/api";
import { Badge, parseJson } from "@/lib/components";
import Link from "next/link";

/* ── Status badge ────────────────────────────────────────────────── */
function StatusBadge({ s }: { s: string }) {
  const m: Record<string, [string, string]> = {
    completed:         ["green",  "Passed"],
    blocked:           ["red",    "Blocked"],
    contained:         ["amber",  "Contained"],
    observed:          ["sky",    "Dry Run"],
    awaiting_approval: ["violet", "Pending Review"],
    approved:          ["green",  "Approved"],
  };
  const [c, l] = m[s] || ["gray", s];
  return <Badge color={c}>{l}</Badge>;
}

/* ── Lifecycle pipeline ──────────────────────────────────────────── */
function Lifecycle({ events, status }: { events: any[]; status: string }) {
  const types = (events || []).map((e: any) => e.type || "");
  type S = "done" | "active" | "fail" | "skip" | "wait";

  const steps: { label: string; state: S; sub: string }[] = [
    {
      label: "Diff", sub: "Blast radius scanned",
      state: types.some(t => t.includes("preview")) ? "done" : "wait",
    },
    {
      label: "Gate", sub: "Policy evaluated",
      state: types.some(t => t.includes("decision")) ? "done" : "wait",
    },
    {
      label: "Approval",
      state: types.some(t => t.includes("approval.recorded")) ? "done"
           : types.some(t => t.includes("approval.denied")) ? "fail"
           : status === "awaiting_approval" ? "active" : "skip",
      sub: "",
    },
    {
      label: "Canary",
      state: types.some(t => t.includes("breaker.tripped")) ? "fail"
           : types.some(t => t.includes("canary.completed")) ? "done"
           : types.some(t => t.includes("canary.started")) ? "active"
           : (status === "blocked" || status === "observed") ? "skip" : "wait",
      sub: "",
    },
    {
      label: "Rollout",
      state: status === "contained" ? "fail"
           : types.some(t => t.includes("expand.completed")) ? "done"
           : types.some(t => t.includes("expand.started")) ? "active"
           : ["blocked", "observed", "contained"].includes(status) ? "skip" : "wait",
      sub: "",
    },
    {
      label: "Audit Log", sub: "Signed receipt",
      state: types.some(t => t.includes("proof")) ? "done" : "wait",
    },
  ];

  // Fill in dynamic subs
  steps[2].sub = steps[2].state === "skip" ? "Not required"
               : steps[2].state === "done" ? "Human approved"
               : steps[2].state === "fail" ? "Denied" : "Pending";
  steps[3].sub = steps[3].state === "done" ? "Staged deploy OK"
               : steps[3].state === "fail" ? "Anomaly detected"
               : steps[3].state === "skip" ? "Skipped" : "Pending";
  steps[4].sub = steps[4].state === "done" ? "Full deploy complete"
               : steps[4].state === "fail" ? "Halted by breaker"
               : steps[4].state === "skip" ? "Not reached" : "Pending";

  const dotCls: Record<S, string> = {
    done:   "bg-emerald-500",
    active: "bg-sky-500 animate-pulse",
    fail:   "bg-red-500",
    skip:   "bg-gray-300 dark:bg-[#30363d]",
    wait:   "bg-gray-200 border border-gray-300 dark:bg-[#21262d] dark:border-[#30363d]",
  };
  const lbl: Record<S, string> = {
    done:   "text-emerald-600 dark:text-emerald-400",
    active: "text-sky-600 dark:text-sky-400",
    fail:   "text-red-600 dark:text-red-400",
    skip:   "text-ks-text3",
    wait:   "text-ks-text3",
  };
  const sub: Record<S, string> = {
    done:   "text-ks-text2",
    active: "text-sky-600/70 dark:text-sky-400/70",
    fail:   "text-red-600/70 dark:text-red-400/60",
    skip:   "text-ks-text3",
    wait:   "text-ks-text3",
  };
  const line: Record<S, string> = {
    done:   "bg-emerald-400 dark:bg-emerald-700",
    active: "bg-ks-border",
    fail:   "bg-ks-border",
    skip:   "bg-ks-border",
    wait:   "bg-ks-border",
  };

  return (
    <div className="flex items-start">
      {steps.map((step, i) => (
        <div key={step.label} className="flex items-start flex-1">
          <div className="flex flex-col items-center text-center" style={{ minWidth: "64px" }}>
            <div className={`w-2.5 h-2.5 rounded-full ${dotCls[step.state]}`} />
            <span className={`text-[11px] mt-1.5 font-medium ${lbl[step.state]}`}>{step.label}</span>
            <span className={`text-[10px] mt-0.5 ${sub[step.state]}`}>{step.sub}</span>
          </div>
          {i < steps.length - 1 && (
            <div className={`flex-1 h-px mt-[5px] mx-1 ${line[step.state]}`} />
          )}
        </div>
      ))}
    </div>
  );
}

/* ── Vertical timeline ───────────────────────────────────────────── */
type EventKind = "success" | "error" | "warning" | "info" | "neutral";

const EVENT_MAP: Record<string, { label: string; kind: EventKind }> = {
  "action.created":            { label: "Action created",            kind: "neutral" },
  "preview.generated":         { label: "Preview generated",         kind: "success" },
  "decision.made":             { label: "Policy evaluated",          kind: "success" },
  "action.blocked":            { label: "Blocked by policy",         kind: "error" },
  "action.awaiting_approval":  { label: "Awaiting approval",         kind: "warning" },
  "slack.notification_sent":   { label: "Slack notification sent",   kind: "info" },
  "approval.recorded":         { label: "Approval recorded",         kind: "success" },
  "approval.denied":           { label: "Approval denied",           kind: "error" },
  "canary.started":            { label: "Canary started",            kind: "info" },
  "canary.completed":          { label: "Canary completed",          kind: "success" },
  "checks.completed":          { label: "Safety checks evaluated",   kind: "info" },
  "breaker.tripped":           { label: "Circuit breaker tripped",   kind: "error" },
  "expand.started":            { label: "Expansion started",         kind: "info" },
  "expand.completed":          { label: "Expansion completed",       kind: "success" },
  "action.completed":          { label: "Action completed",          kind: "success" },
  "action.observed":           { label: "Observed (no execution)",   kind: "info" },
  "proof.generated":           { label: "Audit receipt signed",      kind: "success" },
};

function getEventSummary(type: string, p: any): string {
  if (!p || typeof p !== "object") return "";
  switch (type) {
    case "action.created":    return p.mode ? `Mode: ${p.mode}` : "";
    case "preview.generated": return `${p.blast_radius || "?"} ops · hash: ${(p.preview_hash || "").slice(0, 12)}...`;
    case "decision.made":     return `${p.decision || "?"} · rules: ${(p.matched_rules || []).join(", ") || "default"}`;
    case "canary.started":    return `${(p.subset || []).length || "?"} records selected`;
    case "canary.completed":  return `${p.count || "?"} records · error rate: ${((p.error_rate || 0) * 100).toFixed(1)}%`;
    case "checks.completed": {
      const r = p.results || {};
      const pass = Object.values(r).filter(v => v === true).length;
      const tot = Object.keys(r).length;
      const fail = Object.entries(r).filter(([, v]) => !v).map(([k]) => k.replace(/_/g, " "));
      return fail.length ? `${pass}/${tot} passed · failed: ${fail.join(", ")}` : `All ${tot} passed`;
    }
    case "breaker.tripped":   return (p.reason || "").slice(0, 100);
    case "expand.started": case "expand.completed": return `${p.count || "?"} records in rollout`;
    case "approval.recorded": return `${p.approver || "unknown"} via ${p.channel || "?"}`;
    case "proof.generated":   return `sig: ${p.signature_prefix || "?"}...`;
    default:                  return "";
  }
}

function VerticalTimeline({ events }: { events: any[] }) {
  const kindDot: Record<EventKind, string> = {
    success: "bg-emerald-500", error: "bg-red-500",
    warning: "bg-amber-500",  info:  "bg-sky-500",
    neutral: "bg-gray-400 dark:bg-[#484f58]",
  };
  const kindLbl: Record<EventKind, string> = {
    success: "text-emerald-700 dark:text-emerald-400",
    error:   "text-red-700 dark:text-red-400",
    warning: "text-amber-700 dark:text-amber-400",
    info:    "text-sky-700 dark:text-sky-400",
    neutral: "text-ks-text",
  };
  return (
    <div className="relative ml-2">
      <div className="absolute left-[4px] top-2 bottom-2 w-px bg-ks-border" />
      {events.map((e: any, i: number) => {
        const t = e.type || "";
        const cfg = EVENT_MAP[t] || { label: t, kind: "neutral" as EventKind };
        const payload = e.payload_json || {};
        let kind = cfg.kind;
        if (t === "checks.completed") {
          kind = Object.values(payload.results || {}).some(v => v === false) ? "error" : "success";
        }
        const summary = getEventSummary(t, payload);
        return (
          <div key={i} className="relative flex items-start gap-4 pb-4 last:pb-0">
            <div className={`relative z-10 w-[9px] h-[9px] rounded-full ${kindDot[kind]} shrink-0 mt-1`} />
            <div className="flex-1 min-w-0 -mt-0.5">
              <div className="flex items-baseline gap-3">
                <span className={`text-sm font-medium ${kindLbl[kind]}`}>{cfg.label}</span>
                <span className="text-xs text-ks-text3 font-mono shrink-0">{e.created_at}</span>
              </div>
              {summary && <p className="text-xs text-ks-text2 mt-0.5">{summary}</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Section wrapper ─────────────────────────────────────────────── */
function Section({ title, sub, children, action }: {
  title: string; sub?: string; children: React.ReactNode; action?: React.ReactNode;
}) {
  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-xs font-semibold text-ks-text3 uppercase tracking-wider">{title}</h2>
          {sub && <p className="text-xs text-ks-text3 mt-0.5">{sub}</p>}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

/* ── Card wrapper ────────────────────────────────────────────────── */
function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-ks-border bg-ks-surface shadow-sm dark:shadow-none ${className}`}>
      {children}
    </div>
  );
}

/* ── Decision color map ──────────────────────────────────────────── */
const DEC_COLOR: Record<string, string> = {
  AUTO:               "text-green-700 bg-green-50 border-green-200 dark:text-emerald-400 dark:bg-emerald-950 dark:border-emerald-800",
  CANARY:             "text-sky-700 bg-sky-50 border-sky-200 dark:text-sky-400 dark:bg-sky-950 dark:border-sky-800",
  BLOCK:              "text-red-700 bg-red-50 border-red-200 dark:text-red-400 dark:bg-red-950 dark:border-red-800",
  APPROVAL_REQUIRED:  "text-purple-700 bg-purple-50 border-purple-200 dark:text-violet-400 dark:bg-violet-950 dark:border-violet-800",
};
const DEC_LABEL: Record<string, string> = {
  AUTO: "Auto-Approved", CANARY: "Canary Required",
  BLOCK: "Blocked", APPROVAL_REQUIRED: "Approval Required",
};

/* ── Main Page ───────────────────────────────────────────────────── */
export default function ActionDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showDiffs, setShowDiffs] = useState(false);
  const [approving, setApproving] = useState(false);
  const [denying, setDenying] = useState(false);
  const [actionError, setActionError] = useState("");
  const [running, setRunning] = useState(false);
  const [employeeId, setEmployeeId] = useState("");
  const [approvers, setApprovers] = useState<any[]>([]);
  const [compareResult, setCompareResult] = useState<any>(null);
  const [comparing, setComparing] = useState(false);
  const [snowUrl, setSnowUrl] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<any>(null);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [targets, setTargets] = useState<any>(null);
  const [targetsLoading, setTargetsLoading] = useState(false);
  const [showTargets, setShowTargets] = useState(false);

  const LIVE_STATUSES = new Set(["awaiting_approval", "approved", "canary_executing", "expanding"]);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    const load = () =>
      fetchAction(id).then(d => {
        setData(d);
        setLoading(false);
        if (d?.action?.status && !LIVE_STATUSES.has(d.action.status) && timer) {
          clearInterval(timer); timer = null;
        }
      }).catch(() => setLoading(false));
    load().then(() => { timer = setInterval(load, 2000); });
    return () => { if (timer) clearInterval(timer); };
  }, [id]);

  useEffect(() => { fetchApprovers().then(setApprovers).catch(() => {}); }, []);
  useEffect(() => {
    if (!data) return;
    const p = parseJson(data.action?.params_json) || {};
    if (p.connector === "servicenow_real") {
      fetchConnectorUrl().then(r => setSnowUrl(r.servicenow_url)).catch(() => {});
    }
  }, [data]);

  if (loading) return (
    <div className="max-w-4xl mx-auto animate-pulse space-y-4 pt-4">
      <div className="h-4 bg-ks-border rounded w-48" />
      <div className="h-6 bg-ks-border rounded w-64" />
      <div className="h-3 bg-ks-border rounded w-80" />
      <div className="h-24 bg-ks-border rounded-lg mt-6" />
      <div className="grid grid-cols-3 gap-3">
        {[...Array(3)].map((_, i) => <div key={i} className="h-20 bg-ks-border rounded-lg" />)}
      </div>
    </div>
  );
  if (!data) return (
    <div className="py-20 text-center">
      <p className="text-ks-text2 text-sm mb-2">Transaction not found</p>
      <Link href="/" className="text-indigo-600 dark:text-indigo-400 text-xs hover:underline">Back to Transactions</Link>
    </div>
  );

  const { action, preview, decision, approvals, executions, checks, breaker, events } = data;
  const pr = preview || {};
  const br = pr.blast_radius_json || {};
  const flags = pr.flags_json || {};
  const diffs = pr.diffs_json || [];
  const dec = decision || {};
  const reasons = dec.reasons_json || [];
  const breakerData = breaker || {};
  const actor = parseJson(action.actor_json) || {};
  const actionParams = parseJson(action.params_json) || {};

  const canaryExec = executions.find((e: any) => e.phase === "canary");
  const expandExec = executions.find((e: any) => e.phase === "expand");
  const canaryResults = canaryExec?.results_json || [];
  const canaryIds = canaryExec?.subset_ids_json || [];
  const recordsMatched = br.count || 0;
  const recordsChanged = (canaryIds.length || 0) + ((expandExec?.subset_ids_json || []).length || 0);
  const isContained = breakerData.tripped === 1;
  const isBlocked = action.status === "blocked";

  const intended = new Set(Object.keys(actionParams.changes || {}));
  const unexpectedFields = new Set<string>();
  for (const r of canaryResults) {
    for (const f of (r.changes_applied || [])) {
      if (!intended.has(f)) unexpectedFields.add(f);
    }
  }

  const fieldSummary: Record<string, { count: number; before: any; after: any }> = {};
  for (const d of diffs) {
    for (const [field, val] of Object.entries(d.fields || {})) {
      const v = val as any;
      if (!fieldSummary[field]) fieldSummary[field] = { count: 0, before: v.before, after: v.after };
      fieldSummary[field].count++;
    }
  }

  const execResultMap = new Map<string, any>();
  for (const r of canaryResults) execResultMap.set(r.sys_id, { ...r, phase: "canary" });
  const expandResults: any[] = expandExec?.results_json || [];
  for (const r of expandResults) execResultMap.set(r.sys_id, { ...r, phase: "expand" });

  type RecordStatus = "canary" | "expand" | "protected" | "blocked";
  const recordRows = diffs.map((d: any) => {
    const exec = execResultMap.get(d.sys_id);
    const status: RecordStatus = isBlocked ? "blocked"
      : exec?.phase === "canary" ? "canary"
      : exec?.phase === "expand" ? "expand"
      : "protected";
    const applied: string[] = exec?.changes_applied || [];
    const rowUnexpected = applied.filter((f: string) => !intended.has(f));
    const fieldsNotApplied: string[] = exec?.fields_not_applied || [];
    let fields: Record<string, { before: any; after: any; predicted?: boolean }> = {};
    for (const [f, val] of Object.entries(d.fields || {}) as [string, any][]) {
      fields[f] = { before: val?.before, after: val?.after, predicted: true };
    }
    const verified = !!(exec?.before_snapshot && exec?.after_snapshot);
    if (verified) {
      const merged: Record<string, { before: any; after: any; predicted?: boolean }> = {};
      for (const f of applied) {
        merged[f] = {
          before: exec.before_snapshot[f] ?? fields[f]?.before,
          after:  exec.after_snapshot[f]  ?? fields[f]?.after,
          predicted: false,
        };
      }
      for (const f of fieldsNotApplied) {
        if (fields[f]) merged[f] = { ...fields[f], predicted: true };
      }
      fields = merged;
    }
    return {
      sys_id: d.sys_id,
      number: exec?.number || d.number || d.sys_id.slice(0, 12),
      status, fields, unexpectedFields: rowUnexpected,
      success: exec?.success ?? true, verified,
      fieldsNotApplied, warning: exec?.warning,
    };
  });

  const executedAsEvent = (events || []).find((e: any) => e.type === "dryrun.executed_as");
  const childActionId = executedAsEvent?.payload_json?.child_action_id;
  const createdEvent = (events || []).find((e: any) => e.type === "action.created");
  const parentDryRunId = createdEvent?.payload_json?.parent_dry_run;

  return (
    <div className="max-w-4xl mx-auto">

      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 mb-5 text-xs">
        <Link href="/" className="text-ks-text3 hover:text-ks-text2 transition">Transactions</Link>
        <span className="text-ks-text3">/</span>
        <span className="font-mono text-ks-text3">{id.slice(0, 20)}…</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between mb-6 gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5 mb-2 flex-wrap">
            <h1 className="text-base font-semibold text-ks-text">{action.tool}.{action.action_type}</h1>
            <StatusBadge s={action.status} />
            {action.mode === "observe_only" && (
              <span className="text-[10px] font-medium uppercase tracking-wide text-sky-600 dark:text-sky-400 bg-sky-50 dark:bg-sky-950 border border-sky-200 dark:border-sky-800 px-1.5 py-0.5 rounded">
                Dry Run
              </span>
            )}
          </div>
          <div className="flex items-center gap-x-4 gap-y-1 flex-wrap text-xs text-ks-text2">
            <span>{actor.name || "Unknown"} <span className="text-ks-text3">({actor.type})</span></span>
            <span className="text-ks-border hidden sm:inline">·</span>
            <span className="uppercase tracking-wide text-[11px]">{action.environment}</span>
            <span className="text-ks-border hidden sm:inline">·</span>
            <span className="font-mono text-ks-text3 text-[10px]">{id}</span>
          </div>
        </div>
        <Link
          href={`/actions/${id}/proof`}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-ks-border bg-ks-surface hover:bg-ks-hover text-xs font-medium text-ks-text2 hover:text-ks-text transition shrink-0"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          Audit Receipt
        </Link>
      </div>

      {/* Parent dry-run link */}
      {parentDryRunId && (
        <Card className="mb-4 px-4 py-3 flex items-center justify-between">
          <span className="text-sm text-ks-text2">
            Executed from dry run{" "}
            <span className="font-mono text-xs text-indigo-600 dark:text-indigo-400">{parentDryRunId}</span>
          </span>
          <Link href={`/actions/${parentDryRunId}`}
            className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline">
            View dry run
          </Link>
        </Card>
      )}

      {/* ── Alert banners ── */}
      {isContained && (
        <div className="mb-5 flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950 px-4 py-3.5">
          <div className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0 mt-1.5" />
          <div>
            <div className="text-xs font-semibold text-amber-800 dark:text-amber-400">Containment Activated</div>
            <div className="text-xs text-amber-700 dark:text-amber-400/70 mt-0.5">
              Canary ran on {canaryIds.length} operations and detected unexpected side-effects.
              Rollout to the remaining {recordsMatched - canaryIds.length} records was halted automatically.
            </div>
          </div>
        </div>
      )}
      {isBlocked && (
        <div className="mb-5 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950 px-4 py-3.5">
          <div className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0 mt-1.5" />
          <div>
            <div className="text-xs font-semibold text-red-700 dark:text-red-400">Blocked by Policy</div>
            <div className="text-xs text-red-600 dark:text-red-400/70 mt-0.5">
              Policy gate prevented execution. Zero operations were executed.
            </div>
          </div>
        </div>
      )}

      {/* ── Deployment scope (collapsible) ── */}
      {diffs.length > 0 && (
        <Card className="mb-5 overflow-hidden">
          <button
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-ks-hover transition-colors text-left group"
            onClick={async () => {
              const next = !showTargets;
              setShowTargets(next);
              if (next && !targets) {
                setTargetsLoading(true);
                try { setTargets(await fetchTargets(id)); } catch { /* ignore */ }
                finally { setTargetsLoading(false); }
              }
            }}
          >
            <div className="flex items-center gap-3">
              <span className="text-xs font-semibold text-ks-text">Deployment Scope</span>
              <span className="text-[11px] text-ks-text3 bg-ks-surface-2 border border-ks-border px-1.5 py-0.5 rounded tabular-nums">{recordsMatched} ops</span>
            </div>
            <span className="text-[11px] text-ks-text3 group-hover:text-ks-text2 transition-colors">{showTargets ? "▲ hide" : "▼ show"}</span>
          </button>

          {showTargets && (
            <div className="border-t border-ks-border px-5 py-4">
              {targetsLoading && <div className="text-xs text-ks-text2">Loading...</div>}
              {targets && (
                <>
                  {targets.snow_list_url && (
                    <div className="mb-3 rounded-lg border border-sky-200 bg-sky-50 dark:border-sky-800 dark:bg-sky-950 px-4 py-3">
                      <div className="text-xs text-sky-700 dark:text-sky-400 font-medium mb-2">
                        Open all {targets.total} operations in ServiceNow
                      </div>
                      <div className="flex items-center gap-3">
                        <a href={targets.snow_list_url} target="_blank" rel="noopener noreferrer"
                          className="text-xs text-sky-600 dark:text-sky-400/70 font-mono truncate flex-1 hover:underline">
                          {targets.snow_list_url.slice(0, 80)}{targets.snow_list_url.length > 80 ? "..." : ""}
                        </a>
                        <a href={targets.snow_list_url} target="_blank" rel="noopener noreferrer"
                          className="shrink-0 px-3 py-1.5 rounded bg-sky-600 hover:bg-sky-700 text-white text-xs font-medium transition">
                          Open in ServiceNow
                        </a>
                      </div>
                    </div>
                  )}
                  {(targets.canary_count > 0 || targets.expand_count > 0) && (
                    <div className="flex items-center gap-2 mb-3 text-xs">
                      {targets.canary_count > 0 && <Badge color="sky">{targets.canary_count} canary</Badge>}
                      {targets.expand_count > 0 && <Badge color="green">{targets.expand_count} expanded</Badge>}
                      {targets.pending_count > 0 && <Badge color="gray">{targets.pending_count} pending</Badge>}
                    </div>
                  )}
                  <div className="rounded-lg border border-ks-border divide-y divide-ks-border overflow-hidden">
                    {(targets.records || []).map((rec: any) => (
                      <div key={rec.sys_id} className="flex items-center gap-4 px-4 py-2.5">
                        <span className="text-xs font-mono text-indigo-600 dark:text-indigo-400 font-medium w-28 shrink-0">{rec.number}</span>
                        {rec.phase !== "pending" && (
                          <span className={`text-[10px] font-semibold uppercase w-14 shrink-0 ${
                            rec.phase === "canary" ? "text-sky-600 dark:text-sky-400"
                            : rec.phase === "expand" ? "text-emerald-600 dark:text-emerald-400"
                            : "text-ks-text3"
                          }`}>{rec.phase}</span>
                        )}
                        {Object.entries(rec.before || {}).slice(0, 2).map(([field, val]: [string, any]) => (
                          <span key={field} className="text-xs text-ks-text2 shrink-0">
                            <span className="text-ks-text3">{field}:</span> {String(val ?? "—")}
                          </span>
                        ))}
                        <div className="ml-auto shrink-0">
                          {snowUrl ? (
                            <a href={`${snowUrl}/incident.do?sys_id=${rec.sys_id}`} target="_blank" rel="noopener noreferrer"
                              className="text-[11px] text-sky-600 dark:text-sky-500/70 border border-sky-200 dark:border-sky-800/40 hover:underline px-2 py-0.5 rounded transition">
                              Open
                            </a>
                          ) : (
                            <span className="text-[10px] text-ks-text3 font-mono">{rec.sys_id.slice(0, 16)}...</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </Card>
      )}

      {/* ── Dry-run panel ── */}
      {action.status === "observed" && (
        <div className="mb-5 rounded-lg border border-sky-200 dark:border-sky-800 overflow-hidden">
          <div className="px-5 py-4 bg-sky-50 dark:bg-sky-950 border-b border-sky-200 dark:border-sky-800">
            <div className="text-sm font-semibold text-sky-800 dark:text-sky-400 mb-1">Dry Run — No Changes Made</div>
            <div className="text-sm text-sky-700 dark:text-sky-400/60">
              This was a preview. Below shows what would happen if this transaction runs for real.
            </div>
          </div>
          <div className="px-5 py-4 bg-ks-surface space-y-4">
            {/* Scope */}
            <div className="flex items-center gap-6">
              <div>
                <div className="text-2xl font-bold text-ks-text">{recordsMatched}</div>
                <div className="text-xs text-ks-text2">operations in scope</div>
              </div>
              {br.breakdowns?.by_priority && (
                <div className="flex gap-2 flex-wrap">
                  {Object.entries(br.breakdowns.by_priority).map(([k, v]) => (
                    <span key={k} className="text-xs text-ks-text2 bg-ks-surface-2 border border-ks-border px-2 py-0.5 rounded">{k}: {v as number}</span>
                  ))}
                </div>
              )}
            </div>

            {/* Field changes */}
            {Object.keys(fieldSummary).length > 0 && (
              <div>
                <div className="text-xs font-medium text-ks-text3 uppercase tracking-wide mb-2">Would change</div>
                <div className="space-y-1">
                  {Object.entries(fieldSummary).map(([field, info]) => (
                    <div key={field} className="flex items-center gap-3 text-sm">
                      <span className="text-ks-text font-medium w-36 shrink-0">{field}</span>
                      <span className="text-red-600 dark:text-red-400/70 line-through text-xs">{String(info.before)}</span>
                      <span className="text-ks-text3 text-xs">to</span>
                      <span className="text-emerald-600 dark:text-emerald-400 text-xs">{String(info.after)}</span>
                      <span className="text-ks-text3 text-xs ml-auto">{info.count} ops</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Policy decision */}
            <div>
              <div className="text-xs font-medium text-ks-text3 uppercase tracking-wide mb-2">Policy would decide</div>
              <div className="flex items-center gap-3">
                <span className={`px-3 py-1 rounded text-sm font-semibold border ${DEC_COLOR[dec.decision] || "text-ks-text2 bg-ks-surface-2 border-ks-border"}`}>
                  {DEC_LABEL[dec.decision] || dec.decision}
                </span>
                {dec.decision === "BLOCK" && <span className="text-sm text-red-600 dark:text-red-400">Would be blocked</span>}
                {dec.decision === "CANARY" && <span className="text-sm text-sky-600 dark:text-sky-400">Canary required</span>}
                {dec.decision === "AUTO" && <span className="text-sm text-emerald-600 dark:text-emerald-400">Would auto-approve</span>}
                {dec.decision === "APPROVAL_REQUIRED" && <span className="text-sm text-purple-600 dark:text-violet-400">Would need human approval</span>}
              </div>
            </div>

            {/* Risk flags */}
            {Object.entries(flags || {}).some(([, v]) => v === true) && (
              <div>
                <div className="text-xs font-medium text-ks-text3 uppercase tracking-wide mb-2">Risk flags</div>
                <div className="flex gap-2 flex-wrap">
                  {Object.entries(flags || {})
                    .filter(([, v]) => typeof v === "boolean" && v === true)
                    .map(([k]) => {
                      const fl: Record<string, string> = { has_p1: "red", has_p2: "amber", has_vip: "violet", cross_group: "sky", state_transition: "gray" };
                      const ll: Record<string, string> = { has_p1: "P1 Critical", has_p2: "P2 High", has_vip: "VIP Caller", cross_group: "Cross-Group", state_transition: "State Transition" };
                      return <Badge key={k} color={fl[k] || "gray"}>{ll[k] || k.replace(/_/g, " ")}</Badge>;
                    })}
                </div>
              </div>
            )}

            {/* Run for Real */}
            <div className="pt-3 border-t border-ks-border">
              {childActionId ? (
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm text-emerald-600 dark:text-emerald-400 font-medium">Executed</div>
                    <div className="text-xs text-ks-text2 mt-0.5">This dry run was converted to a live transaction.</div>
                  </div>
                  <Link href={`/actions/${childActionId}`}
                    className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition">
                    View Execution
                  </Link>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm text-ks-text font-medium">Ready to execute for real?</div>
                    <div className="text-xs text-ks-text2 mt-0.5">
                      {dec.decision === "CANARY" && "Canary-deploys 5 ops first, then rolls out if all checks pass."}
                      {dec.decision === "AUTO" && "Runs the full pipeline with post-execution safety checks."}
                      {dec.decision === "BLOCK" && "Cannot be executed — blocked by policy."}
                      {dec.decision === "APPROVAL_REQUIRED" && "Will route for human approval before execution."}
                    </div>
                  </div>
                  <button
                    disabled={running || dec.decision === "BLOCK"}
                    onClick={async () => {
                      setRunning(true); setActionError("");
                      try {
                        const result = await rerunAction(id);
                        window.location.href = `/actions/${result.action_id}`;
                      } catch (e: any) {
                        setActionError(e.message || "Failed to run");
                        setRunning(false);
                      }
                    }}
                    className={`px-5 py-2 rounded-lg text-sm font-medium transition shrink-0 ${
                      dec.decision === "BLOCK"
                        ? "bg-gray-100 dark:bg-[#21262d] text-ks-text3 cursor-not-allowed"
                        : "bg-emerald-600 hover:bg-emerald-700 text-white"
                    }`}
                  >
                    {running ? "Running..." : dec.decision === "BLOCK" ? "Blocked by Policy" : "Run for Real"}
                  </button>
                </div>
              )}
              {actionError && <div className="mt-2 text-xs text-red-600 dark:text-red-400">{actionError}</div>}
            </div>
          </div>
        </div>
      )}

      {/* ── Approval panel ── */}
      {action.status === "awaiting_approval" && (
        <div className="mb-6 rounded-lg border border-violet-200 dark:border-violet-800 overflow-hidden">
          <div className="px-5 py-3.5 border-b border-violet-200 dark:border-violet-800 bg-violet-50 dark:bg-violet-950 flex items-center gap-3">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse shrink-0" />
            <div>
              <div className="text-xs font-semibold text-violet-700 dark:text-violet-300">Approval Required</div>
              <div className="text-[11px] text-violet-600/70 dark:text-violet-400/60 mt-0.5">
                This transaction is waiting for human review. Enter your Employee ID to approve or deny.
              </div>
            </div>
          </div>
          <div className="px-5 py-4 bg-ks-surface">
            {approvers.length > 0 && (
              <Card className="mb-4 divide-y divide-ks-border overflow-hidden">
                <div className="px-4 py-2 bg-ks-surface-2">
                  <span className="text-xs font-medium text-ks-text3 uppercase tracking-wide">Authorized approvers</span>
                </div>
                {approvers.map((a: any) => (
                  <div key={a.employee_id} className="flex items-center justify-between px-4 py-2.5 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-ks-text">{a.name}</span>
                      <span className="text-ks-text2">{a.designation}</span>
                    </div>
                    <span className="text-ks-text3 font-mono">{a.employee_id}</span>
                  </div>
                ))}
              </Card>
            )}
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <label className="text-xs text-ks-text2 block mb-1.5">Employee ID</label>
                <input
                  type="text"
                  value={employeeId}
                  onChange={(e) => { setEmployeeId(e.target.value); setActionError(""); }}
                  placeholder="e.g. EMP001"
                  className="w-full px-3 py-2 rounded-lg bg-ks-surface border border-ks-border text-sm text-ks-text placeholder-ks-text3 focus:border-indigo-500 focus:outline-none font-mono"
                />
              </div>
              <button
                disabled={!employeeId.trim() || approving || denying}
                onClick={async () => {
                  setApproving(true); setActionError("");
                  try {
                    await approveAction(id, employeeId.trim());
                    await executeAction(id);
                    setData(await fetchAction(id));
                  } catch (e: any) {
                    setActionError(e.message || "Approval failed");
                  } finally { setApproving(false); }
                }}
                className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-100 disabled:dark:bg-[#21262d] disabled:text-ks-text3 text-white text-sm font-medium transition"
              >
                {approving ? "Approving..." : "Approve"}
              </button>
              <button
                disabled={!employeeId.trim() || approving || denying}
                onClick={async () => {
                  setDenying(true); setActionError("");
                  try {
                    await denyAction(id, employeeId.trim());
                    setData(await fetchAction(id));
                  } catch (e: any) {
                    setActionError(e.message || "Deny failed");
                  } finally { setDenying(false); }
                }}
                className="px-5 py-2 rounded-lg bg-red-600 hover:bg-red-700 disabled:bg-gray-100 disabled:dark:bg-[#21262d] disabled:text-ks-text3 text-white text-sm font-medium transition"
              >
                {denying ? "Denying..." : "Deny"}
              </button>
            </div>
            {actionError && (
              <div className="mt-3 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg px-3 py-2">{actionError}</div>
            )}
          </div>
        </div>
      )}

      {/* ── Pipeline ── */}
      <Card className="mb-6 overflow-hidden">
        <div className="px-4 py-2.5 border-b border-ks-border bg-ks-surface-2 flex items-center justify-between">
          <span className="text-[11px] font-semibold text-ks-text3 uppercase tracking-wider">Transaction Pipeline</span>
          <span className="text-[11px] text-ks-text3 font-mono">{action.status}</span>
        </div>
        <div className="px-6 py-4">
          <Lifecycle events={events || []} status={action.status} />
        </div>
      </Card>

      {/* ── Key numbers ── */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        {[
          {
            n: recordsMatched,
            label: "In Scope",
            sub: "Matched by query",
            color: "text-ks-text",
            icon: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2",
          },
          {
            n: isBlocked ? 0 : recordsChanged,
            label: "Executed",
            sub: isContained ? "Halted by breaker" : "Successfully deployed",
            color: isBlocked ? "text-ks-text3" : isContained ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400",
            icon: "M5 13l4 4L19 7",
          },
          {
            n: checks.length === 0 ? "—"
              : `${checks.filter((c: any) => c.passed === 1 || c.passed === true).length}/${checks.length}`,
            label: "Safety Checks",
            sub: "Post-execution invariants",
            color: checks.length === 0 ? "text-ks-text3"
              : checks.every((c: any) => c.passed === 1 || c.passed === true)
                ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400",
            icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0 1 12 2.944a11.955 11.955 0 0 1-8.618 3.04A12.02 12.02 0 0 0 3 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
          },
        ].map((s, i) => (
          <Card key={i} className="px-4 py-3.5">
            <div className={`text-2xl font-bold tabular-nums ${s.color}`}>{s.n}</div>
            <div className="text-xs font-medium text-ks-text mt-1">{s.label}</div>
            <div className="text-[11px] text-ks-text3 mt-0.5">{s.sub}</div>
          </Card>
        ))}
      </div>

      {/* ── Policy Decision ── */}
      <Section title="Policy Decision">
        <Card className="p-5">
          <div className="flex items-center gap-3 mb-4">
            <span className={`px-3 py-1 rounded text-sm font-semibold border ${DEC_COLOR[dec.decision] || "text-ks-text2 bg-ks-surface-2 border-ks-border"}`}>
              {DEC_LABEL[dec.decision] || dec.decision || "Unknown"}
            </span>
            <span className="text-xs text-ks-text2">Policy v{dec.policy_version} · {dec.policy_id}</span>
          </div>
          {reasons.length > 0 && (
            <div className="space-y-2 mb-4">
              {reasons.map((r: any, i: number) => (
                <div key={i} className="rounded-lg border border-ks-border bg-ks-surface-2 px-4 py-3">
                  <div className="text-[11px] text-ks-text3 font-mono mb-1">{r.rule}</div>
                  <div className="text-sm text-ks-text">{(r.reason || "").replace(/\u00e2\u0080\u0094|\u00e2\u0080\u0093|â€"|â€"/g, " -- ")}</div>
                </div>
              ))}
            </div>
          )}
          {!compareResult ? (
            <button
              disabled={comparing}
              onClick={async () => {
                setComparing(true);
                try { setCompareResult(await comparePolicy(id)); }
                catch { /* silently fail */ }
                finally { setComparing(false); }
              }}
              className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline border border-indigo-200 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-950 px-3 py-1.5 rounded-lg transition"
            >
              {comparing ? "Comparing..." : "Compare with strict_policy.yaml"}
            </button>
          ) : (
            <div className="mt-2 rounded-lg border border-ks-border bg-ks-surface-2 px-4 py-3">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-ks-text2 font-medium">Same preview — different rules</span>
                <button onClick={() => setCompareResult(null)} className="text-xs text-ks-text3 hover:text-ks-text2 transition">hide</button>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-ks-text2">default v{compareResult.default.version}</span>
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold border ${DEC_COLOR[compareResult.default.decision] || "text-ks-text2 bg-ks-surface-2 border-ks-border"}`}>
                    {compareResult.default.decision}
                  </span>
                </div>
                <span className="text-ks-text3 text-xs">vs</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-ks-text2">strict v{compareResult.alternate.version}</span>
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold border ${DEC_COLOR[compareResult.alternate.decision] || "text-ks-text2 bg-ks-surface-2 border-ks-border"}`}>
                    {compareResult.alternate.decision}
                  </span>
                </div>
                {compareResult.same_decision
                  ? <span className="text-xs text-ks-text2 ml-auto">Same outcome</span>
                  : <span className="text-xs text-amber-600 dark:text-amber-400 ml-auto">Outcomes differ</span>
                }
              </div>
              {!compareResult.same_decision && compareResult.alternate.reasons.length > 0 && (
                <div className="mt-2 space-y-1">
                  {compareResult.alternate.reasons.map((r: any, i: number) => (
                    <div key={i} className="text-xs text-ks-text2 bg-ks-surface rounded px-3 py-1.5 border border-ks-border">
                      <span className="text-ks-text3 font-mono mr-2">{r.rule}</span>
                      {(r.reason || "").replace(/\u00e2\u0080\u0094|\u00e2\u0080\u0093|â€"|â€"/g, " -- ")}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Card>
      </Section>

      {/* ── Approvals ── */}
      {approvals.length > 0 && (
        <Section title="Approvals">
          <div className="space-y-2">
            {approvals.map((a: any, i: number) => {
              const ap = a.approver_json || {};
              return (
                <Card key={i} className="p-4 flex items-center gap-4">
                  <div className="w-9 h-9 rounded-full bg-emerald-50 dark:bg-emerald-950 border border-emerald-200 dark:border-emerald-800 flex items-center justify-center text-emerald-600 dark:text-emerald-400 text-sm font-semibold shrink-0">
                    {(ap.name || "?")[0].toUpperCase()}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-ks-text">{ap.name || "Unknown"}</div>
                    {ap.designation && (
                      <div className="text-xs text-ks-text2">{ap.designation}{ap.department ? ` · ${ap.department}` : ""}</div>
                    )}
                    <div className="text-xs text-ks-text3">
                      via {a.channel} · hash: {(a.preview_hash || "").slice(0, 12)}... · policy v{a.policy_version}
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </Section>
      )}

      {/* ── Record Changes ── */}
      {Object.keys(fieldSummary).length > 0 && (
        <Section
          title="Record Changes"
          action={
            <div className="flex items-center gap-2">
              {recordRows.filter((r: any) => r.status === "canary").length > 0 && (
                <Badge color="sky">{recordRows.filter((r: any) => r.status === "canary").length} canary</Badge>
              )}
              {recordRows.filter((r: any) => r.status === "expand").length > 0 && (
                <Badge color="green">{recordRows.filter((r: any) => r.status === "expand").length} expanded</Badge>
              )}
              {recordRows.filter((r: any) => r.status === "protected").length > 0 && (
                <Badge color="gray">{recordRows.filter((r: any) => r.status === "protected").length} protected</Badge>
              )}
              {diffs.length > 0 && (
                <button onClick={() => setShowDiffs(!showDiffs)}
                  className="text-xs text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-950 px-2.5 py-0.5 rounded hover:underline">
                  {showDiffs ? "collapse" : "expand all"}
                </button>
              )}
            </div>
          }
        >
          {/* Field summary */}
          <Card className="divide-y divide-ks-border overflow-hidden mb-3">
            {Object.entries(fieldSummary).map(([field, info]) => (
              <div key={field} className="flex items-center justify-between px-5 py-3">
                <div className="flex items-center gap-4">
                  <span className="text-sm font-medium text-ks-text w-36 shrink-0">{field}</span>
                  <span className="text-sm text-red-600 dark:text-red-400/70 line-through">{String(info.before ?? "—")}</span>
                  <span className="text-ks-text3 text-xs mx-1">to</span>
                  <span className="text-sm text-emerald-600 dark:text-emerald-400">{String(info.after ?? "—")}</span>
                </div>
                <span className="text-xs text-ks-text2">{info.count} ops</span>
              </div>
            ))}
          </Card>

          {unexpectedFields.size > 0 && (
            <div className="mb-3 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950 px-4 py-3">
              <div className="text-xs font-semibold text-amber-800 dark:text-amber-400 mb-1">Business rule side-effects detected</div>
              <div className="text-xs text-amber-700 dark:text-amber-400/60 mb-2">
                ServiceNow auto-changed these fields — not intended by the agent. This triggered the circuit breaker.
              </div>
              <div className="flex gap-2 flex-wrap">
                {Array.from(unexpectedFields).map(f => (
                  <span key={f} className="text-xs bg-amber-100 dark:bg-amber-950 border border-amber-300 dark:border-amber-700 text-amber-700 dark:text-amber-400 px-2 py-0.5 rounded font-mono">{f}</span>
                ))}
              </div>
            </div>
          )}

          {showDiffs && (
            <Card className="divide-y divide-ks-border overflow-hidden">
              {recordRows.map((row: any) => {
                const sCfg: Record<string, { label: string; dot: string; text: string }> = {
                  canary:    { label: "CANARY",    dot: "bg-sky-500",     text: "text-sky-600 dark:text-sky-400" },
                  expand:    { label: "EXPANDED",  dot: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400" },
                  protected: { label: "PROTECTED", dot: "bg-gray-400",    text: "text-ks-text3" },
                  blocked:   { label: "BLOCKED",   dot: "bg-red-500",     text: "text-red-600 dark:text-red-400" },
                };
                const cfg = sCfg[row.status];
                const wasExecuted = row.status === "canary" || row.status === "expand";
                return (
                  <div key={row.sys_id} className="px-4 py-3">
                    <div className="flex items-center gap-3 mb-2">
                      <div className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                      <span className={`text-[10px] font-semibold uppercase tracking-wide ${cfg.text}`}>{cfg.label}</span>
                      <span className="text-sm font-mono text-indigo-600 dark:text-indigo-400 font-medium">{row.number}</span>
                      <span className="text-[10px] text-ks-text3 font-mono">{row.sys_id}</span>
                      {row.verified && wasExecuted && (
                        <span className="text-[10px] text-emerald-600 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950 px-1.5 py-0.5 rounded">verified</span>
                      )}
                      <div className="ml-auto flex items-center gap-2">
                        {snowUrl && wasExecuted && (
                          <a href={`${snowUrl}/incident.do?sys_id=${row.sys_id}`} target="_blank" rel="noopener noreferrer"
                            className="text-[11px] text-sky-600 dark:text-sky-400/70 border border-sky-200 dark:border-sky-800/40 px-2 py-0.5 rounded hover:underline transition">
                            ServiceNow ↗
                          </a>
                        )}
                        {snowUrl && row.status === "protected" && (
                          <a href={`${snowUrl}/incident.do?sys_id=${row.sys_id}`} target="_blank" rel="noopener noreferrer"
                            className="text-[11px] text-ks-text3 border border-ks-border px-2 py-0.5 rounded hover:underline transition">
                            ServiceNow ↗
                          </a>
                        )}
                      </div>
                    </div>
                    {wasExecuted && row.fieldsNotApplied.length > 0 && (
                      <div className="ml-5 mb-2 rounded border border-orange-200 dark:border-orange-800 bg-orange-50 dark:bg-orange-950 px-3 py-2">
                        <div className="text-[11px] font-semibold text-orange-700 dark:text-orange-400 mb-0.5">
                          Not applied: {row.fieldsNotApplied.join(", ")}
                        </div>
                        <div className="text-[10px] text-orange-600 dark:text-orange-400/60">
                          ServiceNow returned HTTP 200 but did not change these fields. Values shown are predictions.
                        </div>
                        {snowUrl && (
                          <a href={`${snowUrl}/incident.do?sys_id=${row.sys_id}`} target="_blank" rel="noopener noreferrer"
                            className="text-[10px] text-sky-600 dark:text-sky-400 hover:underline mt-1 inline-block">
                            Verify in ServiceNow ↗
                          </a>
                        )}
                      </div>
                    )}
                    {wasExecuted && Object.entries(row.fields).length > 0 && (
                      <div className="ml-5 space-y-0.5">
                        {row.verified && row.fieldsNotApplied.length === 0 && (
                          <div className="text-[10px] text-emerald-600/60 dark:text-emerald-500/60 mb-1">
                            Real values from ServiceNow before and after execution
                          </div>
                        )}
                        {Object.entries(row.fields).map(([field, val]: [string, any]) => {
                          const isUnexpected = row.unexpectedFields.includes(field);
                          const isPredicted = val.predicted === true;
                          return (
                            <div key={field} className="flex items-center gap-2 text-xs">
                              {isUnexpected
                                ? <span className="text-amber-600 dark:text-amber-400/80 w-36 shrink-0">⚠ {field}</span>
                                : <span className={`w-36 shrink-0 ${isPredicted ? "text-orange-500 dark:text-orange-400/60" : "text-ks-text2"}`}>{field}</span>
                              }
                              <span className="text-red-600 dark:text-red-400/60 line-through max-w-[140px] truncate">{String(val.before ?? "—")}</span>
                              <span className="text-ks-text3">→</span>
                              <span className={`max-w-[160px] truncate ${isUnexpected ? "text-amber-600 dark:text-amber-400/80" : isPredicted ? "text-orange-500 dark:text-orange-400/70" : "text-emerald-600 dark:text-emerald-400/80"}`}>
                                {String(val.after ?? "—")}
                              </span>
                              {isPredicted && <span className="text-orange-400/60 text-[10px]">predicted</span>}
                              {isUnexpected && !isPredicted && <span className="text-amber-500/70 text-[10px]">business rule</span>}
                            </div>
                          );
                        })}
                      </div>
                    )}
                    {row.status === "protected" && (
                      <div className="ml-5 text-xs text-ks-text3">not executed — circuit breaker halted expansion</div>
                    )}
                    {row.status === "blocked" && (
                      <div className="ml-5 text-xs text-ks-text3">not executed — blocked by policy</div>
                    )}
                  </div>
                );
              })}
            </Card>
          )}
        </Section>
      )}

      {/* ── Record Timeline ── */}
      {(executions.length > 0 || action.status === "observed") && diffs.length > 0 && (
        <Section
          title="Record Timeline"
          sub="Before the agent ran · During canary · After full execution"
          action={
            !timeline ? (
              <button
                disabled={timelineLoading}
                onClick={async () => {
                  setTimelineLoading(true);
                  try { setTimeline(await fetchRecordTimeline(id)); }
                  catch { /* silently fail */ }
                  finally { setTimelineLoading(false); }
                }}
                className="text-xs text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-950 px-3 py-1.5 rounded-lg hover:underline transition"
              >
                {timelineLoading ? "Loading..." : "Show before / after"}
              </button>
            ) : (
              <div className="flex items-center gap-3">
                {timeline.has_verified_snapshots && (
                  <span className="text-[11px] text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950 px-2 py-0.5 rounded font-medium">
                    Verified from ServiceNow
                  </span>
                )}
                <button onClick={() => setTimeline(null)} className="text-xs text-ks-text3 hover:text-ks-text2 transition">hide</button>
              </div>
            )
          }
        >
          {timeline && (
            <Card className="overflow-hidden">
              <div className="grid grid-cols-[130px_80px_1fr] border-b border-ks-border px-4 py-2 bg-ks-surface-2">
                <div className="text-[10px] text-ks-text3 font-semibold uppercase tracking-wide">Record</div>
                <div className="text-[10px] text-ks-text3 font-semibold uppercase tracking-wide">Phase</div>
                <div className="text-[10px] text-ks-text3 font-semibold uppercase tracking-wide">
                  {timeline.changes_intended.join(", ")}
                  <span className="text-ks-text3 normal-case font-normal ml-1">Before → After</span>
                </div>
              </div>
              {(timeline.records || []).map((rec: any, i: number) => {
                const phCfg: Record<string, { label: string; dot: string; text: string }> = {
                  canary:    { label: "CANARY",    dot: "bg-sky-500",     text: "text-sky-600 dark:text-sky-400" },
                  expand:    { label: "EXPAND",    dot: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400" },
                  protected: { label: "PROTECTED", dot: "bg-gray-400",    text: "text-ks-text3" },
                  blocked:   { label: "BLOCKED",   dot: "bg-red-500",     text: "text-red-600 dark:text-red-400" },
                };
                const cfg = phCfg[rec.phase] || { label: rec.phase, dot: "bg-gray-400", text: "text-ks-text2" };
                const wasExecuted = rec.phase === "canary" || rec.phase === "expand";
                const allFields = new Set([...Object.keys(rec.before || {}), ...Object.keys(rec.after || {})]);
                const intendedSet = new Set(timeline.changes_intended);
                return (
                  <div key={rec.sys_id} className={`grid grid-cols-[130px_80px_1fr] border-b border-ks-border last:border-0 px-4 py-3 ${i % 2 === 1 ? "bg-ks-surface-2" : ""}`}>
                    <div className="flex flex-col justify-center">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-mono text-indigo-600 dark:text-indigo-400 font-medium">{rec.number}</span>
                        {rec.verified && wasExecuted && (
                          <span className="text-[9px] text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950 px-1 py-0.5 rounded font-bold">✓</span>
                        )}
                      </div>
                      {snowUrl && wasExecuted && (
                        <a href={`${snowUrl}/incident.do?sys_id=${rec.sys_id}`} target="_blank" rel="noopener noreferrer"
                          className="text-[10px] text-sky-600 dark:text-sky-500/60 hover:underline mt-0.5">verify ↗</a>
                      )}
                      {rec.error && <span className="text-[10px] text-red-600 dark:text-red-400/70 mt-0.5">{rec.error.slice(0, 40)}</span>}
                    </div>
                    <div className="flex items-center gap-1.5">
                      <div className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                      <span className={`text-[10px] font-semibold ${cfg.text}`}>{cfg.label}</span>
                    </div>
                    <div className="space-y-0.5">
                      {Array.from(allFields).map((field: string) => {
                        const bef = rec.before?.[field];
                        const aft = rec.after?.[field];
                        const isUnexpected = rec.unexpected_fields?.includes(field);
                        return (
                          <div key={field} className="flex items-center gap-2 text-xs">
                            <span className={`shrink-0 w-32 ${isUnexpected ? "text-amber-600 dark:text-amber-400/80" : "text-ks-text2"}`}>
                              {isUnexpected && <span className="text-amber-500 mr-1">⚠</span>}
                              {field}
                            </span>
                            {wasExecuted ? (
                              <>
                                <span className="text-red-600 dark:text-red-400/60 line-through max-w-[120px] truncate">{String(bef ?? "—")}</span>
                                <span className="text-ks-text3">→</span>
                                {intendedSet.has(field)
                                  ? <span className="text-emerald-600 dark:text-emerald-400/80 max-w-[140px] truncate">{String(aft ?? "—")}</span>
                                  : <span className="text-amber-600 dark:text-amber-400/70 max-w-[140px] truncate">{String(aft ?? "—")} <span className="text-amber-500/50 text-[10px]">unexpected</span></span>
                                }
                              </>
                            ) : (
                              <>
                                <span className="text-ks-text2 max-w-[120px] truncate">{String(bef ?? "—")}</span>
                                {rec.phase === "protected" && <span className="text-ks-text3 text-[10px]">(not executed)</span>}
                              </>
                            )}
                          </div>
                        );
                      })}
                      {wasExecuted && allFields.size === 0 && (
                        <span className="text-xs text-ks-text3">no field changes recorded</span>
                      )}
                    </div>
                  </div>
                );
              })}
              <div className="px-4 py-2 bg-ks-surface-2 border-t border-ks-border flex items-center justify-between">
                <div className="flex items-center gap-4 text-[10px] text-ks-text3">
                  {timeline.phase_counts?.canary > 0 && <span><span className="text-sky-600 dark:text-sky-400">{timeline.phase_counts.canary}</span> canary</span>}
                  {timeline.phase_counts?.expand > 0 && <span><span className="text-emerald-600 dark:text-emerald-400">{timeline.phase_counts.expand}</span> expanded</span>}
                  {timeline.phase_counts?.protected > 0 && <span><span className="text-ks-text2">{timeline.phase_counts.protected}</span> protected</span>}
                  {timeline.phase_counts?.blocked > 0 && <span><span className="text-red-600 dark:text-red-400">{timeline.phase_counts.blocked}</span> blocked</span>}
                </div>
                {timeline.has_verified_snapshots && (
                  <span className="text-[10px] text-ks-text3">✓ = real values from live system</span>
                )}
              </div>
            </Card>
          )}
        </Section>
      )}

      {/* ── Safety Checks ── */}
      {checks.length > 0 && (
        <Section title="Safety Checks">
          <Card className="divide-y divide-ks-border overflow-hidden">
            {checks.map((c: any, i: number) => {
              const passed = c.passed === 1 || c.passed === true;
              return (
                <div key={i} className={`flex items-center justify-between px-4 py-2.5 ${!passed ? "bg-red-50 dark:bg-red-950/30" : ""}`}>
                  <div className="flex items-center gap-2.5">
                    <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${passed ? "bg-emerald-500" : "bg-red-500"}`} />
                    <span className={`text-xs ${passed ? "text-ks-text" : "text-red-700 dark:text-red-400"}`}>
                      {(c.check_name || "").replace(/_/g, " ")}
                    </span>
                  </div>
                  <span className={`text-[11px] font-semibold ${passed ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
                    {passed ? "Passed" : "Failed"}
                  </span>
                </div>
              );
            })}
          </Card>
        </Section>
      )}

      {/* ── Event Timeline ── */}
      <Section title="Event Log">
        <Card className="overflow-hidden">
          <div className="px-4 py-2.5 border-b border-ks-border bg-ks-surface-2">
            <span className="text-[11px] font-medium text-ks-text3">{(events || []).length} events</span>
          </div>
          <div className="p-4">
            <VerticalTimeline events={events || []} />
          </div>
        </Card>
      </Section>

      {/* ── Action Parameters ── */}
      <Section title="Transaction Parameters">
        <Card className="divide-y divide-ks-border overflow-hidden">
          {[
            { label: "Connector", value: actionParams.connector || "unknown", mono: false },
            { label: "Environment", value: action.environment, mono: false },
            { label: "Mode", value: action.mode || "enforce", mono: false },
            ...(actionParams.query && Object.keys(actionParams.query).length > 0 ? [{ label: "Query", value: JSON.stringify(actionParams.query), mono: true }] : []),
            ...(actionParams.changes && Object.keys(actionParams.changes).length > 0 ? [{ label: "Changes", value: JSON.stringify(actionParams.changes), mono: true }] : []),
            { label: "Preview hash", value: pr.preview_hash || "—", mono: true, highlight: true },
            { label: "Action ID", value: id, mono: true },
          ].map((row, i) => (
            <div key={i} className="flex items-start gap-4 px-4 py-2.5">
              <span className="text-[11px] text-ks-text3 w-24 shrink-0 pt-0.5">{row.label}</span>
              <span className={`text-[11px] break-all ${row.mono ? "font-mono" : ""} ${(row as any).highlight ? "text-indigo-600 dark:text-indigo-400" : "text-ks-text"}`}>
                {row.value}
              </span>
            </div>
          ))}
        </Card>
      </Section>

    </div>
  );
}
