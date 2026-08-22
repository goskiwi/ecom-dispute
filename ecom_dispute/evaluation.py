from __future__ import annotations

import json
from pathlib import Path

from .harness import DiagnosticHarness
from .llm import ResponsesClient
from .repository import ROOT, Repository


def evaluate(
    repository: Repository,
    oracle_path: Path = ROOT / "evals" / "oracle.json",
    llm_client: ResponsesClient | None = None,
) -> dict:
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    harness = DiagnosticHarness(repository, llm_client=llm_client)
    results = []
    for case_id in repository.case_ids():
        report = harness.diagnose_sync(repository.case(case_id))
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
        results.append(
            {
                "case_id": case_id,
                "checks": checks,
                "passed": all(checks.values()),
                "llm": llm_trace,
            }
        )
    llm_calls = sum(item["llm"].get("mode") == "llm" for item in results)
    return {
        "mode": "llm" if llm_client else "offline",
        "case_count": len(results),
        "passed": sum(item["passed"] for item in results),
        "pass_rate": sum(item["passed"] for item in results) / len(results) if results else 0,
        "llm_calls": llm_calls,
        "input_tokens": sum(item["llm"].get("input_tokens", 0) for item in results),
        "output_tokens": sum(item["llm"].get("output_tokens", 0) for item in results),
        "latency_ms": sum(item["llm"].get("latency_ms", 0) for item in results),
        "results": results,
    }
