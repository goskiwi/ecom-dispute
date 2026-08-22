from __future__ import annotations

from .contracts import AgentResult, CaseState, EvidenceKind


class CaseStateReducer:
    """Projects agent outputs into replayable case state without asking a model to merge facts."""

    def apply(self, state: CaseState, result: AgentResult) -> CaseState:
        next_state = state.model_copy(deep=True)
        for item in result.evidence:
            next_state.evidence[item.evidence_id] = item
            if item.occurred_at:
                next_state.timeline.append(
                    {
                        "occurred_at": item.occurred_at.isoformat(),
                        "kind": item.kind.value,
                        "evidence_id": item.evidence_id,
                        "summary": item.summary,
                    }
                )
        for finding in result.findings:
            if finding.category == "user_fact":
                next_state.user_facts.append(finding.claim)
            elif finding.category == "agent_statement":
                next_state.agent_statements.append(finding.claim)
            next_state.findings.append(finding)
        next_state.timeline.sort(key=lambda event: event["occurred_at"])
        next_state.trace.append(
            {
                "stage": "agent_result",
                "agent": result.agent,
                "finding_count": len(result.findings),
                "evidence_count": len(result.evidence),
                "tool_calls": result.tool_calls,
                "telemetry": result.telemetry,
            }
        )
        return next_state


def evidence_ids_by_kind(state: CaseState, kind: EvidenceKind) -> list[str]:
    return [item.evidence_id for item in state.evidence.values() if item.kind == kind]
