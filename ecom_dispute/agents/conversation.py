from __future__ import annotations

from ..contracts import (
    AgentResult,
    CaseInput,
    Evidence,
    EvidenceKind,
    Finding,
)
from ..llm import LLMResult, ResponsesClient


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

        result = None
        findings = []
        repair_hint = None
        model_repairs = 0
        for attempt in range(2):
            try:
                result = await asyncio.to_thread(
                    self.llm_client.extract_conversation,
                    case.conversation,
                    repair_hint,
                )
                findings = self._build_findings(case, evidence, result)
                break
            except ValueError as exc:
                if attempt == 1:
                    raise RuntimeError(
                        "conversation output invalid after one model repair"
                    ) from exc
                repair_hint = str(exc)
                model_repairs += 1
        if result is None:
            raise RuntimeError("conversation model returned no result")

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
                "request_attempts": result.request_attempts,
                "model_repairs": model_repairs,
                "route_type": result.semantics.route_type,
                "has_dispute": result.semantics.has_dispute,
                "business_facts": [
                    fact.model_dump(mode="json") for fact in result.semantics.business_facts
                ],
                "interaction_acts": [
                    act.model_dump(mode="json") for act in result.semantics.interaction_acts
                ],
                "uncertainty": result.semantics.uncertainty,
            },
        )

    def _build_findings(
        self,
        case: CaseInput,
        evidence: Evidence,
        result: LLMResult,
    ) -> list[Finding]:
        findings = []
        for index, fact in enumerate(result.semantics.business_facts, start=1):
            self._validate_grounding(case, fact)
            findings.append(
                Finding(
                    finding_id=f"llm-business-fact-{index}",
                    category=(
                        "user_business_fact" if fact.speaker == "user" else "agent_business_fact"
                    ),
                    claim=fact.quote,
                    fact_type=fact.fact_type,
                    polarity=fact.polarity,
                    fact_mode=fact.fact_mode,
                    time_relation=fact.time_relation,
                    quote=fact.quote,
                    message_index=fact.message_index,
                    evidence_ids=[evidence.evidence_id],
                )
            )
        for index, act in enumerate(result.semantics.interaction_acts, start=1):
            self._validate_grounding(case, act)
            findings.append(
                Finding(
                    finding_id=f"llm-interaction-act-{index}",
                    category=(
                        "user_interaction_act" if act.speaker == "user" else "agent_interaction_act"
                    ),
                    claim=act.quote,
                    speech_act=act.speech_act,
                    quote=act.quote,
                    message_index=act.message_index,
                    evidence_ids=[evidence.evidence_id],
                )
            )
        findings.append(
            Finding(
                finding_id="llm-route-type",
                category="candidate_route_type",
                claim=result.semantics.route_type,
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
        return findings

    @staticmethod
    def _validate_grounding(case: CaseInput, item: object) -> None:
        if item.message_index >= len(case.conversation):
            raise ValueError(f"message_index out of range: {item.message_index}")
        source_message = case.conversation[item.message_index]
        if source_message["speaker"] != item.speaker or item.quote not in source_message["text"]:
            raise ValueError(f"quote is not grounded in message {item.message_index}")
