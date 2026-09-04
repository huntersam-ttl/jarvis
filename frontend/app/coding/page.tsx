"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { CodingAgentStatus, CodingTask } from "@/types/api";
import { Card, PageHeader, StatusDot } from "@/components/ui";

const STATUS_LABEL: Record<string, string> = {
  ready: "Ready",
  working: "Working",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

const PIPELINE = ["ANALYZING", "PLANNING", "IMPLEMENTING", "TESTING", "REVIEWING", "VERIFYING", "COMPLETED"] as const;

function phaseIndex(phase?: string): number {
  if (!phase) return -1;
  if (phase === "DEBUGGING") return 2; // back to build step visually
  const idx = PIPELINE.indexOf(phase as (typeof PIPELINE)[number]);
  return idx;
}

function taskTone(status: string): { dot: "ok" | "warn" | "bad" | "idle"; cls: string } {
  if (status === "completed") return { dot: "ok", cls: "border-ok/25 bg-ok/10 text-ok" };
  if (status === "working" || status === "ready")
    return { dot: "warn", cls: "border-warn/25 bg-warn/10 text-warn" };
  if (status === "failed") return { dot: "bad", cls: "border-bad/25 bg-bad/10 text-bad" };
  return { dot: "idle", cls: "border-white/10 bg-ink-850/80 text-slate-400" };
}

function toolLabel(tool: string): string {
  const labels: Record<string, string> = {
    list_files: "Inspected project files",
    read_file: "Read a file",
    write_file: "Wrote a file",
    replace_text: "Edited a file",
    run_command: "Ran a command",
    git_status: "Checked git status",
    git_diff: "Reviewed changes",
    git_log: "Reviewed history",
    git_add: "Staged changes",
    git_commit: "Created a commit",
    run_tests: "Ran tests",
    run_build: "Ran build",
  };
  return labels[tool] ?? tool;
}

export default function CodingPage() {
  const [status, setStatus] = useState<CodingAgentStatus | null>(null);
  const [task, setTask] = useState<CodingTask | null>(null);
  const [instruction, setInstruction] = useState("");
  const [project, setProject] = useState("");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const s = await api.codingStatus();
      setStatus(s);
      setTask(s.task ?? null);
      if (!project && s.allowed_projects.length > 0) {
        setProject(s.allowed_projects[0]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Coding agent unreachable");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pollTask = useCallback(async (taskId: string) => {
    try {
      const t = await api.codingTask(taskId);
      setTask(t);
      if (t.status !== "working") {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = null;
      }
    } catch {
      // transient — keep polling
    }
  }, []);

  useEffect(() => {
    load();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [load]);

  function startPolling(taskId: string) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(() => pollTask(taskId), 2000);
  }

  async function start() {
    if (!instruction.trim() || starting) return;
    setStarting(true);
    setError(null);
    try {
      const t = await api.createCodingTask({
        instruction: instruction.trim(),
        project_path: project,
      });
      setTask(t);
      setInstruction("");
      startPolling(t.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the coding agent");
    } finally {
      setStarting(false);
    }
  }

  async function cancel() {
    if (!task) return;
    try {
      const res = await api.cancelCodingTask(task.id);
      setTask((prev) => (prev ? { ...prev, status: res.status } : prev));
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Cancel failed");
    }
  }

  const agentTone = taskTone(status?.status === "working" ? "working" : "ready");

  return (
    <>
      <PageHeader
        title="Coding Agent"
        subtitle="Delegate coding tasks to Jarvis — inspected, tested, and committed"
      />

      {error && (
        <p className="mb-4 rounded-xl border border-bad/30 bg-bad/10 px-4 py-2.5 text-sm text-bad">
          {error}
        </p>
      )}

      {/* Agent status */}
      <Card className="glass-hover">
        <div className="flex flex-wrap items-center gap-3">
          <span className={`chip ${agentTone.cls}`}>
            <StatusDot status={agentTone.dot} animate={status?.status === "working"} />
            {STATUS_LABEL[status?.status ?? "ready"] ?? status?.status}
          </span>
          {status && (
            <span className="text-xs text-slate-500">
              {status.allowed_projects.length} registered project
              {status.allowed_projects.length === 1 ? "" : "s"}
            </span>
          )}
        </div>
      </Card>

      {/* New task */}
      <Card className="mt-4" eyebrow="Delegate" title="New Coding Task">
        <div className="space-y-3">
          <div>
            <div className="label-eyebrow mb-1.5">Project</div>
            <select
              className="field"
              value={project}
              onChange={(e) => setProject(e.target.value)}
              disabled={status?.has_active_task}
            >
              {(status?.allowed_projects ?? []).map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
          <div>
            <div className="label-eyebrow mb-1.5">Instruction</div>
            <textarea
              className="field min-h-[90px] resize-y"
              placeholder="e.g. Run the tests and fix the failing frontend build"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              disabled={status?.has_active_task}
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              className="btn-primary"
              onClick={start}
              disabled={starting || !instruction.trim() || status?.has_active_task}
            >
              {starting ? "Starting…" : "Run Coding Agent"}
            </button>
            {task?.status === "working" && (
              <button className="btn-ghost" onClick={cancel}>
                Cancel
              </button>
            )}
          </div>
        </div>
      </Card>

      {/* Task */}
      {task && (
        <Card className="mt-4" eyebrow="Task" title={task.current_task}>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`chip ${taskTone(task.status).cls}`}>
              <StatusDot
                status={taskTone(task.status).dot}
                animate={task.status === "working"}
              />
              {STATUS_LABEL[task.status] ?? task.status}
            </span>
            <span className="chip border-white/10 bg-ink-850/80 text-slate-400">
              {task.project_path.split("/").pop() || task.project_path}
            </span>
            <span className="chip border-white/10 bg-ink-850/80 text-slate-400">
              {task.actions.length} action{task.actions.length === 1 ? "" : "s"}
            </span>
            {(task.skills_used ?? []).length > 0 && (
              <span className="chip border-accent/25 bg-accent/10 text-accent">
                ⌘ {(task.skills_used ?? []).length} skill
                {(task.skills_used ?? []).length === 1 ? "" : "s"}
              </span>
            )}
          </div>

          {/* Task pipeline */}
          <div className="mt-5 flex flex-wrap items-center gap-1.5">
            {PIPELINE.map((p, i) => {
              const cur = phaseIndex(task.phase);
              const state =
                task.phase === "FAILED" || task.phase === "CANCELLED"
                  ? i <= cur
                    ? "bad"
                    : "idle"
                  : i < cur
                    ? "done"
                    : i === cur
                      ? "active"
                      : "idle";
              return (
                <span key={p} className="flex items-center gap-1.5">
                  <span
                    className={`rounded-full px-2.5 py-1 text-[10px] font-medium uppercase tracking-wider transition-colors duration-300 ${
                      state === "done"
                        ? "bg-ok/10 text-ok"
                        : state === "active"
                          ? "bg-accent/15 text-accent shadow-glow"
                          : state === "bad"
                            ? "bg-bad/10 text-bad"
                            : "bg-ink-850/80 text-slate-600"
                    }`}
                  >
                    {p === "IMPLEMENTING" ? "Build" : p === "VERIFYING" ? "Verify" : p.charAt(0) + p.slice(1).toLowerCase()}
                  </span>
                  {i < PIPELINE.length - 1 && (
                    <span className="text-slate-700">→</span>
                  )}
                </span>
              );
            })}
          </div>

          {/* Skills used */}
          {(task.skills_used ?? []).length > 0 && (
            <div className="mt-4 flex flex-wrap gap-1.5">
              {(task.skills_used ?? []).map((s) => (
                <span
                  key={s}
                  className="chip border-white/10 bg-ink-850/80 text-slate-400"
                  title={s}
                >
                  {s.replace(/-/g, " ")}
                </span>
              ))}
            </div>
          )}

          {/* Verification result */}
          {task.verification && (
            <div
              className={`mt-4 rounded-xl border px-4 py-3 ${
                task.verification.passed
                  ? "border-ok/25 bg-ok/5"
                  : "border-bad/25 bg-bad/10"
              }`}
            >
              <div className="flex items-center gap-2 text-sm">
                <StatusDot status={task.verification.passed ? "ok" : "bad"} />
                <span
                  className={`font-medium ${task.verification.passed ? "text-ok" : "text-bad"}`}
                >
                  Verification {task.verification.passed ? "passed" : "failed"}
                </span>
                <span className="text-xs text-slate-500">
                  {task.verification.summary}
                </span>
              </div>
            </div>
          )}

          {/* Review result */}
          {task.review && task.review.verdict !== "skipped" && (
            <div
              className={`mt-3 rounded-xl border px-4 py-3 ${
                task.review.verdict === "approve"
                  ? "border-ok/25 bg-ok/5"
                  : "border-warn/25 bg-warn/10"
              }`}
            >
              <div className="flex items-center gap-2 text-sm">
                <StatusDot
                  status={task.review.verdict === "approve" ? "ok" : "warn"}
                />
                <span
                  className={`font-medium ${
                    task.review.verdict === "approve" ? "text-ok" : "text-warn"
                  }`}
                >
                  Review: {task.review.verdict}
                </span>
                <span className="text-xs text-slate-500">{task.review.summary}</span>
              </div>
            </div>
          )}

          {task.result && (
            <p className="mt-4 rounded-xl border border-ok/20 bg-ok/5 px-4 py-3 text-sm leading-relaxed text-slate-200">
              {task.result}
            </p>
          )}
          {task.last_error && (
            <p className="mt-4 rounded-xl border border-bad/25 bg-bad/10 px-4 py-3 text-sm leading-relaxed text-bad">
              {task.last_error}
            </p>
          )}

          {/* Progress timeline */}
          {task.actions.length > 0 && (
            <div className="mt-5">
              <div className="label-eyebrow mb-3">Progress</div>
              <ol className="space-y-2">
                {task.actions.map((a) => (
                  <li
                    key={a.id}
                    className="flex items-center gap-3 rounded-xl border border-white/5 bg-ink-850/60 px-4 py-2.5 text-sm"
                  >
                    <StatusDot
                      status={a.ok ? "ok" : a.approval_required ? "warn" : "bad"}
                    />
                    <span className="min-w-0 flex-1 truncate text-slate-300">
                      {toolLabel(a.tool)}
                      {a.detail && <span className="text-slate-500"> — {a.detail}</span>}
                    </span>
                    <span className="shrink-0 text-xs text-slate-600">step {a.step}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Advanced disclosure */}
          <details className="group mt-5 rounded-xl border border-white/5 bg-ink-850/60">
            <summary className="flex cursor-pointer select-none items-center justify-between px-4 py-3 text-sm text-slate-300 transition hover:text-white">
              <span>Advanced — technical details</span>
              <span className="text-xs text-slate-500 transition group-open:rotate-180">
                ▾
              </span>
            </summary>
            <div className="space-y-3 border-t border-white/5 p-4">
              <div className="text-xs text-slate-500">
                Task ID: <span className="font-mono text-slate-400">{task.id}</span> ·
                Steps: {task.steps_taken} · Model calls: {task.model_calls ?? 0} ·
                Repair loops: {task.repair_loops ?? 0}
                {task.git_commit && (
                  <>
                    {" "}· Commit:{" "}
                    <span className="font-mono text-slate-400">{task.git_commit}</span>
                  </>
                )}
              </div>

              {task.plan && (task.plan.steps?.length ?? 0) > 0 && (
                <div className="rounded-lg border border-white/5 bg-ink-950/60 p-3">
                  <div className="label-eyebrow mb-2">
                    Plan — {task.plan.complexity}
                  </div>
                  <ol className="space-y-1 text-xs text-slate-400">
                    {(task.plan.steps ?? []).map((s, i) => (
                      <li key={i}>
                        {i + 1}. {s.title}
                        {s.verify && (
                          <span className="text-slate-600"> · verify: {s.verify}</span>
                        )}
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {task.verification && (task.verification.checks?.length ?? 0) > 0 && (
                <div className="rounded-lg border border-white/5 bg-ink-950/60 p-3">
                  <div className="label-eyebrow mb-2">Verification checks</div>
                  <ul className="space-y-1 font-mono text-[11px] text-slate-500">
                    {(task.verification.checks ?? []).map((c, i) => (
                      <li key={i} className={c.ok ? "text-ok" : "text-bad"}>
                        {c.ok ? "✔" : "✘"} $ {c.command} ({c.duration_ms}ms)
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="max-h-80 space-y-2 overflow-y-auto">
                {task.actions.map((a) => (
                  <div
                    key={a.id}
                    className="rounded-lg border border-white/5 bg-ink-950/60 p-3"
                  >
                    <div className="mb-1 font-mono text-[11px] text-slate-400">
                      step {a.step} · {a.tool}({a.args_summary}) · {a.duration_ms}ms
                    </div>
                    {a.output_preview && (
                      <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-all font-mono text-[11px] leading-relaxed text-slate-500">
                        {a.output_preview}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </details>
        </Card>
      )}
    </>
  );
}

