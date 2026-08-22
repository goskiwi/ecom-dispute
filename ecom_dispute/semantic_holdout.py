from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .llm import AtomicFact, ResponsesClient


def evaluate_holdout(
    client: ResponsesClient,
    input_path: Path,
    oracle_path: Path,
    repeats: int = 3,
    workers: int = 1,
) -> dict:
    inputs = json.loads(input_path.read_text(encoding="utf-8"))["cases"]
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    jobs = [(repeat, case) for repeat in range(1, repeats + 1) for case in inputs]
    results = []

    def run_one(repeat: int, case: dict) -> dict:
        expected = oracle[case["case_id"]]
        try:
            result = client.extract_conversation(case["conversation"])
        except (RuntimeError, ValueError) as exc:
            checks = {
                "business_type": False,
                "has_dispute": False,
                "user_facts": False,
                "agent_facts": False,
            }
            return {
                "repeat": repeat,
                "case_id": case["case_id"],
                "checks": checks,
                "passed": False,
                "error": str(exc),
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0,
            }

        observed_user = {
            _fact_key(item) for item in result.semantics.facts if item.speaker == "user"
        }
        observed_agent = {
            _fact_key(item) for item in result.semantics.facts if item.speaker == "agent"
        }
        expected_user = {_oracle_key(item) for item in expected["expected_user_facts"]}
        expected_agent = {_oracle_key(item) for item in expected["expected_agent_facts"]}
        checks = {
            "business_type": result.semantics.business_type == expected["business_type"],
            "has_dispute": result.semantics.has_dispute == expected["has_dispute"],
            "user_facts": expected_user == observed_user,
            "agent_facts": expected_agent == observed_agent,
        }
        return {
            "repeat": repeat,
            "case_id": case["case_id"],
            "checks": checks,
            "passed": all(checks.values()),
            "expected_user_facts": sorted(expected_user),
            "observed_user_facts": sorted(observed_user),
            "expected_agent_facts": sorted(expected_agent),
            "observed_agent_facts": sorted(observed_agent),
            "response_id": result.response_id,
            "model": result.model,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_ms": result.latency_ms,
        }

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_one, repeat, case) for repeat, case in jobs]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: (item["repeat"], item["case_id"]))

    per_repeat = []
    for repeat in range(1, repeats + 1):
        subset = [item for item in results if item["repeat"] == repeat]
        evaluated = [item for item in subset if "error" not in item]
        per_repeat.append(
            {
                "repeat": repeat,
                "passed": sum(item["passed"] for item in evaluated),
                "case_count": len(subset),
                "evaluated": len(evaluated),
                "api_errors": len(subset) - len(evaluated),
                "pass_rate": (
                    sum(item["passed"] for item in evaluated) / len(evaluated)
                    if evaluated
                    else None
                ),
            }
        )
    evaluated_results = [item for item in results if "error" not in item]
    user_precision, user_recall = _fact_precision_recall(evaluated_results, "user")
    agent_precision, agent_recall = _fact_precision_recall(evaluated_results, "agent")
    return {
        "schema_version": 2,
        "mode": "semantic_holdout",
        "case_count": len(inputs),
        "repeats": repeats,
        "per_repeat": per_repeat,
        "evaluated": len(evaluated_results),
        "api_errors": len(results) - len(evaluated_results),
        "business_type_accuracy": _check_rate(evaluated_results, "business_type"),
        "has_dispute_accuracy": _check_rate(evaluated_results, "has_dispute"),
        "user_fact_exact_match": _check_rate(evaluated_results, "user_facts"),
        "agent_fact_exact_match": _check_rate(evaluated_results, "agent_facts"),
        "user_fact_precision": user_precision,
        "user_fact_recall": user_recall,
        "agent_fact_precision": agent_precision,
        "agent_fact_recall": agent_recall,
        "input_tokens": sum(item["input_tokens"] for item in results),
        "output_tokens": sum(item["output_tokens"] for item in results),
        "latency_ms": sum(item["latency_ms"] for item in results),
        "results": results,
    }


def _fact_key(item: AtomicFact) -> tuple[str, str, str, str]:
    return (
        item.fact_type.value,
        item.polarity.value,
        item.temporal_status.value,
        item.speech_act.value,
    )


def _oracle_key(item: dict) -> tuple[str, str, str, str]:
    return (
        item["fact_type"],
        item["polarity"],
        item["temporal_status"],
        item["speech_act"],
    )


def _check_rate(results: list[dict], name: str) -> float | None:
    return sum(item["checks"][name] for item in results) / len(results) if results else None


def _fact_precision_recall(results: list[dict], speaker: str) -> tuple[float | None, float | None]:
    expected_total = observed_total = matched_total = 0
    for item in results:
        expected = {tuple(value) for value in item[f"expected_{speaker}_facts"]}
        observed = {tuple(value) for value in item[f"observed_{speaker}_facts"]}
        expected_total += len(expected)
        observed_total += len(observed)
        matched_total += len(expected & observed)
    precision = matched_total / observed_total if observed_total else None
    recall = matched_total / expected_total if expected_total else None
    return precision, recall
