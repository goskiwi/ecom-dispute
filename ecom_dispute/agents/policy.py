from __future__ import annotations

from ..contracts import AgentResult, CaseInput, Finding
from ..tool_registry import ToolRegistry


class PolicyAgent:
    name = "policy"

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def run(self, case: CaseInput) -> AgentResult:
        result = self.registry.execute(
            "read_policy",
            region=case.region,
            business_type=case.business_type,
            effective_at=case.occurred_at.isoformat(),
        )
        findings = [
            Finding(
                finding_id="policy-1",
                category="policy_rule",
                claim=item.summary,
                evidence_ids=[item.evidence_id],
                policy_rule_ids=[item.evidence_id],
            )
            for item in result.evidence
        ]
        return AgentResult(
            agent=self.name,
            findings=findings,
            evidence=result.evidence,
            tool_calls=["read_policy"],
        )
