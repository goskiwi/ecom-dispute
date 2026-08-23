from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .abcd_annotation import ROUTE_GUIDE
from .llm import ResponsesClient

RouteId = Literal[
    "refund",
    "refund_amount",
    "duplicate_charge",
    "payment_order_failure",
    "delivery",
    "merchant_not_shipped",
    "delivered_not_received",
    "cancellation_in_transit",
    "return_eligibility",
    "wrong_item",
    "missing_item",
    "damaged_item",
    "other",
]


class CandidateAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supported: bool
    has_dispute: bool
    primary_route: RouteId
    acceptable_routes: list[RouteId]
    evidence_turns: list[int] = Field(min_length=1)
    reason: str = Field(min_length=1)
    confidence: Literal["low", "medium", "high"]
    ambiguity: str | None

    @model_validator(mode="after")
    def validate_route_relationships(self) -> CandidateAnnotation:
        if not self.supported and self.primary_route != "other":
            raise ValueError("unsupported conversations must use other")
        if self.supported and self.primary_route == "other":
            raise ValueError("supported conversations cannot use other")
        if self.primary_route not in self.acceptable_routes:
            self.acceptable_routes.append(self.primary_route)
        self.acceptable_routes = list(dict.fromkeys(self.acceptable_routes))
        self.evidence_turns = sorted(set(self.evidence_turns))
        return self


def preannotate_abcd(
    client: ResponsesClient,
    source_path: Path,
    output_path: Path,
    cache_path: Path,
    workers: int = 4,
) -> dict:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    cache_lock = threading.Lock()

    def annotate_one(item: dict) -> dict:
        external_id = item["external_id"]
        if external_id in cache and "annotation" in cache[external_id]:
            return cache[external_id]
        conversation = item["conversation"]
        translation = item.get("translation")
        prompt = _prompt(conversation, translation)
        started = time.perf_counter()
        input_tokens = 0
        output_tokens = 0
        repair_hint = None
        for validation_attempt in range(1, 3):
            request_prompt = prompt
            if repair_hint:
                request_prompt += (
                    "\n上一次候选标签未通过校验。请重新阅读全文并修正，不能解释。"
                    f"校验错误：{repair_hint}"
                )
            payload = {
                "model": client.model,
                "input": request_prompt,
                "max_output_tokens": 900,
                "store": False,
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "abcd_candidate_annotation",
                        "strict": True,
                        "schema": CandidateAnnotation.model_json_schema(),
                    }
                },
            }
            response = client.create_response(payload)
            usage = response.get("usage") or {}
            input_tokens += int(usage.get("input_tokens", 0))
            output_tokens += int(usage.get("output_tokens", 0))
            try:
                annotation = CandidateAnnotation.model_validate_json(
                    ResponsesClient._output_text(response)
                )
                if any(index >= len(conversation) for index in annotation.evidence_turns):
                    raise ValueError(f"evidence turn out of range: {external_id}")
            except ValueError as exc:
                if validation_attempt == 2:
                    raise
                repair_hint = str(exc)
                continue
            break
        return {
            "annotation": annotation.model_dump(),
            "telemetry": {
                "model": response.get("model", client.model),
                "response_id": response.get("id"),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "validation_attempts": validation_attempt,
            },
        }

    errors: dict[str, str] = {}
    pending = [item for item in source["items"] if item["external_id"] not in cache]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(annotate_one, item): item["external_id"] for item in pending}
        for future in as_completed(futures):
            external_id = futures[future]
            try:
                result = future.result()
            except (RuntimeError, ValueError) as exc:
                errors[external_id] = str(exc)
                continue
            with cache_lock:
                cache[external_id] = result
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(
                    json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
                )

    draft = json.loads(json.dumps(source, ensure_ascii=False))
    draft["rater_id"] = "assistant_draft"
    draft["annotation_method"] = "AI pre-annotation; requires disclosed human review"
    completed = 0
    careful = 0
    for item in draft["items"]:
        result = cache.get(item["external_id"])
        if not result:
            continue
        candidate = dict(result["annotation"])
        ambiguity = candidate.pop("ambiguity")
        candidate["translation_uncertain"] = False
        candidate["human_verified"] = False
        audit_reasons = _conservative_audit_reasons(candidate, item["conversation"])
        needs_careful_review = (
            candidate["confidence"] != "high" or bool(ambiguity) or bool(audit_reasons)
        )
        item["annotation"] = candidate
        item["assistant_review"] = {
            "review_tier": "careful_review" if needs_careful_review else "quick_audit",
            "ambiguity": ambiguity,
            "audit_reasons": audit_reasons,
            "model": result["telemetry"]["model"],
        }
        completed += 1
        careful += needs_careful_review
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")

    valid = [item for item in cache.values() if "annotation" in item]
    return {
        "case_count": len(source["items"]),
        "preannotated": completed,
        "quick_audit": completed - careful,
        "careful_review": careful,
        "errors": len(errors),
        "error_items": errors,
        "input_tokens": sum(item["telemetry"]["input_tokens"] for item in valid),
        "output_tokens": sum(item["telemetry"]["output_tokens"] for item in valid),
        "latency_ms": sum(item["telemetry"]["latency_ms"] for item in valid),
    }


