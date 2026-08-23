from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .agent_ablation import compare_agent_layers
from .agents import ConversationAgent
from .e2e_evaluation import prepare_e2e_database
from .llm import ResponsesClient


def evaluate_gap_ablation(
    client: ResponsesClient,
    db_path: Path,
    input_path: Path,
    oracle_path: Path,
    workers: int = 1,
) -> dict:
    repository, case_ids = prepare_e2e_database(db_path, input_path)
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))

    def run_one(case_id: str) -> dict:
        case = repository.case(case_id)
        expected = oracle[case_id]
        try:
            conversation = asyncio.run(ConversationAgent(client).run(case))
            comparison = compare_agent_layers(repository, case, conversation, client)
        except (RuntimeError, ValueError) as exc:
            return {"case_id": case_id, "error": str(exc)}
        route_type = str(conversation.telemetry["route_type"])
        modes = comparison["modes"]
        checks = {
            "route_type": route_type == expected["route_type"],
            "core_decision": _decision_matches(modes["core"], expected),
            "gap_decision": _decision_matches(modes["gap"], expected),
            "full_decision": _decision_matches(modes["full"], expected),
            "gap_tool": modes["gap"]["selected_lazy_tool"] == expected["expected_gap_tool"],
            "full_gap_tool": modes["full"]["selected_lazy_tool"] == expected["expected_gap_tool"],
            "gap_tool_status": modes["gap"]["lazy_tool_status"] == expected["expected_tool_status"],
            "full_gap_tool_status": modes["full"]["lazy_tool_status"]
            == expected["expected_tool_status"],
        }
        expected_kind = expected.get("expected_added_evidence_kind")
        if expected_kind:
            checks["gap_evidence_kind"] = expected_kind in modes["gap"]["evidence_kinds"]
            checks["full_gap_evidence_kind"] = expected_kind in modes["full"]["evidence_kinds"]
        else:
            checks["gap_evidence_kind"] = (
                modes["gap"]["evidence_count"] == modes["core"]["evidence_count"]
            )
            checks["full_gap_evidence_kind"] = (
                modes["full"]["evidence_count"] == modes["core"]["evidence_count"]
            )
        return {
            "case_id": case_id,
            "route_type": route_type,
            "expected": expected,
            "checks": checks,
            "passed": all(checks.values()),
            "shared_conversation": comparison["shared_conversation"],
            "modes": modes,
        }

    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_one, case_id): case_id for case_id in case_ids}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item["case_id"])
    valid = [item for item in results if "error" not in item]
    correctly_routed = [item for item in valid if item["checks"]["route_type"]]
    return {
        "mode": "v3_evidence_gap_ablation",
        "case_count": len(case_ids),
        "evaluated": len(valid),
        "api_errors": len(results) - len(valid),
        "passed": sum(item["passed"] for item in valid),
        "route_accuracy": _rate(valid, "route_type"),
        "gap_tool_accuracy": _rate(valid, "gap_tool"),
        "full_gap_tool_accuracy": _rate(valid, "full_gap_tool"),
        "gap_tool_accuracy_on_correct_route": _rate(correctly_routed, "gap_tool"),
        "full_gap_tool_accuracy_on_correct_route": _rate(correctly_routed, "full_gap_tool"),
        "gap_tool_status_accuracy": _rate(valid, "gap_tool_status"),
        "full_gap_tool_status_accuracy": _rate(valid, "full_gap_tool_status"),
        "core_decision_accuracy": _rate(valid, "core_decision"),
        "gap_decision_accuracy": _rate(valid, "gap_decision"),
        "full_decision_accuracy": _rate(valid, "full_decision"),
        "gap_full_selection_agreement": (
            sum(
                item["modes"]["gap"]["selected_lazy_tool"]
                == item["modes"]["full"]["selected_lazy_tool"]
                for item in valid
            )
            / len(valid)
            if valid
            else None
        ),
        "gap_selection": _selection_metrics(valid, "gap"),
        "full_gap_selection": _selection_metrics(valid, "full"),
        "conversation_input_tokens": sum(
            item["shared_conversation"].get("input_tokens", 0) for item in valid
        ),
        "conversation_output_tokens": sum(
            item["shared_conversation"].get("output_tokens", 0) for item in valid
        ),
        "conversation_latency_ms": sum(
            item["shared_conversation"].get("latency_ms", 0) for item in valid
        ),
        "gap_increment": _increment(valid, "gap"),
        "full_increment": _increment(valid, "full"),
        "results": results,
    }


def _decision_matches(observed: dict, expected: dict) -> bool:
    return (
        observed["decision"] == expected["decision"]
        and observed["responsible_party"] == expected["responsible_party"]
        and observed["review_required"] == expected["review_required"]
    )


def _rate(results: list[dict], name: str) -> float | None:
    return sum(item["checks"][name] for item in results) / len(results) if results else None


def _increment(results: list[dict], mode: str) -> dict:
    return {
        "input_tokens": sum(item["modes"][mode]["incremental_input_tokens"] for item in results),
        "output_tokens": sum(item["modes"][mode]["incremental_output_tokens"] for item in results),
        "latency_ms": sum(item["modes"][mode]["incremental_latency_ms"] for item in results),
        "evidence_gain": sum(
            item["modes"][mode]["evidence_count"] - item["modes"]["core"]["evidence_count"]
            for item in results
        ),
    }


def _selection_metrics(results: list[dict], mode: str) -> dict:
    expected = sum(item["expected"]["expected_gap_tool"] is not None for item in results)
    predicted = sum(item["modes"][mode]["selected_lazy_tool"] is not None for item in results)
    matched = sum(
        item["modes"][mode]["selected_lazy_tool"] == item["expected"]["expected_gap_tool"]
        and item["expected"]["expected_gap_tool"] is not None
        for item in results
    )
    return {
        "expected": expected,
        "predicted": predicted,
        "matched": matched,
        "precision": matched / predicted if predicted else None,
        "recall": matched / expected if expected else None,
    }
