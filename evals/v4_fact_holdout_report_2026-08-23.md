# V4 Fact Ontology Holdout Run 1

## 设置

- 模型：`gpt-5.6-luna`
- 数据：8条在支付、订单、商品和退货FactType加入后新建的未见对话
- Oracle：首次模型调用前完成，运行后未调整
- 有效结果：8/8，API错误0

新增一等事实类型：

```text
order_creation
payment_charge
payment_duplicate
payment_reversal
item_identity
item_quantity
item_damage
return_request
return_eligibility
item_condition
```

## 结果

| 指标 | 结果 |
|---|---:|
| 全项Exact Match | 2/8（25%） |
| Route Type Accuracy | 100% |
| Has Dispute Accuracy | 100% |
| FactType-only Precision / Recall | 90.9% / 100% |
| 用户BusinessFact三元组 Precision / Recall | 36.4% / 40.0% |
| 用户InteractionAct Precision / Recall | 88.9% / 100% |
| 客服InteractionAct Precision / Recall | 100% / 100% |
| 输入 / 输出Token | 45,207 / 2,082 |
| 累计模型延迟 | 106,380 ms |

## 结论

破坏性事实本体迁移已经解决新业务只能输出`other`的问题：Oracle中的10个新FactType全部被模型识别，唯一多报是破损案例同时输出了`delivery_receipt`。

剩余主要错误来自TemporalStatus，而不是FactType：

- 重复扣款、错件、少件和破损被模型标为`current`，Oracle标为`completed`。
- 退款金额和实际入账金额被模型标为`current`，Oracle标为`completed`。
- 退货资格案例FactType完全匹配，但InteractionAct多报或少报导致全项失败。

`current/completed`对“已经发生的事件”和“目前仍存在的状态”定义仍不够清楚。下一版需要先写明确的时间语义规范，再新建holdout；不得修改本轮Oracle后重算。
