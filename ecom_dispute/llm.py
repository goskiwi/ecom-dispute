from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import FactMode, FactType, Polarity, SpeechAct, TimeRelation
from .ontology import (
    ROUTE_DESCRIPTIONS,
    BusinessRoute,
    ItemAttribute,
    OrderOperationType,
    ReturnReason,
)


class BusinessFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: Literal["user", "agent"]
    quote: str
    message_index: int = Field(ge=0)
    fact_type: FactType
    polarity: Polarity
    fact_mode: FactMode
    time_relation: TimeRelation


class InteractionAct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: Literal["user", "agent"]
    quote: str
    message_index: int = Field(ge=0)
    speech_act: SpeechAct


class ItemMismatchClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attribute: ItemAttribute
    ordered_value: str | None
    received_value: str | None
    explicit_order_received_mismatch: bool
    message_indices: list[int]


class ConversationSemantics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_type: BusinessRoute
    has_business_exception: bool
    return_reason: ReturnReason | None
    order_operation: OrderOperationType | None
    item_mismatch_claim: ItemMismatchClaim | None
    business_facts: list[BusinessFact]
    interaction_acts: list[InteractionAct]
    uncertainty: str | None

    @model_validator(mode="after")
    def validate_route_evidence(self) -> ConversationSemantics:
        if self.route_type == BusinessRoute.RECEIVED_ITEM_MISMATCH:
            claim = self.item_mismatch_claim
            if claim is None or not claim.explicit_order_received_mismatch:
                raise ValueError(
                    "received_item_mismatch requires an explicit order/received mismatch"
                )
        if self.route_type != BusinessRoute.ORDER_MANAGEMENT and self.order_operation:
            raise ValueError("order_operation is only valid for order_management")
        if self.route_type != BusinessRoute.RETURN_REQUEST and self.return_reason:
            raise ValueError("return_reason is only valid for return_request")
        return self


@dataclass(frozen=True)
class LLMResult:
    semantics: ConversationSemantics
    response_id: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    request_attempts: int = 1


class LLMRequestError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


