# E2E Blind: Live ToolQuery vs Fixed Executor

## 设置

- 模型：`gpt-5.6-luna`
- 数据：20 个新建端到端案例，Refund/Delivery 各 10 个
- 每个案例包含对话、订单、支付/退款或物流记录、事发时间、政策环境和独立 Oracle
- ConversationAgent 每案例只调用一次，其 AgentResult 同时提供给两条工具链
- Oracle 在模型调用前固定，运行后未调整

## 完整性

- 计划案例：20
- 有效案例：19
- API 错误：1（`e2e_delivery_006`，connection reset by peer）

以下指标只以 19 个有效案例为分母，不把 API 错误计为模型错误。

## 结果

| 指标 | Live ToolQuery | Fixed Executor |
|---|---:|---:|
| 全项通过 | 19/19 | 19/19 |
| 裁决准确率 | 100% | 100% |
| 责任方准确率 | 100% | 100% |
| 复检准确率 | 100% | 100% |
| 复检 Precision / Recall | 100% / 100% | 100% / 100% |
| 必需 Evidence 完整率 | 100% | 100% |
| 必需工具完整率 | 100% | 100% |
| Evidence Grounded | 100% | 100% |
| 平均工具调用 | 4.05 | 4.05 |
| 平均 ToolQuery 轮次 | 2.0 | 0 |

两条链路查询了完全相同数量的工具。Live ToolQuery 没有减少调用，也没有提高裁决、责任方、复检或 Evidence 指标。

## 增量成本

ConversationAgent 成本由两条链路共享，不计入工具链差异。Live ToolQuery 额外消耗：

- 输入 Token：209,720，平均约 11,038/案例
- 输出 Token：7,977，平均约 420/案例
- 模型累计延迟：428,983 ms，平均约 22.6 秒/案例

## 决策

当前两个 Skill 的必需工具集合很小且事前已知，LLM 工具规划没有产生收益。因此产品默认改为：

```text
ConversationAgent
→ FixedFactExecutor + PolicyResolver
→ Reducer
→ Skill Decision Strategy
→ Evidence Fusion
```

ToolQueryAgent 保留为显式 `--tool-mode agent` 对照模式，不作为默认链路。只有未来出现“工具集合大、必要查询依赖前一步结果”的具体场景，才重新评估 Agent 工具规划。

## 限制

案例为项目内后置构造数据，不代表线上准确率；有效样本为 19 个。结果证明当前固定工具策略优于 Agent 工具规划的成本收益比，不证明所有业务都不需要 ToolQuery Agent。

