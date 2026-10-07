// Reports: deterministic investigation reports from validated findings.
// Only accepted findings appear as validated. Print view uses the browser's
// print-to-PDF; no LLM is involved at any stage.

import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { FileText, Printer } from "lucide-react";
import { api } from "../api/client";
import type { Report } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Button } from "../components/Button";
import { Dialog } from "../components/Dialog";
import { EmptyState, ErrorState, Skeleton } from "../components/StateViews";
import { useToast } from "../components/Toast";
import { actionErrorMessage } from "../lib/errors";
import { formatDate } from "../lib/format";

export default function ReportsPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { notify } = useToast();
  const [reports, setReports] = useState<Report[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Report | null>(null);
  const [generating, setGenerating] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const invId = Number(id);
  const canGenerate =
    !!user && (user.role === "admin" || user.role === "investigator");

  const load = useCallback(async () => {
    try {
      setReports(await api.listReports(invId));
      setError(null);
    } catch (err) {
      setError(actionErrorMessage(err, "Could not load reports."));
    }
  }, [invId]);

  useEffect(() => {
    setReports(null);
    void load();
  }, [load]);

  async function onGenerate() {
    setGenerating(true);
    try {
      const report = await api.generateReport(invId);
      notify("success", `Report ${report.report_label ?? ""} generated from accepted findings.`);
      setConfirming(false);
      await load();
      setSelected(report);
    } catch (err) {
      notify("error", actionErrorMessage(err, "Could not generate the report."));
    } finally {
      setGenerating(false);
    }
  }

  if (error) return <ErrorState body={error} onRetry={() => void load()} />;
  if (reports === null) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-16" />
        <Skeleton className="h-16" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-ink2">
          Deterministic snapshots: overview, team, evidence, custody, accepted findings,
          recommendations, and notes. Rejected findings never appear as conclusions.
        </p>
        {canGenerate && (
          <Button variant="primary" size="sm" icon={<FileText size={14} />} onClick={() => setConfirming(true)}>
            Generate report
          </Button>
        )}
      </div>

      {reports.length === 0 ? (
        <EmptyState
          icon={<FileText size={22} />}
          title="No reports yet"
          body="Generate a report once findings have been reviewed and accepted. The report is a frozen snapshot with a content hash."
        />
      ) : (
        <ol className="space-y-2">
          {reports.map((report) => (
            <li key={report.id}>
              <button
                onClick={() => setSelected(report)}
                className="pv-transition w-full cursor-pointer rounded-md border border-line bg-surface px-4 py-3 text-left hover:bg-hover"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm font-semibold">
                    {report.report_label ?? `RPT-${report.report_number}`}
                  </span>
                  <span className="ml-auto text-xs text-ink3">
                    {formatDate(report.created_at)} · by {report.generated_by_username ?? "unknown"}
                  </span>
                </div>
                <p className="mt-0.5 font-mono text-xs break-all text-ink3">
                  sha256:{report.content_sha256.slice(0, 16)}...
                </p>
              </button>
            </li>
          ))}
        </ol>
      )}

      <Dialog
        open={confirming}
        onClose={() => setConfirming(false)}
        title="Generate report"
        description="Snapshots the current accepted findings, evidence, custody, and notes. Rejected and pending findings are excluded from conclusions."
      >
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirming(false)} disabled={generating}>
            Cancel
          </Button>
          <Button variant="primary" loading={generating} onClick={() => void onGenerate()}>
            Generate
          </Button>
        </div>
      </Dialog>

      <Dialog
        open={selected !== null}
        onClose={() => setSelected(null)}
        title={selected ? (selected.report_label ?? `RPT-${selected.report_number}`) : "Report"}
        description="Frozen snapshot. Use print to save as PDF."
        wide
      >
        {selected && <ReportView report={selected} />}
      </Dialog>
    </div>
  );
}

function ReportView({ report }: { report: Report }) {
  const content = report.content;
  return (
    <div>
      <div className="flex justify-end print:hidden">
        <Button variant="secondary" size="sm" icon={<Printer size={14} />} onClick={() => window.print()}>
          Print / save as PDF
        </Button>
      </div>
      <article className="prose-report mt-2 space-y-5 text-sm">
        <header>
          <p className="font-mono text-xs text-ink3">
            {report.report_label} · {content.generator} · {formatDate(report.created_at)}
          </p>
          <h3 className="mt-1 text-lg font-semibold">
            {content.investigation.case_number}: {content.investigation.title}
          </h3>
          <p className="mt-1 whitespace-pre-wrap text-ink2">{content.investigation.description}</p>
          <p className="mt-1 text-xs text-ink3">
            Status {content.investigation.status} · Priority {content.investigation.priority} · Lead{" "}
            {content.investigation.lead_investigator ?? "unknown"}
          </p>
        </header>

        <ReportSection title="Team">
          <ul className="list-disc pl-5">
            {content.investigation.team.map((member) => (
              <li key={member.username}>
                {member.full_name || member.username} ({member.username}, {member.role}
                {member.team_role === "lead" ? ", lead" : ""})
              </li>
            ))}
          </ul>
        </ReportSection>

        <ReportSection title={`Evidence summary (${content.evidence_summary.length} items)`}>
          <ul className="space-y-1.5">
            {content.evidence_summary.map((item) => (
              <li key={item.evidence_number}>
                <span className="font-mono text-xs">{item.evidence_number}</span> {item.title} ·{" "}
                {item.integrity_status} · <span className="font-mono text-xs">{item.sha256.slice(0, 16)}...</span>
              </li>
            ))}
            {content.evidence_summary.length === 0 && <li>No evidence registered.</li>}
          </ul>
        </ReportSection>

        <ReportSection title="Accepted findings">
          {content.accepted_findings.length === 0 ? (
            <p>No accepted findings at generation time.</p>
          ) : (
            <ol className="list-decimal space-y-3 pl-5">
              {content.accepted_findings.map((finding, index) => (
                <li key={index}>
                  <p className="font-medium">{finding.title}</p>
                  <p className="text-ink2">{finding.summary}</p>
                  <p className="text-xs text-ink3">
                    {finding.rule_id}-v{finding.rule_version} · {finding.severity} · confidence{" "}
                    {finding.confidence}/100 · reviewed by {finding.reviewer ?? "unknown"}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </ReportSection>

        {content.recommendations.length > 0 && (
          <ReportSection title="Recommendations and next actions">
            <ul className="list-disc pl-5">
              {content.recommendations.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </ReportSection>
        )}

        {content.investigator_notes.length > 0 && (
          <ReportSection title="Investigator notes">
            <ul className="space-y-1.5">
              {content.investigator_notes.map((note, index) => (
                <li key={index}>
                  {note.body}
                  <span className="block text-xs text-ink3">
                    {note.author ?? "Unknown"}
                    {note.finding_id ? ` · on finding #${note.finding_id}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </ReportSection>
        )}

        <ReportSection title="Traceability">
          <p className="font-mono text-xs break-all">sha256:{report.content_sha256}</p>
          <p className="text-xs text-ink3">
            Generated by {content.generated_by} at {formatDate(content.generated_at)} from
            validated structured data only. No generative model was involved.
          </p>
        </ReportSection>
      </article>
    </div>
  );
}

function ReportSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h4 className="border-b border-line pb-1 text-xs font-semibold tracking-wide uppercase">
        {title}
      </h4>
      <div className="mt-2">{children}</div>
    </section>
  );
}
