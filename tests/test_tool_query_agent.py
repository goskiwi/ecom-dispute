import asyncio
import json
from pathlib import Path

from ecom_dispute.agents.tool_query import ToolQueryAgent
from ecom_dispute.case_state import CaseStateReducer
from ecom_dispute.contracts import CaseState
from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.repository import Repository, rebuild_database
from ecom_dispute.runtime_state import AgentRunState, HarnessStage
from ecom_dispute.tool_runtime import ToolRuntime, ToolSurfaceResolver


class FakeQueryClient:
    model = "fake-query-model"

    def __init__(self) -> None:
        self.calls = 0
        self.inputs = []

    def create_response(self, payload: dict) -> dict:
        self.calls += 1
        self.inputs.append(payload["input"])
        if self.calls == 1:
            output = [
                {
                    "type": "function_call",
                    "name": "get_order",
                    "arguments": "{}",
                    "call_id": "call-order",
                },
                {
                    "type": "function_call",
                    "name": "read_policy",
                    "arguments": "{}",
                    "call_id": "call-policy",
                },
            ]
        else:
            conclusion = {"done": True, "summary": "evidence collected", "missing_evidence": []}
            output = [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(conclusion)}],
                }
            ]
        return {
            "id": f"response-{self.calls}",
            "model": self.model,
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "output": output,
        }


def test_tool_query_agent_reduces_each_tool_round(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "query.db"))
    client = FakeQueryClient()
    harness = DiagnosticHarness.heuristic_tests(repository)
    route = harness.skills.resolve("refund")
    run_state = AgentRunState(case_id="refund_complete_001").activate(
        route.skill_id, route.route_id, route.route.start_stage
    )
    run_state = run_state.move_to(HarnessStage.VERIFY)
    surface = ToolSurfaceResolver(harness.registry).resolve(route, run_state)
    agent = ToolQueryAgent(client, harness.tool_runtime)  # type: ignore[arg-type]
    state = asyncio.run(
        agent.run(
            repository.case("refund_complete_001"),
            CaseState(case_id="refund_complete_001"),
            CaseStateReducer(),
            surface,
        )
    )

    assert client.calls == 2
    assert {item.kind.value for item in state.evidence.values()} == {"order", "policy"}
    assert any(event.get("agent") == "fact_query" for event in state.trace)
    assert state.trace[-1]["stage"] == "tool_query_stop"
    assert "orders:ord-1001:v1" in client.inputs[1][-1]["content"]


def test_registry_returns_structured_invalid_arguments(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "invalid.db"))
    harness = DiagnosticHarness.heuristic_tests(repository)
    case = repository.case("refund_complete_001")
    route = harness.skills.resolve(case.business_type)
    run_state = AgentRunState(case_id=case.case_id).activate(
        route.skill_id, route.route_id, route.route.start_stage
    )
    run_state = run_state.move_to(HarnessStage.VERIFY)
    surface = ToolSurfaceResolver(harness.registry).resolve(route, run_state)
    result = ToolRuntime(harness.registry).execute(
        "get_order", {"wrong": "value"}, case, surface
    )
    assert result.status == "invalid"
    assert result.error_code == "TOOL_ARGUMENT_INVALID"


def test_live_harness_defaults_to_fixed_tools(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "live-mode.db"))
    client = FakeQueryClient()
    fixed = DiagnosticHarness.live(repository, client)  # type: ignore[arg-type]
    agentic = DiagnosticHarness.live(repository, client, "agent")  # type: ignore[arg-type]
    assert fixed.tool_query_agent is None
    assert agentic.tool_query_agent is not None
