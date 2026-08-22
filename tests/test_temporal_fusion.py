from ecom_dispute.contracts import (
    CaseState,
    Evidence,
    EvidenceKind,
    Finding,
    StatementType,
    TemporalStatus,
)
from ecom_dispute.fusion import EvidenceFusion


def _state(temporal_status: TemporalStatus) -> CaseState:
    evidence = Evidence(
        evidence_id="conversation:temporal:v1",
        kind=EvidenceKind.CONVERSATION,
        source="test",
        business_key="temporal",
        facts={},
        summary="test conversation",
    )
    return CaseState(
        case_id="temporal",
        evidence={evidence.evidence_id: evidence},
        findings=[
            Finding(
                finding_id="statement-1",
                category="agent_commitment",
                claim="退款会在稍后完成",
                statement_type=StatementType.REFUND_COMPLETED,
                temporal_status=temporal_status,
                evidence_ids=[evidence.evidence_id],
            )
        ],
    )


def test_future_completion_does_not_conflict_with_missing_refund() -> None:
    state = _state(TemporalStatus.FUTURE)
    EvidenceFusion._fuse_conversation_facts(state, [], [], [])
    assert state.conflicts == []


def test_completed_claim_conflicts_with_missing_refund() -> None:
    state = _state(TemporalStatus.COMPLETED)
    EvidenceFusion._fuse_conversation_facts(state, [], [], [])
    assert state.conflicts == ["客服称退款已完成，但退款系统不存在成功记录"]
