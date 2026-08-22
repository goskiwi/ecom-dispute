# EcomDispute 项目计划

## 1. 项目定位

EcomDispute 是一个面向电商售后争议的多 Agent 证据化诊断系统。

系统输入客服与用户对话、订单号和可选的用户自述问题，通过订单、物流、支付、退款、售后和政策工具核验业务事实，输出：

- 争议类型
- 责任方与处理结论
- 对话证据和业务事实证据
- 适用政策及其版本
- 事件时间线
- 事实或结论冲突
- 证据不足项
- 建议处理动作
- 是否需要人工复检

项目是独立业务 Agent 项目，不依赖 Pico，也不复用 Pico 的 Runtime 代码。

核心架构为“稳定 Harness + 可插拔 Skill + 确定性 Evidence Fusion”：

- Harness 统一负责执行循环、CaseState、工具调度、上下文预算和轨迹记录。
- Skill 声明争议场景的排查 SOP、工具范围、必需证据、责任类型和复检条件。
- 多个专项 Agent 分别分析对话、业务事实、政策和风险。
- Evidence Fusion 由确定性代码完成去重、时间对齐、政策适用性检查、冲突标记和复检分流。

### 1.1 两段实习的融合边界

项目不复刻两段实习的原业务，而是复用其中可迁移的方法：

| 实习能力 | 项目中的实现 | 项目自己的业务问题 |
|---|---|---|
| 虫盯盯：稳定 Harness、CaseState、Tool Registry、时间线和证据链 | 统一管理售后 Case、业务查询、上下文和执行轨迹 | 如何把分散在对话与业务系统中的争议事实重建出来 |
| 虫盯盯：可插拔 Skill | 每类争议声明 SOP、允许工具、必需证据和复检条件 | 不同售后争议如何独立演进，避免统一 Prompt 膨胀 |
| SHEIN：多阶段质检与专项并行 | 对话理解、事实核验、政策选择、融合和复检分阶段执行 | 如何同时判断客服表述、系统事实和政策是否一致 |
| SHEIN：多地区策略路由 | 地区、业务场景、事件时间共同选择政策版本 | 如何避免使用当前政策误判历史订单 |
| SHEIN：规则与事实联合裁决、冲突合并 | Evidence Fusion 校验证据引用，检测退款与支付等跨源冲突 | 如何避免重复扣分、矛盾结论和无证据裁决 |

最终产品主线是“售后争议裁决”，而不是运维诊断或对话质检：系统先重建事件时间线与业务事实，再依据事发时有效政策输出建议裁决和人工复检任务。

### 1.2 当前可运行基线（2026-08-22）

仓库已完成退款与物流延迟 M4 跨 Skill 闭环：

- 订单、支付、退款、售后、物流、政策 SQLite Schema 与 60 个固定案例，其中 Refund 40 个、Delivery 20 个。
- 6 个只读业务工具、CaseState Reducer、Refund/Delivery 两个 Skill 和 Evidence Fusion。
- Conversation/Fact/Policy 三个专项任务并行，其中 Conversation Agent 支持真实 LLM 严格结构化输出；事实与政策模块当前为确定性执行器。
- 覆盖退款未发起超时、处理中、到账超时、已完成、退款/支付事实冲突、证据缺失和历史政策版本。
- 单 LLM Agent Function Calling 基线，支持并行工具调用、完整历史续轮、严格 JSON Schema、轮数预算和 Evidence 引用校验。
- LLM 将用户主张和客服承诺输出为 `business_type + has_dispute + statement_types[]`，Evidence Fusion 核验退款或送达承诺与业务事实；空查询生成独立负向 Evidence。
- 25 个自动化测试通过。

真实 LLM 首轮对照评测使用 `gpt-5.4-mini-2026-03-17`。Hybrid 最终裁决、责任方和复检分流为 20/20，语义路由为 19/20；单 Agent Function Calling 基线最终裁决为 14/20，全项通过 11/20。Baseline 使用 216,619 输入 Token、累计模型延迟 385,275 ms，分别约为 Hybrid 的 2.32 倍和 3.33 倍。全部失败结果及调用轨迹原样保留。

M3 的 40 案例真实 LLM 首轮评测中，最终裁决、责任方和复检分流均为 40/40；用户 statement type 召回 90.7%，客服承诺类型召回 97.6%，对话-事实冲突 Precision/Recall 均为 100%，全项通过 34/40。原始模型输出与 Oracle 审计后计分分开保存，不用重跑覆盖首轮结果。

