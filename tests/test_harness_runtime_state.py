from pathlib import Path

import pytest

from ecom_dispute.context_projector import ContextProjector
from ecom_dispute.contracts import CaseState
from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.repository import Repository, rebuild_database
from ecom_dispute.runtime_state import AgentRunState, HarnessStage, RunStatus


def test_run_state_enforces_stage_order() -> None:
    state = AgentRunState(case_id="case-1").activate(
        "funds-dispute", "refund-status", "ANALYZE"
    )
    state = state.move_to(HarnessStage.VERIFY)
    state = state.move_to(HarnessStage.DECIDE)
    state = state.move_to(HarnessStage.FUSE_AND_REVIEW).complete()

    assert state.status == RunStatus.COMPLETED
    assert state.turn_count == 3


def test_run_state_rejects_stage_skip() -> None:
    state = AgentRunState(case_id="case-1").activate(
        "funds-dispute", "refund-status", "ANALYZE"
    )
    with pytest.raises(ValueError, match="invalid harness stage transition"):
        state.move_to(HarnessStage.DECIDE)


def test_context_projector_loads_only_current_stage(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "context.db"))
    harness = DiagnosticHarness.heuristic_tests(repository)
    case = repository.case("refund_complete_001")
    route = harness.skills.resolve(case.business_type)
    run_state = AgentRunState(case_id=case.case_id).activate(
        route.skill_id, route.route_id, route.route.start_stage
    )

    projected = ContextProjector().project(
        case,
        CaseState(case_id=case.case_id),
        run_state,
        route,
    )

    assert projected.stage_id == "ANALYZE"
    assert projected.tool_ids == ()
    assert "分析资金争议对话" in (projected.stage_instructions or "")
    assert "Tool Schema" not in projected.skill_instructions
