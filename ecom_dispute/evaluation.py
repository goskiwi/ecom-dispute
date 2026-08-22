from __future__ import annotations

import json
from pathlib import Path

from .baseline import ToolCallingBaseline
from .harness import DiagnosticHarness
from .llm import ResponsesClient
from .repository import ROOT, Repository
from .tool_registry import ToolRegistry


def evaluate(
    repository: Repository,
    oracle_path: Path = ROOT / "evals" / "oracle.json",
    semantic_oracle_path: Path = ROOT / "evals" / "semantic_oracle.json",
    llm_client: ResponsesClient | None = None,
    case_ids: list[str] | None = None,
) -> dict:
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    semantic_oracle = (
        json.loads(semantic_oracle_path.read_text(encoding="utf-8"))
        if semantic_oracle_path.exists()
        else {}
    )
    harness = DiagnosticHarness(repository, llm_client=llm_client)
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
            (
                event["telemetry"]
                for event in report.trace
                if event.get("agent") == "conversation"
            ),
            {},
        )
        semantic_ok = (
            any(
                finding.category == "candidate_dispute_type"
                and finding.claim == "refund_dispute"
                for finding in report.findings
            )
            if llm_client
            else True
        )
        checks["semantic_route"] = semantic_ok
        observed_user_types = {
            finding.statement_type.value
            for finding in report.findings
            if finding.category == "user_claim" and finding.statement_type
        }
        observed_agent_types = {
            finding.statement_type.value
            for finding in report.findings
            if finding.category == "agent_commitment" and finding.statement_type
        }
        observed_conversation_conflict = any(
            finding.category == "conversation_fact_conflict" for finding in report.findings
        )
        semantic_expected = semantic_oracle.get(case_id, {})
        if llm_client and semantic_expected:
            checks["user_claim_types"] = set(
                semantic_expected["required_user_types"]
            ).issubset(observed_user_types)
            checks["agent_commitment_types"] = set(
                semantic_expected["required_agent_types"]
            ).issubset(observed_agent_types)
            checks["conversation_conflict"] = (
                observed_conversation_conflict
                == semantic_expected["conversation_conflict"]
            )
        results.append(
            {
                "case_id": case_id,
                "source_type": case.source_type,
                "checks": checks,
                "passed": all(checks.values()),
                "semantics": {
                    "observed_user_types": sorted(observed_user_types),
                    "observed_agent_types": sorted(observed_agent_types),
                    "conversation_conflict": observed_conversation_conflict,
                },
                "llm": llm_trace,
            }
        )
    llm_calls = sum(item["llm"].get("mode") == "llm" for item in results)
    semantic_cases = [item for item in results if item["case_id"] in semantic_oracle]
    expected_user = sum(
        len(semantic_oracle[item["case_id"]]["required_user_types"])
        for item in semantic_cases
    )
    matched_user = sum(
        len(
            set(semantic_oracle[item["case_id"]]["required_user_types"])
            & set(item["semantics"]["observed_user_types"])
        )
        for item in semantic_cases
    )
    expected_agent = sum(
        len(semantic_oracle[item["case_id"]]["required_agent_types"])
        for item in semantic_cases
    )
    matched_agent = sum(
        len(
            set(semantic_oracle[item["case_id"]]["required_agent_types"])
            & set(item["semantics"]["observed_agent_types"])
        )
        for item in semantic_cases
    )
    conflict_tp = sum(
        semantic_oracle[item["case_id"]]["conversation_conflict"]
        and item["semantics"]["conversation_conflict"]
        for item in semantic_cases
    )
    conflict_fp = sum(
        not semantic_oracle[item["case_id"]]["conversation_conflict"]
        and item["semantics"]["conversation_conflict"]
        for item in semantic_cases
    )
    conflict_fn = sum(
        semantic_oracle[item["case_id"]]["conversation_conflict"]
        and not item["semantics"]["conversation_conflict"]
        for item in semantic_cases
    )
    return {
        "mode": "llm" if llm_client else "offline",
        "case_count": len(results),
        "passed": sum(item["passed"] for item in results),
        "pass_rate": sum(item["passed"] for item in results) / len(results) if results else 0,
        "llm_calls": llm_calls,
        "input_tokens": sum(item["llm"].get("input_tokens", 0) for item in results),
        "output_tokens": sum(item["llm"].get("output_tokens", 0) for item in results),
        "latency_ms": sum(item["llm"].get("latency_ms", 0) for item in results),
        "semantic_metrics": {
            "user_type_recall": matched_user / expected_user if expected_user else 1.0,
            "agent_type_recall": matched_agent / expected_agent if expected_agent else 1.0,
            "conversation_conflict_precision": (
                conflict_tp / (conflict_tp + conflict_fp)
                if conflict_tp + conflict_fp
                else 1.0
            ),
            "conversation_conflict_recall": (
                conflict_tp / (conflict_tp + conflict_fn)
                if conflict_tp + conflict_fn
                else 1.0
            ),
            "conflict_tp": conflict_tp,
            "conflict_fp": conflict_fp,
            "conflict_fn": conflict_fn,
        },
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