M4 扩展至 60 个跨 Skill 案例。审计后 `business_type`、`has_dispute`、最终裁决、责任方和复检均为 60/60；用户/客服 statement type 召回分别为 95.7% 和 96.7%，对话-事实冲突 Precision 为 70%、Recall 为 100%，全项通过 53/60。剩余错误集中于未来、当前和完成时态混淆。

实测单次短请求仍约产生 4.7k 输入 Token。M2 前保持“一次 LLM 语义分析 + 确定性事实/政策/融合”，新增 LLM Agent 必须通过相同案例、模型和总预算的对照实验说明证据完整率或语义判断存在收益。

## 2. 版本目标

| 版本 | 目标 | 预计代码量 | 用途 |
|---|---|---:|---|
| 简历版 v0.1 | 完成可运行、可演示、可量化评测的售后裁决闭环 | 4,000～6,000 行 | 简历、GitHub 展示、面试 Demo |
| 完整版 v1.0 | 扩展为作品集级多地区售后质检与复检平台 | 8,000～12,000 行 | 深入面试、课程项目、公开演示 |

开发原则：

1. 先完成单案例事实核验闭环，再抽象 Skill 和多 Agent。
2. 只有当独立分析任务确实可以并行时才使用多 Agent。
3. 不预填准确率、降低比例或处理量，简历只使用实际评测结果。
4. 合成数据、人工编写数据和公开数据分别报告，不把模拟案例写成真实业务流量。

## 3. 总体架构

```text
售后对话 + 订单号
          |
          v
     Case Intake
   - 地区/业务类型
   - 关键事件时间
   - 可用数据范围
          |
          v
     Skill Router
   - 未收到货
   - 物流延迟
   - 退款争议
   - 重复扣款
          |
          v
   Diagnostic Harness
   - CaseState Reducer
   - Tool Registry
   - Context Budget
   - Agent Scheduler
   - Evidence Store
          |
          v
   并行专项 Agent
   - Conversation Agent
   - Fact Agent
   - Policy Agent
          |
          v
   Evidence Fusion
   - 事实去重
   - 时间对齐
   - 政策版本校验
   - 冲突检测
   - 证据完整性
          |
          v
       Risk Agent
   - 冲突与不确定性
   - 复检条件检查
   - 复检分流
          |
          v
     结构化裁决报告
```

## 4. 技术栈

### 简历版

- Python 3.11+
- Pydantic、httpx
- OpenAI-compatible Function Calling
- asyncio
- SQLite
- JSONL 诊断轨迹和 Artifact
- pytest、Ruff
- Jinja2 或 Markdown 报告

### 完整版新增

- PostgreSQL（可选；SQLite 达到容量或并发限制后再迁移）
- FastAPI 服务端渲染或 HTMX 控制台
- 批处理任务队列
- 多语言模型或翻译适配

## 5. 仓库目录

```text
ecom-dispute/
├── ecom_dispute/
│   ├── contracts.py
│   ├── harness.py
│   ├── case_state.py
│   ├── reducer.py
│   ├── intake.py
│   ├── skill_registry.py
│   ├── tool_registry.py
│   ├── scheduler.py
│   ├── fusion.py
│   ├── recheck.py
│   ├── report.py
│   └── persistence.py
├── agents/
│   ├── conversation.py
│   ├── fact.py
│   ├── policy.py
│   └── risk.py
├── skills/
│   ├── not_received/
│   ├── delivery_delay/
│   ├── refund_dispute/
│   └── duplicate_charge/
├── tools/
│   ├── orders.py
│   ├── logistics.py
│   ├── payments.py
│   ├── refunds.py
│   ├── after_sales.py
│   └── policies.py
├── data/
│   ├── schema.sql
│   ├── policies/
│   └── cases/
├── generators/
├── evals/
├── tests/
├── scripts/
├── web/                 # v1.0
├── pyproject.toml
└── README.md
```

# 第一部分：简历版 v0.1

## 6. 业务数据与自然工具

### 6.1 SQLite 业务表

```text
orders
logistics_events
payments
refunds
after_sales_cases
policies
conversations
```

每条数据使用稳定业务主键和事件时间。政策使用生效时间范围区分版本，确保评测能检查系统是否选择了事件发生时的有效政策。

