from pathlib import Path

from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.repository import Repository, rebuild_database
from ecom_dispute.runtime_state import AgentRunState, HarnessStage
from ecom_dispute.skills import ResolvedRoute
from ecom_dispute.tool_runtime import ToolSearchService


def _verify_surface(harness: DiagnosticHarness, business_type: str, case_id: str):
    route = harness.skills.resolve(business_type)
    run_state = AgentRunState(case_id=case_id).activate(
        route.skill_id, route.route_id, route.route.start_stage
    )
    analyze = harness.tool_surface_resolver.resolve(route, run_state)
    run_state = run_state.move_to(HarnessStage.VERIFY)
    verify = harness.tool_surface_resolver.resolve(route, run_state)
    return route, analyze, verify


def test_surface_changes_with_stage_and_route(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "surface.db"))
    harness = DiagnosticHarness.heuristic_tests(repository)

    _, refund_analyze, refund_verify = _verify_surface(
        harness, "refund", "refund_complete_001"
    )
    _, delivery_analyze, delivery_verify = _verify_surface(
        harness, "delivery", "delivery_ontime_001"
    )

    assert refund_analyze.tool_ids == ()
    assert delivery_analyze.tool_ids == ()
    assert set(refund_verify.tool_ids) == {
        "get_order",
        "get_payment_records",
        "get_refund_records",
        "get_after_sales_case",
        "read_policy",
    }
    assert set(delivery_verify.tool_ids) == {
        "get_order",
        "get_logistics_events",
        "read_policy",
    }


def test_runtime_injects_case_scope_and_rejects_outside_surface(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "scope.db"))
    harness = DiagnosticHarness.heuristic_tests(repository)
    case = repository.case("refund_complete_001")
    _, _, surface = _verify_surface(harness, case.business_type, case.case_id)

    order = harness.tool_runtime.execute("get_order", {}, case, surface)
    denied = harness.tool_runtime.execute("get_logistics_events", {}, case, surface)

    assert order.status == "ok"
    assert order.evidence[0].business_key == case.order_id
    assert denied.status == "invalid"
    assert denied.error_code == "TOOL_NOT_IN_CURRENT_SURFACE"


def test_tool_search_is_limited_to_route_lazy_tools(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "search.db"))
    harness = DiagnosticHarness.heuristic_tests(repository)
    original = harness.skills.resolve("refund")
    route = original.route.model_copy(update={"lazy_tools": ("get_refund_records",)})
    resolved = ResolvedRoute(original.skill, route, original.strategy)

    matches = ToolSearchService(harness.registry).search(
        "查询退款处理记录",
        resolved,
        loaded_tools=set(),
    )

    assert [item.tool_id for item in matches] == ["get_refund_records"]
