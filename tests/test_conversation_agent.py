import asyncio

import pytest

from ecom_dispute.agents import ConversationAgent
from ecom_dispute.contracts import FactType, Polarity, SpeechAct, TemporalStatus
from ecom_dispute.llm import BusinessFact, ConversationSemantics, InteractionAct, LLMResult
from ecom_dispute.repository import Repository, rebuild_database


class FakeConversationClient:
    def __init__(self, fact: BusinessFact):
        self.fact = fact

    def extract_conversation(self, messages: list[dict[str, str]]) -> LLMResult:
        return LLMResult(
            semantics=ConversationSemantics(
                business_type="refund",
                has_dispute=True,
                business_facts=[self.fact],
                interaction_acts=[
                    InteractionAct(
                        speaker="user",
                        quote=self.fact.quote,
                        message_index=self.fact.message_index,
                        speech_act=SpeechAct.ASSERTION,
                    )
                ],
                uncertainty=None,
            ),
            response_id="response-v2",
            model="fake-v2",
            input_tokens=10,
            output_tokens=5,
            latency_ms=1,
        )


def _fact(quote: str, message_index: int = 0) -> BusinessFact:
    return BusinessFact(
        speaker="user",
        quote=quote,
        message_index=message_index,
        fact_type=FactType.REFUND_RECEIPT,
        polarity=Polarity.NEGATED,
        temporal_status=TemporalStatus.CURRENT,
    )


def test_atomic_fact_is_projected_without_legacy_statement_fields(tmp_path) -> None:
    repository = Repository(rebuild_database(tmp_path / "conversation.db"))
    case = repository.case("refund_conflict_001")
    agent = ConversationAgent(FakeConversationClient(_fact("银行卡一直没入账")))  # type: ignore[arg-type]
    result = asyncio.run(agent.run(case))
    finding = result.findings[0]
    assert finding.category == "user_business_fact"
    assert finding.fact_type == FactType.REFUND_RECEIPT
    assert finding.polarity == Polarity.NEGATED
    assert "statement_type" not in finding.model_dump()


def test_non_verbatim_quote_is_rejected(tmp_path) -> None:
    repository = Repository(rebuild_database(tmp_path / "bad-quote.db"))
    case = repository.case("refund_conflict_001")
    agent = ConversationAgent(FakeConversationClient(_fact("用户没有收到退款")))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="quote is not grounded"):
        asyncio.run(agent.run(case))
