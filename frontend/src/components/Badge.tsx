// Badges: restrained semantic pills. Color never carries meaning alone,
// labels always accompany the tone.

import type {
  CustodyAction,
  EvidenceType,
  IntegrityStatus,
  InvestigationStatus,
  Priority,
  Role,
} from "../api/client";

export type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const TONES: Record<Tone, string> = {
  neutral: "bg-hover text-ink2 border-line",
  info: "bg-info-bg text-info-ink border-info-line",
  success: "bg-success-bg text-success-ink border-success-line",
  warning: "bg-warning-bg text-warning-ink border-warning-line",
  danger: "bg-danger-bg text-danger-ink border-danger-line",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-px text-xs font-medium whitespace-nowrap ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

export const STATUS_LABELS: Record<InvestigationStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  under_review: "Under review",
  closed: "Closed",
  archived: "Archived",
};

const STATUS_TONES: Record<InvestigationStatus, Tone> = {
  open: "info",
  in_progress: "warning",
  under_review: "info",
  closed: "success",
  archived: "neutral",
};

export function StatusBadge({ status }: { status: InvestigationStatus }) {
  return <Badge tone={STATUS_TONES[status]}>{STATUS_LABELS[status]}</Badge>;
}

const PRIORITY_TONES: Record<Priority, Tone> = {
  low: "neutral",
  medium: "info",
  high: "warning",
  critical: "danger",
};

export function PriorityBadge({ priority }: { priority: Priority }) {
  const label = priority.charAt(0).toUpperCase() + priority.slice(1);
  return <Badge tone={PRIORITY_TONES[priority]}>{label}</Badge>;
}

export const INTEGRITY_LABELS: Record<IntegrityStatus, string> = {
  not_verified: "Not verified",
  verified: "Verified",
  mismatch: "Mismatch detected",
  unavailable: "Unavailable",
};

const INTEGRITY_TONES: Record<IntegrityStatus, Tone> = {
  not_verified: "neutral",
  verified: "success",
  mismatch: "danger",
  unavailable: "warning",
};

export function IntegrityBadge({ status }: { status: IntegrityStatus }) {
  return <Badge tone={INTEGRITY_TONES[status]}>{INTEGRITY_LABELS[status]}</Badge>;
}

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Admin",
  investigator: "Investigator",
  forensic_analyst: "Forensic Analyst",
  evidence_custodian: "Evidence Custodian",
};

export function RoleBadge({ role }: { role: Role }) {
  return <Badge tone="neutral">{ROLE_LABELS[role]}</Badge>;
}

export const EVIDENCE_TYPE_LABELS: Record<EvidenceType, string> = {
  log: "Log",
  document: "Document",
  image: "Image",
  network: "Network",
  email: "Email",
  device: "Device",
  archive: "Archive",
  other: "Other",
};

export const CUSTODY_ACTION_LABELS: Record<CustodyAction, string> = {
  registered: "Registered",
  transferred: "Transferred",
  released_for_analysis: "Released for analysis",
  returned_to_custody: "Returned to custody",
  received: "Received",
  other: "Other",
};
