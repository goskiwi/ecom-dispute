from __future__ import annotations

from ..contracts import (
    AgentResult,
    CaseInput,
    Evidence,
    EvidenceKind,
    Finding,
)
from ..llm import ResponsesClient


class ConversationAgent:
    name = "conversation"

    def __init__(self, llm_client: ResponsesClient):
        self.llm_client = llm_client

    async def run(self, case: CaseInput) -> AgentResult:
        evidence = Evidence(
            evidence_id=f"conversation:{case.case_id}:v1",
            kind=EvidenceKind.CONVERSATION,
            source="cases.conversation_json",
            business_key=case.case_id,
            occurred_at=case.occurred_at,
            facts={"messages": case.conversation},
            summary=f"会话共 {len(case.conversation)} 条消息",
        )
        return await self._run_with_llm(case, evidence)

    async def _run_with_llm(self, case: CaseInput, evidence: Evidence) -> AgentResult:
        import asyncio

        result = await asyncio.to_thread(self.llm_client.extract_conversation, case.conversation)
        findings = []
        for index, statement in enumerate(result.semantics.user_claims, start=1):
            for type_index, statement_type in enumerate(statement.statement_types, start=1):
                findings.append(
                    Finding(
                        finding_id=f"llm-user-claim-{index}-{type_index}",
                        category="user_claim",
                        claim=statement.text,
                        statement_type=statement_type,
                        temporal_status=statement.temporal_status,
                        evidence_ids=[evidence.evidence_id],
                    )
                )
        for index, statement in enumerate(result.semantics.agent_commitments, start=1):
            for type_index, statement_type in enumerate(statement.statement_types, start=1):
                findings.append(
                    Finding(
                        finding_id=f"llm-agent-commitment-{index}-{type_index}",
                        category="agent_commitment",
                        claim=statement.text,
                        statement_type=statement_type,
                        temporal_status=statement.temporal_status,
                        evidence_ids=[evidence.evidence_id],
                    )
                )
        findings.append(
            Finding(
                finding_id="llm-business-type",
                category="candidate_business_type",
                claim=result.semantics.business_type,
                evidence_ids=[evidence.evidence_id],
                review_recommended=result.semantics.uncertainty is not None,
            )
        )
        findings.append(
            Finding(
                finding_id="llm-has-dispute",
                category="has_dispute",
                claim=str(result.semantics.has_dispute).lower(),
                evidence_ids=[evidence.evidence_id],
            )
        )
        return AgentResult(
            agent=self.name,
            findings=findings,
            evidence=[evidence],
            tool_calls=["responses.create"],
            telemetry={
                "mode": "llm",
                "response_id": result.response_id,
                "model": result.model,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "latency_ms": result.latency_ms,
                "business_type": result.semantics.business_type,
                "has_dispute": result.semantics.has_dispute,
                "user_claim_types": [
                    statement_type.value
                    for item in result.semantics.user_claims
                    for statement_type in item.statement_types
                ],
                "agent_commitment_types": [
                    statement_type.value
                    for item in result.semantics.agent_commitments
                    for statement_type in item.statement_types
                ],
                "statements": [
                    {
                        "speaker": speaker,
                        "text": item.text,
                        "types": [value.value for value in item.statement_types],
                        "temporal_status": item.temporal_status.value,
                    }
                    for speaker, items in (
                        ("user", result.semantics.user_claims),
                        ("agent", result.semantics.agent_commitments),
                    )
                    for item in items
                ],
                "uncertainty": result.semantics.uncertainty,
            },
        )
