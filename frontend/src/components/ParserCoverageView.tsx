import type { ParserCoverage } from "../api/client";

export function ParserCoverageView({ coverage, label }: { coverage?: ParserCoverage | null; label: string }) {
  if (!coverage) return <p className="mt-1 text-xs text-ink3">{label}: coverage not recorded.</p>;
  return <details className="mt-1 text-xs text-ink2">
    <summary className="cursor-pointer">{label}: {coverage.status} coverage</summary>
    <p>{coverage.units_processed ?? 0} source units; {coverage.characters_scanned ?? 0} characters scanned.</p>
    {coverage.total_pages !== undefined && <p>{coverage.processed_pages?.length ?? 0} / {coverage.total_pages} PDF pages processed; {coverage.skipped_pages?.length ?? 0} skipped; {coverage.unprocessed_page_count ?? 0} beyond processing budget.</p>}
    {coverage.warnings?.map((warning) => <p key={warning} className="text-warning-ink">{warning}</p>)}
    {coverage.skipped_pages?.map((page) => <p key={page.page}>Page {page.page}: {page.reason}</p>)}
  </details>;
}
