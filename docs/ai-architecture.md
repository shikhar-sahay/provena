# AI Architecture

## Pipeline (planned)

```text
Evidence Ingestion
  → Processing / Normalization
  → Artifact & Entity Extraction
  → Evidence Correlation
  → Rule-Based Reasoning
  → Confidence Scoring
  → Investigation Recommendations
  → Human Investigator Validation
  → LLM-Assisted Report Generation
```

Each stage records its inputs, rules, and outputs so any finding can be traced
back to the evidence and logic that produced it.

## Stage responsibilities (planned)

- **Ingestion / processing:** deterministic parsing and normalization of evidence
  formats (logs, file listings, CSV exports, etc.).
- **Extraction:** regular expressions for structured artifacts (IPs, hashes,
  timestamps, filenames); spaCy only where NLP genuinely adds value, e.g. named
  entities in unstructured text.
- **Correlation:** custom logic linking artifacts across evidence items
  (shared IPs, overlapping time windows, common files/hosts).
- **Reasoning:** a custom, inspectable rule engine ("IF observed pattern X with
  supporting evidence Y THEN suggest hypothesis Z"). Rules are data with IDs,
  not hidden model weights.
- **Scoring:** transparent **weighted** confidence scores — every weight and
  contributing factor is recorded. Initial scoring is deterministic/weighted;
  probabilistic/Bayesian scoring is a possible future enhancement, not the
  current design.
- **Recommendations:** deterministic suggestions derived from scored rules
  (e.g. "verify custody of item E-12", "collect logs covering window W").
- **Human validation:** an investigator accepts or rejects each AI finding with
  a recorded rationale. Rejected findings are excluded downstream.
- **Report generation:** only validated, structured findings are rendered into
  professional prose — this is the single place a generative LLM may be used.

## Why deterministic analysis is separated from generative AI

An LLM predicts plausible text; it does not preserve evidence integrity, does
not cite verifiable derivation steps, and can hallucinate. An investigation
platform must produce findings that are **explainable, reproducible, and
auditable**. Therefore:

- Investigative truth comes from deterministic, inspectable code over evidence.
- The LLM, if used at all, is a **language-generation component**: it formats
  already-validated structured findings into readable prose.
- The LLM never invents findings, scores, or recommendations.

## Ollama / local models (planned, not configured)

No LLM dependency exists in this repository today, and none should be added
without explicit request. The intended future integration is a local model via
Ollama (zero budget, data stays on the machine), called only at the report
stage with validated findings as input.

## Graceful degradation

The system must remain fully useful when no LLM is available: analysis,
validation, and structured reports work without one; only the polished
natural-language rendering of the report is skipped or replaced by a simple
template. Never implement fake AI functionality or label ordinary conditional
logic "machine learning".
