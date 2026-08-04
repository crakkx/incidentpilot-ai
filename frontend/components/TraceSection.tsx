"use client";

import { useState } from "react";

export function TraceSection({
  title,
  subtitle,
  defaultOpen = false,
  children,
}: {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="glass-card overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-5 py-4 text-left hover:bg-slate-50 transition-colors"
      >
        <span className="flex items-center gap-2">
          <span className="font-bold text-sm text-slate-900">{title}</span>
          {subtitle && (
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-bold text-slate-600">
              {subtitle}
            </span>
          )}
        </span>
        <span className="font-mono text-xs text-slate-500 font-bold">{open ? "−" : "+"}</span>
      </button>
      {open && <div className="border-t border-slate-200 bg-slate-50/50 p-5 space-y-3">{children}</div>}
    </div>
  );
}

export function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="max-h-72 overflow-auto rounded-xl border border-slate-200 bg-slate-900 p-4 font-mono text-xs text-cyan-300 shadow-sm">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
