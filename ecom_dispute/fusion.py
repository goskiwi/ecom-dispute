from __future__ import annotations

from .case_state import evidence_ids_by_kind
from .contracts import (
    CaseInput,
    CaseState,
    DecisionReport,
    Evidence,
    EvidenceKind,
    Finding,
    StatementType,
    TemporalStatus,
)
from .skills import Skill


class EvidenceFusion:
    def fuse(
        self,
        case: CaseInput,
        state: CaseState,
        skill: Skill,
    ) -> DecisionReport:
        state = state.model_copy(deep=True)
        state.findings = self._validated_findings(state)
        available_kinds = {item.kind for item in state.evidence.values()}
        state.missing_evidence = [
            kind.value for kind in skill.required_evidence if kind not in available_kinds
        ]

        refunds = self._of_kind(state, EvidenceKind.REFUND)
        payments = self._of_kind(state, EvidenceKind.PAYMENT)
        logistics = self._of_kind(state, EvidenceKind.LOGISTICS)
        self._fuse_conversation_facts(state, refunds, payments, logistics)
        outcome = skill.decide(case, state, tuple(state.missing_evidence))
        state.findings.extend(outcome.findings)
        for conflict in outcome.conflicts:
            if conflict not in state.conflicts:
                state.conflicts.append(conflict)

        state.trace.append(
            {
                "stage": "evidence_fusion",
                "validated_findings": len(state.findings),
                "conflicts": len(state.conflicts),
                "missing_evidence": state.missing_evidence,
            }
        )
        return DecisionReport(
            case_id=case.case_id,
            dispute_type=skill.name,
            responsible_party=outcome.responsible_party,
            decision=outcome.decision,
            timeline=state.timeline,
            findings=state.findings,
            evidence=sorted(state.evidence.values(), key=lambda item: item.evidence_id),
            evidence_ids=sorted(state.evidence),
            policy_evidence_ids=evidence_ids_by_kind(state, EvidenceKind.POLICY),
            conflicts=state.conflicts,
            missing_evidence=state.missing_evidence,
            recommended_action=outcome.recommended_action,
            review_required=outcome.review_required,
            trace=state.trace,
        )

    @staticmethod
    def _validated_findings(state: CaseState) -> list[Finding]:
        available = set(state.evidence)
        seen: set[tuple[str, str, str | None, str | None, tuple[str, ...]]] = set()
        validated: list[Finding] = []
        for finding in state.findings:
            if not finding.evidence_ids or not set(finding.evidence_ids).issubset(available):
                continue
            key = (
                finding.category,
                finding.claim,
                finding.statement_type.value if finding.statement_type else None,
                finding.temporal_status.value if finding.temporal_status else None,
                tuple(sorted(finding.evidence_ids)),
            )
            if key not in seen:
                seen.add(key)
                validated.append(finding)
        return validated

    @staticmethod
    def _of_kind(state: CaseState, kind: EvidenceKind) -> list[Evidence]:
        return [item for item in state.evidence.values() if item.kind == kind]

    @staticmethod
    def _fuse_conversation_facts(
        state: CaseState,
        refunds: list[Evidence],
        payments: list[Evidence],
        logistics: list[Evidence],
    ) -> None:
        succeeded_refund = any(item.facts.get("status") == "succeeded" for item in refunds)
        matching_credit = any(
            item.facts.get("event_type") == "credit" and item.facts.get("status") == "succeeded"
            for item in payments
        )
        conversation_ids = evidence_ids_by_kind(state, EvidenceKind.CONVERSATION)
        negative_refund_ids = [
            item.evidence_id
            for item in state.evidence.values()
            if item.kind == EvidenceKind.QUERY and item.source == "query:refunds"
        ]
        fact_ids = [
            item.evidence_id for item in refunds + payments + logistics
        ] + negative_refund_ids
        delivered_events = [
            item for item in logistics if item.facts.get("event_type") == "delivered"
        ]

        for finding in list(state.findings):
            conflict: str | None = None
            if finding.category == "agent_commitment":
                if not refunds and (
                    (
                        finding.statement_type == StatementType.REFUND_INITIATED
                        and finding.temporal_status
                        in {TemporalStatus.CURRENT, TemporalStatus.COMPLETED}
                    )
                    or (
                        finding.statement_type == StatementType.REFUND_PROCESSING
                        and finding.temporal_status == TemporalStatus.CURRENT
                    )
                ):
                    conflict = "客服称退款已进入处理链路，但业务系统不存在退款记录"
                elif (
                    finding.statement_type == StatementType.REFUND_COMPLETED
                    and finding.temporal_status == TemporalStatus.COMPLETED
                    and not succeeded_refund
                ):
                    conflict = "客服称退款已完成，但退款系统不存在成功记录"
                elif (
                    finding.statement_type == StatementType.DELIVERY_COMPLETED
                    and finding.temporal_status == TemporalStatus.COMPLETED
                    and not delivered_events
                ):
                    conflict = "客服称包裹已送达，但物流系统不存在送达事件"
            elif (
                finding.category == "user_claim"
                and finding.statement_type == StatementType.REFUND_NOT_RECEIVED
                and finding.temporal_status == TemporalStatus.CURRENT
                and matching_credit
            ):
                conflict = "用户称退款未到账，但支付系统存在成功入账记录"
            elif (
                finding.category == "user_claim"
                and finding.statement_type == StatementType.REFUND_NOT_INITIATED
                and finding.temporal_status == TemporalStatus.CURRENT
                and refunds
            ):
                conflict = "用户称退款未发起，但退款系统存在处理记录"
            elif (
                finding.category == "user_claim"
                and finding.statement_type == StatementType.DELIVERY_NOT_RECEIVED
                and finding.temporal_status == TemporalStatus.CURRENT
                and delivered_events
            ):
                conflict = "用户称未收到货，但物流系统存在送达事件"

            if not conflict or conflict in state.conflicts:
                continue
            state.conflicts.append(conflict)
            state.findings.append(
                Finding(
                    finding_id=f"conversation-fact-conflict-{len(state.conflicts)}",
                    category="conversation_fact_conflict",
                    claim=conflict,
                    evidence_ids=conversation_ids + fact_ids,
                    severity="warning",
                    review_recommended=False,
                )
            )
