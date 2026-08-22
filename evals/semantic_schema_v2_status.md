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

第一次 30 条运行使用机械迁移 Oracle，发现 receipt/completion 标签存在领域错误，因此该结果只作为 schema validation 移入 `evals/legacy/`。随后创建全新的 30 条盲测对话并在调用前固定 Oracle，`gpt-5.6-luna` Run 1 获得 30/30 有效响应；全项 Exact Match 为 10/30，详细结果见 `semantic_holdout_schema-v2_blind_report_2026-08-22.md`。

## 当前结论

v2 合同和运行代码已经生效，旧合同没有兼容解析器。新的盲测集合已经产生首轮未调优基线；运行后不修改 Oracle，后续改进必须使用新的测试集验证。
