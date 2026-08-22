# Semantic Schema v2 状态

## 破坏性变更

v2 删除了以下旧字段：

- `statement_types[]`
- `user_claims`
- `agent_commitments`
- `statement_type`

新输出统一为原子 `facts[]`，每项包含：

```text
speaker
quote
message_index
fact_type
polarity
temporal_status
speech_act
```

每个事实只有一个类型和一个时态。用户实际收到钱/货使用 `*_receipt`，系统退款完成或物流送达状态使用 `*_completion`；未来承诺与当前事实通过 `speech_act` 和 `temporal_status` 区分。

## 验证

`gpt-5.6-luna` 严格 Schema 探针成功，能够把“预计今晚到账，请再等等”拆成未来到账 promise 与等待 advice，并提供逐字 quote。完整 live 冒烟也成功：Conversation Agent 输出三个原子事实，Tool Query Agent 两轮完成订单、售后、支付、退款和政策查询，最终策略判定 `refund_record_conflict`。

第一次 30 条运行使用机械迁移 Oracle，发现 receipt/completion 标签存在领域错误，因此该结果只作为 schema validation 移入 `evals/legacy/`，不发布准确率。Oracle 已在运行后按领域定义修正；为避免看过输出后重算分数，当前没有 v2 正式 holdout 指标。

## 当前结论

v2 合同和运行代码已经生效，旧合同没有兼容解析器。下一次指标必须使用新的未见对话集，不能继续用已查看输出的 30 条集合宣称测试准确率。
