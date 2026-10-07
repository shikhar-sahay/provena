// Findings tab: rule proposals with full Why provenance, human validation,
// and investigator notes. Nothing is auto-validated.

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { FileSearch, MessageSquarePlus } from "lucide-react";
import { api } from "../api/client";
import type { Finding, Investigation, Note } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Drawer } from "../components/Dialog";
import { Field, Textarea } from "../components/Field";
import { EmptyState, ErrorState, Skeleton } from "../components/StateViews";
import { useToast } from "../components/Toast";
import { FINDING_STATUS_LABELS, severityTone } from "../lib/analysis";
import { actionErrorMessage } from "../lib/errors";
import { displayName, formatDate, timeAgo } from "../lib/format";

export default function FindingsTab({
  invId,
  inv,
  onChanged,
}: {
  invId: number;
  inv: Investigation;
  onChanged: () => void;
}) {
  const { user } = useAuth();
  const { notify } = useToast();
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [selected, setSelected] = useState<Finding | null>(null);

  const canValidate =
    !!user &&
    (user.role === "admin" ||
      user.id === inv.created_by.id ||
      user.id === inv.lead_investigator.id);
  const archivedLocked = inv.status === "archived" && user?.role !== "admin";

  const load = useCallback(async () => {
    try {
      setFindings(await api.listFindings(invId));
      setError(null);
    } catch (err) {
      setError(actionErrorMessage(err, "Could not load findings."));
    }
  }, [invId]);

  useEffect(() => {
    setFindings(null);
    void load();
  }, [load]);

  async function onGenerate() {
    setGenerating(true);
    try {
      const result = await api.generateFindings(invId);
      notify(
        "success",
        result.new_count === 0
          ? "Rules evaluated. No new findings."
          : `Rules evaluated. ${result.new_count} new finding${result.new_count === 1 ? "" : "s"}.`,
      );
      await load();
      onChanged();
    } catch (err) {
      notify("error", actionErrorMessage(err, "Could not generate findings."));
    } finally {
      setGenerating(false);
    }
  }

  if (error) return <ErrorState body={error} onRetry={() => void load()} />;
  if (findings === null) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-ink2">
          Deterministic rule proposals over extracted artifacts. Validation is human-only.
        </p>
        <Button variant="primary" size="sm" loading={generating} onClick={() => void onGenerate()}>
          Evaluate rules
        </Button>
      </div>

      {findings.length === 0 ? (
        <EmptyState
          icon={<FileSearch size={22} />}
          title="No findings yet"
          body="Evaluate the rule set against current artifacts and correlations. Rules surface patterns with confidence factors; investigators decide what they mean."
        />
      ) : (
        <ol className="space-y-3">
          {findings.map((finding) => (
            <li key={finding.id} className="rounded-md border border-line bg-surface px-4 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => setSelected(finding)}
                  className="min-w-0 flex-1 cursor-pointer text-left"
                >
                  <span className="block truncate text-sm font-semibold hover:underline">
                    {finding.title}
                  </span>
                </button>
                <Badge tone={severityTone(finding.severity)}>{finding.severity}</Badge>
                <Badge
                  tone={
                    finding.status === "accepted"
                      ? "success"
                      : finding.status === "rejected"
                        ? "danger"
                        : "warning"
                  }
                >
                  {FINDING_STATUS_LABELS[finding.status]}
                </Badge>
                <span className="text-xs tabular-nums text-ink2" title="Deterministic weighted score for ranking, not a probability">
                  {finding.confidence}/100
                </span>
              </div>
              <p className="mt-1 line-clamp-2 text-[13px] text-ink2">{finding.summary}</p>
              <p className="mt-1 text-xs text-ink3">
                {finding.rule_id}-v{finding.rule_version} ·{" "}
                {finding.reviewer_username
                  ? `reviewed by ${finding.reviewer_username}`
                  : "awaiting review"}{" "}
                · {timeAgo(finding.updated_at)}
              </p>
            </li>
          ))}
        </ol>
      )}

      <Drawer
        open={selected !== null}
        onClose={() => setSelected(null)}
        title={selected?.title ?? "Finding"}
        description="Why this was proposed, and human validation."
      >
        {selected && (
          <FindingDetail
            invId={invId}
            finding={selected}
            canValidate={canValidate && !archivedLocked}
            onChanged={(updated) => {
              setSelected(updated);
              void load();
              onChanged();
            }}
          />
        )}
      </Drawer>
    </div>
  );
}

