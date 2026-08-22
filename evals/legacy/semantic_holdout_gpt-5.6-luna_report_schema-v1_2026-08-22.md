# GPT-5.6-Luna Semantic Holdout 评测

## 范围

- 数据：30 条 post-implementation authored holdout，Refund/Delivery 各 15 条
- 模型：`gpt-5.6-luna`
- 计划：30 条 × 3 次，串行执行
- 匹配规则：业务类型、争议判断、用户事实集合、客服事实集合；事实由 `(statement_type, temporal_status)` 构成
- 多报和漏报均计错，同时报告 micro Precision/Recall

## API 完整性

计划调用 90 次，实际得到 53 个有效模型响应：

| 重复轮次 | 有效响应 | API 错误 |
|---|---:|---:|
| Run 1 | 30/30 | 0 |
| Run 2 | 23/30 | 7 |
| Run 3 | 0/30 | 30 |

Run 2 是部分结果，Run 3 无效。HTTP 502 不进入模型指标分母，也不进行选择性自动重试。因此不能声称完成了三次稳定性评测。

## Run 1 完整结果

| 指标 | 结果 |
|---|---:|
| 全项精确匹配 | 11/30（36.7%） |
| Business Type Accuracy | 96.7% |
| Has Dispute Accuracy | 96.7% |
| 用户事实案例级 Exact Match | 63.3% |
| 客服事实案例级 Exact Match | 60.0% |
| 用户事实 micro Precision | 81.4% |
| 用户事实 micro Recall | 79.5% |
| 客服事实 micro Precision | 76.0% |
| 客服事实 micro Recall | 63.3% |

## Run 2 部分观察

仅覆盖 23 条，不与 Run 1 做完整均值：全项 8/23（34.8%），用户事实 Precision/Recall 为 78.1%/78.1%，客服事实 Precision/Recall 为 63.2%/52.2%。

## 主要失败模式

- 未来到账承诺被额外标成 `refund_completed + future`，类型多报。
- “系统显示已送达/已退款”等客服事实经常没有进入 `agent_commitments`。
- 查询动作的 `temporal_status` 在 `current`、`future`、`unknown` 间不稳定。
- “申请已登记、稍后审核”会在 `refund_requested` 与 `refund_processing` 间混淆。
- 已到账但需要核单的正常查询，偶尔被路由为 `other`。

## 限制

holdout 由实现完成后另行编写，不是公开数据或外部团队标注数据。Run 1 可以作为当前模型在该后置集合上的一次完整结果；无法据此推断线上准确率。

