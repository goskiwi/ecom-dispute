from __future__ import annotations

import json
from pathlib import Path

from .agents import HeuristicConversationStub
from .baseline import ToolCallingBaseline
from .harness import DiagnosticHarness
from .llm import ResponsesClient
from .repository import ROOT, Repository
from .tool_registry import ToolRegistry


def evaluate(
    repository: Repository,
    oracle_path: Path = ROOT / "evals" / "oracle.json",
    llm_client: ResponsesClient | None = None,
    case_ids: list[str] | None = None,
) -> dict:
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    harness = (
        DiagnosticHarness.live(repository, llm_client)
        if llm_client
        else DiagnosticHarness(repository, HeuristicConversationStub())
    )
    results = []
    for case_id in case_ids or repository.case_ids():
        case = repository.case(case_id)
        report = harness.diagnose_sync(case)
        expected = oracle[case_id]
        checks = {
            field: getattr(report, field) == expected[field]
            for field in ("decision", "responsible_party", "review_required")
        }
        llm_trace = next(
            (event["telemetry"] for event in report.trace if event.get("agent") == "conversation"),
            {},
        )
        if llm_client:
            checks["business_type"] = llm_trace.get("business_type") == case.business_type
        results.append(
            {
                "case_id": case_id,
                "source_type": case.source_type,
                "checks": checks,
                "passed": all(checks.values()),
                "llm": llm_trace,
            }
        )
    llm_calls = sum(item["llm"].get("mode") == "llm" for item in results)
    return {
        "mode": "llm" if llm_client else "deterministic_test",
        "case_count": len(results),
        "passed": sum(item["passed"] for item in results),
        "pass_rate": sum(item["passed"] for item in results) / len(results) if results else 0,
        "llm_calls": llm_calls,
        "input_tokens": sum(item["llm"].get("input_tokens", 0) for item in results),
        "output_tokens": sum(item["llm"].get("output_tokens", 0) for item in results),
        "latency_ms": sum(item["llm"].get("latency_ms", 0) for item in results),
        "results": results,
    }


def evaluate_baseline(
    repository: Repository,
    llm_client: ResponsesClient,
    oracle_path: Path = ROOT / "evals" / "oracle.json",
    case_ids: list[str] | None = None,
) -> dict:
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    results = []
    for case_id in case_ids or repository.case_ids():
        case = repository.case(case_id)
        agent = ToolCallingBaseline(llm_client, ToolRegistry(repository))
        try:
            run = agent.diagnose(case)
            expected = oracle[case_id]
            cited = set(run.decision.evidence_ids)
            returned = set(run.returned_evidence_ids)
            checks = {
                "decision": run.decision.decision == expected["decision"],
                "responsible_party": (
                    run.decision.responsible_party == expected["responsible_party"]
                ),
                "review_required": run.decision.review_required == expected["review_required"],
                "evidence_grounded": not run.invalid_evidence_ids,
                "required_evidence": returned.issubset(cited),
            }
            results.append(
                {
                    "case_id": case_id,
                    "source_type": case.source_type,
                    "checks": checks,
                    "passed": all(checks.values()),
                    "decision": run.decision.model_dump(),
                    "invalid_evidence_ids": run.invalid_evidence_ids,
                    "returned_evidence_ids": run.returned_evidence_ids,
                    "llm_calls": run.llm_calls,
                    "tool_calls": run.tool_calls,
                    "input_tokens": run.input_tokens,
                    "output_tokens": run.output_tokens,
                    "latency_ms": run.latency_ms,
                    "trace": run.trace,
                }
            )
        except (KeyError, RuntimeError, ValueError) as exc:
            results.append(
                {
                    "case_id": case_id,
                    "source_type": case.source_type,
                    "checks": {},
                    "passed": False,
                    "error": str(exc),
                    "llm_calls": 0,
                    "tool_calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "latency_ms": 0,
                }
            )
    return {
        "mode": "tool_calling_baseline",
        "case_count": len(results),
        "passed": sum(item["passed"] for item in results),
        "pass_rate": sum(item["passed"] for item in results) / len(results) if results else 0,
        "llm_calls": sum(item["llm_calls"] for item in results),
        "tool_calls": sum(item["tool_calls"] for item in results),
        "input_tokens": sum(item["input_tokens"] for item in results),
        "output_tokens": sum(item["output_tokens"] for item in results),
        "latency_ms": sum(item["latency_ms"] for item in results),
        "results": results,
    }
