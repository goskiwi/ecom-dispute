from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ...contracts import CaseInput, CaseState, EvidenceKind
from ..base import DecisionOutcome


def _evidence(state: CaseState, kind: EvidenceKind) -> list:
    return [item for item in state.evidence.values() if item.kind == kind]


@dataclass(frozen=True)
class MerchantNotShippedStrategy:
    def decide(
        self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]
    ) -> DecisionOutcome:
        if missing_evidence:
            return DecisionOutcome()
        orders = _evidence(state, EvidenceKind.ORDER)
        logistics = _evidence(state, EvidenceKind.LOGISTICS)
        policies = _evidence(state, EvidenceKind.POLICY)
        if not orders or not policies:
            return DecisionOutcome()
        picked_up = any(
            item.facts.get("event_type") in {"picked_up", "in_transit", "out_for_delivery"}
            for item in logistics
        )
        if picked_up:
            return DecisionOutcome(
                responsible_party="none",
                decision="shipment_already_picked_up",
                recommended_action="转入物流运输阶段继续跟踪",
                review_required=False,
            )
        created_at = datetime.fromisoformat(orders[0].facts["created_at"])
        elapsed = (case.current_time - created_at).total_seconds() / 3600
        if elapsed > policies[0].facts["rules"]["merchant_ship_hours"]:
            return DecisionOutcome(
                responsible_party="merchant",
                decision="merchant_ship_overdue",
                recommended_action="催促商家发货并按政策处理超时",
                review_required=False,
            )
        return DecisionOutcome(
            responsible_party="none",
            decision="merchant_ship_within_sla",
            recommended_action="订单仍在商家发货时限内",
            review_required=False,
        )


@dataclass(frozen=True)
class DeliveredNotReceivedStrategy:
    def decide(
        self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]
    ) -> DecisionOutcome:
        if missing_evidence:
            return DecisionOutcome()
        delivered = any(
            item.facts.get("event_type") == "delivered"
            for item in _evidence(state, EvidenceKind.LOGISTICS)
        )
        if not delivered:
            return DecisionOutcome(
                responsible_party="undetermined",
                decision="delivery_not_marked_delivered",
                recommended_action="转入普通物流状态排查",
                review_required=True,
            )
        proofs = _evidence(state, EvidenceKind.DELIVERY_PROOF)
        if not proofs:
            return DecisionOutcome(
                responsible_party="logistics_provider",
                decision="delivery_proof_missing",
                recommended_action="要求承运商补充签收证明并转人工复检",
                review_required=True,
            )
        return DecisionOutcome(
            responsible_party="undetermined",
            decision="delivery_receipt_disputed",
            recommended_action="核对签收人、地址与用户陈述后人工复检",
            review_required=True,
        )


@dataclass(frozen=True)
class CancellationInTransitStrategy:
    def decide(
        self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]
    ) -> DecisionOutcome:
        if missing_evidence:
            return DecisionOutcome()
        requests = _evidence(state, EvidenceKind.CANCELLATION_REQUEST)
        logistics = _evidence(state, EvidenceKind.LOGISTICS)
        refunds = _evidence(state, EvidenceKind.REFUND)
        if not requests:
            return DecisionOutcome()
        requested_at = datetime.fromisoformat(requests[0].facts["requested_at"])
        pickup_times = [
            item.occurred_at
            for item in logistics
            if item.facts.get("event_type") == "picked_up" and item.occurred_at
        ]
        if refunds:
            return DecisionOutcome(
                responsible_party="none",
                decision="cancellation_completed",
                recommended_action="向用户提供取消和退款流水",
                review_required=False,
            )
        if pickup_times and requested_at < min(pickup_times):
            return DecisionOutcome(
                responsible_party="merchant",
                decision="cancel_before_pickup_but_shipped",
                recommended_action="拦截包裹并核验商家取消处理链路",
                review_required=True,
            )
        if pickup_times:
            return DecisionOutcome(
                responsible_party="none",
                decision="cancel_after_pickup",
                recommended_action="按运输中取消政策执行拒收或退回",
                review_required=False,
            )
        return DecisionOutcome(
            responsible_party="platform",
            decision="cancellation_refund_missing",
            recommended_action="核验取消受理状态并发起应退资金",
            review_required=True,
        )
