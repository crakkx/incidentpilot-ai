"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { SeverityBadge, StatusBadge } from "@/components/Badge";
import { api, IncidentRead } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

function IncidentsList() {
  const { role } = useAuth();
  const [incidents, setIncidents] = useState<IncidentRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "resolved" | "closed">("all");
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const fetchIncidents = () => {
    setLoading(true);
    api
      .listIncidents()
      .then(setIncidents)
      .catch(() => setError("Could not load incidents."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchIncidents();
  }, []);

  const handleStatusUpdate = async (e: React.MouseEvent, incidentId: string, newStatus: string) => {
    e.preventDefault();
    e.stopPropagation();
    setUpdatingId(incidentId);
    try {
      await api.updateIncidentStatus(incidentId, newStatus);
      fetchIncidents();
    } catch {
      setError("Failed to update status — check user role permissions.");
    } finally {
      setUpdatingId(null);
    }
  };

  const filteredIncidents = incidents.filter((inc) => {
    const matchesSearch =
      inc.title.toLowerCase().includes(search.toLowerCase()) ||
      (inc.service_name ?? "").toLowerCase().includes(search.toLowerCase());
    
    let matchesStatus = true;
    const s = inc.status.toLowerCase();
    if (statusFilter === "active") {
      matchesStatus = s !== "resolved" && s !== "closed";
    } else if (statusFilter === "resolved") {
      matchesStatus = s === "resolved";
    } else if (statusFilter === "closed") {
      matchesStatus = s === "closed";
    }

    return matchesSearch && matchesStatus;
  });

  const activeCount = incidents.filter(
    (i) => i.status.toLowerCase() !== "resolved" && i.status.toLowerCase() !== "closed"
  ).length;
  const resolvedCount = incidents.filter((i) => i.status.toLowerCase() === "resolved").length;
  const closedCount = incidents.filter((i) => i.status.toLowerCase() === "closed").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
            Incidents Overview
          </h1>
          <p className="text-xs text-slate-500 font-medium mt-0.5">
            Real-time infrastructure incident telemetry & agentic root-cause diagnostics
          </p>
        </div>
        {(role === "operator" || role === "admin") && (
          <Link
            href="/incidents/new"
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-xs font-bold text-white shadow hover:bg-slate-800 transition-all active:scale-[0.98]"
          >
            <span>+</span> Report Incident
          </Link>
        )}
      </div>

      {/* Metric Stat Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="glass-card p-4">
          <span className="text-[11px] font-bold uppercase tracking-wider text-blue-700">
            Active / Investigating
          </span>
          <div className="mt-1 text-2xl font-black text-blue-900">{activeCount}</div>
        </div>
        <div className="glass-card p-4">
          <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-700">
            Resolved
          </span>
          <div className="mt-1 text-2xl font-black text-emerald-900">{resolvedCount}</div>
        </div>
        <div className="glass-card p-4">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
            Closed
          </span>
          <div className="mt-1 text-2xl font-black text-slate-700">{closedCount}</div>
        </div>
      </div>

      {/* Filter Tabs & Search */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between glass-card p-3">
        <div className="flex items-center gap-1 border-b sm:border-b-0 pb-2 sm:pb-0 border-slate-200">
          <button
            onClick={() => setStatusFilter("all")}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              statusFilter === "all"
                ? "bg-slate-900 text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            All ({incidents.length})
          </button>
          <button
            onClick={() => setStatusFilter("active")}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              statusFilter === "active"
                ? "bg-blue-600 text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            Active ({activeCount})
          </button>
          <button
            onClick={() => setStatusFilter("resolved")}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              statusFilter === "resolved"
                ? "bg-emerald-600 text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            Resolved ({resolvedCount})
          </button>
          <button
            onClick={() => setStatusFilter("closed")}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              statusFilter === "closed"
                ? "bg-slate-600 text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            Closed ({closedCount})
          </button>
        </div>

        <input
          type="text"
          placeholder="Filter by title or service (e.g. checkout-api)…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-lg border border-slate-200 bg-white px-3.5 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:border-indigo-500 focus:outline-none sm:w-72"
        />
      </div>

      {/* Incident List */}
      {loading && (
        <div className="glass-card p-12 text-center text-slate-500">
          Loading incidents telemetry…
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs font-semibold text-red-700">
          {error}
        </div>
      )}

      {!loading && filteredIncidents.length === 0 && (
        <div className="glass-card p-12 text-center text-slate-500">
          No incidents matched your query.
        </div>
      )}

      <div className="space-y-3">
        {filteredIncidents.map((incident) => {
          const isClosedOrResolved =
            incident.status.toLowerCase() === "resolved" || incident.status.toLowerCase() === "closed";
          return (
            <div
              key={incident.id}
              className="glass-card-hover flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <Link
                href={`/incidents/${incident.id}/timeline`}
                className="flex-1 space-y-1"
              >
                <h2 className="font-bold text-base text-slate-900 hover:text-indigo-600 transition-colors">
                  {incident.title}
                </h2>
                <div className="flex items-center gap-3 text-xs text-slate-500 font-medium">
                  <span className="inline-flex items-center gap-1 font-semibold text-slate-700">
                    <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" />
                    {incident.service_name ?? "unknown service"}
                  </span>
                  <span>•</span>
                  <span>Started: {new Date(incident.started_at).toLocaleString()}</span>
                </div>
              </Link>

              <div className="flex items-center gap-3">
                <SeverityBadge severity={incident.severity} />
                <StatusBadge status={incident.status} />

                {/* Inline Close / Resolve Buttons for Operator/Admin */}
                {(role === "operator" || role === "admin") && !isClosedOrResolved && (
                  <div className="flex items-center gap-1.5 ml-2">
                    <button
                      onClick={(e) => handleStatusUpdate(e, incident.id, "resolved")}
                      disabled={updatingId === incident.id}
                      className="rounded border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-[11px] font-bold text-emerald-800 hover:bg-emerald-100 transition-all"
                    >
                      Resolve
                    </button>
                    <button
                      onClick={(e) => handleStatusUpdate(e, incident.id, "closed")}
                      disabled={updatingId === incident.id}
                      className="rounded border border-slate-300 bg-slate-100 px-2.5 py-1 text-[11px] font-bold text-slate-700 hover:bg-slate-200 transition-all"
                    >
                      Close
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function IncidentsPage() {
  return (
    <ProtectedRoute>
      <IncidentsList />
    </ProtectedRoute>
  );
}
