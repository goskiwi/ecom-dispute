from __future__ import annotations

import json
import sqlite3

ADDITIONAL_DECISIONS = {
    "refund_progress": [
        "refund_not_initiated_overdue",
        "refund_pending_within_sla",
        "refund_arrival_overdue",
        "refund_completed",
        "refund_record_conflict",
    ],
    "refund_amount_mismatch": ["refund_amount_correct", "refund_credit_amount_mismatch"],
    "duplicate_charge": ["duplicate_charge_pending_authorization", "duplicate_charge_not_found"],
    "payment_captured_order_failed": [
        "captured_order_failed_reversed",
        "payment_order_state_conflict",
    ],
    "unrecognized_charge": ["unrecognized_charge_not_found", "charge_recognized"],
    "order_fee_dispute": ["order_fee_correct"],
    "fulfillment_progress": [
        "fulfillment_event_conflict",
        "fulfillment_completed_late",
        "fulfillment_completed_on_time",
        "fulfillment_force_majeure",
        "fulfillment_delayed_carrier",
        "fulfillment_within_sla",
    ],
    "delivered_not_received": ["delivery_receipt_disputed", "delivery_not_marked_delivered"],
    "order_cancellation": [
        "cancel_after_pickup",
        "cancellation_refund_missing",
        "cancellation_completed",
    ],
    "return_request": [
        "return_window_expired",
        "return_category_excluded",
        "return_condition_ineligible",
        "return_condition_unknown",
    ],
    "return_progress": [
        "return_requested",
        "return_label_created",
        "return_received",
        "return_inspected",
        "return_closed",
    ],
    "exchange_request": [
        "exchange_inventory_unavailable",
        "exchange_price_difference",
        "exchange_created",
    ],
    "received_item_mismatch": ["received_item_mismatch_unverified"],
    "missing_item": ["missing_item_not_verified"],
    "item_condition_issue": [
        "item_condition_attachment_missing",
        "item_condition_evidence_insufficient",
    ],
    "order_management": [
        "order_change_blocked",
        "order_change_completed",
        "order_details_conflict",
    ],
    "product_information": ["product_information_missing"],
    "inventory_availability": ["inventory_available", "inventory_backorder_available"],
    "price_adjustment": [
        "price_adjustment_ineligible",
        "price_adjustment_completed",
        "price_record_conflict",
    ],
    "promotion_support": ["promotion_valid", "promotion_expired", "promotion_reissued"],
    "shipping_options": ["shipping_option_unavailable"],
    "membership_support": ["membership_active", "membership_inactive"],
    "checkout_issue": ["checkout_recovered", "checkout_payment_declined"],
    "cart_issue": ["cart_recovered", "cart_item_unavailable"],
    "search_issue": ["search_healthy", "search_no_results"],
    "site_performance": ["site_healthy", "site_outage"],
}


def seed_decision_matrix_v3(connection: sqlite3.Connection) -> None:
    serial = 100
    for business_type, decisions in ADDITIONAL_DECISIONS.items():
        for decision in decisions:
            serial += 1
            _seed_case(connection, serial, business_type, decision)


def _seed_case(
    connection: sqlite3.Connection,
    serial: int,
    business_type: str,
    decision: str,
) -> None:
    case_id = f"v3d-{decision}"
    order_id = f"v3d-order-{serial}"
    order_status = _order_status(decision)
    agent_text = "我会依据业务记录和政策进行核验。"
    if decision == "payment_order_state_conflict":
        agent_text = "退款已完成。"
    elif decision == "received_item_mismatch_unverified":
        agent_text = "我们会在明天补发正确商品。"
    elif decision == "refund_record_conflict":
        agent_text = "我已提交复检并转人工处理。"
    connection.execute(
        "INSERT INTO cases VALUES (?, ?, 'rule_generated', 'CN', ?, '2026-07-01T10:00:00', '2026-07-10T12:00:00', ?)",
        (
            case_id,
            order_id,
            business_type,
            json.dumps(
                [
                    {"speaker": "user", "text": f"请核验{decision}对应的业务状态。"},
                    {"speaker": "agent", "text": agent_text},
                ],
                ensure_ascii=False,
            ),
        ),
    )
    promised_at = (
        "2026-07-12T18:00:00" if decision == "fulfillment_within_sla" else "2026-07-05T18:00:00"
    )
    connection.execute(
        "INSERT INTO orders VALUES (?, ?, 'CN', ?, ?, 199.0, 'CNY', '2026-07-01T08:00:00', ?, 1)",
        (order_id, f"v3d-user-{serial}", business_type, order_status, promised_at),
    )
    _seed_evidence(connection, serial, order_id, business_type, decision)


