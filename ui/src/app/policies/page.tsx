"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ShieldCheck, Hash, Copy, Check, ChevronRight, Briefcase, Box, Star, FileText } from "lucide-react";
import { motion } from "framer-motion";
import { Badge } from "@/lib/components";
import { fetchPolicies } from "@/lib/api";

type PolicyRule = {
  name: string;
  condition: { field?: string; flag?: string; op?: string; value?: unknown };
  decision: string;
  reason?: string;
  required_checks?: string[];
};

type BoundWorkspace = {
  workspace_id: string;
  name: string;
  risk_posture: string;
};

type BoundAgent = {
  agent_id: string;
  name: string;
  workspace_id: string | null;
  workspace_name: string | null;
  status: string;
  binding_type: "override" | "inherited";
};

type Policy = {
  policy_id: string;
  name: string;
  version: string;
  source_file: string;
  hash: string;
  is_default: boolean;
  description: string | null;
  rule_count: number;
  thresholds: Record<string, number | string>;
  bound_workspaces: BoundWorkspace[];
  bound_agents: BoundAgent[];
  direct_agent_count: number;
  inherited_agent_count: number;
  action_count: number;
  updated_at: string;
};

const DECISION_COLORS: Record<string, string> = {
  BLOCK: "red",
  APPROVAL_REQUIRED: "violet",
  CANARY: "amber",
  AUTO: "green",
};

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<Policy[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  useEffect(() => {
    fetchPolicies()
      .then(setPolicies)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  }, []);

  async function copyHash(hash: string) {
    await navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 1500);
  }

  return (
    <div className="animate-in fade-in duration-500 pb-16 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-ks-text">Policies</h1>
        <p className="text-[13px] text-ks-text2 mt-1.5 max-w-2xl leading-relaxed">
          Versioned YAML policies loaded from{" "}
          <code className="font-mono bg-ks-surface-2 px-1 py-0.5 rounded text-ks-text border border-ks-border">
            backend/app/policies/
          </code>
          . Each workspace and agent can be bound to a specific policy. The
          resolver picks the strictest match: <strong>agent override → workspace → default</strong>.
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-500 mb-6">
          {error}
        </div>
      )}

      {!policies && !error && (
        <div className="space-y-4">
          {[0, 1].map((i) => (
            <div key={i} className="h-72 rounded-xl border border-ks-border bg-ks-surface/40 animate-pulse" />
          ))}
        </div>
      )}

      {policies && policies.length === 0 && (
        <div className="rounded-xl border border-ks-border bg-ks-surface/40 px-6 py-16 text-center">
          <ShieldCheck className="w-12 h-12 text-ks-text3 mx-auto mb-4" />
          <p className="text-sm text-ks-text2">No policies loaded.</p>
        </div>
      )}

      {policies && policies.length > 0 && (
        <div className="space-y-5">
          {policies.map((p, i) => (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              key={p.policy_id}
              className="rounded-xl border border-ks-border bg-ks-surface shadow-sm overflow-hidden"
            >
              {/* Header */}
              <div className="px-6 py-5 border-b border-ks-border/50">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-lg bg-ks-surface-2 border border-ks-border flex items-center justify-center shrink-0">
                      <ShieldCheck className="w-5 h-5 text-ks-primary" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h2 className="text-lg font-semibold text-ks-text">{p.name}</h2>
                        {p.is_default && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/30">
                            <Star className="w-3 h-3" />
                            Default
                          </span>
                        )}
                        <span className="text-[11px] font-mono text-ks-text3">v{p.version}</span>
                      </div>
                      {p.description && (
                        <p className="text-[12px] text-ks-text2 mt-1 max-w-xl">{p.description}</p>
                      )}
                      <div className="flex items-center gap-3 mt-2 flex-wrap">
                        <code className="text-[10px] font-mono text-ks-text3 bg-ks-surface-2 border border-ks-border px-1.5 py-0.5 rounded flex items-center gap-1">
                          <FileText className="w-3 h-3" />
                          {p.source_file}
                        </code>
                        <button
                          onClick={() => copyHash(p.hash)}
                          className="text-[10px] font-mono text-ks-text3 hover:text-ks-text transition-colors flex items-center gap-1 group"
                        >
                          <Hash className="w-3 h-3" />
                          {p.hash}
                          {copiedHash === p.hash ? (
                            <Check className="w-3 h-3 text-emerald-500" />
                          ) : (
                            <Copy className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 shrink-0">
                    <Metric label="Rules" value={p.rule_count} />
                    <Metric label="Workspaces" value={p.bound_workspaces.length} />
                    <Metric
                      label="Agents"
                      value={p.bound_agents.length}
                      sub={p.inherited_agent_count > 0 ? `${p.direct_agent_count} override · ${p.inherited_agent_count} inherited` : undefined}
                    />
                    <Metric label="Actions" value={p.action_count} />
                  </div>
                </div>
              </div>

              {/* Bindings strip */}
              <div className="px-6 py-4 bg-ks-surface-2/40 border-b border-ks-border/50">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Workspaces */}
                  <div>
                    <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest mb-2 flex items-center gap-1.5">
                      <Briefcase className="w-3 h-3" />
                      Applies to Workspaces
                    </div>
                    {p.bound_workspaces.length === 0 ? (
                      <div className="text-[12px] text-ks-text3 italic">
                        {p.is_default
                          ? "(fallback — used when no other policy matches)"
                          : "No workspace bindings"}
                      </div>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {p.bound_workspaces.map((w) => (
                          <Link
                            key={w.workspace_id}
                            href={`/workspaces/${w.workspace_id}`}
                            className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-[11px] bg-ks-surface border border-ks-border text-ks-text hover:bg-ks-hover hover:border-ks-primary/30 transition-colors"
                          >
                            <span
                              className={`w-1.5 h-1.5 rounded-full ${
                                w.risk_posture === "critical"
                                  ? "bg-red-500"
                                  : w.risk_posture === "warning"
                                    ? "bg-amber-500"
                                    : "bg-emerald-500"
                              }`}
                            />
                            {w.name}
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Agents: direct overrides + inherited via workspace */}
                  <div>
                    <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest mb-2 flex items-center gap-1.5">
                      <Box className="w-3 h-3" />
                      Agents Using This Policy
                    </div>
                    {p.bound_agents.length === 0 ? (
                      <div className="text-[12px] text-ks-text3 italic">
                        No agents
                      </div>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {p.bound_agents.map((a) => (
                          <Link
                            key={a.agent_id}
                            href={`/agents/${a.agent_id}`}
                            className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-[11px] bg-ks-surface border border-ks-border text-ks-text hover:bg-ks-hover hover:border-ks-primary/30 transition-colors"
                            title={a.binding_type === "override" ? "Agent-level override" : "Inherited via workspace"}
                          >
                            <Box className="w-3 h-3 text-ks-text3" />
                            <span>{a.name}</span>
                            {a.workspace_name && (
                              <span className="text-ks-text3">· {a.workspace_name}</span>
                            )}
                            <span
                              className={`text-[9px] font-semibold px-1 py-px rounded ${
                                a.binding_type === "override"
                                  ? "bg-violet-500/15 text-violet-500"
                                  : "bg-ks-surface-2 text-ks-text3"
                              }`}
                            >
                              {a.binding_type === "override" ? "OVERRIDE" : "INHERITED"}
                            </span>
                            {a.status !== "active" && (
                              <Badge color={a.status === "paused" ? "amber" : "red"}>
                                {a.status}
                              </Badge>
                            )}
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Thresholds */}
              <div className="px-6 py-4 border-b border-ks-border/50">
                <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest mb-3">
                  Thresholds
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {Object.entries(p.thresholds).map(([k, v]) => (
                    <div
                      key={k}
                      className="bg-ks-surface-2/50 border border-ks-border rounded px-3 py-2"
                    >
                      <div className="text-[10px] text-ks-text3 uppercase tracking-wide">
                        {k.replace(/_/g, " ")}
                      </div>
                      <div className="text-sm font-mono font-bold text-ks-text tabular-nums">
                        {String(v)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Rules toggle */}
              <button
                onClick={() =>
                  setExpanded(expanded === p.policy_id ? null : p.policy_id)
                }
                className="w-full flex items-center justify-between px-6 py-3 hover:bg-ks-hover transition-colors text-[11px] font-semibold text-ks-text3 uppercase tracking-widest"
              >
                <span>
                  {expanded === p.policy_id ? "Hide rules" : `Show ${p.rule_count} rule${p.rule_count !== 1 ? "s" : ""}`}
                </span>
                <ChevronRight
                  className={`w-3.5 h-3.5 transition-transform ${
                    expanded === p.policy_id ? "rotate-90" : ""
                  }`}
                />
              </button>

              {expanded === p.policy_id && (
                <PolicyRules policyId={p.policy_id} />
              )}
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, sub }: { label: string; value: number; sub?: string }) {
  return (
    <div className="text-right">
      <div className="text-lg font-bold tabular-nums text-ks-text">{value}</div>
      <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">
        {label}
      </div>
      {sub && <div className="text-[9px] text-ks-text3 mt-0.5 whitespace-nowrap">{sub}</div>}
    </div>
  );
}

function PolicyRules({ policyId }: { policyId: string }) {
  const [rules, setRules] = useState<PolicyRule[] | null>(null);

  useEffect(() => {
    import("@/lib/api").then((api) => {
      api.fetchPolicyById(policyId).then((d) => setRules(d.rules || []));
    });
  }, [policyId]);

  if (!rules) {
    return <div className="px-6 py-4 text-sm text-ks-text3">Loading rules…</div>;
  }

  if (rules.length === 0) {
    return <div className="px-6 py-4 text-sm text-ks-text3">No rules.</div>;
  }

  return (
    <div className="divide-y divide-ks-border/50 bg-ks-surface-2/20">
      {rules.map((rule, i) => {
        const decisionColor = DECISION_COLORS[rule.decision] || "gray";
        const cond = rule.condition || {};
        const condLabel = cond.field
          ? `${cond.field} ${formatOp(cond.op)} ${formatValue(cond.value)}`
          : cond.flag
            ? `flag.${cond.flag} ${formatOp(cond.op)} ${formatValue(cond.value)}`
            : JSON.stringify(cond);

        return (
          <div key={rule.name || i} className="px-6 py-3">
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 rounded bg-ks-surface border border-ks-border flex items-center justify-center text-[10px] font-mono font-semibold text-ks-text3 shrink-0">
                {String(i + 1).padStart(2, "0")}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1.5">
                  <span className="text-sm font-semibold text-ks-text">{rule.name}</span>
                  <Badge color={decisionColor}>{rule.decision}</Badge>
                </div>
                <div className="flex items-center gap-2 flex-wrap mb-1 text-[12px]">
                  <span className="text-ks-text3 font-mono uppercase text-[10px]">if</span>
                  <code className="font-mono text-ks-text bg-ks-surface border border-ks-border px-1.5 py-0.5 rounded">
                    {condLabel}
                  </code>
                  <ChevronRight className="w-3 h-3 text-ks-text3" />
                  <code
                    className={`font-mono px-1.5 py-0.5 rounded font-semibold ${
                      decisionColor === "red"
                        ? "text-red-500 bg-red-500/10 border border-red-500/20"
                        : decisionColor === "violet"
                          ? "text-violet-500 bg-violet-500/10 border border-violet-500/20"
                          : decisionColor === "amber"
                            ? "text-amber-500 bg-amber-500/10 border border-amber-500/20"
                            : "text-emerald-500 bg-emerald-500/10 border border-emerald-500/20"
                    }`}
                  >
                    {rule.decision}
                  </code>
                </div>
                {rule.reason && (
                  <div className="text-[12px] text-ks-text2 leading-relaxed mt-1">{rule.reason}</div>
                )}
                {rule.required_checks && rule.required_checks.length > 0 && (
                  <div className="mt-1.5 flex items-center gap-1 flex-wrap">
                    <span className="text-[10px] font-bold text-ks-text3 uppercase tracking-widest">
                      requires:
                    </span>
                    {rule.required_checks.map((c) => (
                      <span
                        key={c}
                        className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-ks-surface text-ks-text2 border border-ks-border"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function formatOp(op: string | undefined): string {
  const ops: Record<string, string> = {
    eq: "==", ne: "!=", gt: ">", gte: ">=", lt: "<", lte: "<=", in: "in",
  };
  return ops[op || "eq"] || op || "==";
}

function formatValue(val: unknown): string {
  if (val === null || val === undefined) return "—";
  if (typeof val === "string") return JSON.stringify(val);
  if (Array.isArray(val)) return JSON.stringify(val);
  return String(val);
}
