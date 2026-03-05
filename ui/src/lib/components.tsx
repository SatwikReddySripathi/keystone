"use client";

/* ── Badge ──────────────────────────────────────── */
const BADGE_STYLES: Record<string, string> = {
  green: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  red: "bg-red-500/15 text-red-300 border-red-500/30",
  amber: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  sky: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  violet: "bg-violet-500/15 text-violet-300 border-violet-500/30",
  gray: "bg-white/5 text-gray-300 border-white/10",
  white: "bg-white/5 text-white border-white/10",
};

export function Badge({ color = "gray", children, className = "" }: {
  color?: string; children: React.ReactNode; className?: string;
}) {
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium border ${BADGE_STYLES[color] || BADGE_STYLES.gray} ${className}`}>
      {children}
    </span>
  );
}

/* ── Lifecycle Stepper ──────────────────────────── */
const STEPS = [
  { key: "preview", label: "Preview" },
  { key: "policy", label: "Policy" },
  { key: "approval", label: "Approval" },
  { key: "canary", label: "Canary" },
  { key: "expand", label: "Expand" },
  { key: "receipt", label: "Receipt" },
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
        if (types.some((t: string) => t.includes("awaiting"))) return "skipped";
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

  return (
    <div className="flex items-center">
      {STEPS.map((step, i) => {
        const state = getState(step.key);

        const dotColor = {
          done: "bg-emerald-500 border-emerald-400",
          active: "bg-sky-500 border-sky-400 animate-pulse",
          failed: "bg-red-500 border-red-400",
          skipped: "bg-gray-700 border-gray-600",
          pending: "bg-gray-800 border-gray-700",
        }[state];

        const labelColor = {
          done: "text-emerald-300",
          active: "text-sky-300",
          failed: "text-red-300",
          skipped: "text-gray-600",
          pending: "text-gray-600",
        }[state];

        const lineColor = state === "done" ? "bg-emerald-500/50" : state === "failed" ? "bg-red-500/50" : "bg-gray-800";

        const symbol = {
          done: "OK",
          active: "..",
          failed: "NO",
          skipped: "--",
          pending: "",
        }[state];

        return (
          <div key={step.key} className="flex items-center">
            <div className="flex flex-col items-center w-16">
              <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center ${dotColor}`}>
                <span className="text-[9px] font-bold text-white">{symbol}</span>
              </div>
              <span className={`text-[10px] mt-1.5 font-semibold ${labelColor}`}>{step.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`w-4 h-0.5 mb-5 ${lineColor}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ── Risk Meter ─────────────────────────────────── */
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
  const color = total >= 8 ? "text-red-300" : total >= 4 ? "text-amber-300" : "text-emerald-300";
  const barColor = total >= 8 ? "bg-red-500" : total >= 4 ? "bg-amber-500" : "bg-emerald-500";
  const pct = Math.min(total / 15 * 100, 100);

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-sm font-bold ${color}`}>{level} Risk</span>
        <span className="text-xs text-gray-400">({total} pts)</span>
      </div>
      <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden mb-2">
        <div className={`h-full rounded-full transition-all duration-500 ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="space-y-0.5">
        {factors.filter(f => f.score > 0).map((f, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="text-gray-400">+{f.score}</span>
            <span className="text-gray-300">{f.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Breaker Status ─────────────────────────────── */
export function BreakerBadge({ tripped, reason }: { tripped: boolean; reason?: string }) {
  if (tripped) {
    return (
      <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/25">
        <div className="w-3 h-3 rounded-full bg-red-500 shrink-0" />
        <div>
          <div className="text-xs font-bold text-red-300">BREAKER TRIPPED</div>
          {reason && <div className="text-[11px] text-red-300/50 mt-0.5 max-w-xs">{reason.slice(0, 80)}</div>}
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-white/3 border border-white/8">
      <div className="w-3 h-3 rounded-full bg-emerald-500 shrink-0" />
      <div>
        <div className="text-xs font-medium text-gray-300">Circuit breaker armed</div>
        <div className="text-[11px] text-gray-500">Auto-halt on anomaly detection</div>
      </div>
    </div>
  );
}

/* ── Event Timeline ─────────────────────────────── */
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
  "breaker.tripped":           { label: "Circuit breaker TRIPPED",     kind: "error" },
  "expand.started":            { label: "Expansion started",           kind: "info" },
  "expand.completed":          { label: "Expansion completed",         kind: "success" },
  "action.completed":          { label: "Action completed",            kind: "success" },
  "action.observed":           { label: "Observed — no execution",     kind: "info" },
  "proof.generated":           { label: "Audit receipt signed",        kind: "success" },
};

function getEventSummary(type: string, payload: any): string {
  if (!payload || typeof payload !== "object") return "";
  switch (type) {
    case "action.created":
      return payload.mode ? `Mode: ${payload.mode}` : "";
    case "preview.generated":
      return `${payload.blast_radius || "?"} records matched  |  Hash: ${(payload.preview_hash || "").slice(0, 12)}...`;
    case "decision.made": {
      const rules = (payload.matched_rules || []).join(", ");
      return `Decision: ${payload.decision || "?"}  |  Rules: ${rules || "default"}`;
    }
    case "canary.started":
      return `Subset: ${(payload.subset || []).length || "?"} records`;
    case "canary.completed":
      return `${payload.count || "?"} records  |  Error rate: ${((payload.error_rate || 0) * 100).toFixed(1)}%`;
    case "checks.completed": {
      const r = payload.results || {};
      const passed = Object.values(r).filter(v => v === true).length;
      const total = Object.keys(r).length;
      const failed = Object.entries(r).filter(([, v]) => v === false).map(([k]) => k.replace(/_/g, " "));
      if (failed.length > 0) return `${passed}/${total} passed  |  Failed: ${failed.join(", ")}`;
      return `All ${total} checks passed`;
    }
    case "breaker.tripped":
      return (payload.reason || "").slice(0, 120);
    case "expand.started":
      return `${payload.count || "?"} remaining records`;
    case "expand.completed":
      return `${payload.count || "?"} records  |  Error rate: ${((payload.error_rate || 0) * 100).toFixed(1)}%`;
    case "approval.recorded":
      return `By ${payload.approver || "unknown"} via ${payload.channel || "?"}`;
    case "proof.generated":
      return `Signature: ${payload.signature_prefix || "?"}...`;
    default:
      return "";
  }
}

export function EventTimeline({ events }: { events: TimelineEvent[] }) {
  // Color schemes for each kind
  const kindStyles: Record<EventKind, { border: string; dot: string; label: string; summary: string; bg: string }> = {
    success: { border: "border-l-emerald-500", dot: "bg-emerald-500",  label: "text-emerald-300", summary: "text-emerald-300/60", bg: "bg-emerald-500/[0.03]" },
    error:   { border: "border-l-red-500",     dot: "bg-red-500",      label: "text-red-300",     summary: "text-red-300/60",     bg: "bg-red-500/[0.05]" },
    warning: { border: "border-l-amber-500",   dot: "bg-amber-500",    label: "text-amber-300",   summary: "text-amber-300/60",   bg: "bg-amber-500/[0.03]" },
    info:    { border: "border-l-sky-500",     dot: "bg-sky-500",      label: "text-sky-300",     summary: "text-sky-300/60",     bg: "bg-sky-500/[0.03]" },
    neutral: { border: "border-l-gray-600",    dot: "bg-gray-500",     label: "text-gray-300",    summary: "text-gray-400",       bg: "bg-transparent" },
  };

  return (
    <div className="space-y-1">
      {events.map((e, i) => {
        const t = e.type || "";
        const cfg = EVENT_MAP[t] || { label: t, kind: "neutral" as EventKind };
        const payload = e.payload_json || {};

        // Override kind based on actual data
        let kind = cfg.kind;
        if (t === "checks.completed") {
          const results = payload.results || {};
          const hasFail = Object.values(results).some(v => v === false);
          kind = hasFail ? "error" : "success";
        }

        const s = kindStyles[kind];
        const summary = getEventSummary(t, payload);

        return (
          <div key={i} className={`flex items-start border-l-[3px] ${s.border} ${s.bg} rounded-r-lg px-4 py-3`}>
            {/* Dot indicator */}
            <div className={`w-2.5 h-2.5 rounded-full ${s.dot} shrink-0 mt-1 mr-3`} />

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-4">
                <span className={`text-sm font-semibold ${s.label}`}>{cfg.label}</span>
                <span className="text-[10px] text-gray-500 font-mono shrink-0">{e.created_at}</span>
              </div>
              {summary && (
                <p className={`text-xs mt-1 ${s.summary}`}>{summary}</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Mini Bar Chart ─────────────────────────────── */
export function MiniBarChart({ data, colorMap }: {
  data: Record<string, number>;
  colorMap?: Record<string, string>;
}) {
  const entries = Object.entries(data);
  const max = Math.max(...entries.map(([, v]) => v), 1);
  const palette = [
    "bg-indigo-500", "bg-sky-500", "bg-violet-500", "bg-emerald-500",
    "bg-amber-500", "bg-rose-500", "bg-teal-500", "bg-orange-500",
  ];

  function getColor(label: string, index: number): string {
    if (colorMap && colorMap[label]) return colorMap[label];
    return palette[index % palette.length];
  }

  return (
    <div className="space-y-1.5">
      {entries.map(([label, value], i) => (
        <div key={label} className="flex items-center gap-2">
          <span className="text-xs text-gray-300 w-28 text-right truncate">{label}</span>
          <div className="flex-1 h-5 bg-gray-800/60 rounded overflow-hidden">
            <div className={`h-full rounded ${getColor(label, i)}`} style={{ width: `${(value / max) * 100}%` }} />
          </div>
          <span className="text-xs text-gray-200 w-6 text-right font-medium">{value}</span>
        </div>
      ))}
    </div>
  );
}

/* ── Helpers ─────────────────────────────────────── */
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