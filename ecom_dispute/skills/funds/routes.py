from __future__ import annotations

from dataclasses import dataclass

from ...contracts import CaseInput, CaseState, EvidenceKind
from ..base import DecisionOutcome


def _evidence(state: CaseState, kind: EvidenceKind) -> list:
    return [item for item in state.evidence.values() if item.kind == kind]


@dataclass(frozen=True)
class RefundAmountMismatchStrategy:
    def decide(
        self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]
    ) -> DecisionOutcome:
        if missing_evidence:
            return DecisionOutcome()
        orders = _evidence(state, EvidenceKind.ORDER)
        refunds = _evidence(state, EvidenceKind.REFUND)
        credits = [
            item
            for item in _evidence(state, EvidenceKind.PAYMENT)
            if item.facts.get("event_type") == "credit" and item.facts.get("status") == "succeeded"
        ]
        if not orders or not refunds:
            return DecisionOutcome()
        expected = float(orders[0].facts["paid_amount"])
        refund_amount = float(refunds[-1].facts["amount"])
        if refund_amount != expected:
            return DecisionOutcome(
                responsible_party="platform",
                decision="refund_amount_incorrect",
                recommended_action="按订单实付金额修正退款并核验售后计算链路",
                review_required=False,
            )
        if not credits or float(credits[-1].facts["amount"]) != refund_amount:
            return DecisionOutcome(
                responsible_party="payment_channel",
                decision="refund_credit_amount_mismatch",
                recommended_action="携退款流水向支付渠道核验实际入账金额",
                review_required=True,
            )
        return DecisionOutcome(
            responsible_party="none",
            decision="refund_amount_correct",
            recommended_action="向用户提供退款和入账流水",
            review_required=False,
        )


@dataclass(frozen=True)
class DuplicateChargeStrategy:
    def decide(
        self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]
    ) -> DecisionOutcome:
        if missing_evidence:
            return DecisionOutcome()
        debits = [
            item
            for item in _evidence(state, EvidenceKind.PAYMENT)
            if item.facts.get("event_type") == "debit"
        ]
        succeeded = [item for item in debits if item.facts.get("status") == "succeeded"]
        pending = [item for item in debits if item.facts.get("status") == "pending"]
        if len(succeeded) >= 2:
            return DecisionOutcome(
                responsible_party="payment_channel",
                decision="duplicate_charge_confirmed",
                recommended_action="撤销重复扣款并核验支付幂等链路",
                review_required=True,
            )
        if len(succeeded) == 1 and pending:
            return DecisionOutcome(
                responsible_party="none",
                decision="duplicate_charge_pending_authorization",
                recommended_action="等待预授权释放并继续跟踪账单",
                review_required=False,
            )
        return DecisionOutcome(
            responsible_party="none",
            decision="duplicate_charge_not_found",
            recommended_action="向用户提供唯一成功扣款流水",
            review_required=False,
        )


@dataclass(frozen=True)
class PaymentCapturedOrderFailedStrategy:
    def decide(
        self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]
    ) -> DecisionOutcome:
        if missing_evidence:
            return DecisionOutcome()
        orders = _evidence(state, EvidenceKind.ORDER)
        payments = _evidence(state, EvidenceKind.PAYMENT)
        refunds = _evidence(state, EvidenceKind.REFUND)
        if not orders:
            return DecisionOutcome()
        order_failed = orders[0].facts.get("status") in {"failed", "cancelled"}
        captured = any(
            item.facts.get("event_type") == "debit" and item.facts.get("status") == "succeeded"
            for item in payments
        )
        reversed_funds = bool(refunds) or any(
            item.facts.get("event_type") in {"credit", "reversal"}
            and item.facts.get("status") == "succeeded"
            for item in payments
        )
        if order_failed and captured and reversed_funds:
            return DecisionOutcome(
                responsible_party="none",
                decision="captured_order_failed_reversed",
                recommended_action="向用户提供资金撤销或退款流水",
                review_required=False,
            )
        if order_failed and captured:
            return DecisionOutcome(
                responsible_party="platform",
                decision="captured_order_failed_unreversed",
                recommended_action="立即发起资金撤销并排查订单创建链路",
                review_required=True,
            )
        return DecisionOutcome(
            responsible_party="undetermined",
            decision="payment_order_state_conflict",
            recommended_action="补充订单创建和支付网关证据后复检",
            review_required=True,
        )


@dataclass(frozen=True)
class UnrecognizedChargeStrategy:
    def decide(
        self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]
    ) -> DecisionOutcome:
        if missing_evidence:
            return DecisionOutcome()
        claims = _evidence(state, EvidenceKind.CHARGE_CLAIM)
        if not claims:
            return DecisionOutcome(
                "none",
                "unrecognized_charge_not_found",
                "未查询到对应成功扣款，向用户说明查询范围",
                False,
            )
        if all(item.facts.get("status") == "recognized" for item in claims):
            return DecisionOutcome(
                "none",
                "charge_recognized",
                "向用户提供订单与支付流水关联信息",
                False,
            )
        return DecisionOutcome(
            "payment_channel",
            "unrecognized_charge_confirmed",
            "冻结争议交易并转入支付安全人工复检",
            True,
        )


@dataclass(frozen=True)
class OrderFeeDisputeStrategy:
    def decide(
        self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]
    ) -> DecisionOutcome:
        if missing_evidence:
            return DecisionOutcome()
        fees = _evidence(state, EvidenceKind.ORDER_FEE)
        if not fees:
            return DecisionOutcome()
        expected = sum(float(item.facts.get("expected_amount", 0)) for item in fees)
        charged = sum(float(item.facts.get("charged_amount", 0)) for item in fees)
        if expected != charged:
            return DecisionOutcome(
                "platform",
                "order_fee_incorrect",
                "按适用政策修正订单费用并说明费用明细",
                False,
            )
        return DecisionOutcome(
            "none",
            "order_fee_correct",
            "向用户展示费用项目和适用政策",
            False,
        )
