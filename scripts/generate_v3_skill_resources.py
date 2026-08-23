from __future__ import annotations

import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "ecom_dispute" / "resources" / "skills"


def route(
    route_id: str,
    name: str,
    tools: list[str],
    required: list[str],
    decisions: list[str],
    description: str,
    positive: str,
    negative: str,
    *,
    optional: list[str] | None = None,
    lazy: list[str] | None = None,
) -> dict:
    business_type = route_id.replace("-", "_")
    return {
        "route_id": route_id,
        "name": name,
        "report_type": business_type,
        "match": {
            "description": description,
            "business_types": [business_type],
            "positive_examples": [positive],
            "negative_examples": [negative],
        },
        "start_stage": "ANALYZE",
        "core_tools": tools,
        "lazy_tools": lazy or [],
        "required_evidence": ["conversation", *required],
        "optional_evidence": optional or [],
        "allowed_decisions": [*decisions, "manual_review"],
        "decision_strategy": business_type,
        "stages": {
            "ANALYZE": {
                "mode": "agent",
                "objective": f"提取{name}的用户主张、客服行为和关键边界",
                "instruction_file": "stages/analyze.md",
                "default_next": "VERIFY",
            },
            "VERIFY": {
                "mode": "deterministic",
                "objective": f"查询{name}所需业务证据",
                "tools": tools,
                "default_next": "DECIDE",
            },
            "DECIDE": {
                "mode": "deterministic",
                "objective": f"依据证据和政策执行{name}确定性策略",
                "default_next": "FUSE_AND_REVIEW",
            },
            "FUSE_AND_REVIEW": {
                "mode": "deterministic",
                "objective": "合并证据冲突并创建必要的人工复检任务",
            },
        },
    }


