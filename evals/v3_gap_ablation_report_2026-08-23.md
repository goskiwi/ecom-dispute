# V3.1 EvidenceGap真实消融报告

## 目标

验证EvidenceGapAgent是否能在Route限定范围内判断长尾证据是否必要、选择正确Lazy Tool、保留无记录的负向Evidence，并量化其对Decision、证据完整度、Token和延迟的影响。

## Core/Lazy边界

| Route | Lazy Tool | 用途 |
|---|---|---|
| `unrecognized_charge` | `get_payment_gateway_events` | 核对渠道交易事件 |
| `refund_amount_mismatch` | `get_payment_gateway_events` | 核对实际渠道入账金额 |
| `received_item_mismatch` | `get_claim_attachments` | 获取实收商品图片等长尾凭证 |
| `delivered_not_received` | `get_delivery_address` | 核对是否配送到错误地址 |
| `item_condition_issue` | `get_logistics_events` | 判断商品状况是否可能与运输异常相关 |

这些工具只补责任或长尾材料，不是主Decision必需证据。EvidenceGap Prompt读取原始对话、现有核心Evidence和当前Route唯一候选工具。

## 数据

- 12条，在模型调用前保存输入和Oracle；
- 7条应该加载Lazy Tool；
- 5条核心证据已经足够，应拒绝加载；
- 2条Lazy Tool查询预期返回`not_found`并形成负向Query Evidence；
- 每条共享一次Conversation；Gap与Full分别独立调用一次EvidenceGap；
- Full按确定性Review条件调用ReviewAgent。

## 初轮数据审计

初轮Route只有9/12。两条签收未收到样本没有明确写“用户未收到”，一条“已经确认是本人订单”不应继续作为陌生扣款Route。该轮不修改结果重算，保存在`v3_gap_12_gpt-5.6-luna_run1_raw.json.gz`。

V3.1只修正这三条不满足Route定义的自然对话，没有改变Lazy Tool Oracle或EvidenceGap Prompt。

## V3.1结果

| 指标 | Gap | Full中的Gap |
|---|---:|---:|
| 有效结果 | 12/12 | 12/12 |
| Route Accuracy | 100% | 100% |
| Decision / Party / Review | 100% | 100% |
| Tool Exact Accuracy | 11/12（91.7%） | 12/12（100%） |
| Tool Status Accuracy | 91.7% | 100% |
| Selection Precision | 87.5% | 100% |
| Selection Recall | 100% | 100% |
| 新增Evidence | 8 | 7 |

Core、Gap和Full的Decision准确率均为100%，准确率增量为0。两条预期负向查询均选择了正确工具并保存Query Evidence。

Gap与Full两次独立选择的一致率为11/12（91.7%）。

## 唯一选择错误

`v3gap-item-mismatch-not-needed`：

- 订单SKU与仓库扫描已经明确不一致，核心证据足以确认仓库错配；
- 对话明确说明不需要额外照片；
- Gap模式仍选择`get_claim_attachments`，结果为`not_found`；
- Full中的独立Gap调用正确选择不加载；
- 两种模式Decision都保持`received_item_mismatch_confirmed`。

这说明Agent具有过度查询倾向，且同输入下选择并非完全稳定。该错误保留，不针对本集继续调Prompt。

## 成本

| 成本 | Conversation | Gap增量 | Full增量 | Review相对Gap增量 |
|---|---:|---:|---:|---:|
| Input Token | 86,330 | 58,174 | 107,677 | 49,503 |
| Output Token | 6,217 | 1,565 | 5,878 | 4,313 |
| 累计延迟 | 215,476ms | 128,000ms | 343,851ms | 215,851ms |

Full中10条触发ReviewAgent。EvidenceGap增加证据但不改变确定性Decision；Review增加复检材料但不改变Decision。

## 限制

- 只有5个Route、每个Route单一Lazy Tool，没有验证多个Lazy候选之间的检索排序；
- 12条为项目构造对话，不代表生产证据缺口分布；
- 两次独立Gap调用不能替代更多重复实验；
- 本轮只证明EvidenceGap可以受Route约束补证，不能声称提高业务准确率。

V3.1原始结果保存在`v3_1_gap_12_gpt-5.6-luna_run1_raw.json.gz`。
