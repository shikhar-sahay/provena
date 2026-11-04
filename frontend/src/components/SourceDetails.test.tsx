import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { SourceDetails } from "./SourceDetails";
import { locatorLabel } from "../lib/analysis";
it("separates source spans, decoded offsets and unknown local time", () => {
  const locator = {kind: "line", line: 2, span: [320,329], offset_basis: "decoded_line_codepoints",
    excerpt_whitespace_collapsed: true, timestamp: { original: "2026-11-01 01:30:00", timezone_status: "unknown", precision: "second" }};
  render(<SourceDetails locator={locator} />);
  expect(locatorLabel(locator)).toContain("characters [320, 329)");
  expect(screen.getByText(/Source timezone unknown/)).toBeInTheDocument();
  expect(screen.getByText(/offsets do not refer to preview/)).toBeInTheDocument();
});
it("preserves explicit offsets and UTC display", () => {
  render(<SourceDetails locator={{timestamp: { original: "2026-01-01T01:00:00+05:30", timezone_status: "explicit_offset", source_offset: "+05:30", utc: "2025-12-31T19:30:00+00:00" }}} />);
  expect(screen.getByText(/Source offset \+05:30; UTC 2025/)).toBeInTheDocument();
});
