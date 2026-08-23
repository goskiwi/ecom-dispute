import gzip
import json
from pathlib import Path

from ecom_dispute.abcd_evaluation import build_abcd_manifest


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
