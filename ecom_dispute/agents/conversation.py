from __future__ import annotations

from ..contracts import (
    AgentResult,
    CaseInput,
    Evidence,
    EvidenceKind,
    Finding,
    StatementType,
)
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
                    statement_type=self._offline_statement_type(text, speaker == "user"),
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
            for type_index, statement_type in enumerate(statement.statement_types, start=1):
                findings.append(
                    Finding(
                        finding_id=f"llm-user-claim-{index}-{type_index}",
                        category="user_claim",
                        claim=statement.text,
                        statement_type=statement_type,
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
                "uncertainty": result.semantics.uncertainty,
            },
        )

    @staticmethod
    def _offline_statement_type(text: str, is_user: bool) -> StatementType:
        if any(token in text for token in ("没收到货", "没有收到货", "还没收到", "未收到货")):
            return StatementType.DELIVERY_NOT_RECEIVED
        if any(token in text for token in ("物流延迟", "配送延迟", "晚到", "超时", "超过承诺")):
            return StatementType.DELIVERY_DELAYED
        if any(token in text for token in ("已经送达", "已送达", "签收了", "收到货了")):
            return StatementType.DELIVERY_COMPLETED
        if any(token in text for token in ("承诺送达", "预计送达", "配送时限")):
            return StatementType.DELIVERY_PROMISED
        if any(token in text for token in ("金额不", "只到账", "少退", "少了")):
            return StatementType.REFUND_AMOUNT_MISMATCH
        if any(token in text for token in ("没发起", "未发起", "没有退款流水", "没有退款记录")):
            return StatementType.REFUND_NOT_INITIATED
        if any(token in text for token in ("没到账", "未到账", "没收到", "未入账")):
            return StatementType.REFUND_NOT_RECEIVED
        if any(
            token in text for token in ("已经完成", "已完成", "退款成功", "退回来了", "已经退回")
        ):
            return StatementType.REFUND_COMPLETED
        if any(token in text for token in ("已经发起", "已发起", "为您申请", "申请成功")):
            return StatementType.REFUND_INITIATED
        if any(token in text for token in ("处理中", "正在处理", "支付渠道正在")):
            return StatementType.REFUND_PROCESSING
        if is_user and any(token in text for token in ("申请退款", "申请过退款", "点了退款")):
            return StatementType.REFUND_REQUESTED
        if any(token in text for token in ("等待", "耐心", "规定时间", "预计", "排队")):
            return StatementType.WAIT_ADVICE
        if any(token in text for token in ("查询", "确认", "核验", "看下", "核对")):
            return StatementType.VERIFY_STATUS
        return StatementType.OTHER
