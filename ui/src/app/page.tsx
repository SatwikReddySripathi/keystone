"use client";
import { useEffect, useState } from "react";
import { fetchActions } from "@/lib/api";
import { Badge, parseJson, timeAgo } from "@/lib/components";
import Link from "next/link";

const STATUS_MAP: Record<string, { label: string; color: string; icon: string }> = {
  completed: { label: "Completed", color: "green", icon: "✓" },
  blocked: { label: "Blocked", color: "red", icon: "■" },
  contained: { label: "Contained", color: "amber", icon: "▲" },
  observed: { label: "Observed", color: "sky", icon: "◆" },
  awaiting_approval: { label: "Pending Approval", color: "violet", icon: "◎" },
  approved: { label: "Approved", color: "green", icon: "✓" },
  pending: { label: "Pending", color: "gray", icon: "○" },
};

export default function ActionsPage() {
  const [actions, setActions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => { setLoading(true); fetchActions().then(setActions).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, []);

  const completed = actions.filter((a: any) => a.status === "completed").length;
  const contained = actions.filter((a: any) => a.status === "contained").length;
  const blocked = actions.filter((a: any) => a.status === "blocked").length;
  const total = actions.length;

  return (
    <div>
      {/* Hero */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-1">
          <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
            Transaction Governance
          </h1>
          <Badge color="white">Live</Badge>
        </div>
        <p className="text-gray-500 text-sm">
          Every agent action - Previewed, Policy-Checked, Canary-Tested, and Signed.
        </p>
      </div>

      {/* Stats */}
      {total > 0 && (
        <div className="grid grid-cols-4 gap-3 mb-8">
          {[
            { n: total, label: "Total", color: "text-white" },
            { n: completed, label: "Completed", color: "text-emerald-400" },
            { n: contained, label: "Contained", color: "text-amber-400" },
            { n: blocked, label: "Blocked", color: "text-red-400" },
          ].map((s, i) => (
            <div key={i} className="rounded-lg border border-gray-800 bg-gray-900/40 px-4 py-4 text-center">
              <div className={`text-3xl font-bold ${s.color}`}>{s.n}</div>
              <div className="text-xs text-gray-400 mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Actions List */}
      {loading ? (
        <div className="text-gray-600 py-20 text-center">Loading...</div>
      ) : actions.length === 0 ? (
        <div className="py-20 text-center rounded-xl border border-dashed border-gray-800">
          <div className="text-4xl mb-4 opacity-20">◆</div>
          <p className="text-gray-400 mb-2">No actions yet</p>
          <code className="text-xs bg-gray-900 px-3 py-1.5 rounded-lg text-gray-500">python demo.py</code>
        </div>
      ) : (
        <div className="space-y-2">
          {actions.map((a: any) => {
            const st = STATUS_MAP[a.status] || STATUS_MAP.pending;
            const actor = parseJson(a.actor_json);
            return (
              <Link key={a.action_id} href={`/actions/${a.action_id}`}
                className="group block rounded-xl border border-gray-800/50 bg-gray-900/20 hover:bg-gray-900/50 hover:border-gray-700/60 transition-all px-5 py-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-4 min-w-0">
                    {/* Status Icon */}
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center text-sm border ${
                      st.color === "green" ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400" :
                      st.color === "red" ? "bg-red-500/10 border-red-500/20 text-red-400" :
                      st.color === "amber" ? "bg-amber-500/10 border-amber-500/20 text-amber-400" :
                      st.color === "sky" ? "bg-sky-500/10 border-sky-500/20 text-sky-400" :
                      st.color === "violet" ? "bg-violet-500/10 border-violet-500/20 text-violet-400" :
                      "bg-gray-800 border-gray-700 text-gray-500"
                    }`}>{st.icon}</div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-sm font-medium text-gray-200">{a.tool}.{a.action_type}</span>
                        <Badge color={st.color}>{st.label}</Badge>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-gray-600">
                        <span>by {actor?.name || "Unknown Agent"}</span>
                        <span className="font-mono">{a.action_id}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-xs text-gray-600">{timeAgo(a.created_at)}</span>
                    <span className="text-gray-700 group-hover:text-gray-400 transition text-lg">&rsaquo;</span>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {total > 0 && (
        <div className="mt-6 text-center">
          <button onClick={load} className="text-xs text-gray-600 hover:text-gray-400 transition px-4 py-2 rounded-lg border border-gray-800/40 hover:border-gray-700">
            Refresh
          </button>
        </div>
      )}
    </div>
  );
}