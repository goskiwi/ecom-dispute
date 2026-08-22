# EcomDispute

EcomDispute 是一个面向电商售后争议的多阶段 Agent Harness。系统用真实 LLM 理解对话和处理长尾证据，用只读工具核验业务事实，再通过确定性策略完成金额、时限、政策和责任裁决，最终生成带 Evidence、Timeline、Trace 和人工复检任务的报告。

## 为什么做这个项目

电商争议通常同时包含三种互不等价的信息：

- 用户和客服在对话中的说法；
- 订单、支付、退款、物流、仓库等系统事实；
- 事发时有效的业务政策。

模型适合理解非结构化语言，但不应该自由编造业务记录或计算确定性规则。本项目的核心边界是：

> 模型负责开放性理解和长尾判断，Harness 负责工具边界、状态、恢复和Trace，Strategy负责确定性裁决。

## 当前规模

| 能力 | 当前实现 |
|---|---:|
| Skill Pack | 4 |
| Route | 15 |
| 只读业务Tool | 14 |
| live LLM Agent角色 | 3 |
| 持久化回归案例 | 152 |
| 自动化测试 | 74 |

### Skill与Route

```text
funds-dispute
├── refund-status
├── refund-amount-mismatch
├── duplicate-charge
└── payment-captured-order-failed

fulfillment-dispute
├── delivery-delay
├── merchant-not-shipped
├── delivered-not-received
└── cancellation-in-transit

item-after-sales
├── return-eligibility
├── wrong-item
├── missing-item
└── damaged-item

service-compliance
├── false-business-statement
├── unsupported-promise
└── missing-required-escalation
```

### 三个真实LLM Agent

- `ConversationAgent`：输出具体 `route_type`、BusinessFact 和 InteractionAct；quote 必须来自原消息。
- `EvidenceGapAgent`：核心证据完成后，只能在当前Route的Lazy Tool中选择一个长尾工具，不负责裁决。
- `ReviewAgent`：仅在冲突或合规问题需要复检时运行，只能引用已存在的Evidence ID。

确定性执行器、Policy Resolver、Reducer和Decision Strategy不称为Agent。

## 五阶段链路

```text
ROUTE
ConversationAgent选择具体Route
  ↓
ANALYZE
提取BusinessFact与InteractionAct
  ↓
VERIFY
固定核心工具 + 按需EvidenceGapAgent
  ↓
DECIDE
确定性Decision Strategy
  ↓
FUSE_AND_REVIEW
客服合规子任务 + Evidence Fusion + 按需ReviewAgent
```

主争议和客服合规保持独立Route与Trace，最后才合并Finding；合规结论不能覆盖主业务责任。

## Skill资源

```text
SKILL.md   给模型和开发者阅读的业务说明
skill.yaml Skill工具能力上限与Route索引
route.yaml Stage、工具面、证据要求和输出范围
stage.md   按需加载的当前阶段说明
tool.yaml  Schema、Scope、错误映射和实现绑定
Python     Strategy、Executor、Adapter、Reducer和Fusion
```

YAML不包含金额/SLA计算、责任逻辑、任意脚本或复杂表达式DSL。所有资源通过Pydantic加载并检查Tool、Stage、Strategy、Executor和引用文件。

## Tool Runtime

每轮工具集合由当前Skill、Route、Stage和已加载Lazy Tool计算。`tool_search`只能搜索当前Route声明的Lazy Tool，不能访问全局Registry。

已知Case参数由Runtime注入：

```text
order_id / region / business_type / effective_at
```

模型生成的ToolCall还要经过：

```text
Tool Surface准入
→ JSON Schema
→ Case Scope
→ Executor
→ ToolResultEnvelope
→ Result Adapter
→ StateDelta
→ CaseStateReducer
```

## 状态、证据和上下文

- `AgentRunState` 保存Skill、Route、Stage、预算、Lazy Tool和恢复状态。
- `CaseState` 保存事实、对话行为、时间线、Evidence、缺口、冲突和候选裁决。
- ToolResult通过Reducer确定性更新CaseState，LLM不能重写完整状态。
- 商品或签收附件只保留URI、摘要和大小，原始内容不进入长期上下文。
- ContextProjector每轮只投影当前Stage、精简状态、最近Observation和当前工具定义。

## 有限错误恢复

- 429、502/503/504、超时和连接重置：Model Gateway保持原请求重试一次。
- Schema、quote、speaker或message index不合法：模型获得字段级提示后修复一次。
- 业务记录不存在：生成负向Evidence，不盲目重试。
- Tool越界或Case Scope错误：拒绝执行。
- 第二次模型修复仍失败：终止当前路径并生成不完整结果。

所有尝试进入Trace，但临时错误提示不进入长期上下文。

## 快速开始

