from ..contracts import EvidenceKind
from .base import DecisionOutcome, DecisionStrategy, ResolvedRoute, SkillRegistry
from .compliance import (
    BusinessStatementCheckStrategy,
    EscalationRequirementCheckStrategy,
    PromiseGroundingCheckStrategy,
)
from .fulfillment import (
    DeliveredNotReceivedStrategy,
    FulfillmentProgressStrategy,
    OrderCancellationStrategy,
)
from .funds import (
    DuplicateChargeStrategy,
    OrderFeeDisputeStrategy,
    PaymentCapturedOrderFailedStrategy,
    RefundAmountMismatchStrategy,
    RefundProgressStrategy,
    UnrecognizedChargeStrategy,
)
from .item_after_sales import (
    ItemConditionIssueStrategy,
    MissingItemStrategy,
    ReceivedItemMismatchStrategy,
    ReturnRequestStrategy,
)
from .support_strategies import status_strategy


def _status_strategies() -> dict[str, DecisionStrategy]:
    return {
        "return_progress": status_strategy(
            EvidenceKind.RETURN_TRACKING,
            "补充退货物流或入库证据后复检",
            requested=("none", "return_requested", "等待生成退货标签", False),
            label_created=("none", "return_label_created", "向用户提供退货标签", False),
            in_transit=("none", "return_in_transit", "继续跟踪退货物流", False),
            received=("warehouse", "return_received", "安排仓库验货", False),
            inspected=("none", "return_inspected", "进入后续退款或换货流程", False),
            closed=("none", "return_closed", "向用户提供退货闭环记录", False),
        ),
        "exchange_request": status_strategy(
            EvidenceKind.EXCHANGE_REQUEST,
            "补充换货资格与库存证据后复检",
            available=("none", "exchange_available", "生成换货方案", False),
            unavailable=("none", "exchange_inventory_unavailable", "提供退款或到货提醒", False),
            price_difference=("user", "exchange_price_difference", "确认差价后生成换货方案", True),
            created=("none", "exchange_created", "向用户提供换货申请记录", False),
        ),
        "order_management": status_strategy(
            EvidenceKind.ORDER_CHANGE_OPTION,
            "补充订单当前状态与可修改项后复检",
            allowed=("none", "order_change_allowed", "生成订单修改ActionPlan", False),
            blocked=("none", "order_change_blocked", "说明不可修改原因和替代方案", False),
            updated=("none", "order_change_completed", "向用户提供更新后的订单信息", False),
            conflict=("undetermined", "order_details_conflict", "核对订单版本后人工复检", True),
        ),
        "product_information": status_strategy(
            EvidenceKind.PRODUCT_CATALOG,
            "未查询到商品目录证据",
            found=("none", "product_information_found", "仅依据目录回答商品属性", False),
            not_found=("none", "product_information_missing", "告知暂缺可靠商品信息", False),
        ),
        "inventory_availability": status_strategy(
            EvidenceKind.INVENTORY,
            "未查询到库存证据",
            in_stock=("none", "inventory_available", "向用户提供可售库存", False),
            out_of_stock=("none", "inventory_unavailable", "提供补货时间或到货提醒", False),
            backorder=("none", "inventory_backorder_available", "生成预订方案", False),
        ),
        "price_adjustment": status_strategy(
            EvidenceKind.PRICE,
            "补充订单价格、当前价格和价保政策后复检",
            eligible=("platform", "price_adjustment_eligible", "生成价保补差方案", False),
            ineligible=("none", "price_adjustment_ineligible", "说明不满足价保条件的规则", False),
            adjusted=("none", "price_adjustment_completed", "提供价格调整记录", False),
            mismatch=("platform", "price_record_conflict", "核对价格版本后人工复检", True),
        ),
        "promotion_support": status_strategy(
            EvidenceKind.PROMOTION,
            "补充优惠券和活动规则后复检",
            valid=("none", "promotion_valid", "说明使用门槛和适用范围", False),
            expired=("none", "promotion_expired", "说明过期规则和替代活动", False),
            invalid=("platform", "promotion_invalid", "生成优惠券修复或补发方案", True),
            reissued=("none", "promotion_reissued", "提供新优惠券记录", False),
        ),
        "shipping_options": status_strategy(
            EvidenceKind.SHIPPING_OPTION,
            "未查询到配送报价与覆盖范围",
            available=("none", "shipping_option_available", "展示配送方式、费用和时效", False),
            unavailable=("none", "shipping_option_unavailable", "说明地区或商品限制", False),
        ),
        "membership_support": status_strategy(
            EvidenceKind.MEMBERSHIP,
            "补充会员账户与权益记录后复检",
            active=("none", "membership_active", "展示会员等级和有效权益", False),
            inactive=("none", "membership_inactive", "说明会员状态和恢复方式", False),
            credit_missing=(
                "platform",
                "membership_credit_missing",
                "核对并补记会员权益额度",
                True,
            ),
        ),
        "checkout_issue": status_strategy(
            EvidenceKind.CHECKOUT_EVENT,
            "补充结账尝试和支付授权证据后复检",
            recovered=("none", "checkout_recovered", "确认结账链路恢复", False),
            payment_declined=(
                "payment_channel",
                "checkout_payment_declined",
                "说明拒绝原因并提供替代付款方式",
                False,
            ),
            service_error=("platform", "checkout_service_error", "关联站点事故并转技术排查", True),
        ),
        "cart_issue": status_strategy(
            EvidenceKind.CART_EVENT,
            "补充购物车事件后复检",
            recovered=("none", "cart_recovered", "确认购物车状态恢复", False),
            item_unavailable=("none", "cart_item_unavailable", "转入库存查询", False),
            state_conflict=(
                "platform",
                "cart_state_conflict",
                "修复购物车状态并保留诊断事件",
                True,
            ),
        ),
        "search_issue": status_strategy(
            EvidenceKind.SEARCH_EVENT,
            "补充搜索请求与索引状态后复检",
            healthy=("none", "search_healthy", "说明搜索条件和可用结果", False),
            index_stale=("platform", "search_index_stale", "触发索引修复并关联技术事件", True),
            no_results=("none", "search_no_results", "提供筛选建议或库存状态", False),
        ),
        "site_performance": status_strategy(
            EvidenceKind.SITE_HEALTH,
            "补充站点健康与前端性能证据后复检",
            healthy=("none", "site_healthy", "提供客户端排查建议", False),
            degraded=("platform", "site_degraded", "关联降级事件并通知用户", True),
            outage=("platform", "site_outage", "关联事故并提供恢复进度", True),
        ),
    }


