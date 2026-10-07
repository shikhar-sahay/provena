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
  active_workspace_id: number | null;
}

export interface Workspace {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  role: Role;
  member_count: number;
  created_at: string;
}

export interface WorkspaceMember {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  joined_at: string;
}

export interface WorkspaceInvite {
  id: number;
  code: string | null;
  code_hint: string;
  role: Role;
  expires_at: string | null;
  revoked_at: string | null;
  use_count: number;
  max_uses: number;
  created_at: string;
}

export interface AiProviderHealth {
  enabled: boolean;
  provider: string;
  model: string | null;
  available: boolean;
  detail: string;
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

export interface DashboardLastAnalysis {
  run_id: number;
  run_label: string;
  investigation_id: number;
  investigation_title: string;
  status: string;
  completed_at: string | null;
  artifact_count: number;
  correlation_count: number;
}

export interface DashboardSummary {
  investigations_total: number;
  by_status: Record<string, number>;
  evidence_total: number;
  integrity_issues: number;
  open_investigations: number[];
  recent_activity: DashboardActivity[];
  pending_analysis: number;
  findings_pending_review: number;
  last_analysis: DashboardLastAnalysis | null;
}

export type RunStatus = "pending" | "running" | "completed" | "failed";
export type RunEvidenceStatus =
  | "processed"
  | "blocked_not_verified"
  | "blocked_mismatch"
  | "blocked_unavailable"
  | "unsupported"
  | "failed";

export interface RunEvidenceOutcome {
  id: number;
  evidence_id: number;
  evidence_number: string | null;
  status: RunEvidenceStatus;
  error: string | null;
  artifact_count: number;
}

export interface AnalysisRun {
  id: number;
  investigation_id: number;
  run_number: number;
  run_label: string | null;
  initiated_by_username: string | null;
  status: RunStatus;
  pipeline_version: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  evidence_count: number;
  artifact_count: number;
  correlation_count: number;
  created_at: string;
  evidence_outcomes: RunEvidenceOutcome[];
}

export interface EligibilityEntry {
  evidence_id: number;
  evidence_number: string;
  title: string;
  integrity_status: string;
  supported: boolean;
  eligible: boolean;
  reason: string | null;
}

export type ArtifactType =
  | "IP_ADDRESS"
  | "EMAIL_ADDRESS"
  | "USERNAME"
  | "HOSTNAME"
  | "DOMAIN"
  | "FILE_PATH"
  | "FILE_NAME"
  | "HASH"
  | "USB_DEVICE"
  | "TIMESTAMP"
  | "URL"
  | "PORT"
  | "MAC_ADDRESS"
  | "PROCESS_NAME";

export interface Artifact {
  id: number;
  investigation_id: number;
  evidence_id: number;
  evidence_number: string | null;
  evidence_title: string | null;
  artifact_type: ArtifactType;
  raw_value: string;
  normalized_value: string;
  locator: Record<string, unknown>;
  source_key: string;
  context: string;
  method: string;
  extractor_name: string;
  extractor_version: string;
  created_at: string;
}

export interface ArtifactList {
  total: number;
  limit: number;
  offset: number;
  items: Artifact[];
}

export interface CorrelationEvidenceItem {
  evidence_id: number;
  evidence_number: string;
  evidence_title: string;
  artifact_count: number;
}

export interface Correlation {
  id: number;
  investigation_id: number;
  correlation_type: string;
  artifact_type: ArtifactType;
  normalized_value: string;
  evidence_count: number;
  artifact_count: number;
  created_at: string;
  evidence_items: CorrelationEvidenceItem[];
}

export interface CorrelationArtifact {
  id: number;
  evidence_id: number;
  evidence_number: string;
  artifact_type: ArtifactType;
  raw_value: string;
  normalized_value: string;
  locator: Record<string, unknown>;
  source_key: string;
  context: string;
  method: string;
  extractor_name: string;
  extractor_version: string;
}

export interface CorrelationDetail extends Correlation {
  artifacts: CorrelationArtifact[];
}

export type FindingStatus = "pending_review" | "accepted" | "rejected";

export interface Finding {
  id: number;
  investigation_id: number;
  rule_id: string;
  rule_version: string;
  title: string;
  summary: string;
  severity: string;
  confidence: number;
  factors: { factor: string; weight: number; detail: string }[];
  evidence_ids: number[];
  artifact_ids: number[];
  correlation_ids: number[];
  recommendations: string[];
  status: FindingStatus;
  reviewer_username: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  investigation_title?: string | null;
  investigation_case_number?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SearchResultItem {
  category: "investigation" | "evidence" | "finding" | "artifact";
  id: number;
  title: string;
  subtitle: string;
  url: string;
  investigation_id: number;
  investigation_title: string;
}

export interface SearchResponse {
  query: string;
  total: number;
  results: SearchResultItem[];
}

export interface BulkFindingReviewPayload {
  finding_ids: number[];
  status: "accepted" | "rejected";
  note?: string;
}

export interface BulkReviewResult {
  updated: Finding[];
  count: number;
}

export interface Note {
  id: number;
  investigation_id: number;
  finding_id: number | null;
  author_username: string | null;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface Report {
  id: number;
  investigation_id: number;
  report_number: number;
  report_label: string | null;
  generated_by_username: string | null;
  content: ReportContent;
  content_sha256: string;
  created_at: string;
}

export interface ReportContent {
  investigation: {
    case_number: string;
    title: string;
    description: string;
    status: string;
    priority: string;
    created_by: string | null;
    lead_investigator: string | null;
    team: { username: string; full_name: string; role: string; team_role: string }[];
    created_at: string | null;
  };
  evidence_summary: {
    evidence_number: string;
    title: string;
    evidence_type: string;
    original_filename: string;
    file_size: number;
    sha256: string;
    integrity_status: string;
    last_verified_at: string | null;
    registered_by: string | null;
    current_holder: string | null;
    created_at: string | null;
  }[];
  custody_summary: {
    id: number;
    evidence_id: number;
    evidence_number: string;
    evidence_title: string;
    action: string;
    from_user: string | null;
    to_user: string | null;
    performed_by: string | null;
    notes: string;
    created_at: string;
  }[];
  timeline: TimelineEntry[];
  accepted_findings: {
    id: number;
    rule_id: string;
    rule_version: string;
    title: string;
    summary: string;
    severity: string;
    confidence: number;
    factors: { factor: string; weight: number; detail: string }[];
    evidence_ids: number[];
    artifact_ids: number[];
    correlation_ids: number[];
    recommendations: string[];
    reviewer: string | null;
    reviewed_at: string | null;
    review_note: string | null;
  }[];
  recommendations: string[];
  investigator_notes: {
    author: string | null;
    finding_id: number | null;
    body: string;
    created_at: string | null;
  }[];
  generated_by: string;
  generated_at: string;
  generator: string;
  narrative?: {
    executive_summary: string;
    investigation_narrative: string;
    finding_narratives: Record<string, string>;
    conclusion: string;
    used_finding_ids: number[];
  };
  generation_metadata?: {
    mode: "ai_enhanced" | "deterministic_fallback";
    provider: string | null;
    model: string | null;
    generated_at: string;
    context_sha256: string;
    template_version: string;
    fallback: boolean;
    error: string | null;
  };
}

export interface AdminUser {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  investigations: { id: number; case_number: string; title: string }[];
}

export interface InvestigationCustodyRow {
  id: number;
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
  register(payload: { username: string; email: string; full_name: string; password: string }) {
    return apiFetch<{ access_token: string; token_type: string; user: User }>(
      "/api/auth/register",
      { method: "POST", body: JSON.stringify(payload) },
    );
  },
  logout() {
    return apiFetch<{ detail: string }>("/api/auth/logout", { method: "POST" });
  },
  me() {
    return apiFetch<User>("/api/auth/me");
  },
  listWorkspaces() {
    return apiFetch<Workspace[]>("/api/workspaces");
  },
  createWorkspace(name: string) {
    return apiFetch<Workspace>("/api/workspaces", {
      method: "POST", body: JSON.stringify({ name }),
    });
  },
  joinWorkspace(code: string) {
    return apiFetch<Workspace>("/api/workspaces/join", {
      method: "POST", body: JSON.stringify({ code }),
    });
  },
  listWorkspaceMembers() {
    return apiFetch<WorkspaceMember[]>("/api/workspaces/current/members");
  },
  updateWorkspaceMemberRole(userId: number, role: Role) {
    return apiFetch<WorkspaceMember>(`/api/workspaces/current/members/${userId}`, {
      method: "PATCH", body: JSON.stringify({ role }),
    });
  },
  createWorkspaceInvite(role: Role) {
    return apiFetch<WorkspaceInvite>("/api/workspaces/current/invites", {
      method: "POST", body: JSON.stringify({ role, expires_in_days: 7, max_uses: 25 }),
    });
  },
  aiProviderHealth() {
    return apiFetch<AiProviderHealth>("/api/ai/provider-health");
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
    async downloadEvidence(invId: number, evidenceId: number, filename: string) {    const API_BASE = import.meta.env.VITE_API_URL ?? "";
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
  analysisEligibility(invId: number) {
    return apiFetch<EligibilityEntry[]>(`/api/investigations/${invId}/analysis/eligibility`);
  },
  startAnalysisRun(invId: number, evidenceIds: number[]) {
    return apiFetch<AnalysisRun>(`/api/investigations/${invId}/analysis/runs`, {
      method: "POST",
      body: JSON.stringify({ evidence_ids: evidenceIds }),
    });
  },
  listAnalysisRuns(invId: number) {
    return apiFetch<AnalysisRun[]>(`/api/investigations/${invId}/analysis/runs`);
  },
  getAnalysisRun(invId: number, runId: number) {
    return apiFetch<AnalysisRun>(`/api/investigations/${invId}/analysis/runs/${runId}`);
  },
  listArtifacts(
    invId: number,
    filters: {
      artifact_type?: ArtifactType;
      evidence_id?: number;
      q?: string;
      limit?: number;
      offset?: number;
    } = {},
  ) {
    const params = new URLSearchParams();
    if (filters.artifact_type) params.set("artifact_type", filters.artifact_type);
    if (filters.evidence_id !== undefined) params.set("evidence_id", String(filters.evidence_id));
    if (filters.q) params.set("q", filters.q);
    params.set("limit", String(filters.limit ?? 100));
    params.set("offset", String(filters.offset ?? 0));
    return apiFetch<ArtifactList>(`/api/investigations/${invId}/analysis/artifacts?${params}`);
  },
  getArtifact(invId: number, artifactId: number) {
    return apiFetch<Artifact>(`/api/investigations/${invId}/analysis/artifacts/${artifactId}`);
  },
  listCorrelations(invId: number) {
    return apiFetch<Correlation[]>(`/api/investigations/${invId}/analysis/correlations`);
  },
  getCorrelation(invId: number, correlationId: number) {
    return apiFetch<CorrelationDetail>(
      `/api/investigations/${invId}/analysis/correlations/${correlationId}`,
    );
  },
  generateFindings(invId: number) {
    return apiFetch<{ findings: Finding[]; new_count: number }>(
      `/api/investigations/${invId}/analysis/findings/generate`,
      { method: "POST" },
    );
  },
  listFindings(invId: number, status?: FindingStatus) {
    const query = status ? `?status=${status}` : "";
    return apiFetch<Finding[]>(`/api/investigations/${invId}/analysis/findings${query}`);
  },
  getFinding(invId: number, findingId: number) {
    return apiFetch<Finding>(`/api/investigations/${invId}/analysis/findings/${findingId}`);
  },
  reviewFinding(invId: number, findingId: number, status: "accepted" | "rejected", note?: string) {
    return apiFetch<Finding>(
      `/api/investigations/${invId}/analysis/findings/${findingId}/review`,
      { method: "POST", body: JSON.stringify({ status, note: note ?? null }) },
    );
  },
  bulkReviewFindings(invId: number, payload: BulkFindingReviewPayload) {
    return apiFetch<BulkReviewResult>(
      `/api/investigations/${invId}/analysis/findings/bulk-review`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  },
  listGlobalFindings(
    filters: {
      status?: FindingStatus;
      severity?: string;
      rule_id?: string;
      investigation_id?: number;
      q?: string;
      limit?: number;
    } = {},
  ) {
    const params = new URLSearchParams();
    if (filters.status) params.set("status", filters.status);
    if (filters.severity) params.set("severity", filters.severity);
    if (filters.rule_id) params.set("rule_id", filters.rule_id);
    if (filters.investigation_id !== undefined) {
      params.set("investigation_id", String(filters.investigation_id));
    }
    if (filters.q) params.set("q", filters.q);
    if (filters.limit) params.set("limit", String(filters.limit));
    const qs = params.toString();
    return apiFetch<Finding[]>(`/api/findings${qs ? `?${qs}` : ""}`);
  },
  bulkReviewGlobalFindings(payload: BulkFindingReviewPayload) {
    return apiFetch<BulkReviewResult>("/api/findings/bulk-review", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  globalSearch(query: string) {
    const q = encodeURIComponent(query.trim());
    return apiFetch<SearchResponse>(`/api/search?q=${q}`);
  },
  listNotes(invId: number, findingId?: number) {
    const query = findingId !== undefined ? `?finding_id=${findingId}` : "";
    return apiFetch<Note[]>(`/api/investigations/${invId}/analysis/notes${query}`);
  },
  createNote(invId: number, body: string, findingId?: number) {
    return apiFetch<Note>(`/api/investigations/${invId}/analysis/notes`, {
      method: "POST",
      body: JSON.stringify({ body, finding_id: findingId ?? null }),
    });
  },
  updateNote(invId: number, noteId: number, body: string) {
    return apiFetch<Note>(`/api/investigations/${invId}/analysis/notes/${noteId}`, {
      method: "PATCH",
      body: JSON.stringify({ body }),
    });
  },
  generateReport(invId: number) {
    return apiFetch<Report>(`/api/investigations/${invId}/analysis/reports`, {
      method: "POST",
    });
  },
  listReports(invId: number) {
    return apiFetch<Report[]>(`/api/investigations/${invId}/analysis/reports`);
  },
  getReport(invId: number, reportId: number) {
    return apiFetch<Report>(`/api/investigations/${invId}/analysis/reports/${reportId}`);
  },
  adminListUsers() {
    return apiFetch<AdminUser[]>("/api/admin/users");
  },
  adminSetActive(userId: number, isActive: boolean) {
    return apiFetch<AdminUser>(`/api/admin/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive }),
    });
  },
  adminCreateUser(payload: {
    username: string;
    email: string;
    full_name?: string;
    password: string;
    role: Role;
  }) {
    return apiFetch<User>("/api/users", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
