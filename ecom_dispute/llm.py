from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import StatementType, TemporalStatus


class ExtractedStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    statement_types: list[StatementType] = Field(min_length=1)
    temporal_status: TemporalStatus
    message_indexes: list[int] = Field(min_length=1)


class ConversationSemantics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_type: Literal["refund", "delivery", "other"]
    has_dispute: bool
    user_claims: list[ExtractedStatement]
    agent_commitments: list[ExtractedStatement]
    uncertainty: str | None


@dataclass(frozen=True)
class LLMResult:
    semantics: ConversationSemantics
    response_id: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class ResponsesClient:
    """Small Responses API client; credentials remain process-only."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "gpt-5.4-mini",
        timeout_seconds: int = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def extract_conversation(self, messages: list[dict[str, str]]) -> LLMResult:
        prompt = (
            "你是电商售后争议的对话分析 Agent。仅依据下列对话提取信息，不推测订单、"
            "支付、退款、物流或政策事实。business_type 只能是 refund、delivery 或 other；"
            "has_dispute 表示用户是否表达业务异常或对处理结果不满，正常查询或问题已解决为 false。"
            "只要用户明确陈述晚到、未收到、未发起、未到账或金额不符等异常，has_dispute 必须为 true，"
            "即使用户同时在询问政策；只有没有异常的状态查询或已正常解决才为 false。"
            "逐条提取用户主张和客服承诺，不把询问或核验动作写成已发生事实。"
            "一个语义片段包含多个事实时，statement_types 必须列出所有适用类型；也可以拆成多个原子条目，"
            "这些条目可以使用相同 message_indexes。statement_types 中的值只能从以下类型选择："
            "refund_requested（申请退款）、"
            "refund_not_initiated（用户称退款未发起）、refund_not_received（用户否认到账）、"
            "refund_amount_mismatch（退款金额不符）、refund_initiated（退款已发起）、"
            "refund_processing（退款处理中）、refund_completed（退款或入账已完成）、"
            "delivery_not_received（未收到货）、delivery_delayed（物流延迟）、"
            "delivery_completed（已送达）、delivery_promised（承诺送达或配送时限）、"
            "wait_advice（建议等待）、verify_status（查询或核验）、other。"
            "temporal_status 必须区分 future（将会/预计/会处理）、current（正在/仍处于）、"
            "completed（已经发生或完成）和 unknown（无法判断）。"
            "边界示例：‘晚了两天才送到’同时输出 delivery_delayed 和 delivery_completed，has_dispute=true；"
            "‘还没收到，但预计明天送达’输出 delivery_not_received 和 delivery_promised，has_dispute=false；"
            "‘退款已经正常到账’输出 refund_completed、temporal_status=completed，business_type=refund，has_dispute=false；"
            "‘退款会尽快处理’输出 refund_processing、temporal_status=future；"
            "‘预计五天内到账’不是已完成，使用 wait_advice、temporal_status=future。"
            "user_claims 与 agent_commitments 中的 text 使用原意简述，message_indexes 使用从 0 开始的消息序号。\n"
            f"对话：{json.dumps(messages, ensure_ascii=False)}"
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
        )

    def create_response(self, payload: dict[str, Any]) -> dict[str, Any]:
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
            raise RuntimeError(f"LLM request failed with HTTP {exc.code}: {body[:500]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError(
                f"LLM request timed out after {self.timeout_seconds} seconds"
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
