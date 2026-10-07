// Findings workspace: cross-investigation triage, rule proposals, and human validation.

import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, ChevronRight, FileSearch, XCircle } from "lucide-react";
import { api } from "../api/client";
import type { Finding, FindingStatus } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Drawer } from "../components/Dialog";
import { Field, Input, Select, Textarea } from "../components/Field";
import { EmptyState, ErrorState, Skeleton } from "../components/StateViews";
import { useToast } from "../components/Toast";
import { FINDING_STATUS_LABELS, severityTone } from "../lib/analysis";
import { actionErrorMessage } from "../lib/errors";
import { formatDate } from "../lib/format";

export default function FindingsWorkspacePage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Finding | null>(null);

  // Filters
  const statusParam = searchParams.get("status") || "all";
  const [statusFilter, setStatusFilter] = useState<string>(statusParam);
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Bulk selection
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkNote, setBulkNote] = useState("");

  const canReview = user?.role === "admin" || user?.role === "investigator";

  const loadFindings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listGlobalFindings({
        status: statusFilter !== "all" ? (statusFilter as FindingStatus) : undefined,
        severity: severityFilter !== "all" ? severityFilter : undefined,
        q: searchQuery.trim() || undefined,
      });
      setFindings(data);
      setError(null);
      setSelectedIds(new Set());
    } catch (err) {
      setError(actionErrorMessage(err, "Could not load findings."));
    } finally {
      setLoading(false);
    }
  }, [statusFilter, severityFilter, searchQuery]);

  useEffect(() => {
    const param = searchParams.get("status") || "all";
    setStatusFilter(param);
  }, [searchParams]);

  useEffect(() => {
    void loadFindings();
  }, [loadFindings]);

  function handleStatusChange(status: string) {
    setStatusFilter(status);
    if (status === "all") {
      searchParams.delete("status");
    } else {
      searchParams.set("status", status);
    }
    setSearchParams(searchParams);
  }

  const filteredFindings = (findings ?? []).filter((f) => {
    if (severityFilter !== "all" && f.severity !== severityFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const match =
        f.title.toLowerCase().includes(q) ||
        f.summary.toLowerCase().includes(q) ||
        f.rule_id.toLowerCase().includes(q) ||
        (f.investigation_title && f.investigation_title.toLowerCase().includes(q)) ||
        (f.investigation_case_number && f.investigation_case_number.toLowerCase().includes(q));
      if (!match) return false;
    }
    return true;
  });

  const pendingFindings = filteredFindings.filter((f) => f.status === "pending_review");

  function toggleSelectAllPending() {
    if (selectedIds.size === pendingFindings.length && pendingFindings.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(pendingFindings.map((f) => f.id)));
    }
  }

  function toggleSelectFinding(id: number) {
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setSelectedIds(next);
  }

  async function handleBulkReview(status: "accepted" | "rejected") {
    if (selectedIds.size === 0) return;
    setBulkBusy(true);
    try {
      const result = await api.bulkReviewGlobalFindings({
        finding_ids: Array.from(selectedIds),
        status,
        note: bulkNote.trim() || undefined,
      });
      notify(
        "success",
        `Reviewed ${result.count} finding${result.count === 1 ? "" : "s"} as ${status}.`,
      );
      setBulkNote("");
      setSelectedIds(new Set());
      await loadFindings();
    } catch (err) {
      notify("error", actionErrorMessage(err, "Failed to bulk review findings."));
    } finally {
      setBulkBusy(false);
    }
  }

  async function handleIndividualReview(finding: Finding, status: "accepted" | "rejected", note?: string) {
    try {
      const updated = await api.reviewFinding(finding.investigation_id, finding.id, status, note);
      notify("success", `Finding marked as ${status}.`);
      setSelected(updated);
      await loadFindings();
    } catch (err) {
      notify("error", actionErrorMessage(err, "Failed to review finding."));
    }
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-ink">Findings</h1>
          <p className="mt-0.5 text-sm text-ink2">
            Cross-investigation finding curation and human review. Deterministic rule proposals with explainable provenance.
          </p>
        </div>
      </div>

      {/* Filters bar */}
      <div className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          {/* Status Tabs */}
          <div className="inline-flex rounded-md border border-line bg-canvas p-0.5 text-xs">
            {[
              { id: "all", label: "All" },
              { id: "pending_review", label: "Pending" },
              { id: "accepted", label: "Accepted" },
              { id: "rejected", label: "Rejected" },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => handleStatusChange(tab.id)}
                className={`rounded px-2.5 py-1 font-medium transition-colors ${
                  statusFilter === tab.id
                    ? "bg-surface text-ink shadow-xs"
                    : "text-ink3 hover:text-ink"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Severity Dropdown */}
          <div className="w-32">
            <Select
              aria-label="Filter by severity"
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
            >
              <option value="all">All severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </Select>
          </div>
        </div>

        {/* Search input */}
        <div className="w-full sm:w-64">
          <Input
            type="search"
            aria-label="Search findings"
            placeholder="Search findings or rules..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Bulk Action Banner */}
      {canReview && pendingFindings.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-line bg-canvas px-4 py-2.5 text-sm">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="select-all-pending"
              aria-label="Select all pending findings"
              checked={selectedIds.size === pendingFindings.length && pendingFindings.length > 0}
              onChange={toggleSelectAllPending}
              className="h-4 w-4 rounded border-line text-accent"
            />
            <label htmlFor="select-all-pending" className="cursor-pointer text-xs font-medium text-ink2">
              Select all pending ({selectedIds.size} of {pendingFindings.length} selected)
            </label>
          </div>

          {selectedIds.size > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                aria-label="Bulk review note"
                placeholder="Optional review note..."
                value={bulkNote}
                onChange={(e) => setBulkNote(e.target.value)}
                className="h-7 w-48 rounded border border-line bg-surface px-2 text-xs text-ink placeholder:text-ink3"
              />
              <Button
                variant="primary"
                size="sm"
                loading={bulkBusy}
                icon={<CheckCircle2 size={13} />}
                onClick={() => void handleBulkReview("accepted")}
              >
                Accept ({selectedIds.size})
              </Button>
              <Button
                variant="danger"
                size="sm"
                loading={bulkBusy}
                icon={<XCircle size={13} />}
                onClick={() => void handleBulkReview("rejected")}
              >
                Reject ({selectedIds.size})
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Findings Content */}
      {error && <ErrorState body={error} onRetry={() => void loadFindings()} />}

      {loading && findings === null && (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {findings !== null && filteredFindings.length === 0 && (
        <EmptyState
          icon={<FileSearch size={24} />}
          title="No findings found"
          body={
            statusFilter !== "all" || severityFilter !== "all" || searchQuery
              ? "No findings match the current filter criteria."
              : "No findings have been generated across authorized investigations yet."
          }
        />
      )}

      {findings !== null && filteredFindings.length > 0 && (
        <div className="space-y-3">
          {filteredFindings.map((finding) => {
            const isPending = finding.status === "pending_review";
            const isSelected = selectedIds.has(finding.id);

            return (
              <div
                key={finding.id}
                className={`group relative flex flex-col justify-between gap-3 rounded-lg border bg-surface p-4 transition-all hover:border-linestrong sm:flex-row sm:items-center ${
                  isSelected ? "border-accent ring-1 ring-accent" : "border-line"
                }`}
              >
                <div className="flex items-start gap-3 min-w-0 flex-1">
                  {canReview && isPending && (
                    <input
                      type="checkbox"
                      aria-label={`Select finding ${finding.title}`}
                      checked={isSelected}
                      onChange={() => toggleSelectFinding(finding.id)}
                      className="mt-1 h-4 w-4 shrink-0 rounded border-line text-accent"
                    />
                  )}

                  <div className="min-w-0 flex-1">
                    {/* Investigation context link */}
                    <div className="flex items-center gap-1.5 text-xs text-ink3 mb-1">
                      <Link
                        to={`/investigations/${finding.investigation_id}/analysis`}
                        className="font-medium text-ink2 hover:text-ink hover:underline"
                      >
                        {finding.investigation_case_number || `Case #${finding.investigation_id}`}
                      </Link>
                      {finding.investigation_title && (
                        <>
                          <span>·</span>
                          <span className="truncate">{finding.investigation_title}</span>
                        </>
                      )}
                    </div>

                    {/* Finding title and detail trigger */}
                    <button
                      type="button"
                      onClick={() => setSelected(finding)}
                      className="cursor-pointer text-left focus:outline-none"
                    >
                      <span className="text-sm font-semibold text-ink group-hover:text-accent">
                        {finding.title}
                      </span>
                    </button>

                    <p className="mt-1 line-clamp-2 text-xs text-ink2 leading-relaxed">
                      {finding.summary}
                    </p>

                    {/* Meta tags and provenance info */}
                    <div className="mt-2.5 flex flex-wrap items-center gap-2 text-[11px] text-ink3">
                      <span className="font-mono">Rule {finding.rule_id}</span>
                      <span>·</span>
                      <span>{finding.factors.length} factors</span>
                      <span>·</span>
                      <span>{finding.evidence_ids.length} evidence references</span>
                      {finding.reviewer_username && (
                        <>
                          <span>·</span>
                          <span>
                            Reviewed by {finding.reviewer_username}
                            {finding.reviewed_at && ` on ${formatDate(finding.reviewed_at)}`}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right badges & trigger */}
                <div className="flex shrink-0 items-center gap-2 self-end sm:self-center">
                  <Badge tone={severityTone(finding.severity)}>{finding.severity}</Badge>
                  <Badge
                    tone={
                      finding.status === "accepted"
                        ? "success"
                        : finding.status === "rejected"
                          ? "neutral"
                          : "warning"
                    }
                  >
                    {FINDING_STATUS_LABELS[finding.status]}
                  </Badge>
                  <span className="rounded border border-line px-1.5 py-0.5 font-mono text-[11px] tabular-nums text-ink2">
                    {finding.confidence}/100
                  </span>
                  <button
                    type="button"
                    onClick={() => setSelected(finding)}
                    aria-label={`View details for ${finding.title}`}
                    className="pv-transition cursor-pointer rounded p-1 text-ink3 hover:bg-hover hover:text-ink"
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Finding Detail Drawer */}
      {selected && (
        <Drawer
          title={selected.title}
          open={!!selected}
          onClose={() => setSelected(null)}
        >
          <FindingDetailWorkspaceView
            finding={selected}
            canReview={canReview}
            onReview={(status, note) => void handleIndividualReview(selected, status, note)}
          />
        </Drawer>
      )}
    </div>
  );
}

function FindingDetailWorkspaceView({
  finding,
  canReview,
  onReview,
}: {
  finding: Finding;
  canReview: boolean;
  onReview: (status: "accepted" | "rejected", note?: string) => void;
}) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  async function submitReview(status: "accepted" | "rejected") {
    setBusy(true);
    try {
      await onReview(status, note.trim() || undefined);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Badges and metadata */}
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={severityTone(finding.severity)}>{finding.severity}</Badge>
        <Badge
          tone={
            finding.status === "accepted"
              ? "success"
              : finding.status === "rejected"
                ? "neutral"
                : "warning"
          }
        >
          {FINDING_STATUS_LABELS[finding.status]}
        </Badge>
        <span className="rounded border border-line px-2 py-0.5 font-mono text-xs text-ink2">
          Confidence {finding.confidence}/100
        </span>
      </div>

      {/* Investigation banner */}
      <div className="rounded-md border border-line bg-canvas p-3 text-xs">
        <p className="font-medium text-ink">Investigation Details</p>
        <p className="mt-0.5 text-ink2">
          {finding.investigation_case_number} · {finding.investigation_title}
        </p>
        <Link
          to={`/investigations/${finding.investigation_id}/analysis`}
          className="mt-1.5 inline-block text-accent hover:underline font-medium"
        >
          Open investigation workspace →
        </Link>
      </div>

      {/* Summary */}
      <section>
        <h3 className="text-xs font-semibold tracking-wide text-ink2 uppercase">Summary</h3>
        <p className="mt-1.5 text-sm text-ink leading-relaxed">{finding.summary}</p>
      </section>

      {/* Why & Confidence Provenance */}
      <section>
        <h3 className="text-xs font-semibold tracking-wide text-ink2 uppercase">
          Why this was flagged (rule factors)
        </h3>
        <p className="mt-1 text-xs text-ink3 font-mono">
          Rule: {finding.rule_id} (version {finding.rule_version})
        </p>
        <ol className="mt-2 space-y-1.5">
          {finding.factors.map((factor, idx) => (
            <li
              key={idx}
              className="flex items-baseline justify-between gap-3 rounded-md border border-line bg-surface px-3 py-2 text-xs"
            >
              <div>
                <span className="font-medium text-ink">{factor.factor}</span>
                <span className="block text-ink3 mt-0.5">{factor.detail}</span>
              </div>
              <span className="shrink-0 font-mono text-ink2 tabular-nums">+{factor.weight}</span>
            </li>
          ))}
        </ol>
        <p className="mt-2 text-xs text-ink3">
          Factors are deterministically weighted. Confidence is not a probabilistic score.
        </p>
      </section>

      {/* Supporting References */}
      <section>
        <h3 className="text-xs font-semibold tracking-wide text-ink2 uppercase">Supporting References</h3>
        <div className="mt-1.5 text-xs text-ink2 space-y-1">
          <p>
            Evidence items:{" "}
            {finding.evidence_ids.length === 0
              ? "None recorded"
              : finding.evidence_ids.map((id) => (
                  <Link
                    key={id}
                    to={`/investigations/${finding.investigation_id}/evidence/${id}`}
                    className="mr-2 font-mono text-accent hover:underline"
                  >
                    #{id}
                  </Link>
                ))}
          </p>
          <p>
            {finding.artifact_ids.length} extracted artifacts and {finding.correlation_ids.length} correlations.
          </p>
        </div>
      </section>

      {/* Recommendations */}
      {finding.recommendations.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold tracking-wide text-ink2 uppercase">
            Recommended Next Actions
          </h3>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-xs text-ink leading-relaxed">
            {finding.recommendations.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        </section>
      )}

      {/* Current Review status info */}
      {finding.status !== "pending_review" && (
        <section className="rounded-md border border-line bg-canvas p-3 text-xs">
          <p className="font-medium text-ink">
            Status: {FINDING_STATUS_LABELS[finding.status]}
            {finding.reviewer_username && ` by ${finding.reviewer_username}`}
            {finding.reviewed_at && ` on ${formatDate(finding.reviewed_at)}`}
          </p>
          {finding.review_note && (
            <p className="mt-1 text-ink2 italic">Note: {finding.review_note}</p>
          )}
        </section>
      )}

      {/* Review Actions Form */}
      {canReview && (
        <div className="space-y-3 rounded-md border border-line bg-surface p-4">
          <Field
            label={finding.status === "pending_review" ? "Review note (optional)" : "Update review note"}
            htmlFor="workspace-finding-review-note"
          >
            <Textarea
              id="workspace-finding-review-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Rationale for accepting or rejecting this finding..."
            />
          </Field>
          <div className="flex gap-2">
            <Button
              variant="primary"
              loading={busy}
              icon={<CheckCircle2 size={14} />}
              onClick={() => void submitReview("accepted")}
            >
              Accept finding
            </Button>
            <Button
              variant="danger"
              loading={busy}
              icon={<XCircle size={14} />}
              onClick={() => void submitReview("rejected")}
            >
              Reject finding
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
