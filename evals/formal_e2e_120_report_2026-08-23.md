# Formal 120-Case E2E Run 1

## 设置

- 模型：`gpt-5.6-luna`
- 数据：120条，12个主Route各10条
- 数据组成：84个不同业务模板 + 36个同业务表达变体
- 数据来源：项目回归库提取并在模型调用前生成、提交输入和Oracle；不是生产订单
- Conversation结果在Live和Core链路间共享
- workers：4
- 有效结果：120/120，API错误0

## 总体结果

| 指标 | Live | Core |
|---|---:|---:|
| 全项通过 | 116/120（96.7%） | 116/120（96.7%） |
| Route / Decision / Party | 96.7% | 96.7% |
| Review Accuracy | 97.5% | 97.5% |
| Review Precision / Recall | 95.6% / 100% | 95.6% / 100% |
| Required Evidence | 99.2% | 99.2% |
| Required Tools | 99.2% | 99.2% |
| Evidence Grounded | 100% | 100% |
| 平均Tool Calls | 4.74 | 4.47 |

## 每个Route

| Route | 通过 |
|---|---:|
| refund | 9/10 |
| refund_amount | 10/10 |
| duplicate_charge | 10/10 |
| payment_order_failure | 10/10 |
| delivery | 7/10 |
| merchant_not_shipped | 10/10 |
| delivered_not_received | 10/10 |
| cancellation_in_transit | 10/10 |
| return_eligibility | 10/10 |
| wrong_item | 10/10 |
| missing_item | 10/10 |
| damaged_item | 10/10 |

## 4个失败

- `formal_delivery_07`：包裹丢失且未收到，模型路由到`delivered_not_received`；Oracle为普通`delivery`。
- `formal_delivery_08`：运输途中包裹破损，模型路由到`damaged_item`；Oracle为物流异常`delivery`。
- `formal_delivery_10`：持续派送中但未收到，模型路由到`delivered_not_received`；Oracle为`delivery`。
- `formal_refund_09`：少到账100元，模型路由到更具体`refund_amount`；Oracle为宽泛`refund`。

4条失败都从Conversation Route开始，后续Tool、Evidence和Strategy按照错误Route稳定执行。它们暴露的是Route边界重叠，不是随机工具失败。

## Agent成本

Live调用：

```text
Conversation: 120
EvidenceGap: 41
Review: 68
Input Token: 1,226,301
Output Token: 69,115
模型累计延迟: 2,380,250 ms
单Case延迟 P50/P95: 20.6s / 32.2s
```

Gap/Review相对共享Conversation的Core增量：

```text
Input Token: 530,033
Output Token: 37,671
模型延迟: 1,213,959 ms
准确率增量: 0
```

## 结论与限制

- 120条正式集把12条覆盖测试扩展到每Route 10条，结果从12/12变为116/120，更可信地暴露了Route重叠。
- Gap/Review仍未提高裁决准确率；价值只在长尾Evidence和复检材料。
- 84个独立模板和36个表达变体必须分开说明，不能称120个完全独立业务案例。
- 数据仍来自项目构造回归库，不代表生产准确率。
