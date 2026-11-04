export function SourceDetails({ locator }: { locator: Record<string, unknown> }) {
  const time = locator.timestamp as Record<string, unknown> | undefined;
  return <div className="mt-1 text-xs text-ink3">
    <p>{typeof locator.offset_basis === "string" ? `Zero-based, half-open offsets in ${locator.offset_basis.replaceAll("_", " ")}.` : "Historical source offset semantics were not recorded."}</p>
    {locator.exact_file_offsets === false && <p>Exact original file offsets are unavailable for this decoded or extracted value.</p>}
    {locator.excerpt_whitespace_collapsed === true && <p>Preview whitespace is collapsed; source offsets do not refer to preview positions.</p>}
    {time && <>
      <p>Original timestamp: {String(time.original ?? "unknown")}</p>
      <p>{time.timezone_status === "explicit_offset" ? `Source offset ${String(time.source_offset)}; UTC ${String(time.utc)}.` : "Source timezone unknown. Local wall time is not confirmed UTC and is excluded from cross-source temporal rules."}</p>
      <p>Recorded precision: {String(time.precision ?? "unknown")}.</p>
    </>}
  </div>;
}
