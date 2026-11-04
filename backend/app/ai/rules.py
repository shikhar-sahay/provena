"""Rule-based investigative assistance over extracted facts.

Rules match structured patterns (shared identities, devices, hosts, ordered
transfers) and produce proposed findings with deterministic weighted
confidence. A finding is decision support, never a conclusion: scores rank
and prioritize, they are not calibrated probabilities, and every factor is
recorded for the Why view. No rule determines guilt, intent or certainty.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

RULE_VERSION = "2"

UPLOAD_KEYWORDS = ("upload", "uploaded", "exfil", "sent", "transmit")
EXTERNAL_WINDOW_HOURS = 24
MAX_FINDINGS_PER_RULE = 25
MAX_TRANSFER_PAIRS = 100_000


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
    support_key: str | None = None
    input_sha256: str | None = None
    upload_keyword_offsets: tuple[int, ...] | None = None
    file_access: bool | None = None
    verified: bool = True


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

    support_keys: list[str] = field(default_factory=list)
    coverage: dict = field(default_factory=dict)

    def inputs_key(self) -> str:
        canonical = json.dumps(
            {
                "rule_id": self.rule_id,
                "rule_version": self.rule_version,
                "support": sorted(self.support_keys) if self.support_keys else sorted(self.artifact_ids),
                "claim": [self.title, self.summary, self.severity, self.confidence, self.factors],
                "coverage": self.coverage,
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
        self.rule_coverage: dict[str, dict] = {}
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

    def supporting_verified(self, members: list[ArtifactFact]) -> bool:
        return bool(members) and all(m.verified for m in members)

    def record_patterns(self, members: list[ArtifactFact]) -> int:
        # Splitting or copying logs does not create independent observations.
        return len({tuple(sorted({(a.artifact_type, a.normalized_value)
                    for a in self.units[(m.evidence_id, m.locator_key)]})) for m in members})

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
    return findings


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
            patterns = facts.record_patterns(members)
            additional = min(15 * max(patterns - 2, 0), 65)
            confidence = 30 + additional
            factors = [
                {"factor": "identity recurrence", "weight": 30,
                 "detail": f"{value} in {len(evidence_ids)} evidence items"},
                {"factor": "distinct supporting record patterns", "weight": additional,
                 "detail": f"{patterns} patterns; duplicates and file partitions do not establish independent sources"},
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
    """Conservative record-level removable-media observations."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="removable-media-session",
            name="Potential removable-media session",
            description=(
                "Removable-media entities share one structural record. Missing or "
                "ambiguous fields remain weak observations, not established sessions."
            ),
            severity="medium",
            recommendations=[
                "Review removable-media custody and activity for the device.",
                "Inspect file-access evidence for copies to removable volumes.",
                "Validate whether the account owner used the device.",
            ],
        )

    def evaluate(self, facts: FactView) -> list[ProposedFinding]:
        grouped = {}
        for (evidence_id, record), members in sorted(facts.units.items()):
            devices = sorted({m.normalized_value for m in members if m.artifact_type == "USB_DEVICE"})
            if not devices:
                continue
            users = sorted({m.normalized_value for m in members if m.artifact_type == "USERNAME"})
            hosts = sorted({m.normalized_value for m in members if m.artifact_type == "HOSTNAME"})
            # Only a shared source record links these entities. Whole-file
            # co-occurrence never creates a user/device/host association.
            key = (tuple(devices), tuple(users), tuple(hosts))
            grouped.setdefault(key, []).extend(m for m in members if m.artifact_type in
                                              {"USB_DEVICE", "USERNAME", "HOSTNAME", "TIMESTAMP"})
        findings = []
        for (devices, users, hosts), members in sorted(grouped.items()):
            linked = len(devices) == len(users) == len(hosts) == 1
            factors = [{"factor": "device identifier recorded", "weight": 20,
                        "detail": "Identifier extracted from an addressable source record"}]
            if linked:
                factors += [{"factor": "single user and host co-recorded", "weight": 35,
                             "detail": "Structural record association; not proof of an actual session or device use"}]
            if facts.supporting_verified(members):
                factors.append({"factor": "supporting input verified", "weight": 10,
                                "detail": "Only the cited supporting evidence passed the integrity gate"})
            title = (f"Co-recorded removable-media entities: {users[0]} on {hosts[0]} ({devices[0]})"
                     if linked else "Ambiguous removable-media observation")
            summary = ("A single source record contains one user, host and device identifier. "
                       "This is record-level co-occurrence, not an established session or proof of use."
                       if linked else "A device identifier is recorded, but missing or multiple users, hosts or devices "
                       "prevent an unambiguous association. No session relationship is established.")
            findings.append(ProposedFinding(self.rule_id, RULE_VERSION, title, summary,
                self.severity if linked else "low", sum(f['weight'] for f in factors), factors,
                sorted({m.evidence_id for m in members}), sorted({m.id for m in members}),
                sorted({facts.correlations[(m.artifact_type, m.normalized_value)] for m in members
                        if (m.artifact_type, m.normalized_value) in facts.correlations}),
                list(self.recommendations)))
        return _cap(findings)


