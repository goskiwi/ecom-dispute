# V3失败与负向证据矩阵报告

## 目标

验证V3在证据缺失、工具瞬时错误、跨源冲突和动作前置条件失败时关闭自动路径并进入人工复检，而不是用默认值继续裁决。

## 必需Evidence缺失矩阵

| 指标 | 结果 |
|---|---:|
| 业务Route | 26 |
| 固定缺失证据案例 | 26 |
| `manual_review` | 26/26 |
| `responsible_party=undetermined` | 26/26 |
| `review_required=true` | 26/26 |
| 缺失Evidence准确列出 | 26/26 |
| 意外ActionPlan | 0 |

矩阵覆盖21类缺失Evidence，包括支付、退款、售后、取消、退货追踪、订单商品、仓库、费用、陌生扣款声明、库存、价格、促销、会员、订单修改选项和站点技术事件。仅依赖订单与政策的Route通过不存在的地区政策验证缺失路径。

## 工具瞬时失败

Tool Registry新增结构化`transient_error`：

- `TimeoutError` → `TOOL_TIMEOUT`；
- `ConnectionError` → `TOOL_CONNECTION_ERROR`。

错误结果不写入成功缓存，CoreEvidenceExecutor将工具状态记录到Trace；必需Evidence未形成时，Strategy只能输出`manual_review`。测试覆盖购物车核心工具的超时与连接失败，两条均未导致Harness崩溃或错误ActionPlan。

## 冲突验证

- 退款系统成功但支付无匹配入账 → `refund_record_conflict`；
- 订单状态与物流送达事件冲突 → `fulfillment_event_conflict`；
- 客服称退款已完成但业务无记录 → `business_statement_conflict`；
- 用户称未收到货但物流存在送达事件 → 生成带Conversation和Logistics Evidence ID的冲突Finding。

## ActionPlan前置条件

`order_change_blocked`、`exchange_inventory_unavailable`、`price_adjustment_ineligible`和`promotion_expired`均不得生成ActionPlan。正向ActionPlan仍要求显式确认并携带幂等键。

## 自动化结果

- Ruff：通过；
- Pytest：81/81；
- 默认90条Decision E2E：90/90；
- 97个非manual Decision：97/97；
- 26条缺失证据矩阵：26/26安全关闭。

## 限制

- 工具瞬时错误目前只验证本地封装，未连接真实远程服务的超时、重试和熔断指标；
- 每个Route只删除一种必需Evidence，尚未覆盖多个证据同时缺失；
- 跨源冲突集中在退款、履约和客服陈述，后续还应补库存、价格和促销多版本冲突。
