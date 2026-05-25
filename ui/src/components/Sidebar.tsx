"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/lib/ThemeToggle";
import {
  LayoutDashboard,
  Briefcase,
  Box,
  Network,
  ShieldCheck,
  CheckSquare,
  FileSearch,
  LogOut,
  Crown,
} from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { pingHealth } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const NAV_ITEMS = [
  { name: "Global Overview", href: "/", icon: LayoutDashboard },
  { name: "Workspaces", href: "/workspaces", icon: Briefcase },
  { name: "Agents", href: "/agents", icon: Box },
  { name: "Connected Systems", href: "/systems", icon: Network },
  { name: "Policies", href: "/policies", icon: ShieldCheck },
  { name: "Approvals", href: "/approvals", icon: CheckSquare },
  { name: "Audit Trail", href: "/audit", icon: FileSearch },
];

type HealthState = "connecting" | "healthy" | "unreachable";

export function Sidebar() {
  const pathname = usePathname();
  const { me, logout } = useAuth();
  const [health, setHealth] = useState<HealthState>("connecting");
  const [lastPingAt, setLastPingAt] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    const check = async () => {
      const r = await pingHealth();
      if (!alive) return;
      setHealth(r.ok ? "healthy" : "unreachable");
      if (r.ok) setLastPingAt(Date.now());
    };
    check();
    const t = setInterval(check, 10_000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const healthCfg = {
    connecting:  { label: "Connecting…",     dot: "bg-zinc-400",    ping: false, text: "text-ks-text3" },
    healthy:     { label: "Backend online",  dot: "bg-emerald-500", ping: true,  text: "text-ks-text2" },
    unreachable: { label: "Backend offline", dot: "bg-red-500",     ping: false, text: "text-red-500" },
  }[health];

  return (
    <aside className="w-64 border-r border-ks-border bg-ks-surface flex flex-col h-screen sticky top-0 shrink-0 z-50">
      {/* Brand */}
      <div className="h-16 flex items-center px-6 border-b border-ks-border shrink-0">
        <Link href="/" className="flex items-center gap-2.5 shrink-0 group">
          <div className="w-6 h-6 rounded-md bg-ks-primary flex items-center justify-center text-white font-bold select-none shadow-[0_0_15px_rgba(79,70,229,0.5)] group-hover:shadow-[0_0_20px_rgba(79,70,229,0.7)] transition-shadow duration-300" style={{ fontSize: "12px" }}>
            K
          </div>
          <span className="text-[15px] font-semibold text-ks-text tracking-tight group-hover:text-ks-primary transition-colors">Action Marshall</span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-6 px-3 flex flex-col gap-1">
        <div className="text-[10px] font-bold text-ks-text3 uppercase tracking-wider mb-2 px-3">Governance Plane</div>
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          const Icon = item.icon;
          
          const badge = item.href === "/workspaces" && me?.pending_requests_as_admin
            ? me.pending_requests_as_admin : null;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 group relative",
                isActive
                  ? "text-ks-primary bg-ks-primary/10 shadow-sm"
                  : "text-ks-text2 hover:text-ks-text hover:bg-ks-hover"
              )}
            >
              {isActive && (
                <div className="absolute left-0 top-1.5 bottom-1.5 w-1 bg-ks-primary rounded-r-full" />
              )}
              <Icon className={cn("w-4 h-4", isActive ? "text-ks-primary" : "text-ks-text3 group-hover:text-ks-text2")} />
              <span className="flex-1">{item.name}</span>
              {badge ? (
                <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-full bg-violet-500/20 text-violet-500 border border-violet-500/30">
                  {badge}
                </span>
              ) : null}
            </Link>
          );
        })}
      </nav>

      {/* Footer: signed-in user + backend health */}
      <div className="p-4 border-t border-ks-border shrink-0 flex flex-col gap-3">
        {me && (
          <div className="flex items-center gap-3 p-2 rounded-lg bg-ks-surface-2/60 border border-ks-border">
            <div
              className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center text-[11px] font-semibold shrink-0 border",
                me.is_admin
                  ? "bg-violet-500/10 text-violet-500 border-violet-500/30"
                  : "bg-ks-surface text-ks-text2 border-ks-border"
              )}
            >
              {me.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className="text-[12px] font-semibold text-ks-text truncate">
                  {me.name}
                </span>
                {me.is_admin && (
                  <Crown className="w-3 h-3 text-violet-500 shrink-0" aria-label="Admin" />
                )}
              </div>
              <div className="text-[10px] text-ks-text3 truncate">
                {me.is_admin
                  ? "Admin · all workspaces"
                  : `${me.memberships.length} workspace${me.memberships.length !== 1 ? "s" : ""}`}
              </div>
            </div>
            <button
              onClick={logout}
              className="p-1.5 rounded text-ks-text3 hover:text-ks-text hover:bg-ks-hover transition-colors"
              title="Sign out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
        <div className="flex items-center justify-between">
          <div
            className="flex items-center gap-2"
            title={lastPingAt ? `Last ping: ${new Date(lastPingAt).toLocaleTimeString()}` : "No successful ping yet"}
          >
            <div className="relative flex items-center justify-center">
              <span className={cn("w-2 h-2 rounded-full z-10", healthCfg.dot)} />
              {healthCfg.ping && (
                <span className="absolute w-4 h-4 rounded-full bg-emerald-500 opacity-30 animate-ping" />
              )}
            </div>
            <span className={cn("text-[11px] font-medium", healthCfg.text)}>{healthCfg.label}</span>
          </div>
          <ThemeToggle />
        </div>
      </div>
    </aside>
  );
}
