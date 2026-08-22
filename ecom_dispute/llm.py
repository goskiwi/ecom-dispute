from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .contracts import StatementType


class ExtractedStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    statement_type: StatementType
    message_indexes: list[int] = Field(min_length=1)


class ConversationSemantics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispute_type: str
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

    def __init__(self, base_url: str, api_key: str, model: str = "gpt-5.4-mini"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def extract_conversation(self, messages: list[dict[str, str]]) -> LLMResult:
        prompt = (
            "你是电商售后争议的对话分析 Agent。仅依据下列对话提取信息，不推测订单、"
            "支付、退款或政策事实。dispute_type 只能是 refund_dispute 或 other。"
            "逐条提取用户主张和客服承诺，不把询问或核验动作写成已发生事实。"
            "statement_type 只能从以下类型选择：refund_requested（申请退款）、"
            "refund_not_initiated（用户称退款未发起）、refund_not_received（用户否认到账）、"
            "refund_amount_mismatch（退款金额不符）、refund_initiated（退款已发起）、"
            "refund_processing（退款处理中）、refund_completed（退款或入账已完成）、"
            "wait_advice（建议等待）、verify_status（查询或核验）、other。"
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
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM request failed with HTTP {exc.code}: {body[:500]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

    @staticmethod
    def _output_text(response: dict[str, Any]) -> str:
        for item in response.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return str(content["text"])
        raise RuntimeError("LLM response contains no output_text")
