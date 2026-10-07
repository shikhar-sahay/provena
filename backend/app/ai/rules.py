"""Rule-based investigative assistance over extracted facts.

Rules match structured patterns (shared identities, devices, hosts, ordered
transfers) and produce proposed findings with deterministic weighted
confidence. A finding is decision support, never a conclusion: scores rank
and prioritize, they are not calibrated probabilities, and every factor is
recorded for the Why view. Milestone 5 owns guilt, intent, and certainty;
nothing here claims them.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

RULE_VERSION = "1"

UPLOAD_KEYWORDS = ("upload", "uploaded", "exfil", "sent", "transmit")
EXTERNAL_WINDOW_HOURS = 24
MAX_FINDINGS_PER_RULE = 25


@dataclass(frozen=True)
class ArtifactFact:
    id: int
    evidence_id: int
    evidence_number: str
    artifact_type: str
    normalized_value: str
    locator_key: str
    context: str
    span: tuple[int, int] | None = None


@dataclass
class ProposedFinding:
    rule_id: str
    rule_version: str
    title: str
    summary: str
    severity: str
    confidence: int
    factors: list[dict]
    evidence_ids: list[int]
    artifact_ids: list[int]
    correlation_ids: list[int]
    recommendations: list[str]

    def inputs_key(self) -> str:
        canonical = json.dumps(
            {
                "rule_id": self.rule_id,
                "rule_version": self.rule_version,
                "evidence_ids": sorted(self.evidence_ids),
                "artifact_ids": sorted(self.artifact_ids),
                "correlation_ids": sorted(self.correlation_ids),
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class Rule:
    rule_id: str
    name: str
    description: str
    severity: str
    recommendations: list[str]

    def evaluate(self, facts: "FactView") -> list[ProposedFinding]:
        raise NotImplementedError


class FactView:
    """Indexes over one investigation's artifacts for rule evaluation."""

    def __init__(
        self,
        artifacts: list[ArtifactFact],
        correlations: dict[tuple[str, str], int],
        all_verified: bool,
    ):
        self.artifacts = artifacts
        self.correlations = correlations
        self.all_verified = all_verified
        self.by_type_value: dict[tuple[str, str], list[ArtifactFact]] = {}
        self.units: dict[tuple[int, str], list[ArtifactFact]] = {}
        for artifact in artifacts:
            self.by_type_value.setdefault(
                (artifact.artifact_type, artifact.normalized_value), []
            ).append(artifact)
            self.units.setdefault((artifact.evidence_id, artifact.locator_key), []).append(
                artifact
            )

    def evidence_of(self, artifact_type: str, value: str) -> set[int]:
        return {a.evidence_id for a in self.by_type_value.get((artifact_type, value), [])}

    def timestamps_on_unit(self, evidence_id: int, locator_key: str) -> list[datetime]:
        out = []
        for artifact in self.units.get((evidence_id, locator_key), []):
            if artifact.artifact_type != "TIMESTAMP":
                continue
            try:
                parsed = datetime.fromisoformat(artifact.normalized_value)
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            out.append(parsed)
        return out


def _cap(findings: list[ProposedFinding]) -> list[ProposedFinding]:
    findings.sort(key=lambda f: (-f.confidence, f.title))
    return findings[:MAX_FINDINGS_PER_RULE]