同一条业务记录无论被哪个 Agent 查询，都必须映射为相同的 Evidence ID。Evidence ID 由数据源、业务主键和记录版本组成，用于跨 Agent 引用和融合去重。

### 6.2 工具

```text
get_order(order_id)
get_logistics_events(order_id)
get_payment_records(order_id)
get_refund_records(order_id)
get_after_sales_case(order_id)
read_policy(region, business_type, effective_at)
```

所有工具是只读业务查询，返回：

- Evidence ID
- 数据源和表名
- 查询条件
- 业务主键
- 事件时间
- 结构化事实
- 面向模型的简短摘要

读取工具只对明确的短暂性技术错误执行有限重试；业务空结果、参数错误和记录不存在作为结构化结果返回，不盲目重试。

Harness 为只读工具提供 Case 级共享查询缓存。同一 Case 中参数完全相同的查询复用同一事实快照和 Evidence ID，减少多 Agent 重复查询；不同参数、数据版本或 Case 之间不复用结果。

### 6.3 政策数据

政策以结构化规则和原文摘要共同保存：

```text
policy_id
version
region
business_type
effective_from
effective_to
conditions
required_evidence
allowed_decisions
recommended_actions
source_summary
```

代码确定性检查地区、业务类型和生效时间；模型负责理解对话语义、判断候选条件是否满足并引用原文摘要。政策工具不得返回评测标准答案。

## 7. 核心数据合同

### 7.1 CaseState

```text
case_id
user_claims
agent_commitments
timeline
confirmed_facts
policy_rules
candidate_decisions
evidence
conflicts
missing_evidence
pending_queries
review_status
final_decision
```

LLM 负责提取语义、选择下一步查询和提出候选结论；Reducer 根据工具结果和结构化 Finding 更新 CaseState。

### 7.2 Finding

```text
finding_id
category
claim
evidence_ids
policy_rule_ids
supports_decision
conflicts_with
missing_evidence
severity
review_recommended
```

### 7.3 DecisionReport

```text
case_id
dispute_type
responsible_party
decision
timeline
conversation_evidence
business_evidence
policy_evidence
conflicts
missing_evidence
recommended_action
review_required
```

## 8. Harness

Harness 负责：

- Function Calling 合同与 Tool Registry
- Pydantic 参数 Schema
- CaseState Reducer
- Skill 路由
- 工具调度、Case 级查询缓存和有限预算
- 并行 Agent 任务调度
- 诊断轨迹和 Artifact
- Evidence Fusion
- 复检分流
- DecisionReport 生成

首版不实现：

- 任意动态代码插件
- 多 Provider 兼容层
- 通用工作流平台
- 分布式 Worker
- 业务写入和自动退款

## 9. Skill

### 9.1 未收到货

- 核验对话中的用户主张和客服承诺
- 查询物流时间线和签收证据
- 区分未签收、虚假签收、签收证据不足和用户否认
- 缺少关键物流证据时进入人工复检

### 9.2 物流延迟

- 对齐承诺送达时间、物流事件和当前时间
- 判断是否超过政策阈值
- 区分平台、商家、物流方和不可抗力责任

### 9.3 退款争议

- 查询售后申请、退款事件和支付记录
- 核验客服承诺与系统事实是否一致
- 区分未发起、审核中、退款成功和到账延迟
- 根据事件时间选择正确政策版本

### 9.4 重复扣款

- 区分多次支付尝试、预授权、真实扣款和撤销
- 核验同一订单的支付与退款记录
- 证据不足时要求补充支付流水或人工复检

每个 Skill 声明：

- 适用场景
- 排查 SOP
- 允许工具
- 必需证据
- 责任分类
- 政策要求
- 停止条件
- 人工复检条件

Skill 只能收窄 Harness 已提供的工具集合，不能改变 Harness 的执行逻辑或执行任意代码。

## 10. 多 Agent 与结果融合

### 10.1 Agent 职责

- Conversation Agent：提取用户主张、客服承诺、争议对象和对话证据。
- Fact Agent：通过工具核验订单、物流、支付、退款和售后事实。
- Policy Agent：根据地区、业务类型和事件时间选择政策版本并提取适用条款。
- Risk Agent：在 Evidence Fusion 之后检查证据缺失、事实冲突、责任不确定性和复检条件，不参与前置并行分析。

### 10.2 五阶段流程

