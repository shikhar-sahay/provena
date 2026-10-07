import { describe, expect, it } from "vitest";
import type { Report } from "../api/client";
import { presentReport } from "./reports";

function reportWith(content: Record<string, unknown>): Report {
  return {
    id: 1,
    investigation_id: 1,
    report_number: 1,
    report_label: "RPT-0001",
    generated_by_username: "investigator",
    content: {
      investigation: {
        case_number: "PRV-2026-0001",
        title: "Synthetic case",
        description: "Synthetic investigation overview.",
        status: "under_review",
        priority: "high",
        created_by: "investigator",
        lead_investigator: "investigator",
        team: [],
        created_at: "2026-10-08T00:00:00Z",
      },
      evidence_summary: [],
      custody_summary: [],
      timeline: [],
      accepted_findings: [],
      recommendations: [],
      investigator_notes: [],
      generated_by: "investigator",
      generated_at: "2026-10-08T00:00:00Z",
      generator: "grounded-report-v2",
      ...content,
    },
    content_sha256: "a".repeat(64),
    created_at: "2026-10-08T00:00:00Z",
  } as Report;
}

describe("report snapshot compatibility", () => {
  it("renders a legacy snapshot with no narrative metadata", () => {
    const presentation = presentReport(reportWith({ generator: "deterministic-report-v1" }));
    expect(presentation.modeLabel).toBe("Deterministic fallback");
    expect(presentation.executiveSummary).toContain("immutable report snapshot");
    expect(presentation.contextSha256).toBeNull();
  });

  it("preserves truthful AI-enhanced provider and model metadata", () => {
    const presentation = presentReport(reportWith({
      narrative: {
        executive_summary: "Grounded summary.",
        investigation_narrative: "Grounded overview.",
        finding_narratives: {},
        conclusion: "Grounded conclusion.",
        used_finding_ids: [],
      },
      generation_metadata: {
        mode: "ai_enhanced",
        provider: "Ollama",
        model: "qwen2.5:7b",
        generated_at: "2026-10-08T00:00:00Z",
        context_sha256: "b".repeat(64),
        template_version: "1",
        fallback: false,
        error: null,
      },
    }));
    expect(presentation.modeLabel).toBe("AI-enhanced narrative");
    expect(presentation.provider).toBe("Ollama");
    expect(presentation.model).toBe("qwen2.5:7b");
  });

  it("turns provider failures into actionable fallback metadata without exposing internals", () => {
    const presentation = presentReport(reportWith({
      generation_metadata: {
        mode: "deterministic_fallback",
        provider: "Ollama",
        model: "qwen2.5:7b",
        generated_at: "2026-10-08T00:00:00Z",
        context_sha256: "c".repeat(64),
        template_version: "1",
        fallback: true,
        error: "ConnectionError: stack trace with private implementation detail",
      },
    }));
    expect(presentation.fallbackReason).toBe("The local narrative provider was unavailable.");
    expect(presentation.fallbackReason).not.toContain("stack trace");
  });
});
