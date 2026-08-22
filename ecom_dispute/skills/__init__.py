from .base import (
    DecisionOutcome,
    DecisionStrategy,
    ResolvedRoute,
    SkillRegistry,
)
from .fulfillment import DeliveryDelayStrategy
from .funds import RefundStatusStrategy


def default_strategies() -> dict[str, DecisionStrategy]:
    return {
        "refund_status": RefundStatusStrategy(),
        "delivery_delay": DeliveryDelayStrategy(),
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
