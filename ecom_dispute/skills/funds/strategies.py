from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ...case_state import evidence_ids_by_kind
from ...contracts import CaseInput, CaseState, EvidenceKind, Finding
from ..base import DecisionOutcome


@dataclass(frozen=True)
class RefundProgressStrategy:
    def decide(
        self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]
    ) -> DecisionOutcome:
        if missing_evidence:
            return DecisionOutcome()
        refunds = [item for item in state.evidence.values() if item.kind == EvidenceKind.REFUND]
        payments = [item for item in state.evidence.values() if item.kind == EvidenceKind.PAYMENT]
        after_sales = [
            item for item in state.evidence.values() if item.kind == EvidenceKind.AFTER_SALES
        ]
        policies = [item for item in state.evidence.values() if item.kind == EvidenceKind.POLICY]
        approved = next(
            (item for item in after_sales if item.facts.get("status") == "approved"), None
        )
        if not approved or not policies:
            return DecisionOutcome()
        rules = policies[0].facts["rules"]
        if not refunds:
            approved_at = datetime.fromisoformat(approved.facts["approved_at"])
            elapsed_hours = (case.current_time - approved_at).total_seconds() / 3600
            if elapsed_hours > rules["initiate_within_hours"]:
                return DecisionOutcome(
                    responsible_party="platform",
                    decision="refund_not_initiated_overdue",
                    recommended_action="立即发起退款并排查售后到退款链路",
                    review_required=False,
                )
            return DecisionOutcome(
                responsible_party="none",
                decision="refund_pending_within_sla",
                recommended_action="等待退款发起时限并向用户同步进度",
                review_required=False,
            )

        latest = max(refunds, key=lambda item: item.occurred_at or case.occurred_at)
        if latest.facts["status"] == "processing":
            initiated = datetime.fromisoformat(latest.facts["initiated_at"])
            elapsed_days = (case.current_time - initiated).total_seconds() / 86400
            if elapsed_days <= rules["arrival_within_days"]:
                return DecisionOutcome(
                    responsible_party="none",
                    decision="refund_processing_within_sla",
                    recommended_action="告知用户预计到账时间并继续跟踪",
                    review_required=False,
                )
            return DecisionOutcome(
                responsible_party="payment_channel",
                decision="refund_arrival_overdue",
                recommended_action="向支付渠道核验退款流水",
                review_required=True,
            )

        if latest.facts["status"] == "succeeded":
            matching_credit = any(
                item.facts.get("event_type") == "credit"
                and item.facts.get("status") == "succeeded"
                and item.facts.get("amount") == latest.facts.get("amount")
                for item in payments
            )
            if matching_credit:
                return DecisionOutcome(
                    responsible_party="none",
                    decision="refund_completed",
                    recommended_action="向用户提供退款流水与到账时间",
                    review_required=False,
                )
            conflict = "退款系统显示成功，但支付记录中不存在匹配的入账流水"
            finding = Finding(
                finding_id="fusion-refund-payment-conflict",
                category="fact_conflict",
                claim=conflict,
                evidence_ids=[latest.evidence_id]
                + evidence_ids_by_kind(state, EvidenceKind.PAYMENT),
                severity="critical",
                review_recommended=True,
            )
            return DecisionOutcome(
                responsible_party="undetermined",
                decision="refund_record_conflict",
                recommended_action="携退款流水号向支付渠道核验，并转人工复检",
                review_required=True,
                findings=[finding],
                conflicts=[conflict],
            )
        return DecisionOutcome()