要求Python 3.11+和[uv](https://docs.astral.sh/uv/)。

```bash
uv sync --dev
uv run python -m ecom_dispute data rebuild
uv run pytest -q
uv run python -m ecom_dispute eval --mode deterministic
uv run python -m ecom_dispute web --agent-mode heuristic-test --port 8765
```

真实LLM：

```bash
export ECOM_DISPUTE_API_KEY='your-key'
uv run python -m ecom_dispute \
  --base-url 'https://your-openai-compatible-endpoint.example' \
  --model 'your-model' \
  demo --agent-mode live-llm --case-id refund_conflict_001
```

旧 `--tool-mode` 已删除。live链路固定采用核心工具确定性收集，并按条件触发EvidenceGapAgent和ReviewAgent。

## 当前评测

### 确定性回归

152/152通过。它证明构造业务数据、工具、Reducer和Strategy之间一致，不代表LLM或线上准确率。

### 真实LLM冒烟

`gpt-5.6-luna`已真实运行三个Agent角色：

| Case | Agent | Route | Decision | Input | Output | 模型延迟 |
|---|---|---|---|---:|---:|---:|
| `m6_refund_amount_001` | Conversation + EvidenceGap | refund_amount | refund_amount_incorrect | 10,145 | 379 | 26,898ms |
| `refund_conflict_001` | Conversation + Review | refund | refund_record_conflict | 10,289 | 810 | 56,795ms |

两条定向案例的Route、裁决、责任和复检符合预期。该结果是已有案例冒烟，不称为盲测准确率。详见[真实Agent冒烟报告](evals/v2_live_agent_smoke_2026-08-23.md)。

新建8条Route holdout首轮结果：Route Type与Has Dispute均为8/8，但全项Exact Match为0/8；旧事实本体无法细分商品、支付和退货事实，InteractionAct召回也偏低。Oracle未在运行后调整。详见[V2 Route Holdout报告](evals/v2_route_holdout_report_2026-08-23.md)。

随后破坏性升级Fact ontology，并使用8条全新v4 holdout首轮验证：Route与Has Dispute均为8/8，FactType-only Precision/Recall为90.9%/100%，InteractionAct P/R提升到用户88.9%/100%、客服100%/100%；全项Exact仍为2/8，剩余错误主要是`current/completed`边界。详见[V4 Fact Holdout报告](evals/v4_fact_holdout_report_2026-08-23.md)。

Temporal v5进一步删除`temporal_status`，拆分为`fact_mode + time_relation`。16条全新holdout首轮全项11/16，用户BusinessFact P/R为88.9%/94.1%，用户InteractionAct为100%/100%。详见[V5 Temporal Holdout报告](evals/v5_temporal_holdout_report_2026-08-23.md)。

v1.0发布后新建12条完整E2E案件，每个主Route一条。真实三Agent链路与共享Conversation的Core对照均为12/12，Route、Decision、Party、Review、Evidence和Tool检查全部通过；Gap/Review额外增加58,712输入Token和158.8秒累计延迟，没有提高本轮裁决准确率。详见[12-Route E2E报告](evals/v1_e2e_12route_report_2026-08-23.md)。

正式120条E2E由84个业务模板和36个表达变体组成，首轮Live/Core均为116/120（96.7%），Evidence Grounded 100%。4个失败全部来自Route边界；Gap/Review没有提高准确率，额外增加530,033输入Token和1,214秒累计延迟。详见[Formal 120 E2E报告](evals/formal_e2e_120_report_2026-08-23.md)。

共享Conversation输出的三层消融显示：GapAgent增加1条网关Evidence但不改变裁决，增量成本约4.7k输入Token；ReviewAgent增加1条复检Finding而不改确定性裁决，增量成本约4.8k输入Token。详见[V5 Agent Layer消融](evals/v5_agent_layer_ablation_report_2026-08-23.md)。

### 外部数据

ABCD正式外部集包含160条受支持对话和40条拒识对话。首轮199条有效结果中，总Route Accuracy 71.9%、受支持Route 66.7%、unsupported拒识92.5%；Action-presence代理P/R为100%/64.8%。详见[Formal ABCD 200报告](evals/formal_abcd_200_report_2026-08-23.md)。外部对话不与本项目订单硬拼成“真实案件”。

### Review人工评测

40条固定模板/ReviewAgent匿名A/B已生成，分布为5条冲突、4条证据缺失、31条合规。当前人工评分为0/40，尚不能声称ReviewAgent优于模板。评审方法见[Review A/B说明](docs/review_rubric_instructions.md)。

## 已有架构取舍

旧实验中，全量ToolQueryAgent在19个有效案例上没有提高裁决、责任、复检或工具数量，却额外消耗约21万输入Token和429秒模型延迟。因此它已被删除，不保留兼容路径。新EvidenceGapAgent只处理Route声明的长尾证据。

## 当前限制

- 业务数据主要为人工和规则构造，不是企业生产流量。
- 工具后端主要为本地SQLite，不代表远程微服务可靠性。
- 152/152是确定性回归，不是LLM准确率。
- 正式120条E2E仍包含36条同业务表达变体，并非120个完全独立业务模板。
- ABCD受支持Route准确率只有66.7%，外部分布泛化仍弱。
- Review A/B尚未完成人工评分，不能声称提升审核效率。
- 没有写操作、审批、沙箱、长期记忆、完整DAG或分布式恢复。
- 多Agent串行延迟仍高，真实复检案例累计模型延迟约57秒。

## 计划

完整实施范围、真实性边界和里程碑见[EcomDispute作品集版实施计划V2.md](EcomDispute作品集版实施计划V2.md)。

面试演示顺序见[三分钟Demo脚本](docs/demo_script.md)。
