from __future__ import annotations

from dataclasses import dataclass

from ...contracts import CaseInput, CaseState, EvidenceKind, Finding, SpeechAct
from ..base import DecisionOutcome


def _evidence_ids(state: CaseState) -> list[str]:
    ids = [
        item.evidence_id
        for item in state.evidence.values()
        if item.kind in {EvidenceKind.CONVERSATION, EvidenceKind.POLICY}
    ]
    ids.extend(
        evidence_id
        for finding in state.findings
        if finding.category == "conversation_fact_conflict"
        for evidence_id in finding.evidence_ids
    )
    return sorted(set(ids))


def _outcome(decision: str, claim: str, state: CaseState, violation: bool) -> DecisionOutcome:
    return DecisionOutcome(
        responsible_party="agent" if violation else "none",
        decision=decision,
        recommended_action=claim,
        review_required=violation,
        findings=[
            Finding(
                finding_id=f"compliance-{decision}",
                category="service_compliance",
                claim=claim,
                evidence_ids=_evidence_ids(state),
                severity="warning" if violation else "info",
                review_recommended=violation,
            )
        ],
    )


@dataclass(frozen=True)
class FalseBusinessStatementStrategy:
    def decide(self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]) -> DecisionOutcome:
        conflict = any(
            finding.category == "conversation_fact_conflict" for finding in state.findings
        )
        if conflict:
            return _outcome("false_statement_found", "客服业务陈述与系统事实冲突", state, True)
        return _outcome("false_statement_not_found", "未发现客服业务陈述冲突", state, False)


@dataclass(frozen=True)
class UnsupportedPromiseStrategy:
    def decide(self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]) -> DecisionOutcome:
        promise = any(
            finding.category == "agent_interaction_act"
            and finding.speech_act == SpeechAct.PROMISE
            for finding in state.findings
        )
        primary_requires_review = any(
            item.get("review_required") for item in state.candidate_decisions
        )
        primary_requires_review = primary_requires_review or any(
            finding.category == "conversation_fact_conflict" for finding in state.findings
        )
        if promise and primary_requires_review:
            return _outcome("unsupported_promise_found", "证据未闭环时客服做出结果承诺", state, True)
        return _outcome("unsupported_promise_not_found", "未发现无依据结果承诺", state, False)


@dataclass(frozen=True)
class MissingRequiredEscalationStrategy:
    def decide(self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]) -> DecisionOutcome:
        primary_requires_review = any(
            item.get("review_required") for item in state.candidate_decisions
        )
        primary_requires_review = primary_requires_review or any(
            finding.category == "conversation_fact_conflict" for finding in state.findings
        )
        escalated = any(
            finding.category == "agent_interaction_act"
            and finding.speech_act == SpeechAct.ESCALATION
            for finding in state.findings
        )
        if not primary_requires_review:
            return _outcome("escalation_not_required", "当前案件不要求升级复检", state, False)
        if escalated:
            return _outcome("required_escalation_present", "客服已按要求升级复检", state, False)
        return _outcome("required_escalation_missing", "冲突案件缺少必要的人工升级", state, True)
