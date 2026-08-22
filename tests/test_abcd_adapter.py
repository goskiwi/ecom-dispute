import gzip
import json
from pathlib import Path

from ecom_dispute.datasets import load_abcd_subset


def test_abcd_adapter_preserves_source_labels_and_actions(tmp_path: Path) -> None:
    path = tmp_path / "abcd.json.gz"
    payload = {
        "train": [],
        "dev": [],
        "test": [
            {
                "convo_id": 42,
                "scenario": {"flow": "product_defect", "subflow": "refund_status"},
                "original": [
                    ["customer", "Where is my refund?"],
                    ["agent", "I will check it."],
                    ["action", "Refund status lookup started."],
                ],
            },
            {
                "convo_id": 43,
                "scenario": {"flow": "account", "subflow": "password_reset"},
                "original": [["customer", "Reset my password."]],
            },
        ],
    }
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(payload, stream)

    records = load_abcd_subset(path, limit=10)

    assert len(records) == 1
    assert records[0].external_id == "abcd:42"
    assert records[0].subflow == "refund_status"
    assert records[0].conversation[0]["speaker"] == "user"
    assert records[0].expected_actions == ["Refund status lookup started."]
