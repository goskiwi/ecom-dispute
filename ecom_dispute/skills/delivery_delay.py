from __future__ import annotations

from dataclasses import dataclass

from ..contracts import EvidenceKind


@dataclass(frozen=True)
class DeliveryDelaySkill:
    name: str = "delivery_delay"
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

    def supports(self, business_type: str) -> bool:
        return business_type == "delivery"
