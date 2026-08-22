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

    detail = application.case("delivery_conflict_001")
    assert detail["report"]["decision"] == "delivery_event_conflict"
    assert detail["report"]["evidence"]
    assert any(item["kind"] == "logistics" for item in detail["report"]["evidence"])
