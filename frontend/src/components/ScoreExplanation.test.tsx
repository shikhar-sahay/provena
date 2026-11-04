import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ScoreExplanation } from "./ScoreExplanation";
it("shows the reconstructible factor total", () => {
  render(<ScoreExplanation score={70} weights={[25,15,20,10]} />);
  expect(screen.getByText(/Declared factors total 70\/100/)).toBeInTheDocument();
});
it("does not present a historical unexplained score as reconciled", () => {
  render(<ScoreExplanation score={80} weights={[25,15,20,10]} />);
  expect(screen.getByText(/Historical score 80\/100 differs/)).toBeInTheDocument();
});
