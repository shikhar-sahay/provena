// AI Analysis workspace: deterministic extraction and shared-value
// correlation over verified evidence. Overview, Artifacts, Correlations, and
// Findings are functional. Nothing here infers guilt or intent.

import { useCallback, useEffect, useRef, useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { FlaskConical, Play } from "lucide-react";
import { api } from "../api/client";
import type { AnalysisRun, EligibilityEntry } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Dialog } from "../components/Dialog";
import { EmptyState, ErrorState, Skeleton } from "../components/StateViews";
import { useToast } from "../components/Toast";
import { actionErrorMessage } from "../lib/errors";
import { RUN_EVIDENCE_LABELS, RUN_STATUS_LABELS } from "../lib/analysis";
import { formatDate, timeAgo } from "../lib/format";
import type { WorkspaceContext } from "./InvestigationWorkspace";
import ArtifactsTab from "./ArtifactsTab";
import CorrelationsTab from "./CorrelationsTab";
import FindingsTab from "./FindingsTab";

type SubTab = "overview" | "artifacts" | "correlations" | "findings";

export default function AnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const { inv } = useOutletContext<WorkspaceContext>();
  const { user } = useAuth();
  const [tab, setTab] = useState<SubTab>("overview");
  const [runs, setRuns] = useState<AnalysisRun[] | null>(null);
  const [eligibility, setEligibility] = useState<EligibilityEntry[] | null>(null);
  const [artifactTotal, setArtifactTotal] = useState<number | null>(null);
  const [correlationTotal, setCorrelationTotal] = useState<number | null>(null);
  const [findingTotal, setFindingTotal] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const invId = Number(id);
  const canInitiate =
    !!user &&
    (user.role === "admin" ||
      user.role === "investigator" ||
      user.role === "forensic_analyst");

  const load = useCallback(async () => {
    try {
      const [runList, elig, artifacts, correlations, findings] = await Promise.all([
        api.listAnalysisRuns(invId),
        api.analysisEligibility(invId),
        api.listArtifacts(invId, { limit: 1 }),
        api.listCorrelations(invId),
        api.listFindings(invId),
      ]);
      setRuns(runList);
      setEligibility(elig);
      setArtifactTotal(artifacts.total);
      setCorrelationTotal(correlations.length);
      setFindingTotal(findings.length);
      setError(null);
    } catch (err) {
      setError(actionErrorMessage(err, "Could not load analysis state."));
    }
  }, [invId]);

  useEffect(() => {
    setRuns(null);
    void load();
  }, [load]);

  if (error) return <ErrorState body={error} onRetry={() => void load()} />;
  if (!runs || !eligibility || artifactTotal === null || correlationTotal === null || findingTotal === null) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-24" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  const eligible = eligibility.filter((e) => e.eligible);
  const blocked = eligibility.filter((e) => !e.eligible);
  const lastRun = runs[0] ?? null;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div
          role="tablist"
          aria-label="Analysis sections"
          className="flex gap-0.5 overflow-x-auto text-sm"
        >
          {(
            [
              ["overview", "Overview"],
              ["artifacts", "Artifacts"],
              ["correlations", "Correlations"],
              ["findings", "Findings"],
            ] as [SubTab, string][]
          ).map(([value, label]) => (
            <button
              key={value}
              role="tab"
              aria-selected={tab === value}
              onClick={() => setTab(value)}
              className={`pv-transition shrink-0 cursor-pointer rounded-md px-3 py-1.5 font-medium whitespace-nowrap ${
                tab === value ? "bg-hover text-ink" : "text-ink2 hover:text-ink"
              }`}
            >
              {label}
              {value === "findings" && findingTotal > 0 && (
                <span className="ml-1.5 rounded bg-hover px-1.5 text-xs tabular-nums">{findingTotal}</span>
              )}
            </button>
          ))}
        </div>
        {canInitiate && (
          <Button variant="primary" size="sm" icon={<Play size={14} />} onClick={() => setRunning(true)}>
            Run analysis
          </Button>
        )}
      </div>

      <div className="mt-4">
        {tab === "overview" && (
          <AnalysisOverview
            runs={runs}
            eligibility={eligibility}
            eligibleCount={eligible.length}
            blockedCount={blocked.length}
            artifactTotal={artifactTotal}
            correlationCount={correlationTotal}
            findingTotal={findingTotal}
            lastRun={lastRun}
            canInitiate={canInitiate}
            onRun={() => setRunning(true)}
          />
        )}
        {tab === "artifacts" && <ArtifactsTab invId={invId} />}
        {tab === "correlations" && <CorrelationsTab invId={invId} />}
        {tab === "findings" && <FindingsTab invId={invId} inv={inv} onChanged={() => void load()} />}
      </div>

      <RunAnalysisDialog
        open={running}
        onClose={() => setRunning(false)}
        invId={invId}
        eligibility={eligibility}
        onDone={() => {
          setRunning(false);
          void load();
        }}
      />
    </div>
  );
}

