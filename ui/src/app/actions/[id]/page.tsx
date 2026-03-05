"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { fetchAction, approveAction, executeAction, denyAction, rerunAction, fetchApprovers } from "@/lib/api";
import { Badge, parseJson } from "@/lib/components";
import Link from "next/link";

/* ── Status / Decision helpers ────────────────────── */
function statusBadge(s: string) {
  const m: Record<string, [string, string]> = {
    completed: ["green", "Completed"], blocked: ["red", "Blocked"],
    contained: ["amber", "Contained"], observed: ["sky", "Dry Run"],
    awaiting_approval: ["violet", "Awaiting Approval"], approved: ["green", "Approved"],
  };
  const [c, l] = m[s] || ["gray", s];
  return <Badge color={c}>{l}</Badge>;
}

/* ── Lifecycle Steps ──────────────────────────────── */
function Lifecycle({ events, status }: { events: any[]; status: string }) {
  const types = (events || []).map((e: any) => e.type || "");

  type S = "done" | "active" | "fail" | "skip" | "wait";

  function getApproval(): S {
    if (types.some(t => t.includes("approval.recorded"))) return "done";
    if (types.some(t => t.includes("approval.denied"))) return "fail";
    if (status === "awaiting_approval") return "active";
    return "skip";
  }
  function getCanary(): S {
    if (types.some(t => t.includes("breaker.tripped"))) return "fail";
    if (types.some(t => t.includes("canary.completed"))) return "done";
    if (types.some(t => t.includes("canary.started"))) return "active";
    if (status === "blocked" || status === "observed") return "skip";
    return "wait";
  }
  function getExpand(): S {
    if (status === "contained") return "fail";
    if (types.some(t => t.includes("expand.completed"))) return "done";
    if (types.some(t => t.includes("expand.started"))) return "active";
    if (["blocked", "observed", "contained"].includes(status)) return "skip";
    return "wait";
  }

  const steps: { label: string; state: S; desc: string }[] = [
    { label: "Preview", state: types.some(t => t.includes("preview")) ? "done" : "wait", desc: "Blast radius computed" },
    { label: "Policy", state: types.some(t => t.includes("decision")) ? "done" : "wait", desc: "Rules evaluated" },
    { label: "Approval", state: getApproval(), desc: getApproval() === "skip" ? "Not required" : getApproval() === "done" ? "Human approved" : getApproval() === "fail" ? "Denied" : "Pending" },
    { label: "Canary", state: getCanary(), desc: getCanary() === "done" ? "Test batch OK" : getCanary() === "fail" ? "Anomaly detected" : getCanary() === "skip" ? "Skipped" : "Pending" },
    { label: "Expand", state: getExpand(), desc: getExpand() === "done" ? "All records updated" : getExpand() === "fail" ? "Halted by breaker" : getExpand() === "skip" ? "Not reached" : "Pending" },
    { label: "Receipt", state: types.some(t => t.includes("proof")) ? "done" : "wait", desc: "Audit proof signed" },
  ];

  const dotColor: Record<S, string> = {
    done: "bg-emerald-500", active: "bg-sky-500 animate-pulse", fail: "bg-red-500", skip: "bg-gray-700", wait: "bg-gray-800",
  };
  const textColor: Record<S, string> = {
    done: "text-emerald-300", active: "text-sky-300", fail: "text-red-300", skip: "text-gray-500", wait: "text-gray-600",
  };
  const descColor: Record<S, string> = {
    done: "text-emerald-400/50", active: "text-sky-400/50", fail: "text-red-400/50", skip: "text-gray-600", wait: "text-gray-700",
  };

  return (
    <div className="flex items-start justify-between">
      {steps.map((step, i) => (
        <div key={step.label} className="flex items-start flex-1">
          <div className="flex flex-col items-center text-center" style={{ minWidth: "60px" }}>
            <div className={`w-3.5 h-3.5 rounded-full ${dotColor[step.state]} ring-2 ring-offset-2 ring-offset-[#0a0a0f] ${
              step.state === "done" ? "ring-emerald-500/30" : step.state === "fail" ? "ring-red-500/30" : step.state === "active" ? "ring-sky-500/30" : "ring-transparent"
            }`} />
            <span className={`text-[11px] mt-2 font-semibold ${textColor[step.state]}`}>{step.label}</span>
            <span className={`text-[9px] mt-0.5 ${descColor[step.state]}`}>{step.desc}</span>
          </div>
          {i < steps.length - 1 && (
            <div className={`flex-1 h-px mt-[7px] mx-1 ${step.state === "done" ? "bg-emerald-500/30" : "bg-gray-800"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

/* ── Vertical Timeline ────────────────────────────── */
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
    case "action.created": return p.mode ? `Mode: ${p.mode}` : "";
    case "preview.generated": return `${p.blast_radius || "?"} records | hash: ${(p.preview_hash || "").slice(0, 12)}...`;
    case "decision.made": return `${p.decision || "?"} | rules: ${(p.matched_rules || []).join(", ") || "default"}`;
    case "canary.started": return `${(p.subset || []).length || "?"} records selected`;
    case "canary.completed": return `${p.count || "?"} records | error rate: ${((p.error_rate || 0) * 100).toFixed(1)}%`;
    case "checks.completed": {
      const r = p.results || {};
      const pass = Object.values(r).filter(v => v === true).length;
      const tot = Object.keys(r).length;
      const fail = Object.entries(r).filter(([, v]) => !v).map(([k]) => k.replace(/_/g, " "));
      return fail.length > 0 ? `${pass}/${tot} passed | failed: ${fail.join(", ")}` : `All ${tot} passed`;
    }
    case "breaker.tripped": return (p.reason || "").slice(0, 100);
    case "expand.started": case "expand.completed": return `${p.count || "?"} records`;
    case "approval.recorded": return `${p.approver || "unknown"} via ${p.channel || "?"}`;
    case "proof.generated": return `sig: ${p.signature_prefix || "?"}...`;
    default: return "";
  }
}

function VerticalTimeline({ events }: { events: any[] }) {
  const dotColor: Record<EventKind, string> = {
    success: "bg-emerald-500 border-emerald-500",
    error: "bg-red-500 border-red-500",
    warning: "bg-amber-500 border-amber-500",
    info: "bg-sky-500 border-sky-500",
    neutral: "bg-gray-600 border-gray-600",
  };
  const labelColor: Record<EventKind, string> = {
    success: "text-emerald-300",
    error: "text-red-300",
    warning: "text-amber-300",
    info: "text-sky-300",
    neutral: "text-gray-300",
  };
  const summaryColor: Record<EventKind, string> = {
    success: "text-emerald-300/50",
    error: "text-red-300/50",
    warning: "text-amber-300/50",
    info: "text-sky-300/50",
    neutral: "text-gray-500",
  };

  return (
    <div className="relative ml-3">
      {/* Straight vertical line */}
      <div className="absolute left-[5px] top-0 bottom-0 w-px bg-gray-800" />

      {events.map((e: any, i: number) => {
        const t = e.type || "";
        const cfg = EVENT_MAP[t] || { label: t, kind: "neutral" as EventKind };
        const payload = e.payload_json || {};

        let kind = cfg.kind;
        if (t === "checks.completed") {
          const results = payload.results || {};
          kind = Object.values(results).some(v => v === false) ? "error" : "success";
        }

        const summary = getEventSummary(t, payload);

        return (
          <div key={i} className="relative flex items-start gap-4 pb-5 last:pb-0">
            {/* Circle on the line */}
            <div className={`relative z-10 w-[11px] h-[11px] rounded-full border-2 ${dotColor[kind]} shrink-0 mt-0.5`} />

            {/* Content */}
            <div className="flex-1 min-w-0 -mt-0.5">
              <div className="flex items-center gap-3">
                <span className={`text-sm font-medium ${labelColor[kind]}`}>{cfg.label}</span>
                <span className="text-[10px] text-gray-600 font-mono">{e.created_at}</span>
              </div>
              {summary && (
                <p className={`text-xs mt-0.5 ${summaryColor[kind]}`}>{summary}</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Main Page ────────────────────────────────────── */
export default function ActionDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showDiffs, setShowDiffs] = useState(false);
  const [approverName, setApproverName] = useState("");
  const [approving, setApproving] = useState(false);
  const [denying, setDenying] = useState(false);
  const [actionError, setActionError] = useState("");
  const [running, setRunning] = useState(false);
  const [employeeId, setEmployeeId] = useState("");
  const [approvers, setApprovers] = useState<any[]>([]);

  useEffect(() => { fetchAction(id).then(setData).finally(() => setLoading(false)); }, [id]);
  useEffect(() => { fetchApprovers().then(setApprovers).catch(() => {}); }, []);

  if (loading) return <div className="py-20 text-center text-gray-500">Loading...</div>;
  if (!data) return <div className="py-20 text-center text-red-400">Action not found</div>;

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

  // Check if this dry run was already executed
  const executedAsEvent = (events || []).find((e: any) => e.type === "dryrun.executed_as");
  const childActionId = executedAsEvent?.payload_json?.child_action_id;
  // Check if this action came from a dry run
  const createdEvent = (events || []).find((e: any) => e.type === "action.created");
  const parentDryRunId = createdEvent?.payload_json?.parent_dry_run;

  const decisionLabel: Record<string, string> = {
    AUTO: "Auto-Approved", CANARY: "Canary Required",
    BLOCK: "Blocked", APPROVAL_REQUIRED: "Approval Required",
  };
  const decisionColor: Record<string, string> = {
    AUTO: "text-emerald-300 bg-emerald-500/15 border-emerald-500/30",
    CANARY: "text-sky-300 bg-sky-500/15 border-sky-500/30",
    BLOCK: "text-red-300 bg-red-500/15 border-red-500/30",
    APPROVAL_REQUIRED: "text-violet-300 bg-violet-500/15 border-violet-500/30",
  };

  return (
    <div className="max-w-3xl mx-auto">
      {/* Nav */}
      <div className="flex items-center gap-2 mb-6 text-sm">
        <Link href="/" className="text-gray-500 hover:text-gray-300 transition">Actions</Link>
        <span className="text-gray-700">/</span>
        <span className="text-gray-400 font-mono text-xs">{id}</span>
      </div>

      {/* ── Header ── */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-xl font-bold text-white">{action.tool}.{action.action_type}</h1>
            {statusBadge(action.status)}
          </div>
          <div className="text-sm text-gray-400">
            {actor.name || "Unknown"} ({actor.type}) · {action.environment} · {action.mode === "observe_only" ? "observe only" : "enforce"}
          </div>
        </div>
        <Link href={`/actions/${id}/proof`}
          className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition shrink-0">
          Audit Receipt
        </Link>
      </div>

      {/* ── Parent dry run link ── */}
      {parentDryRunId && (
        <div className="mb-4 rounded-lg border border-gray-800 bg-gray-900/30 px-4 py-3 flex items-center justify-between">
          <div className="text-sm text-gray-300">
            Executed from dry run <span className="font-mono text-xs text-indigo-400">{parentDryRunId}</span>
          </div>
          <Link href={`/actions/${parentDryRunId}`} className="text-xs text-indigo-400 hover:text-indigo-300 transition">
            View dry run
          </Link>
        </div>
      )}

      

      {/* ── Alert Banners ── */}
      {isContained && (
        <div className="mb-6 rounded-lg border border-amber-500/30 bg-amber-500/5 px-5 py-4">
          <div className="text-sm font-semibold text-amber-300 mb-1">Runtime Containment Activated</div>
          <div className="text-sm text-amber-200/60">
            Canary ran on {canaryIds.length} records and detected unexpected field changes.
            Expansion to remaining {recordsMatched - canaryIds.length} records was halted automatically.
          </div>
        </div>
      )}
      {isBlocked && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/5 px-5 py-4">
          <div className="text-sm font-semibold text-red-300 mb-1">Blocked by Policy</div>
          <div className="text-sm text-red-200/60">
            Policy prevented execution. Zero records were modified.
          </div>
        </div>
      )}

      {/* ── Observed Banner ── */}
      {action.status === "observed" && (
        <div className="mb-6 rounded-lg border border-sky-500/30 bg-sky-500/5 px-5 py-4">
          <div className="text-sm font-semibold text-sky-300 mb-1">Dry Run Result</div>
          <div className="text-sm text-sky-200/60 mb-4">
            No records were modified. Below is what would happen if this action ran for real.
          </div>

          <div className="space-y-3">
            {/* What would be affected */}
            <div className="bg-gray-900/40 rounded-lg px-4 py-3">
              <div className="text-xs text-gray-400 mb-1">Would affect</div>
              <div className="text-lg font-bold text-white">{recordsMatched} records</div>
              {br.breakdowns?.by_priority && (
                <div className="flex gap-2 mt-1 flex-wrap">
                  {Object.entries(br.breakdowns.by_priority).map(([k, v]) => (
                    <span key={k} className="text-xs text-gray-300 bg-gray-800 px-2 py-0.5 rounded">{k}: {v as number}</span>
                  ))}
                </div>
              )}
            </div>

            {/* What would change */}
            {Object.keys(fieldSummary).length > 0 && (
              <div className="bg-gray-900/40 rounded-lg px-4 py-3">
                <div className="text-xs text-gray-400 mb-2">Would change</div>
                {Object.entries(fieldSummary).map(([field, info]) => (
                  <div key={field} className="flex items-center gap-3 text-sm mb-1">
                    <span className="text-white font-medium">{field}</span>
                    <span className="text-red-400/70 line-through text-xs">{String(info.before)}</span>
                    <span className="text-gray-600 text-xs">to</span>
                    <span className="text-emerald-400 text-xs">{String(info.after)}</span>
                    <span className="text-gray-500 text-xs ml-auto">on {info.count} records</span>
                  </div>
                ))}
              </div>
            )}

            {/* Policy result */}
            <div className="bg-gray-900/40 rounded-lg px-4 py-3">
              <div className="text-xs text-gray-400 mb-2">Policy would decide</div>
              <div className="flex items-center gap-3">
                <span className={`px-3 py-1 rounded-lg text-sm font-bold border ${decisionColor[dec.decision] || "text-gray-300 bg-gray-800 border-gray-700"}`}>
                  {decisionLabel[dec.decision] || dec.decision}
                </span>
                {dec.decision === "BLOCK" && <span className="text-sm text-red-300">This action would be blocked</span>}
                {dec.decision === "CANARY" && <span className="text-sm text-sky-300">This action would require canary testing first</span>}
                {dec.decision === "AUTO" && <span className="text-sm text-emerald-300">This action would be auto-approved</span>}
                {dec.decision === "APPROVAL_REQUIRED" && <span className="text-sm text-violet-300">This action would need human approval</span>}
              </div>
            </div>

            {/* Risk flags */}
            {Object.entries(flags || {}).some(([, v]) => v === true) && (
              <div className="bg-gray-900/40 rounded-lg px-4 py-3">
                <div className="text-xs text-gray-400 mb-2">Risk flags detected</div>
                <div className="flex gap-2 flex-wrap">
                  {Object.entries(flags || {}).filter(([, v]) => typeof v === "boolean" && v === true).map(([k]) => {
                    const flagLabels: Record<string, string> = {
                      has_p1: "P1 Critical", has_p2: "P2 High", has_vip: "VIP Caller",
                      cross_group: "Cross-Group", state_transition: "State Transition",
                    };
                    const flagColors: Record<string, string> = {
                      has_p1: "red", has_p2: "amber", has_vip: "violet",
                      cross_group: "sky", state_transition: "gray",
                    };
                    return <Badge key={k} color={flagColors[k] || "gray"}>{flagLabels[k] || k.replace(/_/g, " ")}</Badge>;
                  })}
                </div>
              </div>
            )}

            {/* Run for real button */}
            <div className="bg-gray-900/40 rounded-lg px-4 py-3">
              {childActionId ? (
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm text-emerald-300 font-medium">Executed</div>
                    <div className="text-xs text-gray-400 mt-0.5">This dry run was executed as a real action.</div>
                  </div>
                  <Link href={`/actions/${childActionId}`}
                    className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition">
                    View Execution
                  </Link>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm text-white font-medium">Ready to execute?</div>
                    <div className="text-xs text-gray-400 mt-0.5">
                      {dec.decision === "CANARY" && "This will run a canary test on 5 records first, then expand if all safety checks pass."}
                      {dec.decision === "AUTO" && "This will execute on all matched records with safety checks."}
                      {dec.decision === "BLOCK" && "This action would be blocked by policy. It cannot be executed."}
                      {dec.decision === "APPROVAL_REQUIRED" && "This will require human approval before execution begins."}
                    </div>
                  </div>
                  <button
                    disabled={running || dec.decision === "BLOCK"}
                    onClick={async () => {
                      setRunning(true);
                      setActionError("");
                      try {
                        const result = await rerunAction(id);
                        window.location.href = `/actions/${result.action_id}`;
                      } catch (e: any) {
                        setActionError(e.message || "Failed to run");
                        setRunning(false);
                      }
                    }}
                    className={`px-5 py-2.5 rounded-lg text-sm font-medium transition shrink-0 ${
                      dec.decision === "BLOCK"
                        ? "bg-gray-700 text-gray-500 cursor-not-allowed"
                        : "bg-emerald-600 hover:bg-emerald-500 text-white"
                    }`}
                  >
                    {running ? "Running..." : dec.decision === "BLOCK" ? "Blocked by Policy" : "Run for Real"}
                  </button>
                </div>
              )}
              {actionError && <div className="mt-2 text-xs text-red-400">{actionError}</div>}
            </div>
          </div>
        </div>
      )}

      {/* ── Approval Panel ── */}
      {action.status === "awaiting_approval" && (
        <div className="mb-6 rounded-lg border border-violet-500/30 bg-violet-500/5 px-5 py-5">
          <div className="text-sm font-semibold text-violet-300 mb-1">Approval Required</div>
          <div className="text-sm text-violet-200/60 mb-4">
            This action requires human approval. Enter your Employee ID to approve or deny.
          </div>

          {/* Authorized approvers list */}
          {approvers.length > 0 && (
            <div className="mb-4 bg-gray-900/40 rounded-lg px-4 py-3">
              <div className="text-xs text-gray-400 mb-2">Authorized approvers</div>
              <div className="space-y-1">
                {approvers.map((a: any) => (
                  <div key={a.employee_id} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">{a.name}</span>
                      <span className="text-gray-500">{a.designation}</span>
                    </div>
                    <span className="text-gray-600 font-mono">{a.employee_id}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="text-xs text-gray-400 block mb-1">Employee ID</label>
              <input
                type="text"
                value={employeeId}
                onChange={(e) => { setEmployeeId(e.target.value); setActionError(""); }}
                placeholder="e.g. EMP001"
                className="w-full px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-sm text-white placeholder-gray-600 focus:border-violet-500 focus:outline-none font-mono"
              />
            </div>
            <button
              disabled={!employeeId.trim() || approving || denying}
              onClick={async () => {
                setApproving(true);
                setActionError("");
                try {
                  await approveAction(id, employeeId.trim());
                  await executeAction(id);
                  const fresh = await fetchAction(id);
                  setData(fresh);
                } catch (e: any) {
                  setActionError(e.message || "Approval failed");
                } finally {
                  setApproving(false);
                }
              }}
              className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium transition"
            >
              {approving ? "Approving..." : "Approve"}
            </button>
            <button
              disabled={!employeeId.trim() || approving || denying}
              onClick={async () => {
                setDenying(true);
                setActionError("");
                try {
                  await denyAction(id, employeeId.trim());
                  const fresh = await fetchAction(id);
                  setData(fresh);
                } catch (e: any) {
                  setActionError(e.message || "Deny failed");
                } finally {
                  setDenying(false);
                }
              }}
              className="px-5 py-2 rounded-lg bg-red-600 hover:bg-red-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium transition"
            >
              {denying ? "Denying..." : "Deny"}
            </button>
          </div>
          {actionError && (
            <div className="mt-2 text-sm text-red-400 bg-red-500/5 border border-red-500/20 rounded-lg px-3 py-2">{actionError}</div>
          )}
        </div>
      )}

      {/* ── Lifecycle ── */}
      <div className="mb-8">
        <Lifecycle events={events || []} status={action.status} />
      </div>

      {/* ── Key Numbers ── */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="rounded-lg border border-gray-800 bg-gray-900/40 px-4 py-4">
          <div className="text-3xl font-bold text-white">{recordsMatched}</div>
          <div className="text-xs text-gray-300 mt-1">Records Matched</div>
          <div className="text-[10px] text-gray-500 mt-0.5">How many records the query found</div>
        </div>
        <div className="rounded-lg border border-gray-800 bg-gray-900/40 px-4 py-4">
          <div className={`text-3xl font-bold ${isBlocked ? "text-gray-600" : isContained ? "text-amber-400" : "text-emerald-400"}`}>
            {isBlocked ? 0 : recordsChanged}
          </div>
          <div className="text-xs text-gray-300 mt-1">Records Changed</div>
          <div className="text-[10px] text-gray-500 mt-0.5">How many were actually modified</div>
        </div>
        <div className="rounded-lg border border-gray-800 bg-gray-900/40 px-4 py-4">
          <div className={`text-3xl font-bold ${
            checks.length === 0 ? "text-gray-600" :
            checks.every((c: any) => c.passed === 1 || c.passed === true) ? "text-emerald-400" : "text-red-400"
          }`}>
            {checks.length === 0 ? "---" : `${checks.filter((c: any) => c.passed === 1 || c.passed === true).length}/${checks.length}`}
          </div>
          <div className="text-xs text-gray-300 mt-1">Safety Checks</div>
          <div className="text-[10px] text-gray-500 mt-0.5">Post-execution verification results</div>
        </div>
      </div>

      {/* ── Policy Decision ── */}
      <div className="mb-8">
        <h2 className="text-sm font-semibold text-white mb-3">Policy Decision</h2>
        <div className="rounded-lg border border-gray-800 bg-gray-900/30 p-5">
          <div className="flex items-center gap-3 mb-4">
            <span className={`px-3 py-1.5 rounded-lg text-sm font-bold border ${decisionColor[dec.decision] || "text-gray-300 bg-gray-800 border-gray-700"}`}>
              {decisionLabel[dec.decision] || dec.decision || "Unknown"}
            </span>
            <span className="text-xs text-gray-400">Policy v{dec.policy_version} | {dec.policy_id}</span>
          </div>
          {reasons.length > 0 && (
            <div className="space-y-2">
              {reasons.map((r: any, i: number) => (
                <div key={i} className="bg-gray-800/40 rounded-lg px-4 py-3">
                  <div className="text-xs text-gray-500 font-mono mb-1">{r.rule}</div>
                  <div className="text-sm text-gray-200">{(r.reason || "").replace(/\u00e2\u0080\u0094|\u00e2\u0080\u0093|â€"|â€"/g, " -- ")}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Approvals ── */}
      {approvals.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-white mb-3">Approvals</h2>
          {approvals.map((a: any, i: number) => {
            const ap = a.approver_json || {};
            return (
              <div key={i} className="rounded-lg border border-gray-800 bg-gray-900/30 p-4 flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-300 font-bold">
                  {(ap.name || "?")[0].toUpperCase()}
                </div>
                <div>
                  <div className="text-sm text-white font-medium">{ap.name || "Unknown"}</div>
                  {ap.designation && <div className="text-xs text-gray-400">{ap.designation}{ap.department ? ` | ${ap.department}` : ""}</div>}
                  <div className="text-xs text-gray-500">
                    via {a.channel} | hash: {(a.preview_hash || "").slice(0, 12)}... | policy v{a.policy_version}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Changes ── */}
      {Object.keys(fieldSummary).length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white">Changes</h2>
            {diffs.length > 0 && (
              <button onClick={() => setShowDiffs(!showDiffs)} className="text-xs text-indigo-400 hover:text-indigo-300 transition">
                {showDiffs ? "Hide record details" : `Show ${diffs.length} record details`}
              </button>
            )}
          </div>
          <div className="rounded-lg border border-gray-800 bg-gray-900/30 divide-y divide-gray-800/50">
            {Object.entries(fieldSummary).map(([field, info]) => (
              <div key={field} className="flex items-center justify-between px-5 py-3">
                <div className="flex items-center gap-4">
                  <span className="text-sm text-white font-medium w-40">{field}</span>
                  <span className="text-sm text-red-400/70 line-through">{String(info.before)}</span>
                  <span className="text-gray-600 text-xs">to</span>
                  <span className="text-sm text-emerald-400">{String(info.after)}</span>
                </div>
                <span className="text-xs text-gray-400">{info.count} records</span>
              </div>
            ))}
          </div>

          {unexpectedFields.size > 0 && (
            <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-3">
              <div className="text-xs font-semibold text-red-300 mb-1">Unexpected field changes detected</div>
              <div className="flex gap-2 flex-wrap">
                {Array.from(unexpectedFields).map(f => (
                  <span key={f} className="text-xs bg-red-500/10 border border-red-500/25 text-red-300 px-2 py-0.5 rounded">{f}</span>
                ))}
              </div>
            </div>
          )}

          {showDiffs && (
            <div className="mt-3 rounded-lg border border-gray-800 bg-gray-900/30 p-4 max-h-64 overflow-y-auto space-y-1">
              {diffs.map((d: any, i: number) => (
                <div key={i} className="text-xs bg-gray-800/30 rounded px-3 py-2">
                  <span className="font-mono text-indigo-400">{d.number}</span>
                  <span className="text-gray-600 ml-2">{d.sys_id}</span>
                  {Object.entries(d.fields || {}).map(([f, v]: [string, any]) => (
                    <div key={f} className="flex gap-2 ml-3 mt-0.5">
                      <span className="text-gray-400 w-28">{f}</span>
                      <span className="text-red-400/50 line-through">{String(v.before)}</span>
                      <span className="text-gray-600">to</span>
                      <span className="text-emerald-400/80">{String(v.after)}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Safety Checks ── */}
      {checks.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-white mb-3">Safety Checks</h2>
          <div className="rounded-lg border border-gray-800 bg-gray-900/30 divide-y divide-gray-800/50">
            {checks.map((c: any, i: number) => {
              const passed = c.passed === 1 || c.passed === true;
              return (
                <div key={i} className={`flex items-center justify-between px-5 py-3 ${!passed ? "bg-red-500/5" : ""}`}>
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${passed ? "bg-emerald-500" : "bg-red-500"}`} />
                    <span className={`text-sm ${passed ? "text-gray-200" : "text-red-300"}`}>
                      {(c.check_name || "").replace(/_/g, " ")}
                    </span>
                  </div>
                  <span className={`text-xs font-semibold ${passed ? "text-emerald-400" : "text-red-400"}`}>
                    {passed ? "PASSED" : "FAILED"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Event Timeline ── */}
      <div className="mb-8">
        <h2 className="text-sm font-semibold text-white mb-3">
          Event Timeline <span className="text-gray-500 font-normal">({(events || []).length} events)</span>
        </h2>
        <div className="rounded-lg border border-gray-800 bg-gray-900/30 p-5">
          <VerticalTimeline events={events || []} />
        </div>
      </div>

      {/* ── Action Parameters ── */}
      <div className="mb-8">
        <h2 className="text-sm font-semibold text-white mb-3">Action Parameters</h2>
        <div className="rounded-lg border border-gray-800 bg-gray-900/30 p-4 text-xs space-y-2">
          <div className="flex gap-3">
            <span className="text-gray-500 w-24 shrink-0">Connector</span>
            <span className="text-gray-200">{actionParams.connector || "unknown"}</span>
          </div>
          {actionParams.query && Object.keys(actionParams.query).length > 0 && (
            <div className="flex gap-3">
              <span className="text-gray-500 w-24 shrink-0">Query</span>
              <span className="text-gray-200 font-mono break-all">{JSON.stringify(actionParams.query)}</span>
            </div>
          )}
          {actionParams.changes && Object.keys(actionParams.changes).length > 0 && (
            <div className="flex gap-3">
              <span className="text-gray-500 w-24 shrink-0">Changes</span>
              <span className="text-gray-200 font-mono break-all">{JSON.stringify(actionParams.changes)}</span>
            </div>
          )}
          <div className="flex gap-3">
            <span className="text-gray-500 w-24 shrink-0">Preview hash</span>
            <span className="text-indigo-300/70 font-mono">{pr.preview_hash || "---"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}