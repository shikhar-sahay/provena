"""Grounded report narrative providers.

Providers receive only validated structured investigation state. They never
receive raw evidence and never create findings, scores, or integrity results.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings

TEMPLATE_VERSION = "deterministic-report-v2"


@dataclass
class NarrativeResult:
    narrative: dict[str, Any]
    metadata: dict[str, Any]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _context_hash(context: dict[str, Any]) -> str:
    canonical = json.dumps(context, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def deterministic_narrative(context: dict[str, Any], error: str | None = None) -> NarrativeResult:
    findings = context["accepted_findings"]
    finding_narratives = {
        str(item["id"]): (
            f"{item['title']}. {item['summary']} This accepted finding has a deterministic "
            f"support score of {item['confidence']}/100 based on the recorded factors, not a calibrated probability."
        )
        for item in findings
    }
    if findings:
        executive = (
            f"This investigation contains {len(findings)} accepted finding"
            f"{'s' if len(findings) != 1 else ''}. The conclusions below are limited to findings "
            "reviewed and accepted by an authorized investigator."
        )
        conclusion = (
            "The accepted findings warrant the documented follow-up actions. Pending and rejected "
            "findings are excluded from validated conclusions."
        )
    else:
        executive = (
            "This investigation currently has no accepted findings. "
            "No validated analytical conclusion is presented."
        )
        conclusion = "No accepted findings are available for a validated conclusion."
    narrative = {
        "executive_summary": executive,
        "investigation_narrative": (
            f"The report inventory contains {context['evidence_count']} evidence item"
            f"{'s' if context['evidence_count'] != 1 else ''}."
        ),
        "finding_narratives": finding_narratives,
        "conclusion": conclusion,
        "used_finding_ids": [item["id"] for item in findings],
    }
    return NarrativeResult(
        narrative=narrative,
        metadata={
            "mode": "deterministic_fallback",
            "provider": "deterministic",
            "model": None,
            "generated_at": _now_iso(),
            "context_sha256": _context_hash(context),
            "template_version": TEMPLATE_VERSION,
            "fallback": True,
            "error": error,
        },
    )


def generate_narrative(context: dict[str, Any]) -> NarrativeResult:
    """Only deterministic assembly enters authoritative reports.

    Literal/reference validation cannot prove semantic equivalence or prevent
    negation reversal. Model prose is therefore never requested or accepted,
    even when an operator retains the legacy Ollama configuration. Notes,
    descriptions and uploaded content are not narration instructions.
    """
    reason = ("Free-form model narration is disabled in authoritative reports; "
              "deterministic assembly preserves validated finding meaning.") if settings.llm_enabled else None
    return deterministic_narrative(context, reason)


def provider_health() -> dict[str, Any]:
    configured = settings.llm_enabled and settings.llm_provider.lower() == "ollama"
    result: dict[str, Any] = {
        "enabled": settings.llm_enabled,
        "authoritative_mode": "deterministic",
        "provider": settings.llm_provider,
        "model": settings.ollama_model or None,
        "available": False,
        "detail": "Deterministic fallback is active.",
    }
    if not configured:
        return result
    try:
        response = httpx.get(
            f"{settings.ollama_base_url.rstrip('/')}/api/tags",
            timeout=min(settings.llm_timeout_seconds, 5.0),
        )
        response.raise_for_status()
        models = [item.get("name", "") for item in response.json().get("models", [])]
        result["available"] = any(
            name == settings.ollama_model or name.split(":")[0] == settings.ollama_model
            for name in models
        )
        result["detail"] = "Configured model is available. Authoritative reports use deterministic assembly." if result["available"] else "Ollama is reachable, but the configured model is not installed."
    except (httpx.HTTPError, ValueError, TypeError):
        result["detail"] = "Ollama is unavailable. Deterministic fallback remains active."
    return result
