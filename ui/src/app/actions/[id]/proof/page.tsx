"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { fetchProof } from "@/lib/api";
import { Badge } from "@/lib/components";
import Link from "next/link";

export default function ProofPage() {
  const params = useParams();
  const id = params.id as string;
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [tab, setTab] = useState<"summary" | "json">("summary");

  useEffect(() => {
    fetchProof(id).then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }, [id]);

  const copy = () => {
    if (!data) return;
    navigator.clipboard.writeText(JSON.stringify({ receipt: data.receipt, signature: data.signature }, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const download = () => {
    if (!data) return;
    const blob = new Blob([JSON.stringify({ receipt: data.receipt, signature: data.signature }, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `keystone-receipt-${id}.json`;
    a.click();
  };

  if (loading) return <div className="py-20 text-center text-ks-text2 text-sm">Loading...</div>;
  if (!data) return (
    <div className="py-20 text-center">
      <p className="text-red-600 dark:text-red-400 text-sm mb-3">Receipt not available</p>
      <Link href={`/actions/${id}`} className="text-indigo-600 dark:text-indigo-400 text-sm hover:underline">Back to action</Link>
    </div>
  );

  const r = data.receipt || {};
  const pol = r.policy || {};
  const prev = r.preview || {};
  const exec = r.execution || {};
  const br = exec.breaker || {};
  const chk = exec.checks || [];
  const tl = r.timeline || [];

  return (
    <div className="max-w-4xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 mb-5 text-sm">
        <Link href="/" className="text-ks-text2 hover:text-ks-text transition">Transactions</Link>
        <span className="text-ks-text3">/</span>
        <Link href={`/actions/${id}`} className="text-ks-text2 hover:text-ks-text transition font-mono text-xs">{id}</Link>
        <span className="text-ks-text3">/</span>
        <span className="text-ks-text3">Audit Receipt</span>
      </div>

      {/* Verification banner */}
      <div className={`rounded-lg border overflow-hidden mb-6 ${
        data.verified
          ? "border-emerald-200 dark:border-emerald-800"
          : "border-red-200 dark:border-red-800"
      }`}>
        <div className={`px-6 py-4 flex items-center justify-between ${
          data.verified
            ? "bg-emerald-50 dark:bg-emerald-950"
            : "bg-red-50 dark:bg-red-950"
        }`}>
          <div className="flex items-center gap-4">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold border ${
              data.verified
                ? "border-emerald-200 dark:border-emerald-700 bg-white dark:bg-emerald-900 text-emerald-700 dark:text-emerald-400"
                : "border-red-200 dark:border-red-700 bg-white dark:bg-red-900 text-red-700 dark:text-red-400"
            }`}>
              {data.verified ? "✓" : "✗"}
            </div>
            <div>
              <h1 className={`text-base font-semibold ${data.verified ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400"}`}>
                {data.verified ? "Cryptographically Verified" : "Signature Mismatch"}
              </h1>
              <p className="text-xs text-ks-text3 mt-0.5">
                Signed by Keystone · HMAC-SHA256 · {r.generated_at}
              </p>
            </div>
          </div>
          <Badge color={data.verified ? "green" : "red"}>
            {data.verified ? "Authentic" : "Tampered"}
          </Badge>
        </div>
        <div className={`px-6 py-2.5 border-t flex items-center gap-3 ${
          data.verified
            ? "border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/50"
            : "border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-950/50"
        }`}>
          <span className="text-[10px] text-ks-text3 uppercase tracking-wider shrink-0">Signature</span>
          <code className="text-[11px] text-ks-text2 break-all font-mono">{data.signature}</code>
        </div>
        <div className="px-6 py-2.5 border-t border-ks-border bg-ks-surface flex items-center gap-6 text-xs">
          <div>
            <span className="text-ks-text3">Receipt ID</span>
            <span className="text-ks-text ml-2 font-mono">{r.action?.action_id || id}</span>
          </div>
          <div>
            <span className="text-ks-text3">Preview Hash</span>
            <span className="text-indigo-600 dark:text-indigo-400 ml-2 font-mono">{prev.preview_hash || "N/A"}</span>
          </div>
          <div>
            <span className="text-ks-text3">Policy</span>
            <span className="text-ks-text ml-2">v{pol.policy_version}</span>
          </div>
        </div>
      </div>

      {/* WHO / WHAT / WHEN */}
      <div className="grid grid-cols-3 gap-4 mb-5">
        <div className="rounded-lg border border-ks-border bg-ks-surface shadow-sm dark:shadow-none p-4">
          <div className="text-[10px] text-ks-text3 uppercase tracking-wider font-semibold mb-3">Who</div>
          <div className="space-y-2">
            <div>
              <div className="text-sm text-ks-text font-medium">{r.action?.actor?.name || "Unknown"}</div>
              <div className="text-[10px] text-ks-text3">Agent ({r.action?.actor?.type})</div>
            </div>
            {(r.approvals || []).map((a: any, i: number) => (
              <div key={i} className="pt-2 border-t border-ks-border">
                <div className="text-sm text-emerald-700 dark:text-emerald-400 font-medium">{a.approver_json?.name || "Unknown"}</div>
                {a.approver_json?.designation && (
                  <div className="text-[10px] text-ks-text2">{a.approver_json.designation}</div>
                )}
                <div className="text-[10px] text-ks-text3">
                  {a.approver_json?.department ? `${a.approver_json.department} · ` : ""}
                  Approved via {a.channel}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-ks-border bg-ks-surface shadow-sm dark:shadow-none p-4">
          <div className="text-[10px] text-ks-text3 uppercase tracking-wider font-semibold mb-3">What</div>
          <div className="text-sm text-ks-text font-medium mb-1">{r.action?.tool}.{r.action?.action_type}</div>
          <div className="text-xs text-ks-text3 mb-3">{r.environment}</div>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-ks-text2">Blast radius</span>
              <span className="text-xs text-ks-text font-medium">{prev.blast_radius}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-ks-text2">Decision</span>
              <span className={`text-xs font-semibold ${
                pol.decision === "BLOCK" ? "text-red-600 dark:text-red-400" :
                pol.decision === "CANARY" ? "text-sky-600 dark:text-sky-400" : "text-emerald-600 dark:text-emerald-400"
              }`}>{pol.decision}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-ks-text2">Breaker</span>
              <span className={`text-xs font-semibold ${br.tripped ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                {br.tripped ? "Tripped" : "Clear"}
              </span>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-ks-border bg-ks-surface shadow-sm dark:shadow-none p-4">
          <div className="text-[10px] text-ks-text3 uppercase tracking-wider font-semibold mb-3">When</div>
          <div className="text-sm text-ks-text font-medium mb-1">{r.generated_at}</div>
          <div className="text-xs text-ks-text3 mb-2">{tl.length} lifecycle events</div>
          <div className="text-xs text-ks-text2">
            Checks: <span className="text-ks-text font-medium">{chk.filter((c: any) => c.passed).length}/{chk.length} passed</span>
          </div>
        </div>
      </div>

      {/* Export actions */}
      <div className="flex gap-2 mb-5">
        <button onClick={copy}
          className="px-4 py-2 text-sm rounded-lg bg-ks-surface border border-ks-border hover:bg-ks-hover transition text-ks-text">
          {copied ? "Copied" : "Copy JSON"}
        </button>
        <button onClick={download}
          className="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 transition text-white font-medium">
          Export Receipt
        </button>
        <Link href={`/actions/${id}`}
          className="px-4 py-2 text-sm rounded-lg border border-ks-border hover:bg-ks-hover transition text-ks-text2 ml-auto">
          Back to Action
        </Link>
      </div>

      {/* Tabbed content */}
      <div className="rounded-lg border border-ks-border bg-ks-surface shadow-sm dark:shadow-none overflow-hidden">
        <div className="flex border-b border-ks-border bg-ks-surface-2">
          {(["summary", "json"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-5 py-3 text-sm font-medium transition ${
                tab === t
                  ? "text-ks-text border-b-2 border-indigo-600 dark:border-indigo-400 bg-ks-surface"
                  : "text-ks-text3 hover:text-ks-text2"
              }`}>
              {t === "summary" ? "Formatted" : "Raw JSON"}
            </button>
          ))}
        </div>

        {tab === "summary" ? (
          <div className="p-5 space-y-5 max-h-[500px] overflow-y-auto">
            {pol.reasons?.length > 0 && (
              <div>
                <h4 className="text-xs text-ks-text3 uppercase tracking-wider font-semibold mb-2">Policy Reasons</h4>
                {pol.reasons.map((r: any, i: number) => (
                  <div key={i} className="rounded-lg border border-ks-border bg-ks-surface-2 px-4 py-2.5 mb-1.5">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge color={r.decision === "BLOCK" ? "red" : r.decision === "CANARY" ? "sky" : "green"}>
                        {r.decision}
                      </Badge>
                      <span className="text-ks-text3 font-mono text-xs">{r.rule}</span>
                    </div>
                    <p className="text-xs text-ks-text2">{r.reason}</p>
                  </div>
                ))}
              </div>
            )}
            {chk.length > 0 && (
              <div>
                <h4 className="text-xs text-ks-text3 uppercase tracking-wider font-semibold mb-2">Safety Invariants</h4>
                <div className="rounded-lg border border-ks-border divide-y divide-ks-border overflow-hidden">
                  {chk.map((c: any, i: number) => (
                    <div key={i} className="flex items-center gap-3 px-4 py-2.5 bg-ks-surface">
                      <div className={`w-1.5 h-1.5 rounded-full ${c.passed ? "bg-emerald-500" : "bg-red-500"}`} />
                      <span className={`text-xs ${c.passed ? "text-ks-text" : "text-red-600 dark:text-red-400"}`}>{c.check_name}</span>
                      <span className={`text-xs ml-auto font-medium ${c.passed ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
                        {c.passed ? "Passed" : "Failed"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div>
              <h4 className="text-xs text-ks-text3 uppercase tracking-wider font-semibold mb-2">
                Timeline ({tl.length} events)
              </h4>
              <div className="space-y-1">
                {tl.map((e: any, i: number) => (
                  <div key={i} className="flex gap-3 text-xs">
                    <span className="text-ks-text3 font-mono w-40 shrink-0">{e.timestamp}</span>
                    <span className="text-ks-text2">{e.type}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <pre className="p-5 text-xs text-ks-text2 overflow-auto max-h-[500px] font-mono leading-relaxed">
            {JSON.stringify(data.receipt, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
