from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict

from ..case_state import CaseStateReducer
from ..contracts import AgentResult, CaseInput, CaseState, Finding
from ..llm import ResponsesClient
from ..tool_registry import ToolRegistry


class QueryConclusion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    done: bool
    summary: str
    missing_evidence: list[str]


@dataclass
class QuerySession:
    history: list[dict[str, Any]] = field(default_factory=list)
    rounds: int = 0
    tool_calls: int = 0


class ToolQueryAgent:
    name = "fact_query"

    def __init__(
        self,
        client: ResponsesClient,
        registry: ToolRegistry,
        max_rounds: int = 6,
        max_tool_calls: int = 10,
    ):
        self.client = client
        self.registry = registry
        self.max_rounds = max_rounds
        self.max_tool_calls = max_tool_calls

    async def run(
        self,
        case: CaseInput,
        state: CaseState,
        skill: object,
        reducer: CaseStateReducer,
    ) -> CaseState:
        session = QuerySession(history=[{"role": "user", "content": self._initial_prompt(case)}])
        allowed_tools = set(skill.allowed_tools)
        for round_index in range(1, self.max_rounds + 1):
            session.rounds = round_index
            session.history.append(
                {
                    "role": "user",
                    "content": "最新 CaseState 快照：\n" + self._state_snapshot(state),
                }
            )
            payload = {
                "model": self.client.model,
                "input": session.history,
                "tools": self.registry.response_tools(allowed_tools),
                "tool_choice": "required" if round_index == 1 else "auto",
                "parallel_tool_calls": True,
                "max_output_tokens": 800,
                "store": False,
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "query_conclusion",
                        "strict": True,
                        "schema": QueryConclusion.model_json_schema(),
                    }
                },
            }
            started = time.perf_counter()
            response = await asyncio.to_thread(self.client.create_response, payload)
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            usage = response.get("usage") or {}
            calls = [
                item for item in response.get("output", []) if item.get("type") == "function_call"
            ]
            telemetry = {
                "mode": "llm_tool_query",
                "round": round_index,
                "response_id": response.get("id"),
                "model": response.get("model", self.client.model),
                "input_tokens": int(usage.get("input_tokens", 0)),
                "output_tokens": int(usage.get("output_tokens", 0)),
                "latency_ms": elapsed_ms,
            }
            if not calls:
                conclusion = QueryConclusion.model_validate_json(
                    ResponsesClient._output_text(response)
                )
                state.trace.append(
                    {
                        "stage": "tool_query_stop",
                        "agent": self.name,
                        "stop_reason": conclusion.summary,
                        "reported_missing_evidence": conclusion.missing_evidence,
                        "round": round_index,
                        "telemetry": telemetry,
                    }
                )
                return state

            evidence = []
            findings = []
            called_names = []
            for call in calls:
                if session.tool_calls >= self.max_tool_calls:
                    state.trace.append(
                        {
                            "stage": "tool_query_stop",
                            "agent": self.name,
                            "stop_reason": "tool_call_budget_exhausted",
                            "round": round_index,
                        }
                    )
                    return state
                name = str(call["name"])
                arguments = json.loads(call.get("arguments") or "{}")
                result = self.registry.execute(name, **arguments)
                session.tool_calls += 1
                called_names.append(name)
                evidence.extend(result.evidence)
                findings.extend(
                    Finding(
                        finding_id=f"query-{round_index}-{len(findings) + 1}",
                        category=f"business_fact:{item.kind.value}",
                        claim=item.summary,
                        evidence_ids=[item.evidence_id],
                    )
                    for item in result.evidence
                )
                session.history.extend(
                    [
                        {
                            "type": "function_call",
                            "call_id": call["call_id"],
                            "name": name,
                            "arguments": json.dumps(arguments, ensure_ascii=False),
                        },
                        {
                            "type": "function_call_output",
                            "call_id": call["call_id"],
                            "output": result.model_dump_json(),
                        },
                    ]
                )
            state = reducer.apply(
                state,
                AgentResult(
                    agent=self.name,
                    findings=findings,
                    evidence=evidence,
                    tool_calls=called_names,
                    telemetry=telemetry,
                ),
            )

        state.trace.append(
            {
                "stage": "tool_query_stop",
                "agent": self.name,
                "stop_reason": "round_budget_exhausted",
                "round": self.max_rounds,
            }
        )
        return state

    @staticmethod
    def _initial_prompt(case: CaseInput) -> str:
        return (
            "你是电商争议事实查询 Agent。你的唯一职责是选择只读工具收集裁决需要的业务事实和"
            "事发时有效政策，不直接决定责任方。不要把对话说法当成系统事实；空结果也是有效观察。"
            "证据充分后输出 QueryConclusion 并停止。\n"
            f"case_id={case.case_id}\norder_id={case.order_id}\nregion={case.region}\n"
            f"business_type={case.business_type}\noccurred_at={case.occurred_at.isoformat()}\n"
            f"current_time={case.current_time.isoformat()}"
        )

    @staticmethod
    def _state_snapshot(state: CaseState) -> str:
        return json.dumps(
            {
                "case_id": state.case_id,
                "user_facts": state.user_facts,
                "agent_statements": state.agent_statements,
                "evidence": [
                    {
                        "evidence_id": item.evidence_id,
                        "kind": item.kind.value,
                        "summary": item.summary,
                    }
                    for item in state.evidence.values()
                ],
                "missing_evidence": state.missing_evidence,
            },
            ensure_ascii=False,
        )
