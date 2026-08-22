from __future__ import annotations

import asyncio
from dataclasses import replace

from .agents import (
    ConversationAgent,
    CoreEvidenceExecutor,
    HeuristicConversationStub,
    ToolQueryAgent,
)
from .case_state import CaseStateReducer
from .context_projector import ContextProjector
from .contracts import CaseInput, CaseState, DecisionReport
from .fusion import EvidenceFusion
from .llm import ResponsesClient
from .repository import Repository
from .runtime_state import AgentRunState, HarnessStage
from .skills import SkillRegistry, default_strategies
from .skills.compliance.runner import ServiceComplianceRunner
from .tool_registry import ToolRegistry
from .tool_runtime import ToolRuntime, ToolSurfaceResolver
from .trace import TraceRecorder


class DiagnosticHarness:
    def __init__(
        self,
        repository: Repository,
        conversation_agent: object,
        tool_query_agent: ToolQueryAgent | None = None,
    ):
        self.registry = ToolRegistry(repository)
        self.tool_runtime = ToolRuntime(self.registry)
        self.tool_surface_resolver = ToolSurfaceResolver(self.registry)
        self.repository = repository
        self.reducer = CaseStateReducer()
        self.fusion = EvidenceFusion()
        self.context_projector = ContextProjector()
        self.trace_recorder = TraceRecorder()
        self.skills = SkillRegistry(default_strategies(), known_tools=self.registry.names)
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
            harness.tool_query_agent = ToolQueryAgent(llm_client, harness.tool_runtime)
        elif tool_mode != "fixed":
            raise ValueError(f"unknown tool mode: {tool_mode}")
        return harness

    @classmethod
    def heuristic_tests(cls, repository: Repository) -> DiagnosticHarness:
        return cls(repository, HeuristicConversationStub())

    async def diagnose(self, case: CaseInput) -> DecisionReport:
        run_state = AgentRunState(case_id=case.case_id)
        state = CaseState(case_id=case.case_id)
        self.trace_recorder.record(state, run_state, "TASK_STARTED")

        skill = self.skills.resolve(case.business_type)
        run_state = run_state.activate(
            skill.skill_id,
            skill.route_id,
            skill.route.start_stage,
        )
        self.trace_recorder.record(
            state,
            run_state,
            "ROUTE_SELECTED",
            business_type=case.business_type,
        )

        analyze_context = self.context_projector.project(case, state, run_state, skill)
        self.trace_recorder.record(
            state,
            run_state,
            "STAGE_ENTERED",
            objective=analyze_context.stage_objective,
            tool_ids=list(analyze_context.tool_ids),
        )
        conversation_result = await self.conversation_agent.run(case)
        state = self.reducer.apply(state, conversation_result)
        agent_names = [self.conversation_agent.name]

        run_state = run_state.move_to(HarnessStage.VERIFY)
        verify_context = self.context_projector.project(case, state, run_state, skill)
        self.trace_recorder.record(
            state,
            run_state,
            "STAGE_ENTERED",
            objective=verify_context.stage_objective,
            tool_ids=list(verify_context.tool_ids),
        )
        tool_surface = self.tool_surface_resolver.resolve(skill, run_state)
        self.trace_recorder.record(
            state,
            run_state,
            "TOOL_SURFACE_RESOLVED",
            tool_ids=list(tool_surface.tool_ids),
        )
        trace_start = len(state.trace)
        if self.tool_query_agent:
            state = await self.tool_query_agent.run(
                case,
                state,
                self.reducer,
                tool_surface,
            )
            agent_names.append(self.tool_query_agent.name)
        else:
            executor = CoreEvidenceExecutor(self.tool_runtime, tool_surface)
            result = await executor.run(case)
            state = self.reducer.apply(state, result)
            agent_names.append(executor.name)
        verification_calls = sum(
            len(event.get("tool_calls", [])) for event in state.trace[trace_start:]
        )
        run_state = run_state.add_tool_calls(verification_calls)
        self.trace_recorder.record(
            state,
            run_state,
            "VERIFICATION_COMPLETED",
            agents=agent_names,
        )

        run_state = run_state.move_to(HarnessStage.DECIDE)
        decide_context = self.context_projector.project(case, state, run_state, skill)
        self.trace_recorder.record(
            state,
            run_state,
            "STAGE_ENTERED",
            objective=decide_context.stage_objective,
            tool_ids=list(decide_context.tool_ids),
        )
        state, outcome = self.fusion.decide(case, state, skill)
        state.candidate_decisions.append(
            {
                "skill_id": skill.skill_id,
                "route_id": skill.route_id,
                "decision": outcome.decision,
                "responsible_party": outcome.responsible_party,
                "review_required": outcome.review_required,
            }
        )
        compliance_runner = ServiceComplianceRunner(
            self.skills,
            self.tool_runtime,
            self.tool_surface_resolver,
            self.reducer,
        )
        state = await compliance_runner.run(case, state)
        compliance_review = any(
            finding.category == "service_compliance" and finding.review_recommended
            for finding in state.findings
        )
        if compliance_review and not outcome.review_required:
            outcome = replace(outcome, review_required=True)

        run_state = run_state.move_to(HarnessStage.FUSE_AND_REVIEW)
        fuse_context = self.context_projector.project(case, state, run_state, skill)
        self.trace_recorder.record(
            state,
            run_state,
            "STAGE_ENTERED",
            objective=fuse_context.stage_objective,
            tool_ids=list(fuse_context.tool_ids),
        )
        run_state = run_state.complete()
        self.trace_recorder.record(
            state,
            run_state,
            "TASK_COMPLETED",
            decision=outcome.decision,
            review_required=outcome.review_required,
        )
        report = self.fusion.fuse(case, state, skill, outcome)
        if report.review_required:
            self.repository.ensure_review_task(report)
        return report

    def diagnose_sync(self, case: CaseInput) -> DecisionReport:
        return asyncio.run(self.diagnose(case))
