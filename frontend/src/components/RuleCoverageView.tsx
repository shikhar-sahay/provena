import type { RuleCoverage } from "../api/client";
export function RuleCoverageView({ coverage }: { coverage: RuleCoverage[] }) {
  if (!coverage.length) return <p className="text-xs text-ink3">Rule evaluation coverage not recorded.</p>;
  return <ul className="space-y-1 text-xs text-ink2" aria-label="Rule evaluation coverage">
    {coverage.map((row) => <li key={row.rule_id}>
      {row.rule_id}: {row.emitted_count} / {row.proposed_count} enumerated proposals; {row.omitted_count} omitted (limit {row.output_limit}).
      {!row.evaluation_complete && <span className="text-warning-ink"> Evaluation budget reached; total possible results are unknown. {row.candidate_pairs_checked} candidate pairs checked.</span>}
    </li>)}
  </ul>;
}