def default_strategies() -> dict[str, DecisionStrategy]:
    strategies: dict[str, DecisionStrategy] = {
        "refund_progress": RefundProgressStrategy(),
        "refund_amount_mismatch": RefundAmountMismatchStrategy(),
        "duplicate_charge": DuplicateChargeStrategy(),
        "payment_captured_order_failed": PaymentCapturedOrderFailedStrategy(),
        "unrecognized_charge": UnrecognizedChargeStrategy(),
        "order_fee_dispute": OrderFeeDisputeStrategy(),
        "fulfillment_progress": FulfillmentProgressStrategy(),
        "delivered_not_received": DeliveredNotReceivedStrategy(),
        "order_cancellation": OrderCancellationStrategy(),
        "return_request": ReturnRequestStrategy(),
        "received_item_mismatch": ReceivedItemMismatchStrategy(),
        "missing_item": MissingItemStrategy(),
        "item_condition_issue": ItemConditionIssueStrategy(),
        "business_statement_check": BusinessStatementCheckStrategy(),
        "promise_grounding_check": PromiseGroundingCheckStrategy(),
        "escalation_requirement_check": EscalationRequirementCheckStrategy(),
    }
    strategies.update(_status_strategies())
    return strategies


__all__ = [
    "DecisionOutcome",
    "DecisionStrategy",
    "ResolvedRoute",
    "SkillRegistry",
    "default_strategies",
]
