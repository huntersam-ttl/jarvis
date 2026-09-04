"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ProviderList, ProviderModelList } from "@/types/api";
import { Card, PageHeader, StatusChip } from "@/components/ui";

export default function ProvidersPage() {
  const [providers, setProviders] = useState<ProviderList | null>(null);
  const [models, setModels] = useState<ProviderModelList | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [p, m] = await Promise.all([
        api.providers(),
        api.openrouterModels().catch(() => null),
      ]);
      setProviders(p);
      setModels(m);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load providers");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openrouter = providers?.providers.find((p) => p.name === "openrouter");

  return (
    <>
      <PageHeader
        title="Providers"
        subtitle="AI provider configuration and status"
      />

      {error && (
        <p className="mb-4 rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-sm text-bad">
          {error}
        </p>
      )}

      <Card
        eyebrow="AI Provider"
        title="OpenRouter"
        action={
          <button className="btn-ghost !py-1.5 !text-xs" onClick={load}>
            Refresh
          </button>
        }
      >
        {!openrouter ? (
          <div className="h-20 rounded-lg shimmer animate-shimmer" />
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <StatusChip
                status={openrouter.status}
                animate={openrouter.status === "offline"}
              />
              <span className="ml-auto text-xs text-slate-500">
                {openrouter.api_key_configured
                  ? "API key: Configured"
                  : "API key: Missing"}
              </span>
            </div>

            <dl className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-white/5 bg-ink-850/60 px-4 py-3">
                <dt className="label-eyebrow mb-1">Default model</dt>
                <dd className="truncate font-mono text-xs text-slate-300">
                  {openrouter.default_model || "—"}
                </dd>
              </div>
              <div className="rounded-xl border border-white/5 bg-ink-850/60 px-4 py-3">
                <dt className="label-eyebrow mb-1">Available models</dt>
                <dd className="text-sm text-slate-300">
                  {openrouter.model_count != null
                    ? `${openrouter.model_count} models`
                    : "—"}
                </dd>
              </div>
              <div className="rounded-xl border border-white/5 bg-ink-850/60 px-4 py-3 sm:col-span-2">
                <dt className="label-eyebrow mb-1">API key</dt>
                <dd className="text-sm text-slate-300">
                  {openrouter.api_key_configured ? (
                    <span className="text-ok">Configured</span>
                  ) : (
                    <span className="text-bad">Missing</span>
                  )}
                  {" — set OPENROUTER_API_KEY in .env (never shown)"}
                </dd>
              </div>
            </dl>

            <div className="space-y-3">
              {models && (
                <details className="group rounded-xl border border-white/5 bg-ink-850/60">
                  <summary className="flex cursor-pointer select-none items-center justify-between px-4 py-3 text-sm text-slate-300 transition hover:text-white">
                    <span>
                      Model catalog
                      <span className="ml-2 text-xs text-slate-500">
                        {models.count} available
                      </span>
                    </span>
                    <span className="text-xs text-slate-500 transition group-open:rotate-180">
                      ▾
                    </span>
                  </summary>
                  <div className="max-h-72 overflow-y-auto border-t border-white/5 p-3">
                    <ul className="grid gap-1 font-mono text-xs text-slate-400 sm:grid-cols-2">
                      {models.models.map((m) => (
                        <li key={m.id} className="truncate">
                          {m.id}
                        </li>
                      ))}
                    </ul>
                  </div>
                </details>
              )}
              <details className="group rounded-xl border border-white/5 bg-ink-850/60">
                <summary className="flex cursor-pointer select-none items-center justify-between px-4 py-3 text-sm text-slate-300 transition hover:text-white">
                  <span>Advanced / connection details</span>
                  <span className="text-xs text-slate-500 transition group-open:rotate-180">
                    ▾
                  </span>
                </summary>
                <div className="border-t border-white/5 px-4 py-3">
                  <div className="label-eyebrow mb-1">Base URL</div>
                  <div className="truncate font-mono text-xs text-slate-400">
                    {openrouter.base_url || "—"}
                  </div>
                </div>
              </details>
            </div>
          </div>
        )}
      </Card>
    </>
  );
}
