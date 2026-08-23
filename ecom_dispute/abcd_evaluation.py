from __future__ import annotations

import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .contracts import SpeechAct
from .datasets import load_abcd_subset
from .llm import ResponsesClient


def build_abcd_manifest(dataset_path: Path, manifest_path: Path, case_count: int = 200) -> dict:
    records = load_abcd_subset(dataset_path, limit=100_000, subflows=None)
    grouped: dict[str, list] = defaultdict(list)
    for record in records:
        grouped[record.subflow].append(record)
    for rows in grouped.values():
        rows.sort(key=lambda item: item.external_id)

    selected = []
    depth = 0
    while len(selected) < case_count:
        added = 0
        for subflow in sorted(grouped):
            if depth < len(grouped[subflow]):
                selected.append(grouped[subflow][depth])
                added += 1
                if len(selected) == case_count:
                    break
        if not added:
            break
        depth += 1
    if len(selected) != case_count:
        raise ValueError(f"ABCD dataset contains only {len(selected)} selectable records")

    items = [
        {
            "external_id": record.external_id,
            "split": record.split,
            "subflow": record.subflow,
            "expected_action_present": bool(record.expected_actions),
        }
        for record in sorted(selected, key=lambda item: item.external_id)
    ]
    payload = {
        "source": "ABCD v1.1 official dataset",
        "schema_version": 3,
        "case_count": len(items),
        "selection_method": "round_robin_across_all_subflows_no_route_oracle",
        "items": items,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "case_count": len(items),
        "subflows": Counter(item["subflow"] for item in items),
        "route_oracle": False,
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
        for item in load_abcd_subset(dataset_path, limit=100_000, subflows=subflows)
        if item.external_id in wanted
    }
    if set(records) != set(wanted):
        missing = sorted(set(wanted) - set(records))
        raise ValueError(f"ABCD manifest records missing from dataset: {missing[:5]}")

    def run_one(external_id: str) -> dict:
        record = records[external_id]
        manifest_item = wanted[external_id]
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
            "observed_route_type": result.semantics.route_type.value,
            "observed_has_business_exception": result.semantics.has_business_exception,
            "expected_action_present": manifest_item["expected_action_present"],
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
    action_matches = sum(
        item["expected_action_present"] == item["observed_action_present"] for item in valid
    )
    return {
        "mode": "abcd_external_v3_unscored",
        "case_count": len(wanted),
        "evaluated": len(valid),
        "api_errors": len(results) - len(valid),
        "route_accuracy": None,
        "route_accuracy_status": "requires per-dialogue human consensus",
        "route_distribution": Counter(item["observed_route_type"] for item in valid),
        "business_exception_rate": (
            sum(item["observed_has_business_exception"] for item in valid) / len(valid)
            if valid
            else None
        ),
        "action_presence_agreement": action_matches / len(valid) if valid else None,
        "input_tokens": sum(item["input_tokens"] for item in valid),
        "output_tokens": sum(item["output_tokens"] for item in valid),
        "latency_ms": sum(item["latency_ms"] for item in valid),
        "results": results,
    }
