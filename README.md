# EcomDispute

EcomDispute V3 是一个覆盖电商资金、履约、售后、订单操作、商品咨询和站点故障的多阶段 Agent Harness。真实LLM负责理解对话和长尾证据，Route限定动态工具面，确定性Strategy负责政策、金额、时限和责任计算，最终输出Evidence、Trace、ReviewTask和需要确认的ActionPlan。

项目融合两类工程经验：

- 电商售后：订单、支付、退款、物流、仓库、促销和会员证据；
- 线上问题诊断：结账、购物车、搜索和站点性能事件。

核心边界：

> 模型负责开放性理解；Harness负责状态、权限、工具和恢复；Strategy负责确定性裁决；跨系统写入只生成待确认ActionPlan。

## 当前规模

| 能力 | V3实现 |
|---|---:|
| Skill Pack | 7 |
| Route | 29（26个业务Route + 3个合规检查） |
| Tool | 29 |
| SQLite表 | 31 |
| 真实LLM Agent角色 | 3 |
| V3 Decision E2E | 90条主案例 / 97个Decision |
| Route边界集 | 44 |
| 真实LLM全链路E2E | 40 |
| EvidenceGap真实消融 | 12 |
| 失败矩阵 | 26条缺失必需Evidence案例 |
| 自动化测试 | 86 |

完整本体与边界见[EcomDispute Route本体与能力边界V3](EcomDispute-Route本体与能力边界V3.md)。

## Skill与Route

```text
funds-dispute
├── refund-progress
├── refund-amount-mismatch
├── duplicate-charge
├── payment-captured-order-failed
├── unrecognized-charge
└── order-fee-dispute

fulfillment-service
├── fulfillment-progress
├── delivered-not-received
└── order-cancellation

item-after-sales
├── return-request
├── return-progress
├── exchange-request
├── received-item-mismatch
├── missing-item
└── item-condition-issue

order-operations
└── order-management

commerce-support
├── product-information
├── inventory-availability
├── price-adjustment
├── promotion-support
├── shipping-options
└── membership-support

site-reliability
├── checkout-issue
├── cart-issue
├── search-issue
└── site-performance

service-compliance
├── business-statement-check
├── promise-grounding-check
└── escalation-requirement-check
```

V3不保留`refund`、`delivery`、`merchant_not_shipped`、`return_eligibility`、`wrong_item`等V2 Route兼容映射。

## 三个真实LLM Agent

- `ConversationAgent`：输出V3 Route、`has_business_exception`、BusinessFact、InteractionAct，以及退货原因或商品不符双侧证据；quote必须来自原消息。
- `EvidenceGapAgent`：只能搜索当前Route声明的Lazy Tool，不负责裁决。
- `ReviewAgent`：仅在冲突或合规问题需要复检时运行，只能引用已有Evidence ID。

确定性Executor、Reducer、Policy Resolver和Decision Strategy不称为Agent。

## Harness链路

```text
ROUTE
ConversationAgent选择具体业务Route
  ↓
ANALYZE
抽取有原文依据的事实、原因和交互行为
  ↓
VERIFY
按Skill/Route/Stage计算动态Tool Surface并收集核心证据
  ↓
DECIDE
确定性Strategy执行状态机、金额、SLA、政策和责任判断
  ↓
FUSE_AND_REVIEW
Evidence Fusion + 3个合规检查 + 按需ReviewAgent + ActionPlan
```

`received_item_mismatch`必须包含明确的下单值与实收值比较；“wrong color/size”但原因不明时进入`return_request`，不能推断商家错发。

## Tool Runtime

每轮工具集合由当前Skill、Route、Stage和已加载Lazy Tool共同计算。Runtime负责：

```text
Tool Surface准入
→ JSON Schema
→ Case Scope注入
→ Executor
→ ToolResultEnvelope
→ Evidence Adapter
→ CaseStateReducer
```

29个工具覆盖订单、支付、退款、物流、签收、取消、退货、换货、仓库、附件、费用、商品目录、库存、价格、促销、配送、会员、结账、购物车、搜索和站点健康。

订单修改、退货、换货、价保、优惠修复等流程只产生结构化ActionPlan。ActionPlan带确认要求和幂等键；VERIFY阶段不会无条件执行写操作。

## 快速开始

