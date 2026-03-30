"use client";

/* ── Badge ──────────────────────────────────────────────────────── */
const BADGE_STYLES: Record<string, string> = {
  green:  "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-400 dark:border-emerald-800",
  red:    "bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-400 dark:border-red-800",
  amber:  "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-400 dark:border-amber-800",
  sky:    "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950 dark:text-sky-400 dark:border-sky-800",
  violet: "bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-950 dark:text-violet-400 dark:border-violet-800",
  gray:   "bg-gray-100 text-gray-600 border-gray-200 dark:bg-[#21262d] dark:text-[#8b949e] dark:border-[#30363d]",
  white:  "bg-gray-50 text-gray-700 border-gray-200 dark:bg-[#21262d] dark:text-[#e6edf3] dark:border-[#30363d]",
};

export function Badge({ color = "gray", children, className = "" }: {
  color?: string; children: React.ReactNode; className?: string;
}) {
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium border ${BADGE_STYLES[color] || BADGE_STYLES.gray} ${className}`}>
      {children}
    </span>
  );
}

/* ── Lifecycle Stepper ──────────────────────────────────────────── */
const STEPS = [
  { key: "preview",  label: "Diff" },
  { key: "policy",   label: "Gate" },
  { key: "approval", label: "Approval" },
  { key: "canary",   label: "Canary" },
  { key: "expand",   label: "Rollout" },
  { key: "receipt",  label: "Audit Log" },
];

type StepState = "done" | "active" | "failed" | "skipped" | "pending";

export function LifecycleStepper({ events, status }: { events: any[]; status: string }) {
  const types = events.map((e: any) => e.type || "");

  function getState(key: string): StepState {
    switch (key) {
      case "preview":
        return types.some((t: string) => t.includes("preview")) ? "done" : "pending";
      case "policy":
        return types.some((t: string) => t.includes("decision")) ? "done" : "pending";
      case "approval":
        if (types.some((t: string) => t.includes("approval.recorded"))) return "done";
        if (types.some((t: string) => t.includes("approval.denied"))) return "failed";
        if (status === "awaiting_approval") return "active";
        return "skipped";
      case "canary":
        if (types.some((t: string) => t.includes("breaker.tripped"))) return "failed";
        if (types.some((t: string) => t.includes("canary.completed"))) return "done";
        if (types.some((t: string) => t.includes("canary.started"))) return "active";
        if (status === "blocked") return "skipped";
        return "pending";
      case "expand":
        if (status === "contained") return "failed";
        if (types.some((t: string) => t.includes("expand.completed"))) return "done";
        if (types.some((t: string) => t.includes("expand.started"))) return "active";
        if (["blocked", "observed", "contained"].includes(status)) return "skipped";
        return "pending";
      case "receipt":
        return types.some((t: string) => t.includes("proof")) ? "done" : "pending";
      default:
        return "pending";
    }
  }

  const dotCls: Record<StepState, string> = {
    done:    "bg-emerald-500",
    active:  "bg-sky-500 ring-4 ring-sky-500/20 animate-pulse",
    failed:  "bg-red-500",
    skipped: "bg-ks-border",
    pending: "bg-ks-surface-2 border-2 border-ks-border",
  };
  const lblCls: Record<StepState, string> = {
    done:    "text-emerald-600 dark:text-emerald-400",
    active:  "text-sky-600 dark:text-sky-400",
    failed:  "text-red-600 dark:text-red-400",
    skipped: "text-ks-text3",
    pending: "text-ks-text3",
  };
  const lineCls: Record<StepState, string> = {
    done:    "bg-emerald-300 dark:bg-emerald-800",
    active:  "bg-ks-border",
    failed:  "bg-ks-border",
    skipped: "bg-ks-border",
    pending: "bg-ks-border",
  };

  return (
    <div className="flex items-center">
      {STEPS.map((step, i) => {
        const state = getState(step.key);
        return (
          <div key={step.key} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center text-center" style={{ minWidth: "64px" }}>
              <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${dotCls[state]}`} />
              <span className={`text-[10px] mt-1.5 font-medium ${lblCls[state]}`}>{step.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`flex-1 h-px mb-4 ${lineCls[state]}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ── Risk Meter ─────────────────────────────────────────────────── */
export function RiskMeter({ flags, blastRadius, environment }: {
  flags: any; blastRadius: number; environment: string;
}) {
  const factors: { label: string; score: number }[] = [];
  if (environment === "production") factors.push({ label: "Production environment", score: 3 });
  if (blastRadius > 100) factors.push({ label: `${blastRadius} records (>100)`, score: 3 });
  else if (blastRadius > 10) factors.push({ label: `${blastRadius} records (>10)`, score: 2 });
  if (flags?.has_p1) factors.push({ label: "P1 critical incidents", score: 5 });
  if (flags?.has_p2) factors.push({ label: "P2 high incidents", score: 3 });
  if (flags?.has_vip) factors.push({ label: "VIP callers affected", score: 4 });
  if (flags?.state_transition) factors.push({ label: "State transition", score: 2 });
  if (flags?.cross_group) factors.push({ label: "Cross-group impact", score: 1 });

  const total = factors.reduce((s, f) => s + f.score, 0);
  const level = total >= 8 ? "High" : total >= 4 ? "Medium" : "Low";
  const color = total >= 8 ? "text-red-600 dark:text-red-400" : total >= 4 ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400";
  const barColor = total >= 8 ? "bg-red-500" : total >= 4 ? "bg-amber-500" : "bg-emerald-500";
  const pct = Math.min(total / 15 * 100, 100);

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-sm font-semibold ${color}`}>{level} Risk</span>
        <span className="text-xs text-ks-text3">({total} pts)</span>
      </div>
      <div className="w-full h-1 bg-ks-border rounded-full overflow-hidden mb-3">
        <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="space-y-1">
        {factors.map((f, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="text-ks-text3 w-5 text-right tabular-nums">+{f.score}</span>
            <span className="text-ks-text2">{f.label}</span>
          </div>
        ))}
        {factors.length === 0 && <p className="text-xs text-ks-text3">No risk factors detected.</p>}
      </div>
    </div>
  );
}

