from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .contracts import CaseInput, CaseState
from .runtime_state import AgentRunState
from .skills import ResolvedRoute


class ProjectedContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: str
    route_id: str
    stage_id: str
    stage_objective: str
    skill_instructions: str
    stage_instructions: str | None
    original_question: list[dict[str, str]]
    compact_case_state: dict
    tool_ids: tuple[str, ...]
    repair_hint: str | None


class ContextProjector:
    def project(
        self,
        case: CaseInput,
        state: CaseState,
        run_state: AgentRunState,
        resolved: ResolvedRoute,
    ) -> ProjectedContext:
        stage_id = run_state.current_stage.value
        stage = resolved.route.stages[stage_id]
        instructions = None
        if stage.instruction_file:
            instructions = (resolved.skill.root / stage.instruction_file).read_text(
                encoding="utf-8"
            )
        tool_ids = tuple(dict.fromkeys((*stage.tools, *stage.visible_tools)))
        return ProjectedContext(
            skill_id=resolved.skill_id,
            route_id=resolved.route_id,
            stage_id=stage_id,
            stage_objective=stage.objective,
            skill_instructions=resolved.skill.model_instructions,
            stage_instructions=instructions,
            original_question=case.conversation,
            compact_case_state={
                "case_id": state.case_id,
                "user_business_facts": state.user_business_facts,
                "agent_business_facts": state.agent_business_facts,
                "user_interaction_acts": state.user_interaction_acts,
                "agent_interaction_acts": state.agent_interaction_acts,
                "evidence": [
                    {
                        "evidence_id": item.evidence_id,
                        "kind": item.kind.value,
                        "summary": item.summary,
                    }
                    for item in state.evidence.values()
                ],
                "conflicts": state.conflicts,
                "missing_evidence": state.missing_evidence,
            },
            tool_ids=tool_ids,
            repair_hint=run_state.recovery.transient_repair_hint,
        )
