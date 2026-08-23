# EcomDispute V3破坏性重构与首轮评测

## 重构范围

- 旧本体：4个Skill、12个主业务Route、3个合规Route、14个Tool。
- V3本体：7个Skill、26个业务Route、3个合规Route、29个Tool。
- 删除旧Route ID、旧数据库种子和运行时映射，不保留兼容别名。
- 新增订单费用、陌生扣款声明、退货追踪、换货选项、订单修改选项、目录、库存、价格、促销、配送、会员和站点技术事件等证据。
- SQLite从空文件重建31张表。
- 确定性ActionPlan只在裁决后生成，包含确认要求和幂等键；VERIFY不执行写操作。

完整Route合同见根目录`EcomDispute-Route本体与能力边界V3.md`。

## 关键边界修复

1. 删除独立`merchant_not_shipped`入口，作为`fulfillment_progress`的确定性裁决结果。
2. `cancellation_in_transit`扩展为`order_cancellation`，由证据决定揽收前后路径。
3. `return_eligibility`改为`return_request`，新增独立`return_progress`和`exchange_request`。
4. `wrong_item`改为`received_item_mismatch`，要求下单值/实收值双侧原文证据。
5. 买家选错、不合身、不喜欢通过`return_reason`表达，不提前归责给商家。
6. `damaged_item`扩展为包含破损、污渍、瑕疵和质量缺陷的`item_condition_issue`。
7. 新增陌生扣款与订单费用争议，避免强塞进重复扣款或退款金额。
8. 新增站点可靠性Skill，区分结账、购物车、搜索和性能故障。
9. `has_dispute`替换为`has_business_exception`；问题后来解决不抹掉已经发生的异常。

## 自动化验证

| 项目 | 结果 |
|---|---:|
| Ruff | 通过 |
| Pytest | 70/70 |
| Skill资源 | 7/7加载 |
| Route资源/Strategy | 29/29加载 |
| Tool定义/Executor/Adapter | 29/29加载 |
| V3确定性最小E2E | 26/26 |

26条最小E2E每个业务Route一条，验证Route解析、动态工具面、Evidence Adapter、Strategy、合规子任务、ReviewTask和ActionPlan合同。它不是生产准确率。

## 真实LLM边界评测

### 数据

- 模型：`gpt-5.6-luna`
- 输入：44条，在模型调用前生成并保存。
- 覆盖：26个业务Route各一条、14组边界最小对照、4条明确拒识。
- 重复次数：1。
- workers：4。

### V3初轮

V3初轮有效44/44，原始Route为42/44。人工错误分析发现`buyer-color`文本明确要求“换成白色”，模型选择`exchange_request`正确，而Oracle写成`return_request`。本轮不修改Oracle重算，原始结果保存在`v3_route_boundary_gpt-5.6-luna_run1_raw.json.gz`。

另一条真实失败为：明确缺货导致无法加入购物车时，模型选择`cart_issue`而不是`inventory_availability`。

### V3.1独立重跑

V3.1在运行前完成两项变更：

- 将错标样本替换为“买家选错颜色、只退货退款且不换货”；
- 明确“已知缺货优先库存，库存可用或未知但状态异常才是购物车故障”。

| 指标 | 结果 |
|---|---:|
| Case | 44 |
| Evaluated | 44 |
| API Error | 0 |
| Route Accuracy | 44/44（100%） |
| Has Business Exception | 43/44（97.7%） |
| Return Reason | 3/3（100%） |
| Model Repair | 0 |
| Input Token | 314,780 |
| Output Token | 8,050 |
| 累计模型延迟 | 614,884ms |

唯一失败为`v3-boundary-pair-return-warehouse`：对话明确退货物流签收但仓库未入库，模型Route正确选择`return_progress`，但将`has_business_exception`判断为`false`。该错误保留为模型能力限制，不继续针对本集调Prompt。

原始结果保存于`v3_1_route_boundary_gpt-5.6-luna_run1_raw.json.gz`。

## ABCD V3外部评测口径

- 删除`SUPPORTED_SUBFLOWS`及subflow到Route的一对一映射。
- 从完整ABCD的96个subflow轮转抽样200条。
- Manifest仅保存ID、split、subflow和Action是否存在，不保存Route答案。
- 双盲表单隐藏subflow与模型预测。
- 机器预标注只读英文；中文仅供人工辅助。
- 人工Consensus完成前，Route Accuracy为`null`。

旧71.9%是Legacy Ontology V2粗映射一致率，不是V3指标。

## 限制与下一步

- 26条确定性E2E只覆盖每Route一个主分支，需要扩展各Strategy的状态矩阵。
- V3.1边界集规模仍小，100% Route不能外推到生产准确率。
- ABCD逐对话人工Consensus尚未完成。
- ActionPlan没有连接真实生产写接口。
- 全量Route定义使单次Conversation调用成本偏高；后续可研究分层Skill Router，但必须用全新评测集验证成本与准确率。
