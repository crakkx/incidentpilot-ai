"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { StatusBadge } from "@/components/Badge";
import { api } from "@/lib/api";

interface ApprovalItem {
  analysis_run_id: string;
  incident_id: string;
  incident_title: string;
  service_name: string | null;
  run_status: string;
  proposal: {
    recommended_actions?: string[];
    status?: string;
    confidence_level?: string;
    rejection_reason?: string;
  };
  created_at: string | null;
}

function ApprovalsDashboardContent() {
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"pending" | "approved" | "rejected">("pending");
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const fetchApprovals = () => {
    setLoading(true);
    api
      .listApprovals()
      .then(setItems)
      .catch(() => setError("Failed to load remediation proposals."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchApprovals();
  }, []);

  const handleApprove = async (incidentId: string) => {
    setActionBusy(incidentId);
    setActionMsg(null);
    try {
      await api.approveRemediation(incidentId);
      setActionMsg("Remediation proposal approved!");
      fetchApprovals();
    } catch {
      setError("Failed to approve remediation — check user role permissions.");
    } finally {
      setActionBusy(null);
    }
  };

  const handleReject = async (incidentId: string) => {
    setActionBusy(incidentId);
    setActionMsg(null);
    try {
      await api.rejectRemediation(incidentId, "Rejected from Human Approvals dashboard");
      setActionMsg("Remediation proposal rejected.");
      fetchApprovals();
    } catch {
      setError("Failed to reject remediation — check user role permissions.");
    } finally {
      setActionBusy(null);
    }
  };

  const pendingItems = items.filter(
    (i) => i.proposal.status === "awaiting_approval" || i.run_status === "awaiting_approval"
  );
  const approvedItems = items.filter((i) => i.proposal.status === "approved");
  const rejectedItems = items.filter((i) => i.proposal.status === "rejected");

  const displayItems =
    activeTab === "pending"
      ? pendingItems
      : activeTab === "approved"
      ? approvedItems
      : rejectedItems;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
          Human Remediation Approvals
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Review, approve, or reject low-confidence remediation proposals before action execution
        </p>
      </div>

      {actionMsg && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3.5 text-xs font-semibold text-emerald-800">
          {actionMsg}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3.5 text-xs font-semibold text-red-800">
          {error}
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex border-b border-slate-200 gap-2">
        <button
          onClick={() => setActiveTab("pending")}
          className={`pb-3 px-4 font-bold text-xs uppercase tracking-wider border-b-2 transition-all ${
            activeTab === "pending"
              ? "border-amber-500 text-amber-800"
              : "border-transparent text-slate-500 hover:text-slate-900"
          }`}
        >
          ⚠️ Pending Approvals ({pendingItems.length})
        </button>
        <button
          onClick={() => setActiveTab("approved")}
          className={`pb-3 px-4 font-bold text-xs uppercase tracking-wider border-b-2 transition-all ${
            activeTab === "approved"
              ? "border-emerald-600 text-emerald-800"
              : "border-transparent text-slate-500 hover:text-slate-900"
          }`}
        >
          ✅ Approved ({approvedItems.length})
        </button>
        <button
          onClick={() => setActiveTab("rejected")}
          className={`pb-3 px-4 font-bold text-xs uppercase tracking-wider border-b-2 transition-all ${
            activeTab === "rejected"
              ? "border-red-600 text-red-800"
              : "border-transparent text-slate-500 hover:text-slate-900"
          }`}
        >
          ❌ Rejected ({rejectedItems.length})
        </button>
      </div>

      {/* Content Cards */}
      {loading && (
        <div className="glass-card p-12 text-center text-slate-500">
          Loading remediation proposals…
        </div>
      )}

      {!loading && displayItems.length === 0 && (
        <div className="glass-card p-12 text-center text-slate-500">
          No proposals found in {activeTab} status.
        </div>
      )}

      <div className="space-y-4">
        {displayItems.map((item) => {
          const isPending =
            item.proposal.status === "awaiting_approval" || item.run_status === "awaiting_approval";
          return (
            <div key={item.analysis_run_id} className="glass-card p-6 space-y-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-100 pb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <Link
                      href={`/incidents/${item.incident_id}/report`}
                      className="font-bold text-base text-slate-900 hover:text-indigo-600 transition-colors"
                    >
                      {item.incident_title}
                    </Link>
                    <StatusBadge status={item.proposal.status || item.run_status} />
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Service: {item.service_name || "unknown"} · Created:{" "}
                    {item.created_at ? new Date(item.created_at).toLocaleString() : "N/A"}
                  </p>
                </div>

                <Link
                  href={`/incidents/${item.incident_id}/report`}
                  className="text-xs font-semibold text-indigo-600 hover:text-indigo-800"
                >
                  View Full RCA Report →
                </Link>
              </div>

              {/* Recommended Actions */}
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500 block mb-2">
                  Proposed Remediation Actions:
                </span>
                <ul className="space-y-1.5 text-xs text-slate-800">
                  {item.proposal.recommended_actions?.map((act, idx) => (
                    <li key={idx} className="flex items-start gap-2 rounded-md bg-slate-50 p-2.5 border border-slate-200/80">
                      <span className="font-bold text-indigo-600">{idx + 1}.</span>
                      <span>{act}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {item.proposal.rejection_reason && (
                <div className="rounded-md bg-red-50 p-3 text-xs text-red-700 font-semibold border border-red-200">
                  Rejection Reason: {item.proposal.rejection_reason}
                </div>
              )}

              {/* Inline Action Buttons */}
              {isPending && (
                <div className="flex gap-3 pt-2">
                  <button
                    onClick={() => handleApprove(item.incident_id)}
                    disabled={actionBusy === item.incident_id}
                    className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow hover:bg-emerald-700 disabled:opacity-50 transition-all"
                  >
                    {actionBusy === item.incident_id ? "Approving…" : "Approve Remediation"}
                  </button>
                  <button
                    onClick={() => handleReject(item.incident_id)}
                    disabled={actionBusy === item.incident_id}
                    className="rounded-lg bg-red-600 px-4 py-2 text-xs font-bold text-white shadow hover:bg-red-700 disabled:opacity-50 transition-all"
                  >
                    {actionBusy === item.incident_id ? "Rejecting…" : "Reject Remediation"}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function ApprovalsPage() {
  return (
    <ProtectedRoute allowedRoles={["operator", "admin"]}>
      <ApprovalsDashboardContent />
    </ProtectedRoute>
  );
}
