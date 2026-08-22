# Formal Review 40 A/B Generation

## 设置

- Case来源：Formal E2E 120中实际触发Review的候选
- 数量：40
- 分布：5条跨源冲突、4条证据缺失、31条客服合规
- Option来源：确定性固定模板 vs `gpt-5.6-luna` ReviewAgent
- A/B顺序：固定随机种子匿名交换
- A/B key：仅保存在本地忽略文件，未提交GitHub

## 生成结果

| 指标 | 结果 |
|---|---:|
| 计划案例 | 40 |
| 成功生成 | 40 |
| API错误 | 0 |
| Input / Output Token | 196,317 / 16,857 |
| 模型累计延迟 | 487,432 ms |
| 已完成人工评分 | 0/40 |

匿名表中同时包含原对话、系统Decision/Party、Evidence ID/类型/摘要，以及Option A/B的摘要、问题、建议动作和优先级，能够实际评分Evidence正确性。

## 当前边界

- 类别分布不均衡，合规案例占31/40。
- 在两位人工评审完成前，不能计算ReviewAgent胜率、均分、评审一致率或Kappa。
- 当前结果只证明A/B材料成功生成且ReviewAgent引用通过Evidence校验，不证明它优于固定模板。