/* ── Event Timeline ─────────────────────────────────────────────── */
interface TimelineEvent {
  type: string;
  payload_json: any;
  created_at: string;
}

type EventKind = "success" | "error" | "warning" | "info" | "neutral";

const EVENT_MAP: Record<string, { label: string; kind: EventKind }> = {
  "action.created":            { label: "Action created",              kind: "neutral" },
  "preview.generated":         { label: "Preview generated",           kind: "success" },
  "decision.made":             { label: "Policy evaluated",            kind: "success" },
  "action.blocked":            { label: "Blocked by policy",           kind: "error" },
  "action.awaiting_approval":  { label: "Awaiting human approval",     kind: "warning" },
  "slack.notification_sent":   { label: "Slack notification sent",     kind: "info" },
  "approval.recorded":         { label: "Approval recorded",           kind: "success" },
  "approval.denied":           { label: "Approval denied",             kind: "error" },
  "canary.started":            { label: "Canary started",              kind: "info" },
  "canary.completed":          { label: "Canary completed",            kind: "success" },
  "checks.completed":          { label: "Safety invariants checked",   kind: "info" },
  "breaker.tripped":           { label: "Circuit breaker tripped",     kind: "error" },
  "expand.started":            { label: "Expansion started",           kind: "info" },
  "expand.completed":          { label: "Expansion completed",         kind: "success" },
  "action.completed":          { label: "Action completed",            kind: "success" },
  "action.observed":           { label: "Observed — no execution",     kind: "info" },
  "proof.generated":           { label: "Audit receipt signed",        kind: "success" },
};

