import json
from pathlib import Path

from ecom_dispute.contracts import StatementType, TemporalStatus
from ecom_dispute.llm import ConversationSemantics, ExtractedStatement, LLMResult
from ecom_dispute.semantic_holdout import evaluate_holdout


class FakeSemanticClient:
    def extract_conversation(self, messages: list[dict[str, str]]) -> LLMResult:
        return LLMResult(
            semantics=ConversationSemantics(
                business_type="refund",
                has_dispute=True,
                user_claims=[
                    ExtractedStatement(
                        text=messages[0]["text"],
                        statement_types=[StatementType.REFUND_NOT_RECEIVED],
                        temporal_status=TemporalStatus.CURRENT,
                        message_indexes=[0],
                    )
                ],
                agent_commitments=[],
                uncertainty=None,
            ),
            response_id="fake-response",
            model="fake-model",
            input_tokens=10,
            output_tokens=5,
            latency_ms=1,
        )


def test_semantic_holdout_repeats_without_exposing_oracle(tmp_path: Path) -> None:
    input_path = tmp_path / "inputs.json"
    oracle_path = tmp_path / "oracle.json"
    input_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "holdout_refund_001",
                        "conversation": [{"speaker": "user", "text": "退款一直没到账"}],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    oracle_path.write_text(
        json.dumps(
            {
                "holdout_refund_001": {
                    "business_type": "refund",
                    "has_dispute": True,
                    "expected_user_facts": [
                        {
                            "statement_type": "refund_not_received",
                            "temporal_status": "current",
                        }
                    ],
                    "expected_agent_facts": [],
                }
            }
        ),
        encoding="utf-8",
    )

    result = evaluate_holdout(
        FakeSemanticClient(),  # type: ignore[arg-type]
        input_path,
        oracle_path,
        repeats=2,
        workers=1,
    )
    assert result["case_count"] == 1
    assert result["repeats"] == 2
    assert result["user_fact_exact_match"] == 1.0
    assert result["user_fact_precision"] == 1.0
    assert result["user_fact_recall"] == 1.0
    assert result["input_tokens"] == 20
