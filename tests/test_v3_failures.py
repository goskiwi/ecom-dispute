import json
from pathlib import Path

import pytest

from ecom_dispute.e2e_evaluation import prepare_e2e_database
from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.repository import Repository, rebuild_database


def test_each_business_route_fails_closed_when_required_evidence_is_missing(
    tmp_path: Path,
) -> None:
    repository, case_ids = prepare_e2e_database(
        tmp_path / "missing.db", Path("data/v3_failure_matrix_inputs.json")
    )
    oracle = json.loads(Path("evals/v3_failure_matrix_oracle.json").read_text(encoding="utf-8"))
    harness = DiagnosticHarness.heuristic_tests(repository)
    assert len(case_ids) == 26
    for case_id in case_ids:
        report = harness.diagnose_sync(repository.case(case_id))
        expected = oracle[case_id]
        assert report.decision == "manual_review"
        assert report.responsible_party == "undetermined"
        assert report.review_required is True
        assert set(expected["missing_evidence"]).issubset(report.missing_evidence)
        assert report.action_plan is None


@pytest.mark.parametrize("failure", [TimeoutError("upstream timeout"), ConnectionError("down")])
def test_transient_tool_failure_is_enveloped_and_fails_closed(
    tmp_path: Path, failure: Exception
) -> None:
    repository = Repository(rebuild_database(tmp_path / "transient.db"))
    harness = DiagnosticHarness.heuristic_tests(repository)

    def fail(order_id: str):
        raise failure

    harness.registry._executors["get_cart_events"] = fail
    report = harness.diagnose_sync(repository.case("v3-cart_issue"))
    core_event = next(
        event for event in report.trace if event.get("agent") == "core_evidence_executor"
    )
    result = next(
        item
        for item in core_event["telemetry"]["tool_results"]
        if item["tool"] == "get_cart_events"
    )
    assert result["status"] == "transient_error"
    assert result["error_code"] in {"TOOL_TIMEOUT", "TOOL_CONNECTION_ERROR"}
    assert report.decision == "manual_review"
    assert report.missing_evidence == ["cart_event"]
    assert report.action_plan is None


def test_cross_source_and_conversation_conflicts_remain_reviewable(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "conflicts.db"))
    harness = DiagnosticHarness.heuristic_tests(repository)
    refund = harness.diagnose_sync(repository.case("v3d-refund_record_conflict"))
    fulfillment = harness.diagnose_sync(repository.case("v3d-fulfillment_event_conflict"))
    statement = harness.diagnose_sync(repository.case("v3d-payment_order_state_conflict"))
    assert refund.decision == "refund_record_conflict" and refund.review_required
    assert fulfillment.decision == "fulfillment_event_conflict" and fulfillment.review_required
    assert any(event.get("decision") == "business_statement_conflict" for event in statement.trace)


def test_user_claim_conflict_is_joined_with_logistics_evidence(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "conversation-conflict.db"))
    with repository.connect() as connection:
        connection.execute(
            "UPDATE cases SET conversation_json = ? WHERE case_id = 'v3-delivered_not_received'",
            (
                json.dumps(
                    [
                        {
                            "speaker": "user",
                            "text": "物流显示已经送达，但我还没收到货。",
                        },
                        {"speaker": "agent", "text": "我会核验签收记录。"},
                    ],
                    ensure_ascii=False,
                ),
            ),
        )
    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("v3-delivered_not_received")
    )
    assert "用户称未收到货，但物流系统存在送达事件" in report.conflicts
    conflict = next(
        item for item in report.findings if item.category == "conversation_fact_conflict"
    )
    assert any(evidence_id.startswith("logistics_events:") for evidence_id in conflict.evidence_ids)


@pytest.mark.parametrize(
    "case_id",
    [
        "v3d-order_change_blocked",
        "v3d-exchange_inventory_unavailable",
        "v3d-price_adjustment_ineligible",
        "v3d-promotion_expired",
    ],
)
def test_failed_action_preconditions_do_not_create_action_plan(
    tmp_path: Path, case_id: str
) -> None:
    repository = Repository(rebuild_database(tmp_path / f"{case_id}.db"))
    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(repository.case(case_id))
    assert report.action_plan is None
