// Small shared UI primitives for the Jarvis Control Room.

export function StatusDot({
  status,
  animate,
}: {
  status: "ok" | "warn" | "bad" | "idle";
  animate?: boolean;
}) {
  const color =
    status === "ok"
      ? "bg-ok"
      : status === "warn"
        ? "bg-warn"
        : status === "bad"
          ? "bg-bad"
          : "bg-slate-600";
  return (
    <span className="relative inline-flex h-2.5 w-2.5">
      {animate && (
        <span
          className={`absolute inline-flex h-full w-full rounded-full ${color} opacity-60 animate-pulseDot`}
        />
      )}
      <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${color}`} />
    </span>
  );
}

export function statusTone(
  status: string
): { dot: "ok" | "warn" | "bad" | "idle"; label: string } {
  const s = status.toLowerCase();
  if (["online", "connected", "ready", "completed", "ok"].includes(s))
    return { dot: "ok", label: status };
  if (["degraded", "not_configured", "thinking", "planning", "executing"].includes(s))
    return { dot: "warn", label: status };
  if (["offline", "failed", "error"].includes(s)) return { dot: "bad", label: status };
  return { dot: "idle", label: status };
}

export function StatusChip({
  status,
  animate,
  className = "",
}: {
  status: string;
  animate?: boolean;
  className?: string;
}) {
  const tone = statusTone(status);
  const tint =
    tone.dot === "ok"
      ? "text-ok border-ok/25 bg-ok/10"
      : tone.dot === "warn"
        ? "text-warn border-warn/25 bg-warn/10"
        : tone.dot === "bad"
          ? "text-bad border-bad/25 bg-bad/10"
          : "text-slate-400 border-white/10 bg-ink-850/80";
  return (
    <span className={`chip capitalize ${tint} ${className}`}>
      <StatusDot status={tone.dot} animate={animate} />
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function Card({
  title,
  eyebrow,
  action,
  children,
  className = "",
}: {
  title?: string;
  eyebrow?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`glass card-pad animate-fadeUp ${className}`}>
      {(title || eyebrow) && (
        <header className="mb-4 flex items-center justify-between gap-3">
          <div>
            {eyebrow && <div className="label-eyebrow mb-1">{eyebrow}</div>}
            {title && (
              <h2 className="text-sm font-semibold text-white">{title}</h2>
            )}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function PlaceholderModule({
  title,
  phase,
  icon,
  bullets,
}: {
  title: string;
  phase: string;
  icon: string;
  bullets: string[];
}) {
  return (
    <Card eyebrow={`Phase ${phase}`} title={title}>
      <div className="flex items-start gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-2xl text-accent">
          {icon}
        </div>
        <div>
          <p className="mb-3 text-sm leading-relaxed text-slate-400">
            This module is intentionally not built yet. It is scaffolded so the
            architecture is ready when its phase begins.
          </p>
          <ul className="space-y-1.5 text-sm text-slate-400">
            {bullets.map((b) => (
              <li key={b} className="flex items-center gap-2">
                <span className="text-accent">›</span>
                {b}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  );
}

export function PageHeader({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) {
  return (
    <header className="mb-7 animate-fadeUp">
      <div className="flex items-center gap-3">
        <span className="h-6 w-1 rounded-full bg-gradient-to-b from-accent to-accent-glow" />
        <h1 className="text-2xl font-semibold tracking-tight text-white">{title}</h1>
      </div>
      {subtitle && (
        <p className="mt-1.5 pl-4 text-sm text-slate-500">{subtitle}</p>
      )}
    </header>
  );
}
