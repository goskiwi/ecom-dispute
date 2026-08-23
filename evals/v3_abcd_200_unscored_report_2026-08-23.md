# V3 ABCD 200外部分布未评分报告

## 数据与隔离

- 数据：ABCD v1.1完整10,042条公开模拟客服对话；
- 固定样本：200条，覆盖全部96个subflow；
- 抽样：按subflow轮转，不按支持范围或预期Route选择；
- Manifest不包含Route Oracle；
- 双盲表单隐藏subflow、首次模型预测和旧粗映射；
- 外部对话不与项目订单数据库硬关联。

V3不再使用“160条受支持、40条拒识”的subflow粗映射，人工Consensus前Route Accuracy保持`null`。

## 真实Conversation Run 1

- 模型：`gpt-5.6-luna`；
- workers：4；
- 首轮有效：199/200；
- 1条因非`return_request` Route仍输出`return_reason`而结构失败；
- 只补跑该失败样本，首尝试成功；其余199条未重跑；
- V3.1有效：200/200；
- 模型修复：0；
- API/结构失败补跑：1。

| 指标 | 结果 |
|---|---:|
| Route Accuracy | `null`，等待人工Consensus |
| Business Exception预测率 | 27.0% |
| Action-presence一致率 | 63.0% |
| Input Token | 1,500,058 |
| Output Token | 226,276 |
| 累计模型延迟 | 6,262,819ms |

Action-presence只比较“ABCD是否含Action事件”与“模型是否输出客服Action”，不是Action ID准确率或完整InteractionAct F1。

## Route预测分布

| Route | 数量 |
|---|---:|
| product_information | 62 |
| membership_support | 26 |
| order_management | 17 |
| other | 16 |
| inventory_availability | 13 |
| return_request | 9 |
| promotion_support | 9 |
| refund_progress | 7 |
| fulfillment_progress | 7 |
| shipping_options | 5 |
| price_adjustment | 5 |
| order_fee_dispute | 4 |
| item_condition_issue | 3 |
| duplicate_charge | 3 |
| order_cancellation | 2 |
| search_issue | 3 |
| cart_issue | 2 |
| unrecognized_charge | 2 |
| checkout_issue | 2 |
| site_performance | 2 |
| return_progress | 1 |

## 中文辅助

- 200/200完成；
- 复用旧缓存3条，新翻译197条；
- Schema/轮次/speaker错误：0；
- Input/Output Token：984,458/66,541；
- 累计模型延迟：2,832,662ms；
- 两份评分表译文完全一致，人工标签仍全空；
- 数字差异只有原文`u2`笔误，以及“3项取2项”被译成中文数量词，语义未丢失。

中文只供人工辅助，英文原文是唯一标注依据。

## 英文原文AI预标注

- 200/200完成，错误0；
- Prompt只包含英文对话与V3 Route定义，不包含中文、subflow或首次预测；
- Input/Output Token：1,255,097/44,804；
- 累计模型延迟：2,465,941ms；
- 初始分层：154条快速抽检、46条重点复核。

同模型预标注不是独立Oracle，只用于降低人工从零标注成本。

## Codex语义分流

Codex检查46条初始重点候选和12条高置信Route分歧，依据冻结V3边界进行分流并保留AI修正理由：

- 快速抽检：181条；
- 重点人工复核：19条；
- AI候选修正：10条；
- 已人工确认：0条。

首次Conversation与最终AI候选的一致率只用于验证分层效果：

| 分层 | 数量 | Strict一致率 | Acceptable一致率 |
|---|---:|---:|---:|
| 全部 | 200 | 93.5% | 96.0% |
| 快速抽检 | 181 | 97.8% | 98.3% |
| 重点复核 | 19 | 52.6% | 73.7% |

这不是准确率；两份判断均由AI产生。分层差异只说明19条重点集集中了主要Route边界冲突。

## 总机器成本

Conversation、翻译和预标注合计：

- Input Token：3,739,613；
- Output Token：337,621；
- 累计模型延迟：11,561,422ms。

## 人工下一步

1. 复核全部19条重点样本；
2. 从181条快速样本按Route分层抽查至少37条（20%向上取整）；
3. 复核所有翻译存疑项；
4. 人工确认后生成Consensus；
5. 使用已保存的首次Conversation结果重评分，不重新调用模型。

## 当前不能声称

- ABCD V3 Route Accuracy；
- 183条候选supported就是人工支持范围；
- AI预标注等价于人工真值；
- V3已经实现生产外部分布泛化。

原始结果：

- `v3_abcd_200_gpt-5.6-luna_run1_raw.json.gz`；
- `v3_1_abcd_200_gpt-5.6-luna_run1_raw.json.gz`。
