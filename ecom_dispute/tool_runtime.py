from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from jsonschema import ValidationError, validate
from pydantic import BaseModel, ConfigDict, Field

from .contracts import CaseInput, ToolResult
from .resource_loader import ToolResource
from .runtime_state import AgentRunState
from .skills import ResolvedRoute
from .tool_registry import ToolRegistry

TOOL_SEARCH_DEFINITION = ToolResource(
    tool_id="tool_search",
    name="搜索当前场景长尾工具",
    description="只在当前 Route 声明但尚未加载的 Lazy Tool 中搜索工具。",
    input_schema={
        "type": "object",
        "additionalProperties": False,
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "minLength": 1},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 5},
        },
    },
    output_schema={"type": "object", "additionalProperties": True},
    executor="tool_search",
    result_adapter="tool_search",
)


@dataclass(frozen=True)
class ToolSurface:
    definitions: tuple[ToolResource, ...]

    @property
    def tool_ids(self) -> tuple[str, ...]:
        return tuple(item.tool_id for item in self.definitions)

    def contains(self, tool_id: str) -> bool:
        return any(item.tool_id == tool_id for item in self.definitions)

    def response_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": item.tool_id,
                "description": item.description,
                "strict": True,
                "parameters": item.input_schema,
            }
            for item in self.definitions
        ]


class ToolSurfaceResolver:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def resolve(self, resolved: ResolvedRoute, run_state: AgentRunState) -> ToolSurface:
        stage = resolved.route.stages[run_state.current_stage.value]
        tool_ids = dict.fromkeys((*stage.tools, *stage.visible_tools))
        loaded_lazy = set(run_state.loaded_lazy_tools) & set(resolved.route.lazy_tools)
        for tool_id in resolved.route.lazy_tools:
            if tool_id in loaded_lazy:
                tool_ids[tool_id] = None
        remaining_lazy = set(resolved.route.lazy_tools) - loaded_lazy
        definitions = [self.registry.definition(tool_id) for tool_id in tool_ids]
        if remaining_lazy and stage.mode == "agent":
            definitions.append(TOOL_SEARCH_DEFINITION)
        return ToolSurface(tuple(definitions))


class ToolSearchMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str
    description: str
    score: float = Field(ge=0, le=1)


class ToolSearchService:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def search(
        self,
        query: str,
        resolved: ResolvedRoute,
        loaded_tools: set[str],
        max_results: int = 3,
    ) -> list[ToolSearchMatch]:
        candidates = set(resolved.route.lazy_tools) - loaded_tools
        normalized_query = self._normalize(query)
        matches = []
        for tool_id in candidates:
            definition = self.registry.definition(tool_id)
            document = self._normalize(
                f"{definition.tool_id} {definition.name} {definition.description}"
            )
            sequence = SequenceMatcher(None, normalized_query, document).ratio()
            overlap = len(set(normalized_query) & set(document)) / max(
                len(set(normalized_query)), 1
            )
            score = min(1.0, sequence * 0.6 + overlap * 0.4)
            matches.append(
                ToolSearchMatch(
                    tool_id=tool_id,
                    description=definition.description,
                    score=round(score, 4),
                )
            )
        return sorted(matches, key=lambda item: (-item.score, item.tool_id))[:max_results]

    @staticmethod
    def _normalize(value: str) -> str:
        return "".join(character.lower() for character in value if character.isalnum())


class ToolRuntime:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute(
        self,
        tool_id: str,
        model_arguments: dict[str, Any],
        case: CaseInput,
        surface: ToolSurface,
    ) -> ToolResult:
        if not surface.contains(tool_id) or tool_id == "tool_search":
            return ToolResult(
                tool_name=tool_id,
                status="invalid",
                error_code="TOOL_NOT_IN_CURRENT_SURFACE",
            )
        definition = self.registry.definition(tool_id)
        try:
            validate(instance=model_arguments, schema=definition.input_schema)
        except ValidationError as exc:
            return ToolResult(
                tool_name=tool_id,
                status="invalid",
                error_code="TOOL_ARGUMENT_INVALID",
                message=exc.message,
            )
        bound_arguments = dict(model_arguments)
        for argument, binding in definition.scope_bindings.items():
            expected = self._case_value(case, binding.source)
            supplied = bound_arguments.get(argument)
            if supplied is not None and supplied != expected:
                return ToolResult(
                    tool_name=tool_id,
                    status="invalid",
                    error_code="CASE_SCOPE_VIOLATION",
                    message=f"{argument} does not match {binding.source}",
                )
            bound_arguments[argument] = expected
        return self.registry.execute_bound(tool_id, bound_arguments)

    @staticmethod
    def _case_value(case: CaseInput, source: str) -> str:
        if not source.startswith("case."):
            raise ValueError(f"unsupported scope binding source: {source}")
        value = getattr(case, source.removeprefix("case."), None)
        if value is None:
            raise ValueError(f"case scope field does not exist: {source}")
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
