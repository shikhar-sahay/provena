"""Grounded report narrative providers.

Providers receive only validated structured investigation state. They never
receive raw evidence and never create findings, scores, or integrity results.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings

TEMPLATE_VERSION = "grounded-report-v1"


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
    inv = context["investigation"]
    findings = context["accepted_findings"]
    finding_narratives = {
        str(item["id"]): (
            f"{item['title']}. {item['summary']} This accepted finding has a deterministic "
            f"confidence score of {item['confidence']}/100 based on the recorded factors."
        )
        for item in findings
    }
    if findings:
        executive = (
            f"Investigation {inv['case_number']} contains {len(findings)} accepted finding"
            f"{'s' if len(findings) != 1 else ''}. The conclusions below are limited to findings "
            "reviewed and accepted by an authorized investigator."
        )
        conclusion = (
            "The accepted findings warrant the documented follow-up actions. Pending and rejected "
            "findings are excluded from validated conclusions."
        )
    else:
        executive = (
            f"Investigation {inv['case_number']} currently has no accepted findings. "
            "No validated analytical conclusion is presented."
        )
        conclusion = "No accepted findings are available for a validated conclusion."
    narrative = {
        "executive_summary": executive,
        "investigation_narrative": (
            f"{inv['title']} is recorded with status {inv['status']} and priority {inv['priority']}. "
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


def _validate_generated(data: Any, allowed_ids: set[int], context: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Provider response is not a JSON object.")
    required_strings = ("executive_summary", "investigation_narrative", "conclusion")
    for key in required_strings:
        if not isinstance(data.get(key), str) or not data[key].strip() or len(data[key]) > 6000:
            raise ValueError(f"Provider field {key} is invalid.")
    used = data.get("used_finding_ids")
    if not isinstance(used, list) or any(not isinstance(item, int) for item in used):
        raise ValueError("Provider finding references are invalid.")
    if not set(used).issubset(allowed_ids):
        raise ValueError("Provider referenced an unsupported finding.")
    if set(used) != allowed_ids:
        raise ValueError("Provider omitted an accepted finding.")
    narratives = data.get("finding_narratives")
    if not isinstance(narratives, dict):
        raise ValueError("Provider finding narratives are invalid.")
    ordered_ids = [int(item["id"]) for item in context["accepted_findings"]]
    normalized_narratives: dict[str, str] = {}
    for key, value in narratives.items():
        try:
            finding_id = int(key)
        except (TypeError, ValueError) as exc:
            raise ValueError("Provider finding reference is invalid.") from exc
        if finding_id not in allowed_ids and 1 <= finding_id <= len(ordered_ids):
            finding_id = ordered_ids[finding_id - 1]
        if finding_id not in allowed_ids or not isinstance(value, str) or len(value) > 4000:
            raise ValueError("Provider finding narrative is unsupported.")
        normalized_narratives[str(finding_id)] = value.strip()
    if set(map(int, normalized_narratives)) != allowed_ids:
        raise ValueError("Provider omitted an accepted finding narrative.")
    validated = {
        "executive_summary": data["executive_summary"].strip(),
        "investigation_narrative": data["investigation_narrative"].strip(),
        "finding_narratives": normalized_narratives,
        "conclusion": data["conclusion"].strip(),
        "used_finding_ids": used,
    }
    _validate_grounded_literals(validated, context)
    return validated


def _validate_grounded_literals(narrative: dict[str, Any], context: dict[str, Any]) -> None:
    """Reject concrete identifiers or quantities absent from supplied facts.

    This intentionally favors fallback over fluent but weakly grounded prose.
    It does not claim semantic proof; it catches common hallucination classes
    while the immutable deterministic sections remain authoritative.
    """
    generated = json.dumps(narrative, sort_keys=True).lower()
    source = json.dumps(context, sort_keys=True, default=str).lower()
    patterns = (
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b",
        r"https?://[^\s\"']+",
        r"\b[a-z0-9_-]+\.(?:csv|log|txt|json|pdf|docx?|xlsx?)\b",
        r"\b(?:ws|host|pc)-[a-z0-9_-]+\b",
    )
    for pattern in patterns:
        for value in re.findall(pattern, generated, flags=re.IGNORECASE):
            if value.lower() not in source:
                raise ValueError(f"Provider introduced unsupported literal: {value[:80]}")
    number_words = (
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "eleven", "twelve", "once", "twice",
    )
    for word in number_words:
        if re.search(rf"\b{word}\b", generated) and not re.search(rf"\b{word}\b", source):
            raise ValueError(f"Provider introduced unsupported quantity: {word}")
    for value in re.findall(r"\b\d+(?:\.\d+)?\b", generated):
        if not re.search(rf"(?<!\d){re.escape(value)}(?!\d)", source):
            raise ValueError(f"Provider introduced unsupported quantity: {value}")


def generate_narrative(context: dict[str, Any]) -> NarrativeResult:
    """Use configured local inference, falling back for every failure mode."""
    if not settings.llm_enabled or settings.llm_provider.lower() != "ollama":
        return deterministic_narrative(context)
    if not settings.ollama_model.strip():
        return deterministic_narrative(context, "OLLAMA_MODEL is not configured.")

    allowed_ids = {int(item["id"]) for item in context["accepted_findings"]}
    prompt = (
        "You write cautious digital investigation report prose. Use only the JSON facts supplied. "
        "Do not add people, evidence, events, intent, guilt, scores, or conclusions. Only accepted "
        "findings may appear as conclusions. Return JSON with executive_summary, "
        "investigation_narrative, finding_narratives (object keyed by finding id), conclusion, "
        "and used_finding_ids (integer array). finding_narratives must use the exact finding IDs "
        f"{sorted(allowed_ids)} as keys. Do not state a quantity or count unless copying it exactly "
        "from the facts. Prefer cautious prose without new quantities. Do not include reasoning or "
        "chain-of-thought.\nFACTS:\n"
        + json.dumps(context, sort_keys=True, default=str)
    )
    try:
        response = httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},
            },
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        envelope = response.json()
        data = json.loads(envelope.get("response", ""))
        narrative = _validate_generated(data, allowed_ids, context)
        return NarrativeResult(
            narrative=narrative,
            metadata={
                "mode": "ai_enhanced",
                "provider": "ollama",
                "model": settings.ollama_model,
                "generated_at": _now_iso(),
                "context_sha256": _context_hash(context),
                "template_version": TEMPLATE_VERSION,
                "fallback": False,
                "error": None,
            },
        )
    except (httpx.HTTPError, json.JSONDecodeError, ValueError, TypeError) as exc:
        return deterministic_narrative(context, f"{type(exc).__name__}: {str(exc)[:240]}")


def provider_health() -> dict[str, Any]:
    configured = settings.llm_enabled and settings.llm_provider.lower() == "ollama"
    result: dict[str, Any] = {
        "enabled": settings.llm_enabled,
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
        result["detail"] = "Configured model is available." if result["available"] else "Ollama is reachable, but the configured model is not installed."
    except (httpx.HTTPError, ValueError, TypeError):
        result["detail"] = "Ollama is unavailable. Deterministic fallback remains active."
    return result
