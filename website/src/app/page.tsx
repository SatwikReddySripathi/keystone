import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Action Marshall — Transaction Governance for AI Agents",
  description:
    "Action Marshall sits between your AI agents and your production systems. Every action is previewed, policy-checked, and cryptographically audited.",
};

// ── Primitive ────────────────────────────────────────────────────────
function Label({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] font-semibold tracking-[0.12em] uppercase text-blue-600 mb-3">
      {children}
    </p>
  );
}

// ── Nav ──────────────────────────────────────────────────────────────
function Nav() {
  const links = ["Product", "How It Works", "Enterprise", "Docs"];
  return (
    <header className="fixed inset-x-0 top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-zinc-200">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10 h-16 flex items-center gap-8">
        <a href="/" className="flex items-center gap-2.5 shrink-0">
          <div className="w-7 h-7 bg-zinc-900 rounded-md flex items-center justify-center">
            <span className="text-white text-xs font-bold tracking-tight">K</span>
          </div>
          <span className="text-sm font-semibold text-zinc-900 tracking-tight">Action Marshall</span>
        </a>
        <nav className="hidden md:flex items-center gap-7 ml-2">
          {links.map((item) => (
            <a
              key={item}
              href={`#${item.toLowerCase().replace(/\s+/g, "-")}`}
              className="text-sm text-zinc-500 hover:text-zinc-900 transition-colors duration-150"
            >
              {item}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <a href="#" className="hidden md:block text-sm text-zinc-500 hover:text-zinc-900 transition-colors duration-150">
            Sign in
          </a>
          <a
            href="#"
            className="text-sm font-medium bg-zinc-900 text-white px-4 py-2 rounded-md hover:bg-zinc-700 transition-colors duration-150"
          >
            Request access
          </a>
        </div>
      </div>
    </header>
  );
}

// ── Hero product panel ───────────────────────────────────────────────
const DEC: Record<string, string> = {
  CANARY:   "bg-amber-500/10 text-amber-400 border border-amber-500/20",
  APPROVAL: "bg-violet-500/10 text-violet-400 border border-violet-500/20",
  PASSED:   "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
  BLOCKED:  "bg-red-500/10 text-red-400 border border-red-500/20",
};

const ROWS = [
  { action: "Bulk resolve 124 incidents",    sub: "ServiceNow · canary executing — 5 of 124", dec: "CANARY",   agent: "SLA-Bot",   t: "2m" },
  { action: "Reassign open P2 tickets",      sub: "Jira · awaiting Sarah Chen",               dec: "APPROVAL", agent: "TicketBot", t: "8m" },
  { action: "Archive closed support tickets",sub: "Zendesk · 47 records · all checks passed", dec: "PASSED",   agent: "Archiver",  t: "1h" },
  { action: "Update opportunity stage",      sub: "Salesforce · blocked by policy",           dec: "BLOCKED",  agent: "SalesAI",   t: "3h" },
];

function ProductPanel() {
  return (
    <div className="bg-zinc-950 rounded-xl border border-zinc-800 shadow-2xl overflow-hidden w-full">
      {/* Window bar */}
      <div className="flex items-center gap-2 px-4 py-3 bg-zinc-900 border-b border-zinc-800">
        <div className="flex gap-1.5">
          {[0, 1, 2].map((i) => <div key={i} className="w-2.5 h-2.5 rounded-full bg-zinc-700" />)}
        </div>
        <span className="text-[11px] text-zinc-500 ml-2 font-mono">action_marshall / transactions</span>
        <div className="ml-auto flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          <span className="text-[11px] text-zinc-500">Live</span>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 divide-x divide-zinc-800 border-b border-zinc-800 bg-zinc-900/40">
        {[["1,240","Records governed"],["28","Passed"],["5","Contained"],["1","Pending"]].map(([v, l]) => (
          <div key={l} className="px-4 py-3">
            <div className="text-lg font-semibold tabular-nums text-white">{v}</div>
            <div className="text-[10px] text-zinc-500 mt-0.5">{l}</div>
          </div>
        ))}
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-[1fr_90px_88px_36px] px-4 py-2 border-b border-zinc-800 bg-zinc-900/20">
        {["Transaction", "Decision", "Agent", ""].map((h, i) => (
          <span key={i} className="text-[10px] font-semibold tracking-[0.1em] uppercase text-zinc-600">{h}</span>
        ))}
      </div>

      {/* Rows */}
      <div className="divide-y divide-zinc-800/50">
        {ROWS.map((r) => (
          <div key={r.action} className="grid grid-cols-[1fr_90px_88px_36px] px-4 py-3 hover:bg-zinc-800/30 transition-colors duration-100">
            <div className="min-w-0 pr-3">
              <div className="text-[13px] font-medium text-zinc-100 truncate">{r.action}</div>
              <div className="text-[11px] text-zinc-500 mt-0.5 truncate">{r.sub}</div>
            </div>
            <div className="flex items-center">
              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded tracking-wide ${DEC[r.dec]}`}>
                {r.dec.replace("_", " ")}
              </span>
            </div>
            <div className="flex items-center">
              <span className="text-[12px] text-zinc-400 truncate">{r.agent}</span>
            </div>
            <div className="flex items-center justify-end">
              <span className="text-[11px] text-zinc-600">{r.t}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-zinc-900/40 border-t border-zinc-800">
        <span className="text-[11px] text-zinc-600">4 transactions · 1 governing now</span>
        <span className="text-[11px] text-zinc-600">Updated just now</span>
      </div>
    </div>
  );
}

// ── Hero ─────────────────────────────────────────────────────────────
function Hero() {
  return (
    <section className="pt-16 bg-white">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10 py-20 md:py-28">
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)] gap-12 lg:gap-20 items-center">
          {/* Left */}
          <div>
            <div className="inline-flex items-center gap-2 text-[11px] font-medium text-zinc-600 bg-zinc-100 border border-zinc-200 px-3 py-1.5 rounded-full mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
              Generally available · Open source
            </div>
            <h1 className="text-[38px] md:text-[44px] font-semibold leading-[1.13] tracking-[-0.025em] text-zinc-900 mb-5">
              Govern what your{" "}
              <br className="hidden md:block" />
              AI agents do{" "}
              <span className="text-zinc-400">in production.</span>
            </h1>
            <p className="text-[17px] text-zinc-600 leading-relaxed mb-8 max-w-[460px]">
              Action Marshall sits between your agents and your production systems.
              Every action is previewed, policy-checked, and cryptographically
              audited — without slowing down legitimate automation.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <a href="#" className="inline-flex items-center gap-2 text-[13px] font-semibold bg-zinc-900 text-white px-5 py-2.5 rounded-md hover:bg-zinc-700 transition-colors duration-150">
                Request access
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                  <path d="M2 6.5h9M8 3L11 6.5 8 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </a>
              <a href="#" className="inline-flex items-center gap-1.5 text-[13px] text-zinc-500 hover:text-zinc-900 transition-colors duration-150">
                View on GitHub
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M2 10L10 2M10 2H5M10 2V7" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </a>
            </div>
            <div className="flex flex-wrap items-center gap-5 mt-10 pt-8 border-t border-zinc-100">
              {["SOC 2 Type II ready", "HMAC-SHA256 audit receipts", "Multi-workspace isolation"].map((item) => (
                <div key={item} className="flex items-center gap-2">
                  <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                    <path d="M2 6.5L5 9.5L11 3.5" stroke="#16a34a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  <span className="text-[12px] text-zinc-500">{item}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Right: product panel */}
          <div className="relative">
            <ProductPanel />
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Trust bar ────────────────────────────────────────────────────────
function TrustBar() {
  return (
    <section className="border-y border-zinc-200 bg-zinc-50 py-6">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <div className="flex flex-col md:flex-row items-center gap-5 md:gap-10">
          <span className="text-[11px] text-zinc-400 shrink-0 tracking-wide uppercase">Deployed by teams in</span>
          <div className="flex flex-wrap justify-center md:justify-start items-center gap-x-8 gap-y-2">
            {["Platform Engineering", "Security Operations", "IT & Change Management", "AI Infrastructure", "DevOps & SRE"].map((t) => (
              <span key={t} className="text-[13px] font-medium text-zinc-500">{t}</span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Problem ──────────────────────────────────────────────────────────
function Problem() {
  const bad = (title: string, items: string[]) => (
    <div className="border border-zinc-200 rounded-lg p-7 bg-zinc-50 h-full">
      <div className="flex items-center gap-2 mb-5">
        <div className="w-1.5 h-1.5 rounded-full bg-red-400" />
        <span className="text-[13px] font-semibold text-zinc-700">{title}</span>
      </div>
      <ul className="space-y-3">
        {items.map((item) => (
          <li key={item} className="flex items-start gap-2.5 text-[13px] text-zinc-600">
            <svg width="13" height="13" className="shrink-0 mt-0.5" viewBox="0 0 13 13" fill="none">
              <path d="M3 3L10 10M10 3L3 10" stroke="#f87171" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );

  return (
    <section id="product" className="py-24 bg-white">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <div className="max-w-[600px] mb-14">
          <Label>The Challenge</Label>
          <h2 className="text-[32px] md:text-[36px] font-semibold leading-[1.2] tracking-tight text-zinc-900 mb-4">
            The access control tradeoff holding enterprise AI back
          </h2>
          <p className="text-[15px] text-zinc-600 leading-relaxed">
            Most enterprise teams face a binary choice when deploying AI agents.
            Neither option is acceptable for production.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-[1fr_48px_1fr] items-stretch gap-4 md:gap-0">
          {bad("Restrict agent access", [
            "Agents cannot act on production data",
            "Manual intervention remains the bottleneck",
            "Automation value is severely limited",
            "Teams move slower, not faster",
          ])}
          <div className="hidden md:flex flex-col items-center justify-center gap-2 text-[11px] font-semibold text-zinc-400 uppercase tracking-wide">
            <div className="flex-1 w-px bg-zinc-200" />
            or
            <div className="flex-1 w-px bg-zinc-200" />
          </div>
          {bad("Allow broad access", [
            "Agents operate without guardrails",
            "Risk of unintended bulk modifications",
            "Security teams block deployment",
            "Compliance and audit exposure",
          ])}
        </div>

        <div className="mt-8 p-7 bg-blue-50 border border-blue-100 rounded-lg flex items-start gap-4">
          <div className="w-8 h-8 rounded bg-blue-600 flex items-center justify-center shrink-0 mt-0.5">
            <span className="text-white text-[11px] font-bold">K</span>
          </div>
          <div>
            <h3 className="text-[13px] font-semibold text-zinc-900 mb-1">Action Marshall gives you a third path.</h3>
            <p className="text-[13px] text-zinc-600 leading-relaxed max-w-[580px]">
              Precise, governed access for AI agents across every production system.
              Agents can act. Policies determine what, how much, and when.
              Every action is previewed, audited, and accountable. Nothing happens outside the defined boundary.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Product (pipeline) section ────────────────────────────────────────
function PipelineCard({ step, title, sub, badge, badgeStyle, dim }: {
  step: string; title: string; sub: string;
  badge?: string; badgeStyle?: string; dim?: boolean;
}) {
  return (
    <div className={`bg-zinc-900 rounded-lg border border-zinc-800 p-4 ${dim ? "opacity-40" : ""}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] font-semibold tracking-[0.1em] uppercase text-zinc-600">{step}</span>
        {badge && (
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded tracking-wide ${badgeStyle}`}>{badge}</span>
        )}
      </div>
      <div className={`text-[13px] font-medium mb-1 ${dim ? "text-zinc-500" : "text-zinc-100"}`}>{title}</div>
      <div className="text-[11px] text-zinc-500 leading-relaxed">{sub}</div>
    </div>
  );
}

function ProductSection() {
  return (
    <section className="py-24 bg-zinc-50 border-y border-zinc-200">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-16 items-start">
          <div className="lg:sticky lg:top-24">
            <Label>The Governance Layer</Label>
            <h2 className="text-[32px] font-semibold leading-[1.2] tracking-tight text-zinc-900 mb-4">
              Between your agents and your systems
            </h2>
            <p className="text-[15px] text-zinc-600 leading-relaxed mb-4">
              Action Marshall intercepts every agent action before it touches your data.
              The action either runs under controlled conditions, waits for
              approval, or is blocked outright — based on your versioned policies.
            </p>
            <p className="text-[15px] text-zinc-600 leading-relaxed">
              Nothing executes without a preview. Nothing expands without a
              canary. Nothing completes without a signed proof receipt.
            </p>
          </div>

          {/* Live pipeline mockup */}
          <div className="bg-zinc-950 rounded-xl border border-zinc-800 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800 bg-zinc-900">
              <div>
                <div className="text-[13px] font-medium text-zinc-100 font-mono">act_3f8a1b2c</div>
                <div className="text-[11px] text-zinc-500 mt-0.5">Bulk resolve 124 incidents · ServiceNow · SLA-Bot</div>
              </div>
              <span className={`text-[10px] font-semibold px-2 py-1 rounded tracking-wide ${DEC.CANARY}`}>CANARY</span>
            </div>

            <div className="p-4 space-y-2">
              <PipelineCard
                step="01 / Preview"
                title="Blast radius: 124 incidents"
                sub="Query completed · P3/P4 priority · Assignment group: Triage Team · 12 flags computed"
                badge="hash: 4f8a3b2c…"
                badgeStyle="text-zinc-400 bg-zinc-800 border border-zinc-700"
              />
              <PipelineCard
                step="02 / Policy"
                title="Decision: CANARY"
                sub="Rule: blast_radius_gt_20 · Policy default v1.0.0 · Threshold: 20 records"
                badge="v1.0.0"
                badgeStyle="text-blue-400 bg-blue-900/40 border border-blue-800"
              />
              <PipelineCard
                step="03 / Canary"
                title="5 records executing"
                sub="Deterministic subset · Checks: scope, fields, error rate, VIP, P1 · 2 of 5 complete"
                badge="Running"
                badgeStyle="text-amber-400 bg-amber-900/30 border border-amber-800/50"
              />
              <PipelineCard
                step="04 / Checks"
                title="Awaiting canary completion"
                sub="5 safety invariants will run: no_out_of_scope, only_intended_fields, no_vip_state_change…"
                dim
              />
              <PipelineCard
                step="05 / Audit"
                title="Proof receipt pending"
                sub="HMAC-SHA256 signature generated on completion · Exportable · Tamper-evident"
                dim
              />
            </div>

            <div className="px-5 py-3 border-t border-zinc-800 bg-zinc-900/40 flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
              <span className="text-[11px] text-zinc-500">Canary in progress · 2 of 5 records complete</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Capabilities ─────────────────────────────────────────────────────
const CAPS = [
  { title: "Blast radius preview", body: "Before any action runs, Action Marshall queries the target system and computes exactly how many records will be affected, what will change, and what risk flags are present." },
  { title: "Policy-based decisions", body: "Versioned YAML policies define what triggers an auto-run, a canary, a human approval, or a block. Rules evaluate in milliseconds against the live preview." },
  { title: "Canary execution", body: "Every action executes on a deterministic five-record subset first. Five safety invariants run. Expansion only happens if every check passes." },
  { title: "Human approval flows", body: "High-risk actions route to designated approvers via Slack or the web interface, with full blast radius context. Approvals bind to an exact preview hash." },
  { title: "Workspace isolation", body: "Teams get scoped environments with their own policies, member roles, and connected systems. Org admins have full cross-workspace visibility." },
  { title: "Cryptographic audit trail", body: "Every action generates an HMAC-SHA256 signed proof receipt covering the full lifecycle. Tamper-evident. Exportable as CSV or signed JSON." },
  { title: "App connections", body: "Register every SaaS system your agents operate on. Control permission scopes, risk classification, and connection status per system, per workspace." },
  { title: "Circuit breaker", body: "If canary execution reveals unexpected behavior — wrong fields changed, VIP records touched, error rate exceeded — Action Marshall halts automatically." },
];

function Capabilities() {
  return (
    <section id="how-it-works" className="py-24 bg-white">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,2.5fr)] gap-16 mb-14">
          <div>
            <Label>Capabilities</Label>
            <h2 className="text-[32px] font-semibold leading-[1.2] tracking-tight text-zinc-900 mb-4">
              Everything you need to ship agents in production
            </h2>
            <p className="text-[14px] text-zinc-600 leading-relaxed">
              Action Marshall is not a monitoring layer. It governs execution before,
              during, and after — across every system your agents touch.
            </p>
          </div>
          <div />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-8 gap-y-10">
          {CAPS.map((c) => (
            <div key={c.title} className="group">
              <div className="w-1 h-5 bg-zinc-200 group-hover:bg-blue-500 transition-colors duration-200 mb-3 rounded-full" />
              <h3 className="text-[13px] font-semibold text-zinc-900 mb-2">{c.title}</h3>
              <p className="text-[13px] text-zinc-600 leading-relaxed">{c.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── How it works ──────────────────────────────────────────────────────
const STEPS = [
  { n: "01", title: "Preview", desc: "Action Marshall queries the target system and computes the exact blast radius — records affected, fields changing, risk flags detected.", cond: false },
  { n: "02", title: "Policy gate", desc: "Versioned rules evaluate the preview in milliseconds: AUTO, CANARY, APPROVAL_REQUIRED, or BLOCK.", cond: false },
  { n: "03", title: "Approval", desc: "If required, the action routes to designated approvers with full context. Approval binds to an exact preview hash — not the request.", cond: true },
  { n: "04", title: "Canary rollout", desc: "Five deterministic records execute first. Five safety checks run. If any check fails, the circuit breaker trips and expansion halts.", cond: false },
  { n: "05", title: "Audit trail", desc: "A signed proof receipt is generated for every action. HMAC-SHA256. Exportable. Cryptographically verifiable.", cond: false },
];

const AUDIT_ROWS = [
  { id: "act_3f8a1b2c", ts: "Today 14:32", action: "Bulk resolve 124 incidents",    tool: "ServiceNow", agent: "SLA-Bot",   ws: "Platform Engineering", approver: "—",         dec: "CANARY",   status: "Contained", sc: "text-amber-700 bg-amber-50 border-amber-200" },
  { id: "act_9c2d4e5f", ts: "Today 13:48", action: "Reassign open P2 tickets",      tool: "Jira",        agent: "TicketBot", ws: "Platform Engineering", approver: "Sarah Chen", dec: "APPROVAL", status: "Completed", sc: "text-emerald-700 bg-emerald-50 border-emerald-200" },
  { id: "act_7a1b2c3d", ts: "Today 10:15", action: "Update opportunity stage",       tool: "Salesforce",  agent: "SalesAI",   ws: "Sales Ops",            approver: "—",         dec: "BLOCK",    status: "Blocked",   sc: "text-red-700 bg-red-50 border-red-200" },
];

function HowItWorks() {
  return (
    <section className="py-24 bg-zinc-50 border-y border-zinc-200">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <div className="max-w-[520px] mb-16">
          <Label>How It Works</Label>
          <h2 className="text-[32px] font-semibold leading-[1.2] tracking-tight text-zinc-900 mb-4">
            Every agent action, governed
          </h2>
          <p className="text-[15px] text-zinc-600 leading-relaxed">
            From the moment an agent proposes an action to the moment it
            completes, Action Marshall governs every step.
          </p>
        </div>

        {/* Steps */}
        <div className="relative grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-8 mb-16">
          <div className="hidden lg:block absolute left-5 right-5 h-px bg-zinc-200" style={{ top: "19px" }} />
          {STEPS.map((s) => (
            <div key={s.n} className="relative">
              <div className="relative z-10 w-[38px] h-[38px] rounded-full border-2 border-zinc-300 bg-white flex items-center justify-center text-[11px] font-semibold text-zinc-500 mb-4">
                {s.n}
                {s.cond && <div className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-violet-500 border-2 border-zinc-50" />}
              </div>
              <h3 className="text-[13px] font-semibold text-zinc-900 mb-1.5">
                {s.title}
                {s.cond && (
                  <span className="ml-2 text-[10px] font-medium text-violet-600 bg-violet-50 border border-violet-200 px-1.5 py-0.5 rounded align-middle">
                    if required
                  </span>
                )}
              </h3>
              <p className="text-[12px] text-zinc-500 leading-relaxed">{s.desc}</p>
            </div>
          ))}
        </div>

        {/* Audit log mockup */}
        <div className="bg-white border border-zinc-200 rounded-xl overflow-hidden shadow-sm">
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-zinc-200 bg-zinc-50">
            <span className="text-[12px] font-semibold text-zinc-700">Audit Trail</span>
            <div className="flex items-center gap-4">
              <span className="text-[11px] text-zinc-400 hover:text-zinc-700 cursor-pointer transition-colors">Export CSV</span>
              <span className="text-[11px] text-zinc-400 hover:text-zinc-700 cursor-pointer transition-colors">Export JSON Proofs</span>
            </div>
          </div>
          <div className="overflow-x-auto">
            <div className="min-w-[800px]">
              {/* Table header */}
              <div className="grid grid-cols-[130px_1fr_110px_70px_80px_80px] items-center px-5 py-2 border-b border-zinc-100 bg-zinc-50">
                {["Run ID / Time", "Action", "Approver", "Decision", "Status", ""].map((h, i) => (
                  <span key={i} className="text-[10px] font-semibold tracking-[0.1em] uppercase text-zinc-400">{h}</span>
                ))}
              </div>
              {/* Rows */}
              {AUDIT_ROWS.map((row) => (
                <div
                  key={row.id}
                  className="grid grid-cols-[130px_1fr_110px_70px_80px_80px] items-center px-5 py-3.5 border-b border-zinc-100 hover:bg-zinc-50 transition-colors duration-100"
                >
                  <div>
                    <div className="font-mono text-[10px] text-zinc-400">{row.id}</div>
                    <div className="text-[11px] text-zinc-500 mt-0.5">{row.ts}</div>
                  </div>
                  <div>
                    <div className="text-[13px] font-medium text-zinc-800">{row.action}</div>
                    <div className="text-[11px] text-zinc-500 mt-0.5">{row.tool} · {row.agent} · {row.ws}</div>
                  </div>
                  <div className="text-[12px] text-zinc-600">{row.approver}</div>
                  <div className="text-[12px] text-zinc-600">{row.dec}</div>
                  <div>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-[11px] font-medium ${row.sc}`}>
                      {row.status}
                    </span>
                  </div>
                  <div className="flex justify-end">
                    <span className="text-[11px] text-blue-600 hover:text-blue-800 cursor-pointer transition-colors">
                      View proof →
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Enterprise value ─────────────────────────────────────────────────
const PILLARS = [
  { n: "01", title: "Visibility", body: "See every agent action across every connected system — before execution, during canary, and after completion. Full attribution to the agent, workspace, and approver." },
  { n: "02", title: "Accountability", body: "Every action generates a signed proof receipt with the full execution record: who proposed it, who approved it, which policy version, which records changed." },
  { n: "03", title: "Safe deployment", body: "Canary execution and circuit breakers let you expand agent automation incrementally. Blast radius checks prevent accidental bulk modifications before they happen." },
  { n: "04", title: "Operational velocity", body: "Policy-based automation removes manual review bottlenecks for routine operations — while preserving human approval for high-risk actions. Agents move fast within defined limits." },
];

function EnterpriseValue() {
  return (
    <section id="enterprise" className="py-24 bg-white">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <div className="max-w-[540px] mb-16">
          <Label>Built for Enterprise</Label>
          <h2 className="text-[32px] font-semibold leading-[1.2] tracking-tight text-zinc-900 mb-4">
            Deploy agents without giving up control
          </h2>
          <p className="text-[15px] text-zinc-600 leading-relaxed">
            Action Marshall is designed for platform teams, security leaders, and the
            enterprise buyers who need to govern AI automation at scale.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-14 gap-y-10">
          {PILLARS.map((p) => (
            <div key={p.title} className="flex gap-5">
              <div className="shrink-0 w-8 h-8 rounded border border-zinc-200 bg-zinc-50 flex items-center justify-center text-[11px] font-semibold text-zinc-400 tabular-nums">
                {p.n}
              </div>
              <div>
                <h3 className="text-[13px] font-semibold text-zinc-900 mb-2">{p.title}</h3>
                <p className="text-[13px] text-zinc-600 leading-relaxed">{p.body}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── CTA ───────────────────────────────────────────────────────────────
function CTASection() {
  return (
    <section className="py-24 bg-zinc-950 border-t border-zinc-800">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10 text-center">
        <div className="max-w-[500px] mx-auto">
          <h2 className="text-[32px] font-semibold text-white tracking-tight mb-4">
            Govern agent actions in production.
          </h2>
          <p className="text-[15px] text-zinc-400 leading-relaxed mb-8">
            Action Marshall is production-ready for enterprise teams. Talk to us about
            your deployment, your connectors, and your governance requirements.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <a href="#" className="text-[13px] font-semibold bg-white text-zinc-900 px-5 py-2.5 rounded-md hover:bg-zinc-100 transition-colors duration-150">
              Request access
            </a>
            <a href="#" className="text-[13px] font-medium text-zinc-400 hover:text-white px-5 py-2.5 rounded-md border border-zinc-800 hover:border-zinc-600 transition-colors duration-150">
              Read documentation →
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Footer ────────────────────────────────────────────────────────────
function Footer() {
  const cols = [
    { heading: "Product",   links: ["Transactions", "Workspaces", "App Connections", "Audit Trail", "Approvals"] },
    { heading: "Resources", links: ["Documentation", "API Reference", "SDK", "Changelog", "Status"] },
    { heading: "Company",   links: ["About", "GitHub", "Security", "Privacy", "Terms"] },
  ];
  return (
    <footer className="bg-white border-t border-zinc-200 py-12">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1.6fr)_repeat(3,minmax(0,1fr))] gap-10">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-6 h-6 bg-zinc-900 rounded flex items-center justify-center">
                <span className="text-white text-[10px] font-bold">K</span>
              </div>
              <span className="text-[13px] font-semibold text-zinc-900">Action Marshall</span>
            </div>
            <p className="text-[12px] text-zinc-500 leading-relaxed max-w-[210px]">
              Transaction governance for AI agents.
              Precise. Auditable. Built for enterprise.
            </p>
          </div>
          {cols.map((col) => (
            <div key={col.heading}>
              <h4 className="text-[11px] font-semibold text-zinc-900 mb-3 tracking-wide uppercase">{col.heading}</h4>
              <ul className="space-y-2">
                {col.links.map((link) => (
                  <li key={link}>
                    <a href="#" className="text-[12px] text-zinc-500 hover:text-zinc-900 transition-colors duration-150">{link}</a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="flex flex-col md:flex-row items-center justify-between gap-3 mt-10 pt-6 border-t border-zinc-200">
          <span className="text-[11px] text-zinc-400">© 2025 Action Marshall. All rights reserved.</span>
          <div className="flex items-center gap-5">
            {["Privacy Policy", "Terms of Service", "Security"].map((item) => (
              <a key={item} href="#" className="text-[11px] text-zinc-400 hover:text-zinc-600 transition-colors duration-150">{item}</a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}

// ── Page ──────────────────────────────────────────────────────────────
export default function Home() {
  return (
    <>
      <Nav />
      <main className="pt-16">
        <Hero />
        <TrustBar />
        <Problem />
        <ProductSection />
        <Capabilities />
        <HowItWorks />
        <EnterpriseValue />
        <CTASection />
      </main>
      <Footer />
    </>
  );
}
