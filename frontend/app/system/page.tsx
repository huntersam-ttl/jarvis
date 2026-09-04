"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { HealthResponse, SystemStatus } from "@/types/api";
import { Card, PageHeader, StatusChip, StatusDot, statusTone } from "@/components/ui";

export default function SystemPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [advanced, setAdvanced] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, h] = await Promise.all([
        api.systemStatus(),
        api.health().catch(() => null),
      ]);
      setStatus(s);
      setHealth(h);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Backend unreachable");
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <PageHeader
        title="System"
        subtitle="Overall Jarvis health and components"
      />

      {error && (
        <p className="mb-4 rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-sm text-bad">
          {error}
        </p>
      )}

      <Card
        eyebrow="Health"
        title="Overall Jarvis Health"
        action={
          <div className="flex gap-2">
            <button
              className="btn-ghost !py-1.5 !text-xs"
              onClick={() => setAdvanced((a) => !a)}
            >
              {advanced ? "Hide Advanced" : "Advanced / Developer View"}
            </button>
            <button className="btn-ghost !py-1.5 !text-xs" onClick={load}>
              Refresh
            </button>
          </div>
        }
      >
        {status ? (
          <div className="mb-4 flex items-center gap-3">
            <StatusDot
              status={statusTone(status.overall).dot}
              animate={status.overall !== "online"}
            />
            <span className="text-lg font-semibold capitalize text-white">
              {status.overall}
            </span>
          </div>
        ) : (
          <div className="mb-4 h-8 w-32 rounded-lg shimmer animate-shimmer" />
        )}

        {status ? (
          <ul className="space-y-2">
            {status.components.map((c) => {
              const tone = statusTone(c.status);
              return (
                <li
                  key={c.name}
                  className="flex items-center gap-3 rounded-xl border border-white/5 bg-ink-850/60 px-4 py-3 transition duration-200 hover:border-white/10 hover:bg-ink-800/60"
                >
                  <StatusChip status={c.status} animate={statusTone(c.status).dot === "warn"} />
                  <div className="min-w-0 ml-1">
                    <div className="text-sm font-medium text-white">{c.name}</div>
                    {c.detail && (
                      <div className="truncate text-xs text-slate-500">
                        {c.detail}
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <div className="space-y-2">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-12 rounded-xl shimmer animate-shimmer" />
            ))}
          </div>
        )}

        {advanced && (
          <div className="mt-4 rounded-xl border border-white/5 bg-ink-950/80 p-4">
            <div className="label-eyebrow mb-2">Developer View — raw status</div>
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all font-mono text-[11px] leading-relaxed text-slate-400">
              {JSON.stringify({ health, system: status }, null, 2)}
            </pre>
          </div>
        )}
      </Card>
    </>
  );
}
