from __future__ import annotations

import json
from pathlib import Path

from ecom_dispute.ontology import BUSINESS_ROUTE_IDS
from ecom_dispute.seed_v3 import CASE_SPECS

ROOT = Path(__file__).resolve().parents[1]

EXCEPTION_ROUTES = {
    "refund_amount_mismatch",
    "duplicate_charge",
    "payment_captured_order_failed",
    "unrecognized_charge",
    "order_fee_dispute",
    "fulfillment_progress",
    "delivered_not_received",
    "order_cancellation",
    "received_item_mismatch",
    "missing_item",
    "item_condition_issue",
    "promotion_support",
    "membership_support",
    "checkout_issue",
    "cart_issue",
    "search_issue",
    "site_performance",
}

RETURN_REASONS = {
    "return_request": "fit_issue",
}

BOUNDARIES = [
    (
        "buyer-color",
        "我自己下单时选错了黑色，现在只想退货退款，不需要换货。",
        "return_request",
        False,
        "buyer_selected_wrong_variant",
    ),
    (
        "seller-color",
        "订单写的是白色，但包裹里实际是黑色。",
        "received_item_mismatch",
        True,
        None,
    ),
    ("fit-size", "我订的9码没有发错，但穿起来太紧，想退货。", "return_request", False, "fit_issue"),
    (
        "seller-size",
        "订单是9码，收到的标签却是8码。",
        "received_item_mismatch",
        True,
        None,
    ),
    (
        "refund-after-return",
        "退货仓库已验收，但五天后退款仍未发起。",
        "refund_progress",
        True,
        None,
    ),
    (
        "return-warehouse",
        "退货包裹已经寄出，物流显示签收但仓库还没入库。",
        "return_progress",
        True,
        None,
    ),
    (
        "inventory-cart",
        "页面明确显示这个SKU缺货，所以无法加入购物车。",
        "inventory_availability",
        False,
        None,
    ),
    ("cart-state", "商品有库存，但点击加入购物车后数量始终还是零。", "cart_issue", True, None),
    (
        "checkout-no-charge",
        "结账时银行卡被拒绝，银行确认没有发生扣款。",
        "checkout_issue",
        True,
        None,
    ),
    (
        "captured-no-order",
        "银行卡已经成功扣款，但系统没有生成订单。",
        "payment_captured_order_failed",
        True,
        None,
    ),
    (
        "shipping-before-order",
        "下单前想知道国际标准配送需要多少钱。",
        "shipping_options",
        False,
        None,
    ),
    (
        "shipping-fee-charged",
        "订单确认应收10元运费，但账单实际收了25元。",
        "order_fee_dispute",
        True,
        None,
    ),
    ("not-arrived", "包裹仍显示运输中，已经超过承诺日期三天。", "fulfillment_progress", True, None),
    (
        "delivered-missing",
        "物流显示昨天已送达，但我和家人都没收到。",
        "delivered_not_received",
        True,
        None,
    ),
]

UNSUPPORTED = [
    ("password", "我忘记账户密码，请帮我重置。"),
    ("two-factor", "我无法通过两步验证，需要关闭2FA。"),
    ("credit-extension", "我需要把订阅账单的还款日期延后一个月。"),
    ("identity-name", "请把账户实名信息修改成另一个人的名字。"),
]


def main() -> None:
    cases = []
    oracle = {}
    for route in BUSINESS_ROUTE_IDS:
        case_id = f"v3-boundary-clear-{route}"
        text = CASE_SPECS[route][0]
        cases.append(_case(case_id, text))
        label = {
            "route_type": route,
            "has_business_exception": route in EXCEPTION_ROUTES,
        }
        if route in RETURN_REASONS:
            label["return_reason"] = RETURN_REASONS[route]
        oracle[case_id] = label
    for suffix, text, route, exception, reason in BOUNDARIES:
        case_id = f"v3-boundary-pair-{suffix}"
        cases.append(_case(case_id, text))
        oracle[case_id] = {
            "route_type": route,
            "has_business_exception": exception,
        }
        if reason:
            oracle[case_id]["return_reason"] = reason
    for suffix, text in UNSUPPORTED:
        case_id = f"v3-boundary-unsupported-{suffix}"
        cases.append(_case(case_id, text))
        oracle[case_id] = {
            "route_type": "other",
            "has_business_exception": False,
        }
    input_path = ROOT / "data" / "v3_1_route_boundary_inputs.json"
    oracle_path = ROOT / "evals" / "v3_1_route_boundary_oracle.json"
    input_path.write_text(
        json.dumps({"schema_version": 3, "cases": cases}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    oracle_path.write_text(
        json.dumps(oracle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print({"cases": len(cases), "routes": len({x["route_type"] for x in oracle.values()})})


def _case(case_id: str, text: str) -> dict:
    return {"case_id": case_id, "conversation": [{"speaker": "user", "text": text}]}


if __name__ == "__main__":
    main()
