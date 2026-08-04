"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { ApiError, api } from "@/lib/api";

function IncidentIntakeForm() {
  const router = useRouter();
  const [serviceName, setServiceName] = useState("checkout-api");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState("medium");
  const [startTime, setStartTime] = useState(() => {
    const now = new Date();
    now.setSeconds(0, 0);
    return new Date(now.getTime() - now.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
  });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const incident = await api.createIncident({
        title: `${serviceName || "Incident"}: ${description.slice(0, 60) || "untitled"}`,
        description,
        severity,
        service_name: serviceName || undefined,
        started_at: startTime ? new Date(startTime).toISOString() : undefined,
      });
      await api.analyzeIncident(incident.id);
      router.push(`/incidents/${incident.id}/timeline`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError("Your role (viewer) cannot create incidents — sign in as operator or admin.");
      } else if (err instanceof ApiError && err.status === 429) {
        setError("Rate limit reached — please wait a moment and try again.");
      } else {
        setError("Could not create incident. Check the fields and try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
          Report an Incident
        </h1>
        <p className="text-xs text-slate-500 font-medium mt-1">
          Provide initial details to trigger evidence collection and LangGraph RCA analysis
        </p>
      </div>

      <form onSubmit={handleSubmit} className="glass-card p-6 space-y-5">
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
            Target Service Name
          </label>
          <input
            type="text"
            required
            value={serviceName}
            onChange={(e) => setServiceName(e.target.value)}
            placeholder="e.g. checkout-api"
            className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-all"
          />
        </div>

        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
            Incident Description / User Symptom
          </label>
          <textarea
            required
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What happened? What error codes or symptoms are users seeing?"
            className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-all"
          />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
              Severity Level
            </label>
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
              Incident Start Time
            </label>
            <input
              type="datetime-local"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none"
            />
          </div>
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs font-semibold text-red-700">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-slate-900 py-3 text-xs font-bold text-white shadow hover:bg-slate-800 disabled:opacity-50 transition-all active:scale-[0.99]"
        >
          {submitting ? "Initiating Agentic Analysis…" : "Trigger Incident Analysis →"}
        </button>
      </form>
    </div>
  );
}

export default function NewIncidentPage() {
  return (
    <ProtectedRoute allowedRoles={["operator", "admin"]}>
      <IncidentIntakeForm />
    </ProtectedRoute>
  );
}
