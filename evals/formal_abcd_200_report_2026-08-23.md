# Formal ABCD 200 External Run 1

## 设置

- 模型：`gpt-5.6-luna`
- 数据：ABCD v1.1官方数据
- 160条受支持对话：8个subflow各20条
- 40条不支持对话：8个subflow各5条，期望Route=`other`
- Manifest在模型调用前生成并提交
- workers：4

## 结果

| 指标 | 结果 |
|---|---:|
| 计划案例 | 200 |
| 有效结果 | 199 |
| API错误 | 1（60秒超时） |
| 总Route Accuracy | 71.9% |
| 受支持Route Accuracy | 66.7% |
| Unsupported拒识 | 92.5% |
| Action-presence Precision / Recall | 100% / 64.8% |
| Input / Output Token | 1,228,311 / 236,843 |
| 模型累计延迟 | 5,332,677 ms |

### 受支持subflow

| Subflow | Route Accuracy |
|---|---:|
| refund_status | 100% |
| mistimed_billing_already_returned | 95% |
| status_delivery_time | 90% |
| return_size | 80% |
| refund_initiate | 73.7%（19条有效） |
| refund_update | 65% |
| return_color | 20% |
| status_shipping_question | 10% |

## 失败分析

- `return_color`经常被模型路由到更具体的`wrong_item`，而Manifest将ABCD退换颜色流程映射为`return_eligibility`。这同时暴露映射粒度和项目Route边界问题。
- `status_shipping_question`常被拒识为`other`，说明英文“shipping question”与当前中文物流争议定义不一致。
- `refund_update`经常被分到更具体的`refund_amount`或`return_eligibility`。
- Unsupported拒识达到92.5%，说明模型没有普遍把外部对话强塞进现有Route。

## Action指标边界

ABCD提供系统Action事件，但不直接提供本项目六类InteractionAct标签。本报告只比较“对话是否存在ABCD Action”与“模型是否输出agent action”，因此是Action-presence代理指标，不是Action ID准确率，也不是完整InteractionAct F1。

## 结论

外部真人客服对话的Route准确率显著低于项目内E2E，证明12/12或116/120不能代表跨分布泛化。项目可以处理退款状态和配送时间，但退换颜色、运输咨询和细粒度Route映射仍然薄弱。
