// Shared labels for the intelligence workflow: eligibility, runs, findings.

import type { FindingStatus, RunEvidenceStatus, RunStatus } from "../api/client";

export const RUN_EVIDENCE_LABELS: Record<RunEvidenceStatus, string> = {
  processed: "Processed",
  partial: "Partial coverage",
  blocked_not_verified: "Needs verification",
  blocked_mismatch: "Blocked: mismatch",
  blocked_unavailable: "Blocked: unavailable",
  unsupported: "Unsupported format",
  failed: "Failed",
};

export const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

export const FINDING_STATUS_LABELS: Record<FindingStatus, string> = {
  pending_review: "Pending review",
  accepted: "Accepted",
  rejected: "Rejected",
};

export const SEVERITY_TONES: Record<string, "neutral" | "info" | "warning" | "danger"> = {
  low: "info",
  medium: "warning",
  high: "danger",
  critical: "danger",
};

export function severityTone(severity: string): "neutral" | "info" | "warning" | "danger" {
  return SEVERITY_TONES[severity] ?? "neutral";
}

export const ARTIFACT_TYPE_LABELS: Record<string, string> = {
  IP_ADDRESS: "IP address",
  EMAIL_ADDRESS: "Email",
  USERNAME: "Username",
  HOSTNAME: "Hostname",
  DOMAIN: "Domain",
  FILE_PATH: "File path",
  FILE_NAME: "File name",
  HASH: "Hash",
  USB_DEVICE: "USB device",
  TIMESTAMP: "Timestamp",
  URL: "URL",
  PORT: "Port",
  MAC_ADDRESS: "MAC address",
  PROCESS_NAME: "Process",
};

export function artifactTypeLabel(artifactType: string): string {
  return ARTIFACT_TYPE_LABELS[artifactType] ?? artifactType;
}

function baseLocatorLabel(locator: Record<string, unknown>): string {
  const kind = locator["kind"];
  if (kind === "line" && typeof locator["line"] === "number") {
    return `Line ${locator["line"]}`;
  }
  if (kind === "csv") {
    return `Row ${String(locator["row"] ?? "?")} · ${String(locator["column"] ?? "column")}`;
  }
  if (kind === "json") {
    return String(locator["path"] ?? "JSON value");
  }
  if (kind === "pdf") {
    return `Page ${String(locator["page"] ?? "?")}`;
  }
  return "Source location";
}


export function locatorLabel(locator: Record<string, unknown>): string {
  const span = locator["span"];
  const range = Array.isArray(span) && span.length === 2 && span.every(Number.isInteger)
    ? ` · characters [${span[0]}, ${span[1]})` : "";
  return baseLocatorLabel(locator) + range;
}
