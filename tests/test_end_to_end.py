from pathlib import Path

import pytest

from ecom_dispute.evaluation import evaluate
from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.repository import Repository, rebuild_database


@pytest.fixture()
def repository(tmp_path: Path) -> Repository:
    db_path = rebuild_database(tmp_path / "test.db")
    return Repository(db_path)


@pytest.mark.parametrize(
    ("case_id", "decision", "party", "review"),
    [
        ("refund_missing_001", "refund_not_initiated_overdue", "platform", False),
        ("refund_pending_001", "refund_processing_within_sla", "none", False),
        ("refund_complete_001", "refund_completed", "none", False),
        ("refund_conflict_001", "refund_record_conflict", "undetermined", True),
    ],
)
def test_refund_vertical_slice(
    repository: Repository, case_id: str, decision: str, party: str, review: bool
) -> None:
    report = DiagnosticHarness(repository).diagnose_sync(repository.case(case_id))
    assert report.decision == decision
    assert report.responsible_party == party
    assert report.review_required is review
    assert report.policy_evidence_ids
    assert report.evidence_ids
    assert all(finding.evidence_ids for finding in report.findings)
    assert report.trace[1]["telemetry"]["mode"] == "offline"


def test_conflict_is_evidence_grounded(repository: Repository) -> None:
    report = DiagnosticHarness(repository).diagnose_sync(repository.case("refund_conflict_001"))
    conflict = next(item for item in report.findings if item.category == "fact_conflict")
    assert conflict.review_recommended
    assert any(evidence_id.startswith("refunds:") for evidence_id in conflict.evidence_ids)
    assert any(evidence_id.startswith("payments:") for evidence_id in conflict.evidence_ids)


def test_fixed_eval_set(repository: Repository) -> None:
    result = evaluate(repository)
    assert result["case_count"] == 60
    assert result["passed"] == 60
    assert result["pass_rate"] == 1.0


def test_dataset_has_manual_and_policy_boundary_cases(repository: Repository) -> None:
    cases = [repository.case(case_id) for case_id in repository.case_ids()]
    assert sum(case.source_type == "manual" for case in cases) >= 8
    historical = repository.case("refund_historical_policy_001")
    report = DiagnosticHarness(repository).diagnose_sync(historical)
    assert report.policy_evidence_ids == ["policies:refund-cn-standard:v1"]


@pytest.mark.parametrize(
    ("case_id", "expected"),
    [
        ("refund_missing_005", True),
        ("refund_missing_008", True),
        ("refund_pending_005", True),
        ("refund_within_003", True),
        ("refund_missing_007", False),
    ],
)
def test_conversation_commitments_join_fact_fusion(
    repository: Repository, case_id: str, expected: bool
) -> None:
    report = DiagnosticHarness(repository).diagnose_sync(repository.case(case_id))
    actual = any(item.category == "conversation_fact_conflict" for item in report.findings)
    assert actual is expected


def test_false_commitment_cites_negative_refund_query(repository: Repository) -> None:
    report = DiagnosticHarness(repository).diagnose_sync(repository.case("refund_missing_005"))
    conflict = next(
        item for item in report.findings if item.category == "conversation_fact_conflict"
    )
    assert any(item.startswith("query:refunds:") for item in conflict.evidence_ids)
    assert any(item.startswith("query:refunds:") for item in report.evidence_ids)


@pytest.mark.parametrize(
    ("case_id", "decision", "party", "review"),
    [
        ("delivery_ontime_001", "delivery_completed_on_time", "none", False),
        ("delivery_within_002", "delivery_in_transit_within_sla", "none", False),
        ("delivery_logistics_002", "delivery_delay_logistics", "logistics_provider", False),
        ("delivery_merchant_001", "delivery_delay_merchant", "merchant", False),
        ("delivery_force_majeure_001", "delivery_delay_force_majeure", "none", False),
        ("delivery_conflict_001", "delivery_event_conflict", "undetermined", True),
        ("delivery_late_001", "delivery_completed_late", "logistics_provider", False),
    ],
)
def test_delivery_skill_vertical_slice(
    repository: Repository, case_id: str, decision: str, party: str, review: bool
) -> None:
    report = DiagnosticHarness(repository).diagnose_sync(repository.case(case_id))
    assert report.dispute_type == "delivery_delay"
    assert report.decision == decision
    assert report.responsible_party == party
    assert report.review_required is review
    tool_calls = {tool for event in report.trace for tool in event.get("tool_calls", [])}
    assert tool_calls == {"get_order", "get_logistics_events", "read_policy"}


def test_delivery_false_completion_claim_joins_logistics_evidence(
    repository: Repository,
) -> None:
    report = DiagnosticHarness(repository).diagnose_sync(repository.case("delivery_conflict_001"))
    conflict = next(
        item for item in report.findings if item.category == "conversation_fact_conflict"
    )
    assert any(item.startswith("logistics_events:") for item in conflict.evidence_ids)
