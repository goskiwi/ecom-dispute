from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import FactType, Polarity, SpeechAct, TemporalStatus


class BusinessFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: Literal["user", "agent"]
    quote: str
    message_index: int = Field(ge=0)
    fact_type: FactType
    polarity: Polarity
    temporal_status: TemporalStatus


class InteractionAct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: Literal["user", "agent"]
    quote: str
    message_index: int = Field(ge=0)
    speech_act: SpeechAct


class ConversationSemantics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_type: Literal["refund", "delivery", "other"]
    has_dispute: bool
    business_facts: list[BusinessFact]
    interaction_acts: list[InteractionAct]
    uncertainty: str | None


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
            "支付、退款、物流或政策事实。business_type 只能是 refund、delivery 或 other；"
            "has_dispute 表示用户是否表达业务异常或对处理结果不满，正常查询或问题已解决为 false。"
            "只要用户明确陈述晚到、未收到、未发起、未到账或金额不符等异常，has_dispute 必须为 true，"
            "即使用户同时在询问政策；只有没有异常的状态查询或已正常解决才为 false。"
            "输出 business_facts 与 interaction_acts 两个完全独立的数组。business_facts 只包含可被订单、退款、"
            "支付或物流系统核验的业务命题，每个事实只有一个 fact_type、polarity 和 temporal_status。"
            "interaction_acts 只描述说话行为：promise、action、advice、query、explanation、"
            "assertion 或 escalation。escalation 表示明确转交主管、专员或人工复核。"
            "纯查询、建议等待、正在核验、原因解释不能写入 business_facts。"
            "未来业务承诺需要同时输出 future business_fact 和 promise interaction_act。"
            "同一句含多个业务事实时输出多个 business_facts。两个数组的 quote 都必须逐字取自对应消息，"
            "message_index 从 0 开始。"
            "fact_type 定义：refund_request=用户提交退款申请；refund_initiation=资金退款流程是否发起；"
            "refund_processing=资金退款处理中；refund_completion=退款系统已完成；refund_receipt=用户账户实际入账；"
            "refund_amount=退款金额；delivery_pickup=承运商揽收；delivery_promise=承诺送达时间；"
            "delivery_delay=配送超时；delivery_completion=物流系统送达/签收状态；delivery_receipt=用户实际收到货；"
            "status=查询或处理状态；other=无法归入上述业务事实。fact_type 不编码否定或言语行为。"
            "polarity 定义：affirmed=事实成立，negated=事实明确未发生，conflicting=金额或状态不一致，"
            "uncertain=仅询问或无法确认。"
            "例如未到账 business_fact 是 refund_receipt + negated + current；未来会发起的 business_fact 是"
            "refund_initiation + affirmed + future，同时 interaction_act 是 promise；查询状态只输出 query act；"
            "正在核验只输出 action act；等待只输出 advice act。不要把交互行为写成业务状态。\n"
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
            raise LLMRequestError(
                f"LLM request failed: {exc.reason}", retryable=True
            ) from exc
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
