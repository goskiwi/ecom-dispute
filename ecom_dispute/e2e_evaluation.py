from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from .agents import ConversationAgent, EvidenceGapAgent, ReviewAgent
from .contracts import AgentResult
from .harness import DiagnosticHarness
from .llm import ResponsesClient
from .repository import Repository, rebuild_database


class E2ECase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    order_id: str
    region: str
    business_type: str
    occurred_at: str
    current_time: str
    conversation: list[dict[str, str]]
    order: dict[str, Any]
    payments: list[dict[str, Any]]
    refunds: list[dict[str, Any]]
    after_sales: dict[str, Any] | None
    logistics_events: list[dict[str, Any]]


class E2EInputSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    cases: list[E2ECase]


class PrecomputedConversationAgent:
    name = "conversation"

    def __init__(self, result: AgentResult):
        self.result = result

    async def run(self, case: object) -> AgentResult:
        return self.result.model_copy(deep=True)


def prepare_e2e_database(db_path: Path, input_path: Path) -> tuple[Repository, list[str]]:
    repository = Repository(rebuild_database(db_path))
    dataset = E2EInputSet.model_validate_json(input_path.read_text(encoding="utf-8"))
    with repository.connect() as connection:
        for case in dataset.cases:
            connection.execute(
                "INSERT INTO cases VALUES (?, ?, 'e2e_blind', ?, ?, ?, ?, ?)",
                (
                    case.case_id,
                    case.order_id,
                    case.region,
                    case.business_type,
                    case.occurred_at,
                    case.current_time,
                    json.dumps(case.conversation, ensure_ascii=False),
                ),
            )
            order = case.order
            connection.execute(
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    case.order_id,
                    order["user_id"],
                    case.region,
                    case.business_type,
                    order["status"],
                    order["paid_amount"],
                    order["currency"],
                    order["created_at"],
                    order.get("promised_delivery_at"),
                    order.get("version", 1),
                ),
            )
            for item in case.payments:
                connection.execute(
                    "INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        item["payment_id"],
                        case.order_id,
                        item["event_type"],
                        item["amount"],
                        item["status"],
                        item["occurred_at"],
                        item.get("version", 1),
                    ),
                )
            for item in case.refunds:
                connection.execute(
                    "INSERT INTO refunds VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        item["refund_id"],
                        case.order_id,
                        item["amount"],
                        item["status"],
                        item["initiated_at"],
                        item.get("completed_at"),
                        item.get("version", 1),
                    ),
                )
            if case.after_sales:
                item = case.after_sales
                connection.execute(
                    "INSERT INTO after_sales_cases VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        item["after_sales_id"],
                        case.order_id,
                        item["status"],
                        item.get("approved_at"),
                        item["reason"],
                        item.get("version", 1),
                    ),
                )
            for item in case.logistics_events:
                connection.execute(
                    "INSERT INTO logistics_events VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        item["event_id"],
                        case.order_id,
                        item["event_type"],
                        item["occurred_at"],
                        item["detail"],
                        item.get("version", 1),
                    ),
                )
    return repository, [item.case_id for item in dataset.cases]


def evaluate_e2e(
    client: ResponsesClient,
    db_path: Path,
    input_path: Path,
    oracle_path: Path,
) -> dict:
    repository, case_ids = prepare_e2e_database(db_path, input_path)
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    results = []
    for case_id in case_ids:
        case = repository.case(case_id)
        expected = oracle[case_id]
        try:
            conversation_result = asyncio.run(ConversationAgent(client).run(case))
            live = DiagnosticHarness(repository, PrecomputedConversationAgent(conversation_result))
            live.evidence_gap_agent = EvidenceGapAgent(
                client, live.tool_runtime, live.tool_surface_resolver
            )
            live.review_agent = ReviewAgent(client)
            fixed = DiagnosticHarness(repository, PrecomputedConversationAgent(conversation_result))
            live_report = live.diagnose_sync(case)
            fixed_report = fixed.diagnose_sync(case)
            results.append(
                {
                    "case_id": case_id,
                    "business_type": case.business_type,
                    "conversation_telemetry": conversation_result.telemetry,
                    "live": _score_report(live_report, expected),
                    "fixed": _score_report(fixed_report, expected),
                }
            )
        except (RuntimeError, ValueError) as exc:
            results.append({"case_id": case_id, "error": str(exc)})

    valid = [item for item in results if "error" not in item]
    return {
        "mode": "e2e_blind_comparison",
        "case_count": len(case_ids),
        "evaluated": len(valid),
        "api_errors": len(results) - len(valid),
        "live": _aggregate(valid, "live"),
        "fixed": _aggregate(valid, "fixed"),
        "results": results,
    }


