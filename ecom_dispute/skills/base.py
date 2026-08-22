from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..contracts import CaseInput, CaseState, EvidenceKind, Finding


@dataclass(frozen=True)
class DecisionOutcome:
    responsible_party: str = "undetermined"
    decision: str = "manual_review"
    recommended_action: str = "补充缺失证据后人工复检"
    review_required: bool = True
    findings: list[Finding] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


class Skill(Protocol):
    name: str
    business_type: str
    allowed_tools: tuple[str, ...]
    required_evidence: tuple[EvidenceKind, ...]

    def decide(
        self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]
    ) -> DecisionOutcome: ...


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        if skill.business_type in self._skills:
            raise ValueError(f"duplicate skill for business type: {skill.business_type}")
        self._skills[skill.business_type] = skill

    def resolve(self, business_type: str) -> Skill:
        try:
            return self._skills[business_type]
        except KeyError as exc:
            raise ValueError(f"no skill for business type: {business_type}") from exc

    @property
    def business_types(self) -> set[str]:
        return set(self._skills)
