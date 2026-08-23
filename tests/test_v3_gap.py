import json
from pathlib import Path

import pytest

from ecom_dispute.agents import EvidenceGapAgent
from ecom_dispute.e2e_evaluation import prepare_e2e_database
from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.repository import Repository, rebuild_database


class FakeGapClient:
    model = "fake-gap"

    def __init__(self, needs_more_evidence: bool, tool_id: str | None):
        self.needs_more_evidence = needs_more_evidence
        self.tool_id = tool_id

    def create_response(self, payload: dict) -> dict:
        plan = {
            "needs_more_evidence": self.needs_more_evidence,
            "tool_id": self.tool_id,
            "reason": "test plan",
        }
        return {
            "id": "gap-plan",
            "model": self.model,
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(plan)}],
                }
            ],
        }


def _harness(repository: Repository, client: FakeGapClient) -> DiagnosticHarness:
    harness = DiagnosticHarness.heuristic_tests(repository)
    harness.evidence_gap_agent = EvidenceGapAgent(
        client,  # type: ignore[arg-type]
        harness.tool_runtime,
        harness.tool_surface_resolver,
    )
    return harness


def test_five_routes_have_one_lazy_tool_outside_core_surface(tmp_path: Path) -> None:
    repository = Repository(rebuild_database(tmp_path / "routes.db"))
    harness = DiagnosticHarness.heuristic_tests(repository)
    expected = {
        "unrecognized_charge": "get_payment_gateway_events",
        "refund_amount_mismatch": "get_payment_gateway_events",
        "received_item_mismatch": "get_claim_attachments",
        "delivered_not_received": "get_delivery_address",
        "item_condition_issue": "get_logistics_events",
    }
    for business_type, lazy_tool in expected.items():
        route = harness.skills.resolve(business_type).route
        assert route.lazy_tools == (lazy_tool,)
        assert lazy_tool not in route.core_tools


def test_selected_lazy_tool_adds_negative_query_evidence(tmp_path: Path) -> None:
    repository, _ = prepare_e2e_database(
        tmp_path / "negative.db", Path("data/v3_1_gap_12_inputs.json")
    )
    report = _harness(repository, FakeGapClient(True, "get_delivery_address")).diagnose_sync(
        repository.case("v3gap-delivery-address-negative")
    )
    gap = next(event for event in report.trace if event.get("agent") == "evidence_gap")
    assert gap["telemetry"]["selected_tool"] == "get_delivery_address"
    assert gap["telemetry"]["tool_status"] == "not_found"
    assert any(
        item.kind.value == "query" and item.source == "query:delivery_addresses"
        for item in report.evidence
    )


def test_gap_can_decline_lazy_tool_when_core_evidence_is_sufficient(
    tmp_path: Path,
) -> None:
    repository, _ = prepare_e2e_database(
        tmp_path / "decline.db", Path("data/v3_1_gap_12_inputs.json")
    )
    report = _harness(repository, FakeGapClient(False, None)).diagnose_sync(
        repository.case("v3gap-refund-amount-not-needed")
    )
    gap = next(event for event in report.trace if event.get("agent") == "evidence_gap")
    assert gap["telemetry"]["selected_tool"] is None
    assert gap["tool_calls"] == []


def test_gap_rejects_tool_outside_current_route(tmp_path: Path) -> None:
    repository, _ = prepare_e2e_database(
        tmp_path / "outside.db", Path("data/v3_1_gap_12_inputs.json")
    )
    with pytest.raises(ValueError, match="outside route"):
        _harness(repository, FakeGapClient(True, "get_refund_records")).diagnose_sync(
            repository.case("v3gap-item-mismatch-needed")
        )
