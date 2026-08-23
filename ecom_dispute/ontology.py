from __future__ import annotations

from enum import StrEnum


class BusinessRoute(StrEnum):
    REFUND_PROGRESS = "refund_progress"
    REFUND_AMOUNT_MISMATCH = "refund_amount_mismatch"
    DUPLICATE_CHARGE = "duplicate_charge"
    PAYMENT_CAPTURED_ORDER_FAILED = "payment_captured_order_failed"
    UNRECOGNIZED_CHARGE = "unrecognized_charge"
    ORDER_FEE_DISPUTE = "order_fee_dispute"
    FULFILLMENT_PROGRESS = "fulfillment_progress"
    DELIVERED_NOT_RECEIVED = "delivered_not_received"
    ORDER_CANCELLATION = "order_cancellation"
    RETURN_REQUEST = "return_request"
    RETURN_PROGRESS = "return_progress"
    EXCHANGE_REQUEST = "exchange_request"
    RECEIVED_ITEM_MISMATCH = "received_item_mismatch"
    MISSING_ITEM = "missing_item"
    ITEM_CONDITION_ISSUE = "item_condition_issue"
    ORDER_MANAGEMENT = "order_management"
    PRODUCT_INFORMATION = "product_information"
    INVENTORY_AVAILABILITY = "inventory_availability"
    PRICE_ADJUSTMENT = "price_adjustment"
    PROMOTION_SUPPORT = "promotion_support"
    SHIPPING_OPTIONS = "shipping_options"
    MEMBERSHIP_SUPPORT = "membership_support"
    CHECKOUT_ISSUE = "checkout_issue"
    CART_ISSUE = "cart_issue"
    SEARCH_ISSUE = "search_issue"
    SITE_PERFORMANCE = "site_performance"
    OTHER = "other"


class ReturnReason(StrEnum):
    BUYER_SELECTED_WRONG_VARIANT = "buyer_selected_wrong_variant"
    FIT_ISSUE = "fit_issue"
    PREFERENCE_CHANGE = "preference_change"
    NO_LONGER_NEEDED = "no_longer_needed"
    SELLER_MISMATCH_CLAIM = "seller_mismatch_claim"
    UNKNOWN = "unknown"


class OrderOperationType(StrEnum):
    VERIFY_DETAILS = "verify_details"
    CHANGE_QUANTITY = "change_quantity"
    CHANGE_ADDRESS = "change_address"
    CHANGE_PAYMENT_METHOD = "change_payment_method"
    CHANGE_SHIPPING_LEVEL = "change_shipping_level"
    CHANGE_DELIVERY_TIME = "change_delivery_time"
    ADD_ITEM = "add_item"
    REMOVE_ITEM = "remove_item"


class ItemAttribute(StrEnum):
    SKU = "sku"
    COLOR = "color"
    SIZE = "size"
    MODEL = "model"
    PRODUCT = "product"


COMPLIANCE_ROUTE_IDS = (
    "business-statement-check",
    "promise-grounding-check",
    "escalation-requirement-check",
)

BUSINESS_ROUTE_IDS = tuple(
    route.value for route in BusinessRoute if route is not BusinessRoute.OTHER
)

ROUTE_DESCRIPTIONS = {
    BusinessRoute.REFUND_PROGRESS: "退款已存在或应存在后的未发起、处理中、完成未到账和记录冲突",
    BusinessRoute.REFUND_AMOUNT_MISMATCH: "应退金额与退款记录或实际到账金额不一致",
    BusinessRoute.DUPLICATE_CHARGE: "同一有效订单出现多笔重复扣款",
    BusinessRoute.PAYMENT_CAPTURED_ORDER_FAILED: "支付成功但没有有效订单或订单失败",
    BusinessRoute.UNRECOGNIZED_CHARGE: "用户否认对应购买或授权的陌生扣款",
    BusinessRoute.ORDER_FEE_DISPUTE: "已收取运费、处理费或服务费与订单或政策不一致",
    BusinessRoute.FULFILLMENT_PROGRESS: "订单待发货、运输、延迟、丢失和正常送达进度",
    BusinessRoute.DELIVERED_NOT_RECEIVED: "系统显示送达但用户明确否认收到",
    BusinessRoute.ORDER_CANCELLATION: "取消申请、揽收先后、取消结果和关联退款",
    BusinessRoute.RETURN_REQUEST: "普通退货、买错、不合身、不喜欢及退货资格",
    BusinessRoute.RETURN_PROGRESS: "已提交退货后的标签、寄回、入库、验货和处理进度",
    BusinessRoute.EXCHANGE_REQUEST: "换颜色、尺码或商品的换货申请",
    BusinessRoute.RECEIVED_ITEM_MISMATCH: "原文明示下单与实收SKU、颜色、尺码或型号不一致",
    BusinessRoute.MISSING_ITEM: "实收数量少于订单数量",
    BusinessRoute.ITEM_CONDITION_ISSUE: "商品破损、污渍、瑕疵或质量缺陷",
    BusinessRoute.ORDER_MANAGEMENT: "核验或修改现有订单的数量、地址、付款方式、配送设置和商品",
    BusinessRoute.PRODUCT_INFORMATION: "商品材质、尺码、防水、护理和目录属性咨询",
    BusinessRoute.INVENTORY_AVAILABILITY: "缺货、补货时间、到货提醒和预订能力",
    BusinessRoute.PRICE_ADJUSTMENT: "价保、竞品价格匹配和购买后降价",
    BusinessRoute.PROMOTION_SUPPORT: "优惠券无效、过期、门槛、限制和补发资格",
    BusinessRoute.SHIPPING_OPTIONS: "下单前配送方式、费用、国际配送和预计时效",
    BusinessRoute.MEMBERSHIP_SUPPORT: "会员等级、权益、积分额度和会员服务状态",
    BusinessRoute.CHECKOUT_ISSUE: "未成功扣款前的银行卡拒绝、结账失败和订单无法创建",
    BusinessRoute.CART_ISSUE: "商品无法加入、移除或购物车状态异常",
    BusinessRoute.SEARCH_ISSUE: "搜索结果无关、缺失或索引异常",
    BusinessRoute.SITE_PERFORMANCE: "页面缓慢、错误率、可用性和事故状态",
    BusinessRoute.OTHER: "账户安全、信贷延期、身份资料修改或无法归入项目能力的请求",
}
