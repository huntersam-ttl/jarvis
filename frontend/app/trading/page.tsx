"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type {
  TradingActivityItem,
  TradingPosition,
  TradingStatus,
} from "@/types/api";
import { Card, PageHeader, StatusDot } from "@/components/ui";

type Perf = { today_pnl: number; total_pnl: number; trades_today: number };

function pnlTone(v: number): string {
  return v > 0 ? "text-ok" : v < 0 ? "text-bad" : "text-slate-300";
}

function fmtPnl(v: number): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}`;
}

export default function TradingPage() {
  const [status, setStatus] = useState<TradingStatus | null>(null);
  const [positions, setPositions] = useState<TradingPosition[]>([]);
  const [activity, setActivity] = useState<TradingActivityItem[]>([]);
  const [perf, setPerf] = useState<Perf | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, p, a, pf] = await Promise.all([
        api.tradingStatus(),
        api.tradingPositions().catch(() => []),
        api.tradingActivity().catch(() => []),
        api.tradingPerformance().catch(() => null),
      ]);
      setStatus(s);
      setPositions(p);
      setActivity(a);
      setPerf(pf);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Trading bridge unreachable");
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  async function command(cmd: "start" | "pause" | "resume" | "stop") {
    setBusy(cmd);
    setError(null);
    try {
      const res = await api.tradingCommand(cmd);
      if (!res.success && res.detail) setError(res.detail);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : `Command ${cmd} failed`);
    } finally {
      setBusy(null);
    }
  }

  const state = status?.state ?? "offline";
  const stateDot =
    state === "running"
      ? "ok"
      : state === "paused" || state === "error"
        ? "warn"
        : "idle";

  return (
    <>
      <PageHeader
        title="Trading"
        subtitle="Control and monitoring bridge to the trading agent"
      />

      {error && (
        <p className="mb-4 rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-sm text-bad">
          {error}
        </p>
      )}

      {/* Status + controls */}
      <Card
        eyebrow="Bridge"
        title="Agent Status"
        action={
          <button className="btn-ghost !py-1.5 !text-xs" onClick={load}>
            Refresh
          </button>
        }
      >
        {!status ? (
          <div className="h-16 rounded-lg shimmer animate-shimmer" />
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-xl border border-white/5 bg-ink-850/60 px-4 py-3">
                <div className="label-eyebrow mb-1">Connection</div>
                <div className="flex items-center gap-2 text-sm text-white">
                  <StatusDot status={status.connected ? "ok" : "bad"} />
                  {status.connected ? "Connected" : "Offline"}
                </div>
              </div>
              <div className="rounded-xl border border-white/5 bg-ink-850/60 px-4 py-3">
                <div className="label-eyebrow mb-1">Mode</div>
                <div className="text-sm uppercase tracking-wide text-white">
                  {status.mode}
                </div>
              </div>
              <div className="rounded-xl border border-white/5 bg-ink-850/60 px-4 py-3">
                <div className="label-eyebrow mb-1">State</div>
                <div className="flex items-center gap-2 text-sm capitalize text-white">
                  <StatusDot
                    status={stateDot}
                    animate={state === "running"}
                  />
                  {state}
                </div>
              </div>
              <div className="rounded-xl border border-white/5 bg-ink-850/60 px-4 py-3">
                <div className="label-eyebrow mb-1">Today's P&L</div>
                <div className={`text-sm font-medium ${pnlTone(status.today_pnl)}`}>
                  {fmtPnl(status.today_pnl)}
                </div>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                className="btn-primary"
                onClick={() => command("start")}
                disabled={busy !== null || state !== "offline"}
              >
                {busy === "start" ? "Starting…" : "Start"}
              </button>
              <button
                className="btn-ghost"
                onClick={() => command("pause")}
                disabled={busy !== null || state !== "running"}
              >
                {busy === "pause" ? "Pausing…" : "Pause"}
              </button>
              <button
                className="btn-ghost"
                onClick={() => command("resume")}
                disabled={busy !== null || state !== "paused"}
              >
                {busy === "resume" ? "Resuming…" : "Resume"}
              </button>
              <button
                className="btn-ghost !border-bad/40 !text-bad hover:!border-bad"
                onClick={() => command("stop")}
                disabled={busy !== null || state === "offline"}
              >
                {busy === "stop" ? "Stopping…" : "Stop"}
              </button>
            </div>

            <p className="mt-3 text-xs text-slate-600">
              Adapter: {status.adapter}
              {status.last_heartbeat &&
                ` · last heartbeat ${new Date(status.last_heartbeat).toLocaleTimeString()}`}
            </p>
          </>
        )}
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {/* Positions */}
        <Card eyebrow="Exposure" title="Open Positions">
          {positions.length === 0 ? (
            <p className="text-sm text-slate-500">No open positions.</p>
          ) : (
            <ul className="space-y-2">
              {positions.map((p) => (
                <li
                  key={p.symbol + p.side}
                  className="flex items-center gap-3 rounded-xl border border-white/5 bg-ink-850/60 px-4 py-2.5 text-sm"
                >
                  <span className="font-medium text-white">{p.symbol}</span>
                  <span
                    className={`rounded-md px-1.5 py-0.5 text-[10px] uppercase ${
                      p.side === "long"
                        ? "bg-ok/15 text-ok"
                        : "bg-bad/15 text-bad"
                    }`}
                  >
                    {p.side}
                  </span>
                  <span className="text-slate-400">
                    {p.qty} @ {p.entry_price}
                  </span>
                  <span className={`ml-auto font-medium ${pnlTone(p.unrealized_pnl)}`}>
                    {fmtPnl(p.unrealized_pnl)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Performance */}
        <Card eyebrow="Results" title="Performance">
          {!perf ? (
            <div className="h-16 rounded-lg shimmer animate-shimmer" />
          ) : (
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded-xl border border-white/5 bg-ink-850/60 px-3 py-3">
                <div className="label-eyebrow mb-1">Today</div>
                <div className={`text-sm font-medium ${pnlTone(perf.today_pnl)}`}>
                  {fmtPnl(perf.today_pnl)}
                </div>
              </div>
              <div className="rounded-xl border border-white/5 bg-ink-850/60 px-3 py-3">
                <div className="label-eyebrow mb-1">Total</div>
                <div className={`text-sm font-medium ${pnlTone(perf.total_pnl)}`}>
                  {fmtPnl(perf.total_pnl)}
                </div>
              </div>
              <div className="rounded-xl border border-white/5 bg-ink-850/60 px-3 py-3">
                <div className="label-eyebrow mb-1">Trades</div>
                <div className="text-sm font-medium text-white">
                  {perf.trades_today}
                </div>
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* Activity */}
      <Card className="mt-4" eyebrow="Log" title="Recent Activity">
        {activity.length === 0 ? (
          <p className="text-sm text-slate-500">No activity yet.</p>
        ) : (
          <ul className="space-y-2">
            {activity.map((a) => (
              <li
                key={a.id}
                className="flex items-center gap-3 rounded-xl border border-white/5 bg-ink-850/60 px-3 py-2 text-sm"
              >
                <StatusDot
                  status={
                    a.event === "error"
                      ? "bad"
                      : a.event === "stopped"
                        ? "warn"
                        : "ok"
                  }
                />
                <span className="w-16 shrink-0 capitalize text-slate-300">
                  {a.event}
                </span>
                <span className="min-w-0 truncate text-slate-500">
                  {a.detail}
                </span>
                <span className="ml-auto shrink-0 text-xs text-slate-600">
                  {a.time && new Date(a.time).toLocaleTimeString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
