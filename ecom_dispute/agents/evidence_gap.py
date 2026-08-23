from __future__ import annotations

import asyncio
import json
import time

from pydantic import BaseModel, ConfigDict

from ..case_state import CaseStateReducer
from ..contracts import AgentResult, CaseInput, CaseState, Finding
from ..llm import ResponsesClient
from ..runtime_state import AgentRunState
from ..skills import ResolvedRoute
from ..tool_runtime import ToolRuntime, ToolSurfaceResolver


class EvidenceGapPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    needs_more_evidence: bool
    tool_id: str | None
    reason: str


class EvidenceGapAgent:
    name = "evidence_gap"

    def __init__(
        self,
        client: ResponsesClient,
        runtime: ToolRuntime,
        surface_resolver: ToolSurfaceResolver,
    ) -> None:
        self.client = client
        self.runtime = runtime
        self.surface_resolver = surface_resolver

    async def run(
        self,
        case: CaseInput,
        state: CaseState,
        resolved: ResolvedRoute,
        run_state: AgentRunState,
        reducer: CaseStateReducer,
    ) -> CaseState:
        if not resolved.route.lazy_tools:
            return state
        candidates = [self.runtime.registry.definition(item) for item in resolved.route.lazy_tools]
        prompt = (
            "你是电商争议证据缺口 Agent。核心工具已经由框架执行。"
            "你只能判断是否需要一个长尾工具，不负责裁决责任。"
            "只有原始对话明确提出的问题或现有核心证据冲突需要该长尾证据时才选择；"
            "核心证据已经足够时必须needs_more_evidence=false。最多选择一个工具。"
            f"\nRoute={resolved.route_id}"
            f"\n原始对话={json.dumps(case.conversation, ensure_ascii=False)}"
            f"\n现有证据={json.dumps([{'kind': x.kind.value, 'summary': x.summary} for x in state.evidence.values()], ensure_ascii=False)}"
            f"\n候选工具={json.dumps([{'tool_id': x.tool_id, 'description': x.description} for x in candidates], ensure_ascii=False)}"
        )
        payload = {
            "model": self.client.model,
            "input": prompt,
            "max_output_tokens": 300,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "evidence_gap_plan",
                    "strict": True,
                    "schema": EvidenceGapPlan.model_json_schema(),
                }
            },
        }
        started = time.perf_counter()
        response = await asyncio.to_thread(self.client.create_response, payload)
        latency_ms = round((time.perf_counter() - started) * 1000)
        plan = EvidenceGapPlan.model_validate_json(ResponsesClient._output_text(response))
        allowed = set(resolved.route.lazy_tools)
        if not plan.needs_more_evidence:
            usage = response.get("usage") or {}
            return reducer.apply(
                state,
                AgentResult(
                    agent=self.name,
                    telemetry={
                        "model": response.get("model", self.client.model),
                        "response_id": response.get("id"),
                        "input_tokens": int(usage.get("input_tokens", 0)),
                        "output_tokens": int(usage.get("output_tokens", 0)),
                        "latency_ms": latency_ms,
                        "reason": plan.reason,
                        "selected_tool": None,
                    },
                ),
            )
        if not plan.tool_id or plan.tool_id not in allowed:
            raise ValueError(f"EvidenceGapAgent selected tool outside route: {plan.tool_id}")
        loaded_state = run_state.model_copy(
            update={"loaded_lazy_tools": {*run_state.loaded_lazy_tools, plan.tool_id}}
        )
        surface = self.surface_resolver.resolve(resolved, loaded_state)
        result = self.runtime.execute(plan.tool_id, {}, case, surface)
        findings = [
            Finding(
                finding_id=f"gap-{plan.tool_id}-{index}",
                category=f"business_fact:{item.kind.value}",
                claim=item.summary,
                evidence_ids=[item.evidence_id],
            )
            for index, item in enumerate(result.evidence, start=1)
        ]
        usage = response.get("usage") or {}
        return reducer.apply(
            state,
            AgentResult(
                agent=self.name,
                findings=findings,
                evidence=result.evidence,
                tool_calls=[plan.tool_id],
                telemetry={
                    "model": response.get("model", self.client.model),
                    "response_id": response.get("id"),
                    "input_tokens": int(usage.get("input_tokens", 0)),
                    "output_tokens": int(usage.get("output_tokens", 0)),
                    "latency_ms": latency_ms,
                    "reason": plan.reason,
                    "selected_tool": plan.tool_id,
                    "tool_status": result.status,
                    "tool_error_code": result.error_code,
                },
            ),
        )
