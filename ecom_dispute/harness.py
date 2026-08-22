from __future__ import annotations

import asyncio

from .agents import (
    ConversationAgent,
    FixedFactExecutor,
    HeuristicConversationStub,
    PolicyResolver,
    ToolQueryAgent,
)
from .case_state import CaseStateReducer
from .contracts import CaseInput, CaseState, DecisionReport
from .fusion import EvidenceFusion
from .llm import ResponsesClient
from .repository import Repository
from .skills import DeliveryDelaySkill, RefundDisputeSkill, SkillRegistry
from .tool_registry import ToolRegistry


class DiagnosticHarness:
    def __init__(
        self,
        repository: Repository,
        conversation_agent: object,
        tool_query_agent: ToolQueryAgent | None = None,
    ):
        self.registry = ToolRegistry(repository)
        self.repository = repository
        self.reducer = CaseStateReducer()
        self.fusion = EvidenceFusion()
        self.skills = SkillRegistry()
        self.skills.register(RefundDisputeSkill())
        self.skills.register(DeliveryDelaySkill())
        self.conversation_agent = conversation_agent
        self.tool_query_agent = tool_query_agent

    @classmethod
    def live(
        cls,
        repository: Repository,
        llm_client: ResponsesClient,
        tool_mode: str = "fixed",
    ) -> DiagnosticHarness:
        harness = cls(repository, ConversationAgent(llm_client))
        if tool_mode == "agent":
            harness.tool_query_agent = ToolQueryAgent(llm_client, harness.registry)
        elif tool_mode != "fixed":
            raise ValueError(f"unknown tool mode: {tool_mode}")
        return harness

    @classmethod
    def heuristic_tests(cls, repository: Repository) -> DiagnosticHarness:
        return cls(repository, HeuristicConversationStub())

    async def diagnose(self, case: CaseInput) -> DecisionReport:
        skill = self.skills.resolve(case.business_type)
        state = CaseState(case_id=case.case_id)
        conversation_result = await self.conversation_agent.run(case)
        state = self.reducer.apply(state, conversation_result)
        agent_names = [self.conversation_agent.name]
        if self.tool_query_agent:
            state = await self.tool_query_agent.run(case, state, skill, self.reducer)
            agent_names.append(self.tool_query_agent.name)
        else:
            fact_tools = tuple(name for name in skill.allowed_tools if name != "read_policy")
            fixed_executors = (
                FixedFactExecutor(self.registry, fact_tools),
                PolicyResolver(self.registry),
            )
            results = await asyncio.gather(*(agent.run(case) for agent in fixed_executors))
            for result in results:
                state = self.reducer.apply(state, result)
            agent_names.extend(agent.name for agent in fixed_executors)
        state.trace.insert(
            0,
            {
                "stage": "intake_and_routing",
                "skill": skill.name,
                "agents": agent_names,
            },
        )
        report = self.fusion.fuse(case, state, skill)
        if report.review_required:
            self.repository.ensure_review_task(report)
        return report

    def diagnose_sync(self, case: CaseInput) -> DecisionReport:
        return asyncio.run(self.diagnose(case))
