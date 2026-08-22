from pathlib import Path

from ecom_dispute.repository import Repository, rebuild_database
from ecom_dispute.web import DemoApplication


def test_demo_application_exposes_case_summary_and_evidence(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "web.db"))
    application = DemoApplication(repository)

    cases = application.cases()
    assert len(cases) == 60
    assert {item["business_type"] for item in cases} == {"refund", "delivery"}

    detail = application.case("delivery_conflict_001")
    assert detail["report"]["decision"] == "delivery_event_conflict"
    assert detail["report"]["evidence"]
    assert any(item["kind"] == "logistics" for item in detail["report"]["evidence"])
