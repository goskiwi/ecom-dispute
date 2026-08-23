from pathlib import Path

from ecom_dispute.evaluation import evaluate
from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.repository import Repository, rebuild_database
from ecom_dispute.runtime_state import AgentRunState, HarnessStage
from ecom_dispute.tool_runtime import ToolSurfaceResolver


def test_v3_deterministic_evaluation_is_complete(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "eval.db"))
    result = evaluate(repository)
    assert result["case_count"] == 26
    assert result["passed"] == 26
    assert result["pass_rate"] == 1.0


def test_dynamic_tool_surface_changes_by_route(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "surface.db"))
    harness = DiagnosticHarness.heuristic_tests(repository)

    cart = harness.skills.resolve("cart_issue")
    refund = harness.skills.resolve("refund_progress")
    cart_state = AgentRunState(case_id="cart").activate(
        cart.skill_id, cart.route_id, cart.route.start_stage
    )
    refund_state = AgentRunState(case_id="refund").activate(
        refund.skill_id, refund.route_id, refund.route.start_stage
    )
    resolver = ToolSurfaceResolver(harness.registry)

    cart_tools = set(resolver.resolve(cart, cart_state.move_to(HarnessStage.VERIFY)).tool_ids)
    refund_tools = set(resolver.resolve(refund, refund_state.move_to(HarnessStage.VERIFY)).tool_ids)
    assert cart_tools == {"get_cart_events", "get_site_health"}
    assert {
        "get_order",
        "get_payment_records",
        "get_refund_records",
        "get_after_sales_case",
        "read_policy",
    } == refund_tools
    assert cart_tools.isdisjoint(refund_tools)


def test_review_task_is_created_for_a_v3_conflict(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "review.db"))
    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("v3-cart_issue")
    )
    task = repository.review_task(report.case_id)
    assert report.review_required is True
    assert task is not None
    assert task.system_decision == "cart_state_conflict"


def test_write_capability_stops_at_confirmable_action_plan(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "action.db"))
    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("v3-order_management")
    )
    assert report.action_plan is not None
    assert report.action_plan.action_type == "submit_order_change"
    assert report.action_plan.requires_confirmation is True
    assert report.action_plan.idempotency_key == ("v3-order_management:order_change_allowed")
