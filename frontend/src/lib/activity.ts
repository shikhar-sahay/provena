// Human labels for application audit actions, shared by dashboard, audit log,
// and timeline views.

export const ACTION_LABELS: Record<string, string> = {
  INVESTIGATION_CREATED: "Investigation created",
  INVESTIGATION_UPDATED: "Investigation updated",
  INVESTIGATION_STATUS_CHANGED: "Status changed",
  INVESTIGATION_MEMBER_ADDED: "Member added",
  INVESTIGATION_MEMBER_REMOVED: "Member removed",
  EVIDENCE_REGISTERED: "Evidence registered",
  EVIDENCE_METADATA_UPDATED: "Evidence metadata updated",
  EVIDENCE_VERIFIED: "Evidence verified",
  EVIDENCE_INTEGRITY_MISMATCH: "Integrity mismatch detected",
  EVIDENCE_DOWNLOADED: "Evidence downloaded",
  CUSTODY_TRANSFERRED: "Custody transferred",
  EVIDENCE_CUSTODY_UPDATED: "Custody event recorded",
  AI_ANALYSIS_STARTED: "Analysis started",
  AI_ANALYSIS_COMPLETED: "Analysis completed",
  AI_ANALYSIS_FAILED: "Analysis failed",
  AI_FINDING_GENERATED: "Findings evaluated",
  AI_FINDING_ACCEPTED: "Finding accepted",
  AI_FINDING_REJECTED: "Finding rejected",
  INVESTIGATION_NOTE_ADDED: "Investigator note added",
  INVESTIGATION_NOTE_UPDATED: "Investigator note updated",
  REPORT_GENERATED: "Report generated",
  USER_LOGIN: "Signed in",
  USER_LOGOUT: "Signed out",
  USER_CREATED: "User created",
};

export function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action;
}