class ExternalTransferSequenceRule(Rule):
    """File access followed within 24h by an external upload sharing user/host."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="external-transfer-sequence",
            name="Potential upload sequence",
            description=(
                "A named file appears in file-access context, then an upload to "
                "a recorded destination occurs within 24 hours, with a shared "
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
            offsets = [offset for m in members for offset in (m.upload_keyword_offsets or ())]
            if any(m.upload_keyword_offsets is not None for m in members):
                keyword_at = min(offsets, default=None)
            if keyword_at is None:
                continue
            # Destinations named after the upload keyword: source addresses
            # written before it (e.g. the sender host) do not qualify.
            dests = [
                m for m in members
                if m.artifact_type in ("IP_ADDRESS", "DOMAIN")
                and m.span is not None
                and m.span[0] > (min(m.upload_keyword_offsets) if m.upload_keyword_offsets else keyword_at)
                and (m.upload_keyword_offsets is None or bool(m.upload_keyword_offsets))
            ]
            times = facts.timestamps_on_unit(evidence_id, locator_key)
            if not dests or not times:
                continue
            uploads.append((evidence_id, locator_key, dests, times))
        grouped: dict[tuple[tuple[str, ...], str], dict] = {}
        pair_checks = 0
        truncated = False
        for up_evidence, up_key, dests, up_times in uploads:
            for dest in dests:
                for up_time in up_times:
                    for (f_evidence, f_key), members in facts.units.items():
                        pair_checks += 1
                        if pair_checks > MAX_TRANSFER_PAIRS:
                            truncated = True
                            break
                        files = [m for m in members if m.artifact_type == "FILE_NAME"]
                        explicit_access = any(m.file_access for m in members) if any(m.file_access is not None for m in members) else any(
                            word in members[0].context.casefold() for word in ("read", "open", "access", "copy", "copied"))
                        if not files or not explicit_access:
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
                                "pairs": set(),
                                "link_kinds": set(),
                                "evidence_ids": set(),
                                "artifact_ids": set(),
                            })
                            slot["pairs"].add((file_time, up_time))
                            slot["link_kinds"].add(f"{link_kind}:{link_value}")
                            slot["evidence_ids"] |= {up_evidence, f_evidence}
                            slot["artifact_ids"] |= (
                                {dest.id}
                                | {m.id for m in files}
                                | {m.id for m in facts.units[(up_evidence, up_key)] + members
                                   if m.artifact_type in {"USERNAME", "HOSTNAME"}
                                   and m.normalized_value == link_value}
                                | {m.id for m in facts.units[(up_evidence, up_key)]
                                   if m.artifact_type == "TIMESTAMP"}
                                | {m.id for m in facts.units[(f_evidence, f_key)]
                                   if m.artifact_type == "TIMESTAMP"}
                            )
                    if truncated:
                        break
                if truncated:
                    break
            if truncated:
                break
        facts.rule_coverage[self.rule_id] = {"candidate_pairs_checked": min(pair_checks, MAX_TRANSFER_PAIRS),
            "evaluation_complete": not truncated, "pair_limit": MAX_TRANSFER_PAIRS}
        findings = []
        for (file_values, dest_value), slot in sorted(grouped.items()):
            pairs = sorted(slot["pairs"])
            earliest_access, earliest_upload = pairs[0]
            link_detail = ", ".join(sorted(slot["link_kinds"]))
            confidence = 25 + 15 + 20
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
            if facts.supporting_verified([m for m in facts.artifacts if m.id in slot["artifact_ids"]]):
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
                        "Potential upload sequence: "
                        f"{', '.join(file_values)} then {dest_value}"
                    ),
                    summary=(
                        f"{', '.join(file_values)} appears in file-access "
                        f"context at {earliest_access.isoformat()}, followed by an "
                        f"upload to {dest_value} at "
                        f"{earliest_upload.isoformat()} sharing {link_detail}."
                        f"{occurrences} The sequence is consistent with "
                        "a recorded upload sequence; destination ownership and actual data movement require independent validation."
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
        if len(shared_users) == 1:
            return ("user", sorted(shared_users)[0])
        up_hosts = {m.normalized_value for m in up_members if m.artifact_type == "HOSTNAME"}
        f_hosts = {m.normalized_value for m in f_members if m.artifact_type == "HOSTNAME"}
        shared_hosts = up_hosts & f_hosts
        if len(shared_hosts) == 1:
            return ("host", sorted(shared_hosts)[0])
        return None


RULES: list[Rule] = [
    IdentityRecurrenceRule(),
    RemovableMediaSessionRule(),
    ExternalTransferSequenceRule(),
]


class Evaluation(list[ProposedFinding]):
    def __init__(self):
        super().__init__()
        self.coverage: list[dict] = []


def evaluate_all(facts: FactView, per_rule_limit: int = MAX_FINDINGS_PER_RULE) -> Evaluation:
    """Explicit deterministic output limits; callers can request up to 200/rule."""
    findings = Evaluation()
    for rule in RULES:
        proposed = rule.evaluate(facts)
        proposed.sort(key=lambda f: (-f.confidence, f.title, f.inputs_key()))
        emitted = proposed[:per_rule_limit]
        findings.extend(emitted)
        findings.coverage.append({"rule_id": rule.rule_id, "rule_version": RULE_VERSION,
            "proposed_count": len(proposed), "emitted_count": len(emitted),
            "omitted_count": max(len(proposed) - len(emitted), 0), "output_limit": per_rule_limit,
            "evaluation_complete": True, **facts.rule_coverage.get(rule.rule_id, {})})
    findings.sort(key=lambda f: (f.rule_id, -f.confidence, f.title, f.inputs_key()))
    return findings
