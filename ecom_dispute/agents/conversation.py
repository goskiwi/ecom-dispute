from __future__ import annotations

from ..contracts import AgentResult, CaseInput, Evidence, EvidenceKind, Finding
from ..llm import ResponsesClient


class ConversationAgent:
    name = "conversation"

    def __init__(self, llm_client: ResponsesClient | None = None):
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
        if self.llm_client:
            return await self._run_with_llm(case, evidence)

        findings: list[Finding] = []
        for index, message in enumerate(case.conversation):
            speaker = message.get("speaker")
            text = message.get("text", "").strip()
            if not text:
                continue
            category = "user_claim" if speaker == "user" else "agent_commitment"
            findings.append(
                Finding(
                    finding_id=f"conversation-{index + 1}",
                    category=category,
                    claim=text,
                    evidence_ids=[evidence.evidence_id],
                )
            )
        return AgentResult(
            agent=self.name,
            findings=findings,
            evidence=[evidence],
            telemetry={"mode": "offline"},
        )

    async def _run_with_llm(self, case: CaseInput, evidence: Evidence) -> AgentResult:
        import asyncio

        result = await asyncio.to_thread(self.llm_client.extract_conversation, case.conversation)
        findings = []
        for index, statement in enumerate(result.semantics.user_claims, start=1):
            findings.append(
                Finding(
                    finding_id=f"llm-user-claim-{index}",
                    category="user_claim",
                    claim=statement.text,
                    evidence_ids=[evidence.evidence_id],
                )
            )
        for index, statement in enumerate(result.semantics.agent_commitments, start=1):
            findings.append(
                Finding(
                    finding_id=f"llm-agent-commitment-{index}",
                    category="agent_commitment",
                    claim=statement.text,
                    evidence_ids=[evidence.evidence_id],
                )
            )
        findings.append(
            Finding(
                finding_id="llm-dispute-type",
                category="candidate_dispute_type",
                claim=result.semantics.dispute_type,
                evidence_ids=[evidence.evidence_id],
                review_recommended=result.semantics.uncertainty is not None,
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
                "uncertainty": result.semantics.uncertainty,
            },
        )
