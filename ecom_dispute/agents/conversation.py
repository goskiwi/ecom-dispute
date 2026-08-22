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
        for index, fact in enumerate(result.semantics.facts, start=1):
            if fact.message_index >= len(case.conversation):
                raise ValueError(f"fact message_index out of range: {fact.message_index}")
            source_message = case.conversation[fact.message_index]
            if (
                source_message["speaker"] != fact.speaker
                or fact.quote not in source_message["text"]
            ):
                raise ValueError(f"fact quote is not grounded in message {fact.message_index}")
            findings.append(
                Finding(
                    finding_id=f"llm-fact-{index}",
                    category="user_fact" if fact.speaker == "user" else "agent_statement",
                    claim=fact.quote,
                    fact_type=fact.fact_type,
                    polarity=fact.polarity,
                    temporal_status=fact.temporal_status,
                    speech_act=fact.speech_act,
                    quote=fact.quote,
                    message_index=fact.message_index,
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
                "facts": [fact.model_dump(mode="json") for fact in result.semantics.facts],
                "uncertainty": result.semantics.uncertainty,
            },
        )
