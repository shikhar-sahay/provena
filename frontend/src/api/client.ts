// Typed API client. All backend calls go through here, not scattered fetch calls.

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function getToken(): string | null {
  return localStorage.getItem("provena_token");
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> | undefined),
  };
  // Only send JSON content type when the body is not FormData (uploads).
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (response.status === 204) return undefined as T;
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    const detail =
      body !== null && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : `Request failed (${response.status}).`;
    // Session expiry: any authenticated 401 outside the login call itself
    // means the token is dead. Broadcast so AuthContext can sign out.
    if (response.status === 401 && !path.startsWith("/api/auth/login")) {
      window.dispatchEvent(new CustomEvent("provena:unauthorized"));
    }
    throw new ApiError(response.status, detail);
  }
  return body as T;
}

export type Role = "admin" | "investigator" | "forensic_analyst" | "evidence_custodian";
export type InvestigationStatus =
  | "open"
  | "in_progress"
  | "under_review"
  | "closed"
  | "archived";
export type Priority = "low" | "medium" | "high" | "critical";

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
}

export interface Member {
  user: User;
  team_role: "lead" | "member";
  created_at: string;
}

export interface Investigation {
  id: number;
  case_number: string;
  title: string;
  description: string;
  status: InvestigationStatus;
  priority: Priority;
  created_by: User;
  lead_investigator: User;
  members: Member[];
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export interface AuditEntry {
  id: number;
  action: string;
  resource_type: string;
  resource_id: string | null;
  actor_id: number | null;
  actor_username: string | null;
  event_metadata: Record<string, unknown> | null;
  created_at: string;
}

export type EvidenceType =
  | "log"
  | "document"
  | "image"
  | "network"
  | "email"
  | "device"
  | "archive"
  | "other";
export type IntegrityStatus = "not_verified" | "verified" | "mismatch" | "unavailable";
export type CustodyAction =
  | "registered"
  | "transferred"
  | "released_for_analysis"
  | "returned_to_custody"
  | "received"
  | "other";

export interface Evidence {
  id: number;
  investigation_id: number;
  evidence_number: string;
  title: string;
  description: string;
  evidence_type: EvidenceType;
  original_filename: string;
  content_type: string | null;
  source: string;
  acquired_at: string | null;
  registered_by: User;
  current_holder: User | null;
  file_size: number;
  sha256: string;
  integrity_status: IntegrityStatus;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Verification {
  id: number;
  evidence_id: number;
  performed_by: User | null;
  expected_sha256: string;
  observed_sha256: string | null;
  result: IntegrityStatus;
  reason: string | null;
  created_at: string;
}

export interface CustodyEvent {
  id: number;
  evidence_id: number;
  action: CustodyAction;
  from_user: User | null;
  to_user: User | null;
  performed_by: User | null;
  notes: string;
  created_at: string;
}

export interface TimelineEntry {
  occurred_at: string;
  kind: string;
  title: string;
  detail: string;
  actor_username: string | null;
  evidence_number: string | null;
}

export interface DashboardActivity {
  id: number;
  action: string;
  actor_username: string | null;
  investigation_id: number;
  investigation_title: string;
  evidence_number: string | null;
  created_at: string;
}

export interface DashboardSummary {
  investigations_total: number;
  by_status: Record<string, number>;
  evidence_total: number;
  integrity_issues: number;
  open_investigations: number[];
  recent_activity: DashboardActivity[];
}

export interface InvestigationCustodyRow {  id: number;
  evidence_id: number;
  evidence_number: string;
  evidence_title: string;
  action: string;
  from_user: string | null;
  to_user: string | null;
  performed_by: string | null;
  notes: string;
  created_at: string;
}

export const api = {
  login(usernameOrEmail: string, password: string) {
    return apiFetch<{ access_token: string; token_type: string; user: User }>(
      "/api/auth/login",
      {
        method: "POST",
        body: JSON.stringify({ username_or_email: usernameOrEmail, password }),
      },
    );
  },
  logout() {
    return apiFetch<{ detail: string }>("/api/auth/logout", { method: "POST" });
  },
  me() {
    return apiFetch<User>("/api/auth/me");
  },
  dashboardSummary() {
    return apiFetch<DashboardSummary>("/api/dashboard/summary");
  },
  listUsers() {
    return apiFetch<User[]>("/api/users");
  },
  listInvestigations(status?: InvestigationStatus) {
    const query = status ? `?status=${status}` : "";
    return apiFetch<Investigation[]>(`/api/investigations${query}`);
  },
  createInvestigation(payload: {
    title: string;
    description: string;
    priority: Priority;
    lead_investigator_id?: number;
  }) {
    return apiFetch<Investigation>("/api/investigations", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getInvestigation(id: number) {
    return apiFetch<Investigation>(`/api/investigations/${id}`);
  },
  updateInvestigation(
    id: number,
    payload: Partial<{
      title: string;
      description: string;
      priority: Priority;
      status: InvestigationStatus;
      lead_investigator_id: number;
    }>,
  ) {
    return apiFetch<Investigation>(`/api/investigations/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  addMember(id: number, userId: number) {
    return apiFetch<Investigation>(`/api/investigations/${id}/members`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    });
  },
  removeMember(id: number, userId: number) {
    return apiFetch<Investigation>(`/api/investigations/${id}/members/${userId}`, {
      method: "DELETE",
    });
  },
  investigationAudit(id: number) {
    return apiFetch<AuditEntry[]>(`/api/investigations/${id}/audit`);
  },
  listEvidence(
    invId: number,
    filters: { evidence_type?: EvidenceType; integrity_status?: IntegrityStatus; q?: string } = {},
  ) {
    const params = new URLSearchParams();
    if (filters.evidence_type) params.set("evidence_type", filters.evidence_type);
    if (filters.integrity_status) params.set("integrity_status", filters.integrity_status);
    if (filters.q) params.set("q", filters.q);
    const query = params.toString() ? `?${params.toString()}` : "";
    return apiFetch<Evidence[]>(`/api/investigations/${invId}/evidence${query}`);
  },
  registerEvidence(invId: number, form: FormData) {
    return apiFetch<Evidence>(`/api/investigations/${invId}/evidence`, {
      method: "POST",
      body: form,
    });
  },
  getEvidence(invId: number, evidenceId: number) {
    return apiFetch<Evidence>(`/api/investigations/${invId}/evidence/${evidenceId}`);
  },
  updateEvidence(
    invId: number,
    evidenceId: number,
    payload: Partial<{
      title: string;
      description: string;
      evidence_type: EvidenceType;
      source: string;
      acquired_at: string | null;
    }>,
  ) {
    return apiFetch<Evidence>(`/api/investigations/${invId}/evidence/${evidenceId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  verifyEvidence(invId: number, evidenceId: number) {
    return apiFetch<Verification>(
      `/api/investigations/${invId}/evidence/${evidenceId}/verify`,
      { method: "POST" },
    );
  },
  listVerifications(invId: number, evidenceId: number) {
    return apiFetch<Verification[]>(
      `/api/investigations/${invId}/evidence/${evidenceId}/verifications`,
    );
  },
  listCustody(invId: number, evidenceId: number) {
    return apiFetch<CustodyEvent[]>(
      `/api/investigations/${invId}/evidence/${evidenceId}/custody`,
    );
  },
  recordCustody(
    invId: number,
    evidenceId: number,
    payload: { action: CustodyAction; to_user_id?: number; notes?: string },
  ) {
    return apiFetch<CustodyEvent>(
      `/api/investigations/${invId}/evidence/${evidenceId}/custody`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  },
  evidenceTimeline(invId: number, evidenceId: number) {
    return apiFetch<TimelineEntry[]>(
      `/api/investigations/${invId}/evidence/${evidenceId}/timeline`,
    );
  },
  investigationTimeline(invId: number) {
    return apiFetch<TimelineEntry[]>(`/api/investigations/${invId}/timeline`);
  },
  investigationCustody(invId: number) {
    return apiFetch<InvestigationCustodyRow[]>(`/api/investigations/${invId}/custody`);
  },
  async downloadEvidence(invId: number, evidenceId: number, filename: string) {
    const API_BASE = import.meta.env.VITE_API_URL ?? "";
    const response = await fetch(
      `${API_BASE}/api/investigations/${invId}/evidence/${evidenceId}/download`,
      { headers: { Authorization: `Bearer ${localStorage.getItem("provena_token") ?? ""}` } },
    );
    if (!response.ok) throw new ApiError(response.status, "Download failed.");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },
};
