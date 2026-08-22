from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvidenceKind(StrEnum):
    CONVERSATION = "conversation"
    ORDER = "order"
    PAYMENT = "payment"
    REFUND = "refund"
    AFTER_SALES = "after_sales"
    LOGISTICS = "logistics"
    POLICY = "policy"
    QUERY = "query"


class StatementType(StrEnum):
    REFUND_REQUESTED = "refund_requested"
    REFUND_NOT_INITIATED = "refund_not_initiated"
    REFUND_NOT_RECEIVED = "refund_not_received"
    REFUND_AMOUNT_MISMATCH = "refund_amount_mismatch"
    REFUND_INITIATED = "refund_initiated"
    REFUND_PROCESSING = "refund_processing"
    REFUND_COMPLETED = "refund_completed"
    DELIVERY_NOT_RECEIVED = "delivery_not_received"
    DELIVERY_DELAYED = "delivery_delayed"
    DELIVERY_COMPLETED = "delivery_completed"
    DELIVERY_PROMISED = "delivery_promised"
    WAIT_ADVICE = "wait_advice"
    VERIFY_STATUS = "verify_status"
    OTHER = "other"


class Evidence(BaseModel):
    evidence_id: str
    kind: EvidenceKind
    source: str
    business_key: str
    version: int = 1
    occurred_at: datetime | None = None
    facts: dict[str, Any]
    summary: str


class ToolResult(BaseModel):
    tool_name: str
    status: Literal["ok", "not_found", "invalid"]
    evidence: list[Evidence] = Field(default_factory=list)
    error_code: str | None = None
    message: str | None = None


class CaseInput(BaseModel):
    case_id: str
    order_id: str
    source_type: Literal["manual", "rule_generated"]
    region: str
    business_type: str
    occurred_at: datetime
    current_time: datetime
    conversation: list[dict[str, str]]


class Finding(BaseModel):
    finding_id: str
    category: str
    claim: str
    statement_type: StatementType | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    policy_rule_ids: list[str] = Field(default_factory=list)
    severity: Literal["info", "warning", "critical"] = "info"
    review_recommended: bool = False


class AgentResult(BaseModel):
    agent: str
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    telemetry: dict[str, Any] = Field(default_factory=dict)


class CaseState(BaseModel):
    case_id: str
    user_claims: list[str] = Field(default_factory=list)
    agent_commitments: list[str] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    evidence: dict[str, Evidence] = Field(default_factory=dict)
    conflicts: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)


class DecisionReport(BaseModel):
    case_id: str
    dispute_type: str
    responsible_party: str
    decision: str
    timeline: list[dict[str, Any]]
    findings: list[Finding]
    evidence_ids: list[str]
    policy_evidence_ids: list[str]
    conflicts: list[str]
    missing_evidence: list[str]
    recommended_action: str
    review_required: bool
    trace: list[dict[str, Any]]
