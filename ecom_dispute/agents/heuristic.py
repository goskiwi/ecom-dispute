from __future__ import annotations

from ..contracts import (
    AgentResult,
    CaseInput,
    Evidence,
    EvidenceKind,
    Finding,
    StatementType,
    TemporalStatus,
)


class HeuristicConversationStub:
    """Deterministic test stub. Never used by the live or recorded Agent path."""

    name = "conversation"

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
        findings = []
        for index, message in enumerate(case.conversation):
            speaker = message.get("speaker")
            text = message.get("text", "").strip()
            if not text:
                continue
            findings.append(
                Finding(
                    finding_id=f"heuristic-{index + 1}",
                    category="user_claim" if speaker == "user" else "agent_commitment",
                    claim=text,
                    statement_type=self.statement_type(text, speaker == "user"),
                    temporal_status=self.temporal_status(text),
                    evidence_ids=[evidence.evidence_id],
                )
            )
        return AgentResult(
            agent=self.name,
            findings=findings,
            evidence=[evidence],
            telemetry={"mode": "heuristic_test_stub"},
        )

    @staticmethod
    def statement_type(text: str, is_user: bool) -> StatementType:
        rules = (
            (
                ("没收到货", "没有收到货", "还没收到", "未收到货"),
                StatementType.DELIVERY_NOT_RECEIVED,
            ),
            (("物流延迟", "配送延迟", "晚到", "超时", "超过承诺"), StatementType.DELIVERY_DELAYED),
            (("已经送达", "已送达", "签收了", "收到货了"), StatementType.DELIVERY_COMPLETED),
            (("承诺送达", "预计送达", "配送时限"), StatementType.DELIVERY_PROMISED),
            (("金额不", "只到账", "少退", "少了"), StatementType.REFUND_AMOUNT_MISMATCH),
            (
                ("没发起", "未发起", "没有退款流水", "没有退款记录"),
                StatementType.REFUND_NOT_INITIATED,
            ),
            (("没到账", "未到账", "没收到", "未入账"), StatementType.REFUND_NOT_RECEIVED),
            (
                ("已经完成", "已完成", "退款成功", "退回来了", "已经退回"),
                StatementType.REFUND_COMPLETED,
            ),
            (("已经发起", "已发起", "为您申请", "申请成功"), StatementType.REFUND_INITIATED),
            (("处理中", "正在处理", "支付渠道正在"), StatementType.REFUND_PROCESSING),
        )
        for tokens, statement_type in rules:
            if any(token in text for token in tokens):
                return statement_type
        if is_user and any(token in text for token in ("申请退款", "申请过退款", "点了退款")):
            return StatementType.REFUND_REQUESTED
        if any(token in text for token in ("等待", "耐心", "规定时间", "预计", "排队")):
            return StatementType.WAIT_ADVICE
        if any(token in text for token in ("查询", "确认", "核验", "看下", "核对")):
            return StatementType.VERIFY_STATUS
        return StatementType.OTHER

    @staticmethod
    def temporal_status(text: str) -> TemporalStatus:
        if any(token in text for token in ("已经", "已完成", "已送达", "收到货了", "到账了")):
            return TemporalStatus.COMPLETED
        if any(token in text for token in ("预计", "将", "会尽快", "会在", "请等待")):
            return TemporalStatus.FUTURE
        if any(token in text for token in ("正在", "处理中", "仍", "一直", "还没", "未")):
            return TemporalStatus.CURRENT
        return TemporalStatus.UNKNOWN
