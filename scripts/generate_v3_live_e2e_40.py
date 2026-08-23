from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = 40

RISK_TOKENS = {
    "conflict",
    "mismatch",
    "overdue",
    "missing",
    "unavailable",
    "outage",
    "error",
    "declined",
    "incorrect",
    "unrecognized",
    "blocked",
    "expired",
    "unsupported",
}

LIVE_CONVERSATIONS = {
    "v3d-cancellation_refund_missing": [
        {"speaker": "user", "text": "取消申请已经受理，订单也没有发货，但退款一直没有开始。"},
        {"speaker": "agent", "text": "我会核对取消记录和退款流水。"},
    ],
    "v3d-delivery_not_marked_delivered": [
        {"speaker": "user", "text": "客服说包裹已经送达，但我没收到，物流页面也没有送达记录。"},
        {"speaker": "agent", "text": "我会核验订单和物流状态。"},
    ],
    "v3d-delivery_receipt_disputed": [
        {"speaker": "user", "text": "物流显示已签收，但签收人不是我，家里也没有收到包裹。"},
        {"speaker": "agent", "text": "我会核对签收证明和配送地址。"},
    ],
    "v3d-exchange_price_difference": [
        {
            "speaker": "user",
            "text": "我想把当前商品换成另一个尺码，但目标尺码价格更高，请确认差价。",
        },
        {"speaker": "agent", "text": "我会查询换货资格、库存和差价。"},
    ],
    "v3d-fulfillment_event_conflict": [
        {
            "speaker": "user",
            "text": "订单页面仍显示运输中，但承运商页面却显示已经送达，请帮我核对状态。",
        },
        {"speaker": "agent", "text": "我会比对订单和物流事件。"},
    ],
    "v3d-inventory_backorder_available": [
        {"speaker": "user", "text": "这件商品暂时缺货，可以预订并在补货后发出吗？"},
        {"speaker": "agent", "text": "我会查询库存和预订能力。"},
    ],
    "v3d-item_condition_attachment_missing": [
        {"speaker": "user", "text": "收到的商品已经破损，但我还没有上传商品和包装照片。"},
        {"speaker": "agent", "text": "我会检查现有仓库记录和附件。"},
    ],
    "v3d-item_condition_evidence_insufficient": [
        {"speaker": "user", "text": "商品有明显质量问题，但目前没有照片或其他凭证。"},
        {"speaker": "agent", "text": "我会核对当前能够取得的证据。"},
    ],
    "v3d-missing_item_not_verified": [
        {"speaker": "user", "text": "订单有两件商品，我只收到一件，但仓库记录似乎显示打包了两件。"},
        {"speaker": "agent", "text": "我会核对订单数量和仓库扫描。"},
    ],
    "v3d-order_details_conflict": [
        {"speaker": "user", "text": "确认邮件写了两件商品，但订单页面只显示一件，请核对订单明细。"},
        {"speaker": "agent", "text": "我会核对不同版本的订单记录。"},
    ],
    "v3d-payment_order_state_conflict": [
        {
            "speaker": "user",
            "text": "银行显示扣款成功，但订单页面明确显示创建失败。",
        },
        {"speaker": "agent", "text": "退款已完成。"},
    ],
    "v3d-price_record_conflict": [
        {"speaker": "user", "text": "订单购买价、当前页面价格和价保记录显示的金额互相对不上。"},
        {"speaker": "agent", "text": "我会核对价格版本和政策。"},
    ],
    "v3d-product_information_missing": [
        {"speaker": "user", "text": "请问这双靴子是否防水？商品页面没有写清楚。"},
        {"speaker": "agent", "text": "我会查询商品目录，不会猜测属性。"},
    ],
    "v3d-received_item_mismatch_unverified": [
        {
            "speaker": "user",
            "text": "我下单的是白色9码，实际收到黑色8码，但仓库扫描似乎仍显示白色9码。",
        },
        {"speaker": "agent", "text": "我们会在明天补发正确商品。"},
    ],
    "v3d-refund_arrival_overdue": [
        {"speaker": "user", "text": "退款已经处理中超过承诺天数，银行卡仍然没有到账。"},
        {"speaker": "agent", "text": "我会核验退款流水和支付渠道状态。"},
    ],
    "v3d-refund_credit_amount_mismatch": [
        {"speaker": "user", "text": "退款记录是199元，但银行卡实际只入账99元。"},
        {"speaker": "agent", "text": "我会比对退款金额和入账流水。"},
    ],
    "v3d-refund_not_initiated_overdue": [
        {"speaker": "user", "text": "售后很早就审核通过了，但直到现在仍没有发起退款。"},
        {"speaker": "agent", "text": "我会核验售后时间和退款记录。"},
    ],
    "v3d-refund_record_conflict": [
        {"speaker": "user", "text": "退款系统显示成功，但银行卡里没有对应的入账流水。"},
        {"speaker": "agent", "text": "我已提交复检并转人工处理。"},
    ],
    "v3d-return_condition_unknown": [
        {"speaker": "user", "text": "我想退货，但还没有说明商品是否拆封或使用过。"},
        {"speaker": "agent", "text": "我需要先确认商品状态再判断资格。"},
    ],
    "v3d-shipping_option_unavailable": [
        {"speaker": "user", "text": "下单前想选择国际配送，但这个地区似乎没有可用方案。"},
        {"speaker": "agent", "text": "我会查询配送覆盖范围。"},
    ],
    "v3d-site_outage": [
        {"speaker": "user", "text": "网站所有页面都打不开，结账和搜索也完全无法使用。"},
        {"speaker": "agent", "text": "我会查询站点健康和事故状态。"},
    ],
}


