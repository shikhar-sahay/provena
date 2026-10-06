// Evidence detail: a forensic record with integrity, custody, and timeline.
// Baseline facts stay prominent; verification and custody are explicit actions.

import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle,
  Check,
  ChevronRight,
  Copy,
  Download,
  Pencil,
  Repeat,
  Send,
} from "lucide-react";
import { api } from "../api/client";
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
} from "../components/Badge";
import { Button } from "../components/Button";
import { Dialog } from "../components/Dialog";
import { Field, Input, Select, Textarea } from "../components/Field";
import { EmptyState, ErrorState, Skeleton } from "../components/StateViews";
import { useToast } from "../components/Toast";
import { actionErrorMessage } from "../lib/errors";
import { displayName, formatBytes, formatDate, timeAgo } from "../lib/format";

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
  const { notify } = useToast();
  const invId = Number(id);
  const evidenceId = Number(eid);

  const [item, setItem] = useState<Evidence | null>(null);
  const [inv, setInv] = useState<Investigation | null>(null);
  const [verifications, setVerifications] = useState<Verification[] | null>(null);
  const [custody, setCustody] = useState<CustodyEvent[] | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [transferring, setTransferring] = useState(false);

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
      if (err instanceof Error && "status" in err && (err as { status: number }).status === 404) {
        setNotFound(true);
      } else {
        setError(actionErrorMessage(err, "Could not load evidence."));
      }
    }
  }, [invId, evidenceId]);

  useEffect(() => {
    setItem(null);
    void load();
  }, [load]);

  async function onVerify() {
    setVerifying(true);
    try {
      const result = await api.verifyEvidence(invId, evidenceId);
      if (result.result === "verified") {
        notify("success", "Integrity verified: bytes match the baseline.");
      } else if (result.result === "mismatch") {
        notify("error", "Integrity mismatch detected. The item is now flagged.");
      } else {
        notify("error", "Stored file unavailable: verification could not read it.");
      }
      await load();
    } catch (err) {
      notify("error", actionErrorMessage(err, "Verification failed."));
    } finally {
      setVerifying(false);
    }
  }

  async function onDownload() {
    if (!item) return;
    setDownloading(true);
    try {
      await api.downloadEvidence(invId, evidenceId, item.original_filename);
      notify("success", "Download started.");
    } catch (err) {
      notify("error", actionErrorMessage(err, "Download failed."));
    } finally {
      setDownloading(false);
    }
  }

  if (notFound) {
    return (
      <EmptyState
        title="Evidence not found"
        body="It may not exist, or you may not have access to it."
        action={
          <Link to={`/investigations/${invId}/evidence`} className="text-sm font-medium text-accentink hover:underline">
            Back to evidence
          </Link>
        }
      />
    );
  }
  if (error) return <ErrorState body={error} onRetry={() => void load()} />;
  if (!item || !inv || !user) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }

  const canManage =
    user.role === "admin" ||
    user.id === inv.created_by.id ||
    user.id === inv.lead_investigator.id;
  const archivedLocked = inv.status === "archived" && user.role !== "admin";
  const canRecordCustody =
    !archivedLocked && (canManage || user.role === "evidence_custodian");

  return (
    <div>
      <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-[13px] text-ink3">
        <Link to={`/investigations/${invId}/evidence`} className="hover:text-ink2 hover:underline">
          Evidence
        </Link>
        <ChevronRight size={13} aria-hidden="true" />
        <span className="font-mono" aria-current="page">
          {item.evidence_number}
        </span>
      </nav>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
        <h1 className="text-xl font-semibold tracking-tight">{item.title}</h1>
        <IntegrityBadge status={item.integrity_status} />
      </div>
      <p className="mt-1 font-mono text-xs text-ink3">
        {item.evidence_number} · {item.original_filename} · {formatBytes(item.file_size)}
      </p>

      {item.integrity_status === "mismatch" && (
        <p
          role="alert"
          className="mt-3 flex items-start gap-2 rounded-md border border-danger-line bg-danger-bg px-3 py-2.5 text-sm text-danger-ink"
        >
          <AlertTriangle size={15} className="mt-0.5 shrink-0" />
          Integrity mismatch detected: the stored bytes no longer match the baseline
          digest recorded at registration. Treat this item as suspect and investigate
          before relying on it.
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="primary" size="sm" icon={<Repeat size={14} />} loading={verifying} onClick={() => void onVerify()}>
          Verify integrity
        </Button>
        <Button variant="secondary" size="sm" icon={<Download size={14} />} loading={downloading} onClick={() => void onDownload()}>
          Download
        </Button>
        {canRecordCustody && (
          <Button variant="secondary" size="sm" icon={<Send size={14} />} onClick={() => setTransferring(true)}>
            Record custody
          </Button>
        )}
        {canManage && !archivedLocked && (
          <Button variant="ghost" size="sm" icon={<Pencil size={14} />} onClick={() => setEditing(true)}>
            Edit metadata
          </Button>
        )}
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <OverviewCard item={item} />
          <IntegrityCard item={item} verifications={verifications} />
          <section className="rounded-md border border-line bg-surface">
            <div className="border-b border-line px-4 py-2.5">
              <h2 className="text-sm font-semibold">Evidence timeline</h2>
            </div>
            <div className="px-4 py-3">
              {!timeline ? (
                <Skeleton className="h-24" />
              ) : (
                <TimelineSpine entries={timeline} />
              )}
            </div>
          </section>
        </div>

        <div>
          <CustodyCard custody={custody} />
        </div>
      </div>

      <MetadataDialog
        open={editing}
        onClose={() => setEditing(false)}
        invId={invId}
        item={item}
        onSaved={(updated) => {
          setItem(updated);
          setEditing(false);
        }}
      />
      <CustodyDialog
        open={transferring}
        onClose={() => setTransferring(false)}
        invId={invId}
        item={item}
        onSaved={(updated) => {
          setItem(updated);
          setTransferring(false);
          void load();
        }}
      />
    </div>
  );
}

function OverviewCard({ item }: { item: Evidence }) {
  const [copied, setCopied] = useState(false);

  async function copyDigest() {
    try {
      await navigator.clipboard.writeText(item.sha256);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard may be unavailable; the digest remains selectable as text.
    }
  }

  return (
    <section className="rounded-md border border-line bg-surface">
      <div className="border-b border-line px-4 py-2.5">
        <h2 className="text-sm font-semibold">Overview</h2>
      </div>
      <div className="space-y-4 px-4 py-3">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-3">
          <DetailItem label="Type" value={EVIDENCE_TYPE_LABELS[item.evidence_type]} />
          <DetailItem label="Source" value={item.source || "Not recorded"} />
          <DetailItem label="Acquired" value={formatDate(item.acquired_at)} />
          <DetailItem label="Registered" value={formatDate(item.created_at)} />
          <DetailItem label="Registered by" value={displayName(item.registered_by)} />
          <DetailItem
            label="Current holder"
            value={item.current_holder ? displayName(item.current_holder) : "Unknown"}
          />
        </dl>
        {item.description && <p className="text-sm whitespace-pre-wrap">{item.description}</p>}
        <div className="rounded-md border border-line bg-canvas p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-medium tracking-wide text-ink2 uppercase">Baseline SHA-256</p>
            <button
              onClick={() => void copyDigest()}
              className="pv-transition inline-flex cursor-pointer items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium text-accentink hover:bg-accentsoft"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <p className="mt-1.5 font-mono text-xs break-all text-ink select-all">{item.sha256}</p>
        </div>
      </div>
    </section>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-ink3">{label}</dt>
      <dd className="mt-0.5 truncate text-ink" title={value}>
        {value}
      </dd>
    </div>
  );
}

function IntegrityCard({
  item,
  verifications,
}: {
  item: Evidence;
  verifications: Verification[] | null;
}) {
  return (
    <section className="rounded-md border border-line bg-surface">
      <div className="border-b border-line px-4 py-2.5">
        <h2 className="text-sm font-semibold">Integrity</h2>
      </div>
      <div className="space-y-3 px-4 py-3">
        <ol className="flex flex-col gap-0 text-[13px] sm:flex-row sm:items-center sm:gap-2">
          <Step done label="Baseline created" detail={formatDate(item.created_at)} />
          <StepConnector />
          <Step
            done={item.integrity_status !== "not_verified"}
            current={item.integrity_status === "not_verified"}
            label="Verification run"
            detail={item.last_verified_at ? formatDate(item.last_verified_at) : "Not yet run"}
          />
          <StepConnector />
          <Step
            done={item.integrity_status === "verified"}
            current={item.integrity_status === "mismatch" || item.integrity_status === "unavailable"}
            label={INTEGRITY_LABELS[item.integrity_status]}
            detail={
              item.integrity_status === "not_verified"
                ? "Run verification to compare bytes to the baseline."
                : item.integrity_status === "verified"
                  ? "Stored bytes match the baseline."
                  : item.integrity_status === "mismatch"
                    ? "Stored bytes differ from the baseline."
                    : "Stored bytes could not be read."
            }
          />
        </ol>

        <div>
          <h3 className="text-xs font-semibold tracking-wide text-ink2 uppercase">Verification history</h3>
          {!verifications ? (
            <Skeleton className="mt-2 h-16" />
          ) : verifications.length === 0 ? (
            <p className="mt-2 text-sm text-ink3">
              No verifications yet. The baseline above was recorded at ingestion; running
              verification recomputes the digest and compares it.
            </p>
          ) : (
            <ol className="mt-2 space-y-2">
              {verifications.map((v) => (
                <li key={v.id} className="rounded-md border border-line px-3 py-2 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <IntegrityBadge status={v.result} />
                    <span className="text-xs text-ink3">{formatDate(v.created_at)}</span>
                  </div>
                  <dl className="mt-1.5 grid gap-1 font-mono text-xs">
                    <div className="flex gap-2">
                      <dt className="w-16 shrink-0 font-sans text-ink3">Expected</dt>
                      <dd className="break-all">{v.expected_sha256}</dd>
                    </div>
                    {v.observed_sha256 && (
                      <div className="flex gap-2">
                        <dt className="w-16 shrink-0 font-sans text-ink3">Observed</dt>
                        <dd className="break-all">{v.observed_sha256}</dd>
                      </div>
                    )}
                  </dl>
                  <p className="mt-1 text-xs text-ink3">
                    By {v.performed_by ? displayName(v.performed_by) : "unknown"}
                    {v.reason ? ` · ${v.reason}` : ""}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </section>
  );
}

function Step({ done, current = false, label, detail }: { done: boolean; current?: boolean; label: string; detail: string }) {
  return (
    <li className="flex items-start gap-2 sm:flex-1 sm:flex-col sm:gap-1">
      <span
        aria-hidden="true"
        className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border sm:mt-0 ${
          done
            ? "border-success-line bg-success-bg text-success-ink"
            : current
              ? "border-warning-line bg-warning-bg text-warning-ink"
              : "border-line bg-hover text-ink3"
        }`}
      >
        {done ? <Check size={10} /> : <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      </span>
      <span>
        <span className="block font-medium">{label}</span>
        <span className="block text-xs text-ink3">{detail}</span>
      </span>
    </li>
  );
}

function StepConnector() {
  return <span aria-hidden="true" className="hidden h-px flex-1 bg-line sm:block" />;
}

function CustodyCard({ custody }: { custody: CustodyEvent[] | null }) {
  return (
    <section className="overflow-hidden rounded-md border border-line bg-surface">
      <div className="border-b border-line px-4 py-2.5">
        <h2 className="text-sm font-semibold">Chain of custody</h2>
      </div>
      <div className="px-4 py-3">
        {!custody ? (
          <Skeleton className="h-24" />
        ) : (
          <ol className="relative space-y-4 border-l border-line pl-0">
            {custody.map((event) => (
              <li key={event.id} className="relative pl-5">
                <span
                  aria-hidden="true"
                  className="absolute top-1 -left-[5px] h-2.5 w-2.5 rounded-full border-2 border-surface bg-ink3"
                />
                <p className="text-sm font-medium">{CUSTODY_ACTION_LABELS[event.action]}</p>
                <p className="text-[13px] text-ink2">
                  {event.from_user ? displayName(event.from_user) : "…"} →{" "}
                  {event.to_user ? displayName(event.to_user) : "…"}
                </p>
                {event.notes && <p className="mt-0.5 text-[13px] text-ink3">{event.notes}</p>}
                <p className="mt-0.5 text-xs text-ink3">
                  {event.performed_by ? displayName(event.performed_by) : "System"} ·{" "}
                  {formatDate(event.created_at)}
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}

function MetadataDialog({
  open,
  onClose,
  invId,
  item,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  invId: number;
  item: Evidence;
  onSaved: (v: Evidence) => void;
}) {
  const { notify } = useToast();
  const [title, setTitle] = useState(item.title);
  const [description, setDescription] = useState(item.description);
  const [evidenceType, setEvidenceType] = useState<EvidenceType>(item.evidence_type);
  const [source, setSource] = useState(item.source);
  const [titleError, setTitleError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffectReset(open, item, () => {
    setTitle(item.title);
    setDescription(item.description);
    setEvidenceType(item.evidence_type);
    setSource(item.source);
    setTitleError(null);
    setError(null);
  });

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      setTitleError("A title is required.");
      return;
    }
    setTitleError(null);
    setError(null);
    setBusy(true);
    try {
      const updated = await api.updateEvidence(invId, item.id, {
        title: title.trim(),
        description,
        evidence_type: evidenceType,
        source,
      });
      onSaved(updated);
      notify("success", "Evidence metadata updated.");
      onClose();
    } catch (err) {
      setError(actionErrorMessage(err, "Could not save changes."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Edit metadata" description="Bytes, baseline, uploader, and registration time cannot change.">
      <form onSubmit={(e) => void onSubmit(e)} className="space-y-4">
        <Field label="Title" htmlFor="ev-title" error={titleError}>
          <Input id="ev-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={255} autoFocus />
        </Field>
        <Field label="Description" htmlFor="ev-description">
          <Textarea id="ev-description" value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Type" htmlFor="ev-type">
            <Select id="ev-type" value={evidenceType} onChange={(e) => setEvidenceType(e.target.value as EvidenceType)}>
              {(Object.keys(EVIDENCE_TYPE_LABELS) as EvidenceType[]).map((t) => (
                <option key={t} value={t}>
                  {EVIDENCE_TYPE_LABELS[t]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Source" htmlFor="ev-source">
            <Input id="ev-source" value={source} onChange={(e) => setSource(e.target.value)} maxLength={255} />
          </Field>
        </div>
        {error && (
          <p role="alert" className="rounded-md border border-danger-line bg-danger-bg px-3 py-2 text-sm text-danger-ink">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" type="button" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" loading={busy}>
            Save changes
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function CustodyDialog({
  open,
  onClose,
  invId,
  item,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  invId: number;
  item: Evidence;
  onSaved: (v: Evidence) => void;
}) {
  const { notify } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [action, setAction] = useState<CustodyAction>("transferred");
  const [toUserId, setToUserId] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffectReset(open, item, () => {
    setAction("transferred");
    setToUserId("");
    setNotes("");
    setError(null);
  });

  // Load candidate users once per open.
  useEffectOpenUsers(open, setUsers);

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
      onSaved(updated);
      notify("success", "Custody event recorded.");
      onClose();
    } catch (err) {
      setError(actionErrorMessage(err, "Could not record the custody event."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Record custody event" description={`${item.evidence_number} · currently held by ${item.current_holder ? displayName(item.current_holder) : "unknown"}. History stays append-only.`}>
      <form onSubmit={(e) => void onSubmit(e)} className="space-y-4">
        <Field label="Action" htmlFor="custody-action">
          <Select id="custody-action" value={action} onChange={(e) => setAction(e.target.value as CustodyAction)}>
            {CUSTODY_ACTIONS.map((a) => (
              <option key={a} value={a}>
                {CUSTODY_ACTION_LABELS[a]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={action === "transferred" ? "To user (required)" : "To user (optional)"} htmlFor="custody-to">
          <Select id="custody-to" value={toUserId} onChange={(e) => setToUserId(e.target.value)}>
            <option value="">None</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {displayName(u)} ({ROLE_LABELS[u.role]})
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Notes" htmlFor="custody-notes">
          <Input
            id="custody-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Reason for the transfer…"
            maxLength={1000}
          />
        </Field>
        {error && (
          <p role="alert" className="rounded-md border border-danger-line bg-danger-bg px-3 py-2 text-sm text-danger-ink">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" type="button" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" loading={busy}>
            Record event
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function useEffectReset(open: boolean, item: Evidence, reset: () => void) {
  const wasOpen = useRef(false);
  const resetRef = useRef(reset);
  resetRef.current = reset;
  useEffect(() => {
    if (open && !wasOpen.current) resetRef.current();
    wasOpen.current = open;
  }, [open, item.id]);
}

function useEffectOpenUsers(open: boolean, setUsers: (u: User[]) => void) {
  useEffect(() => {
    if (!open) return;
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
  }, [open, setUsers]);
}

export function TimelineSpine({ entries }: { entries: TimelineEntry[] }) {
  if (entries.length === 0) {
    return <p className="py-2 text-sm text-ink3">No events yet.</p>;
  }
  return (
    <ol className="relative space-y-4 border-l border-line">
      {entries.map((entry, index) => (
        <li key={`${entry.occurred_at}-${index}`} className="relative pl-5">
          <span
            aria-hidden="true"
            className="absolute top-1 -left-[5px] h-2.5 w-2.5 rounded-full border-2 border-surface bg-ink3"
          />
          <p className="text-sm font-medium">{entry.title}</p>
          {entry.detail && <p className="mt-0.5 text-[13px] text-ink2">{entry.detail}</p>}
          <p className="mt-0.5 text-xs text-ink3">
            {entry.actor_username ?? "System"} · {timeAgo(entry.occurred_at)}
          </p>
        </li>
      ))}
    </ol>
  );
}
