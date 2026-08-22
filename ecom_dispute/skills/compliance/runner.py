from __future__ import annotations

from ...case_state import CaseStateReducer
from ...contracts import CaseInput, CaseState
from ...runtime_state import AgentRunState, HarnessStage
from ...tool_runtime import ToolRuntime, ToolSurfaceResolver
from ..base import SkillRegistry


class ServiceComplianceRunner:
    route_ids = (
        "false-business-statement",
        "unsupported-promise",
        "missing-required-escalation",
    )

    def __init__(
        self,
        registry: SkillRegistry,
        runtime: ToolRuntime,
        surface_resolver: ToolSurfaceResolver,
        reducer: CaseStateReducer,
    ) -> None:
        self.registry = registry
        self.runtime = runtime
        self.surface_resolver = surface_resolver
        self.reducer = reducer

    async def run(self, case: CaseInput, state: CaseState) -> CaseState:
        from ...agents.fact import CoreEvidenceExecutor

        compliance_case = case.model_copy(update={"business_type": "service_compliance"})
        first = self.registry.route("service-compliance", self.route_ids[0])
        run_state = AgentRunState(case_id=case.case_id).activate(
            first.skill_id, first.route_id, first.route.start_stage
        )
        run_state = run_state.move_to(HarnessStage.VERIFY)
        surface = self.surface_resolver.resolve(first, run_state)
        policy_result = await CoreEvidenceExecutor(self.runtime, surface).run(compliance_case)
        base_state = self.reducer.apply(state.model_copy(deep=True), policy_result)

        merged = state.model_copy(deep=True)
        for item in policy_result.evidence:
            merged.evidence[item.evidence_id] = item
        for route_id in self.route_ids:
            resolved = self.registry.route("service-compliance", route_id)
            available = {item.kind for item in base_state.evidence.values()}
            missing = tuple(
                kind.value for kind in resolved.required_evidence if kind not in available
            )
            outcome = resolved.decide(compliance_case, base_state, missing)
            merged.findings.extend(outcome.findings)
            merged.trace.append(
                {
                    "event": "COMPLIANCE_SUBCASE_COMPLETED",
                    "skill": resolved.skill_id,
                    "route": resolved.route_id,
                    "decision": outcome.decision,
                    "review_required": outcome.review_required,
                }
            )
        return merged
