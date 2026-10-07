// Behavior tests for analysis presentation helpers and the run workflow.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ToastProvider } from "../components/Toast";
import { ThemeProvider } from "../theme/ThemeContext";
import {
  FINDING_STATUS_LABELS,
  RUN_EVIDENCE_LABELS,
  artifactTypeLabel,
  locatorLabel,
  severityTone,
} from "./analysis";
import { RunAnalysisDialog } from "../pages/AnalysisPage";
import { api } from "../api/client";

vi.mock("../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../api/client")>();
  return {
    ...original,
    api: {
      ...original.api,
      startAnalysisRun: vi.fn(),
    },
  };
});

const ELIGIBILITY = [
  {
    evidence_id: 1,
    evidence_number: "E-001",
    title: "Auth log",
    integrity_status: "verified",
    supported: true,
    eligible: true,
    reason: null,
  },
  {
    evidence_id: 2,
    evidence_number: "E-002",
    title: "Raw image",
    integrity_status: "not_verified",
    supported: true,
    eligible: false,
    reason: "Evidence has no independent verification yet. Verify integrity first.",
  },
];

describe("analysis labels", () => {
  it("explains blocked outcomes", () => {
    expect(RUN_EVIDENCE_LABELS["blocked_not_verified"]).toContain("verification");
    expect(RUN_EVIDENCE_LABELS["unsupported"]).toContain("Unsupported");
    expect(FINDING_STATUS_LABELS["pending_review"]).toBe("Pending review");
  });

  it("maps severity to restrained tones", () => {
    expect(severityTone("high")).toBe("danger");
    expect(severityTone("low")).toBe("info");
    expect(severityTone("unknown")).toBe("neutral");
  });

  it("renders provenance locators per format", () => {
    expect(locatorLabel({ kind: "line", line: 37 })).toBe("Line 37");
    expect(locatorLabel({ kind: "csv", row: 18, column: "username" })).toBe("Row 18 · username");
    expect(locatorLabel({ kind: "json", path: "$.events[4].username" })).toBe("$.events[4].username");
    expect(locatorLabel({ kind: "pdf", page: 4 })).toBe("Page 4");
    expect(artifactTypeLabel("USB_DEVICE")).toBe("USB device");
  });
});

describe("RunAnalysisDialog", () => {
  function renderDialog() {
    render(
      <ThemeProvider>
        <ToastProvider>
          <RunAnalysisDialog
            open
            onClose={() => undefined}
            invId={1}
            eligibility={ELIGIBILITY}
            onDone={() => undefined}
          />
        </ToastProvider>
      </ThemeProvider>,
    );
  }

  it("shows eligible items and blocked reasons", () => {
    renderDialog();
    expect(screen.getByText("Auth log")).toBeInTheDocument();
    expect(screen.getByText(/no independent verification yet/)).toBeInTheDocument();
  });

  it("requires a selection before starting", async () => {
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Start processing" }));
    expect(
      await screen.findByText("Select at least one eligible evidence item."),
    ).toBeInTheDocument();
    expect(api.startAnalysisRun).not.toHaveBeenCalled();
  });

  it("starts processing with the selected evidence", async () => {
    vi.mocked(api.startAnalysisRun).mockResolvedValueOnce({
      id: 1,
      run_label: "RUN-0001",
      artifact_count: 3,
      correlation_count: 1,
    } as never);
    renderDialog();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Start processing" }));
    await screen.findByText("Auth log");
    expect(api.startAnalysisRun).toHaveBeenCalledWith(1, [1]);
  });
});
