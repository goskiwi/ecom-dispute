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


class FactType(StrEnum):
    REFUND_REQUEST = "refund_request"
    REFUND_INITIATION = "refund_initiation"
    REFUND_PROCESSING = "refund_processing"
    REFUND_COMPLETION = "refund_completion"
    REFUND_RECEIPT = "refund_receipt"
    REFUND_AMOUNT = "refund_amount"
    DELIVERY_RECEIPT = "delivery_receipt"
    DELIVERY_DELAY = "delivery_delay"
    DELIVERY_COMPLETION = "delivery_completion"
    DELIVERY_PROMISE = "delivery_promise"
    DELIVERY_PICKUP = "delivery_pickup"
    STATUS = "status"
    OTHER = "other"


class TemporalStatus(StrEnum):
    FUTURE = "future"
    CURRENT = "current"
    COMPLETED = "completed"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class Polarity(StrEnum):
    AFFIRMED = "affirmed"
    NEGATED = "negated"
    UNCERTAIN = "uncertain"
    CONFLICTING = "conflicting"


class SpeechAct(StrEnum):
    ASSERTION = "assertion"
    PROMISE = "promise"
    ACTION = "action"
    ADVICE = "advice"
    QUERY = "query"
    EXPLANATION = "explanation"


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
    fact_type: FactType | None = None
    polarity: Polarity | None = None
    temporal_status: TemporalStatus | None = None
    speech_act: SpeechAct | None = None
    quote: str | None = None
    message_index: int | None = None
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
    user_facts: list[str] = Field(default_factory=list)
    agent_statements: list[str] = Field(default_factory=list)
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
    evidence: list[Evidence]
    evidence_ids: list[str]
    policy_evidence_ids: list[str]
    conflicts: list[str]
    missing_evidence: list[str]
    recommended_action: str
    review_required: bool
    trace: list[dict[str, Any]]


class ReviewTask(BaseModel):
    review_id: str
    case_id: str
    reason: str
    conflict_evidence_ids: list[str]
    status: Literal["pending", "resolved"]
    system_decision: str
    system_responsible_party: str
    reviewer_decision: str | None = None
    reviewer_responsible_party: str | None = None
    reviewer_comment: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None
