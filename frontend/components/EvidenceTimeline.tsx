"use client";

import { useMemo, useState } from "react";
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { EvidencePayload } from "@/lib/api";

const LEVEL_COLORS: Record<string, string> = {
  ERROR: "bg-red-500",
  WARN: "bg-amber-500",
  WARNING: "bg-amber-500",
  INFO: "bg-blue-500",
  DEBUG: "bg-slate-400",
};

function toMs(ts: string | null): number | null {
  if (!ts) return null;
  const ms = new Date(ts).getTime();
  return Number.isNaN(ms) ? null : ms;
}

export function EvidenceTimeline({ evidence }: { evidence: EvidencePayload }) {
  const [selected, setSelected] = useState<{ kind: string; detail: string } | null>(null);

  const incidentMs = toMs(evidence.incident.started_at);

  const allMs = useMemo(() => {
    const values: number[] = [];
    if (incidentMs) values.push(incidentMs);
    evidence.logs.forEach((l) => {
      const ms = toMs(l.timestamp);
      if (ms) values.push(ms);
    });
    evidence.deployments.forEach((d) => {
      const ms = toMs(d.deployed_at);
      if (ms) values.push(ms);
    });
    evidence.metrics.forEach((m) => {
      const ms = toMs(m.timestamp);
      if (ms) values.push(ms);
    });
    return values;
  }, [evidence, incidentMs]);

  if (allMs.length === 0) {
    return (
      <div className="glass-card p-8 text-center text-slate-500">
        No timestamped evidence collected for this incident yet.
      </div>
    );
  }

  const minMs = Math.min(...allMs);
  const maxMs = Math.max(...allMs);
  const span = Math.max(maxMs - minMs, 1);

  function pct(ms: number | null): number | null {
    if (ms === null) return null;
    return ((ms - minMs) / span) * 100;
  }

  const metricSeries = evidence.metrics
    .map((m) => ({ ms: toMs(m.timestamp), value: m.value, name: m.metric_name }))
    .filter((m): m is { ms: number; value: number; name: string } => m.ms !== null)
    .sort((a, b) => a.ms - b.ms);

  return (
    <div className="space-y-6">
      {/* Event Pins Timeline */}
      <div className="glass-card p-6 space-y-6">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-purple-700">
            Deployments
          </span>
          <div className="relative mt-2 h-8 rounded-lg bg-slate-100 border border-slate-200 p-1">
            {incidentMs !== null && (
              <div
                className="absolute top-0 h-full w-0.5 bg-red-500 z-10"
                style={{ left: `${pct(incidentMs)}%` }}
              />
            )}
            {evidence.deployments.map((d) => {
              const p = pct(toMs(d.deployed_at));
              if (p === null) return null;
              return (
                <button
                  key={d.id}
                  onClick={() =>
                    setSelected({
                      kind: "Deployment",
                      detail: `${d.version ?? "unknown version"} → ${d.environment ?? "?"} (${d.commit_sha ?? "no sha"}) at ${d.deployed_at}`,
                    })
                  }
                  className="absolute top-1.5 h-3.5 w-3.5 -translate-x-1/2 rounded-full bg-purple-600 shadow hover:scale-125 transition-transform"
                  style={{ left: `${p}%` }}
                  title={d.version ?? undefined}
                />
              );
            })}
          </div>
        </div>

        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-blue-700">
            Logs & Anomalies
          </span>
          <div className="relative mt-2 h-8 rounded-lg bg-slate-100 border border-slate-200 p-1">
            {incidentMs !== null && (
              <div
                className="absolute top-0 h-full w-0.5 bg-red-500 z-10"
                style={{ left: `${pct(incidentMs)}%` }}
              />
            )}
            {evidence.logs.map((l) => {
              const p = pct(toMs(l.timestamp));
              if (p === null) return null;
              return (
                <button
                  key={l.id}
                  onClick={() =>
                    setSelected({
                      kind: `Log (${l.level})`,
                      detail: `${l.timestamp ?? ""} — ${l.message}`,
                    })
                  }
                  className={`absolute top-2 h-3 w-3 -translate-x-1/2 rounded-full ${
                    LEVEL_COLORS[l.level] ?? "bg-slate-400"
                  } hover:scale-125 transition-transform`}
                  style={{ left: `${p}%` }}
                  title={l.message}
                />
              );
            })}
          </div>
        </div>

        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-red-700">
            Incident Start Marker
          </span>
          <div className="relative mt-2 h-6">
            {incidentMs !== null && (
              <div
                className="absolute top-0 h-full w-0.5 bg-red-500"
                style={{ left: `${pct(incidentMs)}%` }}
              >
                <span className="absolute -top-1 left-2 whitespace-nowrap rounded border border-red-200 bg-red-50 px-2 py-0.5 font-mono text-[11px] font-bold text-red-700">
                  {evidence.incident.started_at}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Metrics Chart */}
      {metricSeries.length > 0 && (
        <div className="glass-card p-6">
          <span className="text-xs font-bold uppercase tracking-wider text-indigo-700 block mb-4">
            Service Metrics Telemetry
          </span>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metricSeries}>
                <XAxis
                  dataKey="ms"
                  type="number"
                  domain={[minMs, maxMs]}
                  tickFormatter={(ms) => new Date(ms).toLocaleTimeString()}
                  stroke="#64748b"
                  fontSize={11}
                />
                <YAxis stroke="#64748b" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#ffffff",
                    borderColor: "#e2e8f0",
                    borderRadius: "8px",
                    color: "#0f172a",
                    fontSize: "12px",
                    boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
                  }}
                  labelFormatter={(ms) => new Date(ms as number).toLocaleString()}
                  formatter={(value: number, _name, item) => [value, item.payload.name]}
                />
                {incidentMs !== null && (
                  <ReferenceLine x={incidentMs} stroke="#ef4444" strokeDasharray="4 4" />
                )}
                <Line type="monotone" dataKey="value" stroke="#4f46e5" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Selected Inspector Box */}
      {selected && (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-indigo-800">
            {selected.kind}
          </span>
          <p className="mt-1 font-mono text-xs text-indigo-950">{selected.detail}</p>
        </div>
      )}
    </div>
  );
}
