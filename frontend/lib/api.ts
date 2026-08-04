const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("incidentpilot_token");
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem("incidentpilot_token", token);
  else window.localStorage.removeItem("incidentpilot_token");
}

export function getRole(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("incidentpilot_role");
}

export function setRole(role: string | null) {
  if (typeof window === "undefined") return;
  if (role) window.localStorage.setItem("incidentpilot_role", role);
  else window.localStorage.removeItem("incidentpilot_role");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, (detail as any)?.detail ?? detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; role: string; token_type: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  createIncident: (payload: {
    title: string;
    description?: string;
    severity: string;
    service_name?: string;
    started_at?: string;
  }) =>
    request<IncidentRead>("/incidents", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listIncidents: () => request<IncidentRead[]>("/incidents"),

  getIncident: (id: string) =>
    request<IncidentRead[]>("/incidents").then(
      (all) => all.find((i) => i.id === id) as IncidentRead | undefined
    ),

  analyzeIncident: (incidentId: string) =>
    request<IncidentAnalysisResponse>(`/incidents/${incidentId}/analyze`, {
      method: "POST",
    }),

  getLatestAnalysis: (incidentId: string) =>
    request<IncidentAnalysisResponse>(`/incidents/${incidentId}/analyze`),

  getAnalysisStatus: (incidentId: string, runId: string) =>
    request<IncidentAnalysisResponse>(`/incidents/${incidentId}/analyze/${runId}`),

  getTrace: (incidentId: string) =>
    request<AnalysisTraceResponse>(`/incidents/${incidentId}/trace`),

  getEvidence: (incidentId: string) =>
    request<EvidencePayload>(`/incidents/${incidentId}/evidence`),

  getRemediation: (incidentId: string) =>
    request<RemediationProposal>(`/incidents/${incidentId}/remediation`),

  approveRemediation: (incidentId: string) =>
    request(`/incidents/${incidentId}/remediation/approve`, { method: "POST" }),

  rejectRemediation: (incidentId: string, reason?: string) =>
    request(`/incidents/${incidentId}/remediation/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  uploadDocument: (formData: FormData) =>
    request<{ id: string; title: string; chunk_count: number }>("/documents/upload", {
      method: "POST",
      body: formData,
    }),

  ingestLogs: (payload: { service_name: string; incident_id?: string; logs: Array<{ timestamp?: string; level?: string; message: string; source?: string; context?: Record<string, unknown> }> }) =>
    request<{ ingested_count: number; service_id: string; service_name: string }>("/logs/ingest", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listUsers: () => request<UserRead[]>("/users"),

  createUser: (payload: { email: string; password: string; role: string }) =>
    request<UserRead>("/users", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateUserRole: (userId: string, role: string) =>
    request<UserRead>(`/users/${userId}/role`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),

  updateUserStatus: (userId: string, is_active: boolean) =>
    request<UserRead>(`/users/${userId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ is_active }),
    }),

  deleteUser: (userId: string) =>
    request<void>(`/users/${userId}`, {
      method: "DELETE",
    }),

  issueApiKey: (payload: { email: string; role: string }) =>
    request<{ email: string; role: string; api_key: string }>("/auth/api-keys", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateIncidentStatus: (incidentId: string, status: string) =>
    request<IncidentRead>(`/incidents/${incidentId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  ingestMetrics: (payload: {
    service_name: string;
    metrics: Array<{ metric_name: string; value: number; unit?: string; timestamp?: string }>;
  }) =>
    request<{ message: string; ingested_count: number }>("/metrics", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listApprovals: (status_filter?: string) =>
    request<
      Array<{
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
      }>
    >(`/incidents/approvals/list${status_filter ? `?status_filter=${status_filter}` : ""}`),
};

// ── types (mirrors backend Pydantic schemas) ────────────────────────────────

export interface UserRead {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  has_api_key: boolean;
  created_at: string;
}

export interface IncidentRead {
  id: string;
  title: string;
  severity: string;
  status: string;
  description: string | null;
  service_id: string | null;
  service_name: string | null;
  started_at: string;
  created_at: string;
  updated_at: string;
}

export interface EvidenceItem {
  excerpt: string;
  explanation: string;
  source_type: "log" | "metric" | "deployment" | "runbook";
  source_id: string;
}

export interface ObservationItem {
  id: string;
  concept: string;
  source_ids: string[];
}

export interface RootCauseAssessment {
  immediate_mechanism: string;
  suspected_trigger: string | null;
  causal_strength: "confirmed" | "supported" | "correlated" | "unknown" | "refuted";
}

export interface RCAReport {
  evidence: EvidenceItem[];
  observations: ObservationItem[];
  log_anomalies: string[];
  metric_anomalies: string[];
  contradictions_detected: string | null;
  incident_summary: string;
  likely_root_cause: string;
  root_cause: RootCauseAssessment | null;
  recommended_actions: string[];
  confidence: "low" | "medium" | "high";
  missing_information: string[];
}

export interface IncidentAnalysisResponse {
  analysis_run_id: string;
  incident_id: string;
  status: string;
  model_name?: string;
  pipeline_version?: string;
  schema_version?: string;
  prompt_version?: string;
  progress_stage: string | null;
  progress_message: string | null;
  progress_percent: number;
  failure_type: string | null;
  error_message: string | null;
  report: RCAReport | null;
}

export interface AnalysisTraceResponse {
  analysis_run_id: string;
  incident_id: string;
  status: string;
  progress_stage: string | null;
  progress_message: string | null;
  progress_percent: number;
  node_calls: number | null;
  repairs_used: number | null;
  investigation_rounds: number | null;
  tool_results: Array<Record<string, unknown>> | null;
  validation: Record<string, unknown> | null;
  generation_metadata: Record<string, unknown> | null;
  generation_attempts: Array<Record<string, unknown>> | null;
  validation_errors: unknown;
  retrieval_diagnostics: unknown;
}

export interface EvidencePayload {
  incident: {
    id: string;
    title: string;
    description: string | null;
    severity: string;
    status: string;
    service_name: string | null;
    started_at: string | null;
  };
  logs: Array<{ id: string; timestamp: string | null; level: string; message: string; source: string | null }>;
  deployments: Array<{
    id: string;
    version: string | null;
    environment: string | null;
    commit_sha: string | null;
    deployed_at: string | null;
  }>;
  metrics: Array<{
    id: string;
    timestamp: string | null;
    metric_name: string;
    value: number;
    unit: string | null;
  }>;
}

export interface RemediationProposal {
  incident_id: string;
  root_cause_summary: string;
  actions: Array<{
    action: string;
    priority: string;
    target_entity: string;
    rationale: string;
  }>;
  confidence_level: string;
  status: string;
  proposed_at: string;
  rejection_reason?: string;
}
