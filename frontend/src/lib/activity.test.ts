import { describe, expect, it } from "vitest";
import { actionLabel } from "./activity";

describe("activity labels", () => {
  it("presents analysis and reporting events as readable UI copy", () => {
    expect(actionLabel("AI_ANALYSIS_COMPLETED")).toBe("Analysis completed");
    expect(actionLabel("AI_FINDING_ACCEPTED")).toBe("Finding accepted");
    expect(actionLabel("REPORT_GENERATED")).toBe("Report generated");
  });
});
