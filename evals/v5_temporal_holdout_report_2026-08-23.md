# V5 Temporal Contract Holdout Run 1

## 设置

- 模型：`gpt-5.6-luna`
- 数据：16条在v5合同完成后新建的未见对话
- Oracle：首次模型调用前完成，运行后未调整
- 有效结果：16/16，API错误0

v5删除旧`temporal_status`，使用两个正交字段：

```text
fact_mode: event | state
time_relation: past | present | future | unknown
```

## 结果

| 指标 | 结果 |
|---|---:|
| 全项Exact Match | 11/16（68.75%） |
| Route Type Accuracy | 87.5% |
| Has Dispute Accuracy | 87.5% |
| 用户BusinessFact Exact Match | 87.5% |
| 用户BusinessFact Precision / Recall | 88.9% / 94.1% |
| 用户InteractionAct Precision / Recall | 100% / 100% |
| 客服InteractionAct Precision / Recall | 50% / 100% |
| 输入 / 输出Token | 92,410 / 3,280 |
| 累计模型延迟 | 212,051 ms |

## 与v4对比

| 指标 | v4 | v5 |
|---|---:|---:|
| 案例数 | 8 | 16 |
| 全项Exact Match | 2/8（25%） | 11/16（68.75%） |
| 用户BusinessFact P/R | 36.4% / 40.0% | 88.9% / 94.1% |
| 用户InteractionAct P/R | 88.9% / 100% | 100% / 100% |

两批数据不同，不能把差值解释为严格同集提升；它只能说明v5在更明确的新合同和新样本上显著减少了时间语义歧义。

## 剩余5个失败

- 单独陈述成功扣款时，模型将其视为无争议状态查询，Route或Has Dispute与Oracle不一致，但业务事实完全匹配。
- “支付后订单仍未创建”额外提取了已发生扣款事实；Oracle只标订单创建失败。
- “实际到账只有450元”被模型视为`refund_receipt + event + past`，Oracle标为`state + present`。
- 单独陈述已签收时，模型的Route/Has Dispute与Oracle边界不一致，业务事实完全匹配。
- 客服承诺撤销重复扣款时，模型同时提取当前重复扣款状态和未来撤销事件；Oracle只标未来撤销。

## 结论

破坏性拆分`fact_mode`和`time_relation`解决了旧`current/completed`混合语义的主要问题。剩余错误更多来自多事实完整标注和“无异常状态陈述”的Route/Has Dispute定义，而非兼容遗留。
