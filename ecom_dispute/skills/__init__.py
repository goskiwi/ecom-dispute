from .base import (
    DecisionOutcome,
    DecisionStrategy,
    ResolvedRoute,
    SkillRegistry,
)
from .fulfillment import (
    CancellationInTransitStrategy,
    DeliveredNotReceivedStrategy,
    DeliveryDelayStrategy,
    MerchantNotShippedStrategy,
)
from .funds import (
    DuplicateChargeStrategy,
    PaymentCapturedOrderFailedStrategy,
    RefundAmountMismatchStrategy,
    RefundStatusStrategy,
)
from .item_after_sales import (
    DamagedItemStrategy,
    MissingItemStrategy,
    ReturnEligibilityStrategy,
    WrongItemStrategy,
)


def default_strategies() -> dict[str, DecisionStrategy]:
    return {
        "refund_status": RefundStatusStrategy(),
        "refund_amount_mismatch": RefundAmountMismatchStrategy(),
        "duplicate_charge": DuplicateChargeStrategy(),
        "payment_captured_order_failed": PaymentCapturedOrderFailedStrategy(),
        "delivery_delay": DeliveryDelayStrategy(),
        "merchant_not_shipped": MerchantNotShippedStrategy(),
        "delivered_not_received": DeliveredNotReceivedStrategy(),
        "cancellation_in_transit": CancellationInTransitStrategy(),
        "return_eligibility": ReturnEligibilityStrategy(),
        "wrong_item": WrongItemStrategy(),
        "missing_item": MissingItemStrategy(),
        "damaged_item": DamagedItemStrategy(),
    }


__all__ = [
    "DecisionOutcome",
    "DecisionStrategy",
    "DeliveryDelayStrategy",
    "RefundStatusStrategy",
    "ResolvedRoute",
    "SkillRegistry",
    "default_strategies",
]
