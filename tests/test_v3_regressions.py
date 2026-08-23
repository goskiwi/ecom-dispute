import json
from pathlib import Path

from ecom_dispute.e2e_evaluation import prepare_e2e_database
from ecom_dispute.formal_e2e_builder import build_formal_e2e
from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.llm import ConversationSemantics, LLMResult
from ecom_dispute.ontology import BusinessRoute
from ecom_dispute.repository import Repository, rebuild_database
from ecom_dispute.resource_loader import SkillLoader
from ecom_dispute.review_ab_evaluation import build_review_manifest
from ecom_dispute.runtime_state import AgentRunState, HarnessStage
from ecom_dispute.semantic_holdout import evaluate_holdout
from ecom_dispute.skills import default_strategies
from ecom_dispute.tool_runtime import ToolRuntime, ToolSurfaceResolver
from ecom_dispute.web import DemoApplication


def test_formal_builder_and_import_cover_all_v3_routes(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs.json"
    oracle = tmp_path / "oracle.json"
    result = build_formal_e2e(tmp_path / "source.db", inputs, oracle)
    repository, case_ids = prepare_e2e_database(tmp_path / "import.db", inputs)
    assert result["case_count"] == 90
    assert len(case_ids) == 90
    assert len(repository.case_ids()) == 90
    assert set(json.loads(oracle.read_text())) == set(case_ids)


def test_resource_loader_cross_validates_all_v3_resources() -> None:
    packs = SkillLoader(known_strategies=set(default_strategies())).load_all()
    assert len(packs) == 7
    assert sum(len(pack.routes) for pack in packs.values()) == 29


def test_runtime_injects_scope_and_rejects_outside_route(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "scope.db"))
    harness = DiagnosticHarness.heuristic_tests(repository)
    case = repository.case("v3-cart_issue")
    route = harness.skills.resolve(case.business_type)
    state = AgentRunState(case_id=case.case_id).activate(
        route.skill_id, route.route_id, route.route.start_stage
    )
    surface = ToolSurfaceResolver(harness.registry).resolve(
        route, state.move_to(HarnessStage.VERIFY)
    )
    runtime = ToolRuntime(harness.registry)
    accepted = runtime.execute("get_cart_events", {}, case, surface)
    rejected = runtime.execute("get_refund_records", {}, case, surface)
    assert accepted.status == "ok"
    assert accepted.evidence[0].facts["order_id"] == case.order_id
    assert rejected.error_code == "TOOL_NOT_IN_CURRENT_SURFACE"


def test_review_task_resolution_survives_v3_rebuild(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "review.db"))
    DiagnosticHarness.heuristic_tests(repository).diagnose_sync(repository.case("v3-cart_issue"))
    task = repository.resolve_review(
        "v3-cart_issue", "cart_repaired", "platform", "已确认前端状态冲突"
    )
    assert task.status == "resolved"
    assert task.reviewer_decision == "cart_repaired"


def test_demo_application_uses_only_v3_cases(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "web.db"))
    harness = DiagnosticHarness.heuristic_tests(repository)
    application = DemoApplication(repository, harness, "heuristic-test")
    cases = application.cases()
    assert len(cases) == 90
    assert all(item["case_id"].startswith(("v3-", "v3d-")) for item in cases)
    result = application.run_case("v3-product_information")
    assert result["report"]["decision"] == "product_information_found"


class FakeRouteClient:
    def extract_conversation(self, conversation: list[dict], repair_hint: str | None = None):
        return LLMResult(
            semantics=ConversationSemantics(
                route_type=BusinessRoute.PRODUCT_INFORMATION,
                has_business_exception=False,
                return_reason=None,
                order_operation=None,
                item_mismatch_claim=None,
                business_facts=[],
                interaction_acts=[],
                uncertainty=None,
            ),
            response_id="fake-v3",
            model="fake",
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
        )


def test_route_only_holdout_does_not_score_unlabeled_facts(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs.json"
    oracle = tmp_path / "oracle.json"
    inputs.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "route-only",
                        "conversation": [{"speaker": "user", "text": "商品是什么材质？"}],
                    }
                ]
            }
        )
    )
    oracle.write_text(
        json.dumps(
            {
                "route-only": {
                    "route_type": "product_information",
                    "has_business_exception": False,
                }
            }
        )
    )
    result = evaluate_holdout(
        FakeRouteClient(),  # type: ignore[arg-type]
        inputs,
        oracle,
        repeats=1,
    )
    assert result["route_type_accuracy"] == 1.0
    assert result["user_business_facts_accuracy"] is None


def test_review_manifest_uses_available_v3_review_cases(tmp_path: Path) -> None:
    result = build_review_manifest(
        Path("data/v3_e2e_90_inputs.json"),
        tmp_path / "manifest.json",
        tmp_path / "review.db",
    )
    assert result["case_count"] > 14
    assert set(result["categories"]).issubset({"conflict", "missing", "compliance", "strategy"})
