"use client";

import { EvidenceItem, ObservationItem } from "@/lib/api";

const SOURCE_TYPE_STYLES: Record<string, string> = {
  log: "bg-blue-50 text-blue-700 border-blue-200",
  metric: "bg-indigo-50 text-indigo-700 border-indigo-200",
  deployment: "bg-purple-50 text-purple-700 border-purple-200",
  runbook: "bg-teal-50 text-teal-700 border-teal-200",
};

export function ObservationList({
  observations,
  evidence,
  selectedId,
  onSelect,
}: {
  observations: ObservationItem[];
  evidence: EvidenceItem[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  if (observations.length === 0) {
    return <p className="text-sm text-slate-500">No discrete observations were extracted.</p>;
  }

  return (
    <ul className="space-y-2">
      {observations.map((obs) => {
        const active = selectedId === obs.id;
        const citedCount = obs.source_ids.length;
        return (
          <li key={obs.id}>
            <button
              onClick={() => onSelect(active ? null : obs.id)}
              className={`w-full rounded-xl border p-3 text-left transition-all ${
                active
                  ? "border-indigo-500 bg-indigo-50/50 shadow-sm"
                  : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-sm text-slate-900">{obs.concept}</span>
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-bold text-slate-600">
                  {citedCount > 0
                    ? `${citedCount} source${citedCount > 1 ? "s" : ""}`
                    : "no sources"}
                </span>
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function CitedEvidencePanel({
  observation,
  evidence,
}: {
  observation: ObservationItem;
  evidence: EvidenceItem[];
}) {
  const cited = evidence.filter((e) => observation.source_ids.includes(e.source_id));

  return (
    <div className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-4 space-y-3 shadow-sm">
      <span className="text-xs font-bold uppercase tracking-wider text-indigo-800 block">
        Cited Sources for &ldquo;{observation.concept}&rdquo;
      </span>
      {cited.length === 0 && (
        <p className="text-xs text-slate-500">
          No matching evidence item found for source id(s): {observation.source_ids.join(", ") || "none"}
        </p>
      )}
      <ul className="space-y-3">
        {cited.map((item) => (
          <li key={item.source_id} className="rounded-lg border border-slate-200 bg-white p-3 space-y-2 shadow-sm">
            <span
              className={`inline-flex rounded border px-2 py-0.5 text-[10px] font-bold uppercase ${
                SOURCE_TYPE_STYLES[item.source_type] ?? "bg-slate-100 text-slate-700 border-slate-200"
              }`}
            >
              {item.source_type} · {item.source_id}
            </span>
            <div className="rounded bg-slate-900 p-2.5 font-mono text-xs text-cyan-300 break-all">
              {item.excerpt}
            </div>
            <p className="text-xs text-slate-700 font-medium">{item.explanation}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
