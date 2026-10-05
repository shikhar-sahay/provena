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
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  const token = getToken();
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
};
