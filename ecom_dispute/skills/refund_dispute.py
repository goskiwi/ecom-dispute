from __future__ import annotations

from dataclasses import dataclass

from ..contracts import EvidenceKind


@dataclass(frozen=True)
class RefundDisputeSkill:
    name: str = "refund_dispute"
    allowed_tools: tuple[str, ...] = (
        "get_order",
        "get_payment_records",
        "get_refund_records",
        "get_after_sales_case",
        "read_policy",
    )
    required_evidence: tuple[EvidenceKind, ...] = (
        EvidenceKind.CONVERSATION,
        EvidenceKind.ORDER,
        EvidenceKind.PAYMENT,
        EvidenceKind.AFTER_SALES,
        EvidenceKind.POLICY,
    )

    def supports(self, business_type: str) -> bool:
        return business_type == "refund"

