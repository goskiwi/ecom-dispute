from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..contracts import CaseInput, CaseState, EvidenceKind, Finding
from .base import DecisionOutcome


@dataclass(frozen=True)
class DeliveryDelaySkill:
    name: str = "delivery_delay"
    business_type: str = "delivery"
    allowed_tools: tuple[str, ...] = (
        "get_order",
        "get_logistics_events",
        "read_policy",
    )
    required_evidence: tuple[EvidenceKind, ...] = (
        EvidenceKind.CONVERSATION,
        EvidenceKind.ORDER,
        EvidenceKind.LOGISTICS,
        EvidenceKind.POLICY,
    )

    def decide(
        self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]
    ) -> DecisionOutcome:
        if missing_evidence:
            return DecisionOutcome(recommended_action="补充订单或物流证据后人工复检")
        orders = [item for item in state.evidence.values() if item.kind == EvidenceKind.ORDER]
        logistics = [
            item for item in state.evidence.values() if item.kind == EvidenceKind.LOGISTICS
        ]
        policies = [item for item in state.evidence.values() if item.kind == EvidenceKind.POLICY]
        if not orders or not policies:
            return DecisionOutcome(recommended_action="补充订单或物流证据后人工复检")

        order = orders[0]
        rules = policies[0].facts["rules"]
        promised_at = datetime.fromisoformat(order.facts["promised_delivery_at"])
        created_at = datetime.fromisoformat(order.facts["created_at"])
        delivered = [item for item in logistics if item.facts.get("event_type") == "delivered"]
        picked_up = [
            item
            for item in logistics
            if item.facts.get("event_type") in {"picked_up", "in_transit", "out_for_delivery"}
        ]
        exceptions = [item for item in logistics if item.facts.get("event_type") == "exception"]
        if (order.facts.get("status") == "delivered") != bool(delivered):
            conflict = "订单送达状态与物流送达事件不一致"
            finding = Finding(
                finding_id="fusion-order-logistics-conflict",
                category="fact_conflict",
                claim=conflict,
                evidence_ids=[order.evidence_id] + [item.evidence_id for item in logistics],
                severity="critical",
                review_recommended=True,
            )
            return DecisionOutcome(
                decision="delivery_event_conflict",
                recommended_action="核验订单状态与物流轨迹后人工复检",
                findings=[finding],
                conflicts=[conflict],
            )
        if delivered:
            delivered_at = max(item.occurred_at for item in delivered if item.occurred_at)
            elapsed_hours = (delivered_at - promised_at).total_seconds() / 3600
            if elapsed_hours > rules["delivery_grace_hours"]:
                return DecisionOutcome(
                    responsible_party="logistics_provider",
                    decision="delivery_completed_late",
                    recommended_action="记录物流超时并按政策处理补偿",
                    review_required=False,
                )
            return DecisionOutcome(
                responsible_party="none",
                decision="delivery_completed_on_time",
                recommended_action="向用户提供送达时间和物流凭证",
                review_required=False,
            )
        if exceptions and any(item.facts.get("detail") == "weather" for item in exceptions):
            return DecisionOutcome(
                responsible_party="none",
                decision="delivery_delay_force_majeure",
                recommended_action="同步不可抗力原因和新的预计送达时间",
                review_required=False,
            )
        if exceptions:
            return DecisionOutcome(
                responsible_party="logistics_provider",
                decision="delivery_delay_logistics",
                recommended_action="联系物流方处理异常并向用户同步进度",
                review_required=False,
            )
        if not picked_up:
            elapsed_hours = (case.current_time - created_at).total_seconds() / 3600
            if elapsed_hours > rules["merchant_ship_hours"]:
                return DecisionOutcome(
                    responsible_party="merchant",
                    decision="delivery_delay_merchant",
                    recommended_action="催促商家发货并按政策处理超时",
                    review_required=False,
                )
            return DecisionOutcome(
                responsible_party="none",
                decision="delivery_in_transit_within_sla",
                recommended_action="订单仍在商家发货时限内",
                review_required=False,
            )
        elapsed_hours = (case.current_time - promised_at).total_seconds() / 3600
        if elapsed_hours > rules["delivery_grace_hours"]:
            return DecisionOutcome(
                responsible_party="logistics_provider",
                decision="delivery_delay_logistics",
                recommended_action="联系物流方处理超时并向用户同步进度",
                review_required=False,
            )
        return DecisionOutcome(
            responsible_party="none",
            decision="delivery_in_transit_within_sla",
            recommended_action="物流仍在政策宽限时限内，继续跟踪",
            review_required=False,
        )
