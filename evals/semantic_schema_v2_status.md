# Semantic Schema v2 状态

## 破坏性变更

v2 删除了以下旧字段：

- `statement_types[]`
- `user_claims`
- `agent_commitments`
- `statement_type`

最终输出拆为两个数组：

```text
business_facts[]
  speaker
  quote
  message_index
  fact_type
  polarity
  temporal_status

interaction_acts[]
  speaker
  quote
  message_index
  speech_act
```

每个业务事实只有一个类型和一个时态。用户实际收到钱/货使用 `*_receipt`，系统退款完成或物流送达状态使用 `*_completion`；查询、建议、核验动作和解释不再伪装成业务事实。

## 验证

`gpt-5.6-luna` 严格 Schema 探针成功，能够把“预计今晚到账，请再等等”拆成未来到账 promise 与等待 advice，并提供逐字 quote。完整 live 冒烟也成功：Conversation Agent 输出三个原子事实，Tool Query Agent 两轮完成订单、售后、支付、退款和政策查询，最终策略判定 `refund_record_conflict`。

第一次 30 条运行使用机械迁移 Oracle，发现 receipt/completion 标签存在领域错误，因此该结果只作为 schema validation 移入 `evals/legacy/`。随后创建全新的 30 条盲测对话并在调用前固定 Oracle，`gpt-5.6-luna` Run 1 获得 30/30 有效响应；全项 Exact Match 为 10/30，详细结果见 `semantic_holdout_schema-v2_blind_report_2026-08-22.md`。

## 当前结论

随后进一步把 BusinessFact 与 InteractionAct 拆成独立数组，并使用新建的 20 条未见对话完成正式 Run 1：用户/客服 BusinessFact F1 约 86.3%/85.7%，InteractionAct F1 约 94.7%/93.0%，全项 Exact Match 11/20。详见 `semantic_holdout_split-contract_report_2026-08-22.md`。