1. Intake & Routing：确定地区、业务类型、关键事件时间和可用数据范围，再选择 Skill 和专项 Agent。
2. Parallel Analysis：Conversation、Fact 和 Policy Agent 并行执行。
3. Finding Validation：检查输出 Schema、Evidence ID 和政策引用。
4. Evidence Fusion：去重、时间对齐、规则适用和冲突标记。
5. Risk & Recheck：Risk Agent 检查融合结果，缺失证据时发起限定补充查询或转人工复检。

### 10.3 确定性融合

代码负责：

- 相同 Evidence ID 和同一业务事件去重
- 对话、物流、支付和退款时间线对齐
- 政策生效时间与业务事件时间检查
- 相互矛盾事实标记
- 无证据结论过滤
- Skill 必需证据完整性检查
- 复检任务生成

确定性代码只验证结构化事实和可计算约束，不代替模型理解用户否认、客服承诺或责任语义。责任归属和业务语义由模型提出候选判断，但最终报告不得引用不存在的证据或失效政策。

## 11. 评测数据

### 11.1 v0.1 案例构成

目标建设 120 个固定案例。案例随系统能力分阶段扩展：M1 完成 1 个端到端手工案例，M2 扩展到 20 个，M3 扩展到 40 个，M4 在融合逻辑稳定后扩展到 120 个。

| 预期结果 | 数量 |
|---|---:|
| 无争议或客服处理正确 | 20 |
| 证据充足、可明确裁决 | 60 |
| 政策版本或边界条件案例 | 20 |
| 证据冲突或必须人工复检 | 20 |

数据来源分开标注：

- 规则生成案例：覆盖边界条件和已知根因。
- 人工编写案例：覆盖口语化对话、模糊表达和多轮承诺。
- 公开数据适配案例：若找到许可和字段匹配的数据，单独报告评测；不把其作为 v0.1 完成的硬依赖。

每个案例保存：

```text
case_id
conversation
business_records
policy_version
expected_dispute_type
expected_responsible_party
required_evidence
expected_review_required
```

真实标签仅供评测器使用，不进入 Prompt、Skill 或工具返回。系统输入不提供标准争议类型，只允许包含用户在自然对话中表达的问题或外部渠道给出的非可信自述分类。

### 11.2 数据生成与评测隔离

- 案例生成器只负责生成对话、业务记录和政策环境，不向运行数据写入标准答案。
- Oracle 单独保存预期争议类型、责任方、必需证据和复检标签，只能由评测器读取。
- Skill 只包含排查 SOP、工具范围和证据要求，不包含具体案例的责任方或裁决结果。
- 规则生成案例与人工编写案例分别统计；人工案例重点覆盖模糊表达、多轮承诺、时间边界、事实冲突和必须复检场景。
- 120 个案例中至少保留 30 个独立人工编写案例，避免指标仅反映生成模板匹配能力。

### 11.3 评测指标

- Skill 路由准确率
- 争议类型 Precision/Recall/F1
- 责任方准确率
- 政策版本选择准确率
- 必需证据完整率
- 无证据裁决率
- 重复 Finding 比例
- 人工复检 Precision/Recall
- 平均工具调用数
- Token 消耗和处理延迟

### 11.4 对照实验

v0.1 使用相同案例、模型配置和总工具预算比较：

- 单 Agent + 统一 Prompt
- 多 Agent + 确定性 Evidence Fusion

完整版再增加：

- 无 Skill 统一规则 vs Skill 路由
- 多 Agent + LLM 直接合并 vs 多 Agent + 确定性融合

对照用于回答具体问题：Skill 是否改善争议路由？多 Agent 是否提高证据完整度？确定性融合是否降低重复和无证据结论？如果没有改善，如实保留结果。

## 12. v0.1 实施里程碑

### M1：数据模型与工具闭环

交付：

- 独立 Git 仓库和 Python 工程
- SQLite Schema 和数据种子
- 六个业务查询工具
- 一个手工编写的端到端售后案例

验收：可以从对话和订单号出发，通过工具查到全部裁决事实；Prompt 中不直接注入标准答案。

### M2：单 Agent Harness 与 CaseState

交付：

- Function Calling 执行循环
- Tool Registry 和结构化错误
- CaseState/Reducer
- 诊断轨迹和 DecisionReport
- 未收到货、退款争议两个完整场景
- 20 个固定案例，其中包含正常、明确裁决和人工复检案例