class IdentityRecurrenceRule(Rule):
    """A username recurs across three or more distinct evidence items."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="identity-recurrence",
            name="Repeated identity across evidence",
            description=(
                "The same normalized username was extracted from three or more "
                "distinct evidence items. Recurrence alone proves nothing; it "
                "prioritizes the identity for investigator review."
            ),
            severity="low",
            recommendations=[
                "Confirm the account owner and whether each appearance is expected.",
                "Check whether the appearances share hosts or time windows.",
            ],
        )

    def evaluate(self, facts: FactView) -> list[ProposedFinding]:
        findings = []
        for (artifact_type, value), members in sorted(facts.by_type_value.items()):
            if artifact_type != "USERNAME":
                continue
            evidence_ids = {m.evidence_id for m in members}
            if len(evidence_ids) < 3:
                continue
            confidence = min(30 + 15 * (len(evidence_ids) - 2), 95)
            factors = [
                {"factor": "identity recurrence", "weight": 30,
                 "detail": f"{value} in {len(evidence_ids)} evidence items"},
                {"factor": "additional evidence", "weight": min(15 * (len(evidence_ids) - 2), 65),
                 "detail": f"{len(evidence_ids) - 2} items beyond the second"},
            ]
            numbers = sorted({m.evidence_number for m in members})
            findings.append(
                ProposedFinding(
                    rule_id=self.rule_id,
                    rule_version=RULE_VERSION,
                    title=f"Identity {value} recurs across {len(evidence_ids)} evidence items",
                    summary=(
                        f"The username {value} was extracted from "
                        f"{', '.join(numbers)}. Recurrence prioritizes review; "
                        "it does not establish wrongdoing."
                    ),
                    severity=self.severity,
                    confidence=confidence,
                    factors=factors,
                    evidence_ids=sorted(evidence_ids),
                    artifact_ids=sorted(m.id for m in members),
                    correlation_ids=(
                        [facts.correlations[("USERNAME", value)]]
                        if ("USERNAME", value) in facts.correlations
                        else []
                    ),
                    recommendations=list(self.recommendations),
                )
            )
        return _cap(findings)


class RemovableMediaSessionRule(Rule):
    """A user, a USB device, and a shared host link the same session context."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="removable-media-session",
            name="Potential removable-media session",
            description=(
                "A username and a USB device identifier each appear in evidence "
                "that shares a hostname. The pattern is consistent with a user "
                "session involving removable media on that host."
            ),
            severity="medium",
            recommendations=[
                "Review removable-media custody and activity for the device.",
                "Inspect file-access evidence for copies to removable volumes.",
                "Validate whether the account owner used the device.",
            ],
        )

    def evaluate(self, facts: FactView) -> list[ProposedFinding]:
        findings = []
        devices = {m.normalized_value for m in facts.artifacts if m.artifact_type == "USB_DEVICE"}
        for device in sorted(devices):
            device_evidence = facts.evidence_of("USB_DEVICE", device)
            hosts = sorted(
                {
                    m.normalized_value
                    for m in facts.artifacts
                    if m.artifact_type == "HOSTNAME" and m.evidence_id in device_evidence
                }
            )
            for host in hosts:
                host_evidence = facts.evidence_of("HOSTNAME", host)
                if not (host_evidence & device_evidence):
                    continue
                users = sorted(
                    {
                        m.normalized_value
                        for m in facts.artifacts
                        if m.artifact_type == "USERNAME"
                        and m.evidence_id in host_evidence
                        and m.evidence_id in device_evidence
                    }
                )
                if not users:
                    continue
                evidence_ids = set(device_evidence) | set(host_evidence)
                for user in users:
                    evidence_ids |= facts.evidence_of("USERNAME", user)
                factors = [
                    {"factor": "identity link", "weight": 25,
                     "detail": f"users: {', '.join(users)}"},
                    {"factor": "shared host", "weight": 25, "detail": f"host: {host}"},
                    {"factor": "device present", "weight": 20, "detail": f"device: {device}"},
                    {"factor": "independent evidence", "weight": 10,
                     "detail": f"{len(device_evidence)} evidence items hold the device"},
                ]
                confidence = 80
                if facts.all_verified:
                    factors.append({"factor": "all contributing evidence verified", "weight": 10,
                                    "detail": "integrity gate passed at generation"})
                    confidence = 90
                findings.append(
                    ProposedFinding(
                        rule_id=self.rule_id,
                        rule_version=RULE_VERSION,
                        title=(
                            f"Potential removable-media session on {host} involving "
                            f"{', '.join(users)} (device {device})"
                        ),
                        summary=(
                            f"USB device {device} and {', '.join(users)} both link "
                            f"to host {host} across {len(evidence_ids)} evidence "
                            "items. Consistent with a user session involving "
                            "removable media; not proof of misuse."
                        ),
                        severity=self.severity,
                        confidence=min(confidence, 100),
                        factors=factors,
                        evidence_ids=sorted(evidence_ids),
                        artifact_ids=sorted(
                            m.id for m in facts.artifacts
                            if (m.artifact_type, m.normalized_value) in
                            {("USB_DEVICE", device)}
                            | {("USERNAME", u) for u in users}
                            | {("HOSTNAME", host)}
                        ),
                        correlation_ids=[
                            facts.correlations[key]
                            for key in [("USB_DEVICE", device)]
                            + [("USERNAME", u) for u in users]
                            + [("HOSTNAME", host)]
                            if key in facts.correlations
                        ],
                        recommendations=list(self.recommendations),
                    )
                )
        return _cap(findings)


