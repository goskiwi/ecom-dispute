from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..contracts import CaseInput, CaseState, EvidenceKind, Finding
from ..resource_loader import LoadedSkillPack, RouteResource, SkillLoader


@dataclass(frozen=True)
class DecisionOutcome:
    responsible_party: str = "undetermined"
    decision: str = "manual_review"
    recommended_action: str = "补充缺失证据后人工复检"
    review_required: bool = True
    findings: list[Finding] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


class DecisionStrategy(Protocol):
    def decide(
        self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]
    ) -> DecisionOutcome: ...


@dataclass(frozen=True)
class ResolvedRoute:
    skill: LoadedSkillPack
    route: RouteResource
    strategy: DecisionStrategy

    @property
    def name(self) -> str:
        return self.route.report_type

    @property
    def skill_id(self) -> str:
        return self.skill.definition.skill_id

    @property
    def route_id(self) -> str:
        return self.route.route_id

    @property
    def allowed_tools(self) -> tuple[str, ...]:
        return self.route.allowed_tools

    @property
    def required_evidence(self) -> tuple[EvidenceKind, ...]:
        return self.route.required_evidence

    def decide(
        self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]
    ) -> DecisionOutcome:
        outcome = self.strategy.decide(case, state, missing_evidence)
        if outcome.decision not in self.route.allowed_decisions:
            raise ValueError(
                f"strategy {self.route.decision_strategy} returned decision outside route "
                f"contract: {outcome.decision}"
            )
        return outcome


class SkillRegistry:
    def __init__(
        self,
        strategies: dict[str, DecisionStrategy],
        *,
        loader: SkillLoader | None = None,
        known_tools: set[str] | None = None,
    ) -> None:
        self._strategies = strategies
        self._packs = (
            loader
            or SkillLoader(
                known_tools=known_tools,
                known_strategies=set(strategies),
            )
        ).load_all()
        self._business_routes: dict[str, ResolvedRoute] = {}
        for pack in self._packs.values():
            for route in pack.routes.values():
                resolved = ResolvedRoute(
                    skill=pack,
                    route=route,
                    strategy=strategies[route.decision_strategy],
                )
                for business_type in route.match.business_types:
                    if business_type in self._business_routes:
                        previous = self._business_routes[business_type]
                        raise ValueError(
                            f"business type {business_type} is claimed by both "
                            f"{previous.route_id} and {route.route_id}"
                        )
                    self._business_routes[business_type] = resolved

    def resolve(self, business_type: str) -> ResolvedRoute:
        try:
            return self._business_routes[business_type]
        except KeyError as exc:
            raise ValueError(f"no route for business type: {business_type}") from exc

    def route(self, skill_id: str, route_id: str) -> ResolvedRoute:
        try:
            pack = self._packs[skill_id]
            route = pack.routes[route_id]
        except KeyError as exc:
            raise ValueError(f"unknown skill route: {skill_id}/{route_id}") from exc
        return ResolvedRoute(
            skill=pack,
            route=route,
            strategy=self._strategies[route.decision_strategy],
        )

    @property
    def business_types(self) -> set[str]:
        return set(self._business_routes)

    @property
    def skill_ids(self) -> set[str]:
        return set(self._packs)