function FindingDetail({
  invId,
  finding,
  canValidate,
  onChanged,
}: {
  invId: number;
  finding: Finding;
  canValidate: boolean;
  onChanged: (finding: Finding) => void;
}) {
  const { notify } = useToast();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [noteBody, setNoteBody] = useState("");
  const [noteBusy, setNoteBusy] = useState(false);

  useEffectLoadNotes(invId, finding.id, setNotes);

  async function review(status: "accepted" | "rejected") {
    setBusy(true);
    try {
      const updated = await api.reviewFinding(
        invId,
        finding.id,
        status,
        note.trim() || undefined,
      );
      notify("success", status === "accepted" ? "Finding accepted." : "Finding rejected.");
      setNote("");
      onChanged(updated);
    } catch (err) {
      notify("error", actionErrorMessage(err, "Could not record the review."));
    } finally {
      setBusy(false);
    }
  }

  async function addNote(event: FormEvent) {
    event.preventDefault();
    if (!noteBody.trim()) return;
    setNoteBusy(true);
    try {
      await api.createNote(invId, noteBody.trim(), finding.id);
      setNoteBody("");
      const updated = await api.listNotes(invId, finding.id);
      setNotes(updated);
      notify("success", "Note added.");
    } catch (err) {
      notify("error", actionErrorMessage(err, "Could not add the note."));
    } finally {
      setNoteBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={severityTone(finding.severity)}>{finding.severity}</Badge>
        <Badge
          tone={
            finding.status === "accepted"
              ? "success"
              : finding.status === "rejected"
                ? "danger"
                : "warning"
          }
        >
          {FINDING_STATUS_LABELS[finding.status]}
        </Badge>
        <span className="text-sm tabular-nums" title="Deterministic weighted score for ranking, not a probability">
          Confidence {finding.confidence}/100
        </span>
      </div>

      <p className="text-sm">{finding.summary}</p>

      <section>
        <h3 className="text-xs font-semibold tracking-wide text-ink2 uppercase">Why this was proposed</h3>
        <p className="mt-1 text-[13px] text-ink2">
          Rule <span className="font-mono">{finding.rule_id}</span>-v{finding.rule_version}
        </p>
        <ol className="mt-2 space-y-1.5">
          {finding.factors.map((factor, index) => (
            <li
              key={index}
              className="flex items-baseline justify-between gap-3 rounded-md border border-line px-2.5 py-1.5 text-[13px]"
            >
              <span>
                <span className="font-medium">{factor.factor}</span>
                <span className="block text-xs text-ink3">{factor.detail}</span>
              </span>
              <span className="shrink-0 tabular-nums text-ink2">+{factor.weight}</span>
            </li>
          ))}
        </ol>
        <p className="mt-1.5 text-xs text-ink3">
          Weights sum to the confidence score. Deterministic ranking, not a calibrated probability.
        </p>
      </section>

      <section>
        <h3 className="text-xs font-semibold tracking-wide text-ink2 uppercase">Supporting references</h3>
        <p className="mt-1 text-[13px] text-ink2">
          Evidence:{" "}
          {finding.evidence_ids.length === 0
            ? "none recorded"
            : finding.evidence_ids.map((id) => (
                <Link
                  key={id}
                  to={`/investigations/${invId}/evidence/${id}`}
                  className="mr-1.5 font-mono text-accentink hover:underline"
                >
                  #{id}
                </Link>
              ))}
        </p>
        <p className="mt-0.5 text-[13px] text-ink2">
          {finding.artifact_ids.length} artifacts · {finding.correlation_ids.length} correlations
          referenced. Inspect them under Artifacts and Correlations.
        </p>
      </section>

      {finding.recommendations.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold tracking-wide text-ink2 uppercase">
            Recommended next actions
          </h3>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[13px]">
            {finding.recommendations.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </section>
      )}

      {finding.status !== "pending_review" && (
        <section className="rounded-md border border-line bg-canvas px-3 py-2 text-[13px]">
          <p>
            <span className="font-medium">{FINDING_STATUS_LABELS[finding.status]}</span>
            {finding.reviewer_username && <> by {displayName({ full_name: "", username: finding.reviewer_username })}</>}{" "}
            {finding.reviewed_at && <>· {formatDate(finding.reviewed_at)}</>}
          </p>
          {finding.review_note && <p className="mt-0.5 text-ink2">{finding.review_note}</p>}
        </section>
      )}

      {canValidate && finding.status === "pending_review" && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
          }}
          className="space-y-3 rounded-md border border-line p-3"
        >
          <Field label="Review note (optional)" htmlFor="finding-review-note">
            <Textarea
              id="finding-review-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Why this holds or falls apart…"
            />
          </Field>
          <div className="flex gap-2">
            <Button variant="primary" loading={busy} onClick={() => void review("accepted")}>
              Accept finding
            </Button>
            <Button variant="danger" loading={busy} onClick={() => void review("rejected")}>
              Reject
            </Button>
          </div>
        </form>
      )}
      {canValidate && finding.status !== "pending_review" && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
          }}
          className="space-y-3 rounded-md border border-line p-3"
        >
          <Field label="Change review (optional note)" htmlFor="finding-rereview-note">
            <Textarea
              id="finding-rereview-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Reason for changing the decision…"
            />
          </Field>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              loading={busy}
              onClick={() => void review(finding.status === "accepted" ? "rejected" : "accepted")}
            >
              {finding.status === "accepted" ? "Move back to rejected" : "Move back to accepted"}
            </Button>
          </div>
        </form>
      )}

      <section>
        <h3 className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-ink2 uppercase">
          <MessageSquarePlus size={13} /> Investigator notes
        </h3>
        {!notes ? (
          <p className="mt-1.5 text-[13px] text-ink3">Loading notes…</p>
        ) : notes.length === 0 ? (
          <p className="mt-1.5 text-[13px] text-ink3">No notes on this finding yet.</p>
        ) : (
          <ol className="mt-1.5 space-y-2">
            {notes.map((entry) => (
              <li key={entry.id} className="rounded-md border border-line px-2.5 py-2 text-[13px]">
                <p>{entry.body}</p>
                <p className="mt-0.5 text-xs text-ink3">
                  {entry.author_username ?? "Unknown"} · {formatDate(entry.created_at)}
                </p>
              </li>
            ))}
          </ol>
        )}
        <form onSubmit={(e) => void addNote(e)} className="mt-2 flex gap-2">
          <Textarea
            aria-label="Add a note on this finding"
            value={noteBody}
            onChange={(e) => setNoteBody(e.target.value)}
            placeholder="Add human context…"
            className="min-h-10"
          />
          <Button variant="secondary" type="submit" loading={noteBusy}>
            Add
          </Button>
        </form>
      </section>
    </div>
  );
}

function useEffectLoadNotes(
  invId: number,
  findingId: number,
  setNotes: (notes: Note[] | null) => void,
) {
  useEffect(() => {
    let cancelled = false;
    setNotes(null);
    api
      .listNotes(invId, findingId)
      .then((data) => {
        if (!cancelled) setNotes(data);
      })
      .catch(() => {
        if (!cancelled) setNotes([]);
      });
    return () => {
      cancelled = true;
    };
  }, [invId, findingId, setNotes]);
}
