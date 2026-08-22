from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .llm import BusinessFact, InteractionAct, ResponsesClient


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
                "route_type": False,
                "has_dispute": False,
                "user_business_facts": False,
                "agent_business_facts": False,
                "user_interaction_acts": False,
                "agent_interaction_acts": False,
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

        observed_user_facts = {
            _business_fact_key(item)
            for item in result.semantics.business_facts
            if item.speaker == "user"
        }
        observed_agent_facts = {
            _business_fact_key(item)
            for item in result.semantics.business_facts
            if item.speaker == "agent"
        }
        observed_user_acts = {
            _interaction_act_key(item)
            for item in result.semantics.interaction_acts
            if item.speaker == "user"
        }
        observed_agent_acts = {
            _interaction_act_key(item)
            for item in result.semantics.interaction_acts
            if item.speaker == "agent"
        }
        expected_user_facts = {
            _oracle_business_fact_key(item) for item in expected["expected_user_business_facts"]
        }
        expected_agent_facts = {
            _oracle_business_fact_key(item) for item in expected["expected_agent_business_facts"]
        }
        expected_user_acts = set(expected["expected_user_interaction_acts"])
        expected_agent_acts = set(expected["expected_agent_interaction_acts"])
        checks = {
            "route_type": result.semantics.route_type == expected["route_type"],
            "has_dispute": result.semantics.has_dispute == expected["has_dispute"],
            "user_business_facts": expected_user_facts == observed_user_facts,
            "agent_business_facts": expected_agent_facts == observed_agent_facts,
            "user_interaction_acts": expected_user_acts == observed_user_acts,
            "agent_interaction_acts": expected_agent_acts == observed_agent_acts,
        }
        return {
            "repeat": repeat,
            "case_id": case["case_id"],
            "checks": checks,
            "passed": all(checks.values()),
            "expected_user_business_facts": sorted(expected_user_facts),
            "observed_user_business_facts": sorted(observed_user_facts),
            "expected_agent_business_facts": sorted(expected_agent_facts),
            "observed_agent_business_facts": sorted(observed_agent_facts),
            "expected_user_interaction_acts": sorted(expected_user_acts),
            "observed_user_interaction_acts": sorted(observed_user_acts),
            "expected_agent_interaction_acts": sorted(expected_agent_acts),
            "observed_agent_interaction_acts": sorted(observed_agent_acts),
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
    user_precision, user_recall = _set_precision_recall(evaluated_results, "user_business_facts")
    agent_precision, agent_recall = _set_precision_recall(evaluated_results, "agent_business_facts")
    user_act_precision, user_act_recall = _set_precision_recall(
        evaluated_results, "user_interaction_acts"
    )
    agent_act_precision, agent_act_recall = _set_precision_recall(
        evaluated_results, "agent_interaction_acts"
    )
    return {
        "schema_version": 5,
        "mode": "semantic_holdout",
        "case_count": len(inputs),
        "repeats": repeats,
        "per_repeat": per_repeat,
        "evaluated": len(evaluated_results),
        "api_errors": len(results) - len(evaluated_results),
        "route_type_accuracy": _check_rate(evaluated_results, "route_type"),
        "has_dispute_accuracy": _check_rate(evaluated_results, "has_dispute"),
        "user_business_fact_exact_match": _check_rate(evaluated_results, "user_business_facts"),
        "agent_business_fact_exact_match": _check_rate(evaluated_results, "agent_business_facts"),
        "user_business_fact_precision": user_precision,
        "user_business_fact_recall": user_recall,
        "agent_business_fact_precision": agent_precision,
        "agent_business_fact_recall": agent_recall,
        "user_interaction_act_exact_match": _check_rate(evaluated_results, "user_interaction_acts"),
        "agent_interaction_act_exact_match": _check_rate(
            evaluated_results, "agent_interaction_acts"
        ),
        "user_interaction_act_precision": user_act_precision,
        "user_interaction_act_recall": user_act_recall,
        "agent_interaction_act_precision": agent_act_precision,
        "agent_interaction_act_recall": agent_act_recall,
        "input_tokens": sum(item["input_tokens"] for item in results),
        "output_tokens": sum(item["output_tokens"] for item in results),
        "latency_ms": sum(item["latency_ms"] for item in results),
        "results": results,
    }


def _business_fact_key(item: BusinessFact) -> tuple[str, str, str, str]:
    return (
        item.fact_type.value,
        item.polarity.value,
        item.fact_mode.value,
        item.time_relation.value,
    )


def _oracle_business_fact_key(item: dict) -> tuple[str, str, str, str]:
    return (
        item["fact_type"],
        item["polarity"],
        item["fact_mode"],
        item["time_relation"],
    )


def _interaction_act_key(item: InteractionAct) -> str:
    return item.speech_act.value


def _check_rate(results: list[dict], name: str) -> float | None:
    return sum(item["checks"][name] for item in results) / len(results) if results else None


def _set_precision_recall(results: list[dict], field: str) -> tuple[float | None, float | None]:
    expected_total = observed_total = matched_total = 0
    for item in results:
        expected = {
            tuple(value) if isinstance(value, list) else value
            for value in item[f"expected_{field}"]
        }
        observed = {
            tuple(value) if isinstance(value, list) else value
            for value in item[f"observed_{field}"]
        }
        expected_total += len(expected)
        observed_total += len(observed)
        matched_total += len(expected & observed)
    precision = matched_total / observed_total if observed_total else None
    recall = matched_total / expected_total if expected_total else None
    return precision, recall
