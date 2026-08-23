from __future__ import annotations

import json
import sqlite3

from .ontology import BUSINESS_ROUTE_IDS

CASE_SPECS = {
    "refund_progress": ("退款正在处理中，请确认什么时候到账。", "refund_processing_within_sla"),
    "refund_amount_mismatch": ("订单实付199元，但退款记录只有99元。", "refund_amount_incorrect"),
    "duplicate_charge": ("同一订单被成功扣款两次。", "duplicate_charge_confirmed"),
    "payment_captured_order_failed": (
        "银行卡已扣款，但订单创建失败。",
        "captured_order_failed_unreversed",
    ),
    "unrecognized_charge": (
        "我从未买过这件商品，却出现一笔扣款。",
        "unrecognized_charge_confirmed",
    ),
    "order_fee_dispute": ("订单应收10元运费，实际收了20元。", "order_fee_incorrect"),
    "fulfillment_progress": ("下单多日仍没有发货或揽收记录。", "fulfillment_delayed_merchant"),
    "delivered_not_received": ("物流显示送达，但我没有收到。", "delivery_proof_missing"),
    "order_cancellation": ("取消已受理，但包裹随后仍被揽收。", "cancel_before_pickup_but_shipped"),
    "return_request": ("商品不合身，我想申请退货。", "return_eligible"),
    "return_progress": ("退货已经寄出，我想查询入库进度。", "return_in_transit"),
    "exchange_request": ("我想把9码换成10码，请确认库存。", "exchange_available"),
    "received_item_mismatch": (
        "我下单白色SKU，实际收到黑色SKU。",
        "received_item_mismatch_confirmed",
    ),
    "missing_item": ("订单两件商品实际只收到一件。", "missing_item_warehouse_shortage"),
    "item_condition_issue": (
        "收到的衬衫有明显污渍，我已经上传照片。",
        "item_condition_evidence_collected",
    ),
    "order_management": ("我想把当前订单的配送时间改到晚上。", "order_change_allowed"),
    "product_information": ("请问这双靴子是否防水？", "product_information_found"),
    "inventory_availability": ("这条牛仔裤现在有库存吗？", "inventory_unavailable"),
    "price_adjustment": ("昨天购买后今天降价，能补差价吗？", "price_adjustment_eligible"),
    "promotion_support": ("五天前领取的优惠码结账时显示无效。", "promotion_invalid"),
    "shipping_options": ("下单前想了解国际配送方式和费用。", "shipping_option_available"),
    "membership_support": ("会员权益应有40元额度，但账户中没有。", "membership_credit_missing"),
    "checkout_issue": ("结账页面持续报错，但没有成功扣款。", "checkout_service_error"),
    "cart_issue": ("商品无法加入购物车，页面状态反复变化。", "cart_state_conflict"),
    "search_issue": ("搜索鞋子却一直出现不相关商品。", "search_index_stale"),
    "site_performance": ("网站今天非常慢并频繁报错。", "site_degraded"),
}


def seed_v3(connection: sqlite3.Connection) -> None:
    if set(CASE_SPECS) != set(BUSINESS_ROUTE_IDS):
        raise ValueError("V3 seed cases do not cover the frozen business route ontology")
    seed_v3_policies(connection)
    for index, (business_type, (user_text, _)) in enumerate(CASE_SPECS.items(), start=1):
        order_id = f"v3-order-{index:02d}"
        case_id = f"v3-{business_type}"
        status = "failed" if business_type == "payment_captured_order_failed" else "paid"
        if business_type == "delivered_not_received":
            status = "delivered"
        connection.execute(
            "INSERT INTO cases VALUES (?, ?, 'rule_generated', 'CN', ?, '2026-07-01T10:00:00', '2026-07-10T12:00:00', ?)",
            (
                case_id,
                order_id,
                business_type,
                json.dumps(
                    [
                        {"speaker": "user", "text": user_text},
                        {"speaker": "agent", "text": "我会依据业务记录和政策进行核验。"},
                    ],
                    ensure_ascii=False,
                ),
            ),
        )
        connection.execute(
            "INSERT INTO orders VALUES (?, ?, 'CN', ?, ?, 199.0, 'CNY', '2026-07-01T08:00:00', '2026-07-05T18:00:00', 1)",
            (order_id, f"v3-user-{index:02d}", business_type, status),
        )
        _seed_route_evidence(connection, index, order_id, business_type)


