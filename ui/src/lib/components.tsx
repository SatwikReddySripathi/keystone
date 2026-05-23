"use client";

import { CheckCircle2, XCircle, AlertTriangle, ShieldCheck, Clock, Activity, FileCheck, CircleDot, PlayCircle, Eye, Hand } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/* ── Badge ──────────────────────────────────────────────────────── */
const BADGE_STYLES: Record<string, string> = {
  green:  "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.05)]",
  red:    "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20 shadow-[0_0_10px_rgba(239,68,68,0.05)]",
  amber:  "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20 shadow-[0_0_10px_rgba(245,158,11,0.05)]",
  sky:    "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20 shadow-[0_0_10px_rgba(14,165,233,0.05)]",
  violet: "bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20 shadow-[0_0_10px_rgba(139,92,246,0.05)]",
  gray:   "bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border-zinc-500/20",
  white:  "bg-white/10 text-ks-text border-ks-border shadow-sm",
};

export function Badge({ color = "gray", children, className = "" }: {
  color?: string; children: React.ReactNode; className?: string;
}) {
  return (
    <span className={cn(
      "inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium border backdrop-blur-sm",
      BADGE_STYLES[color] || BADGE_STYLES.gray,
      className
    )}>
      {children}
    </span>
  );
}

/* ── Lifecycle Stepper ──────────────────────────────────────────── */
const STEPS = [
  { key: "preview",  label: "Diff", icon: Eye },
  { key: "policy",   label: "Gate", icon: ShieldCheck },
  { key: "approval", label: "Approval", icon: Hand },
  { key: "canary",   label: "Canary", icon: PlayCircle },
  { key: "expand",   label: "Rollout", icon: Activity },
  { key: "receipt",  label: "Audit Log", icon: FileCheck },
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

  const stateColors: Record<StepState, { icon: string; bg: string; border: string; text: string; line: string }> = {
    done:    { icon: "text-emerald-500", bg: "bg-emerald-500/10", border: "border-emerald-500/30", text: "text-emerald-600 dark:text-emerald-400", line: "bg-emerald-500/50" },
    active:  { icon: "text-ks-primary", bg: "bg-ks-primary/10 animate-pulse", border: "border-ks-primary/50 shadow-[0_0_10px_rgba(79,70,229,0.3)]", text: "text-ks-primary", line: "bg-ks-primary/30" },
    failed:  { icon: "text-red-500", bg: "bg-red-500/10", border: "border-red-500/50 shadow-[0_0_10px_rgba(239,68,68,0.3)]", text: "text-red-600 dark:text-red-400", line: "bg-ks-border" },
    skipped: { icon: "text-ks-text3", bg: "bg-ks-surface", border: "border-ks-border border-dashed", text: "text-ks-text3", line: "bg-ks-border border-dashed" },
    pending: { icon: "text-ks-text3", bg: "bg-ks-surface-2", border: "border-ks-border", text: "text-ks-text3", line: "bg-ks-border" },
  };

  return (
    <div className="flex items-center w-full">
      {STEPS.map((step, i) => {
        const state = getState(step.key);
        const colors = stateColors[state];
        const Icon = step.icon;
        
        return (
          <div key={step.key} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center relative z-10" style={{ minWidth: "60px" }}>
              <div className={cn("w-8 h-8 rounded-full flex items-center justify-center border transition-all duration-300", colors.bg, colors.border)}>
                <Icon className={cn("w-4 h-4", colors.icon)} strokeWidth={2.5} />
              </div>
              <span className={cn("text-[10px] mt-2 font-medium tracking-wide uppercase transition-colors duration-300", colors.text)}>
                {step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className="flex-1 px-1">
                <div className={cn("h-[2px] rounded-full transition-all duration-500 mb-4", colors.line)} />
              </div>
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
  const color = total >= 8 ? "text-red-500" : total >= 4 ? "text-amber-500" : "text-emerald-500";
  const barColor = total >= 8 ? "bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]" : total >= 4 ? "bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.5)]" : "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]";
  const pct = Math.min(total / 15 * 100, 100);

  return (
    <div className="bg-ks-surface-2/50 border border-ks-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity className={cn("w-4 h-4", color)} />
          <span className={cn("text-sm font-bold tracking-tight", color)}>{level} Risk</span>
        </div>
        <span className="text-xs font-mono text-ks-text3 bg-ks-surface px-2 py-0.5 rounded border border-ks-border">Score: {total}</span>
      </div>
      
      {/* Segmented bar representation */}
      <div className="w-full h-1.5 bg-ks-border/50 rounded-full overflow-hidden mb-4 flex gap-0.5">
        <div className={cn("h-full rounded-full transition-all duration-700 ease-out", barColor)} style={{ width: `${pct}%` }} />
      </div>
      
      <div className="space-y-1.5">
        {factors.map((f, i) => (
          <div key={i} className="flex items-center gap-2.5 text-xs group">
            <span className="text-ks-text3 w-6 text-right font-mono bg-ks-surface-2 rounded px-1 py-0.5">+{f.score}</span>
            <span className="text-ks-text2 group-hover:text-ks-text transition-colors">{f.label}</span>
          </div>
        ))}
        {factors.length === 0 && (
          <div className="flex items-center gap-2 text-xs text-ks-text3 py-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
            No risk factors detected.
          </div>
        )}
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

const EVENT_MAP: Record<string, { label: string; kind: EventKind, icon: any }> = {
  "action.created":            { label: "Action initialized",          kind: "neutral", icon: CircleDot },
  "preview.generated":         { label: "Preview generated",           kind: "success", icon: Eye },
  "decision.made":             { label: "Policy evaluated",            kind: "success", icon: ShieldCheck },
  "action.blocked":            { label: "Blocked by policy",           kind: "error",   icon: XCircle },
  "action.awaiting_approval":  { label: "Awaiting human approval",     kind: "warning", icon: Clock },
  "slack.notification_sent":   { label: "Slack notification sent",     kind: "info",    icon: Activity },
  "approval.recorded":         { label: "Approval recorded",           kind: "success", icon: CheckCircle2 },
  "approval.denied":           { label: "Approval denied",             kind: "error",   icon: XCircle },
  "canary.started":            { label: "Canary started",              kind: "info",    icon: PlayCircle },
  "canary.completed":          { label: "Canary completed",            kind: "success", icon: CheckCircle2 },
  "checks.completed":          { label: "Safety invariants checked",   kind: "info",    icon: ShieldCheck },
  "breaker.tripped":           { label: "Circuit breaker tripped",     kind: "error",   icon: AlertTriangle },
  "expand.started":            { label: "Expansion started",           kind: "info",    icon: PlayCircle },
  "expand.completed":          { label: "Expansion completed",         kind: "success", icon: CheckCircle2 },
  "action.completed":          { label: "Action completed",            kind: "success", icon: CheckCircle2 },
  "action.observed":           { label: "Observed — no execution",     kind: "info",    icon: Eye },
  "proof.generated":           { label: "Audit receipt signed",        kind: "success", icon: FileCheck },
};

function getEventSummary(type: string, payload: any): string {
  if (!payload || typeof payload !== "object") return "";
  switch (type) {
    case "action.created":      return payload.mode ? `Mode: ${payload.mode}` : "";
    case "preview.generated":   return `${payload.blast_radius || "?"} records matched • hash: ${(payload.preview_hash || "").slice(0, 12)}...`;
    case "decision.made": {
      const rules = (payload.matched_rules || []).join(", ");
      return `${payload.decision || "?"} • rules: ${rules || "default"}`;
    }
    case "canary.started":      return `${(payload.subset || []).length || "?"} records`;
    case "canary.completed":    return `${payload.count || "?"} records • error rate: ${((payload.error_rate || 0) * 100).toFixed(1)}%`;
    case "checks.completed": {
      const r = payload.results || {};
      const passed = Object.values(r).filter(v => v === true).length;
      const total = Object.keys(r).length;
      const failed = Object.entries(r).filter(([, v]) => v === false).map(([k]) => k.replace(/_/g, " "));
      return failed.length > 0 ? `${passed}/${total} passed • failed: ${failed.join(", ")}` : `All ${total} passed`;
    }
    case "breaker.tripped":     return (payload.reason || "").slice(0, 120);
    case "expand.started":      return `${payload.count || "?"} remaining records`;
    case "expand.completed":    return `${payload.count || "?"} records • error rate: ${((payload.error_rate || 0) * 100).toFixed(1)}%`;
    case "approval.recorded":   return `By ${payload.approver || "unknown"} via ${payload.channel || "?"}`;
    case "proof.generated":     return `Signature: ${payload.signature_prefix || "?"}...`;
    default:                    return "";
  }
}

export function EventTimeline({ events }: { events: TimelineEvent[] }) {
  const kindColors: Record<EventKind, string> = {
    success: "text-emerald-500 bg-emerald-500/10 border-emerald-500/20",
    error:   "text-red-500 bg-red-500/10 border-red-500/20",
    warning: "text-amber-500 bg-amber-500/10 border-amber-500/20",
    info:    "text-sky-500 bg-sky-500/10 border-sky-500/20",
    neutral: "text-ks-text3 bg-ks-surface-2 border-ks-border",
  };
  const kindLabel: Record<EventKind, string> = {
    success: "text-emerald-600 dark:text-emerald-400",
    error:   "text-red-600 dark:text-red-400",
    warning: "text-amber-600 dark:text-amber-400",
    info:    "text-sky-600 dark:text-sky-400",
    neutral: "text-ks-text",
  };

  return (
    <div className="relative pl-6">
      <div className="absolute left-[13px] top-3 bottom-3 w-[2px] bg-ks-border/50" />
      {events.map((e, i) => {
        const t = e.type || "";
        const cfg = EVENT_MAP[t] || { label: t, kind: "neutral" as EventKind, icon: CircleDot };
        const payload = e.payload_json || {};
        let kind = cfg.kind;
        if (t === "checks.completed") {
          kind = Object.values(payload.results || {}).some(v => v === false) ? "error" : "success";
        }
        const summary = getEventSummary(t, payload);
        const Icon = cfg.icon;
        
        return (
          <div key={i} className="relative flex items-start gap-4 pb-6 last:pb-0 group">
            <div className={cn(
              "relative z-10 w-6 h-6 rounded-full shrink-0 flex items-center justify-center border backdrop-blur-sm transition-transform duration-300 group-hover:scale-110",
              kindColors[kind]
            )}>
              <Icon className="w-3 h-3" />
            </div>
            <div className="flex-1 min-w-0 pt-0.5">
              <div className="flex items-baseline justify-between gap-2 flex-wrap">
                <span className={cn("text-sm font-medium", kindLabel[kind])}>{cfg.label}</span>
                <span className="text-[11px] text-ks-text3 font-mono bg-ks-surface-2 px-1.5 py-0.5 rounded shrink-0">{e.created_at}</span>
              </div>
              {summary && <p className="text-xs text-ks-text2 mt-1 leading-relaxed font-mono">{summary}</p>}
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
