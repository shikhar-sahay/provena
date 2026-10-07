// Investigator dashboard: live caseload context from the summary endpoint.
// Every figure derives from records the user may see; nothing is fabricated.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, FileSearch, FlaskConical, FolderKanban, Inbox } from "lucide-react";
import { api } from "../api/client";
import type { DashboardSummary, Investigation } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/Badge";
import { Button } from "../components/Button";
import { NewInvestigationDialog } from "../components/NewInvestigationDialog";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "../components/StateViews";
import { actionErrorMessage } from "../lib/errors";
import { actionLabel } from "../lib/activity";
import { displayName, timeAgo } from "../lib/format";

export default function DashboardPage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [recent, setRecent] = useState<Investigation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const canCreate = user?.role === "admin" || user?.role === "investigator";

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.dashboardSummary(), api.listInvestigations()])
      .then(([data, investigations]) => {
        if (cancelled) return;
        setSummary(data);
        setRecent(
          [...investigations]
            .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
            .slice(0, 5),
        );
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(actionErrorMessage(err, "Could not load the dashboard."));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="space-y-4">
        <PageHeader title={`Welcome back${user ? `, ${displayName(user)}` : ""}`} />
        <ErrorState body={error} onRetry={() => window.location.reload()} />
      </div>
    );
  }

  if (!summary || !recent) {
    return (
      <div className="space-y-4">
        <PageHeader title="Dashboard" />
        <div className="grid gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
        <Skeleton className="h-48" />
      </div>
    );
  }

  const needsReview = summary.by_status["under_review"] ?? 0;
  const active = summary.open_investigations.length;

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome back${user ? `, ${displayName(user)}` : ""}`}
        description="What needs your attention across the investigations you can access."
      />

      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-line bg-line sm:grid-cols-4">
        <Stat label="Active investigations" value={active} />
        <Stat label="Needs review" value={needsReview} tone={needsReview > 0 ? "warning" : undefined} />
        <Stat label="Evidence items" value={summary.evidence_total} />
        <Stat
          label="Integrity issues"
          value={summary.integrity_issues}
          tone={summary.integrity_issues > 0 ? "danger" : undefined}
        />
      </dl>

      {summary.integrity_issues > 0 && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-md border border-danger-line bg-danger-bg px-3 py-2 text-sm text-danger-ink"
        >
          <AlertTriangle size={15} className="mt-0.5 shrink-0" />
          {summary.integrity_issues === 1
            ? "One evidence item needs attention: its stored bytes do not match the baseline, or it cannot be read."
            : `${summary.integrity_issues} evidence items need attention: stored bytes do not match baselines, or files cannot be read.`}
        </p>
      )}

      {(summary.pending_analysis > 0 || summary.findings_pending_review > 0) && (
        <section aria-label="Needs attention" className="rounded-md border border-line bg-surface">
          <ul className="divide-y divide-line">
            {summary.pending_analysis > 0 && (
              <li>
                <Link
                  to="/investigations"
                  className="pv-transition flex items-center gap-2.5 px-4 py-2.5 hover:bg-hover"
                >
                  <FlaskConical size={15} className="shrink-0 text-info-ink" />
                  <span className="text-sm">
                    <span className="font-semibold tabular-nums">{summary.pending_analysis}</span>{" "}
                    verified evidence{" "}
                    {summary.pending_analysis === 1 ? "item awaits" : "items await"} analysis
                  </span>
                </Link>
              </li>
            )}
            {summary.findings_pending_review > 0 && (
              <li>
                <Link
                  to="/findings?status=pending_review"
                  className="pv-transition flex items-center gap-2.5 px-4 py-2.5 hover:bg-hover"
                >
                  <Inbox size={15} className="shrink-0 text-warning-ink" />
                  <span className="text-sm">
                    <span className="font-semibold tabular-nums">{summary.findings_pending_review}</span>{" "}
                    {summary.findings_pending_review === 1 ? "finding awaits" : "findings await"}{" "}
                    investigator review
                  </span>
                </Link>
              </li>
            )}
          </ul>
        </section>
      )}

      {summary.last_analysis && (
        <p className="text-[13px] text-ink3">
          Last analysis:{" "}
          <Link
            to={`/investigations/${summary.last_analysis.investigation_id}/analysis`}
            className="font-mono text-accentink hover:underline"
          >
            {summary.last_analysis.run_label}
          </Link>{" "}
          · {summary.last_analysis.investigation_title} · {summary.last_analysis.status} ·{" "}
          {summary.last_analysis.artifact_count} artifacts,{" "}
          {summary.last_analysis.correlation_count} correlations
          {summary.last_analysis.completed_at
            ? ` · ${timeAgo(summary.last_analysis.completed_at)}`
            : ""}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="overflow-hidden rounded-md border border-line bg-surface">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <h2 className="text-sm font-semibold">Recent investigations</h2>
            <Link to="/investigations" className="text-[13px] font-medium text-accentink hover:underline">
              View all
            </Link>
          </div>
          {recent.length === 0 ? (
            <div className="p-4">
              <EmptyState
                icon={<FolderKanban size={22} />}
                title="No investigations yet"
                body="An investigation tracks a case, its team, its evidence, and its custody from open to archive."
                action={
                  canCreate ? (
                    <Button variant="primary" size="sm" onClick={() => setCreating(true)}>
                      Create your first investigation
                    </Button>
                  ) : undefined
                }
              />
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {recent.map((inv) => (
                <li key={inv.id}>
                  <Link
                    to={`/investigations/${inv.id}`}
                    className="pv-transition flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-hover"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">{inv.title}</span>
                      <span className="block font-mono text-xs text-ink3">
                        {inv.case_number} · updated {timeAgo(inv.updated_at)}
                      </span>
                    </span>
                    <StatusBadge status={inv.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="overflow-hidden rounded-md border border-line bg-surface">
          <div className="border-b border-line px-4 py-2.5">
            <h2 className="text-sm font-semibold">Recent activity</h2>
          </div>
          {summary.recent_activity.length === 0 ? (
            <div className="p-4">
              <EmptyState
                icon={<FileSearch size={22} />}
                title="No activity yet"
                body="Actions on your investigations, evidence, and custody will appear here."
              />
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {summary.recent_activity.slice(0, 8).map((entry) => (
                <li key={entry.id} className="px-4 py-2 text-sm">
                  <p className="text-ink">
                    {actionLabel(entry.action)}
                    {entry.evidence_number && (
                      <span className="ml-1.5 font-mono text-xs text-ink3">{entry.evidence_number}</span>
                    )}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-ink3">
                    <Link
                      to={`/investigations/${entry.investigation_id}`}
                      className="hover:text-ink2 hover:underline"
                    >
                      {entry.investigation_title}
                    </Link>
                    {" · "}
                    {entry.actor_username ?? "System"} · {timeAgo(entry.created_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <NewInvestigationDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "warning" | "danger";
}) {
  const valueClass =
    tone === "danger" ? "text-danger-ink" : tone === "warning" ? "text-warning-ink" : "text-ink";
  return (
    <div className="bg-surface px-4 py-3">
      <dt className="text-[13px] text-ink2">{label}</dt>
      <dd className={`mt-0.5 text-2xl font-semibold tracking-tight tabular-nums ${valueClass}`}>
        {value}
      </dd>
    </div>
  );
}