class ExternalTransferSequenceRule(Rule):
    """File access followed within 24h by an external upload sharing user/host."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="external-transfer-sequence",
            name="Potential external transfer sequence",
            description=(
                "A named file appears in file-access context, then an upload to "
                "an external destination occurs within 24 hours, with a shared "
                "user or host linking the two observations."
            ),
            severity="high",
            recommendations=[
                "Verify whether the destination domain or IP is authorized.",
                "Inspect the related file-access evidence for what was copied.",
                "Review custody and endpoint coverage for the gap window.",
                "Interview or validate with the relevant account owner.",
            ],
        )

    def evaluate(self, facts: FactView) -> list[ProposedFinding]:
        uploads = []
        for (evidence_id, locator_key), members in facts.units.items():
            context = members[0].context
            lowered = context.casefold()
            keyword_at = min(
                (lowered.find(word) for word in UPLOAD_KEYWORDS if word in lowered),
                default=None,
            )
            if keyword_at is None:
                continue
            # Destinations named after the upload keyword: source addresses
            # written before it (e.g. the sender host) do not qualify.
            dests = [
                m for m in members
                if m.artifact_type in ("IP_ADDRESS", "DOMAIN")
                and m.span is not None
                and m.span[0] > keyword_at
            ]
            times = facts.timestamps_on_unit(evidence_id, locator_key)
            if not dests or not times:
                continue
            uploads.append((evidence_id, locator_key, dests, times))
        grouped: dict[tuple[tuple[str, ...], str], dict] = {}
        for up_evidence, up_key, dests, up_times in uploads:
            for dest in dests:
                for up_time in up_times:
                    for (f_evidence, f_key), members in facts.units.items():
                        files = [m for m in members if m.artifact_type == "FILE_NAME"]
                        if not files:
                            continue
                        for file_time in facts.timestamps_on_unit(f_evidence, f_key):
                            delta = (up_time - file_time).total_seconds()
                            if not 0 <= delta <= EXTERNAL_WINDOW_HOURS * 3600:
                                continue
                            link = self._shared_link(facts, up_evidence, up_key, f_evidence, f_key)
                            if link is None:
                                continue
                            link_kind, link_value = link
                            file_values = sorted({m.normalized_value for m in files})
                            key = (tuple(file_values), dest.normalized_value)
                            slot = grouped.setdefault(key, {
                                "pairs": [],
                                "link_kinds": set(),
                                "evidence_ids": set(),
                                "artifact_ids": set(),
                            })
                            slot["pairs"].append((file_time, up_time))
                            slot["link_kinds"].add(f"{link_kind}:{link_value}")
                            slot["evidence_ids"] |= {up_evidence, f_evidence}
                            slot["artifact_ids"] |= (
                                {dest.id}
                                | {m.id for m in files}
                                | {m.id for m in facts.units[(up_evidence, up_key)]
                                   if m.artifact_type == "TIMESTAMP"}
                                | {m.id for m in facts.units[(f_evidence, f_key)]
                                   if m.artifact_type == "TIMESTAMP"}
                            )
        findings = []
        for (file_values, dest_value), slot in sorted(grouped.items()):
            pairs = sorted(slot["pairs"])
            earliest_access, earliest_upload = pairs[0]
            link_detail = ", ".join(sorted(slot["link_kinds"]))
            confidence = 10 + 25 + 15 + 20
            factors = [
                {"factor": "shared link", "weight": 25, "detail": link_detail},
                {"factor": "file referenced", "weight": 15,
                 "detail": f"files: {', '.join(file_values)}"},
                {"factor": "temporal order within 24h", "weight": 20,
                 "detail": (
                     f"access {earliest_access.isoformat()} then upload "
                     f"{earliest_upload.isoformat()} (within 24h window)"
                 )},
            ]
            if facts.all_verified:
                factors.append(
                    {"factor": "all contributing evidence verified",
                     "weight": 10,
                     "detail": "integrity gate passed at generation"})
                confidence += 10
            occurrences = (
                f" Observed {len(pairs)} times." if len(pairs) > 1 else ""
            )
            findings.append(
                ProposedFinding(
                    rule_id=self.rule_id,
                    rule_version=RULE_VERSION,
                    title=(
                        "Potential external transfer sequence: "
                        f"{', '.join(file_values)} then {dest_value}"
                    ),
                    summary=(
                        f"{', '.join(file_values)} appears in file-access "
                        f"context at {earliest_access.isoformat()}, followed by an "
                        f"upload to {dest_value} at "
                        f"{earliest_upload.isoformat()} sharing {link_detail}."
                        f"{occurrences} The sequence is consistent with "
                        "data movement off the host; it does not prove it."
                    ),
                    severity=self.severity,
                    confidence=min(confidence, 100),
                    factors=factors,
                    evidence_ids=sorted(slot["evidence_ids"]),
                    artifact_ids=sorted(slot["artifact_ids"]),
                    correlation_ids=[
                        facts.correlations[key]
                        for key in {(t, dest_value) for t in ("IP_ADDRESS", "DOMAIN")}
                        if key in facts.correlations
                    ],
                    recommendations=[
                        r for r in self.recommendations
                    ],
                )
            )
        return _cap(findings)

    @staticmethod
    def _shared_link(
        facts: FactView,
        up_evidence: int,
        up_key: str,
        f_evidence: int,
        f_key: str,
    ) -> tuple[str, str] | None:
        up_members = facts.units[(up_evidence, up_key)]
        f_members = facts.units[(f_evidence, f_key)]
        up_users = {m.normalized_value for m in up_members if m.artifact_type == "USERNAME"}
        f_users = {m.normalized_value for m in f_members if m.artifact_type == "USERNAME"}
        shared_users = up_users & f_users
        if shared_users:
            return ("user", sorted(shared_users)[0])
        up_hosts = {m.normalized_value for m in up_members if m.artifact_type == "HOSTNAME"}
        f_hosts = {m.normalized_value for m in f_members if m.artifact_type == "HOSTNAME"}
        shared_hosts = up_hosts & f_hosts
        if shared_hosts:
            return ("host", sorted(shared_hosts)[0])
        return None


RULES: list[Rule] = [
    IdentityRecurrenceRule(),
    RemovableMediaSessionRule(),
    ExternalTransferSequenceRule(),
]


def evaluate_all(facts: FactView) -> list[ProposedFinding]:
    """Run every rule deterministically, sorted by rule then confidence."""
    findings = []
    for rule in RULES:
        findings.extend(rule.evaluate(facts))
    findings.sort(key=lambda f: (f.rule_id, -f.confidence, f.title))
    return findings
