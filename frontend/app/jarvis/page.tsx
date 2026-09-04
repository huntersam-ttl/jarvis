"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import type { ChatResponse } from "@/types/api";
import { Card, PageHeader, StatusDot, statusTone } from "@/components/ui";

type Turn = {
  id: string;
  role: "user" | "jarvis";
  text: string;
  status?: "thinking" | "planning" | "executing" | "completed" | "failed";
  meta?: string;
};

const STAGE_LABEL: Record<NonNullable<Turn["status"]>, string> = {
  thinking: "Thinking",
  planning: "Planning",
  executing: "Executing",
  completed: "Completed",
  failed: "Failed",
};

function JarvisInner() {
  const searchParams = useSearchParams();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollDown = () =>
    requestAnimationFrame(() =>
      bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    );

  async function send(message: string) {
    const text = message.trim();
    if (!text || busy) return;
    setBusy(true);
    setError(null);

    const pendingId = crypto.randomUUID();
    setTurns((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", text },
      { id: pendingId, role: "jarvis", text: "", status: "thinking" },
    ]);
    scrollDown();

    // Visual stage progression while waiting on the model.
    const stageTimer = setTimeout(
      () =>
        setTurns((prev) =>
          prev.map((t) =>
            t.id === pendingId && t.status === "thinking"
              ? { ...t, status: "planning" }
              : t
          )
        ),
      2500
    );

    try {
      const res: ChatResponse = await api.chat({ message: text });
      clearTimeout(stageTimer);
      setTurns((prev) =>
        prev.map((t) =>
          t.id === pendingId
            ? {
                ...t,
                text: res.reply,
                status: "completed",
                meta: `${res.provider} · ${res.model} · ${Math.round(
                  res.run.duration_ms
                )} ms`,
              }
            : t
        )
      );
    } catch (e) {
      clearTimeout(stageTimer);
      const msg = e instanceof Error ? e.message : "Jarvis could not respond";
      setTurns((prev) =>
        prev.map((t) =>
          t.id === pendingId
            ? { ...t, text: msg, status: "failed" }
            : t
        )
      );
      setError(msg);
    } finally {
      setBusy(false);
      setInput("");
      scrollDown();
    }
  }

  // Support ?q= deep link from Home command box.
  useEffect(() => {
    const q = searchParams.get("q");
    if (q) {
      setTurns([]);
      send(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  return (
    <>
      <PageHeader
        title="Jarvis"
        subtitle="Natural-language command interface"
      />

      <Card className="flex min-h-[60vh] flex-col">
        <div className="flex-1 space-y-4 overflow-y-auto pr-1">
          {turns.length === 0 && (
            <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/15 text-2xl text-accent shadow-glow">
                J
              </div>
              <p className="text-sm text-slate-500">
                Send a command. Jarvis replies through OpenRouter.
              </p>
            </div>
          )}

          {turns.map((t) =>
            t.role === "user" ? (
              <div key={t.id} className="flex justify-end">
                <div className="max-w-[80%] rounded-2xl rounded-br-md bg-accent/20 px-4 py-2.5 text-sm text-slate-100">
                  {t.text}
                </div>
              </div>
            ) : (
              <div key={t.id} className="flex justify-start">
                <div className="max-w-[80%] rounded-2xl rounded-bl-md border border-white/5 bg-ink-850/80 px-4 py-2.5 text-sm text-slate-200">
                  {t.status && t.status !== "completed" && t.status !== "failed" && (
                    <div className="mb-1 flex items-center gap-2 text-xs text-warn">
                      <StatusDot status="warn" animate />
                      {STAGE_LABEL[t.status]}…
                    </div>
                  )}
                  {t.text && <p className="whitespace-pre-wrap">{t.text}</p>}
                  {t.status === "failed" && (
                    <div className="flex items-center gap-2 text-xs text-bad">
                      <StatusDot status="bad" />
                      {STAGE_LABEL.failed}
                    </div>
                  )}
                  {t.status === "completed" && (
                    <details className="group mt-1.5">
                      <summary className="flex w-fit cursor-pointer select-none items-center gap-1.5 text-[11px] text-slate-600 transition hover:text-slate-400">
                        <StatusDot status="ok" />
                        Completed
                        <span className="transition group-open:rotate-180">▾</span>
                      </summary>
                      <div className="mt-1 font-mono text-[11px] text-slate-600">
                        {t.meta}
                      </div>
                    </details>
                  )}
                </div>
              </div>
            )
          )}
          <div ref={bottomRef} />
        </div>

        <div className="mt-4 border-t border-white/5 pt-4">
          {error && (
            <p className="mb-3 rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-sm text-bad">
              {error}
            </p>
          )}
          <div className="flex gap-2">
            <input
              className="field"
              placeholder="Talk to Jarvis…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send(input)}
              disabled={busy}
            />
            <button
              className="btn-primary"
              onClick={() => send(input)}
              disabled={busy || !input.trim()}
            >
              {busy ? STAGE_LABEL.executing : "Send"}
            </button>
          </div>
        </div>
      </Card>
    </>
  );
}

export default function JarvisPage() {
  return (
    <Suspense fallback={<PageHeader title="Jarvis" />}>
      <JarvisInner />
    </Suspense>
  );
}
