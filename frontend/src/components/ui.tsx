// Shared presentation helpers: status/priority badges, role labels, form styles.

import type {
  CustodyAction,
  EvidenceType,
  IntegrityStatus,
  InvestigationStatus,
  Priority,
  Role,
} from "../api/client";

export const STATUS_LABELS: Record<InvestigationStatus, string> = {
  open: "Open",
  in_progress: "In Progress",
  under_review: "Under Review",
  closed: "Closed",
  archived: "Archived",
};

const STATUS_STYLES: Record<InvestigationStatus, string> = {
  open: "bg-sky-950 text-sky-300 ring-sky-800",
  in_progress: "bg-amber-950 text-amber-300 ring-amber-800",
  under_review: "bg-violet-950 text-violet-300 ring-violet-800",
  closed: "bg-emerald-950 text-emerald-300 ring-emerald-800",
  archived: "bg-slate-800 text-slate-400 ring-slate-700",
};

const PRIORITY_STYLES: Record<Priority, string> = {
  low: "bg-slate-800 text-slate-300 ring-slate-700",
  medium: "bg-sky-950 text-sky-300 ring-sky-800",
  high: "bg-amber-950 text-amber-300 ring-amber-800",
  critical: "bg-red-950 text-red-300 ring-red-800",
};

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Admin",
  investigator: "Investigator",
  forensic_analyst: "Forensic Analyst",
  evidence_custodian: "Evidence Custodian",
};

export function StatusBadge({ status }: { status: InvestigationStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${STATUS_STYLES[status]}`}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${PRIORITY_STYLES[priority]}`}
    >
      {priority.charAt(0).toUpperCase() + priority.slice(1)}
    </span>
  );
}

export function formatDate(value: string | null): string {
  if (!value) return "Not set";
  return new Date(value).toLocaleString();
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let size = bytes / 1024;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(1)} ${units[unit]}`;
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

const INTEGRITY_STYLES: Record<IntegrityStatus, string> = {
  not_verified: "bg-slate-800 text-slate-300 ring-slate-700",
  verified: "bg-emerald-950 text-emerald-300 ring-emerald-800",
  mismatch: "bg-red-950 text-red-300 ring-red-700",
  unavailable: "bg-amber-950 text-amber-300 ring-amber-800",
};

export const INTEGRITY_LABELS: Record<IntegrityStatus, string> = {
  not_verified: "Not verified",
  verified: "Verified",
  mismatch: "Integrity mismatch detected",
  unavailable: "Unavailable",
};

export function IntegrityBadge({ status }: { status: IntegrityStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${INTEGRITY_STYLES[status]}`}
    >
      {INTEGRITY_LABELS[status]}
    </span>
  );
}

export const CUSTODY_ACTION_LABELS: Record<CustodyAction, string> = {
  registered: "Registered",
  transferred: "Transferred",
  released_for_analysis: "Released for analysis",
  returned_to_custody: "Returned to custody",
  received: "Received",
  other: "Other",
};

export const inputClass =
  "w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-500 focus:outline-none";

export const labelClass = "mb-1 block text-xs font-medium uppercase tracking-wider text-slate-400";

export const buttonPrimaryClass =
  "rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50";

export const buttonSecondaryClass =
  "rounded-md border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-800 disabled:opacity-50";
