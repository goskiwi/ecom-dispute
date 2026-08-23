from __future__ import annotations

from dataclasses import dataclass

from ..contracts import CaseInput, CaseState, EvidenceKind
from .base import DecisionOutcome


@dataclass(frozen=True)
class StatusEvidenceStrategy:
    evidence_kind: EvidenceKind
    outcomes: dict[str, tuple[str, str, str, bool]]
    missing_action: str

    def decide(
        self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]
    ) -> DecisionOutcome:
        evidence = [item for item in state.evidence.values() if item.kind == self.evidence_kind]
        if missing_evidence or not evidence:
            return DecisionOutcome(recommended_action=self.missing_action)
        status = str(evidence[0].facts.get("status", "unknown"))
        outcome = self.outcomes.get(status)
        if not outcome:
            return DecisionOutcome(recommended_action=f"未知状态 {status}，补充证据后人工复检")
        responsible_party, decision, action, review_required = outcome
        return DecisionOutcome(
            responsible_party=responsible_party,
            decision=decision,
            recommended_action=action,
            review_required=review_required,
        )


def status_strategy(
    evidence_kind: EvidenceKind,
    missing_action: str,
    **outcomes: tuple[str, str, str, bool],
) -> StatusEvidenceStrategy:
    return StatusEvidenceStrategy(evidence_kind, outcomes, missing_action)
