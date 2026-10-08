import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProvenanceMotif } from "./ProvenanceMotif";

describe("ProvenanceMotif", () => {
  it("exposes lightweight motion targets while remaining decorative", () => {
    const { container } = render(<ProvenanceMotif className="pv-motif" />);
    const motif = container.querySelector("svg");

    expect(motif).toHaveAttribute("aria-hidden", "true");
    expect(motif).toHaveClass("pv-motif");
    expect(container.querySelectorAll(".pv-node").length).toBeGreaterThan(0);
    expect(container.querySelectorAll(".pv-trace").length).toBeGreaterThan(0);
    expect(container.querySelectorAll(".pv-hub-ring").length).toBeGreaterThan(0);
  });
});
