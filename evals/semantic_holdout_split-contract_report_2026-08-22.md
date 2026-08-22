# Split Contract Blind Run 1

## 设置

- 模型：`gpt-5.6-luna`
- 数据：20 条在 BusinessFact/InteractionAct 拆分完成后新建的未见中文对话，Refund/Delivery 各 10 条
- Oracle：模型调用前固定，运行后未调整
- 有效响应：20/20，API 错误 0
- BusinessFact 匹配键：`(fact_type, polarity, temporal_status)`
- InteractionAct 匹配键：`speech_act`

## 结果

| 指标 | 结果 |
|---|---:|
| 全项 Exact Match | 11/20（55.0%） |
| Refund 全项 | 5/10 |
| Delivery 全项 | 6/10 |
| Business Type Accuracy | 100% |
| Has Dispute Accuracy | 85.0% |
| 用户 BusinessFact Exact Match | 85.0% |
| 用户 BusinessFact Precision / Recall | 84.6% / 88.0% |
| 客服 BusinessFact Exact Match | 90.0% |
| 客服 BusinessFact Precision / Recall | 90.0% / 81.8% |
| 用户 InteractionAct Exact Match | 90.0% |
| 用户 InteractionAct Precision / Recall | 100% / 90.0% |
| 客服 InteractionAct Exact Match | 90.0% |
| 客服 InteractionAct Precision / Recall | 95.2% / 90.9% |

折算 F1：用户 BusinessFact 约 86.3%，客服 BusinessFact 约 85.7%，用户 InteractionAct 约 94.7%，客服 InteractionAct 约 93.0%。

调用消耗：输入 107,919 Token，输出 5,129 Token，累计模型延迟 186,573 ms。

## 剩余失败

- `has_dispute` 三处不一致，其中包含“仍在 SLA 内但用户陈述未收到”和“询问到账为何慢”等边界语义。
- 物流/退款系统“显示完成”有时被标为 `current`，Oracle 标为 `completed`。
- 客服“请等待”偶尔只识别 promise，漏掉 advice。
- 用户陈述金额差异时，模型额外生成到账事实，导致 Exact Match 多报。
- 少数纯事实陈述没有生成 assertion InteractionAct。

## 结论

拆分合同解决了旧四元组把业务事实与交互行为绑死的问题。BusinessFact 与 InteractionAct 均达到可用的中高 80%/90% F1，但全项 Exact Match 仍受边界争议与任一字段失败影响。该数据由项目完成后另行编写，不代表线上准确率。

