# V2 Route Holdout Run 1

## 设置

- 模型：`gpt-5.6-luna`
- 数据：8条在12类 `route_type` 合同完成后新建的未见对话
- 覆盖：退款金额、重复扣款、扣款成功订单失败、商家未发货、签收未收到、退货资格、错件、破损
- Oracle：首次模型调用前写入，运行后未调整
- 有效结果：8/8，API错误0

## 结果

| 指标 | 结果 |
|---|---:|
| 全项Exact Match | 0/8 |
| Route Type Accuracy | 100% |
| Has Dispute Accuracy | 100% |
| 用户BusinessFact Precision / Recall | 27.3% / 75.0% |
| 用户InteractionAct Precision / Recall | 100% / 37.5% |
| 客服InteractionAct Precision / Recall | 50.0% / 44.4% |
| 输入 / 输出Token | 43,762 / 1,755 |
| 累计模型延迟 | 82,257 ms |

## 失败分析

Route扩展成功：8类新场景全部路由正确，争议识别也全部正确。

全项Exact Match为0的主要原因不是Route，而是旧BusinessFact和InteractionAct合同仍偏退款/物流：

- 重复扣款、支付失败、错件、破损和退货等事实被模型合理输出为 `other`，但Oracle预期为空。
- 商家未发货同时产生 `delivery_delay` 和 `delivery_pickup=negated`，Oracle只标后一项。
- 退款金额句子同时产生金额冲突和实际到账事实，Oracle只标金额冲突。
- 模型经常不为纯业务陈述额外输出Assertion；客服“我会核验”通常识别为Action而不是Promise。
- 签收未收到的两个核心BusinessFact完全匹配，但InteractionAct没有完全匹配。

## 结论

新的 `route_type` 已达到可用路由能力，但通用事实本体没有同步覆盖商品、支付和售后领域。不能用本次0/8说明业务裁决失败，也不能修改本轮Oracle后重算。下一版应先扩展FactType本体，再新建独立holdout；本数据保留为首次合同迁移结果。
