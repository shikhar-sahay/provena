import { render, screen } from "@testing-library/react";
import { it, expect } from "vitest";
import { RuleCoverageView } from "./RuleCoverageView";
it("distinguishes output omissions from unenumerated candidates", () => {
  render(<RuleCoverageView coverage={[{rule_id: "test", emitted_count: 25, proposed_count: 30,
    omitted_count: 5, output_limit: 25, evaluation_complete: false, candidate_pairs_checked: 100000}]} />);
  expect(screen.getByText(/5 omitted/)).toBeInTheDocument();
  expect(screen.getByText(/total possible results are unknown/)).toBeInTheDocument();
});
