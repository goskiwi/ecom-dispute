import json
from pathlib import Path

import pytest

from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.ontology import BUSINESS_ROUTE_IDS, COMPLIANCE_ROUTE_IDS
from ecom_dispute.repository import Repository, rebuild_database
from ecom_dispute.seed_v3 import CASE_SPECS
from ecom_dispute.skills import SkillRegistry, default_strategies
from ecom_dispute.tool_registry import ToolRegistry


@pytest.fixture(scope="module")
def v3_repository(tmp_path_factory: pytest.TempPathFactory) -> Repository:
    path = tmp_path_factory.mktemp("v3") / "v3.db"
    return Repository(rebuild_database(path))


@pytest.mark.parametrize("business_type", sorted(BUSINESS_ROUTE_IDS))
def test_each_v3_business_route_has_a_deterministic_e2e(
    v3_repository: Repository, business_type: str
) -> None:
    case = v3_repository.case(f"v3-{business_type}")
    report = DiagnosticHarness.heuristic_tests(v3_repository).diagnose_sync(case)

    assert report.dispute_type == business_type
    assert report.decision == CASE_SPECS[business_type][1]
    assert report.evidence_ids
    assert all(
        finding.evidence_ids and set(finding.evidence_ids).issubset(report.evidence_ids)
        for finding in report.findings
    )


def test_frozen_runtime_has_seven_skills_and_twenty_nine_routes(
    v3_repository: Repository,
) -> None:
    tools = ToolRegistry(v3_repository)
    skills = SkillRegistry(default_strategies(), known_tools=tools.names)

    assert len(skills.skill_ids) == 7
    assert len(skills.business_types) == 29
    assert skills.business_types == set(BUSINESS_ROUTE_IDS) | {
        item.replace("-", "_") for item in COMPLIANCE_ROUTE_IDS
    }
    assert len(tools.names) == 29


@pytest.mark.parametrize(
    "legacy_route",
    [
        "refund",
        "refund_amount",
        "payment_order_failure",
        "delivery",
        "merchant_not_shipped",
        "cancellation_in_transit",
        "return_eligibility",
        "wrong_item",
        "damaged_item",
        "refund_status",
        "delivery_delay",
        "false_business_statement",
    ],
)
def test_legacy_route_ids_are_not_accepted(v3_repository: Repository, legacy_route: str) -> None:
    registry = SkillRegistry(default_strategies(), known_tools=ToolRegistry(v3_repository).names)
    with pytest.raises(ValueError, match="no route"):
        registry.resolve(legacy_route)


def test_v3_oracle_covers_exactly_the_seeded_cases(v3_repository: Repository) -> None:
    oracle = json.loads(Path("evals/v3_decision_oracle.json").read_text(encoding="utf-8"))
    assert set(oracle) == set(v3_repository.case_ids())
    assert {item["route_type"] for item in oracle.values()} == set(BUSINESS_ROUTE_IDS)
    assert len(oracle) == 90


def test_decision_matrix_executes_all_ninety_seven_contract_decisions(
    v3_repository: Repository,
) -> None:
    oracle = json.loads(Path("evals/v3_decision_oracle.json").read_text(encoding="utf-8"))
    harness = DiagnosticHarness.heuristic_tests(v3_repository)
    registry = SkillRegistry(default_strategies(), known_tools=ToolRegistry(v3_repository).names)
    expected_decisions = {
        decision
        for pack in registry._packs.values()
        for route in pack.routes.values()
        for decision in route.allowed_decisions
        if decision != "manual_review"
    }
    observed_decisions = set()
    for case_id in v3_repository.case_ids():
        report = harness.diagnose_sync(v3_repository.case(case_id))
        expected = oracle[case_id]
        assert report.decision == expected["decision"]
        assert report.responsible_party == expected["responsible_party"]
        assert report.review_required == expected["review_required"]
        assert (report.action_plan.action_type if report.action_plan else None) == expected[
            "action_type"
        ]
        observed_decisions.add(report.decision)
        observed_decisions.update(
            event["decision"]
            for event in report.trace
            if event.get("event") == "COMPLIANCE_SUBCASE_COMPLETED"
        )
    assert observed_decisions == expected_decisions
    assert len(observed_decisions) == 97


def test_return_request_does_not_require_an_existing_return_record(
    v3_repository: Repository,
) -> None:
    with v3_repository.connect() as connection:
        connection.execute("DELETE FROM return_requests WHERE order_id = 'v3-order-10'")
    case = v3_repository.case("v3-return_request")
    report = DiagnosticHarness.heuristic_tests(v3_repository).diagnose_sync(case)
    assert report.decision == "return_condition_unknown"
    assert report.review_required is True
    assert "return_request" not in report.missing_evidence


def test_compliance_checks_are_neutral_check_routes(v3_repository: Repository) -> None:
    report = DiagnosticHarness.heuristic_tests(v3_repository).diagnose_sync(
        v3_repository.case("v3-product_information")
    )
    completed = {
        event["route"]: event["decision"]
        for event in report.trace
        if event.get("event") == "COMPLIANCE_SUBCASE_COMPLETED"
    }
    assert completed == {
        "business-statement-check": "business_statement_verified",
        "promise-grounding-check": "promise_grounded",
        "escalation-requirement-check": "escalation_not_required",
    }
