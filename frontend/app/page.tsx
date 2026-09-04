"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { ChatResponse, ProviderList, SystemStatus } from "@/types/api";
import { Card, PageHeader, StatusDot, statusTone } from "@/components/ui";

type Activity = {
  id: string;
  time: string;
  text: string;
  ok: boolean;
};

export default function Home() {
  const router = useRouter();
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [providers, setProviders] = useState<ProviderList | null>(null);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [command, setCommand] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, p] = await Promise.all([
        api.systemStatus().catch(() => null),
        api.providers().catch(() => null),
      ]);
      setSystem(s);
      setProviders(p);
    } catch {
      // surfaces via nulls
    }
  }, []);

  useEffect(() => {
    load();
    try {
      const raw = localStorage.getItem("jarvis.activity");
      if (raw) setActivity(JSON.parse(raw));
    } catch {
      // ignore
    }
  }, [load]);

  const openrouter = providers?.providers.find((p) => p.name === "openrouter");
  const activeTask = system?.components.find((c) => c.name === "Tasks");

  function pushActivity(text: string, ok: boolean) {
    const entry: Activity = {
      id: crypto.randomUUID(),
      time: new Date().toLocaleTimeString(),
      text,
      ok,
    };
    const next = [entry, ...activity].slice(0, 8);
    setActivity(next);
    try {
      localStorage.setItem("jarvis.activity", JSON.stringify(next));
    } catch {
      // ignore
    }
  }

  async function sendCommand() {
    const message = command.trim();
    if (!message || sending) return;
    setSending(true);
    setError(null);
    try {
      const res: ChatResponse = await api.chat({ message });
      pushActivity(message, true);
      setCommand("");
      router.push(`/jarvis?q=${encodeURIComponent(message)}`);
      void res;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Command failed";
      setError(msg);
      pushActivity(message, false);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Jarvis Control Room"
        subtitle="Personal AI control system — v0"
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* System status */}
        <Card eyebrow="System" title="Jarvis Status" className="glass-hover">
          {system ? (
            <div className="flex items-center gap-3">
              <StatusDot
                status={statusTone(system.overall).dot}
                animate={system.overall !== "online"}
              />
              <div>
                <div className="text-sm font-medium capitalize text-white">
                  {system.overall}
                </div>
                <div className="text-xs text-slate-500">
                  {system.components.length} components
                </div>
              </div>
            </div>
          ) : (
            <div className="h-9 rounded-lg shimmer animate-shimmer" />
          )}
        </Card>

        {/* OpenRouter */}
        <Card eyebrow="AI Provider" title="OpenRouter">
          {openrouter ? (
            <div className="flex items-center gap-3">
              <StatusDot
                status={statusTone(openrouter.status).dot}
                animate={openrouter.status === "offline"}
              />
              <div>
                <div className="text-sm font-medium capitalize text-white">
                  {openrouter.status.replace("_", " ")}
                </div>
                <div className="truncate text-xs text-slate-500">
                  {openrouter.default_model || "model not set"}
                </div>
              </div>
            </div>
          ) : (
            <div className="h-9 rounded-lg shimmer animate-shimmer" />
          )}
        </Card>

        {/* Active task */}
        <Card eyebrow="Runs" title="Active Task">
          {activeTask ? (
            <div className="flex items-center gap-3">
              <StatusDot status={statusTone(activeTask.status).dot} />
              <div>
                <div className="text-sm font-medium text-white">
                  {activeTask.status}
                </div>
                <div className="text-xs text-slate-500">
                  {activeTask.detail || "run tracking"}
                </div>
              </div>
            </div>
          ) : (
            <div className="h-9 rounded-lg shimmer animate-shimmer" />
          )}
        </Card>

        {/* Capability badges */}
        <Card eyebrow="Capabilities" title="Modules">
          <div className="space-y-2.5 text-sm">
            <div className="chip w-fit border-ok/25 bg-ok/10 text-ok">
              <StatusDot status="ok" />
              Coding · Ready
            </div>
            <div className="chip w-fit border-warn/25 bg-warn/10 text-warn">
              <StatusDot status="warn" />
              Trading · Bridge
            </div>
          </div>
        </Card>
      </div>

      {/* Command box */}
      <Card
        className="mt-4"
        eyebrow="Command"
        title="Ask Jarvis"
        action={
          <button className="btn-ghost !py-1.5 !text-xs" onClick={load}>
            Refresh
          </button>
        }
      >
        <div className="flex gap-2">
          <input
            className="field"
            placeholder='Type a command, e.g. "Hello Jarvis"'
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendCommand()}
            disabled={sending}
          />
          <button className="btn-primary" onClick={sendCommand} disabled={sending}>
            {sending ? "Sending…" : "Send"}
          </button>
        </div>
        {error && (
          <p className="mt-3 rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-sm text-bad">
            {error}
          </p>
        )}
      </Card>

      {/* Recent activity */}
      <Card className="mt-4" eyebrow="History" title="Recent Activity">
        {activity.length === 0 ? (
          <p className="text-sm text-slate-500">
            No activity yet. Send your first command above.
          </p>
        ) : (
          <ul className="space-y-2">
            {activity.map((a) => (
              <li
                key={a.id}
                className="flex items-center gap-3 rounded-xl border border-white/5 bg-ink-850/60 px-3 py-2 text-sm"
              >
                <StatusDot status={a.ok ? "ok" : "bad"} />
                <span className="truncate text-slate-300">{a.text}</span>
                <span className="ml-auto shrink-0 text-xs text-slate-600">
                  {a.time}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
