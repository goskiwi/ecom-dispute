from __future__ import annotations

from ..contracts import (
    AgentResult,
    CaseInput,
    Evidence,
    EvidenceKind,
    FactType,
    Finding,
    Polarity,
    SpeechAct,
    TemporalStatus,
)


class HeuristicConversationStub:
    """Deterministic test stub. Never used by the live Agent path."""

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
            text = message.get("text", "").strip()
            if not text:
                continue
            fact_type, polarity = self.classify(text)
            speech_act = self.speech_act(text, message["speaker"])
            if fact_type not in {FactType.STATUS, FactType.OTHER}:
                findings.append(
                    Finding(
                        finding_id=f"heuristic-business-{index + 1}",
                        category=(
                            "user_business_fact"
                            if message["speaker"] == "user"
                            else "agent_business_fact"
                        ),
                        claim=text,
                        fact_type=fact_type,
                        polarity=polarity,
                        temporal_status=self.temporal_status(text, speech_act),
                        quote=text,
                        message_index=index,
                        evidence_ids=[evidence.evidence_id],
                    )
                )
            findings.append(
                Finding(
                    finding_id=f"heuristic-act-{index + 1}",
                    category=(
                        "user_interaction_act"
                        if message["speaker"] == "user"
                        else "agent_interaction_act"
                    ),
                    claim=text,
                    speech_act=speech_act,
                    quote=text,
                    message_index=index,
                    evidence_ids=[evidence.evidence_id],
                )
            )
        return AgentResult(
            agent=self.name,
            findings=findings,
            evidence=[evidence],
            telemetry={"mode": "heuristic_test_stub", "route_type": case.business_type},
        )

    @staticmethod
    def classify(text: str) -> tuple[FactType, Polarity]:
        if any(token in text for token in ("没收到货", "没有收到货", "还没收到", "未收到货")):
            return FactType.DELIVERY_RECEIPT, Polarity.NEGATED
        if any(token in text for token in ("物流延迟", "配送延迟", "晚到", "超时", "超过承诺")):
            return FactType.DELIVERY_DELAY, Polarity.AFFIRMED
        if any(token in text for token in ("已经送达", "已送达", "签收了", "收到货了")):
            return FactType.DELIVERY_COMPLETION, Polarity.AFFIRMED
        if any(token in text for token in ("承诺送达", "预计送达", "配送时限")):
            return FactType.DELIVERY_PROMISE, Polarity.AFFIRMED
        if any(token in text for token in ("金额不", "只到账", "少退", "少了")):
            return FactType.REFUND_AMOUNT, Polarity.CONFLICTING
        if any(token in text for token in ("没发起", "未发起", "没有退款流水", "没有退款记录")):
            return FactType.REFUND_INITIATION, Polarity.NEGATED
        if any(token in text for token in ("没到账", "未到账", "没收到", "未入账")):
            return FactType.REFUND_RECEIPT, Polarity.NEGATED
        if any(token in text for token in ("已经完成", "已完成", "退款成功", "已经退回")):
            return FactType.REFUND_COMPLETION, Polarity.AFFIRMED
        if any(token in text for token in ("已经发起", "已发起", "为您申请", "申请成功")):
            return FactType.REFUND_INITIATION, Polarity.AFFIRMED
        if any(token in text for token in ("处理中", "正在处理", "支付渠道正在")):
            return FactType.REFUND_PROCESSING, Polarity.AFFIRMED
        if any(token in text for token in ("申请退款", "申请过退款", "点了退款")):
            return FactType.REFUND_REQUEST, Polarity.AFFIRMED
        if any(token in text for token in ("查询", "确认", "核验", "看下", "核对")):
            return FactType.STATUS, Polarity.UNCERTAIN
        return FactType.OTHER, Polarity.UNCERTAIN

    @staticmethod
    def speech_act(text: str, speaker: str) -> SpeechAct:
        if any(token in text for token in ("转人工", "升级处理", "转交主管", "提交复检")):
            return SpeechAct.ESCALATION
        if any(token in text for token in ("查询", "确认", "核验", "看下", "核对", "吗", "为什么")):
            return SpeechAct.QUERY if speaker == "user" else SpeechAct.ACTION
        if any(
            token in text
            for token in ("已经", "已发起", "已完成", "已送达", "正在", "处理中", "显示")
        ):
            return SpeechAct.ASSERTION
        if any(token in text for token in ("预计", "将", "会尽快", "会在")):
            return SpeechAct.PROMISE
        if any(token in text for token in ("等待", "耐心")):
            return SpeechAct.ADVICE
        return SpeechAct.ASSERTION

    @staticmethod
    def temporal_status(text: str, speech_act: SpeechAct) -> TemporalStatus:
        if speech_act in {SpeechAct.QUERY, SpeechAct.ADVICE, SpeechAct.EXPLANATION}:
            return TemporalStatus.NOT_APPLICABLE
        if speech_act == SpeechAct.PROMISE:
            return TemporalStatus.FUTURE
        if any(token in text for token in ("已经", "已完成", "已送达", "到账了")):
            return TemporalStatus.COMPLETED
        if any(token in text for token in ("正在", "处理中", "仍", "一直", "还没", "未")):
            return TemporalStatus.CURRENT
        return TemporalStatus.UNKNOWN
