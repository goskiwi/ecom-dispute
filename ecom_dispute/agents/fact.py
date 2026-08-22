from __future__ import annotations

import asyncio

from ..contracts import AgentResult, CaseInput, Finding
from ..tool_runtime import ToolRuntime, ToolSurface


class CoreEvidenceExecutor:
    name = "core_evidence_executor"

    def __init__(self, runtime: ToolRuntime, surface: ToolSurface):
        self.runtime = runtime
        self.surface = surface

    async def run(self, case: CaseInput) -> AgentResult:
        tools = tuple(tool_id for tool_id in self.surface.tool_ids if tool_id != "tool_search")
        results = await asyncio.gather(
            *(
                asyncio.to_thread(
                    self.runtime.execute,
                    tool_id,
                    {},
                    case,
                    self.surface,
                )
                for tool_id in tools
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
            tool_calls=list(tools),
        )
