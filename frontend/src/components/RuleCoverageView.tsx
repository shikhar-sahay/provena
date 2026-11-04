import type { RuleCoverage } from "../api/client";
export function RuleCoverageView({ coverage }: { coverage: RuleCoverage[] }) {
  if (!coverage.length) return <p className="text-xs text-ink3">Rule evaluation coverage not recorded.</p>;
  return <ul title="Counts describe the last evaluation; evaluate again after evidence changes." className="space-y-1 text-xs text-ink2" aria-label="Last rule evaluation coverage">
    {coverage.map((row) => <li key={row.rule_id}>
      {row.rule_id}: {row.emitted_count} / {row.proposed_count} enumerated proposals; {row.omitted_count} omitted (limit {row.output_limit}).
      {!row.evaluation_complete && <span className="text-warning-ink"> Evaluation budget reached; total possible results are unknown. {row.candidate_pairs_checked} candidate pairs checked.</span>}
    </li>)}
  </ul>;
}