def main() -> None:
    dataset = json.loads((ROOT / "data" / "v3_e2e_90_inputs.json").read_text())
    oracle = json.loads((ROOT / "evals" / "v3_decision_oracle.json").read_text())
    cases = {item["case_id"]: item for item in dataset["cases"]}
    ranked = []
    for case_id, expected in oracle.items():
        reasons = []
        score = 0
        if expected["review_required"]:
            score += 5
            reasons.append("review_required")
        if expected["action_type"]:
            score += 3
            reasons.append("action_plan")
        matched = sorted(token for token in RISK_TOKENS if token in expected["decision"])
        if matched:
            score += 2
            reasons.extend(matched)
        if any("conflict" in decision for decision in expected["compliance_decisions"]):
            score += 2
            reasons.append("compliance_conflict")
        ranked.append(
            {
                "case_id": case_id,
                "route_type": expected["route_type"],
                "decision": expected["decision"],
                "risk_score": score,
                "reasons": reasons or ["route_coverage"],
            }
        )
    ranked.sort(key=lambda item: (-item["risk_score"], item["case_id"]))

    by_route = defaultdict(list)
    for item in ranked:
        by_route[item["route_type"]].append(item)
    selected = [by_route[route][0] for route in sorted(by_route)]
    selected_ids = {item["case_id"] for item in selected}
    for item in ranked:
        if len(selected) == TARGET:
            break
        if item["case_id"] not in selected_ids:
            selected.append(item)
            selected_ids.add(item["case_id"])
    if len(selected) != TARGET or len({item["route_type"] for item in selected}) != 26:
        raise ValueError("live E2E selection does not satisfy target and route coverage")
    selected.sort(key=lambda item: item["case_id"])
    selected_cases = []
    for item in selected:
        case = json.loads(json.dumps(cases[item["case_id"]], ensure_ascii=False))
        if item["case_id"].startswith("v3d-"):
            if item["case_id"] not in LIVE_CONVERSATIONS:
                raise ValueError(f"missing blind conversation: {item['case_id']}")
            case["conversation"] = LIVE_CONVERSATIONS[item["case_id"]]
            serialized = json.dumps(case["conversation"], ensure_ascii=False)
            if item["decision"] in serialized:
                raise ValueError(f"decision leakage in conversation: {item['case_id']}")
        selected_cases.append(case)
    selected_oracle = {item["case_id"]: oracle[item["case_id"]] for item in selected}

    (ROOT / "data" / "v3_1_live_e2e_40_inputs.json").write_text(
        json.dumps(
            {"source": "v3_1_live_e2e_40_pre_llm_stratified_risk", "cases": selected_cases},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    (ROOT / "evals" / "v3_1_live_e2e_40_oracle.json").write_text(
        json.dumps(selected_oracle, ensure_ascii=False, indent=2) + "\n"
    )
    (ROOT / "evals" / "v3_1_live_e2e_40_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "selection": "highest risk per route, then global risk fill",
                "case_count": len(selected),
                "route_count": len({item["route_type"] for item in selected}),
                "items": selected,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(
        {
            "cases": len(selected),
            "routes": len({item["route_type"] for item in selected}),
            "review_required": sum(
                selected_oracle[item["case_id"]]["review_required"] for item in selected
            ),
            "action_plans": sum(
                selected_oracle[item["case_id"]]["action_type"] is not None for item in selected
            ),
        }
    )


if __name__ == "__main__":
    main()
