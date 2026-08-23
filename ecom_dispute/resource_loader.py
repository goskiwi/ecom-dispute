from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import EvidenceKind

RESOURCE_ROOT = Path(__file__).with_name("resources")
BUILTIN_TOOLS = frozenset({"tool_search", "read_evidence"})


class ResourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SkillRouteReference(ResourceModel):
    route_id: str
    file: str


class SkillLimits(ResourceModel):
    max_model_turns: int = Field(default=8, ge=1)
    max_tool_calls: int = Field(default=12, ge=1)
    max_loaded_lazy_tools: int = Field(default=3, ge=0)
    max_total_recovery_actions: int = Field(default=4, ge=0)


class SkillResource(ResourceModel):
    skill_id: str
    name: str
    entry: str = "SKILL.md"
    allowed_tools: tuple[str, ...]
    routes: tuple[SkillRouteReference, ...]
    limits: SkillLimits = Field(default_factory=SkillLimits)


class RouteMatch(ResourceModel):
    description: str
    business_types: tuple[str, ...]
    positive_examples: tuple[str, ...] = ()
    negative_examples: tuple[str, ...] = ()


class StageResource(ResourceModel):
    mode: Literal["agent", "deterministic"]
    objective: str
    instruction_file: str | None = None
    tools: tuple[str, ...] = ()
    visible_tools: tuple[str, ...] = ()
    default_next: str | None = None


class RouteResource(ResourceModel):
    route_id: str
    name: str
    report_type: str
    match: RouteMatch
    start_stage: str
    core_tools: tuple[str, ...]
    lazy_tools: tuple[str, ...] = ()
    required_evidence: tuple[EvidenceKind, ...]
    optional_evidence: tuple[EvidenceKind, ...] = ()
    allowed_decisions: tuple[str, ...]
    decision_strategy: str
    stages: dict[str, StageResource]

    @model_validator(mode="after")
    def validate_stage_graph(self) -> RouteResource:
        if self.start_stage not in self.stages:
            raise ValueError(f"start_stage does not exist: {self.start_stage}")
        for stage_id, stage in self.stages.items():
            if stage.default_next and stage.default_next not in self.stages:
                raise ValueError(f"stage {stage_id} points to missing stage: {stage.default_next}")
        return self

    @property
    def allowed_tools(self) -> tuple[str, ...]:
        ordered = dict.fromkeys((*self.core_tools, *self.lazy_tools))
        return tuple(ordered)


class ScopeBinding(ResourceModel):
    source: str
    mode: Literal["RUNTIME_INJECT", "MUST_MATCH"]


class ToolResource(ResourceModel):
    tool_id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    timeout_ms: int = Field(default=3000, ge=1)
    scope_bindings: dict[str, ScopeBinding] = Field(default_factory=dict)
    executor: str
    result_adapter: str
    error_mapping: dict[str, str] = Field(default_factory=dict)


@dataclass(frozen=True)
class LoadedSkillPack:
    definition: SkillResource
    routes: dict[str, RouteResource]
    model_instructions: str
    root: Path


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"resource file does not exist: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise TypeError(f"resource must contain a YAML object: {path}")
    return payload


class SkillLoader:
    def __init__(
        self,
        root: Path | None = None,
        *,
        known_tools: set[str] | None = None,
        known_strategies: set[str] | None = None,
    ) -> None:
        self.root = root or RESOURCE_ROOT / "skills"
        self.known_tools = known_tools
        self.known_strategies = known_strategies

    def load_all(self) -> dict[str, LoadedSkillPack]:
        if not self.root.is_dir():
            raise ValueError(f"skill resource directory does not exist: {self.root}")
        packs: dict[str, LoadedSkillPack] = {}
        for skill_file in sorted(self.root.glob("*/skill.yaml")):
            pack = self.load(skill_file.parent)
            if pack.definition.skill_id in packs:
                raise ValueError(f"duplicate skill_id: {pack.definition.skill_id}")
            packs[pack.definition.skill_id] = pack
        if not packs:
            raise ValueError(f"no skill resources found in: {self.root}")
        return packs

    def load(self, skill_root: Path) -> LoadedSkillPack:
        skill_file = skill_root / "skill.yaml"
        definition = SkillResource.model_validate(_load_yaml(skill_file))
        entry = skill_root / definition.entry
        if not entry.is_file():
            raise ValueError(f"skill entry does not exist: {entry}")

        allowed = set(definition.allowed_tools)
        if self.known_tools is not None:
            unknown = allowed - self.known_tools
            if unknown:
                raise ValueError(
                    f"skill {definition.skill_id} references unknown tools: {sorted(unknown)}"
                )

        routes: dict[str, RouteResource] = {}
        for reference in definition.routes:
            route_file = skill_root / reference.file
            route = RouteResource.model_validate(_load_yaml(route_file))
            if route.route_id != reference.route_id:
                raise ValueError(
                    f"route id mismatch in {route_file}: "
                    f"expected {reference.route_id}, got {route.route_id}"
                )
            if route.route_id in routes:
                raise ValueError(f"duplicate route_id in {skill_file}: {route.route_id}")
            self._validate_route(skill_root, definition, route)
            routes[route.route_id] = route

        return LoadedSkillPack(
            definition=definition,
            routes=routes,
            model_instructions=entry.read_text(encoding="utf-8"),
            root=skill_root,
        )

    def _validate_route(
        self,
        skill_root: Path,
        skill: SkillResource,
        route: RouteResource,
    ) -> None:
        allowed = set(skill.allowed_tools)
        route_tools = set(route.allowed_tools)
        for stage in route.stages.values():
            route_tools.update(stage.tools)
            route_tools.update(stage.visible_tools)
            if stage.instruction_file and not (skill_root / stage.instruction_file).is_file():
                raise ValueError(
                    f"route {route.route_id} references missing instruction file: "
                    f"{stage.instruction_file}"
                )
        outside = route_tools - allowed - BUILTIN_TOOLS
        if outside:
            raise ValueError(
                f"route {route.route_id} uses tools outside skill allowlist: {sorted(outside)}"
            )
        if (
            self.known_strategies is not None
            and route.decision_strategy not in self.known_strategies
        ):
            raise ValueError(
                f"route {route.route_id} references unknown strategy: {route.decision_strategy}"
            )


class ToolDefinitionLoader:
    def __init__(
        self,
        root: Path | None = None,
        *,
        known_executors: set[str] | None = None,
        known_adapters: set[str] | None = None,
    ) -> None:
        self.root = root or RESOURCE_ROOT / "tools"
        self.known_executors = known_executors
        self.known_adapters = known_adapters

    def load_all(self) -> dict[str, ToolResource]:
        if not self.root.is_dir():
            raise ValueError(f"tool resource directory does not exist: {self.root}")
        tools: dict[str, ToolResource] = {}
        for path in sorted(self.root.glob("*.yaml")):
            definition = ToolResource.model_validate(_load_yaml(path))
            if definition.tool_id in tools:
                raise ValueError(f"duplicate tool_id: {definition.tool_id}")
            if self.known_executors is not None and definition.executor not in self.known_executors:
                raise ValueError(
                    f"tool {definition.tool_id} references unknown executor: {definition.executor}"
                )
            if (
                self.known_adapters is not None
                and definition.result_adapter not in self.known_adapters
            ):
                raise ValueError(
                    f"tool {definition.tool_id} references unknown adapter: "
                    f"{definition.result_adapter}"
                )
            tools[definition.tool_id] = definition
        if not tools:
            raise ValueError(f"no tool resources found in: {self.root}")
        return tools
