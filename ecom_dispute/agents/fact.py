from __future__ import annotations

import asyncio

from ..contracts import AgentResult, CaseInput, Finding
from ..tool_registry import ToolRegistry


class FactAgent:
    name = "fact"

    def __init__(self, registry: ToolRegistry, tools: tuple[str, ...]):
        self.registry = registry
        self.tools = tools

    async def run(self, case: CaseInput) -> AgentResult:
        results = await asyncio.gather(
            *(
                asyncio.to_thread(self.registry.execute, name, order_id=case.order_id)
                for name in self.tools
            )
        )
        evidence = [item for result in results for item in result.evidence]
        findings = [
            Finding(
                finding_id=f"fact-{index + 1}",
                category=f"business_fact:{item.kind.value}",
                claim=item.summary,
                evidence_ids=[item.evidence_id],
            )
            for index, item in enumerate(evidence)
        ]
        return AgentResult(
            agent=self.name,
            findings=findings,
            evidence=evidence,
            tool_calls=list(self.tools),
        )
