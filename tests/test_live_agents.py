import asyncio
import json
from pathlib import Path

import pytest

from ecom_dispute.agents import EvidenceGapAgent, ReviewAgent
from ecom_dispute.case_state import CaseStateReducer
from ecom_dispute.contracts import CaseState, Evidence, EvidenceKind
from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.repository import Repository, rebuild_database
from ecom_dispute.runtime_state import AgentRunState, HarnessStage


class FakeAgentClient:
    model = "fake-agent-model"

    def __init__(self, outputs: list[dict]):
        self.outputs = outputs
        self.calls = 0

    def create_response(self, payload: dict) -> dict:
        value = self.outputs[self.calls]
        self.calls += 1
        return {
            "id": f"response-{self.calls}",
            "model": self.model,
            "usage": {"input_tokens": 12, "output_tokens": 6},
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(value)}],
                }
            ],
        }


def test_evidence_gap_agent_can_only_load_route_lazy_tool(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "gap.db"))
    harness = DiagnosticHarness.heuristic_tests(repository)
    case = repository.case("m6_refund_amount_001")
    route = harness.skills.resolve(case.business_type)
    run_state = AgentRunState(case_id=case.case_id).activate(
        route.skill_id, route.route_id, route.route.start_stage
    )
    run_state = run_state.move_to(HarnessStage.VERIFY)
    client = FakeAgentClient(
        [
            {
                "needs_more_evidence": True,
                "tool_id": "get_payment_gateway_events",
                "reason": "需要核验支付网关金额",
            }
        ]
    )
    agent = EvidenceGapAgent(
        client, harness.tool_runtime, harness.tool_surface_resolver  # type: ignore[arg-type]
    )
    state = asyncio.run(
        agent.run(case, CaseState(case_id=case.case_id), route, run_state, CaseStateReducer())
    )

    assert client.calls == 1
    assert any(event.get("agent") == "evidence_gap" for event in state.trace)
    assert any(item.source == "query:payment_gateway_events" for item in state.evidence.values())


def test_evidence_gap_agent_rejects_tool_outside_route(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "gap-denied.db"))
    harness = DiagnosticHarness.heuristic_tests(repository)
    case = repository.case("m6_refund_amount_001")
    route = harness.skills.resolve(case.business_type)
    run_state = AgentRunState(case_id=case.case_id).activate(
        route.skill_id, route.route_id, route.route.start_stage
    ).move_to(HarnessStage.VERIFY)
    client = FakeAgentClient(
        [{"needs_more_evidence": True, "tool_id": "get_delivery_proof", "reason": "越界"}]
    )
    agent = EvidenceGapAgent(
        client, harness.tool_runtime, harness.tool_surface_resolver  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="outside route"):
        asyncio.run(
            agent.run(
                case, CaseState(case_id=case.case_id), route, run_state, CaseStateReducer()
            )
        )


def test_review_agent_validates_evidence_references(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "review-agent.db"))
    case = repository.case("refund_conflict_001")
    evidence = Evidence(
        evidence_id="evidence-1",
        kind=EvidenceKind.CONVERSATION,
        source="test",
        business_key=case.case_id,
        facts={},
        summary="退款状态存在冲突",
    )
    state = CaseState(case_id=case.case_id, evidence={evidence.evidence_id: evidence})
    client = FakeAgentClient(
        [
            {
                "conflict_summary": "退款状态与到账记录冲突",
                "review_questions": ["支付渠道是否存在实际入账？"],
                "recommended_action": "核验支付流水",
                "cited_evidence_ids": ["evidence-1"],
                "priority": "high",
            }
        ]
    )

    result = asyncio.run(ReviewAgent(client).run(case, state))  # type: ignore[arg-type]

    assert result.findings[0].evidence_ids == ["evidence-1"]
    assert result.findings[0].review_recommended
    assert result.telemetry["priority"] == "high"


def test_live_harness_installs_three_real_agent_roles(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "live-agents.db"))
    client = FakeAgentClient([])
    harness = DiagnosticHarness.live(repository, client)  # type: ignore[arg-type]

    assert harness.conversation_agent.name == "conversation"
    assert harness.evidence_gap_agent.name == "evidence_gap"
    assert harness.review_agent.name == "review"
