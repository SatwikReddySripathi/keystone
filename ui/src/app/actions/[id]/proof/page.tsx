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

  useEffect(() => { fetchProof(id).then(setData).catch(() => setData(null)).finally(() => setLoading(false)); }, [id]);

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

  if (loading) return <div className="py-20 text-center text-gray-600">Loading...</div>;
  if (!data) return (
    <div className="py-20 text-center">
      <p className="text-red-400 mb-3">Receipt not available</p>
      <Link href={`/actions/${id}`} className="text-indigo-400 text-sm">&larr; Back</Link>
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
      {/* Nav */}
      <div className="flex items-center gap-2 mb-6 text-sm">
        <Link href="/" className="text-gray-600 hover:text-gray-400">Actions</Link>
        <span className="text-gray-800">/</span>
        <Link href={`/actions/${id}`} className="text-gray-600 hover:text-gray-400 font-mono text-xs">{id}</Link>
        <span className="text-gray-800">/</span>
        <span className="text-gray-400">Audit Receipt</span>
      </div>

      {/* ── Cryptographic Artifact Card ── */}
      <div className={`rounded-2xl border-2 overflow-hidden mb-6 ${
        data.verified ? "border-emerald-500/30" : "border-red-500/30"
      }`}>
        {/* Header band */}
        <div className={`px-6 py-4 ${
          data.verified
            ? "bg-gradient-to-r from-emerald-500/10 to-emerald-900/10"
            : "bg-gradient-to-r from-red-500/10 to-red-900/10"
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-xl border-2 font-bold ${
                data.verified
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                  : "border-red-500/30 bg-red-500/10 text-red-400"
              }`}>
                {data.verified ? "V" : "X"}
              </div>
              <div>
                <h1 className={`text-lg font-bold ${data.verified ? "text-emerald-300" : "text-red-300"}`}>
                  {data.verified ? "Cryptographically Verified" : "Signature Mismatch"}
                </h1>
                <p className="text-xs text-gray-500">
                  Signed by Keystone &middot; HMAC-SHA256 &middot; {r.generated_at}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge color={data.verified ? "green" : "red"}>
                {data.verified ? "AUTHENTIC" : "TAMPERED"}
              </Badge>
            </div>
          </div>
        </div>

        {/* Signature block */}
        <div className="px-6 py-3 bg-black/30 border-t border-gray-800/30">
          <div className="flex items-center gap-3">
            <span className="text-[10px] text-gray-500 uppercase tracking-wider shrink-0">Signature</span>
            <code className="text-[11px] text-gray-600 break-all font-mono">{data.signature}</code>
          </div>
        </div>

        {/* Receipt ID + Hash */}
        <div className="px-6 py-3 border-t border-gray-800/20 flex items-center gap-6 text-xs">
          <div>
            <span className="text-gray-600">Receipt ID</span>
            <span className="text-gray-400 ml-2 font-mono">{r.action?.action_id || id}</span>
          </div>
          <div>
            <span className="text-gray-600">Preview Hash</span>
            <span className="text-indigo-400/70 ml-2 font-mono">{prev.preview_hash || "N/A"}</span>
          </div>
          <div>
            <span className="text-gray-600">Policy</span>
            <span className="text-gray-400 ml-2">v{pol.policy_version}</span>
          </div>
        </div>
      </div>

      {/* ── Summary Grid ── */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {/* WHO */}
        <div className="rounded-xl border border-gray-800/60 bg-gray-900/20 p-4">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">WHO</div>
          <div className="space-y-2">
            <div>
              <div className="text-sm text-gray-300">{r.action?.actor?.name || "Unknown"}</div>
              <div className="text-[10px] text-gray-600">Requested by ({r.action?.actor?.type})</div>
            </div>
            {(r.approvals || []).map((a: any, i: number) => (
              <div key={i} className="pt-2 border-t border-gray-800/30">
                <div className="text-sm text-emerald-400">{a.approver_json?.name || "Unknown"}</div>
                {a.approver_json?.designation && (
                  <div className="text-[10px] text-gray-400">{a.approver_json.designation}</div>
                )}
                <div className="text-[10px] text-gray-600">
                  {a.approver_json?.department ? `${a.approver_json.department} · ` : ""}
                  Approved via {a.channel}
                  {a.approver_json?.email && <span className="text-gray-700"> · {a.approver_json.email}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* WHAT */}
        <div className="rounded-xl border border-gray-800/60 bg-gray-900/20 p-4">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">WHAT</div>
          <div className="text-sm text-gray-300 mb-1">{r.action?.tool}.{r.action?.action_type}</div>
          <div className="text-xs text-gray-600 mb-2">{r.environment}</div>
          <div className="flex gap-2 flex-wrap">
            <div className="bg-gray-800/40 rounded-md px-2 py-1">
              <span className="text-[10px] text-gray-500">Blast</span>
              <span className="text-xs text-gray-300 ml-1 font-bold">{prev.blast_radius}</span>
            </div>
            <div className="bg-gray-800/40 rounded-md px-2 py-1">
              <span className="text-[10px] text-gray-500">Decision</span>
              <span className={`text-xs ml-1 font-bold ${
                pol.decision === "BLOCK" ? "text-red-400" :
                pol.decision === "CANARY" ? "text-sky-400" : "text-emerald-400"
              }`}>{pol.decision}</span>
            </div>
            <div className="bg-gray-800/40 rounded-md px-2 py-1">
              <span className="text-[10px] text-gray-500">Breaker</span>
              <span className={`text-xs ml-1 font-bold ${br.tripped ? "text-amber-400" : "text-emerald-400"}`}>
                {br.tripped ? "TRIPPED" : "CLEAR"}
              </span>
            </div>
          </div>
        </div>

        {/* WHEN */}
        <div className="rounded-xl border border-gray-800/60 bg-gray-900/20 p-4">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">WHEN</div>
          <div className="text-sm text-gray-300 mb-1">{r.generated_at}</div>
          <div className="text-xs text-gray-600 mb-2">{tl.length} events in lifecycle</div>
          <div className="text-xs text-gray-600">
            Checks: <span className="text-gray-300">{chk.filter((c: any) => c.passed).length}/{chk.length} passed</span>
          </div>
        </div>
      </div>

      {/* ── Export ── */}
      <div className="flex gap-2 mb-6">
        <button onClick={copy}
          className="px-4 py-2.5 text-sm rounded-xl bg-gray-800 hover:bg-gray-700 transition text-gray-300 border border-gray-700">
          {copied ? "✓ Copied" : "Copy JSON"}
        </button>
        <button onClick={download}
          className="px-4 py-2.5 text-sm rounded-xl bg-indigo-600 hover:bg-indigo-500 transition text-white font-medium">
          Export Receipt
        </button>
      </div>

      {/* ── Tabbed Content ── */}
      <div className="rounded-xl border border-gray-800/60 bg-gray-900/20 overflow-hidden">
        <div className="flex border-b border-gray-800/40">
          {(["summary", "json"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-5 py-3 text-sm font-medium transition ${
                tab === t ? "text-gray-200 border-b-2 border-indigo-500 bg-gray-900/40" : "text-gray-600 hover:text-gray-400"
              }`}>
              {t === "summary" ? "Formatted" : "Raw JSON"}
            </button>
          ))}
        </div>

        {tab === "summary" ? (
          <div className="p-5 space-y-5 max-h-[500px] overflow-y-auto">
            {/* Reasons */}
            {pol.reasons?.length > 0 && (
              <div>
                <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-2">Policy Reasons</h4>
                {pol.reasons.map((r: any, i: number) => (
                  <div key={i} className="bg-gray-800/20 rounded-lg px-4 py-2 mb-1 text-xs">
                    <Badge color={r.decision === "BLOCK" ? "red" : r.decision === "CANARY" ? "sky" : "green"}>
                      {r.decision}
                    </Badge>
                    <span className="text-gray-500 font-mono ml-2">{r.rule}</span>
                    <p className="text-gray-400 mt-1">{r.reason}</p>
                  </div>
                ))}
              </div>
            )}
            {/* Checks */}
            {chk.length > 0 && (
              <div>
                <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-2">Safety Invariants</h4>
                {chk.map((c: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-xs mb-1">
                    <span className={c.passed ? "text-emerald-400" : "text-red-400"}>{c.passed ? "✓" : "✗"}</span>
                    <span className="text-gray-400">{c.check_name}</span>
                  </div>
                ))}
              </div>
            )}
            {/* Timeline */}
            <div>
              <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-2">Timeline ({tl.length} events)</h4>
              {tl.map((e: any, i: number) => (
                <div key={i} className="flex gap-3 text-[11px] mb-0.5">
                  <span className="text-gray-700 font-mono w-36 shrink-0">{e.timestamp}</span>
                  <span className="text-gray-400">{e.type}</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <pre className="p-5 text-xs text-gray-500 overflow-auto max-h-[500px] font-mono">
            {JSON.stringify(data.receipt, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}