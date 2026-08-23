from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class HarnessStage(StrEnum):
    ROUTE = "ROUTE"
    ANALYZE = "ANALYZE"
    VERIFY = "VERIFY"
    DECIDE = "DECIDE"
    FUSE_AND_REVIEW = "FUSE_AND_REVIEW"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"


class RecoveryState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_error_code: str | None = None
    model_retry_count: int = Field(default=0, ge=0)
    model_repair_count: int = Field(default=0, ge=0)
    tool_argument_repair_count: int = Field(default=0, ge=0)
    total_recovery_actions: int = Field(default=0, ge=0)
    transient_repair_hint: str | None = None


class AgentRunState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    skill_id: str | None = None
    route_id: str | None = None
    current_stage: HarnessStage = HarnessStage.ROUTE
    turn_count: int = Field(default=0, ge=0)
    tool_call_count: int = Field(default=0, ge=0)
    loaded_lazy_tools: set[str] = Field(default_factory=set)
    recovery: RecoveryState = Field(default_factory=RecoveryState)
    status: RunStatus = RunStatus.RUNNING

    def activate(self, skill_id: str, route_id: str, start_stage: str) -> AgentRunState:
        if self.current_stage != HarnessStage.ROUTE:
            raise ValueError("run state can only activate from ROUTE")
        return self.model_copy(
            update={
                "skill_id": skill_id,
                "route_id": route_id,
                "current_stage": HarnessStage(start_stage),
            }
        )

    def move_to(self, stage: HarnessStage) -> AgentRunState:
        transitions = {
            HarnessStage.ANALYZE: HarnessStage.VERIFY,
            HarnessStage.VERIFY: HarnessStage.DECIDE,
            HarnessStage.DECIDE: HarnessStage.FUSE_AND_REVIEW,
        }
        expected = transitions.get(self.current_stage)
        if expected != stage:
            raise ValueError(f"invalid harness stage transition: {self.current_stage} -> {stage}")
        return self.model_copy(update={"current_stage": stage, "turn_count": self.turn_count + 1})

    def add_tool_calls(self, count: int) -> AgentRunState:
        if count < 0:
            raise ValueError("tool call increment cannot be negative")
        return self.model_copy(update={"tool_call_count": self.tool_call_count + count})

    def complete(self) -> AgentRunState:
        if self.current_stage != HarnessStage.FUSE_AND_REVIEW:
            raise ValueError("run state can only complete after FUSE_AND_REVIEW")
        return self.model_copy(update={"status": RunStatus.COMPLETED})