def _order_status(decision: str) -> str:
    if decision in {"captured_order_failed_reversed"}:
        return "failed"
    if decision in {
        "fulfillment_completed_late",
        "fulfillment_completed_on_time",
        "delivery_receipt_disputed",
    }:
        return "delivered"
    return "paid"


def _seed_evidence(
    connection: sqlite3.Connection,
    serial: int,
    order_id: str,
    business_type: str,
    decision: str,
) -> None:
    if business_type == "refund_progress":
        _refund_progress(connection, serial, order_id, decision)
    elif business_type == "refund_amount_mismatch":
        _refund_amount(connection, serial, order_id, decision)
    elif business_type == "duplicate_charge":
        _duplicate(connection, serial, order_id, decision)
    elif business_type == "payment_captured_order_failed":
        _payment_order(connection, serial, order_id, decision)
    elif business_type == "unrecognized_charge":
        _charge_claim(connection, serial, order_id, decision)
    elif business_type == "order_fee_dispute":
        _fee(connection, serial, order_id, decision)
    elif business_type == "fulfillment_progress":
        _fulfillment(connection, serial, order_id, decision)
    elif business_type == "delivered_not_received":
        _delivery_receipt(connection, serial, order_id, decision)
    elif business_type == "order_cancellation":
        _cancellation(connection, serial, order_id, decision)
    elif business_type in {
        "return_request",
        "return_progress",
        "exchange_request",
        "received_item_mismatch",
        "missing_item",
        "item_condition_issue",
    }:
        _item_after_sales(connection, serial, order_id, business_type, decision)
    else:
        _status_record(connection, serial, order_id, business_type, decision)


def _payment(
    connection: sqlite3.Connection,
    serial: int,
    order_id: str,
    suffix: str,
    event_type: str,
    amount: float,
    status: str,
) -> None:
    connection.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?, ?, '2026-07-02T08:00:00', 1)",
        (f"v3d-pay-{serial}-{suffix}", order_id, event_type, amount, status),
    )


def _refund_progress(connection, serial: int, order_id: str, decision: str) -> None:
    _payment(connection, serial, order_id, "debit", "debit", 199, "succeeded")
    approved_at = (
        "2026-07-09T20:00:00" if decision == "refund_pending_within_sla" else "2026-07-01T10:00:00"
    )
    connection.execute(
        "INSERT INTO after_sales_cases VALUES (?, ?, 'approved', ?, 'return', 1)",
        (f"v3d-as-{serial}", order_id, approved_at),
    )
    if decision in {"refund_not_initiated_overdue", "refund_pending_within_sla"}:
        return
    status = "processing" if decision == "refund_arrival_overdue" else "succeeded"
    connection.execute(
        "INSERT INTO refunds VALUES (?, ?, 199, ?, '2026-07-01T12:00:00', ?, 1)",
        (
            f"v3d-ref-{serial}",
            order_id,
            status,
            "2026-07-02T12:00:00" if status == "succeeded" else None,
        ),
    )
    if decision == "refund_completed":
        _payment(connection, serial, order_id, "credit", "credit", 199, "succeeded")


def _refund_amount(connection, serial: int, order_id: str, decision: str) -> None:
    refund_amount = 199
    credit_amount = 99 if decision == "refund_credit_amount_mismatch" else 199
    connection.execute(
        "INSERT INTO refunds VALUES (?, ?, ?, 'succeeded', '2026-07-02T08:00:00', '2026-07-03T08:00:00', 1)",
        (f"v3d-ref-{serial}", order_id, refund_amount),
    )
    _payment(connection, serial, order_id, "credit", "credit", credit_amount, "succeeded")


def _duplicate(connection, serial: int, order_id: str, decision: str) -> None:
    _payment(connection, serial, order_id, "one", "debit", 199, "succeeded")
    if decision == "duplicate_charge_pending_authorization":
        _payment(connection, serial, order_id, "two", "debit", 199, "pending")


def _payment_order(connection, serial: int, order_id: str, decision: str) -> None:
    _payment(connection, serial, order_id, "debit", "debit", 199, "succeeded")
    if decision == "captured_order_failed_reversed":
        _payment(connection, serial, order_id, "reversal", "reversal", 199, "succeeded")


def _charge_claim(connection, serial: int, order_id: str, decision: str) -> None:
    _payment(connection, serial, order_id, "debit", "debit", 199, "succeeded")
    status = "not_found" if decision == "unrecognized_charge_not_found" else "recognized"
    connection.execute(
        "INSERT INTO charge_dispute_records VALUES (?, ?, ?, ?, 'charge claim', '2026-07-02T08:00:00', 1)",
        (f"v3d-claim-{serial}", order_id, status, f"v3d-pay-{serial}-debit"),
    )


def _fee(connection, serial: int, order_id: str, decision: str) -> None:
    connection.execute(
        "INSERT INTO order_fee_records VALUES (?, ?, 'charged', 'shipping', 10, 10, '2026-07-02T08:00:00', 1)",
        (f"v3d-fee-{serial}", order_id),
    )


