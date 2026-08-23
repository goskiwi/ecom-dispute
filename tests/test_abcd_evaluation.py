import gzip
import json
from pathlib import Path

from ecom_dispute.abcd_evaluation import build_abcd_manifest, evaluate_abcd
from ecom_dispute.llm import ConversationSemantics, LLMResult
from ecom_dispute.ontology import BusinessRoute


def test_formal_abcd_manifest_is_stratified_before_model_run(tmp_path: Path) -> None:
    rows = []
    convo_id = 1
    for group in range(10):
        subflow = f"subflow_{group}"
        for _ in range(20):
            rows.append(_row(convo_id, subflow))
            convo_id += 1
    dataset = tmp_path / "abcd.json.gz"
    with gzip.open(dataset, "wt", encoding="utf-8") as stream:
        json.dump({"test": rows, "dev": [], "train": []}, stream)
    manifest = tmp_path / "manifest.json"

    result = build_abcd_manifest(dataset, manifest)
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    assert result["case_count"] == 200
    assert result["route_oracle"] is False
    assert len(payload["items"]) == 200
    assert "expected_route_type" not in payload["items"][0]
    assert payload["selection_method"] == "round_robin_across_all_subflows_no_route_oracle"


def _row(convo_id: int, subflow: str) -> dict:
    return {
        "convo_id": convo_id,
        "scenario": {"flow": "test", "subflow": subflow},
        "original": [
            ["customer", "I need help."],
            ["agent", "I will check."],
            ["action", "Lookup started."],
        ],
    }


class RepairingClient:
    calls = 0

    def extract_conversation(self, messages: list[dict], repair_hint: str | None = None):
        self.calls += 1
        if repair_hint is None:
            raise ValueError("return_reason is only valid for return_request")
        return LLMResult(
            semantics=ConversationSemantics(
                route_type=BusinessRoute.PRODUCT_INFORMATION,
                has_business_exception=False,
                return_reason=None,
                order_operation=None,
                item_mismatch_claim=None,
                business_facts=[],
                interaction_acts=[],
                uncertainty=None,
            ),
            response_id="repair",
            model="fake",
            input_tokens=10,
            output_tokens=5,
            latency_ms=1,
        )


def test_abcd_evaluation_repairs_one_schema_failure(tmp_path: Path) -> None:
    dataset = tmp_path / "abcd.json.gz"
    with gzip.open(dataset, "wt", encoding="utf-8") as stream:
        json.dump({"test": [_row(1, "product")], "dev": [], "train": []}, stream)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "external_id": "abcd:1",
                        "subflow": "product",
                        "expected_action_present": True,
                    }
                ]
            }
        )
    )
    client = RepairingClient()
    result = evaluate_abcd(client, dataset, manifest, workers=1)  # type: ignore[arg-type]
    assert result["evaluated"] == 1
    assert result["api_errors"] == 0
    assert result["model_repairs"] == 1
    assert client.calls == 2
