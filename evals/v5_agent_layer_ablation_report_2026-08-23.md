# V5 Agent Layer Ablation

## 设置

- 模型：`gpt-5.6-luna`
- ConversationAgent每个Case只调用一次，同一输出共享给三条链路
- Core：固定核心工具 + Strategy
- Gap：Core + EvidenceGapAgent
- Full：Gap + ReviewAgent

## 结果

### 退款金额案例

| 模式 | Decision | Evidence | Finding | 增量Input | 增量Output | 增量延迟 |
|---|---|---:|---:|---:|---:|---:|
| Core | refund_amount_incorrect | 7 | 12 | 0 | 0 | 0ms |
| Gap | refund_amount_incorrect | 8 | 13 | 4,680 | 169 | 9,820ms |
| Full | refund_amount_incorrect | 8 | 13 | 4,680 | 179 | 20,933ms |

EvidenceGapAgent补充了一条支付网关空查询Evidence，但没有改变裁决、责任方或复检。它的收益是证明长尾系统已经查询且无记录，不是准确率提升。

### 退款/支付冲突案例

| 模式 | Decision | Evidence | Finding | 增量Input | 增量Output | 增量延迟 |
|---|---|---:|---:|---:|---:|---:|
| Core | refund_record_conflict | 7 | 17 | 0 | 0 | 0ms |
| Gap | refund_record_conflict | 7 | 17 | 0 | 0 | 0ms |
| Full | refund_record_conflict | 7 | 18 | 4,823 | 463 | 17,124ms |

该Route没有Lazy Tool，因此Gap层不调用模型。ReviewAgent不修改确定性裁决，新增一条引用真实Evidence的复检Finding和结构化人审问题。

## 决策

- EvidenceGapAgent继续只允许在声明Lazy Tool的少数Route运行，不扩展到所有Case。
- ReviewAgent继续只在`review_required=true`时运行。
- 不把两个Agent描述为提高裁决准确率；其价值分别是长尾证据完整性和人工复检材料。
- 后续如果更大样本仍只增加空查询Evidence，应继续收紧Gap触发条件。
