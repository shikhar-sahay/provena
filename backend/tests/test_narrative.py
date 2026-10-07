"""Local narrative grounding and fallback behavior."""

import json

import httpx

from app.core.config import settings
from app.modules.intelligence.narrative import generate_narrative


CONTEXT = {
    "investigation": {
        "case_number": "PRV-2026-0001", "title": "Synthetic case",
        "description": "Synthetic only", "status": "under_review", "priority": "high",
    },
    "accepted_findings": [{
        "id": 7, "title": "Potential transfer sequence", "summary": "Warrants review.",
        "confidence": 80, "recommendations": ["Review custody records."],
    }],
    "evidence_count": 2,
    "confidence_scale": "0-100 deterministic weighted score, not a probability",
    "recommendations": ["Review custody records."],
    "investigator_notes": [],
}


def test_disabled_provider_uses_truthful_deterministic_fallback(monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", False)
    result = generate_narrative(CONTEXT)
    assert result.metadata["mode"] == "deterministic_fallback"
    assert result.metadata["fallback"] is True
    assert result.narrative["used_finding_ids"] == [7]


def test_ollama_structured_response_is_accepted(monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_model", "test-model")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": json.dumps({
                "executive_summary": "An accepted finding warrants review.",
                "investigation_narrative": "The supplied investigation record was reviewed.",
                "finding_narratives": {"7": "The accepted finding is consistent with a potential transfer."},
                "conclusion": "Follow the recorded recommendation.",
                "used_finding_ids": [7],
            })}

    monkeypatch.setattr("app.modules.intelligence.narrative.httpx.post", lambda *a, **k: Response())
    result = generate_narrative(CONTEXT)
    assert result.metadata["mode"] == "ai_enhanced"
    assert result.metadata["model"] == "test-model"
    assert result.metadata["fallback"] is False


def test_malformed_unknown_reference_and_timeout_fall_back(monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_model", "test-model")

    class BadResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": json.dumps({
                "executive_summary": "Unsupported", "investigation_narrative": "Unsupported",
                "finding_narratives": {"999": "Invented"}, "conclusion": "Unsupported",
                "used_finding_ids": [999],
            })}

    monkeypatch.setattr("app.modules.intelligence.narrative.httpx.post", lambda *a, **k: BadResponse())
    assert generate_narrative(CONTEXT).metadata["fallback"] is True

    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr("app.modules.intelligence.narrative.httpx.post", timeout)
    result = generate_narrative(CONTEXT)
    assert result.metadata["fallback"] is True
    assert "ReadTimeout" in result.metadata["error"]


def test_unsupported_quantity_forces_fallback(monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_model", "test-model")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": json.dumps({
                "executive_summary": "The event was observed twice.",
                "investigation_narrative": "Only supplied records were reviewed.",
                "finding_narratives": {"7": "The accepted finding warrants review."},
                "conclusion": "Follow the recorded recommendation.",
                "used_finding_ids": [7],
            })}

    monkeypatch.setattr("app.modules.intelligence.narrative.httpx.post", lambda *a, **k: Response())
    result = generate_narrative(CONTEXT)
    assert result.metadata["fallback"] is True
    assert "unsupported quantity" in result.metadata["error"]
