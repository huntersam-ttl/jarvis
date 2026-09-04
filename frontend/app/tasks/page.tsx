"use client";

import { Card, PageHeader, StatusDot } from "@/components/ui";

type TaskRow = {
  id: string;
  name: string;
  status: "queued" | "running" | "completed" | "failed";
  detail: string;
};

// v0 shows the run-tracking foundation. Rows are static until the task
// engine (Phase 1+) persists real runs; chat runs are visible in Jarvis.
const TASKS: TaskRow[] = [
  {
    id: "task-system",
    name: "Task / run tracking",
    status: "completed",
    detail: "Every Jarvis chat records provider, model, duration, success",
  },
  {
    id: "task-engine",
    name: "Task engine (queued jobs, scheduling)",
    status: "queued",
    detail: "Planned — foundation ready, not started",
  },
];

export default function TasksPage() {
  return (
    <>
      <PageHeader
        title="Tasks"
        subtitle="Run tracking and the future task engine"
      />
      <Card eyebrow="v0" title="Task System">
        <ul className="space-y-2">
          {TASKS.map((t) => (
            <li
              key={t.id}
              className="flex items-center gap-3 rounded-xl border border-white/5 bg-ink-850/60 px-4 py-3"
            >
              <StatusDot
                status={
                  t.status === "completed"
                    ? "ok"
                    : t.status === "running"
                      ? "warn"
                      : t.status === "failed"
                        ? "bad"
                        : "idle"
                }
                animate={t.status === "running"}
              />
              <div className="min-w-0">
                <div className="text-sm font-medium text-white">{t.name}</div>
                <div className="truncate text-xs text-slate-500">{t.detail}</div>
              </div>
              <span className="ml-auto shrink-0 text-xs capitalize text-slate-400">
                {t.status}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
