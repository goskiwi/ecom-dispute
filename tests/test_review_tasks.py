from pathlib import Path

import pytest

from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.repository import Repository, rebuild_database


def test_review_task_can_be_resolved_and_is_not_overwritten(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "review.db"))
    harness = DiagnosticHarness.heuristic_tests(repository)
    report = harness.diagnose_sync(repository.case("refund_conflict_001"))

    assert report.review_required
    task = repository.review_task(report.case_id)
    assert task
    assert task.status == "pending"
    assert task.conflict_evidence_ids

    resolved = repository.resolve_review(
        report.case_id,
        report.decision,
        report.responsible_party,
        "已核对退款与支付流水",
    )
    assert resolved.status == "resolved"
    assert resolved.reviewer_comment == "已核对退款与支付流水"

    harness.diagnose_sync(repository.case("refund_conflict_001"))
    assert repository.review_task(report.case_id).status == "resolved"  # type: ignore[union-attr]


def test_resolved_review_cannot_be_resolved_twice(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "review-twice.db"))
    harness = DiagnosticHarness.heuristic_tests(repository)
    harness.diagnose_sync(repository.case("delivery_conflict_001"))
    repository.resolve_review(
        "delivery_conflict_001", "manual_review", "undetermined", "需要补充签收凭证"
    )
    with pytest.raises(ValueError, match="pending review task not found"):
        repository.resolve_review(
            "delivery_conflict_001", "manual_review", "undetermined", "重复提交"
        )