def seed_v3_policies(connection: sqlite3.Connection) -> None:
    for index, business_type in enumerate(BUSINESS_ROUTE_IDS, start=1):
        rules = {
            "initiate_within_hours": 48,
            "arrival_within_days": 5,
            "merchant_ship_hours": 48,
            "delivery_grace_hours": 24,
            "return_window_days": 14,
            "excluded_categories": ["personal_care"],
        }
        connection.execute(
            "INSERT INTO policies VALUES (?, 1, 'CN', ?, '2026-01-01T00:00:00', NULL, ?, ?)",
            (
                f"v3-{business_type}-cn",
                business_type,
                json.dumps(rules, ensure_ascii=False),
                f"V3 {business_type} 测试政策",
            ),
        )
    connection.execute(
        "INSERT INTO policies VALUES ('v3-service-compliance-cn', 1, 'CN', 'service_compliance', '2026-01-01T00:00:00', NULL, ?, 'V3客服合规政策')",
        (
            json.dumps(
                {
                    "fact_statements_must_be_grounded": True,
                    "unsupported_promises_forbidden": True,
                    "conflict_requires_escalation": True,
                },
                ensure_ascii=False,
            ),
        ),
    )


def _seed_route_evidence(
    connection: sqlite3.Connection, index: int, order_id: str, business_type: str
) -> None:
    item_id = f"v3-item-{index:02d}"
    if business_type in {
        "return_request",
        "return_progress",
        "exchange_request",
        "received_item_mismatch",
        "missing_item",
        "item_condition_issue",
    }:
        quantity = 2 if business_type == "missing_item" else 1
        connection.execute(
            "INSERT INTO order_items VALUES (?, ?, 'sku-white-9', 'V3测试商品', ?, 199.0, 'general', 1)",
            (item_id, order_id, quantity),
        )
    if business_type == "refund_progress":
        connection.execute(
            "INSERT INTO payments VALUES (?, ?, 'debit', 199, 'succeeded', '2026-07-01T08:01:00', 1)",
            (f"v3-pay-{index}", order_id),
        )
        connection.execute(
            "INSERT INTO after_sales_cases VALUES (?, ?, 'approved', '2026-07-07T08:00:00', 'return', 1)",
            (f"v3-as-{index}", order_id),
        )
        connection.execute(
            "INSERT INTO refunds VALUES (?, ?, 199, 'processing', '2026-07-08T08:00:00', NULL, 1)",
            (f"v3-ref-{index}", order_id),
        )
    elif business_type == "refund_amount_mismatch":
        connection.execute(
            "INSERT INTO payments VALUES (?, ?, 'credit', 99, 'succeeded', '2026-07-09T08:00:00', 1)",
            (f"v3-pay-{index}", order_id),
        )
        connection.execute(
            "INSERT INTO refunds VALUES (?, ?, 99, 'succeeded', '2026-07-08T08:00:00', '2026-07-09T08:00:00', 1)",
            (f"v3-ref-{index}", order_id),
        )
    elif business_type == "duplicate_charge":
        for offset in (1, 2):
            connection.execute(
                "INSERT INTO payments VALUES (?, ?, 'debit', 199, 'succeeded', ?, 1)",
                (f"v3-pay-{index}-{offset}", order_id, f"2026-07-01T08:0{offset}:00"),
            )
    elif business_type == "payment_captured_order_failed":
        connection.execute(
            "INSERT INTO payments VALUES (?, ?, 'debit', 199, 'succeeded', '2026-07-01T08:01:00', 1)",
            (f"v3-pay-{index}", order_id),
        )
    elif business_type == "unrecognized_charge":
        connection.execute(
            "INSERT INTO payments VALUES (?, ?, 'debit', 199, 'succeeded', '2026-07-01T08:01:00', 1)",
            (f"v3-pay-{index}", order_id),
        )
        connection.execute(
            "INSERT INTO charge_dispute_records VALUES (?, ?, 'unrecognized', ?, '用户否认购买', '2026-07-02T08:00:00', 1)",
            (f"v3-claim-{index}", order_id, f"v3-pay-{index}"),
        )
    elif business_type == "order_fee_dispute":
        connection.execute(
            "INSERT INTO order_fee_records VALUES (?, ?, 'charged', 'shipping', 10, 20, '2026-07-01T08:00:00', 1)",
            (f"v3-fee-{index}", order_id),
        )
    elif business_type == "fulfillment_progress":
        return
    elif business_type == "delivered_not_received":
        connection.execute(
            "INSERT INTO logistics_events VALUES (?, ?, 'delivered', '2026-07-05T17:00:00', 'carrier delivered', 1)",
            (f"v3-log-{index}", order_id),
        )
    elif business_type == "order_cancellation":
        connection.execute(
            "INSERT INTO cancellation_requests VALUES (?, ?, 'accepted', '2026-07-02T08:00:00', '2026-07-02T08:01:00', 'user_request', 1)",
            (f"v3-cancel-{index}", order_id),
        )
        connection.execute(
            "INSERT INTO logistics_events VALUES (?, ?, 'picked_up', '2026-07-02T10:00:00', 'carrier pickup', 1)",
            (f"v3-log-{index}", order_id),
        )
    elif business_type == "return_request":
        connection.execute(
            "INSERT INTO return_requests VALUES (?, ?, ?, 'requested', '2026-07-05T08:00:00', 'fit_issue', 'unopened', 1)",
            (f"v3-return-{index}", order_id, item_id),
        )
    elif business_type == "return_progress":
        connection.execute(
            "INSERT INTO return_requests VALUES (?, ?, ?, 'requested', '2026-07-05T08:00:00', 'return', 'unopened', 1)",
            (f"v3-return-{index}", order_id, item_id),
        )
        connection.execute(
            "INSERT INTO return_tracking_events VALUES (?, ?, 'in_transit', 'carrier accepted', '2026-07-07T08:00:00', 1)",
            (f"v3-rtrack-{index}", order_id),
        )
    elif business_type == "exchange_request":
        connection.execute(
            "INSERT INTO return_requests VALUES (?, ?, ?, 'requested', '2026-07-05T08:00:00', 'exchange_size', 'unopened', 1)",
            (f"v3-return-{index}", order_id, item_id),
        )
        connection.execute(
            "INSERT INTO exchange_options VALUES (?, ?, 'available', 'sku-white-10', 0, '2026-07-06T08:00:00', 1)",
            (f"v3-exchange-{index}", order_id),
        )
        connection.execute(
            "INSERT INTO inventory_records VALUES (?, ?, 'in_stock', 'sku-white-10', 8, NULL, '2026-07-06T08:00:00', 1)",
            (f"v3-inv-{index}", order_id),
        )
    elif business_type in {"received_item_mismatch", "missing_item"}:
        sku = "sku-black-9" if business_type == "received_item_mismatch" else "sku-white-9"
        quantity = 1
        connection.execute(
            "INSERT INTO warehouse_pack_records VALUES (?, ?, ?, ?, '2026-07-02T08:00:00', 'v3-station', 1)",
            (f"v3-pack-{index}", order_id, sku, quantity),
        )
    elif business_type == "item_condition_issue":
        connection.execute(
            "INSERT INTO claim_attachments VALUES (?, ?, 'condition_photo', ?, 1024, '商品污渍照片', '2026-07-05T08:00:00', 1)",
            (f"v3-attach-{index}", order_id, f"evidence://v3/{index}/condition"),
        )
    else:
        _seed_status_record(connection, index, order_id, business_type)


