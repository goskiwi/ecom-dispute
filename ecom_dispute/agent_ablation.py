from __future__ import annotations

from dataclasses import dataclass

from .agents import EvidenceGapAgent, ReviewAgent
from .contracts import AgentResult, CaseInput, DecisionReport
from .harness import DiagnosticHarness
from .llm import ResponsesClient
from .repository import Repository


@dataclass(frozen=True)
class PrecomputedConversationAgent:
    result: AgentResult
    name: str = "conversation"

    async def run(self, case: CaseInput) -> AgentResult:
        return self.result.model_copy(deep=True)


def compare_agent_layers(
    repository: Repository,
    case: CaseInput,
    conversation_result: AgentResult,
    client: ResponsesClient,
) -> dict:
    reports = {}
    for mode in ("core", "gap", "full"):
        harness = DiagnosticHarness(
            repository,
            PrecomputedConversationAgent(conversation_result),
        )
        if mode in {"gap", "full"}:
            harness.evidence_gap_agent = EvidenceGapAgent(
                client,
                harness.tool_runtime,
                harness.tool_surface_resolver,
            )
        if mode == "full":
            harness.review_agent = ReviewAgent(client)
        report = harness.diagnose_sync(case)
        reports[mode] = _report_metrics(report)
    return {
        "case_id": case.case_id,
        "shared_conversation": conversation_result.telemetry,
        "modes": reports,
    }


def _report_metrics(report: DecisionReport) -> dict:
    usages = [
        {"agent": event.get("agent"), **event.get("telemetry", {})}
        for event in report.trace
        if event.get("agent") in {"evidence_gap", "review"}
        and event.get("telemetry")
    ]
    return {
        "decision": report.decision,
        "responsible_party": report.responsible_party,
        "review_required": report.review_required,
        "evidence_count": len(report.evidence_ids),
        "finding_count": len(report.findings),
        "incremental_agents": [item["agent"] for item in usages],
        "incremental_input_tokens": sum(item.get("input_tokens", 0) for item in usages),
        "incremental_output_tokens": sum(item.get("output_tokens", 0) for item in usages),
        "incremental_latency_ms": sum(item.get("latency_ms", 0) for item in usages),
    }
