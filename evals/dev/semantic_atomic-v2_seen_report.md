# Semantic Schema v2 Blind Run 1

## 评测设置

- 模型：`gpt-5.6-luna`
- 数据：30 条在 schema v2 完成后新建的中文盲测对话，Refund/Delivery 各 15 条
- Oracle：在模型调用前完成并固定，运行后未调整
- 调用方式：串行、每条一次
- 有效响应：30/30，API 错误 0
- Fact 匹配键：`(fact_type, polarity, temporal_status, speech_act)`
- Exact Match 要求期望集合与观察集合完全一致，多报和漏报均失败

## 结果

| 指标 | 结果 |
|---|---:|
| 全项 Exact Match | 10/30（33.3%） |
| Refund 全项 | 7/15 |
| Delivery 全项 | 3/15 |
| Business Type Accuracy | 100% |
| Has Dispute Accuracy | 93.3% |
| 用户 Fact 案例级 Exact Match | 73.3% |
| 客服 Fact 案例级 Exact Match | 40.0% |
| 用户 Fact micro Precision | 79.1% |
| 用户 Fact micro Recall | 82.9% |
| 客服 Fact micro Precision | 41.9% |
| 客服 Fact micro Recall | 40.6% |

调用消耗：输入 157,072 Token，输出 7,459 Token，累计模型延迟 309,116 ms。

## 失败分布

- 客服 Fact 不匹配：18 个案例
- 用户 Fact 不匹配：8 个案例
- Has Dispute 不匹配：2 个案例
- Business Type 不匹配：0 个案例

主要错误包括：

- 将客服正在执行的查询动作标为 `current`，而 Oracle 将非业务状态动作标为 `not_applicable`。
- 在 `delivery_receipt` 与 `delivery_completion`、`status` 与具体物流阶段之间混淆。
- 把用户转述商家承诺识别为 promise，而不是用户对未来事实的 assertion。
- 面对“订单显示完成但没有签收事件”时输出两个相反事实，而不是单个 `conflicting` Fact。
- 对 advice 的 polarity 在 `affirmed` 与 `uncertain` 间不稳定。

## 限制

该集合由项目实现完成后另行编写，不是公开数据或外部团队标注数据。它可以作为当前 schema v2 的未调优基线，但不能代表线上业务准确率。

