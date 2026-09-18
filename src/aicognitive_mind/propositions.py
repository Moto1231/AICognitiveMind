import re
from typing import Literal, Protocol

from pydantic import BaseModel

from aicognitive_mind.evidence import EvidenceAssessment


class PropositionEvidence(BaseModel):
    """Normalized proposition candidate used only for contradiction comparison."""

    subject: str
    attribute: str
    value: str
    assessment: EvidenceAssessment
    evidence_role: Literal["claim", "clarification_resolution"] = "claim"


class PropositionDetector(Protocol):
    """Extract contradiction-comparable propositions from evidence text."""

    def detect(
        self,
        text: str,
        *,
        speaker: str | None,
        resolved_subject: str | None,
        assessment: EvidenceAssessment,
    ) -> tuple[PropositionEvidence, ...]: ...


class CompositePropositionDetector:
    def __init__(self, detectors: tuple[PropositionDetector, ...]) -> None:
        self._detectors = detectors

    def detect(
        self,
        text: str,
        *,
        speaker: str | None,
        resolved_subject: str | None,
        assessment: EvidenceAssessment,
    ) -> tuple[PropositionEvidence, ...]:
        return tuple(
            proposition
            for detector in self._detectors
            for proposition in detector.detect(
                text,
                speaker=speaker,
                resolved_subject=resolved_subject,
                assessment=assessment,
            )
        )


_BIRTHDAY_VALUE_PATTERN = (
    r"(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?"
)


class BirthdayPropositionDetector:
    """First V0.1 proposition adapter; intentionally narrow and replaceable."""

    def detect(
        self,
        text: str,
        *,
        speaker: str | None,
        resolved_subject: str | None,
        assessment: EvidenceAssessment,
    ) -> tuple[PropositionEvidence, ...]:
        explicit = re.search(
            rf"([A-Za-z][A-Za-z' -]{{0,79}}?)['’]s\s+birthday\s+is\s+"
            rf"{_BIRTHDAY_VALUE_PATTERN}",
            text,
            flags=re.IGNORECASE,
        )
        subject: str | None = None
        month: str | None = None
        day: str | None = None
        if explicit is not None:
            subject = " ".join(explicit.group(1).split())
            month = explicit.group(2)
            day = explicit.group(3)
        else:
            first_person = re.search(
                rf"\bmy\s+birthday\s+is\s+{_BIRTHDAY_VALUE_PATTERN}",
                text,
                flags=re.IGNORECASE,
            )
            if first_person is not None and speaker:
                subject = speaker.strip()
                month = first_person.group(1)
                day = first_person.group(2)
            else:
                pronoun = re.search(
                    rf"\b(?:his|her|their)\s+birthday\s+is\s+"
                    rf"{_BIRTHDAY_VALUE_PATTERN}",
                    text,
                    flags=re.IGNORECASE,
                )
                if pronoun is not None and resolved_subject:
                    subject = resolved_subject.strip()
                    month = pronoun.group(1)
                    day = pronoun.group(2)

        if not subject or month is None or day is None:
            return ()

        return (
            PropositionEvidence(
                subject=subject,
                attribute="birthday",
                value=f"{month.capitalize()} {int(day)}",
                assessment=assessment,
            ),
        )


def first_conflict(
    items: list[PropositionEvidence],
) -> tuple[PropositionEvidence, PropositionEvidence] | None:
    for position, first in enumerate(items):
        for second in items[position + 1 :]:
            same_subject = first.subject.casefold() == second.subject.casefold()
            same_attribute = first.attribute.casefold() == second.attribute.casefold()
            different_value = first.value.casefold() != second.value.casefold()
            if same_subject and same_attribute and different_value:
                return first, second
    return None


class ClarificationRequest(BaseModel):
    subject: str
    attribute: str
    values: tuple[str, ...]
    question: str


def clarification_request(
    first: PropositionEvidence,
    second: PropositionEvidence,
    current_speaker: str | None,
) -> ClarificationRequest:
    values = tuple(sorted({first.value, second.value}, key=str.casefold))
    choices = " or ".join(values)
    speaker = (current_speaker or "").strip()
    if speaker and speaker.casefold() == first.subject.casefold():
        question = (
            f"I have conflicting information about your {first.attribute}. "
            f"Is it {choices}?"
        )
    else:
        question = (
            f"I have conflicting information about {first.subject}'s {first.attribute}. "
            f"Is it {choices}?"
        )
    return ClarificationRequest(
        subject=first.subject,
        attribute=first.attribute,
        values=values,
        question=question,
    )


def clarification_question(
    first: PropositionEvidence,
    second: PropositionEvidence,
    current_speaker: str | None,
) -> str:
    return clarification_request(first, second, current_speaker).question


def clarification_resolution_for_conflict(
    items: list[PropositionEvidence],
    first: PropositionEvidence,
    second: PropositionEvidence,
) -> PropositionEvidence | None:
    conflict_values = {first.value.casefold(), second.value.casefold()}
    for item in items:
        if item.evidence_role != "clarification_resolution":
            continue
        if item.subject.casefold() != first.subject.casefold():
            continue
        if item.attribute.casefold() != first.attribute.casefold():
            continue
        if item.value.casefold() in conflict_values:
            return item
    return None