def _prompt(conversation: list[dict], translation: list[dict] | None) -> str:
    visible = {"original": conversation}
    if translation:
        visible["chinese_aid"] = translation
    return (
        "你是电商争议数据的预标注员。只根据所给对话和下列Route定义逐对话判断，"
        "不能推测对话外事实。输出是供人工复核的候选标签，不是最终真值。\n"
        f"Route定义：{json.dumps(ROUTE_GUIDE, ensure_ascii=False)}\n"
        "边界规则：\n"
        "1. primary_route按用户当前主要诉求，不按客服后台操作或数据集流程名。\n"
        "2. supported表示12个业务Route之一能准确表达主要诉求；不支持时必须other。\n"
        "3. has_dispute仅表示已经出现业务异常、结果冲突或用户对处理结果不满；"
        "普通信息咨询、仅询问资格、正常状态查询或已正常解决通常为false。\n"
        "4. return_eligibility只用于是否满足退货期限/品类/商品状态；已经收到错误SKU/颜色/型号用wrong_item。\n"
        "5. delivery用于已揽收后的延迟或运输异常；merchant_not_shipped要求超过发货时限且无揽收；"
        "delivered_not_received要求系统显示送达但用户说未收到。\n"
        "6. refund是退款发起/处理/完成/到账状态；refund_amount只用于金额不一致。\n"
        "7. acceptable_routes只放确有合理边界重叠的Route并包含primary，不能为了保险罗列。\n"
        "8. evidence_turns使用从0开始的原对话轮次，至少引用用户主要诉求，必要时补充客服回应。\n"
        "9. reason用中文写一句可由原文验证的理由。只有单一明确Route、无关键省略且证据直接时才用high；"
        "存在多意图、Route边界、关键信息不足或译文疑义时用medium/low并在ambiguity说明。\n"
        f"对话：{json.dumps(visible, ensure_ascii=False)}"
    )


def _conservative_audit_reasons(candidate: dict, conversation: list[dict]) -> list[str]:
    """Escalate boundary indicators for review; never use them to assign a label."""
    user_text = " ".join(turn["text"].lower() for turn in conversation if turn["speaker"] == "user")
    reasons = []
    if candidate["primary_route"] == "delivery":
        status_says_delivered = any(
            phrase in user_text
            for phrase in ("shows delivered", "says delivered", "shows received")
        )
        user_denies_receipt = any(
            phrase in user_text
            for phrase in (
                "haven't received",
                "have not received",
                "didn't receive",
                "did not receive",
                "not delivered",
            )
        )
        if status_says_delivered and user_denies_receipt:
            reasons.append("同时出现系统送达与用户未收到，复核delivery边界")
    if candidate["primary_route"] == "wrong_item":
        explicit_mismatch = any(
            phrase in user_text
            for phrase in (
                "received",
                "i got",
                "they sent",
                "was sent",
                "instead of",
                "different from",
            )
        ) or ("ordered" in user_text and " but " in user_text)
        if not explicit_mismatch:
            reasons.append("未明确实收商品与下单规格不一致，复核wrong_item边界")
    return reasons
