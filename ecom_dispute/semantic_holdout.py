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

    def run_one(repeat: int, case: dict) -> dict:
        expected = oracle[case["case_id"]]
        model_repairs = 0
        try:
            try:
                result = client.extract_conversation(case["conversation"])
            except ValueError as exc:
                model_repairs = 1
                result = client.extract_conversation(case["conversation"], str(exc))
        except (RuntimeError, ValueError) as exc:
            checks = {name: False for name in _scored_fields(expected)}
            return {
                "repeat": repeat,
                "case_id": case["case_id"],
                "checks": checks,
                "scored_fields": sorted(checks),
                "passed": False,
                "error": str(exc),
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0,
            }

        observed = {
            "user_business_facts": {
                _business_fact_key(item)
                for item in result.semantics.business_facts
                if item.speaker == "user"
            },
            "agent_business_facts": {
                _business_fact_key(item)
                for item in result.semantics.business_facts
                if item.speaker == "agent"
            },
            "user_interaction_acts": {
                _interaction_act_key(item)
                for item in result.semantics.interaction_acts
                if item.speaker == "user"
            },
            "agent_interaction_acts": {
                _interaction_act_key(item)
                for item in result.semantics.interaction_acts
                if item.speaker == "agent"
            },
        }
        wanted = {
            "user_business_facts": {
                _oracle_business_fact_key(item)
                for item in expected.get("expected_user_business_facts", [])
            },
            "agent_business_facts": {
                _oracle_business_fact_key(item)
                for item in expected.get("expected_agent_business_facts", [])
            },
            "user_interaction_acts": set(expected.get("expected_user_interaction_acts", [])),
            "agent_interaction_acts": set(expected.get("expected_agent_interaction_acts", [])),
        }
        checks = {
            "route_type": result.semantics.route_type == expected["route_type"],
            "has_business_exception": (
                result.semantics.has_business_exception == expected["has_business_exception"]
            ),
        }
        if "return_reason" in expected:
            reason = (
                result.semantics.return_reason.value if result.semantics.return_reason else None
            )
            checks["return_reason"] = reason == expected["return_reason"]
        for name, value in wanted.items():
            if f"expected_{name}" in expected:
                checks[name] = value == observed[name]
        return {
            "repeat": repeat,
            "case_id": case["case_id"],
            "checks": checks,
            "scored_fields": sorted(checks),
            "passed": all(checks.values()),
            "expected_route_type": expected["route_type"],
            "observed_route_type": result.semantics.route_type.value,
            "expected_has_business_exception": expected["has_business_exception"],
            "observed_has_business_exception": result.semantics.has_business_exception,
            **{f"expected_{name}": sorted(value) for name, value in wanted.items()},
            **{f"observed_{name}": sorted(value) for name, value in observed.items()},
            "response_id": result.response_id,
            "model": result.model,
            "model_repairs": model_repairs,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_ms": result.latency_ms,
        }

    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_one, repeat, case) for repeat, case in jobs]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: (item["repeat"], item["case_id"]))
    evaluated = [item for item in results if "error" not in item]
    per_repeat = []
    for repeat in range(1, repeats + 1):
        subset = [item for item in results if item["repeat"] == repeat]
        valid = [item for item in subset if "error" not in item]
        per_repeat.append(
            {
                "repeat": repeat,
                "passed": sum(item["passed"] for item in valid),
                "case_count": len(subset),
                "evaluated": len(valid),
                "api_errors": len(subset) - len(valid),
                "pass_rate": (
                    sum(item["passed"] for item in valid) / len(valid) if valid else None
                ),
            }
        )
    metrics = {
        name: _check_rate(evaluated, name)
        for name in (
            "route_type",
            "has_business_exception",
            "return_reason",
            "user_business_facts",
            "agent_business_facts",
            "user_interaction_acts",
            "agent_interaction_acts",
        )
    }
    return {
        "schema_version": 6,
        "mode": "semantic_holdout",
        "case_count": len(inputs),
        "repeats": repeats,
        "per_repeat": per_repeat,
        "evaluated": len(evaluated),
        "api_errors": len(results) - len(evaluated),
        **{f"{name}_accuracy": value for name, value in metrics.items()},
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
    scored = [item for item in results if name in item["checks"]]
    return sum(item["checks"][name] for item in scored) / len(scored) if scored else None


def _scored_fields(expected: dict) -> list[str]:
    fields = ["route_type", "has_business_exception"]
    if "return_reason" in expected:
        fields.append("return_reason")
    for name in (
        "user_business_facts",
        "agent_business_facts",
        "user_interaction_acts",
        "agent_interaction_acts",
    ):
        if f"expected_{name}" in expected:
            fields.append(name)
    return fields
