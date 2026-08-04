"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { ProtectedRoute } from "@/components/ProtectedRoute";

function IngestPageContent() {
  const [activeTab, setActiveTab] = useState<"document" | "logs" | "metrics">("document");

  // Document state
  const [file, setFile] = useState<File | null>(null);
  const [docService, setDocService] = useState("checkout-api");
  const [docType, setDocType] = useState("runbook");
  const [severity, setSeverity] = useState("high");
  const [docStatus, setDocStatus] = useState<string | null>(null);
  const [docLoading, setDocLoading] = useState(false);

  // Log state
  const [logService, setLogService] = useState("checkout-api");
  const [incidentId, setIncidentId] = useState("");
  const [rawLogs, setRawLogs] = useState(
    JSON.stringify(
      [
        {
          timestamp: new Date().toISOString(),
          level: "ERROR",
          message: "Database pool exhausted; connection timeout.",
          source: "app",
          context: { status_code: 500 },
        },
      ],
      null,
      2
    )
  );
  const [logStatus, setLogStatus] = useState<string | null>(null);
  const [logLoading, setLogLoading] = useState(false);

  // Metrics state
  const [metricService, setMetricService] = useState("checkout-api");
  const [rawMetrics, setRawMetrics] = useState(
    JSON.stringify(
      [
        {
          metric_name: "db_connection_pool_active",
          value: 98.5,
          unit: "%",
          timestamp: new Date().toISOString(),
        },
        {
          metric_name: "http_requests_latency_ms",
          value: 4500.0,
          unit: "ms",
          timestamp: new Date().toISOString(),
        },
      ],
      null,
      2
    )
  );
  const [metricStatus, setMetricStatus] = useState<string | null>(null);
  const [metricLoading, setMetricLoading] = useState(false);

  const handleDocumentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setDocLoading(true);
    setDocStatus(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      if (docService) formData.append("service_name", docService);
      formData.append("document_type", docType);
      if (severity) formData.append("severity", severity);

      const res = await api.uploadDocument(formData);
      setDocStatus(`Successfully uploaded runbook! Created ${res.chunk_count} vector chunks.`);
      setFile(null);
    } catch (err: any) {
      setDocStatus(`Upload failed: ${err.message || err}`);
    } finally {
      setDocLoading(false);
    }
  };

  const handleLogSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLogLoading(true);
    setLogStatus(null);

    try {
      const parsedLogs = JSON.parse(rawLogs);
      const logArray = Array.isArray(parsedLogs) ? parsedLogs : [parsedLogs];

      const res = await api.ingestLogs({
        service_name: logService,
        incident_id: incidentId ? incidentId : undefined,
        logs: logArray,
      });

      setLogStatus(`Successfully ingested ${res.ingested_count} log entries!`);
    } catch (err: any) {
      setLogStatus(`Ingestion failed: ${err.message || err}`);
    } finally {
      setLogLoading(false);
    }
  };

  const handleMetricSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMetricLoading(true);
    setMetricStatus(null);

    try {
      const parsedMetrics = JSON.parse(rawMetrics);
      const metricsArray = Array.isArray(parsedMetrics) ? parsedMetrics : [parsedMetrics];

      const res = await api.ingestMetrics({
        service_name: metricService,
        metrics: metricsArray,
      });

      setMetricStatus(`Successfully ingested ${res.ingested_count} metric data points!`);
    } catch (err: any) {
      setMetricStatus(`Ingestion failed: ${err.message || err}`);
    } finally {
      setMetricLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">Data Ingestion Center</h1>
        <p className="text-xs text-slate-500 font-medium mt-1">
          Upload operational runbooks to `pgvector`, or ingest log and metric telemetry
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 gap-2">
        <button
          onClick={() => setActiveTab("document")}
          className={`pb-3 px-4 font-bold text-xs uppercase tracking-wider border-b-2 transition-all ${
            activeTab === "document"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-900"
          }`}
        >
          📄 Runbook Upload
        </button>
        <button
          onClick={() => setActiveTab("logs")}
          className={`pb-3 px-4 font-bold text-xs uppercase tracking-wider border-b-2 transition-all ${
            activeTab === "logs"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-900"
          }`}
        >
          📜 Log Telemetry
        </button>
        <button
          onClick={() => setActiveTab("metrics")}
          className={`pb-3 px-4 font-bold text-xs uppercase tracking-wider border-b-2 transition-all ${
            activeTab === "metrics"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-900"
          }`}
        >
          📊 Metric Telemetry
        </button>
      </div>

      {/* Tab 1: Document Upload */}
      {activeTab === "document" && (
        <form onSubmit={handleDocumentSubmit} className="glass-card p-6 space-y-5">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
              Runbook Document File (.md / .txt)
            </label>
            <div className="mt-2 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 p-6 text-center hover:border-indigo-400 transition-all">
              <input
                type="file"
                accept=".md,.txt,.pdf"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="hidden"
                id="runbook-file"
              />
              <label htmlFor="runbook-file" className="cursor-pointer space-y-2">
                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-indigo-50 text-indigo-600">
                  📁
                </div>
                <span className="block text-xs font-semibold text-indigo-600">
                  {file ? file.name : "Click to select a runbook file"}
                </span>
                <span className="block text-[11px] text-slate-400">Supports Markdown or Plain Text</span>
              </label>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
                Service Name
              </label>
              <input
                type="text"
                value={docService}
                onChange={(e) => setDocService(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
                Document Type
              </label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none"
              >
                <option value="runbook">Runbook</option>
                <option value="architecture">Architecture Doc</option>
                <option value="postmortem">Postmortem</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
                Target Severity
              </label>
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none"
              >
                <option value="high">High</option>
                <option value="critical">Critical</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>

          {docStatus && (
            <div className={`rounded-lg border p-3 text-xs font-semibold ${
              docStatus.includes("failed")
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-emerald-200 bg-emerald-50 text-emerald-800"
            }`}>
              {docStatus}
            </div>
          )}

          <button
            type="submit"
            disabled={!file || docLoading}
            className="w-full rounded-lg bg-slate-900 py-3 text-xs font-bold text-white shadow hover:bg-slate-800 disabled:opacity-50 transition-all active:scale-[0.99]"
          >
            {docLoading ? "Chunking & Vectorizing…" : "Embed & Ingest Runbook →"}
          </button>
        </form>
      )}

      {/* Tab 2: Logs Ingestion */}
      {activeTab === "logs" && (
        <form onSubmit={handleLogSubmit} className="glass-card p-6 space-y-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
                Service Name
              </label>
              <input
                type="text"
                required
                value={logService}
                onChange={(e) => setLogService(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
                Associate Incident ID (Optional)
              </label>
              <input
                type="text"
                value={incidentId}
                onChange={(e) => setIncidentId(e.target.value)}
                placeholder="UUID"
                className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-mono text-slate-900 focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">
              Raw JSON Log Array Payload
            </label>
            <textarea
              required
              rows={8}
              value={rawLogs}
              onChange={(e) => setRawLogs(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-900 p-4 font-mono text-xs text-emerald-400 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          {logStatus && (
            <div className={`rounded-lg border p-3 text-xs font-semibold ${
              logStatus.includes("failed")
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-emerald-200 bg-emerald-50 text-emerald-800"
            }`}>
              {logStatus}
            </div>
          )}

          <button
            type="submit"
            disabled={logLoading}
            className="w-full rounded-lg bg-slate-900 py-3 text-xs font-bold text-white shadow hover:bg-slate-800 disabled:opacity-50 transition-all active:scale-[0.99]"
          >
            {logLoading ? "Ingesting Logs…" : "Ingest Log Telemetry →"}
          </button>
        </form>
      )}

      {/* Tab 3: Metrics Ingestion */}
      {activeTab === "metrics" && (
        <form onSubmit={handleMetricSubmit} className="glass-card p-6 space-y-5">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
              Service Name
            </label>
            <input
              type="text"
              required
              value={metricService}
              onChange={(e) => setMetricService(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">
              Raw JSON Metric Points Array
            </label>
            <textarea
              required
              rows={8}
              value={rawMetrics}
              onChange={(e) => setRawMetrics(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-900 p-4 font-mono text-xs text-cyan-400 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          {metricStatus && (
            <div className={`rounded-lg border p-3 text-xs font-semibold ${
              metricStatus.includes("failed")
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-emerald-200 bg-emerald-50 text-emerald-800"
            }`}>
              {metricStatus}
            </div>
          )}

          <button
            type="submit"
            disabled={metricLoading}
            className="w-full rounded-lg bg-slate-900 py-3 text-xs font-bold text-white shadow hover:bg-slate-800 disabled:opacity-50 transition-all active:scale-[0.99]"
          >
            {metricLoading ? "Ingesting Metrics…" : "Ingest Metric Telemetry →"}
          </button>
        </form>
      )}
    </div>
  );
}

export default function IngestPage() {
  return (
    <ProtectedRoute allowedRoles={["operator", "admin"]}>
      <IngestPageContent />
    </ProtectedRoute>
  );
}
