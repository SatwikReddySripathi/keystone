"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw, Pause, Play } from "lucide-react";

/**
 * Auto-refresh hook.
 *
 *   const { loading, refreshing, lastUpdatedAt, paused, togglePause, refresh } =
 *     useAutoRefresh(loadData, 5000);
 *
 * `loadData` is called once on mount and then every `intervalMs` while the
 * tab is visible and not paused. Call `refresh()` manually for an immediate
 * tick. The hook does NOT hold data — your caller sets state from inside
 * `loadData`. That keeps the shape of each page's state unchanged.
 */
export function useAutoRefresh(loadData: () => Promise<void> | void, intervalMs = 5000) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  const [paused, setPaused] = useState(false);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;
  const loadRef = useRef(loadData);
  loadRef.current = loadData;

  const run = useCallback(async (isInitial: boolean) => {
    if (isInitial) setLoading(true);
    else setRefreshing(true);
    try {
      await loadRef.current();
      setLastUpdatedAt(Date.now());
    } catch {
      // callers handle their own errors
    } finally {
      if (isInitial) setLoading(false);
      else setRefreshing(false);
    }
  }, []);

  const refresh = useCallback(() => run(false), [run]);

  useEffect(() => {
    run(true);
  }, [run]);

  useEffect(() => {
    const tick = () => {
      if (pausedRef.current) return;
      if (document.visibilityState !== "visible") return;
      run(false);
    };
    const t = setInterval(tick, intervalMs);
    return () => clearInterval(t);
  }, [intervalMs, run]);

  const togglePause = useCallback(() => setPaused((p) => !p), []);

  return { loading, refreshing, lastUpdatedAt, paused, togglePause, refresh };
}


/** Human-readable time-ago for a timestamp in ms. Ticks live. */
function useLiveAgo(lastUpdatedAt: number | null): string {
  const [, forceTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => forceTick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);
  if (!lastUpdatedAt) return "never";
  const diff = Math.floor((Date.now() - lastUpdatedAt) / 1000);
  if (diff < 2) return "just now";
  if (diff < 60) return `${diff}s ago`;
  const mins = Math.floor(diff / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ago`;
}


/**
 * Compact refresh indicator. Shows last-updated, manual refresh button,
 * and pause/resume toggle. Place near the page header.
 */
export function RefreshControl({
  refreshing,
  lastUpdatedAt,
  paused,
  togglePause,
  refresh,
  intervalLabel,
}: {
  refreshing: boolean;
  lastUpdatedAt: number | null;
  paused: boolean;
  togglePause: () => void;
  refresh: () => void;
  intervalLabel?: string;
}) {
  const ago = useLiveAgo(lastUpdatedAt);
  return (
    <div className="inline-flex items-center gap-2 px-2 py-1 rounded-lg bg-ks-surface-2/60 border border-ks-border text-[11px] font-mono">
      <div className="flex items-center gap-1.5">
        <div
          className={`w-1.5 h-1.5 rounded-full ${
            paused
              ? "bg-zinc-400"
              : refreshing
                ? "bg-sky-500 animate-pulse"
                : "bg-emerald-500"
          }`}
        />
        <span className="text-ks-text3 uppercase tracking-wider">
          {paused ? "Paused" : "Live"}
          {intervalLabel && !paused ? ` · ${intervalLabel}` : ""}
        </span>
        <span className="text-ks-text3">·</span>
        <span className="text-ks-text2">{ago}</span>
      </div>
      <div className="flex items-center gap-0.5 ml-1 border-l border-ks-border/50 pl-1.5">
        <button
          onClick={refresh}
          disabled={refreshing}
          className="p-1 rounded text-ks-text3 hover:text-ks-text hover:bg-ks-hover transition-colors disabled:opacity-50"
          title="Refresh now"
        >
          <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} />
        </button>
        <button
          onClick={togglePause}
          className="p-1 rounded text-ks-text3 hover:text-ks-text hover:bg-ks-hover transition-colors"
          title={paused ? "Resume auto-refresh" : "Pause auto-refresh"}
        >
          {paused ? <Play className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
        </button>
      </div>
    </div>
  );
}
