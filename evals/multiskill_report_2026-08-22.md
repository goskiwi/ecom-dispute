# EcomDispute M4 跨 Skill 真实 LLM 评测

## 目标

M4 验证两项能力：

1. 将语义路由拆分为 `business_type` 与 `has_dispute`，避免把“退款业务”与“是否存在争议”混为一个字段。
2. 新增 `DeliveryDelaySkill`，证明 Harness、Tool Registry、Policy Agent 和 Evidence Fusion 能承载第二条独立业务链路。

## 数据与实现

- Refund：40 个案例
- Delivery Delay：20 个案例
- 合计：60 个案例，其中人工编写 33 个、规则生成 27 个
- 模型：`gpt-5.4-mini-2026-03-17`
- LLM 调用：60 次，每案一次，不选择性重跑
- 输入 Token：308,516
- 输出 Token：5,548
- 模型累计延迟：353,821 ms

物流 Skill 只允许订单、物流和政策工具，覆盖按时送达、政策宽限期、物流责任、商家未发货、不可抗力、订单/物流冲突和超时送达。

## 审计后结果

| 指标 | 结果 |
|---|---:|
| 确定性最终裁决 | 60/60 |
| 责任方 | 60/60 |
| 人工复检分流 | 60/60 |
| `business_type` | 60/60 |
| `has_dispute` | 60/60 |
| 用户 statement type 案例级通过 | 57/60 |
| 客服 statement type 案例级通过 | 58/60 |
| 用户 statement type 召回 | 95.7% |
| 客服 statement type 召回 | 96.7% |
| 对话-事实冲突 Precision | 7/10（70%） |
| 对话-事实冲突 Recall | 7/7（100%） |
| 全项通过 | 53/60（88.3%） |

分层全项结果：

| Skill / 来源 | 通过 |
|---|---:|
| Refund / 人工编写 | 18/21 |
| Refund / 规则生成 | 17/19 |
| Delivery / 人工编写 | 10/12 |
| Delivery / 规则生成 | 8/8 |

## Oracle 审计

原始口径为 43/60。人工复核后调整 10 个标签，主要原因是：

- “仍在运输”“正在联系物流”“等待商家发货”属于状态核验或处理动作，不应强制归为 `other` 承诺。
- 纯政策说明不属于客服承诺，允许 `agent_commitments=[]`。
- SLA 内正常处理中且用户未表达不满的案例应为 `has_dispute=false`。
- “订单显示已送达”应提取 `delivery_completed`，即使同一句又指出物流轨迹矛盾。

审计只重新计算原始输出，没有重跑模型。原始 JSON 与审计后 JSON 分开保存。

## 剩余 7 个失败

| 案例 | 失败表现 |
|---|---|
| `delivery_merchant_003` | “只有电子面单、一直没揽收”未识别为配送延迟 |
| `delivery_ontime_003` | 正式首轮只提取延迟，漏掉“已经送到”；校准调用曾正确输出双标签，说明存在单次波动 |
| `refund_complete_004` | 把“卡里收到 199”同时误标为未到账，产生冲突误报 |
| `refund_conflict_001` | 漏掉客服“页面显示已退款”的完成状态 |
| `refund_missing_002` | 把“会尽快处理”的未来表达误标为已经处理中，产生冲突误报 |
| `refund_missing_003` | 把“退款申请超时未处理”误标为退款处理中，漏掉申请事实 |
| `refund_pending_003` | 把“预计五天内到账”误标为已完成，产生冲突误报 |

## 结论

第二个 Skill 已证明工具边界和裁决规则可以独立演进：Refund 每案查询订单、支付、退款、售后和政策；Delivery 每案只查询订单、物流和政策。`business_type + has_dispute` 解决了正常完成案例的路由歧义，多标签合同也提高了复合句召回。

剩余主要问题已从路由和单标签限制收敛到时态识别：未来、当前与完成状态仍会混淆。下一阶段应增加结构化 `temporal_status`，而不是增加 Agent 数量。