class ResponsesClient:
    """Small Responses API client; credentials remain process-only."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "gpt-5.4-mini",
        timeout_seconds: int = 60,
        max_attempts: int = 2,
        retry_backoff_seconds: float = 0.2,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds

    def extract_conversation(
        self,
        messages: list[dict[str, str]],
        repair_hint: str | None = None,
    ) -> LLMResult:
        prompt = (
            "你是电商售后争议的对话分析 Agent。仅依据下列对话提取信息，不推测订单、"
            "支付、退款、物流或政策事实。route_type 必须从Schema列出的具体Route中选择。"
            f"Route定义：{json.dumps({key.value: value for key, value in ROUTE_DESCRIPTIONS.items()}, ensure_ascii=False)}。"
            "has_business_exception表示对话中是否曾发生业务异常或处理结果争议；后续被客服解决不能抹掉"
            "已经发生的异常。正常咨询、普通修改或主动退换货且没有异常时为false。"
            "买家自己选错规格、穿着不合身、不喜欢或改变主意本身不是业务异常；"
            "只有商家错发、系统失败或用户明确争议处理结果时才为true。"
            "route_type按用户的主要业务诉求和需要执行的证据工作流选择，不按客服最终采取的补发、退款、"
            "改期等动作选择。"
            "退货申请使用return_request，已提交退货后的标签、寄回、入库或验货进度使用return_progress；"
            "退款已经存在或应存在后的进度与到账使用refund_progress。"
            "received_item_mismatch必须有明确的下单值与实收值比较，或用户明确声称商家错发；"
            "只说wrong color/size、不合身或不喜欢时不得推断商家错发，应使用return_request并填写return_reason。"
            "return_reason只描述return_request的普通退货原因，其他Route必须为null。"
            "item_mismatch_claim只有存在商品不符主张时填写；同一句或多句明确给出下单值与实收值时，"
            "explicit_order_received_mismatch必须为true，不要求提前证明最终责任；"
            "ordered_value或received_value原文没有就必须为null，禁止补写。"
            "账户密码/2FA、身份资料修改和信贷延期明确选择other。order_operation只在order_management时填写。"
            "商品明确缺货或库存为零时选择inventory_availability；只有库存可用或未知但购物车状态异常时才选择cart_issue。"
            "输出 business_facts 与 interaction_acts 两个完全独立的数组。business_facts 只包含可被订单、退款、"
            "支付或物流系统核验的业务命题，每个事实包含fact_type、polarity、fact_mode和time_relation。"
            "interaction_acts 只描述说话行为：promise、action、advice、query、explanation、"
            "assertion 或 escalation。escalation 表示明确转交主管、专员或人工复核。"
            "纯查询、建议等待、正在核验、原因解释不能写入 business_facts。"
            "未来业务承诺需要同时输出 future business_fact 和 promise interaction_act。"
            "同一句含多个业务事实时输出多个 business_facts。两个数组的 quote 都必须逐字取自对应消息，"
            "message_index 从 0 开始。"
            "fact_type 定义：order_creation=订单是否创建成功；payment_charge=是否发生实际扣款；"
            "payment_duplicate=同一订单是否发生重复扣款；payment_reversal=扣款是否撤销；"
            "refund_request=用户提交退款申请；refund_initiation=资金退款流程是否发起；"
            "refund_processing=资金退款处理中；refund_completion=退款系统已完成；refund_receipt=用户账户实际入账；"
            "refund_amount=退款金额；delivery_pickup=承运商揽收；delivery_promise=承诺送达时间；"
            "delivery_delay=配送超时；delivery_completion=物流系统送达/签收状态；delivery_receipt=用户实际收到货；"
            "item_identity=实收商品身份/SKU是否与订单一致；item_quantity=实收商品数量；"
            "item_damage=商品是否破损；return_request=是否提交退货申请；"
            "return_eligibility=是否满足退货资格；item_condition=未拆封、可二次销售等商品状态；"
            "order_attribute=订单数量、地址、付款方式或配送设置；order_change=订单修改；"
            "fee_charge=运费或处理费；return_progress=退货寄回、入库或验货状态；"
            "exchange_request=换货申请；product_attribute=商品目录属性；inventory_status=库存状态；"
            "price_adjustment=价保或价格匹配；promotion_status=优惠券状态；shipping_option=配送方案；"
            "membership_status=会员状态或权益；checkout_status/cart_status/search_status/site_health分别表示"
            "结账、购物车、搜索和站点健康事实；"
            "status=查询或处理状态；other=确实无法归入上述任何类型的业务事实。"
            "不得因为旧退款/物流类型无法表达就使用other。fact_type不编码否定或言语行为。"
            "fact_mode定义：event=扣款、创建、发起、签收等离散事件；state=金额差异、商品身份、"
            "数量、破损、未收到等可持续状态。time_relation定义：past=离散事件已发生；"
            "present=状态当前成立或事件当前尚未发生/正在发生；future=预期未来发生；unknown=原文无法判断。"
            "已经发生但影响持续的事件仍标event+past；当前仍存在的商品破损、数量不符、金额差异标state+present。"
            "polarity 定义：affirmed=事实成立，negated=事实明确未发生，conflicting=金额或状态不一致，"
            "uncertain=仅询问或无法确认。"
            "例如未到账是refund_receipt+negated+state+present；未来会发起退款是"
            "refund_initiation+affirmed+event+future，同时interaction_act是promise；查询状态只输出query act；"
            "正在核验只输出 action act；等待只输出 advice act。不要把交互行为写成业务状态。\n"
            "只要一句陈述产生了business_fact，并且不是纯query/advice/explanation，通常还应独立输出assertion act。"
            f"对话：{json.dumps(messages, ensure_ascii=False)}"
        )
        if repair_hint:
            prompt += (
                "\n上一次输出未通过结构或原文一致性校验。"
                f"错误：{repair_hint}。请依据相同对话重新生成一次，不要解释。"
            )
        schema = ConversationSemantics.model_json_schema()
        payload = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": 800,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "conversation_semantics",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        started = time.perf_counter()
        response = self.create_response(payload)
        latency_ms = round((time.perf_counter() - started) * 1000)
        output_text = self._output_text(response)
        usage = response.get("usage") or {}
        return LLMResult(
            semantics=ConversationSemantics.model_validate_json(output_text),
            response_id=response.get("id", "unknown"),
            model=response.get("model", self.model),
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            latency_ms=latency_ms,
            request_attempts=int(response.get("_ecom_request_attempts", 1)),
        )

    def create_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: LLMRequestError | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._create_response_once(payload)
                response["_ecom_request_attempts"] = attempt
                return response
            except LLMRequestError as exc:
                last_error = exc
                if not exc.retryable or attempt >= self.max_attempts:
                    raise
                time.sleep(self.retry_backoff_seconds)
        raise last_error or RuntimeError("LLM request failed without an error")

    def _create_response_once(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}/v1/responses",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LLMRequestError(
                f"LLM request failed with HTTP {exc.code}: {body[:500]}",
                retryable=exc.code in {429, 502, 503, 504},
            ) from exc
        except urllib.error.URLError as exc:
            raise LLMRequestError(f"LLM request failed: {exc.reason}", retryable=True) from exc
        except TimeoutError as exc:
            raise LLMRequestError(
                f"LLM request timed out after {self.timeout_seconds} seconds",
                retryable=True,
            ) from exc

    @staticmethod
    def _output_text(response: dict[str, Any]) -> str:
        for item in response.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return str(content["text"])
        raise RuntimeError("LLM response contains no output_text")