def _seed_status_record(
    connection: sqlite3.Connection, index: int, order_id: str, business_type: str
) -> None:
    specs = {
        "order_management": (
            "order_change_options",
            "change_option_id",
            "allowed",
            ["change_delivery_time", "delivery time can change"],
        ),
        "product_information": (
            "product_catalog_records",
            "product_record_id",
            "found",
            [json.dumps({"waterproof": True}, ensure_ascii=False)],
        ),
        "inventory_availability": (
            "inventory_records",
            "inventory_id",
            "out_of_stock",
            ["sku-v3", 0, "2026-07-20T08:00:00"],
        ),
        "price_adjustment": ("price_records", "price_record_id", "eligible", [199, 179, 175]),
        "promotion_support": (
            "promotion_records",
            "promotion_id",
            "invalid",
            ["V3CODE", "2026-07-20T08:00:00", "system invalid"],
        ),
        "shipping_options": (
            "shipping_option_records",
            "shipping_option_id",
            "available",
            ["international-standard", 30, 7, "GLOBAL"],
        ),
        "membership_support": (
            "membership_records",
            "membership_id",
            "credit_missing",
            ["gold", 0, json.dumps({"expected_credit": 40}, ensure_ascii=False)],
        ),
        "checkout_issue": (
            "checkout_events",
            "checkout_event_id",
            "service_error",
            ["checkout service 500"],
        ),
        "cart_issue": (
            "cart_events",
            "cart_event_id",
            "state_conflict",
            ["add item state conflict"],
        ),
        "search_issue": (
            "search_events",
            "search_event_id",
            "index_stale",
            ["boots", "irrelevant results"],
        ),
        "site_performance": (
            "site_health_events",
            "health_event_id",
            "degraded",
            [0.12, 3200, "frontend degraded"],
        ),
    }
    table, key, status, extra = specs[business_type]
    columns = {
        "order_change_options": "operation_type, detail",
        "product_catalog_records": "attributes_json",
        "inventory_records": "sku_id, available_quantity, restock_at",
        "price_records": "purchase_price, current_price, competitor_price",
        "promotion_records": "code, expires_at, detail",
        "shipping_option_records": "option_name, amount, estimated_days, region",
        "membership_records": "level, credit_balance, benefits_json",
        "checkout_events": "detail",
        "cart_events": "detail",
        "search_events": "query_text, detail",
        "site_health_events": "error_rate, p95_ms, detail",
    }[table]
    placeholders = ", ".join("?" for _ in extra)
    connection.execute(
        f"INSERT INTO {table} ({key}, order_id, status, {columns}, occurred_at, version) VALUES (?, ?, ?, {placeholders}, '2026-07-05T08:00:00', 1)",
        (f"v3-record-{index}", order_id, status, *extra),
    )