function AnalysisOverview({
  runs,
  eligibility,
  eligibleCount,
  blockedCount,
  artifactTotal,
  correlationCount,
  findingTotal,
  lastRun,
  canInitiate,
  onRun,
}: {
  runs: AnalysisRun[];
  eligibility: EligibilityEntry[];
  eligibleCount: number;
  blockedCount: number;
  artifactTotal: number;
  correlationCount: number;
  findingTotal: number;
  lastRun: AnalysisRun | null;
  canInitiate: boolean;
  onRun: () => void;
}) {
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-line bg-line sm:grid-cols-4">
        <OverviewStat label="Evidence processed" value={lastRun?.evidence_count ?? 0} />
        <OverviewStat label="Artifacts extracted" value={artifactTotal} />
        <OverviewStat label="Correlations" value={correlationCount} />
        <OverviewStat label="Findings" value={findingTotal} />
      </dl>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-md border border-line bg-surface">
          <div className="border-b border-line px-4 py-2.5">
            <h2 className="text-sm font-semibold">Evidence eligibility</h2>
          </div>
          <ul className="divide-y divide-line">
            {eligibility.length === 0 && (
              <li className="px-4 py-3 text-sm text-ink3">No evidence registered yet.</li>
            )}
            {eligibility.map((entry) => (
              <li key={entry.evidence_id} className="flex items-center justify-between gap-2 px-4 py-2 text-sm">
                <span className="min-w-0">
                  <span className="font-mono text-xs text-ink3">{entry.evidence_number}</span>{" "}
                  <span className="truncate font-medium">{entry.title}</span>
                  {!entry.eligible && entry.reason && (
                    <span className="block truncate text-xs text-ink3">{entry.reason}</span>
                  )}
                </span>
                <Badge tone={entry.eligible ? "success" : "neutral"}>
                  {entry.eligible ? "Eligible" : "Blocked"}
                </Badge>
              </li>
            ))}
          </ul>
          <p className="border-t border-line px-4 py-2.5 text-xs text-ink3">
            Only verified evidence is processed. {eligibleCount} eligible · {blockedCount} blocked.
            {canInitiate ? "" : " Your role can view results but cannot start runs."}
          </p>
        </section>

        <section className="rounded-md border border-line bg-surface">
          <div className="border-b border-line px-4 py-2.5">
            <h2 className="text-sm font-semibold">Run history</h2>
          </div>
          {runs.length === 0 ? (
            <div className="p-4">
              <EmptyState
                icon={<FlaskConical size={22} />}
                title="No analysis runs yet"
                body="Select verified evidence and run the deterministic extraction pipeline. Nothing is inferred at this stage."
                action={
                  canInitiate ? (
                    <Button variant="primary" size="sm" onClick={onRun}>
                      Run analysis
                    </Button>
                  ) : undefined
                }
              />
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {runs.slice(0, 6).map((run) => (
                <li key={run.id} className="px-4 py-2.5 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono font-medium">{run.run_label ?? `RUN-${run.run_number}`}</span>
                    <Badge tone={run.status === "completed" ? "success" : run.status === "failed" ? "danger" : "neutral"}>
                      {RUN_STATUS_LABELS[run.status]}
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-ink3">
                    {run.evidence_count} evidence · {run.artifact_count} artifacts ·{" "}
                    {run.correlation_count} correlations ·{" "}
                    {run.initiated_by_username ?? "unknown"} ·{" "}
                    {run.completed_at ? timeAgo(run.completed_at) : formatDate(run.started_at)}
                  </p>
                  {run.status === "failed" && run.error && (
                    <p className="mt-0.5 text-xs text-danger-ink">{run.error}</p>
                  )}
                  {run.evidence_outcomes.some((o) => o.status !== "processed") && (
                    <p className="mt-0.5 text-xs text-warning-ink">
                      {run.evidence_outcomes
                        .filter((o) => o.status !== "processed")
                        .map((o) => `${o.evidence_number ?? "E-?"}: ${RUN_EVIDENCE_LABELS[o.status]}`)
                        .join("; ")}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <p className="text-xs text-ink3">
        Deterministic extraction and shared-value correlation only. Conclusions,
        scores of suspicion, and recommendations arrive with reviewed findings, not runs.
      </p>
    </div>
  );
}

function OverviewStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-surface px-4 py-3">
      <dt className="text-[13px] text-ink2">{label}</dt>
      <dd className="mt-0.5 text-2xl font-semibold tracking-tight tabular-nums">{value}</dd>
    </div>
  );
}

export function RunAnalysisDialog({
  open,
  onClose,
  invId,
  eligibility,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  invId: number;
  eligibility: EligibilityEntry[];
  onDone: () => void;
}) {
  const { notify } = useToast();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState<string | null>(null);

  useEffectReset(open, setSelected, setError, setPhase);

  const eligible = eligibility.filter((e) => e.eligible);
  const blocked = eligibility.filter((e) => !e.eligible);

  function toggle(id: number) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function onStart() {
    if (selected.size === 0) {
      setError("Select at least one eligible evidence item.");
      return;
    }
    setError(null);
    setBusy(true);
    setPhase("Processing evidence on the server…");
    try {
      const run = await api.startAnalysisRun(invId, [...selected]);
      notify(
        "success",
        `Analysis ${run.run_label ?? ""} completed: ${run.artifact_count} artifacts, ${run.correlation_count} correlations.`,
      );
      onDone();
    } catch (err) {
      setError(actionErrorMessage(err, "Analysis failed to start."));
    } finally {
      setBusy(false);
      setPhase(null);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Run analysis"
      description="Only verified evidence is processed. Blocked items stay out with reasons."
      wide
    >
      {eligible.length === 0 ? (
        <EmptyState
          icon={<FlaskConical size={22} />}
          title="Nothing eligible to analyze"
          body="Verify evidence integrity first. Verification is available to every investigation member from the evidence record."
        />
      ) : (
        <>
          <ul className="max-h-64 space-y-1 overflow-y-auto">
            {eligible.map((entry) => (
              <li key={entry.evidence_id}>
                <label className="pv-transition flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 hover:bg-hover">
                  <input
                    type="checkbox"
                    checked={selected.has(entry.evidence_id)}
                    onChange={() => toggle(entry.evidence_id)}
                    className="h-4 w-4 accent-[var(--accent)]"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{entry.title}</span>
                    <span className="block font-mono text-xs text-ink3">
                      {entry.evidence_number} · verified
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          {blocked.length > 0 && (
            <div className="mt-3 rounded-md border border-line bg-canvas px-3 py-2">
              <p className="text-xs font-medium text-ink2">Blocked from this run</p>
              <ul className="mt-1 space-y-0.5">
                {blocked.map((entry) => (
                  <li key={entry.evidence_id} className="text-xs text-ink3">
                    <span className="font-mono">{entry.evidence_number}</span> · {entry.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
      {phase && <p className="mt-3 text-sm text-ink2" role="status">{phase}</p>}
      {error && (
        <p role="alert" className="mt-3 rounded-md border border-danger-line bg-danger-bg px-3 py-2 text-sm text-danger-ink">
          {error}
        </p>
      )}
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose} disabled={busy}>
          Cancel
        </Button>
        <Button
          variant="primary"
          onClick={() => void onStart()}
          loading={busy}
          disabled={eligible.length === 0}
        >
          Start processing
        </Button>
      </div>
    </Dialog>
  );
}

function useEffectReset(
  open: boolean,
  setSelected: (v: Set<number>) => void,
  setError: (v: string | null) => void,
  setPhase: (v: string | null) => void,
) {
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open && !wasOpen.current) {
      setSelected(new Set());
      setError(null);
      setPhase(null);
    }
    wasOpen.current = open;
  }, [open, setSelected, setError, setPhase]);
}
