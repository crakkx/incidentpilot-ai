"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { StatusBadge } from "@/components/Badge";
import { JsonBlock, TraceSection } from "@/components/TraceSection";
import { AnalysisTraceResponse, RemediationProposal, api } from "@/lib/api";

export default function TracePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [trace, setTrace] = useState<AnalysisTraceResponse | null>(null);
  const [remediation, setRemediation] = useState<RemediationProposal | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getTrace(id)
      .then(setTrace)
      .catch(() => setError("No investigation trace available for this incident yet."));

    api
      .getRemediation(id)
      .then(setRemediation)
      .catch(() => setRemediation(null));
  }, [id]);

  if (error) return <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs font-semibold text-red-700">{error}</div>;
  if (!trace) return (
    <div className="glass-card p-12 text-center text-slate-500">
      Loading investigation trace…
    </div>
  );

  const retrieval = trace.retrieval_diagnostics as
    | {
        query?: string;
        filters?: Record<string, unknown>;
        returned_count?: number;
        latency_ms?: number;
        score_summary?: Record<string, unknown>;
        chunks?: Array<Record<string, unknown>>;
      }
    | null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">LangGraph Investigation Trace</h1>
            <StatusBadge status={trace.status} />
          </div>
          <p className="text-xs font-mono text-slate-500 mt-1">Run ID: {trace.analysis_run_id}</p>
        </div>

        <button
          onClick={() => router.push(`/incidents/${id}/report`)}
          className="rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-bold text-indigo-600 hover:bg-slate-50 shadow-sm transition-all"
        >
          ← Back to RCA Report
        </button>
      </div>

      {/* Metric Stat Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Node Calls" value={trace.node_calls} />
        <Stat label="Schema Retries" value={trace.repairs_used} />
        <Stat label="Investigation Rounds" value={trace.investigation_rounds} />
        <Stat label="Agent Tool Calls" value={trace.tool_results?.length ?? 0} />
      </div>

      <TraceSection title="Evidence Collection & Vector Retrieval" defaultOpen>
        {retrieval ? (
          <div className="space-y-3 text-xs text-slate-800">
            <p><span className="font-bold text-indigo-700">Dense Vector Query:</span> {retrieval.query}</p>
            <p><span className="font-bold text-indigo-700">Returned Chunks:</span> {retrieval.returned_count} chunks in <span className="text-emerald-700 font-bold">{retrieval.latency_ms}ms</span></p>
            {retrieval.score_summary && <JsonBlock value={retrieval.score_summary} />}
            {retrieval.chunks && retrieval.chunks.length > 0 && (
              <JsonBlock value={retrieval.chunks} />
            )}
          </div>
        ) : (
          <p className="text-xs text-slate-500">No retrieval diagnostics recorded.</p>
        )}
      </TraceSection>

      <TraceSection
        title="LLM Generation Calls"
        subtitle={`${trace.generation_attempts?.length ?? 0} call(s)`}
      >
        {trace.generation_attempts && trace.generation_attempts.length > 0 ? (
          <div className="space-y-4">
            {trace.generation_attempts.map((attempt, i) => (
              <div key={i} className="rounded-lg border border-slate-200 bg-white p-4 space-y-2">
                <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-700 block">
                  {(attempt.node as string) ?? `Call Node ${i + 1}`}
                </span>
                <JsonBlock value={attempt} />
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500">No generation attempts recorded.</p>
        )}
      </TraceSection>

      <TraceSection title="Adversarial Validation Pass">
        {trace.validation ? (
          <JsonBlock value={trace.validation} />
        ) : (
          <p className="text-xs text-slate-500">
            No adversarial validation pass ran for this report.
          </p>
        )}
      </TraceSection>

      <TraceSection
        title="Agent Dynamic Tool Execution"
        subtitle={`${trace.tool_results?.length ?? 0} tool call(s)`}
      >
        {trace.tool_results && trace.tool_results.length > 0 ? (
          <JsonBlock value={trace.tool_results} />
        ) : (
          <p className="text-xs text-slate-500">
            The agent contained sufficient evidence upfront — no additional tool calls were triggered.
          </p>
        )}
      </TraceSection>

      <TraceSection title="Auto-Repair Retry Audit">
        <p className="text-xs text-slate-700">
          Schema-repair retries used: <span className="font-bold text-indigo-700">{trace.repairs_used ?? 0}</span>
        </p>
        {trace.validation_errors ? (
          <JsonBlock value={trace.validation_errors} />
        ) : (
          <p className="mt-1 text-xs text-slate-500">No validation errors recorded.</p>
        )}
      </TraceSection>

      <TraceSection title="Human Approval Audit Status">
        {remediation ? (
          <div className="space-y-1 text-xs text-slate-800">
            <p>Proposal Status: <span className="font-bold text-indigo-700">{remediation.status}</span></p>
            <p>Confidence Level: <span className="font-bold text-slate-900">{remediation.confidence_level}</span></p>
            {remediation.rejection_reason && (
              <p className="text-red-700 font-semibold">Rejection Reason: {remediation.rejection_reason}</p>
            )}
          </div>
        ) : (
          <p className="text-xs text-slate-500">
            No remediation proposal required human approval for this run.
          </p>
        )}
      </TraceSection>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <div className="glass-card p-4 text-center">
      <div className="text-2xl font-black text-indigo-700">{value ?? "—"}</div>
      <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mt-1">{label}</div>
    </div>
  );
}
