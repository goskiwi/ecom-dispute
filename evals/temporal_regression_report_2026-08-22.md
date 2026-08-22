# EcomDispute M5 时态冲突回归

## 目标

针对 M4 发现的三个对话-事实冲突误报，增加结构化 `temporal_status`，区分：

- `future`：预计、将会、后续处理
- `current`：正在、仍处于
- `completed`：已经发起、已经完成、已经送达
- `unknown`：无法从原文判断

Evidence Fusion 只对时态明确为当前或已完成的状态声明生成硬冲突，未来承诺不与当前业务记录直接冲突。

## 定向真实 LLM 校准

模型：`gpt-5.4-mini-2026-03-17`

| 案例 | M4 问题 | M5 结果 |
|---|---|---|
| `refund_missing_002` | “会尽快处理”被当作当前处理中，产生误报 | 输出 `refund_processing + future`，冲突消除 |
| `refund_pending_003` | “预计五天内到账”被当作退款完成，产生误报 | 输出 `wait_advice + future`，冲突消除 |
| `refund_complete_004` | “卡里收到 199”曾被反向标为未到账 | 曾用原文一致性校验过滤；M6 已从 live 路径删除该关键词校验 |

M6 审计认为第三项仍属于关键词后处理，会掩盖模型误报，因此已从真实 Conversation Agent 删除。该历史回归不再代表当前 live 主链路表现。

本报告是 3 个已知误报的定向回归，不更新 M4 的 60 案例首轮指标。全量重新评测前，仍以 M4 原始与审计后结果为准。
