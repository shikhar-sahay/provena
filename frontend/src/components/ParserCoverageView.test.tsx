import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ParserCoverageView } from "./ParserCoverageView";

describe("parser coverage", () => {
  it("exposes page omissions and warnings", () => {
    render(<ParserCoverageView label="E-1" coverage={{ status: "partial", total_pages: 51,
      processed_pages: [1, 3], skipped_pages: [{ page: 2, reason: "Extraction failed" }],
      unprocessed_page_count: 1, warnings: ["Page budget reached"] }} />);
    expect(screen.getByText("E-1: partial coverage")).toBeInTheDocument();
    expect(screen.getByText(/2 \/ 51 PDF/)).toBeInTheDocument();
    expect(screen.getByText("Page 2: Extraction failed")).toBeInTheDocument();
    expect(screen.getByText("Page budget reached")).toBeInTheDocument();
  });
  it("does not assume legacy coverage is complete", () => {
    render(<ParserCoverageView label="E-2" />);
    expect(screen.getByText("E-2: coverage not recorded.")).toBeInTheDocument();
  });
});
