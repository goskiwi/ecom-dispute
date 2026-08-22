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
    assert result["case_count"] == 40
    assert result["passed"] == 40
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
