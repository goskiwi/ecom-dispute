from __future__ import annotations

import asyncio

from .agents import ConversationAgent, FactAgent, PolicyAgent
from .case_state import CaseStateReducer
from .contracts import CaseInput, CaseState, DecisionReport
from .fusion import EvidenceFusion
from .llm import ResponsesClient
from .repository import Repository
from .skills import RefundDisputeSkill
from .tool_registry import ToolRegistry


class DiagnosticHarness:
    def __init__(self, repository: Repository, llm_client: ResponsesClient | None = None):
        self.registry = ToolRegistry(repository)
        self.reducer = CaseStateReducer()
        self.fusion = EvidenceFusion()
        self.skill = RefundDisputeSkill()
        self.llm_client = llm_client

    async def diagnose(self, case: CaseInput) -> DecisionReport:
        if not self.skill.supports(case.business_type):
            raise ValueError(f"no skill for business type: {case.business_type}")
        agents = (
            ConversationAgent(self.llm_client),
            FactAgent(self.registry),
            PolicyAgent(self.registry),
        )
        results = await asyncio.gather(*(agent.run(case) for agent in agents))
        state = CaseState(case_id=case.case_id)
        for result in results:
            state = self.reducer.apply(state, result)
        state.trace.insert(
            0,
            {
                "stage": "intake_and_routing",
                "skill": self.skill.name,
                "agents": [agent.name for agent in agents],
            },
        )
        return self.fusion.fuse(case, state, self.skill)

    def diagnose_sync(self, case: CaseInput) -> DecisionReport:
        return asyncio.run(self.diagnose(case))
