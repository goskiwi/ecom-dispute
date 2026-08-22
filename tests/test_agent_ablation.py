import asyncio
import json
from pathlib import Path

from ecom_dispute.agent_ablation import compare_agent_layers
from ecom_dispute.agents import HeuristicConversationStub
from ecom_dispute.repository import Repository, rebuild_database


class FakeAblationClient:
    model = "fake-ablation"

    def __init__(self) -> None:
        self.calls = 0

    def create_response(self, payload: dict) -> dict:
        self.calls += 1
        schema_name = payload["text"]["format"]["name"]
        if schema_name == "evidence_gap_plan":
            value = {
                "needs_more_evidence": True,
                "tool_id": "get_payment_gateway_events",
                "reason": "核验网关金额",
            }
        else:
            raise AssertionError(f"unexpected schema: {schema_name}")
        return {
            "id": f"response-{self.calls}",
            "model": self.model,
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(value)}],
                }
            ],
        }


def test_ablation_reuses_conversation_and_adds_only_gap_cost(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "ablation.db"))
    case = repository.case("m6_refund_amount_001")
    conversation = asyncio.run(HeuristicConversationStub().run(case))

    result = compare_agent_layers(
        repository,
        case,
        conversation,
        FakeAblationClient(),  # type: ignore[arg-type]
    )

    assert result["modes"]["core"]["incremental_agents"] == []
    assert result["modes"]["gap"]["incremental_agents"] == ["evidence_gap"]
    assert result["modes"]["full"]["incremental_agents"] == ["evidence_gap"]
    assert {
        result["modes"][mode]["decision"] for mode in ("core", "gap", "full")
    } == {"refund_amount_incorrect"}