要求Python 3.11+和[uv](https://docs.astral.sh/uv/)。

```bash
uv sync --dev
uv run python -m ecom_dispute data rebuild
uv run pytest -q
uv run python -m ecom_dispute eval --mode deterministic
uv run python -m ecom_dispute web --agent-mode heuristic-test --port 8765
```

真实LLM Route边界评测：

```bash
export ECOM_DISPUTE_API_KEY='your-key'
uv run python -m ecom_dispute \
  --base-url 'https://your-openai-compatible-endpoint.example' \
  --model 'your-model' \
  holdout --repeats 1 --workers 4
```

## V3评测

### 确定性Decision全分支E2E

29个Route合同共有97个非`manual_review` Decision。V3使用90条主案例覆盖全部90个业务Decision，并通过嵌套合规子任务覆盖7个合规Decision；实际执行达到97/97，同时校验Party、Review、必需Evidence、必需Tool和13类ActionPlan。它证明合同分支可执行，不代表生产准确率。详见[V3 Decision覆盖报告](evals/v3_decision_coverage_report_2026-08-23.md)。

另建26条缺失必需Evidence矩阵：26/26均安全关闭为`manual_review + undetermined`，准确列出缺失Evidence且不生成ActionPlan；工具Timeout和ConnectionError进入结构化Trace。详见[V3失败矩阵报告](evals/v3_failure_matrix_report_2026-08-23.md)。

### 真实LLM Route边界集

V3.1边界集在模型调用前提交44条输入和Oracle，覆盖26个业务Route、14组相邻Route最小对照和4条明确拒识。

`gpt-5.6-luna`首轮：

| 指标 | 结果 |
|---|---:|
| 有效结果 | 44/44 |
| Route Accuracy | 44/44（100%） |
| Business Exception Accuracy | 43/44（97.7%） |
| Return Reason Accuracy | 3/3（100%） |
| 模型修复 | 0 |
| Input / Output Token | 314,780 / 8,050 |
| 累计模型延迟 | 614,884ms |

唯一错误：退货物流已签收但仓库未入库，被模型判断为普通进度而不是业务异常；Route仍为`return_progress`。详见[V3重构与评测报告](evals/v3_rebuild_report_2026-08-23.md)。

### 真实LLM全链路E2E

从90条Decision矩阵按风险分层预提交40条，覆盖26/26业务Route，其中31条预期Review、12条预期ActionPlan。共享Conversation的Live/Core均为39/40（97.5%）；Review P/R为100%/100%，Evidence Grounding 100%，ActionPlan 97.5%。唯一失败是“取消已受理但退款未开始”被模型路由到`refund_progress`，V3边界要求`order_cancellation`。ReviewAgent增加150,762输入Token和440,587ms累计延迟，准确率增量为0。详见[V3.1真实E2E报告](evals/v3_live_e2e_40_report_2026-08-23.md)。

### EvidenceGap真实消融

5个Route声明真实Lazy Tool，12条预提交案例包含7条应加载、5条应拒绝和2条负向查询。Core/Gap/Full的Decision均12/12；Gap工具选择11/12（P/R 87.5%/100%），Full中的独立Gap选择12/12，选择一致率91.7%。Gap增加8条Evidence和58,174输入Token，但Decision准确率增量为0。详见[V3.1 Gap消融报告](evals/v3_gap_ablation_report_2026-08-23.md)。

### ABCD外部数据

V3 Manifest从完整ABCD v1.1的96个subflow轮转抽样200条，只负责固定样本，不包含Route Oracle，也不再声称“160条受支持”。真实`gpt-5.6-luna` Conversation完成200/200，Route指标保持`null`；中文辅助和英文预标注均完成200/200。8条重点样本已完成人工复核，39条Route分层样本完成Codex语义抽检并修正1条；没有全量人工Consensus，因此V3外部集不报告Route Accuracy。详见[V3 ABCD未评分报告](evals/v3_abcd_200_unscored_report_2026-08-23.md)。

机器预标注只允许读取英文原文；中文翻译仅供人工辅助，同模型预标注不能作为独立Oracle。

## V2历史结果

旧12 Route、120 E2E、ABCD 71.9%粗映射和Review 40报告均属于Legacy Ontology V2，保留作演进记录，但不能作为V3指标引用。V3没有为旧Route、旧Oracle或旧数据库增加兼容层。

## 当前限制

- 97个Decision目前各自只有一条主证据组合，仍需增加缺失证据、跨源冲突和表达变体。
- 数据为人工/规则构造和公开模拟对话，不是企业生产流量。
- 工具后端是本地SQLite模拟连接器，不代表远程微服务可靠性。
- ActionPlan尚未连接真实生产写接口。
- ABCD V3人工Consensus尚未完成，不能提前报告外部Route准确率。
- ReviewAgent V3匿名A/B尚未完成人工评分，不能声称提高审核效率。
- 29 Route完整定义增加Prompt成本；分层Skill Router的成本优化必须使用新评测集验证。

## 设计与面试材料

- [V3 Route本体](EcomDispute-Route本体与能力边界V3.md)
- [V3重构与评测报告](evals/v3_rebuild_report_2026-08-23.md)
- [V3 Decision覆盖报告](evals/v3_decision_coverage_report_2026-08-23.md)
- [V3失败矩阵报告](evals/v3_failure_matrix_report_2026-08-23.md)
- [V3.1真实E2E报告](evals/v3_live_e2e_40_report_2026-08-23.md)
- [V3.1 Gap消融报告](evals/v3_gap_ablation_report_2026-08-23.md)
- [V3 ABCD未评分报告](evals/v3_abcd_200_unscored_report_2026-08-23.md)
- [ABCD标注指南](docs/abcd_route_annotation_guide.md)
- [简历与面试口径](docs/resume_and_interview.md)
