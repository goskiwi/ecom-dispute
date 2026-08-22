from __future__ import annotations

import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .contracts import SpeechAct
from .datasets import load_abcd_subset
from .llm import ResponsesClient

SUPPORTED_SUBFLOWS = {
    "refund_status": "refund",
    "refund_update": "refund",
    "refund_initiate": "refund",
    "mistimed_billing_already_returned": "refund",
    "return_size": "return_eligibility",
    "return_color": "return_eligibility",
    "status_delivery_time": "delivery",
    "status_shipping_question": "delivery",
}


def build_abcd_manifest(dataset_path: Path, manifest_path: Path) -> dict:
    records = load_abcd_subset(dataset_path, limit=100_000, subflows=None)
    supported: dict[str, list] = defaultdict(list)
    unsupported: dict[str, list] = defaultdict(list)
    for record in records:
        target = supported if record.subflow in SUPPORTED_SUBFLOWS else unsupported
        target[record.subflow].append(record)

    items = []
    for subflow, route in SUPPORTED_SUBFLOWS.items():
        chosen = supported[subflow][:20]
        if len(chosen) < 20:
            raise ValueError(f"ABCD subflow has fewer than 20 records: {subflow}")
        items.extend(_manifest_item(record, route) for record in chosen)

    unsupported_counts: Counter[str] = Counter()
    for subflow in sorted(unsupported):
        for record in unsupported[subflow]:
            if unsupported_counts[subflow] >= 5:
                break
            items.append(_manifest_item(record, "other"))
            unsupported_counts[subflow] += 1
            if sum(unsupported_counts.values()) == 40:
                break
        if sum(unsupported_counts.values()) == 40:
            break
    if sum(unsupported_counts.values()) != 40:
        raise ValueError("could not select 40 unsupported ABCD records")
    items.sort(key=lambda item: item["external_id"])
    payload = {
        "source": "ABCD v1.1 official dataset",
        "supported_count": 160,
        "unsupported_count": 40,
        "items": items,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "case_count": len(items),
        "supported": 160,
        "unsupported": 40,
        "subflows": Counter(item["subflow"] for item in items),
    }


def evaluate_abcd(
    client: ResponsesClient,
    dataset_path: Path,
    manifest_path: Path,
    workers: int = 4,
) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    wanted = {item["external_id"]: item for item in manifest["items"]}
    subflows = {item["subflow"] for item in manifest["items"]}
    records = {
        item.external_id: item
        for item in load_abcd_subset(
            dataset_path,
            limit=100_000,
            subflows=subflows,
        )
        if item.external_id in wanted
    }
    if set(records) != set(wanted):
        missing = sorted(set(wanted) - set(records))
        raise ValueError(f"ABCD manifest records missing from dataset: {missing[:5]}")

    def run_one(external_id: str) -> dict:
        record = records[external_id]
        expected = wanted[external_id]
        try:
            result = client.extract_conversation(record.conversation)
        except (RuntimeError, ValueError) as exc:
            return {"external_id": external_id, "error": str(exc)}
        predicted_action = any(
            item.speaker == "agent" and item.speech_act == SpeechAct.ACTION
            for item in result.semantics.interaction_acts
        )
        return {
            "external_id": external_id,
            "split": record.split,
            "subflow": record.subflow,
            "expected_route_type": expected["expected_route_type"],
            "observed_route_type": result.semantics.route_type,
            "route_correct": result.semantics.route_type == expected["expected_route_type"],
            "expected_action_present": expected["expected_action_present"],
            "observed_action_present": predicted_action,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_ms": result.latency_ms,
        }

    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_one, item): item for item in wanted}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item["external_id"])
    valid = [item for item in results if "error" not in item]
    supported = [item for item in valid if item["expected_route_type"] != "other"]
    rejected = [item for item in valid if item["expected_route_type"] == "other"]
    action_tp = sum(
        item["expected_action_present"] and item["observed_action_present"] for item in valid
    )
    action_predicted = sum(item["observed_action_present"] for item in valid)
    action_expected = sum(item["expected_action_present"] for item in valid)
    return {
        "mode": "abcd_external_first_run",
        "case_count": len(wanted),
        "evaluated": len(valid),
        "api_errors": len(results) - len(valid),
        "route_accuracy": _mean(item["route_correct"] for item in valid),
        "supported_route_accuracy": _mean(item["route_correct"] for item in supported),
        "unsupported_rejection_accuracy": _mean(item["route_correct"] for item in rejected),
        "action_presence_precision": action_tp / action_predicted if action_predicted else None,
        "action_presence_recall": action_tp / action_expected if action_expected else None,
        "input_tokens": sum(item["input_tokens"] for item in valid),
        "output_tokens": sum(item["output_tokens"] for item in valid),
        "latency_ms": sum(item["latency_ms"] for item in valid),
        "per_subflow": {
            subflow: {
                "count": len(rows),
                "route_accuracy": _mean(item["route_correct"] for item in rows),
            }
            for subflow in sorted({item["subflow"] for item in valid})
            if (rows := [item for item in valid if item["subflow"] == subflow])
        },
        "results": results,
    }


def _manifest_item(record: object, route: str) -> dict:
    return {
        "external_id": record.external_id,
        "split": record.split,
        "subflow": record.subflow,
        "expected_route_type": route,
        "expected_action_present": bool(record.expected_actions),
    }


def _mean(values: object) -> float | None:
    items = list(values)
    return sum(items) / len(items) if items else None
