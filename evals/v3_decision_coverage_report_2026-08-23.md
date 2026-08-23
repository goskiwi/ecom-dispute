# V3 97-Decision确定性覆盖报告

## 目标

验证V3的29份Route合同中，除`manual_review`兜底之外的每一个允许Decision都能通过真实Harness链路执行，而不是只在YAML中声明。

## 覆盖规模

| 项目 | 结果 |
|---|---:|
| Skill | 7 |
| Route | 29 |
| 非manual Decision | 97 |
| 主业务案例 | 90 |
| 实际观察Decision | 97 |
| 未覆盖Decision | 0 |
| 主Decision与Oracle一致 | 90/90 |
| 带ActionPlan案例 | 13 |

7个合规Decision通过每条主案例中的嵌套合规子任务覆盖，因此不需要额外伪造7条“合规主案件”。

## 按Skill的Decision数量

| Skill | Decision |
|---|---:|
| funds-dispute | 20 |
| fulfillment-service | 14 |
| item-after-sales | 22 |
| order-operations | 4 |
| commerce-support | 18 |
| site-reliability | 12 |
| service-compliance | 7 |
| 合计 | 97 |

## 校验字段

每条案例执行完整Harness并检查：

- Route与主Decision；
- responsible_party；
- review_required；
- Route必需EvidenceKind；
- Route core tools；
- 合规子任务Decision；
- ActionPlan类型、确认要求和幂等键。

## 关键分支示例

- 退款：未发起超时、SLA内等待、处理中、到账超时、完成、退款/支付记录冲突；
- 履约：订单/物流冲突、按时送达、晚到、不可抗力、承运商延迟、商家延迟、SLA内；
- 退货：申请、标签、运输、入库、验货、关闭；
- 换货：可换、缺货、存在差价、申请已创建；
- 促销：有效、过期、系统无效、已补发；
- 站点：健康、降级、宕机及购物车/结账/搜索状态分支；
- 合规：陈述冲突/一致、承诺有无依据、升级无需/已完成/缺失。

## 自动化结果

- 默认数据库空库重建后包含90条V3主案例；
- `eval --mode deterministic`：90/90；
- Pytest：81/81；
- Ruff：通过。

## 限制

- 这是构造数据与确定性合同一致性验证，不是LLM准确率。
- 每个Decision当前只有一条主证据组合，尚未覆盖同一Decision的多种缺失证据与跨源冲突。
- 真实LLM不需要把90条全部运行；下一阶段应从高风险资金、履约、退换货和站点冲突中预提交约40条全链路E2E。