def _logistics(connection, serial: int, order_id: str, event: str, at: str, detail: str) -> None:
    connection.execute(
        "INSERT INTO logistics_events VALUES (?, ?, ?, ?, ?, 1)",
        (f"v3d-log-{serial}-{event}", order_id, event, at, detail),
    )


def _fulfillment(connection, serial: int, order_id: str, decision: str) -> None:
    if decision == "fulfillment_event_conflict":
        _logistics(connection, serial, order_id, "delivered", "2026-07-05T12:00:00", "signed")
    elif decision in {"fulfillment_completed_late", "fulfillment_completed_on_time"}:
        at = "2026-07-08T20:00:00" if decision.endswith("late") else "2026-07-05T17:00:00"
        _logistics(connection, serial, order_id, "delivered", at, "signed")
    elif decision == "fulfillment_force_majeure":
        _logistics(connection, serial, order_id, "exception", "2026-07-06T08:00:00", "weather")
    elif decision == "fulfillment_delayed_carrier":
        _logistics(
            connection, serial, order_id, "exception", "2026-07-06T08:00:00", "carrier_sorting"
        )
    else:
        _logistics(connection, serial, order_id, "picked_up", "2026-07-04T08:00:00", "pickup")


def _delivery_receipt(connection, serial: int, order_id: str, decision: str) -> None:
    if decision == "delivery_not_marked_delivered":
        return
    _logistics(connection, serial, order_id, "delivered", "2026-07-05T12:00:00", "signed")
    connection.execute(
        "INSERT INTO delivery_proofs VALUES (?, ?, 'front-desk', 'photo', '2026-07-05T12:00:00', 'proof', 1)",
        (f"v3d-proof-{serial}", order_id),
    )


def _cancellation(connection, serial: int, order_id: str, decision: str) -> None:
    requested = (
        "2026-07-03T10:00:00" if decision == "cancel_after_pickup" else "2026-07-02T08:00:00"
    )
    connection.execute(
        "INSERT INTO cancellation_requests VALUES (?, ?, 'accepted', ?, ?, 'user_request', 1)",
        (f"v3d-cancel-{serial}", order_id, requested, requested),
    )
    if decision == "cancel_after_pickup":
        _logistics(connection, serial, order_id, "picked_up", "2026-07-02T08:00:00", "pickup")
    elif decision == "cancellation_completed":
        connection.execute(
            "INSERT INTO refunds VALUES (?, ?, 199, 'succeeded', '2026-07-03T08:00:00', '2026-07-04T08:00:00', 1)",
            (f"v3d-ref-{serial}", order_id),
        )


def _item_after_sales(
    connection, serial: int, order_id: str, business_type: str, decision: str
) -> None:
    item_id = f"v3d-item-{serial}"
    category = "personal_care" if decision == "return_category_excluded" else "general"
    quantity = 2 if business_type == "missing_item" else 1
    connection.execute(
        "INSERT INTO order_items VALUES (?, ?, 'sku-white-9', 'V3决策矩阵商品', ?, 199, ?, 1)",
        (item_id, order_id, quantity, category),
    )
    if business_type == "return_request":
        if decision == "return_condition_unknown":
            return
        requested = (
            "2026-07-20T08:00:00" if decision == "return_window_expired" else "2026-07-05T08:00:00"
        )
        condition = "used" if decision == "return_condition_ineligible" else "unopened"
        connection.execute(
            "INSERT INTO return_requests VALUES (?, ?, ?, 'requested', ?, 'return', ?, 1)",
            (f"v3d-return-{serial}", order_id, item_id, requested, condition),
        )
    elif business_type == "return_progress":
        connection.execute(
            "INSERT INTO return_requests VALUES (?, ?, ?, 'requested', '2026-07-05T08:00:00', 'return', 'unopened', 1)",
            (f"v3d-return-{serial}", order_id, item_id),
        )
        status = {
            "return_requested": "requested",
            "return_label_created": "label_created",
            "return_received": "received",
            "return_inspected": "inspected",
            "return_closed": "closed",
        }[decision]
        connection.execute(
            "INSERT INTO return_tracking_events VALUES (?, ?, ?, 'matrix event', '2026-07-06T08:00:00', 1)",
            (f"v3d-track-{serial}", order_id, status),
        )
    elif business_type == "exchange_request":
        connection.execute(
            "INSERT INTO return_requests VALUES (?, ?, ?, 'requested', '2026-07-05T08:00:00', 'exchange', 'unopened', 1)",
            (f"v3d-return-{serial}", order_id, item_id),
        )
        status = {
            "exchange_inventory_unavailable": "unavailable",
            "exchange_price_difference": "price_difference",
            "exchange_created": "created",
        }[decision]
        connection.execute(
            "INSERT INTO exchange_options VALUES (?, ?, ?, 'sku-white-10', ?, '2026-07-06T08:00:00', 1)",
            (f"v3d-exchange-{serial}", order_id, status, 20 if status == "price_difference" else 0),
        )
        inventory_status = "out_of_stock" if status == "unavailable" else "in_stock"
        connection.execute(
            "INSERT INTO inventory_records VALUES (?, ?, ?, 'sku-white-10', ?, NULL, '2026-07-06T08:00:00', 1)",
            (
                f"v3d-inventory-{serial}",
                order_id,
                inventory_status,
                0 if status == "unavailable" else 5,
            ),
        )
    elif business_type in {"received_item_mismatch", "missing_item"}:
        packed_quantity = quantity
        connection.execute(
            "INSERT INTO warehouse_pack_records VALUES (?, ?, 'sku-white-9', ?, '2026-07-02T08:00:00', 'matrix-station', 1)",
            (f"v3d-pack-{serial}", order_id, packed_quantity),
        )
    elif business_type == "item_condition_issue":
        if decision == "item_condition_attachment_missing":
            connection.execute(
                "INSERT INTO warehouse_pack_records VALUES (?, ?, 'sku-white-9', 1, '2026-07-02T08:00:00', 'matrix-station', 1)",
                (f"v3d-pack-{serial}", order_id),
            )


