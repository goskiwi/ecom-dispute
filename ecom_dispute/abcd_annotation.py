from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

from .datasets import load_abcd_subset

ROUTE_GUIDE = {
    "refund": "退款是否发起、处理中、完成或到账状态争议。",
    "refund_amount": "应退金额、退款记录金额或实际入账金额不一致。",
    "duplicate_charge": "同一订单存在两笔或多笔扣款。",
    "payment_order_failure": "资金已扣但订单创建失败、取消或未形成有效订单。",
    "delivery": "已发货后的运输延迟、物流异常或承诺时效问题。",
    "merchant_not_shipped": "商家超过发货时限且没有承运商揽收。",
    "delivered_not_received": "系统显示签收/送达，但用户否认实际收到。",
    "cancellation_in_transit": "取消申请与揽收、运输、退款时间存在争议。",
    "return_eligibility": "用户是否满足退货期限、品类或商品状态条件。",
    "wrong_item": "实收SKU、颜色、型号或商品身份与订单不一致。",
    "missing_item": "实际收到商品数量少于订单数量。",
    "damaged_item": "用户已收到商品且商品本身破损。",
    "other": "普通咨询、项目不支持或无法归入以上争议Route。",
}


def build_annotation_forms(
    dataset_path: Path,
    manifest_path: Path,
    rater1_path: Path,
    rater2_path: Path,
) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    wanted = {item["external_id"] for item in manifest["items"]}
    subflows = {item["subflow"] for item in manifest["items"]}
    records = {
        item.external_id: item
        for item in load_abcd_subset(dataset_path, limit=100_000, subflows=subflows)
        if item.external_id in wanted
    }
    if set(records) != wanted:
        raise ValueError("ABCD annotation source does not match committed manifest")
    base_items = [
        {
            "external_id": external_id,
            "conversation": records[external_id].conversation,
            "annotation": _blank_annotation(),
        }
        for external_id in sorted(wanted)
    ]
    for rater_id, path in (("rater1", rater1_path), ("rater2", rater2_path)):
        payload = {
            "schema_version": 1,
            "rater_id": rater_id,
            "blind_fields_hidden": ["abcd_subflow", "coarse_route", "model_prediction"],
            "route_guide": ROUTE_GUIDE,
            "items": json.loads(json.dumps(base_items, ensure_ascii=False)),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"case_count": len(base_items), "rater_files": 2}


def agreement_and_consensus(
    rater1_path: Path,
    rater2_path: Path,
    consensus_path: Path,
) -> dict:
    first = json.loads(rater1_path.read_text(encoding="utf-8"))
    second = json.loads(rater2_path.read_text(encoding="utf-8"))
    first_items = {item["external_id"]: item for item in first["items"]}
    second_items = {item["external_id"]: item for item in second["items"]}
    if set(first_items) != set(second_items):
        raise ValueError("rater forms contain different ABCD records")
    completed_pairs = []
    consensus_items = []
    for external_id in sorted(first_items):
        a = first_items[external_id]["annotation"]
        b = second_items[external_id]["annotation"]
        complete = _annotation_complete(a) and _annotation_complete(b)
        if complete:
            completed_pairs.append((a, b))
        agreed = complete and _labels(a) == _labels(b)
        consensus_items.append(
            {
                "external_id": external_id,
                "status": "agreed" if agreed else "needs_resolution",
                "consensus": dict(a) if agreed else _blank_annotation(),
                "rater1": a,
                "rater2": b,
            }
        )
    consensus_path.write_text(
        json.dumps({"schema_version": 1, "items": consensus_items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "case_count": len(first_items),
        "completed_pairs": len(completed_pairs),
        "exact_agreement": _mean(_labels(a) == _labels(b) for a, b in completed_pairs),
        "supported_agreement": _mean(a["supported"] == b["supported"] for a, b in completed_pairs),
        "has_dispute_agreement": _mean(
            a["has_dispute"] == b["has_dispute"] for a, b in completed_pairs
        ),
        "primary_route_agreement": _mean(
            a["primary_route"] == b["primary_route"] for a, b in completed_pairs
        ),
        "supported_kappa": _cohen_kappa(
            [a["supported"] for a, _ in completed_pairs],
            [b["supported"] for _, b in completed_pairs],
        ),
        "has_dispute_kappa": _cohen_kappa(
            [a["has_dispute"] for a, _ in completed_pairs],
            [b["has_dispute"] for _, b in completed_pairs],
        ),
        "primary_route_kappa": _cohen_kappa(
            [a["primary_route"] for a, _ in completed_pairs],
            [b["primary_route"] for _, b in completed_pairs],
        ),
        "needs_resolution": sum(item["status"] == "needs_resolution" for item in consensus_items),
    }


def rescore_first_run(
    raw_result_path: Path,
    consensus_path: Path,
) -> dict:
    with gzip.open(raw_result_path, "rt", encoding="utf-8") as stream:
        raw = json.load(stream)
    observed = {
        item["external_id"]: item
        for item in raw["results"]
        if "error" not in item
    }
    consensus = json.loads(consensus_path.read_text(encoding="utf-8"))
    scored = []
    for item in consensus["items"]:
        label = item["consensus"]
        if item["status"] not in {"agreed", "resolved"} or not _annotation_complete(label):
            continue
        prediction = observed.get(item["external_id"])
        if not prediction:
            continue
        acceptable = set(label["acceptable_routes"]) | {label["primary_route"]}
        scored.append(
            {
                "external_id": item["external_id"],
                "observed_route_type": prediction["observed_route_type"],
                "primary_route": label["primary_route"],
                "strict_correct": prediction["observed_route_type"] == label["primary_route"],
                "acceptable_correct": prediction["observed_route_type"] in acceptable,
            }
        )
    return {
        "consensus_cases": len(scored),
        "strict_route_accuracy": _mean(item["strict_correct"] for item in scored),
        "acceptable_route_accuracy": _mean(item["acceptable_correct"] for item in scored),
        "results": scored,
    }


def _blank_annotation() -> dict[str, Any]:
    return {
        "supported": None,
        "has_dispute": None,
        "primary_route": None,
        "acceptable_routes": [],
        "evidence_turns": [],
        "reason": None,
        "confidence": None,
        "translation_uncertain": False,
    }


def _annotation_complete(annotation: dict) -> bool:
    return (
        isinstance(annotation.get("supported"), bool)
        and isinstance(annotation.get("has_dispute"), bool)
        and annotation.get("primary_route") in ROUTE_GUIDE
        and annotation.get("confidence") in {"low", "medium", "high"}
        and bool(annotation.get("reason"))
    )


def _labels(annotation: dict) -> tuple:
    return (
        annotation["supported"],
        annotation["has_dispute"],
        annotation["primary_route"],
        tuple(sorted(annotation["acceptable_routes"])),
    )


def _cohen_kappa(first: list, second: list) -> float | None:
    if not first:
        return None
    observed = _mean(a == b for a, b in zip(first, second, strict=True))
    labels = set(first) | set(second)
    expected = sum(
        (first.count(label) / len(first)) * (second.count(label) / len(second))
        for label in labels
    )
    if expected == 1:
        return 1.0 if observed == 1 else None
    return (observed - expected) / (1 - expected)


def _mean(values: object) -> float | None:
    items = list(values)
    return sum(items) / len(items) if items else None
