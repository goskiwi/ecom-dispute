import pytest
from pydantic import ValidationError

from ecom_dispute.agents.conversation import ConversationAgent
from ecom_dispute.contracts import CaseInput
from ecom_dispute.llm import (
    ConversationSemantics,
    ItemMismatchClaim,
    LLMResult,
)
from ecom_dispute.ontology import BusinessRoute, ItemAttribute, ReturnReason


def _case(text: str) -> CaseInput:
    return CaseInput.model_validate(
        {
            "case_id": "conversation-v3",
            "order_id": "order-v3",
            "source_type": "manual",
            "region": "CN",
            "business_type": "received_item_mismatch",
            "occurred_at": "2026-08-01T10:00:00",
            "current_time": "2026-08-02T10:00:00",
            "conversation": [{"speaker": "user", "text": text}],
        }
    )


def _semantics(claim: ItemMismatchClaim | None) -> ConversationSemantics:
    return ConversationSemantics(
        route_type=BusinessRoute.RECEIVED_ITEM_MISMATCH,
        has_business_exception=True,
        return_reason=None,
        order_operation=None,
        item_mismatch_claim=claim,
        business_facts=[],
        interaction_acts=[],
        uncertainty=None,
    )


def test_received_item_mismatch_requires_explicit_source_comparison() -> None:
    with pytest.raises(ValidationError, match="explicit order/received mismatch"):
        _semantics(None)


def test_mismatch_values_must_be_grounded_in_source_text() -> None:
    case = _case("我下单白色，实际收到黑色。")
    result = LLMResult(
        semantics=_semantics(
            ItemMismatchClaim(
                attribute=ItemAttribute.COLOR,
                ordered_value="红色",
                received_value="黑色",
                explicit_order_received_mismatch=True,
                message_indices=[0],
            )
        ),
        response_id="v3",
        model="fake",
        input_tokens=1,
        output_tokens=1,
        latency_ms=1,
    )
    with pytest.raises(ValueError, match="not grounded"):
        ConversationAgent._build_findings(ConversationAgent(None), case, None, result)  # type: ignore[arg-type]


def test_explicit_ordered_and_received_values_are_accepted() -> None:
    claim = ItemMismatchClaim(
        attribute=ItemAttribute.COLOR,
        ordered_value="白色",
        received_value="黑色",
        explicit_order_received_mismatch=True,
        message_indices=[0],
    )
    semantics = _semantics(claim)
    assert semantics.has_business_exception is True
    assert semantics.route_type == BusinessRoute.RECEIVED_ITEM_MISMATCH


def test_buyer_fit_issue_is_a_return_request_not_mismatch() -> None:
    semantics = ConversationSemantics(
        route_type=BusinessRoute.RETURN_REQUEST,
        has_business_exception=False,
        return_reason=ReturnReason.FIT_ISSUE,
        order_operation=None,
        item_mismatch_claim=None,
        business_facts=[],
        interaction_acts=[],
        uncertainty=None,
    )
    assert semantics.route_type == BusinessRoute.RETURN_REQUEST
