from __future__ import annotations

import json
from pathlib import Path

from ..contracts import (
    AgentResult,
    CaseInput,
    Evidence,
    EvidenceKind,
    Finding,
    StatementType,
    TemporalStatus,
)


class RecordedConversationAgent:
    name = "conversation"

    def __init__(self, recording_path: Path):
        self.recording_path = recording_path
        payload = json.loads(recording_path.read_text(encoding="utf-8"))
        self.results = {item["case_id"]: item for item in payload["results"]}

    async def run(self, case: CaseInput) -> AgentResult:
        recorded = self.results[case.case_id]
        semantics = recorded["semantics"]
        llm = recorded["llm"]
        evidence = Evidence(
            evidence_id=f"conversation:{case.case_id}:v1",
            kind=EvidenceKind.CONVERSATION,
            source="cases.conversation_json",
            business_key=case.case_id,
            occurred_at=case.occurred_at,
            facts={"messages": case.conversation},
            summary=f"会话共 {len(case.conversation)} 条消息",
        )
        findings = []
        for speaker, category, key in (
            ("user", "user_claim", "observed_user_types"),
            ("agent", "agent_commitment", "observed_agent_types"),
        ):
            text = " / ".join(
                message["text"] for message in case.conversation if message["speaker"] == speaker
            )
            for index, value in enumerate(semantics[key], start=1):
                findings.append(
                    Finding(
                        finding_id=f"recorded-{speaker}-{index}",
                        category=category,
                        claim=text,
                        statement_type=StatementType(value),
                        temporal_status=TemporalStatus.UNKNOWN,
                        evidence_ids=[evidence.evidence_id],
                    )
                )
        findings.extend(
            [
                Finding(
                    finding_id="recorded-business-type",
                    category="candidate_business_type",
                    claim=llm["business_type"],
                    evidence_ids=[evidence.evidence_id],
                ),
                Finding(
                    finding_id="recorded-has-dispute",
                    category="has_dispute",
                    claim=str(llm["has_dispute"]).lower(),
                    evidence_ids=[evidence.evidence_id],
                ),
            ]
        )
        return AgentResult(
            agent=self.name,
            findings=findings,
            evidence=[evidence],
            telemetry={
                **llm,
                "mode": "recorded_llm",
                "source_run": self.recording_path.name,
            },
        )