验收：单 Agent 可通过真实工具查询完成责任判断，报告的每项关键结论都能定位到 Evidence ID。

### M3：四个 Skill 与 40 个固定案例

交付：

- Skill Contract/Registry/Router
- 四个售后 Skill
- 案例生成器
- 40 个固定案例，其中至少 10 个独立人工编写案例
- 单 Agent 评测报告

验收：案例可从清洁数据库重建，所有指标由评测脚本生成，正常案例能用于测量误报。

### M4：多 Agent 与 Evidence Fusion

交付：

- Conversation/Fact/Policy/Risk Agent
- Finding Schema 校验
- 事实去重、时间对齐和政策版本检查
- 冲突标记和人工复检分流
- 扩展至 120 个固定案例，其中至少 30 个独立人工编写案例
- 单 Agent/多 Agent 对照报告

验收：全部 120 个案例进入评测；报告明确列出多 Agent 的指标收益和额外 Token/延迟开销；无证据 Finding 不进入最终裁决。

### M5：简历交付

交付：

- pytest 和 Ruff 通过
- JSON 和 Markdown 评测报告
- README、架构图和数据说明
- 一键数据重建、Demo 和评测脚本
- 一份成功裁决报告
- 一份误判或复检失败分析
- 简历文案和面试讲解大纲

## 13. v0.1 验收命令

```bash
python -m ecom_dispute.data rebuild
python -m ecom_dispute demo --case-id refund_conflict_001
python -m ecom_dispute.eval --mode single
python -m ecom_dispute.eval --mode multi
pytest -q
ruff check .
```

验收要求：

- 从清洁环境可重建全部业务数据和案例。
- 评测同时生成 JSON 和 Markdown 报告。
- 所有 120 个案例均进入报告，不选择性重跑失败任务。
- 模拟数据、人工数据和公开数据的指标分开展示。
- 简历只使用报告实际生成的数字。

# 第二部分：完整版 v1.0

## 14. v1.0 扩展范围

### 14.1 地区、语言和政策版本

扩展至：

- 3 个地区的差异化政策
- 2 种语言的对话
- 政策发布、生效和失效时间
- 同一争议在不同地区的不同裁决路径

评测单独报告跨地区和跨语言结果，不用总体均值掩盖某个地区的低质量结果。

### 14.2 更多业务场景

新增 Skill：

- 商品破损或缺件
- 退货入库争议
- 优惠券和运费争议
- 售后申请未闭环

扩展业务工具，但优先从既有数据表组合查询；只有在存在新的业务事实来源时才新增工具。

### 14.3 持久任务与批处理

实现：

- 持久 Case 状态
- 批量任务创建
- 并发度和 Token 预算
- 任务失败重试
- 人工复检队列
- 复检后重新裁决
- 诊断轨迹和报告查询

自动重试仅用于无副作用的读取工具短暂失败；裁决失败、证据不足和业务空结果不通过重试隐藏。

### 14.4 人工复检与反馈

人工可以：

- 确认或修改责任方
- 补充业务证据
- 选择正确政策条款
- 标记无法自动裁决原因
- 将失败 Case 加入固定评测集

人工反馈作为后续评测数据，不自动改写生产 Skill 或政策规则。

### 14.5 Web 控制台

页面包括：

- Case 列表和批处理状态
- 对话、业务记录和事件时间线
- Agent 执行轨迹
- 工具调用和 Evidence 详情
- 政策版本和引用条款
- 候选结论和冲突
- 人工复检操作
- 单 Agent/多 Agent 对照结果

系统仍只生成建议裁决，不直接调用真实退款、扣款或优惠券发放接口。

### 14.6 完整评测

扩展至 300～500 个固定案例，并按以下维度分层报告：

- 数据来源
- Skill
- 地区
- 语言
- 政策版本
- 明确裁决/人工复检
- 证据完整/证据冲突

真实模型评测与确定性机制测试分开报告。若成本允许，关键案例重复运行三次并报告波动；否则明确标注单次结果。

## 15. v1.0 实施里程碑

### M6：地区、语言和政策版本

- 建设三地区差异政策。
- 增加第二语言对话。
- 建立跨地区和跨语言评测分层。

### M7：场景扩展与批处理

- 扩展至 8 个 Skill。
- 实现持久 Case、批量任务和预算控制。
- 增加人工复检队列。

