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
    PAYMENT_GATEWAY = "payment_gateway"
    DELIVERY_PROOF = "delivery_proof"
    DELIVERY_ADDRESS = "delivery_address"
    CANCELLATION_REQUEST = "cancellation_request"
    ORDER_ITEM = "order_item"
    RETURN_REQUEST = "return_request"
    RETURN_TRACKING = "return_tracking"
    EXCHANGE_REQUEST = "exchange_request"
    WAREHOUSE_PACK = "warehouse_pack"
    CLAIM_ATTACHMENT = "claim_attachment"
    PRODUCT_CATALOG = "product_catalog"
    INVENTORY = "inventory"
    PRICE = "price"
    PROMOTION = "promotion"
    SHIPPING_OPTION = "shipping_option"
    MEMBERSHIP = "membership"
    ORDER_CHANGE_OPTION = "order_change_option"
    ORDER_FEE = "order_fee"
    CHARGE_CLAIM = "charge_claim"
    CHECKOUT_EVENT = "checkout_event"
    CART_EVENT = "cart_event"
    SEARCH_EVENT = "search_event"
    SITE_HEALTH = "site_health"
    POLICY = "policy"
    QUERY = "query"


class FactType(StrEnum):
    ORDER_CREATION = "order_creation"
    PAYMENT_CHARGE = "payment_charge"
    PAYMENT_DUPLICATE = "payment_duplicate"
    PAYMENT_REVERSAL = "payment_reversal"
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
    ITEM_IDENTITY = "item_identity"
    ITEM_QUANTITY = "item_quantity"
    ITEM_DAMAGE = "item_damage"
    RETURN_REQUEST = "return_request"
    RETURN_ELIGIBILITY = "return_eligibility"
    ITEM_CONDITION = "item_condition"
    ORDER_ATTRIBUTE = "order_attribute"
    ORDER_CHANGE = "order_change"
    FEE_CHARGE = "fee_charge"
    RETURN_PROGRESS = "return_progress"
    EXCHANGE_REQUEST = "exchange_request"
    PRODUCT_ATTRIBUTE = "product_attribute"
    INVENTORY_STATUS = "inventory_status"
    PRICE_ADJUSTMENT = "price_adjustment"
    PROMOTION_STATUS = "promotion_status"
    SHIPPING_OPTION = "shipping_option"
    MEMBERSHIP_STATUS = "membership_status"
    CHECKOUT_STATUS = "checkout_status"
    CART_STATUS = "cart_status"
    SEARCH_STATUS = "search_status"
    SITE_HEALTH = "site_health"
    STATUS = "status"
    OTHER = "other"


class FactMode(StrEnum):
    EVENT = "event"
    STATE = "state"


class TimeRelation(StrEnum):
    PAST = "past"
    PRESENT = "present"
    FUTURE = "future"
    UNKNOWN = "unknown"


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
    ESCALATION = "escalation"


class Evidence(BaseModel):
    evidence_id: str
    kind: EvidenceKind
    source: str
    business_key: str
    version: int = 1
    occurred_at: datetime | None = None
    facts: dict[str, Any]
    summary: str
    uri: str | None = None
    size_bytes: int | None = None


class ToolResult(BaseModel):
    tool_name: str
    status: Literal["ok", "not_found", "invalid", "transient_error"]
    evidence: list[Evidence] = Field(default_factory=list)
    error_code: str | None = None
    message: str | None = None


class CaseInput(BaseModel):
    case_id: str
    order_id: str
    source_type: Literal["manual", "rule_generated", "e2e_blind"]
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
    fact_mode: FactMode | None = None
    time_relation: TimeRelation | None = None
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
    user_business_facts: list[str] = Field(default_factory=list)
    agent_business_facts: list[str] = Field(default_factory=list)
    user_interaction_acts: list[str] = Field(default_factory=list)
    agent_interaction_acts: list[str] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    evidence: dict[str, Evidence] = Field(default_factory=dict)
    conflicts: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    candidate_decisions: list[dict[str, Any]] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)


class ActionPlan(BaseModel):
    action_type: str
    parameters: dict[str, Any]
    requires_confirmation: bool = True
    idempotency_key: str


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
    action_plan: ActionPlan | None = None
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
