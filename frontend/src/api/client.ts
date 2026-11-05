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
  | "verified" | "integrity_mismatch" | "unavailable" | "recovered"
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
  registration_status?: "pending" | "failed" | "ready";
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
  | "partial"
  | "blocked_not_verified"
  | "blocked_mismatch"
  | "blocked_unavailable"
  | "unsupported"
  | "failed";

export interface ParserCoverage {
  status: "complete" | "partial" | "rejected";
  parser_version?: string;
  units_processed?: number;
  characters_scanned?: number;
  warnings?: string[];
  total_pages?: number;
  processed_pages?: number[];
  skipped_pages?: { page: number; reason: string }[];
  unprocessed_page_count?: number;
}

export interface RunEvidenceOutcome {
  coverage?: ParserCoverage | null;
  input_sha256?: string | null;
  verification_id?: number | null;
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
  input_sha256?: string | null;
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
  semantic_key?: string | null;
  is_current?: boolean;
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

export interface RuleCoverage {
  rule_id: string;
  proposed_count: number;
  emitted_count: number;
  omitted_count: number;
  output_limit: number;
  evaluation_complete: boolean;
  candidate_pairs_checked?: number;
  pair_limit?: number;
}

export interface Finding {
  confidence_applicable?: boolean;
  support_snapshot?: { identity_version?: string; coverage?: Record<string, ParserCoverage>;
    kind?: string; event_set_id?: number; event_set_key?: string; event_keys?: string[];
    detection?: AuthenticationDetection; input_coverage?: AuthenticationCoverage;
    source_events?: SecurityEvent[]; source_event_snapshot_omitted?: number } | null;
  support_current?: boolean;
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
  authentication_investigation?: { policy: string; omitted_runs: number; sets: { semantic_key: string; name: string; selected_runs: number[]; coverage: AuthenticationCoverage }[];
    runs: AuthenticationRun[]; decision_snapshots: { id: number; rule_id: string; status: string; support_current: boolean; review_note: string | null }[];
    decision_snapshot_limit: number; decision_snapshots_may_be_truncated: boolean };
  rule_coverage?: RuleCoverage[];
  excluded_stale_finding_ids?: number[];
  support_policy?: string;
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
    support_snapshot?: Finding['support_snapshot'];
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
  selectWorkspace(workspaceId: number) {
    return apiFetch<Workspace>(`/api/workspaces/${workspaceId}/select`, { method: "POST" });
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
  recoverEvidence(invId: number, evidenceId: number) {
    return apiFetch<Evidence>(`/api/investigations/${invId}/evidence/${evidenceId}/recover`, { method: "POST" });
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
  findingCoverage(invId: number) {
    return apiFetch<RuleCoverage[]>(`/api/investigations/${invId}/analysis/findings/coverage`);
  },
  generateFindings(invId: number, perRuleLimit = 25) {
    return apiFetch<{ findings: Finding[]; new_count: number; rule_coverage: RuleCoverage[] }>(
      `/api/investigations/${invId}/analysis/findings/generate?per_rule_limit=${perRuleLimit}`,
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
  generateReport(invId: number, eventSetId?: number) {
    return apiFetch<Report>(`/api/investigations/${invId}/analysis/reports${eventSetId ? `?event_set_id=${eventSetId}` : ''}`, {
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


export interface EventProfileConfig {
  adapter: "linux_auth" | "windows_security" | "sysmon";
  format: "syslog" | "json" | "jsonl" | "csv";
  encoding: "utf-8" | "utf-8-sig" | "latin-1";
  source_host: string | null;
  timezone: string | null;
  year: number | null;
  timestamp_convention: "source" | "iso8601" | "syslog";
}
export interface EventProfile {
  id: number; name: string; semantic_key: string; version: string;
  configuration: EventProfileConfig;
}
export interface EventCoverage {
  status?: string; records_total?: number | null; recognized?: number; unrecognized?: number;
  rejected?: number; omitted?: number | null; events_created?: number; warnings?: string[];
  issues?: { locator: Record<string, unknown>; reason: string }[];
}
export interface EventRun {
  id: number; evidence_id: number; profile_id: number; status: string;
  input_sha256: string | null; verification_id: number | null;
  coverage: EventCoverage; error: string | null; created_at: string;
}
export interface SecurityEvent {
  id: number; semantic_key: string; evidence_id: number; evidence_number: string;
  first_run_id: number; profile_id: number; input_sha256: string; record_fingerprint: string;
  provider: string; category: string; event_type: string; outcome: string; event_id: string | null;
  username: string | null; account_domain: string | null; hostname: string | null;
  source_ip: string | null; destination_ip: string | null; source_port: number | null;
  destination_port: number | null; original_timestamp: string | null; timestamp_utc: string | null;
  time_semantics: { certainty: string; precision: string | null; assumptions: Record<string, unknown>[]; warnings: string[] };
  attributes: Record<string, unknown>; warnings: string[]; locator: Record<string, unknown>;
  profile_snapshot: Record<string, unknown>; adapter_version: string; normalization_version: string;
  coverage_status: string; support_verified: boolean;
}
export interface EventPage { items: SecurityEvent[]; total: number; limit: number; offset: number; time_policy: string; view_policy: string }
export interface EventRunPage { items: EventRun[]; total: number; limit: number; offset: number }
export interface AuthenticationCoverage {
  authentication_events?: number; evidence_count?: number; timestamp_certainty_counts?: Record<string, number>;
  selected_events: number; included_events: number; duplicate_source_occurrences_excluded: number;
  partial: boolean; warnings: string[];
  sources: { input_sha256: string; profile_key: string; status: string; coverage: EventCoverage }[];
}
export interface AuthenticationDetection {
  rule_id: string; rule_version: string; count: number; entities: { group: (string | null)[] };
  severity_rationale: string; limitations: string[]; configuration: Record<string, unknown>;
  event_keys: string[]; time_start: string; time_end: string;
}
export interface InvestigationEventSet {
  id: number; name: string; semantic_key: string; selected_runs: number[]; coverage: AuthenticationCoverage;
}
export interface AuthenticationRun {
  id: number; event_set_id: number; status: string; engine_version: string; error: string | null;
  configuration: Record<string, unknown>;
  coverage: { evaluated?: number; eligible?: number; excluded?: Record<string, number>;
    result_count?: number; budget_exhausted?: boolean;
    rules?: Record<string, { candidates: number; returned: number; omitted: number }> };
}
export const eventApi = {
  profiles: (id: number) => apiFetch<EventProfile[]>(`/api/investigations/${id}/events/profiles`),
  createProfile: (id: number, name: string, configuration: EventProfileConfig) => apiFetch<EventProfile>(
    `/api/investigations/${id}/events/profiles`, { method: "POST", body: JSON.stringify({ name, configuration }) }),
  runs: (id: number, offset = 0) => apiFetch<EventRunPage>(`/api/investigations/${id}/events/runs?limit=25&offset=${offset}`),
  ingest: (id: number, evidence_id: number, profile_id: number) => apiFetch<EventRun>(`/api/investigations/${id}/events/runs`,
    { method: "POST", body: JSON.stringify({ evidence_id, profile_id }) }),
  recover: (id: number, run: number) => apiFetch<EventRun>(`/api/investigations/${id}/events/runs/${run}/recover`, { method: "POST" }),
  list: (id: number, filters: Record<string, string>, offset = 0) => {
    const params = new URLSearchParams({ limit: "50", offset: String(offset) });
    Object.entries(filters).forEach(([key, value]) => { if (value.trim()) params.set(key, value.trim()); });
    return apiFetch<EventPage>(`/api/investigations/${id}/events?${params}`);
  },
  detail: (id: number, key: string) => apiFetch<SecurityEvent>(`/api/investigations/${id}/events/${key}`),
};

export const authenticationApi = {
  sets: (id: number) => apiFetch<InvestigationEventSet[]>(`/api/investigations/${id}/authentication/sets`),
  createSet: (id: number, name: string, run_ids: number[]) => apiFetch<InvestigationEventSet>(`/api/investigations/${id}/authentication/sets`, { method: 'POST', body: JSON.stringify({ name, run_ids }) }),
  execute: (id: number, event_set_id: number, configuration: Record<string, unknown>) => apiFetch<AuthenticationRun>(`/api/investigations/${id}/authentication/runs`, { method: 'POST', body: JSON.stringify({ event_set_id, configuration }) }),
  runs: (id: number, set: number, offset = 0) => apiFetch<{ items: AuthenticationRun[]; total: number }>(`/api/investigations/${id}/authentication/runs?event_set_id=${set}&offset=${offset}`),
  recover: (id: number, run: number) => apiFetch<AuthenticationRun>(`/api/investigations/${id}/authentication/runs/${run}/recover`, { method: 'POST' }),
  findings: (id: number, set: number, offset = 0, run?: number) => apiFetch<{ items: Finding[]; total: number }>(`/api/investigations/${id}/authentication/findings?event_set_id=${set}&offset=${offset}${run ? `&run_id=${run}` : ''}`),
  history: (id: number, finding: number) => apiFetch<{ actor_id: number; created_at: string; action: string; decision: Record<string, unknown> }[]>(`/api/investigations/${id}/authentication/findings/${finding}/history`),
  timeline: (id: number, set: number, filters: Record<string, string>, offset = 0) => {
    const params = new URLSearchParams({ event_set_id: String(set), limit: '50', offset: String(offset) });
    Object.entries(filters).forEach(([key, value]) => { if (value.trim()) params.set(key, value.trim()); });
    return apiFetch<{ items: SecurityEvent[]; total: number; ordering: string; lane: string; coverage: AuthenticationCoverage }>(`/api/investigations/${id}/authentication/timeline?${params}`);
  },
};

export interface InvestigationExport {
  id: number; investigation_id: number; requested_by_id: number | null;
  mode: 'metadata' | 'originals'; status: string; selection: { event_set_ids: number[]; report_ids: number[]; evidence_ids: number[] };
  package_sha256: string | null; byte_size: number | null; error: string | null; created_at: string;
  manifest_summary: { schema?: string; files?: number; originals?: number; warnings?: string[]; cleanup_pending?: boolean };
}
export interface ExportSelection { mode: 'metadata' | 'originals'; event_set_ids: number[]; report_ids: number[]; evidence_ids: number[] }
export const exportApi = {
  list: (id: number, offset = 0) => apiFetch<InvestigationExport[]>(`/api/investigations/${id}/exports?limit=25&offset=${offset}`),
  create: (id: number, selection: ExportSelection, key: string) => apiFetch<InvestigationExport>(`/api/investigations/${id}/exports`, { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify(selection) }),
  recover: (id: number, item: number) => apiFetch<InvestigationExport>(`/api/investigations/${id}/exports/${item}/recover`, { method: 'POST' }),
  download: async (id: number, item: InvestigationExport) => {
    const response = await fetch(`${API_BASE}/api/investigations/${id}/exports/${item.id}/download`, { headers: { Authorization: `Bearer ${getToken() ?? ''}` } });
    if (!response.ok) {
      if (response.status === 401) window.dispatchEvent(new CustomEvent('provena:unauthorized'));
      throw new ApiError(response.status, 'Package is unavailable, expired or access was denied. Reload history or create a new export.');
    }
    const maximum = Math.min(item.byte_size ?? 0, 2 * 1024 * 1024 * 1024);
    if (!response.body || maximum <= 0) throw new ApiError(409, 'Package size was not established. Reload export history.');
    const reader = response.body.getReader(); const parts: Uint8Array<ArrayBuffer>[] = []; let size = 0;
    try {
      while (true) {
        const next = await reader.read(); if (next.done) break;
        size += next.value.byteLength;
        if (size > maximum) { await reader.cancel(); throw new ApiError(413, 'Download exceeded its recorded size.'); }
        parts.push(new Uint8Array(next.value));
      }
    } finally { reader.releaseLock(); }
    if (size !== item.byte_size) throw new ApiError(409, 'Download was incomplete. Retry the existing export.');
    const object = URL.createObjectURL(new Blob(parts, { type: 'application/zip' }));
    const link = document.createElement('a'); link.href = object; link.download = `provena-case-${id}-export-${item.id}.zip`;
    link.click(); setTimeout(() => URL.revokeObjectURL(object), 1000);
  },
};
