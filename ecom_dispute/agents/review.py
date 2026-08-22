from __future__ import annotations

import asyncio
import json
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..contracts import AgentResult, CaseInput, CaseState, Finding
from ..llm import ResponsesClient


class ReviewSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_summary: str
    review_questions: list[str] = Field(min_length=1, max_length=5)
    recommended_action: str
    cited_evidence_ids: list[str] = Field(min_length=1)
    priority: Literal["normal", "high"]


class ReviewAgent:
    name = "review"

    def __init__(self, client: ResponsesClient) -> None:
        self.client = client

    async def run(self, case: CaseInput, state: CaseState) -> AgentResult:
        evidence = [
            {"evidence_id": item.evidence_id, "kind": item.kind.value, "summary": item.summary}
            for item in state.evidence.values()
        ]
        prompt = (
            "你是电商争议人工复检材料 Agent。只能引用给定 evidence_id，不能修改业务事实或最终责任。"
            f"\n冲突={json.dumps(state.conflicts, ensure_ascii=False)}"
            f"\n缺失证据={json.dumps(state.missing_evidence, ensure_ascii=False)}"
            f"\n合规问题={json.dumps([x.claim for x in state.findings if x.category == 'service_compliance' and x.review_recommended], ensure_ascii=False)}"
            f"\n证据={json.dumps(evidence, ensure_ascii=False)}"
        )
        payload = {
            "model": self.client.model,
            "input": prompt,
            "max_output_tokens": 600,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "review_summary",
                    "strict": True,
                    "schema": ReviewSummary.model_json_schema(),
                }
            },
        }
        started = time.perf_counter()
        response = await asyncio.to_thread(self.client.create_response, payload)
        latency_ms = round((time.perf_counter() - started) * 1000)
        summary = ReviewSummary.model_validate_json(ResponsesClient._output_text(response))
        unknown = set(summary.cited_evidence_ids) - set(state.evidence)
        if unknown:
            raise ValueError(f"ReviewAgent cited unknown evidence: {sorted(unknown)}")
        usage = response.get("usage") or {}
        return AgentResult(
            agent=self.name,
            findings=[
                Finding(
                    finding_id="review-agent-summary",
                    category="review_summary",
                    claim=summary.conflict_summary,
                    evidence_ids=summary.cited_evidence_ids,
                    severity="critical" if summary.priority == "high" else "warning",
                    review_recommended=True,
                )
            ],
            telemetry={
                "model": response.get("model", self.client.model),
                "response_id": response.get("id"),
                "input_tokens": int(usage.get("input_tokens", 0)),
                "output_tokens": int(usage.get("output_tokens", 0)),
                "latency_ms": latency_ms,
                "review_questions": summary.review_questions,
                "recommended_action": summary.recommended_action,
                "priority": summary.priority,
            },
        )
