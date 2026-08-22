import json
from pathlib import Path

from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.repository import Repository, rebuild_database


def _compliance_decisions(report) -> set[str]:
    return {
        finding.finding_id.removeprefix("compliance-")
        for finding in report.findings
        if finding.category == "service_compliance"
    }


def test_primary_and_compliance_subcases_are_fused(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "compliance.db"))
    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("refund_missing_005")
    )

    decisions = _compliance_decisions(report)
    assert report.decision == "refund_not_initiated_overdue"
    assert "false_statement_found" in decisions
    assert "required_escalation_missing" in decisions
    assert report.review_required
    assert sum(
        event.get("event") == "COMPLIANCE_SUBCASE_COMPLETED" for event in report.trace
    ) == 3
    assert any(
        evidence_id.startswith("policies:service-compliance")
        for evidence_id in report.policy_evidence_ids
    )


def test_supported_case_keeps_compliance_checks_without_violation(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "compliance-pass.db"))
    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("refund_complete_001")
    )

    decisions = _compliance_decisions(report)
    assert "false_statement_not_found" in decisions
    assert "unsupported_promise_not_found" in decisions
    assert "escalation_not_required" in decisions


def test_explicit_escalation_satisfies_review_requirement(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "compliance-escalation.db"))
    with repository.connect() as connection:
        connection.execute(
            "UPDATE cases SET conversation_json = ? WHERE case_id = 'refund_conflict_001'",
            (
                json.dumps(
                    [
                        {"speaker": "user", "text": "系统显示退款成功，但银行卡一直没入账。"},
                        {"speaker": "agent", "text": "我已提交复检并转人工处理。"},
                    ],
                    ensure_ascii=False,
                ),
            ),
        )
    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("refund_conflict_001")
    )

    decisions = _compliance_decisions(report)
    assert "required_escalation_present" in decisions
    assert "required_escalation_missing" not in decisions