def _status_record(
    connection, serial: int, order_id: str, business_type: str, decision: str
) -> None:
    specs = {
        "order_change_blocked": (
            "order_change_options",
            "change_option_id",
            "blocked",
            ["change_address", "blocked"],
        ),
        "order_change_completed": (
            "order_change_options",
            "change_option_id",
            "updated",
            ["change_address", "updated"],
        ),
        "order_details_conflict": (
            "order_change_options",
            "change_option_id",
            "conflict",
            ["verify_details", "conflict"],
        ),
        "product_information_missing": (
            "product_catalog_records",
            "product_record_id",
            "not_found",
            [json.dumps({}, ensure_ascii=False)],
        ),
        "inventory_available": (
            "inventory_records",
            "inventory_id",
            "in_stock",
            ["sku-v3", 8, None],
        ),
        "inventory_backorder_available": (
            "inventory_records",
            "inventory_id",
            "backorder",
            ["sku-v3", 0, "2026-07-20T08:00:00"],
        ),
        "price_adjustment_ineligible": (
            "price_records",
            "price_record_id",
            "ineligible",
            [199, 179, 175],
        ),
        "price_adjustment_completed": (
            "price_records",
            "price_record_id",
            "adjusted",
            [199, 179, 175],
        ),
        "price_record_conflict": ("price_records", "price_record_id", "mismatch", [199, 179, 175]),
        "promotion_valid": (
            "promotion_records",
            "promotion_id",
            "valid",
            ["CODE", "2026-07-20T08:00:00", "valid"],
        ),
        "promotion_expired": (
            "promotion_records",
            "promotion_id",
            "expired",
            ["CODE", "2026-07-01T08:00:00", "expired"],
        ),
        "promotion_reissued": (
            "promotion_records",
            "promotion_id",
            "reissued",
            ["NEWCODE", "2026-07-20T08:00:00", "reissued"],
        ),
        "shipping_option_unavailable": (
            "shipping_option_records",
            "shipping_option_id",
            "unavailable",
            ["international", 0, 0, "RESTRICTED"],
        ),
        "membership_active": (
            "membership_records",
            "membership_id",
            "active",
            ["gold", 40, json.dumps({"shipping": True})],
        ),
        "membership_inactive": (
            "membership_records",
            "membership_id",
            "inactive",
            ["guest", 0, json.dumps({})],
        ),
        "checkout_recovered": ("checkout_events", "checkout_event_id", "recovered", ["recovered"]),
        "checkout_payment_declined": (
            "checkout_events",
            "checkout_event_id",
            "payment_declined",
            ["issuer decline"],
        ),
        "cart_recovered": ("cart_events", "cart_event_id", "recovered", ["recovered"]),
        "cart_item_unavailable": (
            "cart_events",
            "cart_event_id",
            "item_unavailable",
            ["out of stock"],
        ),
        "search_healthy": ("search_events", "search_event_id", "healthy", ["boots", "healthy"]),
        "search_no_results": (
            "search_events",
            "search_event_id",
            "no_results",
            ["boots", "no results"],
        ),
        "site_healthy": ("site_health_events", "health_event_id", "healthy", [0.0, 200, "healthy"]),
        "site_outage": ("site_health_events", "health_event_id", "outage", [1.0, 10000, "outage"]),
    }
    table, key, status, extra = specs[decision]
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
        (f"v3d-record-{serial}", order_id, status, *extra),
    )
