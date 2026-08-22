from __future__ import annotations

from datetime import datetime

from .case_state import evidence_ids_by_kind
from .contracts import CaseInput, CaseState, DecisionReport, Evidence, EvidenceKind, Finding
from .skills.refund_dispute import RefundDisputeSkill


class EvidenceFusion:
    def fuse(
        self, case: CaseInput, state: CaseState, skill: RefundDisputeSkill
    ) -> DecisionReport:
        state = state.model_copy(deep=True)
        state.findings = self._validated_findings(state)
        available_kinds = {item.kind for item in state.evidence.values()}
        state.missing_evidence = [
            kind.value for kind in skill.required_evidence if kind not in available_kinds
        ]

        refunds = self._of_kind(state, EvidenceKind.REFUND)
        payments = self._of_kind(state, EvidenceKind.PAYMENT)
        after_sales = self._of_kind(state, EvidenceKind.AFTER_SALES)
        policies = self._of_kind(state, EvidenceKind.POLICY)

        responsible_party = "undetermined"
        decision = "manual_review"
        action = "补充缺失证据后人工复检"
        review = bool(state.missing_evidence)

        approved = next((item for item in after_sales if item.facts.get("status") == "approved"), None)
        policy = policies[0] if policies else None
        if not review and approved and policy:
            rules = policy.facts["rules"]
            if not refunds:
                approved_at = datetime.fromisoformat(approved.facts["approved_at"])
                elapsed_hours = (case.current_time - approved_at).total_seconds() / 3600
                if elapsed_hours > rules["initiate_within_hours"]:
                    responsible_party = "platform"
                    decision = "refund_not_initiated_overdue"
                    action = "立即发起退款并排查售后到退款链路"
                else:
                    responsible_party = "none"
                    decision = "refund_pending_within_sla"
                    action = "等待退款发起时限并向用户同步进度"
            else:
                latest = max(refunds, key=lambda item: item.occurred_at or case.occurred_at)
                if latest.facts["status"] == "processing":
                    initiated = datetime.fromisoformat(latest.facts["initiated_at"])
                    elapsed_days = (case.current_time - initiated).total_seconds() / 86400
                    if elapsed_days <= rules["arrival_within_days"]:
                        responsible_party = "none"
                        decision = "refund_processing_within_sla"
                        action = "告知用户预计到账时间并继续跟踪"
                    else:
                        responsible_party = "payment_channel"
                        decision = "refund_arrival_overdue"
                        action = "向支付渠道核验退款流水"
                        review = True
                elif latest.facts["status"] == "succeeded":
                    matching_credit = any(
                        item.facts.get("event_type") == "credit"
                        and item.facts.get("status") == "succeeded"
                        and item.facts.get("amount") == latest.facts.get("amount")
                        for item in payments
                    )
                    if matching_credit:
                        responsible_party = "none"
                        decision = "refund_completed"
                        action = "向用户提供退款流水与到账时间"
                    else:
                        conflict = "退款系统显示成功，但支付记录中不存在匹配的入账流水"
                        state.conflicts.append(conflict)
                        state.findings.append(
                            Finding(
                                finding_id="fusion-refund-payment-conflict",
                                category="fact_conflict",
                                claim=conflict,
                                evidence_ids=[latest.evidence_id]
                                + evidence_ids_by_kind(state, EvidenceKind.PAYMENT),
                                severity="critical",
                                review_recommended=True,
                            )
                        )
                        responsible_party = "undetermined"
                        decision = "refund_record_conflict"
                        action = "携退款流水号向支付渠道核验，并转人工复检"
                        review = True

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
            responsible_party=responsible_party,
            decision=decision,
            timeline=state.timeline,
            findings=state.findings,
            evidence_ids=sorted(state.evidence),
            policy_evidence_ids=evidence_ids_by_kind(state, EvidenceKind.POLICY),
            conflicts=state.conflicts,
            missing_evidence=state.missing_evidence,
            recommended_action=action,
            review_required=review,
            trace=state.trace,
        )

    @staticmethod
    def _validated_findings(state: CaseState) -> list[Finding]:
        available = set(state.evidence)
        seen: set[tuple[str, str, tuple[str, ...]]] = set()
        validated: list[Finding] = []
        for finding in state.findings:
            if not finding.evidence_ids or not set(finding.evidence_ids).issubset(available):
                continue
            key = (finding.category, finding.claim, tuple(sorted(finding.evidence_ids)))
            if key not in seen:
                seen.add(key)
                validated.append(finding)
        return validated

    @staticmethod
    def _of_kind(state: CaseState, kind: EvidenceKind) -> list[Evidence]:
        return [item for item in state.evidence.values() if item.kind == kind]

