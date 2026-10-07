import type { Report, ReportContent } from "../api/client";

export interface ReportPresentation {
  mode: "ai_enhanced" | "deterministic_fallback";
  modeLabel: string;
  provider: string | null;
  model: string | null;
  contextSha256: string | null;
  fallbackReason: string | null;
  executiveSummary: string;
  investigationNarrative: string;
  findingNarratives: Record<string, string>;
  conclusion: string;
}

function cleanFallbackReason(value: string | null | undefined) {
  if (!value) return null;
  const lower = value.toLowerCase();
  if (lower.includes("timeout") || lower.includes("timed out")) {
    return "The local narrative provider did not respond in time.";
  }
  if (lower.includes("connect") || lower.includes("unavailable")) {
    return "The local narrative provider was unavailable.";
  }
  return "The local narrative provider could not produce a valid grounded response.";
}

function legacyNarrative(content: ReportContent) {
  const accepted = content.accepted_findings ?? [];
  const evidence = content.evidence_summary ?? [];
  const findingText = accepted.length === 1 ? "1 accepted finding" : `${accepted.length} accepted findings`;
  const evidenceText = evidence.length === 1 ? "1 evidence item" : `${evidence.length} evidence items`;
  return {
    executive_summary: `This immutable report snapshot records ${findingText} supported by ${evidenceText}. Conclusions are limited to findings accepted by an investigator at generation time.`,
    investigation_narrative: content.investigation?.description || "No investigation overview was recorded in this snapshot.",
    finding_narratives: {} as Record<string, string>,
    conclusion: accepted.length
      ? "The accepted findings and their traceable supporting records are preserved below for investigator review."
      : "No accepted findings were present when this report snapshot was generated.",
  };
}

export function presentReport(report: Report): ReportPresentation {
  const content = report.content;
  const metadata = content.generation_metadata;
  const narrative = content.narrative ?? legacyNarrative(content);
  const aiEnhanced = metadata?.mode === "ai_enhanced";

  return {
    mode: aiEnhanced ? "ai_enhanced" : "deterministic_fallback",
    modeLabel: aiEnhanced ? "AI-enhanced narrative" : "Deterministic fallback",
    provider: aiEnhanced ? metadata?.provider ?? null : null,
    model: aiEnhanced ? metadata?.model ?? null : null,
    contextSha256: metadata?.context_sha256 ?? null,
    fallbackReason: metadata?.fallback ? cleanFallbackReason(metadata.error) : null,
    executiveSummary: narrative.executive_summary,
    investigationNarrative: narrative.investigation_narrative,
    findingNarratives: narrative.finding_narratives ?? {},
    conclusion: narrative.conclusion,
  };
}