### M8：控制台和反馈闭环

- 完成 Web 控制台。
- 展示时间线、Evidence、政策引用和 Agent 轨迹。
- 完成人工复检和失败案例回收。

### M9：规模化评测

- 扩展至 300～500 个案例。
- 完成四组对照模式。
- 生成分层指标、成本报告和失败分类。

### M10：作品集发布

- 完成一键数据重建和本地部署。
- 发布演示视频、架构文档和评测报告。
- 保留全部失败案例和已知限制。

## 16. 代码量估算

### v0.1

| 部分 | 预计代码量 |
|---|---:|
| 数据模型、SQLite 和生成器 | 600～900 行 |
| Harness、CaseState 和 Tool Registry | 900～1,300 行 |
| 六个业务工具 | 350～550 行 |
| 四个 Skill 和路由 | 400～650 行 |
| 多 Agent 与 Evidence Fusion | 600～900 行 |
| 评测、报告和脚本 | 600～900 行 |
| 自动化测试 | 900～1,300 行 |
| 合计 | 4,000～6,000 行 |

### v1.0

| 部分 | 预计代码量 |
|---|---:|
| 业务数据、生成器和政策系统 | 1,200～1,800 行 |
| Harness、持久任务和批处理 | 1,500～2,200 行 |
| 八个 Skill 和业务工具 | 1,200～1,800 行 |
| 多 Agent、融合与复检 | 1,000～1,500 行 |
| API 和 Web 控制台 | 1,000～1,600 行 |
| 评测、报告和案例 | 1,200～1,800 行 |
| 自动化测试 | 1,800～2,600 行 |
| 合计 | 8,000～12,000 行 |

## 17. 风险与控制

### 风险 1：变成对话分类器

控制：裁决必须查询业务事实和政策，评测单独计算业务事实核验和必需证据完整率。

### 风险 2：多 Agent 只是多个 Prompt

控制：每个 Agent 使用不同信息源、工具范围和输出合同，并与相同总预算的单 Agent 模式对照。

### 风险 3：全是自己生成的数据

控制：清晰区分规则生成、人工编写和公开数据；对关键边界案例进行人工复核，并分数据来源报告指标。

### 风险 4：LLM 融合时无证据总结

控制：Evidence ID、政策引用、时间窗口、去重、冲突和必需证据检查由确定性代码完成。

### 风险 5：裁决场景过度自动化

控制：系统只输出建议裁决，冲突、缺失证据和责任不确定案例进入人工复检，不调用真实资金或账户写入接口。

## 18. 简历文案模板

完成 v0.1 并生成真实评测后，根据报告改写：

> EcomDispute - 基于可插拔 Skill 的多 Agent 电商售后争议证据化诊断系统

- 设计“稳定 Harness + 可插拔 Skill”的售后诊断架构，Harness 统一负责执行循环、CaseState 投影、工具调度和诊断轨迹，Skill 声明争议 SOP、工具范围、必需证据、责任类型和复检条件。
- 建设订单、物流、支付、退款、售后和政策六类结构化工具，Reducer 将工具结果确定性更新为用户主张、客服承诺、业务事实、政策条款和事件时间线。
- 将诊断拆分为对话、事实、政策和风险四类 Agent，通过统一 Finding Schema 和确定性 Evidence Fusion 完成事实去重、时间对齐、政策版本检查、冲突标记和证据不足复检。
- 构建 `N` 个固定售后案例，在统一模型和工具预算下实现争议类型 F1 `A`、责任方准确率 `B%`、必需证据完整率 `C%`和人工复检召回率 `D%`。

`N`/`A`/`B`/`C`/`D` 必须替换为实际评测数据，不得预填。

## 19. 最终交付清单

### v0.1

- 独立可运行仓库
- SQLite 业务数据和一键重建
- 六类自然业务工具
- 四个 Skill
- 单 Agent 和四专项 Agent 模式
- CaseState、Finding 和 DecisionReport
- 确定性 Evidence Fusion
- 120 个固定案例
- JSON/Markdown 评测报告
- 测试、README、架构图和 Demo

### v1.0

- 8 个 Skill
- 3 个地区、2 种语言和版本化政策
- 持久 Case、批处理和人工复检
- Web 控制台
- 300～500 个固定案例
- 分层评测和对照实验
- 公开 Demo、评测报告和已知限制
