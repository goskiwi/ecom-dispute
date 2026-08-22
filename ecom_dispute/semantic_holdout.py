from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import StatementType, TemporalStatus
from .llm import ResponsesClient


class HoldoutMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: Literal["user", "agent"]
    text: str


class ExpectedSemanticFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement_type: StatementType
    temporal_status: TemporalStatus


class GeneratedHoldoutCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    conversation: list[HoldoutMessage] = Field(min_length=2, max_length=6)
    business_type: Literal["refund", "delivery"]
    has_dispute: bool
    expected_user_facts: list[ExpectedSemanticFact]
    expected_agent_facts: list[ExpectedSemanticFact]


class GeneratedHoldoutSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cases: list[GeneratedHoldoutCase] = Field(min_length=30, max_length=30)


class GeneratedHoldoutBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cases: list[GeneratedHoldoutCase] = Field(min_length=5, max_length=5)


def generate_holdout(
    client: ResponsesClient,
    input_path: Path,
    oracle_path: Path,
) -> dict:
    generated_cases = []
    responses = []
    allowed_types = ", ".join(item.value for item in StatementType)
    for business_type in ("refund", "delivery"):
        for batch_index in range(3):
            start = batch_index * 5 + 1
            end = start + 4
            prompt = (
                f"生成 5 个全新的中文电商 {business_type} 客服对话，用于独立测试另一个模型的语义抽取。"
                "本批必须混合正常查询、真实争议、复合句、口语、省略、未来承诺、当前或完成状态，"
                "并包含容易混淆的否定表达。不要复用常见示例句，不输出订单或政策事实。"
                f"case_id 严格使用 holdout_{business_type}_{start:03d}..{end:03d}。"
                "只输出 JSON，不要 Markdown。JSON 顶层为 cases 数组；每项包含 case_id、conversation、"
                "business_type、has_dispute、expected_user_facts、expected_agent_facts。conversation 消息"
                "包含 speaker 与 text；expected fact 包含 statement_type 与 temporal_status。"
                f"statement_type 只能是：{allowed_types}。"
                "temporal_status 只能是 future/current/completed/unknown。"
            )
            payload = {
                "model": client.model,
                "input": prompt,
                "max_output_tokens": 3000,
                "store": False,
            }
            response = client.create_response(payload)
            text = ResponsesClient._output_text(response).strip()
            if text.startswith("```"):
                text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            batch = GeneratedHoldoutBatch.model_validate_json(text)
            generated_cases.extend(batch.cases)
            responses.append(response)
    generated = GeneratedHoldoutSet(cases=generated_cases)
    inputs = {
        "source": "llm_generated_holdout",
        "generator_model": responses[0].get("model", client.model),
        "generator_response_ids": [item.get("id") for item in responses],
        "cases": [
            {
                "case_id": item.case_id,
                "conversation": [message.model_dump() for message in item.conversation],
            }
            for item in generated.cases
        ],
    }
    oracle = {
        item.case_id: {
            "business_type": item.business_type,
            "has_dispute": item.has_dispute,
            "expected_user_facts": [
                fact.model_dump(mode="json") for fact in item.expected_user_facts
            ],
            "expected_agent_facts": [
                fact.model_dump(mode="json") for fact in item.expected_agent_facts
            ],
        }
        for item in generated.cases
    }
    input_path.parent.mkdir(parents=True, exist_ok=True)
    oracle_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(json.dumps(inputs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    oracle_path.write_text(
        json.dumps(oracle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    usages = [item.get("usage") or {} for item in responses]
    return {
        "case_count": len(generated.cases),
        "response_ids": [item.get("id") for item in responses],
        "model": responses[0].get("model", client.model),
        "input_tokens": sum(item.get("input_tokens", 0) for item in usages),
        "output_tokens": sum(item.get("output_tokens", 0) for item in usages),
    }


def evaluate_holdout(
    client: ResponsesClient,
    input_path: Path,
    oracle_path: Path,
    repeats: int = 3,
    workers: int = 4,
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
            (statement_type.value, item.temporal_status.value)
            for item in result.semantics.user_claims
            for statement_type in item.statement_types
        }
        observed_agent = {
            (statement_type.value, item.temporal_status.value)
            for item in result.semantics.agent_commitments
            for statement_type in item.statement_types
        }
        expected_user = {
            (item["statement_type"], item["temporal_status"])
            for item in expected["expected_user_facts"]
        }
        expected_agent = {
            (item["statement_type"], item["temporal_status"])
            for item in expected["expected_agent_facts"]
        }
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
