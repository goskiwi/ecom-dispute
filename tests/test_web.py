from pathlib import Path

from ecom_dispute.agents import HeuristicConversationStub
from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.repository import Repository, rebuild_database
from ecom_dispute.web import DemoApplication


def test_demo_application_exposes_case_summary_and_evidence(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "web.db"))
    harness = DiagnosticHarness(repository, HeuristicConversationStub())
    application = DemoApplication(repository, harness, "heuristic-test")

    cases = application.cases()
    assert len(cases) == 152
    assert {item["business_type"] for item in cases} == {
        "refund",
        "delivery",
        "refund_amount",
        "duplicate_charge",
        "payment_order_failure",
        "merchant_not_shipped",
        "delivered_not_received",
        "cancellation_in_transit",
        "return_eligibility",
        "wrong_item",
        "missing_item",
        "damaged_item",
    }
    assert all(item["run_status"] == "not_run" for item in cases)
    assert all(item["decision"] is None for item in cases)

    detail = application.case("delivery_conflict_001")
    assert detail["report"] is None

    detail = application.run_case("delivery_conflict_001")
    assert detail["report"]["decision"] == "delivery_event_conflict"
    assert detail["report"]["evidence"]
    assert any(item["kind"] == "logistics" for item in detail["report"]["evidence"])
    assert next(
        item for item in application.cases() if item["case_id"] == "delivery_conflict_001"
    )["run_status"] == "completed"


def test_demo_application_caches_single_case_run(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "web-cache.db"))
    delegate = DiagnosticHarness(repository, HeuristicConversationStub())

    class CountingHarness:
        calls = 0

        def diagnose_sync(self, case):
            self.calls += 1
            return delegate.diagnose_sync(case)

    harness = CountingHarness()
    application = DemoApplication(repository, harness, "heuristic-test")  # type: ignore[arg-type]

    application.run_case("refund_complete_001")
    application.run_case("refund_complete_001")

    assert harness.calls == 1
