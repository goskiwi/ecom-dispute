from __future__ import annotations

import json
from pathlib import Path

from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.repository import Repository, rebuild_database
from ecom_dispute.skills import SkillRegistry, default_strategies
from ecom_dispute.tool_registry import ToolRegistry

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    repository = Repository(rebuild_database(Path("/tmp/ecom-v3-decision-oracle.db")))
    harness = DiagnosticHarness.heuristic_tests(repository)
    skills = SkillRegistry(default_strategies(), known_tools=ToolRegistry(repository).names)
    oracle = {}
    observed_decisions = set()
    for case_id in repository.case_ids():
        case = repository.case(case_id)
        route = skills.resolve(case.business_type)
        report = harness.diagnose_sync(case)
        compliance = [
            event["decision"]
            for event in report.trace
            if event.get("event") == "COMPLIANCE_SUBCASE_COMPLETED"
        ]
        observed_decisions.add(report.decision)
        observed_decisions.update(compliance)
        oracle[case_id] = {
            "route_type": case.business_type,
            "decision": report.decision,
            "responsible_party": report.responsible_party,
            "review_required": report.review_required,
            "required_evidence_kinds": [kind.value for kind in route.required_evidence],
            "required_tools": list(route.route.core_tools),
            "required_agents": [
                "conversation",
                *(["review"] if report.review_required else []),
            ],
            "action_type": (report.action_plan.action_type if report.action_plan else None),
            "compliance_decisions": compliance,
        }
    expected_decisions = {
        decision
        for pack in skills._packs.values()
        for route in pack.routes.values()
        for decision in route.allowed_decisions
        if decision != "manual_review"
    }
    if observed_decisions != expected_decisions:
        raise ValueError(
            f"decision coverage mismatch: {sorted(expected_decisions - observed_decisions)}"
        )
    path = ROOT / "evals" / "v3_decision_oracle.json"
    path.write_text(json.dumps(oracle, ensure_ascii=False, indent=2) + "\n")
    print(
        {
            "cases": len(oracle),
            "decisions": len(observed_decisions),
            "action_plans": sum(item["action_type"] is not None for item in oracle.values()),
        }
    )


if __name__ == "__main__":
    main()
