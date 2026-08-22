# V1 12-Route E2E Blind Run 1

## 设置

- 模型：`gpt-5.6-luna`
- 数据：12条在v1.0发布后新建的完整E2E案件，每个主Route一条
- Oracle：模型调用前固定，包含Route、Decision、Party、Review、必需Evidence、必需Tool和必需Agent
- ConversationAgent每个Case只调用一次，结果共享给live三Agent链路和core对照链路
- 有效结果：12/12，API错误0

覆盖Route：

```text
refund
refund_amount
duplicate_charge
payment_order_failure
delivery
merchant_not_shipped
delivered_not_received
cancellation_in_transit
return_eligibility
wrong_item
missing_item
damaged_item
```

## 端到端结果

| 指标 | Live三Agent | Core对照 |
|---|---:|---:|
| 全项通过 | 12/12 | 12/12 |
| Route Accuracy | 100% | 100% |
| Decision Accuracy | 100% | 100% |
| Responsible Party Accuracy | 100% | 100% |
| Review Accuracy | 100% | 100% |
| Review Precision / Recall | 100% / 100% | 100% / 100% |
| Required Evidence | 100% | 100% |
| Required Tools | 100% | 100% |
| Evidence Grounded | 100% | 100% |
| 平均Tool Calls | 4.75 | 4.42 |

## Agent调用

| Agent | 调用Case数 |
|---|---:|
| ConversationAgent | 12/12 |
| EvidenceGapAgent | 4/12 |
| ReviewAgent | 8/12 |

Live链路累计：

```text
Input Token: 128,310
Output Token: 8,897
模型累计延迟: 309,725 ms
单Case Agent延迟 P50: 22,903.5 ms
单Case Agent延迟 P95: 46,174 ms
```

相对共享Conversation输出的Core链路，Gap和Review层增加：

```text
Input Token: 58,712
Output Token: 4,557
模型延迟: 158,811 ms
平均Tool Calls: +0.33/Case
```

## 结论

本轮证明新的Conversation Route、14个Tool、12个主Route、确定性Strategy、客服合规、Gap和Review链路能够在完整业务数据上共同运行，并保持Evidence引用有效。

但Gap/Review没有提高这12条的裁决、责任或复检准确率；它们的可见收益分别是补充长尾查询Evidence和生成结构化复检Finding，代价是约5.9万输入Token和159秒累计延迟。因此不能把三Agent描述为准确率提升方案，其触发范围仍应保持在4/12和8/12，而不是全量调用。

## 限制

- 只有每个Route一条，共12条，样本量小。
- 数据为调用前构造的独立E2E集，不是生产订单。
- 100%只代表本轮12条，不代表线上准确率。
- Review材料质量目前只验证Schema、Evidence引用和触发条件，没有真实审核员主观评分。
- 后续不应在同一12条上调Oracle后重新宣传新分数。
