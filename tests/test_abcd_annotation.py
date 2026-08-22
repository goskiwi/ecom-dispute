import gzip
import json
from pathlib import Path

from ecom_dispute.abcd_annotation import (
    agreement_and_consensus,
    build_annotation_forms,
    rescore_first_run,
)


def test_blind_forms_hide_source_labels_and_predictions(tmp_path: Path) -> None:
    dataset = tmp_path / "abcd.json.gz"
    with gzip.open(dataset, "wt", encoding="utf-8") as stream:
        json.dump(
            {
                "test": [
                    {
                        "convo_id": 1,
                        "scenario": {"flow": "test", "subflow": "refund_status"},
                        "original": [["customer", "Where is my refund?"]],
                    }
                ],
                "dev": [],
                "train": [],
            },
            stream,
        )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "external_id": "abcd:1",
                        "subflow": "refund_status",
                        "expected_route_type": "refund",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    first = tmp_path / "rater1.json"
    second = tmp_path / "rater2.json"

    build_annotation_forms(dataset, manifest, first, second)
    payload = json.loads(first.read_text(encoding="utf-8"))

    serialized = json.dumps(payload)
    assert "refund_status" not in serialized
    assert "expected_route_type" not in serialized
    assert payload["items"][0]["annotation"]["primary_route"] is None


def test_agreement_and_rescore_use_completed_consensus(tmp_path: Path) -> None:
    annotation = {
        "supported": True,
        "has_dispute": True,
        "primary_route": "refund",
        "acceptable_routes": ["refund", "refund_amount"],
        "evidence_turns": [0],
        "reason": "refund status dispute",
        "confidence": "high",
    }
    form = {"items": [{"external_id": "abcd:1", "annotation": annotation}]}
    first = tmp_path / "r1.json"
    second = tmp_path / "r2.json"
    first.write_text(json.dumps(form), encoding="utf-8")
    second.write_text(json.dumps(form), encoding="utf-8")
    consensus = tmp_path / "consensus.json"

    agreement = agreement_and_consensus(first, second, consensus)

    assert agreement["exact_agreement"] == 1.0
    assert agreement["primary_route_kappa"] == 1.0
    raw = tmp_path / "raw.json.gz"
    with gzip.open(raw, "wt", encoding="utf-8") as stream:
        json.dump(
            {
                "results": [
                    {
                        "external_id": "abcd:1",
                        "observed_route_type": "refund_amount",
                    }
                ]
            },
            stream,
        )

    scored = rescore_first_run(raw, consensus)

    assert scored["strict_route_accuracy"] == 0.0
    assert scored["acceptable_route_accuracy"] == 1.0
