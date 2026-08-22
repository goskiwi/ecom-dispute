# V2 Real-LLM Agent Smoke

## 设置

- 日期：2026-08-23
- 模型：`gpt-5.6-luna`
- 接口：OpenAI-compatible Responses API
- 目的：验证新的 `route_type`、EvidenceGapAgent 和 ReviewAgent 真实调用链
- 数据：已有项目案例，仅作为冒烟，不作为独立盲测准确率

## 合同迁移发现

首次4案例运行中，业务裁决、责任方和复检均正确，但旧 Conversation Schema 只能输出
`refund/delivery/other`，导致退款金额和破损商品两个新 Route 无法正确计分。

破坏性迁移到12类主 Route 的 `route_type` 后，4案例中3条通过全部检查。剩余
`delivery_conflict_001` 被模型识别为更具体的 `delivered_not_received`，而旧案例元数据仍为
宽泛的 `delivery`。因此 live Harness 随后改为使用 ConversationAgent 的 `route_type` 激活
Skill/Route；确定性测试Stub仍使用案例预置Route。

## Route驱动后的定向实测

| Case | 实际Agent | Route | Decision | Party | Review | Input Token | Output Token | 模型延迟 |
|---|---|---|---|---|---:|---:|---:|---:|
| `m6_refund_amount_001` | Conversation + EvidenceGap | `refund_amount` | `refund_amount_incorrect` | platform | false | 10,145 | 379 | 26,898 ms |
| `refund_conflict_001` | Conversation + Review | `refund` | `refund_record_conflict` | undetermined | true | 10,289 | 810 | 56,795 ms |

两条案例的Route、业务裁决、责任方和复检结果均符合预期。EvidenceGapAgent只在拥有Lazy Tool
的退款金额Route运行；ReviewAgent只在退款记录冲突需要复检时运行。

## 限制

- 这是已有案例的真实模型冒烟，不是新建holdout。
- 当前接口的多Agent串行延迟较高，复检案例累计模型延迟约57秒。
- 旧 `delivery_conflict_001` 的宽泛Route元数据不再适合作为新Route合同的路由Oracle。
- 后续独立盲测必须在首次模型调用前建立新的Route Oracle，并分别报告Conversation、Gap和Review成本。
