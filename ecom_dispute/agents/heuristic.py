from __future__ import annotations

from ..contracts import (
    AgentResult,
    CaseInput,
    Evidence,
    EvidenceKind,
    FactMode,
    FactType,
    Finding,
    Polarity,
    SpeechAct,
    TimeRelation,
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
                        fact_mode=self.fact_mode(fact_type),
                        time_relation=self.time_relation(text, speech_act, fact_type, polarity),
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
        if any(token in text for token in ("重复扣款", "扣了两次", "扣款两次", "重复扣了")):
            return FactType.PAYMENT_DUPLICATE, Polarity.AFFIRMED
        if any(token in text for token in ("已经扣款", "钱已经扣", "扣款成功", "被扣了")):
            return FactType.PAYMENT_CHARGE, Polarity.AFFIRMED
        if any(token in text for token in ("订单创建失败", "订单没创建", "订单没有生成")):
            return FactType.ORDER_CREATION, Polarity.NEGATED
        if any(token in text for token in ("不是我买的", "发错了", "型号不对", "颜色不对")):
            return FactType.ITEM_IDENTITY, Polarity.CONFLICTING
        if any(token in text for token in ("少发", "少了一件", "只收到一件", "数量不对")):
            return FactType.ITEM_QUANTITY, Polarity.CONFLICTING
        if any(token in text for token in ("破损", "碎了", "裂了", "坏了")):
            return FactType.ITEM_DAMAGE, Polarity.AFFIRMED
        if any(token in text for token in ("没拆封", "未拆封", "保持原样", "可二次销售")):
            return FactType.ITEM_CONDITION, Polarity.AFFIRMED
        if any(token in text for token in ("申请退货", "提交退货", "发起退货")):
            return FactType.RETURN_REQUEST, Polarity.AFFIRMED
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
    def fact_mode(fact_type: FactType) -> FactMode:
        event_types = {
            FactType.ORDER_CREATION,
            FactType.PAYMENT_CHARGE,
            FactType.PAYMENT_REVERSAL,
            FactType.REFUND_REQUEST,
            FactType.REFUND_INITIATION,
            FactType.REFUND_COMPLETION,
            FactType.DELIVERY_PICKUP,
            FactType.DELIVERY_COMPLETION,
            FactType.RETURN_REQUEST,
        }
        return FactMode.EVENT if fact_type in event_types else FactMode.STATE

    @classmethod
    def time_relation(
        cls,
        text: str,
        speech_act: SpeechAct,
        fact_type: FactType,
        polarity: Polarity,
    ) -> TimeRelation:
        if speech_act == SpeechAct.PROMISE:
            return TimeRelation.FUTURE
        if cls.fact_mode(fact_type) == FactMode.STATE:
            return TimeRelation.PRESENT
        if polarity == Polarity.NEGATED or any(
            token in text for token in ("正在", "处理中", "仍", "一直", "还没", "未")
        ):
            return TimeRelation.PRESENT
        if any(
            token in text
            for token in ("已经", "成功", "完成", "送达", "签收", "扣了", "收到", "到货")
        ):
            return TimeRelation.PAST
        return TimeRelation.UNKNOWN
