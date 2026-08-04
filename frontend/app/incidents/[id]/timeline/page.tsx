"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { EvidenceTimeline } from "@/components/EvidenceTimeline";
import { StatusBadge } from "@/components/Badge";
import { api, EvidencePayload } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function TimelinePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { role } = useAuth();
  const [evidence, setEvidence] = useState<EvidencePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);

  const fetchEvidence = () => {
    api
      .getEvidence(id)
      .then(setEvidence)
      .catch(() => setError("Could not load evidence for this incident."));
  };

  useEffect(() => {
    fetchEvidence();
  }, [id]);

  const handleResolve = async () => {
    setUpdating(true);
    try {
      await api.updateIncidentStatus(id, "resolved");
      fetchEvidence();
    } catch {
      setError("Failed to resolve incident.");
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
              {evidence?.incident.title ?? "Evidence Timeline"}
            </h1>
            {evidence && <StatusBadge status={evidence.incident.status} />}
          </div>
          <p className="text-xs text-slate-500 font-medium mt-1">
            Service: {evidence?.incident.service_name ?? "unknown"}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {(role === "operator" || role === "admin") && evidence && evidence.incident.status.toLowerCase() !== "resolved" && (
            <button
              onClick={handleResolve}
              disabled={updating}
              className="rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-800 hover:bg-emerald-100 transition-all"
            >
              {updating ? "Resolving…" : "✓ Resolve Incident"}
            </button>
          )}

          <button
            onClick={() => router.push(`/incidents/${id}/report`)}
            className="rounded-lg bg-slate-900 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-slate-800 shadow transition-all"
          >
            View RCA Report →
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs font-semibold text-red-700">
          {error}
        </div>
      )}

      {!evidence && !error && (
        <div className="glass-card p-12 text-center text-slate-500">
          Loading evidence payload…
        </div>
      )}

      {evidence && <EvidenceTimeline evidence={evidence} />}
    </div>
  );
}