SKILLS = {
    "funds-dispute": {
        "name": "资金争议",
        "description": "核验退款、支付、扣款和订单费用证据，不把客服陈述当成资金事实。",
        "tools": [
            "get_order",
            "get_payment_records",
            "get_refund_records",
            "get_after_sales_case",
            "get_payment_gateway_events",
            "get_order_fee_records",
            "read_policy",
            "get_charge_dispute",
        ],
        "routes": [
            route(
                "refund-progress",
                "退款进度与到账",
                [
                    "get_order",
                    "get_payment_records",
                    "get_refund_records",
                    "get_after_sales_case",
                    "read_policy",
                ],
                ["order", "payment", "after_sales", "policy"],
                [
                    "refund_not_initiated_overdue",
                    "refund_pending_within_sla",
                    "refund_processing_within_sla",
                    "refund_arrival_overdue",
                    "refund_completed",
                    "refund_record_conflict",
                ],
                "退款已经存在或应存在后的进度、完成和到账核验。",
                "退货已批准但退款还没发起",
                "我现在想申请退货",
            ),
            route(
                "refund-amount-mismatch",
                "退款金额不符",
                ["get_order", "get_payment_records", "get_refund_records", "read_policy"],
                ["order", "payment", "refund", "policy"],
                [
                    "refund_amount_correct",
                    "refund_amount_incorrect",
                    "refund_credit_amount_mismatch",
                ],
                "应退金额与退款记录或实际到账金额不一致。",
                "应该退100元但只到账80元",
                "退款仍在正常处理中",
            ),
            route(
                "duplicate-charge",
                "重复扣款",
                ["get_order", "get_payment_records", "get_refund_records", "read_policy"],
                ["order", "payment", "policy"],
                [
                    "duplicate_charge_confirmed",
                    "duplicate_charge_pending_authorization",
                    "duplicate_charge_not_found",
                ],
                "同一有效订单出现多笔重复扣款。",
                "同一订单银行卡扣了两次",
                "我不认识这笔唯一扣款",
            ),
            route(
                "payment-captured-order-failed",
                "已扣款但订单失败",
                ["get_order", "get_payment_records", "get_refund_records", "read_policy"],
                ["order", "payment", "policy"],
                [
                    "captured_order_failed_unreversed",
                    "captured_order_failed_reversed",
                    "payment_order_state_conflict",
                ],
                "支付已成功但没有有效订单或订单失败。",
                "钱扣了但订单创建失败",
                "订单正常只是物流慢",
            ),
            route(
                "unrecognized-charge",
                "陌生扣款",
                [
                    "get_order",
                    "get_payment_records",
                    "get_payment_gateway_events",
                    "get_charge_dispute",
                    "read_policy",
                ],
                ["order", "payment", "charge_claim", "policy"],
                [
                    "unrecognized_charge_not_found",
                    "charge_recognized",
                    "unrecognized_charge_confirmed",
                ],
                "用户否认与扣款对应的购买或授权关系。",
                "我从未买过这件商品却被扣款",
                "同一订单扣了两次",
            ),
            route(
                "order-fee-dispute",
                "订单费用争议",
                ["get_order", "get_payment_records", "get_order_fee_records", "read_policy"],
                ["order", "order_fee", "policy"],
                ["order_fee_correct", "order_fee_incorrect"],
                "已收取运费、处理费或服务费与订单或政策不一致。",
                "订单多收了处理费",
                "下单前咨询有哪些配送报价",
            ),
        ],
    },
    "fulfillment-service": {
        "name": "履约服务",
        "description": "重建从订单待发货到送达的履约时间线，并核验取消申请。",
        "tools": [
            "get_order",
            "get_logistics_events",
            "get_delivery_proof",
            "get_delivery_address",
            "get_cancellation_request",
            "get_refund_records",
            "read_policy",
        ],
        "routes": [
            route(
                "fulfillment-progress",
                "发货与配送进度",
                ["get_order", "get_logistics_events", "read_policy"],
                ["order", "policy"],
                [
                    "fulfillment_event_conflict",
                    "fulfillment_completed_late",
                    "fulfillment_completed_on_time",
                    "fulfillment_force_majeure",
                    "fulfillment_delayed_carrier",
                    "fulfillment_delayed_merchant",
                    "fulfillment_within_sla",
                ],
                "核验未发货、运输、延迟、丢失和送达进度；商家未发货是裁决结果。",
                "下单三周仍未收到包裹",
                "物流显示送达但我没收到",
                optional=["logistics"],
            ),
            route(
                "delivered-not-received",
                "显示送达但未收到",
                [
                    "get_order",
                    "get_logistics_events",
                    "get_delivery_proof",
                    "get_delivery_address",
                    "read_policy",
                ],
                ["order", "policy"],
                [
                    "delivery_proof_missing",
                    "delivery_receipt_disputed",
                    "delivery_not_marked_delivered",
                ],
                "系统或物流显示送达，但用户明确否认收到。",
                "物流显示签收但家里没有",
                "包裹仍在运输中",
            ),
            route(
                "order-cancellation",
                "订单取消与关联退款",
                [
                    "get_order",
                    "get_logistics_events",
                    "get_cancellation_request",
                    "get_refund_records",
                    "read_policy",
                ],
                ["order", "cancellation_request", "policy"],
                [
                    "cancel_before_pickup_but_shipped",
                    "cancel_after_pickup",
                    "cancellation_refund_missing",
                    "cancellation_completed",
                ],
                "取消申请、揽收先后关系、取消结果及关联退款。",
                "取消申请后商家仍然发货",
                "只是修改配送时间",
            ),
        ],
    },
    "item-after-sales": {
        "name": "商品售后",
        "description": "处理退货、换货、商品不符、少件和商品状况问题。",
        "tools": [
            "get_order",
            "get_order_items",
            "get_return_request",
            "get_return_tracking",
            "get_exchange_options",
            "get_inventory",
            "get_warehouse_pack_record",
            "get_claim_attachments",
            "get_logistics_events",
            "get_refund_records",
            "read_policy",
        ],
        "routes": [
            route(
                "return-request",
                "退货申请与资格",
                ["get_order", "get_order_items", "get_return_request", "read_policy"],
                ["order", "order_item", "policy"],
                [
                    "return_eligible",
                    "return_window_expired",
                    "return_category_excluded",
                    "return_condition_ineligible",
                    "return_condition_unknown",
                ],
                "普通退货、买错、不合身、不喜欢及退货资格。",
                "自己选错尺码想退货",
                "退货已寄回但仓库没入库",
                optional=["return_request"],
            ),
            route(
                "return-progress",
                "退货处理与入库进度",
                [
                    "get_order",
                    "get_return_request",
                    "get_return_tracking",
                    "get_refund_records",
                    "read_policy",
                ],
                ["return_request", "return_tracking"],
                [
                    "return_requested",
                    "return_label_created",
                    "return_in_transit",
                    "return_received",
                    "return_inspected",
                    "return_closed",
                ],
                "已提交退货后的标签、寄回、仓库入库、验货和闭环状态。",
                "退货寄出一周仓库还没收到",
                "这个商品还能退吗",
                optional=["refund", "policy"],
            ),
            route(
                "exchange-request",
                "换货申请",
                [
                    "get_order",
                    "get_order_items",
                    "get_return_request",
                    "get_exchange_options",
                    "get_inventory",
                    "read_policy",
                ],
                ["order", "order_item", "exchange_request", "inventory", "policy"],
                [
                    "exchange_available",
                    "exchange_inventory_unavailable",
                    "exchange_price_difference",
                    "exchange_created",
                ],
                "换颜色、尺码或商品，需要库存、差价和资格证据。",
                "想把9码换成10码",
                "只想退款不换货",
            ),
            route(
                "received-item-mismatch",
                "实收商品与订单不符",
                [
                    "get_order",
                    "get_order_items",
                    "get_warehouse_pack_record",
                    "get_claim_attachments",
                    "read_policy",
                ],
                ["order", "order_item", "warehouse_pack", "policy"],
                ["received_item_mismatch_confirmed", "received_item_mismatch_unverified"],
                "必须明确比较下单与实收SKU、颜色、尺码、型号。",
                "下单白色实际收到黑色",
                "颜色不喜欢但没有说商家错发",
                optional=["claim_attachment"],
            ),
            route(
                "missing-item",
                "少件",
                [
                    "get_order",
                    "get_order_items",
                    "get_warehouse_pack_record",
                    "get_claim_attachments",
                    "read_policy",
                ],
                ["order", "order_item", "warehouse_pack", "policy"],
                ["missing_item_warehouse_shortage", "missing_item_not_verified"],
                "实际收到数量少于订单数量。",
                "订单两件只收到一件",
                "整单尚未送达",
            ),
            route(
                "item-condition-issue",
                "商品状况问题",
                [
                    "get_order",
                    "get_order_items",
                    "get_warehouse_pack_record",
                    "get_claim_attachments",
                    "get_logistics_events",
                    "read_policy",
                ],
                ["order", "order_item", "policy"],
                [
                    "item_condition_evidence_collected",
                    "item_condition_attachment_missing",
                    "item_condition_evidence_insufficient",
                ],
                "商品破损、污渍、瑕疵和质量缺陷。",
                "收到的衬衫有污渍",
                "实收商品颜色与订单不符",
                optional=["warehouse_pack", "claim_attachment", "logistics"],
            ),
        ],
    },
    "order-operations": {
        "name": "订单操作",
        "description": "核验和规划现有订单的信息修改，不在VERIFY阶段执行写操作。",
        "tools": ["get_order", "get_order_items", "get_order_change_options", "read_policy"],
        "routes": [
            route(
                "order-management",
                "订单信息与修改",
                ["get_order", "get_order_items", "get_order_change_options", "read_policy"],
                ["order", "order_change_option", "policy"],
                [
                    "order_change_allowed",
                    "order_change_blocked",
                    "order_change_completed",
                    "order_details_conflict",
                ],
                "核验或修改数量、地址、付款方式、配送等级/时间和订单商品。",
                "把配送时间改到晚上",
                "包裹为什么还没到",
            )
        ],
    },
    "commerce-support": {
        "name": "电商咨询",
        "description": "只依据商品、库存、价格、促销、配送和会员记录回答。",
        "tools": [
            "get_product_catalog",
            "get_inventory",
            "get_price_records",
            "get_promotion_records",
            "get_shipping_options",
            "get_membership_records",
            "get_order",
            "read_policy",
        ],
        "routes": [
            route(
                "product-information",
                "商品信息",
                ["get_product_catalog"],
                ["product_catalog"],
                ["product_information_found", "product_information_missing"],
                "商品材质、尺码、防水、护理和目录属性。",
                "这双靴子防水吗",
                "这件商品什么时候补货",
            ),
            route(
                "inventory-availability",
                "库存可用性",
                ["get_inventory"],
                ["inventory"],
                ["inventory_available", "inventory_unavailable", "inventory_backorder_available"],
                "缺货、补货时间、到货提醒和预订能力。",
                "这条牛仔裤什么时候补货",
                "我想了解商品材质",
            ),
            route(
                "price-adjustment",
                "价格调整",
                ["get_order", "get_price_records", "read_policy"],
                ["price", "policy"],
                [
                    "price_adjustment_eligible",
                    "price_adjustment_ineligible",
                    "price_adjustment_completed",
                    "price_record_conflict",
                ],
                "价保、竞品价格匹配和购买后降价。",
                "昨天买完今天降价能补差吗",
                "退款金额少了",
            ),
            route(
                "promotion-support",
                "优惠促销支持",
                ["get_promotion_records", "get_membership_records", "read_policy"],
                ["promotion", "policy"],
                ["promotion_valid", "promotion_expired", "promotion_invalid", "promotion_reissued"],
                "优惠券无效、过期、门槛、限制和补发资格。",
                "五天前的优惠码显示无效",
                "商品现在是什么价格",
            ),
            route(
                "shipping-options",
                "配送方案咨询",
                ["get_shipping_options", "get_membership_records"],
                ["shipping_option"],
                ["shipping_option_available", "shipping_option_unavailable"],
                "下单前配送方式、报价、国际配送和预计时效。",
                "会员是否包含国际配送",
                "已经支付的运费被多收",
            ),
            route(
                "membership-support",
                "会员权益",
                ["get_membership_records", "read_policy"],
                ["membership"],
                ["membership_active", "membership_inactive", "membership_credit_missing"],
                "会员等级、权益、积分额度和服务状态。",
                "我的会员额度少了40元",
                "忘记了账户密码",
            ),
        ],
    },
    "site-reliability": {
        "name": "站点可靠性",
        "description": "根据前端、结账、购物车、搜索和站点健康事件诊断电商网站故障。",
        "tools": ["get_checkout_events", "get_cart_events", "get_search_events", "get_site_health"],
        "routes": [
            route(
                "checkout-issue",
                "结账故障",
                ["get_checkout_events", "get_site_health"],
                ["checkout_event"],
                ["checkout_recovered", "checkout_payment_declined", "checkout_service_error"],
                "未成功扣款前的银行卡拒绝、结账失败和订单无法创建。",
                "信用卡在结账时一直被拒绝",
                "已经扣款但订单失败",
                optional=["site_health"],
            ),
            route(
                "cart-issue",
                "购物车故障",
                ["get_cart_events", "get_site_health"],
                ["cart_event"],
                ["cart_recovered", "cart_item_unavailable", "cart_state_conflict"],
                "商品无法加入、移除或购物车状态异常。",
                "商品无法加入购物车",
                "商品只是没有库存",
                optional=["site_health"],
            ),
            route(
                "search-issue",
                "搜索故障",
                ["get_search_events", "get_site_health"],
                ["search_event"],
                ["search_healthy", "search_index_stale", "search_no_results"],
                "搜索结果无关、缺失或索引异常。",
                "搜索鞋子却出现不相关商品",
                "商品明确缺货",
                optional=["site_health"],
            ),
            route(
                "site-performance",
                "站点性能故障",
                ["get_site_health"],
                ["site_health"],
                ["site_healthy", "site_degraded", "site_outage"],
                "页面缓慢、错误率、可用性和事故状态。",
                "网站今天非常慢",
                "只有我的优惠券无效",
            ),
        ],
    },
    "service-compliance": {
        "name": "客服合规",
        "description": "独立核验客服陈述、承诺和必要升级，不覆盖主业务责任。",
        "tools": ["read_policy"],
        "routes": [
            route(
                "business-statement-check",
                "业务陈述核验",
                ["read_policy"],
                ["policy"],
                ["business_statement_conflict", "business_statement_verified"],
                "核验客服业务陈述是否与系统事实一致。",
                "客服说已退款但系统无记录",
                "用户自己询问退款状态",
            ),
            route(
                "promise-grounding-check",
                "承诺依据核验",
                ["read_policy"],
                ["policy"],
                ["promise_unsupported", "promise_grounded"],
                "核验客服结果承诺是否有事实与政策依据。",
                "证据不足却承诺一定退款",
                "只说明正在查询",
            ),
            route(
                "escalation-requirement-check",
                "必要升级核验",
                ["read_policy"],
                ["policy"],
                [
                    "escalation_not_required",
                    "required_escalation_present",
                    "required_escalation_missing",
                ],
                "核验需要复检时是否完成明确升级。",
                "冲突案件没有转人工",
                "无冲突且无需升级",
            ),
        ],
    },
}


def dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )


def main() -> None:
    if SKILLS_ROOT.is_dir():
        shutil.rmtree(SKILLS_ROOT)
    for skill_id, spec in SKILLS.items():
        root = SKILLS_ROOT / skill_id
        routes = spec["routes"]
        dump(
            root / "skill.yaml",
            {
                "skill_id": skill_id,
                "name": spec["name"],
                "entry": "SKILL.md",
                "allowed_tools": spec["tools"],
                "routes": [
                    {"route_id": item["route_id"], "file": f"routes/{item['route_id']}.yaml"}
                    for item in routes
                ],
                "limits": {
                    "max_model_turns": 8,
                    "max_tool_calls": 12,
                    "max_loaded_lazy_tools": 3,
                    "max_total_recovery_actions": 4,
                },
            },
        )
        (root / "SKILL.md").write_text(
            f"---\nname: {skill_id}\ndescription: {spec['description']}\n---\n\n"
            f"# {spec['name']}\n\n{spec['description']}\n\n"
            "所有业务结论必须引用当前Case的Evidence ID；对话主张不能替代系统事实。\n",
            encoding="utf-8",
        )
        stage = root / "stages" / "analyze.md"
        stage.parent.mkdir(parents=True, exist_ok=True)
        stage.write_text(
            "# ANALYZE\n\n只提取对话中有原文依据的用户诉求、业务事实和客服行为。"
            "不得补写对话没有出现的下单值、实收值、金额、状态或责任。\n",
            encoding="utf-8",
        )
        for item in routes:
            dump(root / "routes" / f"{item['route_id']}.yaml", item)
    print({skill: len(spec["routes"]) for skill, spec in SKILLS.items()})


if __name__ == "__main__":
    main()
