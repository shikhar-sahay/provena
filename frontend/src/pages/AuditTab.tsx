// Investigation audit log tab: application actions with human-readable labels.

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { AuditEntry } from "../api/client";
import { formatDate } from "../components/ui";
import { ErrorBlock } from "./DashboardPage";

const ACTION_LABELS: Record<string, string> = {
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
};

export default function AuditTab() {
  const { id } = useParams<{ id: string }>();
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .investigationAudit(Number(id))
      .then((data) => {
        if (!cancelled) setEntries(data);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Could not load the audit log.");
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <ErrorBlock message={error} />;

  return (
    <div>
      <h2 className="text-lg font-semibold">Audit log</h2>
      <p className="mt-1 text-sm text-slate-400">
        Application actions on this investigation, recorded automatically. The audit
        log records that actions happened; chain of custody lives with the evidence.
      </p>
      <div className="mt-4 rounded-lg border border-slate-800 bg-slate-900 p-5">
        {!entries ? (
          <p className="text-sm text-slate-500">Loading audit log…</p>
        ) : entries.length === 0 ? (
          <p className="text-sm text-slate-500">No audit events yet.</p>
        ) : (
          <ol className="space-y-3">
            {entries.map((entry) => (
              <li key={entry.id} className="border-l-2 border-slate-700 pl-3 text-sm">
                <p className="font-medium text-slate-200">
                  {ACTION_LABELS[entry.action] ?? entry.action}
                </p>
                <p className="text-xs text-slate-500">
                  {entry.actor_username ?? "System"} · {formatDate(entry.created_at)}
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
