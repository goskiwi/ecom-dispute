from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SPECS = [
    {
        "case_id": "v3gap-unrecognized-needed",
        "source": "v3-unrecognized_charge",
        "conversation": "这笔扣款不是我授权的，银行还提供了渠道交易号，请一起核验支付网关事件。",
        "tool": "get_payment_gateway_events",
        "status": "ok",
        "kind": "payment_gateway",
        "record": (
            "payment_gateway_events",
            {
                "gateway_event_id": "v3gap-gateway-unrecognized",
                "transaction_id": "txn-unrecognized",
                "event_type": "capture",
                "amount": 199,
                "status": "succeeded",
                "occurred_at": "2026-07-02T08:00:00",
                "version": 1,
            },
        ),
    },
    {
        "case_id": "v3gap-unrecognized-not-needed",
        "source": "v3d-charge_recognized",
        "conversation": "我起初不认识这笔扣款，请核验陌生扣款记录；订单和支付关联已经足够，不需要渠道明细。",
        "tool": None,
    },
    {
        "case_id": "v3gap-refund-amount-needed",
        "source": "v3d-refund_credit_amount_mismatch",
        "conversation": "退款记录是199元，银行卡只入账99元，请进一步核验支付网关事件。",
        "tool": "get_payment_gateway_events",
        "status": "ok",
        "kind": "payment_gateway",
        "record": (
            "payment_gateway_events",
            {
                "gateway_event_id": "v3gap-gateway-refund",
                "transaction_id": "txn-refund-credit",
                "event_type": "credit",
                "amount": 99,
                "status": "succeeded",
                "occurred_at": "2026-07-03T08:00:00",
                "version": 1,
            },
        ),
    },
    {
        "case_id": "v3gap-refund-amount-not-needed",
        "source": "v3-refund_amount_mismatch",
        "conversation": "订单实付199元，退款记录只有99元，核心订单和退款记录已经能说明问题。",
        "tool": None,
    },
    {
        "case_id": "v3gap-item-mismatch-needed",
        "source": "v3d-received_item_mismatch_unverified",
        "conversation": "我下单白色9码却收到黑色8码，并且已经上传了实收商品照片，请核验附件。",
        "tool": "get_claim_attachments",
        "status": "ok",
        "kind": "claim_attachment",
        "record": (
            "claim_attachments",
            {
                "attachment_id": "v3gap-mismatch-photo",
                "attachment_type": "received_item_photo",
                "uri": "evidence://v3gap/mismatch-photo",
                "size_bytes": 2048,
                "summary": "实收黑色8码商品照片",
                "created_at": "2026-07-05T08:00:00",
                "version": 1,
            },
        ),
    },
    {
        "case_id": "v3gap-item-mismatch-not-needed",
        "source": "v3-received_item_mismatch",
        "conversation": "订单是白色9码，仓库扫描已经显示打包成黑色8码，不需要额外照片即可确认仓库错配。",
        "tool": None,
    },
    {
        "case_id": "v3gap-delivery-address-needed",
        "source": "v3d-delivery_receipt_disputed",
        "conversation": "物流显示签收但我没收到，而且怀疑送到了旧地址，请核验订单配送地址。",
        "tool": "get_delivery_address",
        "status": "ok",
        "kind": "delivery_address",
        "record": (
            "delivery_addresses",
            {
                "address_id": "v3gap-delivery-address",
                "city": "旧城市",
                "masked_address": "旧城区***路",
                "contact_suffix": "4321",
                "version": 1,
            },
        ),
    },
    {
        "case_id": "v3gap-delivery-address-not-needed",
        "source": "v3-delivered_not_received",
        "conversation": "物流显示送达但我没有收到，而且承运商没有签收证明；应先补充签收证明，不需要核对地址。",
        "tool": None,
    },
    {
        "case_id": "v3gap-delivery-address-negative",
        "source": "v3d-delivery_not_marked_delivered",
        "conversation": "客服声称包裹已送达但我没有收到，物流系统却没有送达记录；请查询是否寄往旧地址。",
        "tool": "get_delivery_address",
        "status": "not_found",
        "kind": "query",
    },
    {
        "case_id": "v3gap-condition-logistics-needed",
        "source": "v3-item_condition_issue",
        "conversation": "商品和外包装都有挤压破损，我已经上传照片，还需要核验运输途中是否发生异常。",
        "tool": "get_logistics_events",
        "status": "ok",
        "kind": "logistics",
        "record": (
            "logistics_events",
            {
                "event_id": "v3gap-condition-logistics",
                "event_type": "exception",
                "occurred_at": "2026-07-04T08:00:00",
                "detail": "package crushed in transit",
                "version": 1,
            },
        ),
    },
    {
        "case_id": "v3gap-condition-logistics-not-needed",
        "source": "v3d-item_condition_attachment_missing",
        "conversation": "商品破损但我还没有上传任何照片，应先补充商品和包装凭证。",
        "tool": None,
    },
    {
        "case_id": "v3gap-condition-logistics-negative",
        "source": "v3d-item_condition_evidence_insufficient",
        "conversation": "商品破损并怀疑运输异常，但目前系统可能没有物流事件，请查询确认。",
        "tool": "get_logistics_events",
        "status": "not_found",
        "kind": "query",
    },
]


def main() -> None:
    source = json.loads((ROOT / "data" / "v3_e2e_90_inputs.json").read_text())
    oracle = json.loads((ROOT / "evals" / "v3_decision_oracle.json").read_text())
    cases = {item["case_id"]: item for item in source["cases"]}
    output_cases = []
    output_oracle = {}
    for spec in SPECS:
        case = copy.deepcopy(cases[spec["source"]])
        case["case_id"] = spec["case_id"]
        case["conversation"] = [
            {"speaker": "user", "text": spec["conversation"]},
            {"speaker": "agent", "text": "我会先核验核心证据，再判断是否需要长尾证据。"},
        ]
        if spec.get("record"):
            field, record = spec["record"]
            record = {"order_id": case["order_id"], **record}
            case[field] = [record]
        output_cases.append(case)
        base = oracle[spec["source"]]
        output_oracle[spec["case_id"]] = {
            "route_type": base["route_type"],
            "decision": base["decision"],
            "responsible_party": base["responsible_party"],
            "review_required": base["review_required"],
            "expected_gap_tool": spec["tool"],
            "expected_tool_status": spec.get("status"),
            "expected_added_evidence_kind": spec.get("kind"),
        }
    (ROOT / "data" / "v3_1_gap_12_inputs.json").write_text(
        json.dumps(
            {"source": "v3_gap_12_pre_llm", "cases": output_cases}, ensure_ascii=False, indent=2
        )
        + "\n"
    )
    (ROOT / "evals" / "v3_1_gap_12_oracle.json").write_text(
        json.dumps(output_oracle, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        {
            "cases": len(output_cases),
            "tool_needed": sum(
                item["expected_gap_tool"] is not None for item in output_oracle.values()
            ),
            "negative_results": sum(
                item["expected_tool_status"] == "not_found" for item in output_oracle.values()
            ),
        }
    )


if __name__ == "__main__":
    main()
