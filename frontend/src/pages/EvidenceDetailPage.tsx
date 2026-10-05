// Evidence detail: overview, integrity verification, custody, timeline.

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type {
  CustodyAction,
  CustodyEvent,
  Evidence,
  EvidenceType,
  Investigation,
  TimelineEntry,
  User,
  Verification,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import {
  CUSTODY_ACTION_LABELS,
  EVIDENCE_TYPE_LABELS,
  INTEGRITY_LABELS,
  IntegrityBadge,
  ROLE_LABELS,
  buttonPrimaryClass,
  buttonSecondaryClass,
  formatBytes,
  formatDate,
  inputClass,
  labelClass,
} from "../components/ui";
import { ErrorBlock } from "./DashboardPage";

const CUSTODY_ACTIONS: CustodyAction[] = [
  "transferred",
  "released_for_analysis",
  "returned_to_custody",
  "received",
  "other",
];

export default function EvidenceDetailPage() {
  const { id, eid } = useParams<{ id: string; eid: string }>();
  const { user } = useAuth();
  const invId = Number(id);
  const evidenceId = Number(eid);

  const [item, setItem] = useState<Evidence | null>(null);
  const [inv, setInv] = useState<Investigation | null>(null);
  const [verifications, setVerifications] = useState<Verification[] | null>(null);
  const [custody, setCustody] = useState<CustodyEvent[] | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [verifyState, setVerifyState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [verifyError, setVerifyError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [investigation, detail, history, custodyHistory, evidenceTimeline] = await Promise.all([
        api.getInvestigation(invId),
        api.getEvidence(invId, evidenceId),
        api.listVerifications(invId, evidenceId),
        api.listCustody(invId, evidenceId),
        api.evidenceTimeline(invId, evidenceId),
      ]);
      setInv(investigation);
      setItem(detail);
      setVerifications(history);
      setCustody(custodyHistory);
      setTimeline(evidenceTimeline);
      setError(null);
      setNotFound(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setNotFound(true);
      else setError(err instanceof ApiError ? err.message : "Could not load evidence.");
    }
  }, [invId, evidenceId]);

  useEffect(() => {
    setItem(null);
    void load();
  }, [load]);

  async function onVerify() {
    setVerifyState("busy");
    setVerifyError(null);
    try {
      await api.verifyEvidence(invId, evidenceId);
      setVerifyState("done");
      await load();
    } catch (err) {
      setVerifyState("error");
      setVerifyError(err instanceof ApiError ? err.message : "Verification failed.");
    }
  }

  if (notFound) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-8 text-center">
        <p className="font-medium">Evidence not found</p>
        <p className="mt-1 text-sm text-slate-500">
          It may not exist, or you may not have access to it.
        </p>
      </div>
    );
  }
  if (error) return <ErrorBlock message={error} />;
  if (!item || !inv || !user) return <p className="text-sm text-slate-400">Loading evidence…</p>;

  const canManage =
    user.role === "admin" ||
    user.id === inv.created_by.id ||
    user.id === inv.lead_investigator.id;
  const archivedLocked = inv.status === "archived" && user.role !== "admin";
  const canRecordCustody =
    !archivedLocked && (canManage || user.role === "evidence_custodian");

  return (
    <div>
      <Link
        to={`/investigations/${invId}/evidence`}
        className="text-xs text-sky-300 hover:text-sky-200"
      >
        ← Back to evidence
      </Link>
      <p className="mt-2 font-mono text-xs text-sky-400">{item.evidence_number}</p>
      <div className="mt-1 flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold tracking-tight">{item.title}</h2>
        <IntegrityBadge status={item.integrity_status} />
      </div>
      {item.integrity_status === "mismatch" && (
        <p role="alert" className="mt-3 rounded-md border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-200">
          Integrity mismatch detected: the stored bytes no longer match the baseline
          digest recorded at registration. Treat this item as suspect and investigate
          before relying on it.
        </p>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Overview</h3>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
              <DetailItem label="Original filename" value={item.original_filename} />
              <DetailItem label="Type" value={EVIDENCE_TYPE_LABELS[item.evidence_type]} />
              <DetailItem label="Size" value={formatBytes(item.file_size)} />
              <DetailItem label="Source" value={item.source || "Not recorded"} />
              <DetailItem label="Acquired" value={formatDate(item.acquired_at)} />
              <DetailItem label="Registered" value={formatDate(item.created_at)} />
              <DetailItem
                label="Registered by"
                value={item.registered_by.full_name || item.registered_by.username}
              />
              <DetailItem
                label="Current holder"
                value={
                  item.current_holder
                    ? item.current_holder.full_name || item.current_holder.username
                    : "Unknown"
                }
              />
            </dl>
            <p className="mt-3 whitespace-pre-wrap text-sm text-slate-200">
              {item.description || "No description provided."}
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                onClick={() => void api.downloadEvidence(invId, evidenceId, item.original_filename)}
                className={buttonSecondaryClass}
              >
                Download evidence
              </button>
            </div>
          </section>

          <IntegritySection
            item={item}
            verifications={verifications}
            verifyState={verifyState}
            verifyError={verifyError}
            onVerify={() => void onVerify()}
          />

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              Evidence timeline
            </h3>
            {!timeline ? (
              <p className="mt-3 text-sm text-slate-500">Loading timeline…</p>
            ) : (
              <TimelineList entries={timeline} />
            )}
          </section>

          {canManage && !archivedLocked && (
            <MetadataEditSection item={item} invId={invId} onSaved={setItem} />
          )}
        </div>

        <div>
          <CustodySection
            invId={invId}
            item={item}
            custody={custody}
            canRecord={canRecordCustody}
            onChanged={(updated) => {
              setItem(updated);
              void load();
            }}
          />
        </div>
      </div>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt>
      <dd className="mt-0.5 break-words text-slate-200">{value}</dd>
    </div>
  );
}

function IntegritySection({
  item,
  verifications,
  verifyState,
  verifyError,
  onVerify,
}: {
  item: Evidence;
  verifications: Verification[] | null;
  verifyState: string;
  verifyError: string | null;
  onVerify: () => void;
}) {
  async function copyDigest() {
    try {
      await navigator.clipboard.writeText(item.sha256);
    } catch {
      // Clipboard may be unavailable; the digest remains selectable as text.
    }
  }

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Integrity</h3>
      <p className="mt-3 text-sm text-slate-400">
        The baseline digest was recorded when this evidence was ingested. Verification
        recomputes SHA-256 over the stored bytes and compares it to that baseline.
      </p>
      <div className="mt-3 rounded-md bg-slate-950 p-3">
        <p className="text-xs uppercase tracking-wider text-slate-500">Baseline SHA-256</p>
        <p className="mt-1 break-all font-mono text-xs text-slate-200">{item.sha256}</p>
        <button onClick={() => void copyDigest()} className="mt-2 text-xs text-sky-300 hover:text-sky-200">
          Copy digest
        </button>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <DetailItem label="Status" value={INTEGRITY_LABELS[item.integrity_status]} />
        <DetailItem label="Last checked" value={formatDate(item.last_verified_at)} />
      </dl>
      <button onClick={onVerify} disabled={verifyState === "busy"} className={`${buttonPrimaryClass} mt-4`}>
        {verifyState === "busy" ? "Verifying…" : "Verify integrity"}
      </button>
      {verifyError && <p className="mt-2 text-sm text-red-300">{verifyError}</p>}

      <h4 className="mt-5 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Verification history
      </h4>
      {!verifications ? (
        <p className="mt-2 text-sm text-slate-500">Loading history…</p>
      ) : verifications.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">No verifications yet.</p>
      ) : (
        <ol className="mt-2 space-y-2">
          {verifications.map((v) => (
            <li key={v.id} className="rounded-md bg-slate-800/60 px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-2">
                <IntegrityBadge status={v.result} />
                <span className="text-xs text-slate-500">{formatDate(v.created_at)}</span>
              </div>
              <p className="mt-1 text-xs text-slate-400">
                By {v.performed_by ? v.performed_by.full_name || v.performed_by.username : "unknown"}
                {v.observed_sha256 && v.observed_sha256 !== v.expected_sha256
                  ? ` · observed ${v.observed_sha256.slice(0, 16)}…`
                  : ""}
                {v.reason ? ` · ${v.reason}` : ""}
              </p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function CustodySection({
  invId,
  item,
  custody,
  canRecord,
  onChanged,
}: {
  invId: number;
  item: Evidence;
  custody: CustodyEvent[] | null;
  canRecord: boolean;
  onChanged: (updated: Evidence) => void;
}) {
  const [users, setUsers] = useState<User[]>([]);
  const [action, setAction] = useState<CustodyAction>("transferred");
  const [toUserId, setToUserId] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!canRecord) return;
    let cancelled = false;
    api
      .listUsers()
      .then((data) => {
        if (!cancelled) setUsers(data);
      })
      .catch(() => {
        if (!cancelled) setUsers([]);
      });
    return () => {
      cancelled = true;
    };
  }, [canRecord]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (action === "transferred" && !toUserId) {
      setError("Transfers require a target user.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await api.recordCustody(invId, item.id, {
        action,
        to_user_id: toUserId ? Number(toUserId) : undefined,
        notes: notes.trim(),
      });
      const updated = await api.getEvidence(invId, item.id);
      onChanged(updated);
      setNotes("");
      setToUserId("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not record the custody event.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
        Chain of custody
      </h3>
      {!custody ? (
        <p className="mt-3 text-sm text-slate-500">Loading custody…</p>
      ) : (
        <ol className="mt-3 space-y-3">
          {custody.map((event) => (
            <li key={event.id} className="border-l-2 border-slate-700 pl-3 text-sm">
              <p className="font-medium text-slate-200">{CUSTODY_ACTION_LABELS[event.action]}</p>
              <p className="text-xs text-slate-400">
                {event.from_user ? event.from_user.username : "…"} →{" "}
                {event.to_user ? event.to_user.username : "…"}
              </p>
              {event.notes && <p className="mt-0.5 text-xs text-slate-500">{event.notes}</p>}
              <p className="text-xs text-slate-500">
                {event.performed_by ? event.performed_by.username : "System"} ·{" "}
                {formatDate(event.created_at)}
              </p>
            </li>
          ))}
        </ol>
      )}

      {canRecord && (
        <form onSubmit={(e) => void onSubmit(e)} className="mt-4 space-y-3 border-t border-slate-800 pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Record custody event
          </h4>
          <div>
            <label htmlFor="custody-action" className={labelClass}>
              Action
            </label>
            <select
              id="custody-action"
              value={action}
              onChange={(e) => setAction(e.target.value as CustodyAction)}
              className={inputClass}
            >
              {CUSTODY_ACTIONS.map((a) => (
                <option key={a} value={a}>
                  {CUSTODY_ACTION_LABELS[a]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="custody-to" className={labelClass}>
              To user {action === "transferred" ? "(required)" : "(optional)"}
            </label>
            <select
              id="custody-to"
              value={toUserId}
              onChange={(e) => setToUserId(e.target.value)}
              className={inputClass}
            >
              <option value="">None</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name || u.username} ({ROLE_LABELS[u.role]})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="custody-notes" className={labelClass}>
              Notes
            </label>
            <input
              id="custody-notes"
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className={inputClass}
              placeholder="Reason for the transfer…"
              maxLength={1000}
            />
          </div>
          {error && <p className="text-sm text-red-300">{error}</p>}
          <button type="submit" disabled={busy} className={buttonSecondaryClass}>
            {busy ? "Recording…" : "Record event"}
          </button>
        </form>
      )}
    </section>
  );
}

function MetadataEditSection({
  item,
  invId,
  onSaved,
}: {
  item: Evidence;
  invId: number;
  onSaved: (v: Evidence) => void;
}) {
  const [title, setTitle] = useState(item.title);
  const [description, setDescription] = useState(item.description);
  const [evidenceType, setEvidenceType] = useState<EvidenceType>(item.evidence_type);
  const [source, setSource] = useState(item.source);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      setError("A title is required.");
      return;
    }
    setError(null);
    setSaved(false);
    setBusy(true);
    try {
      const updated = await api.updateEvidence(invId, item.id, {
        title: title.trim(),
        description,
        evidence_type: evidenceType,
        source,
      });
      onSaved(updated);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save changes.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
        Edit metadata
      </h3>
      <p className="mt-1 text-xs text-slate-500">
        File bytes, baseline digest, uploader, and registration time cannot be changed.
      </p>
      <form onSubmit={(e) => void onSubmit(e)} className="mt-3 space-y-4">
        <div>
          <label htmlFor="ev-edit-title" className={labelClass}>
            Title
          </label>
          <input
            id="ev-edit-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={inputClass}
            maxLength={255}
          />
        </div>
        <div>
          <label htmlFor="ev-edit-description" className={labelClass}>
            Description
          </label>
          <textarea
            id="ev-edit-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className={`${inputClass} min-h-24`}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="ev-edit-type" className={labelClass}>
              Type
            </label>
            <select
              id="ev-edit-type"
              value={evidenceType}
              onChange={(e) => setEvidenceType(e.target.value as EvidenceType)}
              className={inputClass}
            >
              {(Object.keys(EVIDENCE_TYPE_LABELS) as EvidenceType[]).map((t) => (
                <option key={t} value={t}>
                  {EVIDENCE_TYPE_LABELS[t]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="ev-edit-source" className={labelClass}>
              Source
            </label>
            <input
              id="ev-edit-source"
              type="text"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className={inputClass}
              maxLength={255}
            />
          </div>
        </div>
        {error && (
          <p role="alert" className="rounded-md bg-red-950 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}
        {saved && <p className="text-sm text-emerald-300">Changes saved.</p>}
        <button type="submit" disabled={busy} className={buttonPrimaryClass}>
          {busy ? "Saving…" : "Save changes"}
        </button>
      </form>
    </section>
  );
}

export function TimelineList({ entries }: { entries: TimelineEntry[] }) {
  if (entries.length === 0) {
    return <p className="mt-3 text-sm text-slate-500">No events yet.</p>;
  }
  return (
    <ol className="mt-3 space-y-3">
      {entries.map((entry, index) => (
        <li key={index} className="border-l-2 border-slate-700 pl-3 text-sm">
          <p className="font-medium text-slate-200">{entry.title}</p>
          {entry.detail && <p className="text-xs text-slate-400">{entry.detail}</p>}
          <p className="text-xs text-slate-500">
            {entry.actor_username ?? "System"} · {formatDate(entry.occurred_at)}
          </p>
        </li>
      ))}
    </ol>
  );
}