function getEventSummary(type: string, payload: any): string {
  if (!payload || typeof payload !== "object") return "";
  switch (type) {
    case "action.created":      return payload.mode ? `Mode: ${payload.mode}` : "";
    case "preview.generated":   return `${payload.blast_radius || "?"} records matched · hash: ${(payload.preview_hash || "").slice(0, 12)}...`;
    case "decision.made": {
      const rules = (payload.matched_rules || []).join(", ");
      return `${payload.decision || "?"} · rules: ${rules || "default"}`;
    }
    case "canary.started":      return `${(payload.subset || []).length || "?"} records`;
    case "canary.completed":    return `${payload.count || "?"} records · error rate: ${((payload.error_rate || 0) * 100).toFixed(1)}%`;
    case "checks.completed": {
      const r = payload.results || {};
      const passed = Object.values(r).filter(v => v === true).length;
      const total = Object.keys(r).length;
      const failed = Object.entries(r).filter(([, v]) => v === false).map(([k]) => k.replace(/_/g, " "));
      return failed.length > 0 ? `${passed}/${total} passed · failed: ${failed.join(", ")}` : `All ${total} passed`;
    }
    case "breaker.tripped":     return (payload.reason || "").slice(0, 120);
    case "expand.started":      return `${payload.count || "?"} remaining records`;
    case "expand.completed":    return `${payload.count || "?"} records · error rate: ${((payload.error_rate || 0) * 100).toFixed(1)}%`;
    case "approval.recorded":   return `By ${payload.approver || "unknown"} via ${payload.channel || "?"}`;
    case "proof.generated":     return `Signature: ${payload.signature_prefix || "?"}...`;
    default:                    return "";
  }
}

export function EventTimeline({ events }: { events: TimelineEvent[] }) {
  const kindDot: Record<EventKind, string> = {
    success: "bg-emerald-500",
    error:   "bg-red-500",
    warning: "bg-amber-500",
    info:    "bg-sky-500",
    neutral: "bg-ks-text3",
  };
  const kindLabel: Record<EventKind, string> = {
    success: "text-emerald-700 dark:text-emerald-400",
    error:   "text-red-700 dark:text-red-400",
    warning: "text-amber-700 dark:text-amber-400",
    info:    "text-sky-700 dark:text-sky-400",
    neutral: "text-ks-text",
  };

  return (
    <div className="relative pl-5">
      <div className="absolute left-[6px] top-1 bottom-1 w-px bg-ks-border" />
      {events.map((e, i) => {
        const t = e.type || "";
        const cfg = EVENT_MAP[t] || { label: t, kind: "neutral" as EventKind };
        const payload = e.payload_json || {};
        let kind = cfg.kind;
        if (t === "checks.completed") {
          kind = Object.values(payload.results || {}).some(v => v === false) ? "error" : "success";
        }
        const summary = getEventSummary(t, payload);
        return (
          <div key={i} className="relative flex items-start gap-3 pb-3.5 last:pb-0">
            <div className={`relative z-10 w-2 h-2 rounded-full shrink-0 mt-1.5 ring-2 ring-ks-surface ${kindDot[kind]}`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline gap-2 flex-wrap">
                <span className={`text-xs font-medium ${kindLabel[kind]}`}>{cfg.label}</span>
                <span className="text-[10px] text-ks-text3 font-mono shrink-0">{e.created_at}</span>
              </div>
              {summary && <p className="text-[11px] text-ks-text2 mt-0.5 leading-relaxed">{summary}</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Helpers ─────────────────────────────────────────────────────── */
export function parseJson(s: string | null | undefined) {
  if (!s) return null;
  try { return JSON.parse(s); } catch { return null; }
}

export function timeAgo(dateStr: string) {
  const d = new Date(dateStr + "Z");
  const now = new Date();
  const diff = Math.floor((now.getTime() - d.getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