def _score_report(report: object, expected: dict) -> dict:
    evidence_kinds = {item.kind.value for item in report.evidence}
    called_tools = [
        tool
        for event in report.trace
        if event.get("agent") in {"evidence_gap", "core_evidence_executor"}
        for tool in event.get("tool_calls", [])
    ]
    evidence_ids = set(report.evidence_ids)
    unsupported = sum(
        not finding.evidence_ids or not set(finding.evidence_ids).issubset(evidence_ids)
        for finding in report.findings
    )
    checks = {
        "decision": report.decision == expected["decision"],
        "responsible_party": report.responsible_party == expected["responsible_party"],
        "review_required": report.review_required == expected["review_required"],
        "required_evidence": set(expected["required_evidence_kinds"]).issubset(evidence_kinds),
        "required_tools": set(expected["required_tools"]).issubset(called_tools),
        "evidence_grounded": unsupported == 0,
    }
    tool_events = [event for event in report.trace if event.get("agent") == "evidence_gap"]
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "decision": report.decision,
        "responsible_party": report.responsible_party,
        "review_required": report.review_required,
        "expected_review_required": expected["review_required"],
        "evidence_kinds": sorted(evidence_kinds),
        "called_tools": called_tools,
        "unsupported_findings": unsupported,
        "tool_calls": len(called_tools),
        "tool_rounds": len(tool_events),
        "tool_input_tokens": sum(
            event.get("telemetry", {}).get("input_tokens", 0) for event in tool_events
        ),
        "tool_output_tokens": sum(
            event.get("telemetry", {}).get("output_tokens", 0) for event in tool_events
        ),
        "tool_latency_ms": sum(
            event.get("telemetry", {}).get("latency_ms", 0) for event in tool_events
        ),
    }


def _aggregate(results: list[dict], mode: str) -> dict:
    scored = [item[mode] for item in results]
    total = len(scored)
    review_tp = sum(item["review_required"] and item["expected_review_required"] for item in scored)
    predicted_review = sum(item["review_required"] for item in scored)
    expected_review = sum(item["expected_review_required"] for item in scored)
    return {
        "passed": sum(item["passed"] for item in scored),
        "pass_rate": sum(item["passed"] for item in scored) / total if total else None,
        "decision_accuracy": _rate(scored, "decision"),
        "responsible_party_accuracy": _rate(scored, "responsible_party"),
        "review_accuracy": _rate(scored, "review_required"),
        "required_evidence_rate": _rate(scored, "required_evidence"),
        "required_tools_rate": _rate(scored, "required_tools"),
        "evidence_grounded_rate": _rate(scored, "evidence_grounded"),
        "average_tool_calls": sum(item["tool_calls"] for item in scored) / total if total else 0,
        "average_tool_rounds": sum(item["tool_rounds"] for item in scored) / total if total else 0,
        "tool_input_tokens": sum(item["tool_input_tokens"] for item in scored),
        "tool_output_tokens": sum(item["tool_output_tokens"] for item in scored),
        "tool_latency_ms": sum(item["tool_latency_ms"] for item in scored),
        "review_true_positives": review_tp,
        "predicted_reviews": predicted_review,
        "expected_reviews": expected_review,
        "review_precision": review_tp / predicted_review if predicted_review else None,
        "review_recall": review_tp / expected_review if expected_review else None,
    }


def _rate(scored: list[dict], check: str) -> float | None:
    return sum(item["checks"][check] for item in scored) / len(scored) if scored else None
