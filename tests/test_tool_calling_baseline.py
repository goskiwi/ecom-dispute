import json
from pathlib import Path

from ecom_dispute.baseline import ToolCallingBaseline
from ecom_dispute.repository import Repository, rebuild_database
from ecom_dispute.tool_registry import ToolRegistry


class FakeResponsesClient:
    model = "fake-model"

    def __init__(self) -> None:
        self.calls = 0
        self.inputs = []

    def create_response(self, payload: dict) -> dict:
        self.calls += 1
        self.inputs.append(payload["input"])
        if self.calls == 1:
            specs = [
                ("get_order", {}),
                ("get_payment_records", {}),
                ("get_refund_records", {}),
                ("get_after_sales_case", {}),
                ("read_policy", {}),
            ]
            output = [
                {
                    "type": "function_call",
                    "name": name,
                    "arguments": json.dumps(arguments),
                    "call_id": f"call-{index}",
                }
                for index, (name, arguments) in enumerate(specs)
            ]
        else:
            decision = {
                "dispute_type": "refund_dispute",
                "responsible_party": "none",
                "decision": "refund_completed",
                "evidence_ids": [
                    "orders:ord-1001:v1",
                    "payments:pay-1-debit:v1",
                    "after_sales_cases:as-1:v1",
                    "policies:refund-cn-standard:v2",
                    "refunds:ref-1:v1",
                ],
                "missing_evidence": [],
                "recommended_action": "提供退款流水",
                "review_required": False,
            }
            output = [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(decision)}],
                }
            ]
        return {
            "id": f"response-{self.calls}",
            "model": self.model,
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "output": output,
        }


def test_tool_calling_loop_replays_calls_and_validates_evidence(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "baseline.db"))
    client = FakeResponsesClient()
    baseline = ToolCallingBaseline(client, ToolRegistry(repository))  # type: ignore[arg-type]
    run = baseline.diagnose(repository.case("refund_complete_001"))

    assert run.decision.decision == "refund_completed"
    assert run.llm_calls == 2
    assert run.tool_calls == 5
    assert run.invalid_evidence_ids == []
    assert set(run.decision.evidence_ids).issubset(run.returned_evidence_ids)
    assert len(client.inputs[1]) == 11
    assert {item["type"] for item in client.inputs[1][1:]} == {
        "function_call",
        "function_call_output",
    }


def test_response_tool_schemas_are_strict(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "tools.db"))
    tools = ToolRegistry(repository).response_tools()
    assert len(tools) == 10
    assert all(tool["strict"] for tool in tools)
    assert all(tool["parameters"]["additionalProperties"] is False for tool in tools)
