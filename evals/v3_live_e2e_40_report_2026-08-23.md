# V3.1 40条真实LLM全链路E2E报告

## 预提交设置

- 模型：`gpt-5.6-luna`；
- 数据：从90条Decision矩阵按风险分层选择40条；
- Route覆盖：26/26；
- `review_required`：31条；
- 预期ActionPlan：12条；
- 选样：每个Route先取最高风险案例，再按全局风险补足；
- 21条Decision矩阵扩展案例全部替换为自然对话，Decision字符串泄漏为0；
- Conversation输出在Live与Core之间共享；
- workers：4。

输入、Oracle和选样Manifest均在模型调用前保存。

## 初轮数据问题

初轮39/40有效，其中38条通过。一条`payment_order_state_conflict`对话写成“订单状态正常”，却要求进入“已扣款但订单失败”，模型选择`other`合理。该轮不修改Oracle重算，原始结果保存在`v3_live_e2e_40_gpt-5.6-luna_run1_raw.json.gz`。

V3.1只将该无效对话改为“银行扣款成功，但订单页面明确显示创建失败”，同时把ActionPlan加入正式评分；未调整取消关联退款的Route边界或Prompt。

## V3.1结果

| 指标 | Live | Core |
|---|---:|---:|
| 有效结果 | 40/40 | 40/40 |
| 全项通过 | 39/40（97.5%） | 39/40（97.5%） |
| Route Accuracy | 97.5% | 97.5% |
| Decision Accuracy | 97.5% | 97.5% |
| Responsible Party | 97.5% | 97.5% |
| Review Accuracy | 100% | 100% |
| Review Precision / Recall | 100% / 100% | 100% / 100% |
| Required Evidence | 97.5% | 97.5% |
| Required Tools | 97.5% | 97.5% |
| Evidence Grounded | 100% | 100% |
| ActionPlan Accuracy | 97.5% | 97.5% |
| 平均Tool Calls | 3.95 | 3.95 |

ActionPlan失败与唯一Route失败是同一案例；正确Route下的12个ActionPlan合同均匹配。

## 唯一失败

`v3d-cancellation_refund_missing`：

- 用户：取消已经受理、订单未发货、退款未开始；
- Oracle：`order_cancellation`，因为V3冻结边界明确包含取消结果及关联退款；
- 模型：`refund_progress`；
- 后果：Harness按错误Route稳定查询退款证据，最终输出`manual_review + undetermined`，导致Decision、Party、Evidence、Tool和ActionPlan同时失败；
- Evidence Grounding和Review仍正确。

该失败保留为真实Route边界限制，不针对本集继续调Prompt。

## Agent成本

| 成本 | Live | Core | Review增量 |
|---|---:|---:|---:|
| Input Token | 437,874 | 287,112 | 150,762 |
| Output Token | 24,811 | 12,133 | 12,678 |
| 累计模型延迟 | 933,922ms | 493,335ms | 440,587ms |

- Conversation调用：40；
- ReviewAgent触发：31；
- EvidenceGapAgent触发：0，因为本轮Route没有声明需要动态加载的Lazy Tool；
- ReviewAgent准确率增量：0。

ReviewAgent的价值仅是为31条复检案件生成受Evidence约束的材料，不能表述为提高确定性裁决准确率。

## 限制

- 40条来自项目构造Decision矩阵，不是生产对话；
- 每个Route至少一条，但不是每个Decision都运行真实LLM；
- 31/40为高风险Review样本，分布不代表真实线上Review率；
- ActionPlan只验证生成合同，没有连接生产写接口；
- 本轮没有触发EvidenceGapAgent，不能用于评价其收益。

原始结果保存在`v3_1_live_e2e_40_gpt-5.6-luna_run1_raw.json.gz`。
