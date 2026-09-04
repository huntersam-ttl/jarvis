"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links: { href: string; label: string; icon: string; badge?: string }[] = [
  { href: "/", label: "Home", icon: "◈" },
  { href: "/jarvis", label: "Jarvis", icon: "◉" },
  { href: "/tasks", label: "Tasks", icon: "≡" },
  { href: "/coding", label: "Coding", icon: "⌘" },
  { href: "/trading", label: "Trading", icon: "↗" },
  { href: "/projects", label: "Projects", icon: "▦" },
  { href: "/memory", label: "Memory", icon: "◌" },
  { href: "/providers", label: "Providers", icon: "⬡" },
  { href: "/system", label: "System", icon: "⚙" },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <aside className="flex w-full shrink-0 flex-col gap-1 border-b border-white/5 bg-ink-900/60 px-3 py-4 backdrop-blur-xl md:h-screen md:w-60 md:border-b-0 md:border-r md:py-6">
      <div className="mb-6 flex items-center gap-3 px-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/15 text-lg text-accent shadow-glow">
          J
        </div>
        <div>
          <div className="text-sm font-semibold tracking-wide text-white">
            JARVIS
          </div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">
            Control Room
          </div>
        </div>
      </div>

      <nav className="flex flex-row flex-wrap gap-1 md:flex-col">
        {links.map((l) => {
          const active =
            l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`group relative flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition duration-200 ${
                active
                  ? "bg-accent/15 text-white shadow-glow"
                  : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
              }`}
            >
              <span
                className={`absolute left-0 top-1/2 hidden h-5 w-0.5 -translate-y-1/2 rounded-full bg-accent transition-opacity md:block ${
                  active ? "opacity-100" : "opacity-0 group-hover:opacity-40"
                }`}
              />
              <span
                className={`w-4 text-center transition-transform duration-200 ${
                  active ? "text-accent" : "text-slate-500 group-hover:scale-110"
                }`}
              >
                {l.icon}
              </span>
              <span className="font-medium">{l.label}</span>
              {l.badge && (
                <span className="ml-auto rounded-md bg-white/5 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
                  {l.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto hidden px-3 pt-6 text-[10px] uppercase tracking-[0.2em] text-slate-600 md:block">
        v0 · Personal AI
      </div>
    </aside>
  );
}
