from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import CaseInput
from .llm import ResponsesClient
from .runtime_state import AgentRunState, HarnessStage
from .skills import SkillRegistry, default_strategies
from .tool_registry import ToolRegistry
from .tool_runtime import ToolRuntime, ToolSurfaceResolver


class BaselineDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispute_type: Literal["refund_dispute"]
    responsible_party: Literal["platform", "payment_channel", "none", "undetermined"]
    decision: Literal[
        "refund_not_initiated_overdue",
        "refund_pending_within_sla",
        "refund_processing_within_sla",
        "refund_arrival_overdue",
        "refund_completed",
        "refund_record_conflict",
        "manual_review",
    ]
    evidence_ids: list[str] = Field(min_length=1)
    missing_evidence: list[str]
    recommended_action: str
    review_required: bool


@dataclass(frozen=True)
class BaselineRun:
    decision: BaselineDecision
    trace: list[dict[str, Any]]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    llm_calls: int
    tool_calls: int
    returned_evidence_ids: list[str]
    invalid_evidence_ids: list[str]


class ToolCallingBaseline:
    def __init__(
        self,
        client: ResponsesClient,
        registry: ToolRegistry,
        max_rounds: int = 8,
    ):
        self.client = client
        self.registry = registry
        self.runtime = ToolRuntime(registry)
        self.max_rounds = max_rounds
        self.skill = SkillRegistry(
            default_strategies(), known_tools=registry.names
        ).resolve("refund")
        run_state = AgentRunState(case_id="baseline").activate(
            self.skill.skill_id,
            self.skill.route_id,
            self.skill.route.start_stage,
        )
        run_state = run_state.move_to(HarnessStage.VERIFY)
        self.surface = ToolSurfaceResolver(registry).resolve(self.skill, run_state)

    def diagnose(self, case: CaseInput) -> BaselineRun:
        prompt = self._prompt(case)
        history: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        trace: list[dict[str, Any]] = []
        returned_evidence: set[str] = set()
        input_tokens = output_tokens = latency_ms = llm_calls = tool_calls = 0

        for round_index in range(1, self.max_rounds + 1):
            payload = {
                "model": self.client.model,
                "input": history,
                "tools": self.surface.response_tools(),
                "tool_choice": "required" if round_index == 1 else "auto",
                "parallel_tool_calls": True,
                "max_output_tokens": 1200,
                "store": False,
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "refund_decision",
                        "strict": True,
                        "schema": BaselineDecision.model_json_schema(),
                    }
                },
            }
            started = time.perf_counter()
            response = self.client.create_response(payload)
            elapsed = round((time.perf_counter() - started) * 1000)
            usage = response.get("usage") or {}
            round_input = int(usage.get("input_tokens", 0))
            round_output = int(usage.get("output_tokens", 0))
            input_tokens += round_input
            output_tokens += round_output
            latency_ms += elapsed
            llm_calls += 1

            function_calls = [
                item for item in response.get("output", []) if item.get("type") == "function_call"
            ]
            trace.append(
                {
                    "round": round_index,
                    "response_id": response.get("id"),
                    "model": response.get("model", self.client.model),
                    "input_tokens": round_input,
                    "output_tokens": round_output,
                    "latency_ms": elapsed,
                    "request_attempts": int(response.get("_ecom_request_attempts", 1)),
                    "function_calls": [item.get("name") for item in function_calls],
                }
            )
            if function_calls:
                for call in function_calls:
                    name = str(call["name"])
                    arguments = json.loads(call.get("arguments") or "{}")
                    result = self.runtime.execute(name, arguments, case, self.surface)
                    returned_evidence.update(item.evidence_id for item in result.evidence)
                    history.append(
                        {
                            "type": "function_call",
                            "call_id": call["call_id"],
                            "name": name,
                            "arguments": json.dumps(arguments, ensure_ascii=False),
                        }
                    )
                    history.append(
                        {
                            "type": "function_call_output",
                            "call_id": call["call_id"],
                            "output": result.model_dump_json(),
                        }
                    )
                    tool_calls += 1
                continue

            text = ResponsesClient._output_text(response)
            decision = BaselineDecision.model_validate_json(text)
            invalid_ids = sorted(set(decision.evidence_ids) - returned_evidence)
            return BaselineRun(
                decision=decision,
                trace=trace,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                returned_evidence_ids=sorted(returned_evidence),
                invalid_evidence_ids=invalid_ids,
            )

        raise RuntimeError(f"tool agent exceeded {self.max_rounds} rounds for {case.case_id}")

    @staticmethod
    def _prompt(case: CaseInput) -> str:
        return (
            "你是电商退款争议裁决 Agent。必须通过工具核验订单、售后、退款、支付和事发时有效政策，"
            "不得把用户或客服说法当作业务事实。最终结论只能引用工具真实返回的 evidence_id。"
            "退款系统成功但没有匹配入账记录时，应标记事实冲突并转人工；证据不足时也应转人工。\n"
            f"case_id={case.case_id}\n"
            f"order_id={case.order_id}\n"
            f"region={case.region}\n"
            f"business_type={case.business_type}\n"
            f"occurred_at={case.occurred_at.isoformat()}\n"
            f"current_time={case.current_time.isoformat()}\n"
            f"conversation={json.dumps(case.conversation, ensure_ascii=False)}"
        )
