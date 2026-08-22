from __future__ import annotations

import gzip
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

DEFAULT_SUBFLOWS = frozenset(
    {
        "refund_status",
        "refund_update",
        "refund_initiate",
        "return_size",
        "return_color",
        "return_stain",
        "status_delivery_time",
        "status_shipping_question",
        "mistimed_billing_already_returned",
    }
)


class ABCDRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str
    split: str
    flow: str
    subflow: str
    conversation: list[dict[str, str]]
    expected_actions: list[str]


def load_abcd_subset(
    path: Path,
    *,
    limit: int = 50,
    subflows: set[str] | frozenset[str] | None = DEFAULT_SUBFLOWS,
    splits: tuple[str, ...] = ("test", "dev", "train"),
) -> list[ABCDRecord]:
    if limit < 1:
        raise ValueError("ABCD subset limit must be positive")
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            dataset = json.load(stream)
    else:
        with path.open("rt", encoding="utf-8") as stream:
            dataset = json.load(stream)
    records = []
    for split in splits:
        rows = dataset.get(split, [])
        for row in sorted(rows, key=lambda item: int(item["convo_id"])):
            scenario = row["scenario"]
            if subflows is not None and scenario["subflow"] not in subflows:
                continue
            conversation = []
            actions = []
            for speaker, text in row["original"]:
                if speaker == "action":
                    actions.append(text)
                    continue
                conversation.append(
                    {"speaker": "user" if speaker == "customer" else "agent", "text": text}
                )
            records.append(
                ABCDRecord(
                    external_id=f"abcd:{row['convo_id']}",
                    split=split,
                    flow=scenario["flow"],
                    subflow=scenario["subflow"],
                    conversation=conversation,
                    expected_actions=actions,
                )
            )
            if len(records) == limit:
                return records
    return records
