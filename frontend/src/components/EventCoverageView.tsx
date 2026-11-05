import type { EventRun } from "../api/client";
export function EventCoverageView({ run }: { run: EventRun }) {
  const c = run.coverage;
  return <details className="rounded-md border border-line p-3 text-xs">
    <summary className="cursor-pointer font-medium">Run #{run.id}: {run.status} | Evidence #{run.evidence_id} | Profile #{run.profile_id}</summary>
    <p className="mt-1">Records: {c.records_total ?? "unknown"}; recognized {c.recognized ?? 0}; unsupported {c.unrecognized ?? 0}; rejected {c.rejected ?? 0}; omitted {c.omitted ?? "unknown"}; new events {c.events_created ?? 0}.</p>
    {run.error && <p className="text-warning-ink">{run.error}</p>}
    {c.warnings?.map((w) => <p key={w} className="text-warning-ink">{w}</p>)}
    {c.issues?.map((issue, i) => <p key={i}>{JSON.stringify(issue.locator)}: {issue.reason}</p>)}
    <p className="break-all">Input SHA-256: {run.input_sha256 ?? "not consumed"}; verification #{run.verification_id ?? "not recorded"}.</p>
  </details>;
}
