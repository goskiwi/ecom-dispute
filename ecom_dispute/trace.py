from __future__ import annotations

from typing import Any

from .contracts import CaseState
from .runtime_state import AgentRunState


class TraceRecorder:
    def record(
        self,
        state: CaseState,
        run_state: AgentRunState,
        event: str,
        **payload: Any,
    ) -> None:
        state.trace.append(
            {
                "event": event,
                "stage": run_state.current_stage.value,
                "turn": run_state.turn_count,
                "tool_call_count": run_state.tool_call_count,
                "skill": run_state.skill_id,
                "route": run_state.route_id,
                **payload,
            }
        )
