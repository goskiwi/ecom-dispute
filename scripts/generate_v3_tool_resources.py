from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = ROOT / "ecom_dispute" / "resources" / "tools"

TOOLS = {
    "get_order_fee_records": "查询订单运费、处理费和服务费记录。",
    "get_charge_dispute": "查询用户对扣款是否认可的争议记录。",
    "get_return_tracking": "查询退货标签、寄回、入库和验货进度。",
    "get_exchange_options": "查询换货资格、目标SKU、库存和差价状态。",
    "get_order_change_options": "查询当前订单允许修改的字段和操作状态。",
    "get_product_catalog": "查询商品目录中的材质、尺码、护理等可信属性。",
    "get_inventory": "查询SKU可售库存、补货和预订状态。",
    "get_price_records": "查询购买价、当前价、竞品价和价保计算状态。",
    "get_promotion_records": "查询优惠券、活动规则和使用状态。",
    "get_shipping_options": "查询配送方式、费用、覆盖地区和预计时效。",
    "get_membership_records": "查询会员等级、权益和额度状态。",
    "get_checkout_events": "查询结账尝试、支付拒绝和服务错误事件。",
    "get_cart_events": "查询购物车变更和状态冲突事件。",
    "get_search_events": "查询搜索请求、结果和索引诊断事件。",
    "get_site_health": "查询站点错误率、延迟和事故状态。",
}


def main() -> None:
    TOOLS_ROOT.mkdir(parents=True, exist_ok=True)
    for tool_id, description in TOOLS.items():
        payload = {
            "tool_id": tool_id,
            "name": description.removesuffix("。"),
            "description": description,
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
            "output_schema": {"type": "object", "additionalProperties": True},
            "timeout_ms": 3000,
            "scope_bindings": {"order_id": {"source": "case.order_id", "mode": "RUNTIME_INJECT"}},
            "executor": tool_id,
            "result_adapter": tool_id,
            "error_mapping": {},
        }
        (TOOLS_ROOT / f"{tool_id.replace('_', '-')}.yaml").write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120),
            encoding="utf-8",
        )
    print({"generated_tools": len(TOOLS)})


if __name__ == "__main__":
    main()
