# EcomDispute 作品集版实施计划 V2

> **Legacy Ontology V2**：本文件保留为演进记录，不再是当前实现依据。V3唯一合同见根目录`EcomDispute-Route本体与能力边界V3.md`。

## 0. 文档目的

本文档用于指导 EcomDispute 从当前退款/物流争议原型，升级为可用于校招、实习面试和 GitHub 作品集展示的电商争议 Agent 系统。

项目融合两类可迁移工程方法：

- Robotaxi 运维诊断 Agent：稳定 Harness、可插拔 Skill、受控 Tool Runtime、Reducer CaseState、大结果卸载、证据链与 Trace。
- SHEIN 客服质检 Agent：多阶段任务拆分、并行质检思路、规则与事实联合裁决、冲突合并和人工复检。

本计划描述的是后续准备实现的作品集版本，不将规划能力表述为已经完成。

---

## 1. 项目定位

EcomDispute 是一个面向电商售后争议的 LLM 增强型证据化分析与辅助裁决系统。

系统输入：

- 用户与客服对话；
- 订单号和事发时间；
- 地区与业务上下文；
- 可选的图片、签收证明或商品附件。

系统通过订单、商品、支付、退款、售后、物流、签收、仓库和政策等只读工具核验事实，最终输出：

- 主争议类型；
- 业务事实与交互行为；
- 适用政策；
- 责任方与建议处理结论；
- 关键时间线；
- 证据引用；
- 跨数据源冲突；
- 客服合规问题；
- 证据缺口；
- 人工复检任务；
- 完整执行 Trace。

项目定位为：

> 可运行、可回放、可评测的电商争议 Agent Harness 作品集，不宣称生产级平台或线上业务准确率。

---

## 2. 作品集版本目标

### 2.1 规模目标

| 维度 | 目标 |
|---|---:|
| 领域 Skill Pack | 4 个 |
| 业务 Route | 15 个 |
| 只读业务 Tool | 14 个左右 |
| 真实 LLM Agent | 3 个 |
| 执行/质检 Stage | 5 个 |
| 项目内案例 | 150～200 个 |
| 外部客服对话 | 30～50 条 ABCD 子集 |
| 有效源代码 | 10,000～13,000 行 |
| Skill/YAML/说明资源 | 2,000～3,000 行 |

### 2.2 质量目标

- 所有 LLM Agent 都在 live 模式调用真实模型，不使用关键词逻辑冒充 Agent。
- 所有业务结论必须引用 CaseState 中真实存在的 Evidence。
- 核心业务事实由只读工具产生，模型不能自由编造。
- 金额、时间、SLA、政策版本和责任规则由确定性代码计算。
- 每个 Route 拥有独立证据计划、决策策略、复检条件和测试案例。
- 模型调用、工具调用、错误恢复、状态变化和最终结论均可回放。
- 合成数据、人工构造数据和外部公开数据分别报告。
- 首轮真实 LLM 结果与后续调优结果分开保存，不修改 Oracle 刷分。

---

## 3. 总体架构

```text
对话 + 订单号 + 地区 + 事发时间 + 可选附件
                       |
                       v
                 ROUTE Stage
             ConversationAgent
          识别主争议与客服合规任务
                       |
                       v
                  Task Splitter
            +-----------------------+
            |                       |
            v                       v
      主争议 SubCase          客服合规 SubCase
    独立 Skill/Route          独立 Skill/Route
    独立 Tool Surface         独立 Tool Surface
            |                       |
            +-----------+-----------+
                        v
                  ANALYZE Stage
          BusinessFact / InteractionAct
                        |
                        v
                   VERIFY Stage
       固定核心工具 + 按需 EvidenceGapAgent
                        |
                        v
                   DECIDE Stage
        Route Decision Strategy 确定性裁决
                        |
                        v
              FUSE_AND_REVIEW Stage
       Evidence Fusion + 按需 ReviewAgent
                        |
                        v
        DecisionReport + ReviewTask + Trace
```

### 3.1 核心原则

> 模型负责开放性理解和长尾判断，框架负责确定性执行、状态、安全边界和恢复。

LLM 负责：

- 理解自然语言；
- 提取可核验业务事实；
- 识别客服承诺、解释、建议和动作；
- 在存在多个长尾补查方向时选择工具；
- 将复杂冲突组织成人工复检材料。

代码负责：

- Skill、Route 和 Stage 加载；
- 当前 Tool Surface 计算；
- Case 参数绑定；
- JSON Schema 与范围校验；
- 核心证据稳定收集；
- ToolResult 标准化；
- Reducer 状态更新；
- 金额、时间、SLA 和政策计算；
- 冲突合并与最终裁决；
- 错误恢复、预算和 Trace。

---

## 4. Harness 五阶段

### 4.1 ROUTE

职责：

- ConversationAgent 分析用户和客服对话；
- 输出候选业务 Route；
- 识别是否需要同时创建客服合规子任务；
- Runtime 校验候选 Route 是否已注册。

### 4.2 ANALYZE

职责：

- 提取 `business_facts[]`；
- 提取 `interaction_acts[]`；
- 保留逐字 quote 和 message index；
- 检查 quote、speaker 和消息位置是否一致；
- 不把查询、建议、解释和正在处理误写成业务事实。

### 4.3 VERIFY

职责：

- 代码并行查询 Route 必需的核心证据；
- Result Adapter 将 ToolResult 转成 StateDelta；
- Reducer 更新 CaseState；
- 检查 Evidence Gap 和跨数据源冲突；
- 只有存在多个补查方向时才调用 EvidenceGapAgent；
- EvidenceGapAgent 只能使用当前 Route 的 Lazy Tool。

### 4.4 DECIDE

职责：

- 选择事发时有效的政策；
- 执行对应 Route 的 Decision Strategy；
- 计算金额、时限、SLA 和责任方；
- 输出候选结论、建议动作和复检条件；
- 不允许 LLM 自由决定确定性业务规则。

### 4.5 FUSE_AND_REVIEW

职责：

- 校验所有 Finding 的 Evidence ID；
- 合并重复 Finding；
- 检测主争议与客服合规结果冲突；
- 检查必需证据完整性；
- 决定是否创建 ReviewTask；
- 复杂冲突时调用 ReviewAgent 生成复检摘要和问题。

---

## 5. Skill Pack 与 Route

### 5.1 `funds-dispute`

处理支付和退款相关争议。

Routes：

1. `refund-status`
2. `refund-amount-mismatch`
3. `duplicate-charge`
4. `payment-captured-order-failed`

核心证据：

- ORDER
- PAYMENT
- REFUND
- AFTER_SALES
- PAYMENT_GATEWAY_EVENT
- POLICY

主要责任类型：

- merchant
- platform
- payment_channel
- user
- none
- undetermined

### 5.2 `fulfillment-dispute`

处理订单履约和物流相关争议。

Routes：

5. `merchant-not-shipped`
6. `delivery-delay`
7. `delivered-not-received`
8. `cancellation-in-transit`

核心证据：

- ORDER
- LOGISTICS
- DELIVERY_PROOF
- DELIVERY_ADDRESS
- CANCELLATION_REQUEST
- AFTER_SALES
- POLICY

主要责任类型：

- merchant
- logistics_provider
- platform
- user
- force_majeure
- none
- undetermined

### 5.3 `item-after-sales`

处理商品、退货和图片凭证争议。

Routes：

9. `return-eligibility`
10. `wrong-item`
11. `missing-item`
12. `damaged-item`

核心证据：

- ORDER_ITEM
- RETURN_REQUEST
- WAREHOUSE_PACK_RECORD
- CLAIM_ATTACHMENT
- LOGISTICS
- POLICY

主要责任类型：

- merchant
- warehouse
- logistics_provider
- user
- platform
- none
- undetermined

### 5.4 `service-compliance`

处理客服表述、承诺和升级流程合规问题。

Routes：

13. `false-business-statement`
14. `unsupported-promise`
15. `missing-required-escalation`

核心证据：

- CONVERSATION
- BUSINESS_FACT
- INTERACTION_ACT
- SERVICE_POLICY
- 主争议子任务的核验结果

输出：

- 合规 Finding；
- 严重程度；
- 扣分建议；
- 冲突 Evidence；
- 是否需要人工复检。

---

## 6. Skill 资源与 Python 逻辑边界

### 6.1 文件职责

```text
SKILL.md
→ 给模型和开发者阅读的业务总说明

skill.yaml
→ Runtime 读取的 Skill 能力上限和 Route 索引

route.yaml
→ Route、Stage、工具面、证据要求和输出范围

stage.md
→ 按需加载的当前阶段模型说明

tool.yaml
→ 工具 Schema、Scope、错误映射和实现绑定

Python
→ Strategy、Executor、Adapter、Reducer、Fusion 和恢复逻辑
```

### 6.2 YAML 允许包含

- ID、名称和描述；
- Tool ID 引用；
- Route 列表；
- Stage 结构；
- `agent` / `deterministic` 执行模式；
- `core_tools`、`lazy_tools`；
- required/optional evidence；
- allowed decisions；
- Strategy、Executor 和 Adapter ID；
- Scope 绑定；
- 原始错误映射；
- 轮数、工具和恢复预算。

### 6.3 YAML 禁止包含

- 任意 Python 代码；
- 复杂表达式 DSL；
- 金额和 SLA 计算逻辑；
- 数据库连接；
- 模型密钥；
- 动态权限对象；
- 责任裁决实现；
- Reducer 逻辑；
- 任意 Hook 脚本。

### 6.4 Route Stage 示例

```yaml
stages:
  ANALYZE:
    mode: agent
    objective: 提取用户否认收货和客服相关表述
    instruction_file: stages/analyze.md
    default_next: VERIFY

  VERIFY:
    mode: deterministic
    objective: 查询订单、物流和事发时政策
    tools:
      - get_order
      - get_logistics_events
      - read_policy
    default_next: CHECK_GAPS

  CHECK_GAPS:
    mode: deterministic
    objective: 判断是否需要签收证明或地址证据
    default_next: RESOLVE_GAPS

  RESOLVE_GAPS:
    mode: agent
    objective: 只补充当前仍然缺失的长尾证据
    visible_tools:
      - tool_search
    default_next: DECIDE

  DECIDE:
    mode: deterministic
    objective: 执行责任裁决
    default_next: FUSE_AND_REVIEW
```

---

## 7. 三个真实 LLM Agent

### 7.1 ConversationAgent

输入：原始对话。

输出：

- candidate routes；
- business facts；
- interaction acts；
- uncertainty。

约束：

- 严格结构化输出；
- quote 必须逐字来自原消息；
- message index 必须合法；
- 不推测订单、支付、物流和政策事实。

### 7.2 EvidenceGapAgent

触发条件：

- 核心证据不完整；
- 数据源互相冲突；
- 当前 Route 存在两个以上可选补查方向。

能力边界：

- 只能搜索和调用当前 Route 的 Lazy Tool；
- 只能收集证据；
- 不能决定最终责任方；
- 不能修改已确认业务事实。

### 7.3 ReviewAgent

触发条件：

- 多 Skill 结果冲突；
- 业务记录互相矛盾；
- 证据不足但需要人工继续处理；
- 政策无法唯一适用。

输出：

- conflict summary；
- cited evidence IDs；
- review questions；
- recommended manual action；
- priority。

ReviewAgent 不得覆盖确定性 Strategy 的已确认事实。

---

## 8. Tool Registry 与 Tool Runtime

### 8.1 工具列表

1. `get_order`
2. `get_order_items`
3. `get_payment_records`
4. `get_payment_gateway_events`
5. `get_refund_records`
6. `get_after_sales_case`
7. `get_logistics_events`
8. `get_delivery_proof`
9. `get_delivery_address`
10. `get_cancellation_request`
11. `get_return_request`
12. `get_warehouse_pack_record`
13. `get_claim_attachments`
14. `read_policy`

### 8.2 ToolDefinition

每个 `tool.yaml` 声明：

- tool_id；
- name 和 description；
- input/output JSON Schema；
- timeout；
- Scope 绑定；
- Executor ID；
- Result Adapter ID；
- 原始错误到 Canonical Error 的映射。

### 8.3 Case Scope

以下参数优先由 Runtime 注入：

- order_id；
- case_id；
- region；
- business_type；
- effective_at。

模型不应重复生成已在 CaseInput 中确定的身份参数。

### 8.4 Tool Surface

```text
Current Tool Surface
=
当前 Stage 工具
+ 已通过 Tool Search 加载的 Lazy Tool
+ 必要 Harness 内置工具
∩ 当前 Skill 工具上限
```

Tool Search 的范围必须限制为：

```text
当前 Route.lazy_tools
- 已加载工具
```

不能搜索整个全局 Registry。

### 8.5 内置工具

- `tool_search`
- `read_evidence`（仅存在外置证据时开放）

---

## 9. CaseState、Evidence 与上下文

### 9.1 AgentRunState

描述 Agent 如何运行：

- 当前 Skill；
- 当前 Route；
- 当前 Stage；
- 当前轮数；
- 工具调用次数；
- 已加载 Lazy Tool；
- RecoveryState；
- 当前状态。

### 9.2 CaseState

描述案件已经确认了什么：

- subject；
- business facts；
- interaction acts；
- confirmed business records；
- timeline；
- evidence；
- evidence gaps；
- conflicts；
- candidate decisions；
- review reasons。

### 9.3 Result Adapter 与 Reducer

```text
Raw ToolResult
→ ToolResultEnvelope
→ Result Adapter
→ StateDelta
→ CaseStateReducer
→ New CaseState
```

LLM 不得自由重写整个 CaseState。

### 9.4 Context Projector

每轮只投影：

1. 稳定 System Instructions；
2. 当前 Skill 摘要；
3. 当前 Route 和 Stage 说明；
4. 用户原始问题；
5. 精简 CaseState；
6. 最近 Observation 或临时修复提示；
7. 当前 Tool Surface。

不长期携带：

- 所有历史 ToolResult；
- 所有 Skill；
- 所有工具 Schema；
- 完整大附件；
- 原始异常堆栈；
- 已完成 Stage 的长篇说明。

### 9.5 Evidence Store

只有以下真实大结果进入 Evidence Store：

- 商品或签收图片；
- 长政策原文；
- 大量物流轨迹；
- 仓库或支付网关长记录；
- 用户上传的附件。

普通 SQLite 结构化记录直接进入 CaseState，不为小结果额外外置。

---

## 10. 错误恢复

### 10.1 模型网关瞬时错误

以下错误保持相同请求自动重试一次：

- HTTP 429；
- HTTP 502/503/504；
- Timeout；
- Connection Reset；
- 临时网络不可用。

HTTP 400、401、403、模型不存在和 Schema 配置错误不重试。

### 10.2 模型合同修复

以下错误允许模型修复一次：

- 输出不满足 JSON Schema；
- quote 不是原文；
- message index 越界；
- speaker 不匹配；
- Evidence ID 不存在；
- 最终 Finding 无法在 CaseState 中定位。

第二次失败后生成 INCOMPLETE 结果并转人工复检。

### 10.3 精简 Canonical Error

- MODEL_TRANSIENT_FAILURE
- MODEL_OUTPUT_INVALID
- MODEL_GROUNDING_INVALID
- TOOL_NOT_ALLOWED
- TOOL_ARGUMENT_INVALID
- CASE_SCOPE_VIOLATION
- BUSINESS_NOT_FOUND
- PARTIAL_RESULT
- INTERNAL_ERROR

### 10.4 恢复责任

```text
瞬时模型/远程工具错误
→ Runtime 使用原请求或原参数重试一次

模型输出或参数错误
→ 精简 Repair Hint，模型修复一次

业务记录不存在
→ 负向 Evidence，Reducer 更新 CaseState

Scope 或硬边界错误
→ 拒绝执行，不重试

内部实现错误
→ 停止当前路径并输出不完整报告
```

恢复策略使用类型化 Python 实现，不建设通用 `recovery-policy.yaml`。

---

## 11. 多 Skill 子任务与结果融合

同一个案件可以同时产生：

```text
主争议 SubCase
+
客服合规 SubCase
```

例如：

```text
funds-dispute/refund-status
+
service-compliance/unsupported-promise
```

每个 SubCase 保持独立的：

- skill_id；
- route_id；
- AgentRunState；
- Tool Surface；
- Evidence要求；
- Finding；
- Token预算；
- Trace片段。

Fusion 负责：

- 校验 Evidence 引用；
- 去除重复 Finding；
- 合并同源事实；
- 保留不同维度结论；
- 检测冲突；
- 生成统一 DecisionReport；
- 创建人工 ReviewTask。

---

## 12. 数据模型

计划保留或新增：

```text
cases
orders
order_items
payments
payment_gateway_events
refunds
after_sales_cases
logistics_events
delivery_proofs
delivery_addresses
cancellation_requests
return_requests
warehouse_pack_records
claim_attachments
policies
service_policies
review_tasks
trace_events
evidence_records
```

当前嵌入 `repository.py` 的种子案例迁移到：

```text
data/cases/
├── funds/
├── fulfillment/
├── item/
└── compliance/
```

Repository 只负责数据访问和数据库重建，不继续承载大量案例常量。

---

## 13. Trace

至少记录：

- TASK_STARTED
- ROUTE_SELECTED
- SUBCASE_CREATED
- SKILL_ACTIVATED
- STAGE_ENTERED
- TOOL_SURFACE_RESOLVED
- MODEL_CALL_STARTED
- MODEL_CALL_FINISHED
- MODEL_RETRY_STARTED
- MODEL_OUTPUT_INVALID
- MODEL_REPAIR_TRIGGERED
- TOOL_SEARCHED
- TOOL_CALL_REJECTED
- TOOL_CALL_STARTED
- TOOL_CALL_FAILED
- TOOL_RETRY_STARTED
- TOOL_CALL_FINISHED
- EVIDENCE_STORED
- CASE_STATE_UPDATED
- DECISION_CREATED
- RESULTS_FUSED
- REVIEW_TASK_CREATED
- TASK_COMPLETED
- TASK_INCOMPLETE

每个事件保存必要的：

- case/subcase/trace ID；
- skill/route/stage；
- model；
- tool；
- token；
- latency；
- status/error；
- state diff；
- evidence refs。

不建设复杂分布式 Span 平台，先使用顺序事件时间线。

---

## 14. 评测体系

### 14.1 Router 与语义评测

- Skill/Route Accuracy；
- BusinessFact Precision/Recall/F1；
- InteractionAct Precision/Recall/F1；
- quote grounding 通过率；
- 模型修复成功率。

### 14.2 端到端裁决评测

- Decision Accuracy；
- Responsible Party Accuracy；
- Review Precision/Recall；
- Evidence Completeness；
- Evidence Grounded Rate；
- 冲突检测 Precision/Recall；
- 全项 Exact Match。

### 14.3 Harness 可靠性评测

- 网络瞬时错误恢复率；
- 模型结构错误修复率；
- Tool参数错误修复率；
- Scope越界拦截率；
- 不完整报告生成率；
- 无限循环次数；
- Trace完整率。

### 14.4 成本与延迟

- 平均输入/输出 Token；
- 平均模型调用次数；
- 平均 Tool Calls；
- P50/P95 延迟；
- Gap Agent 增量成本；
- ReviewAgent 增量成本。

### 14.5 消融实验

1. 固定条件补查 vs EvidenceGapAgent；
2. 无 ReviewAgent vs ReviewAgent；
3. 全量工具注入 vs 动态 Tool Surface；
4. 完整历史 ToolResult vs CaseState 投影；
5. 无恢复 vs 有限恢复。

如果某个 LLM Agent 没有产生收益，默认链路不强行保留，但保留负向实验和分析。

---

## 15. 数据集计划

### 15.1 项目内案例

每个 Route 目标：

- 6～8 个常规案例；
- 2～3 个边界案例；
- 2～3 个冲突或证据不足案例。

总量：150～200 个。

### 15.2 外部数据

从 ABCD 选择与退款、退货、物流、承诺和升级相关的 30～50 条对话。

只用于：

- 对话理解外部分布评测；
- InteractionAct 与 Action 识别；
- Route泛化检查。

不把 ABCD 对话与项目订单数据拼成“完整真实案件”。

### 15.3 结果管理

- Oracle 在首次模型运行前完成；
- 首轮输出单独保存；
- 调优后的结果使用新文件；
- 不覆盖原始失败；
- API错误单独统计；
- 不把项目构造数据称为生产数据。

---

## 16. 实施里程碑

### M0：迁移前验证（0.5天）

- 运行当前测试；
- 记录现有60案例结果；
- 确认工作区状态；
- 保存当前评测报告和失败说明。

验收：当前主链路可复现。

### M1：资源合同与Loader（1～2天）

- 定义 Pydantic Skill/Route/Stage/Tool 合同；
- 实现 SkillLoader 和 ToolDefinitionLoader；
- 加载 SKILL.md、skill.yaml、route.yaml、tool.yaml；
- 校验工具引用、Stage跳转、Strategy/Executor/Adapter ID和引用文件。

验收：无效资源产生清晰错误；有效资源可构造运行时定义。

### M2：现有场景无损迁移（1天）

- 建立 funds-dispute/refund-status；
- 建立 fulfillment-dispute/delivery-delay；
- 迁移 allowed tools、required evidence 和 Route说明；
- 保留现有Python策略。

验收：现有测试和结果不变。

### M3：五阶段Harness（2天）

- AgentRunState/RecoveryState；
- 五阶段主循环；
- agent/deterministic Stage模式；
- ContextProjector；
- StageController；
- 顺序Trace。

验收：两个迁移Route通过新Harness端到端运行。

### M4：Tool Runtime与动态工具（2天）

- 拆分 ToolDefinition、Executor、Adapter；
- ToolSurfaceResolver；
- Route范围内Tool Search；
- Case Scope注入；
- Schema和输出校验；
- ToolResultEnvelope。

验收：当前Stage之外工具无法执行；Lazy Tool按需加载。

### M5：模型与错误恢复（1～2天）

- Model Gateway瞬时错误重试；
- Schema/grounding单次修复；
- 精简Canonical Error；
- 恢复预算；
- 降级报告；
- 故障注入测试。

验收：连接重置、502、错误引用和连续失败均有可验证结果。

### M6：资金与履约扩展（3天）

- 完成8个Route；
- 新增支付网关、签收、地址和取消工具；
- 迁移案例数据文件；
- 建设约80～100个案例。

验收：两类Skill覆盖完整核心闭环。

### M7：商品售后与附件（3天）

- 完成4个Route；
- 新增订单明细、退货、仓库和附件工具；
- Evidence Store保存真实大附件；
- 根据模型能力决定是否增加附件理解适配。

验收：商品级和附件证据可进入CaseState并被引用。

### M8：客服合规与多Skill融合（2天）

- 完成3个合规Route；
- 主争议与合规子任务拆分；
- 独立状态和工具面；
- Fusion去重、冲突和复检。

验收：同一案件可以同时输出业务裁决与客服合规结论。

### M9：三个真实LLM Agent（2天）

- 完成 ConversationAgent；
- 完成 EvidenceGapAgent；
- 完成 ReviewAgent；
- 记录各自Token、延迟和调用原因；
- 设置明确触发条件。

验收：三个Agent均有真实必要场景和独立评测。

### M10：完整评测（2～3天）

- 150～200案例回归；
- 新建真实LLM盲测；
- ABCD外部子集；
- 故障注入；
- 五组消融实验；
- 失败案例分析。

验收：原始输出、汇总指标和报告一致。

### M11：作品集交付（1～2天）

- Evidence Console；
- 2～3个黄金Demo；
- README和架构图；
- 评测报告；
- 简历文案；
- 3分钟面试讲解稿。

验收：新环境可以按README运行，文档不声称未实现能力。

---

## 17. 明确不做

作品集版本不实现：

- 订单修改、退款执行等写操作；
- 审批系统；
- 写操作幂等框架；
- Shell或任意代码执行；
- 沙箱；
- 长期用户记忆；
- 完整DAG Planner；
- 分布式Checkpoint；
- 多机房容灾；
- 通用Skill发布平台；
- 插件市场；
- 复杂权限系统；
- 配置表达式DSL；
- 不可变Skill快照；
- 策略hash/fingerprint；
- 为本地SQLite虚构网络重试。

如果未来接入远程工具、真实大文件或写操作，再基于具体失败场景增加对应机制。

---

## 18. 代码规模与时间预算

预计：

```text
生产Python代码          7,000～9,000行
测试代码                2,000～3,000行
前端与脚本              800～1,200行
YAML和Skill说明         2,000～3,000行
```

总有效实现规模约：

```text
12,000～16,000行
```

预计开发时间：

```text
19～24个专注开发日
```

实际工作按里程碑逐步交付，每个里程碑结束时保持仓库可运行，不在最后一次性集成。

---

## 19. Git提交建议

```text
1. refactor: extract case fixtures and preserve current behavior
2. feat: add typed skill and tool resource loaders
3. refactor: migrate refund and delivery to skill packs
4. feat: introduce staged harness and context projector
5. feat: add dynamic tool surface and scoped tool runtime
6. feat: add bounded model recovery and trace events
7. feat: expand funds and fulfillment routes
8. feat: add item after-sales evidence workflows
9. feat: add service compliance and subcase fusion
10. feat: add evidence gap and review agents
11. eval: add blind, recovery, external, and ablation suites
12. docs: deliver interview-ready console and documentation
```

---

## 20. 最终验收标准

作品集版本只有同时满足以下条件才算完成：

- 4个Skill Pack均由资源文件真实加载；
- 15个Route均有独立业务路径；
- 14个Tool均有真实Executor和测试；
- 3个LLM Agent均调用真实模型；
- 每个Route均有Decision Strategy和Evidence要求；
- Tool Surface能阻止无关工具进入模型请求；
- Tool Search不能越过当前Route；
- Case Scope能阻止跨订单或跨Case查询；
- Reducer能确定性更新CaseState；
- 大附件不长期进入模型上下文；
- 瞬时模型错误、grounding错误和业务空结果有不同处理；
- 所有结论可追溯到Evidence；
- 主争议与客服合规结果能够独立执行后融合；
- 150～200案例可以重建并回归；
- 真实LLM评测保留首轮输出；
- 消融实验包含效果、Token和延迟；
- Demo能够展示正常、冲突和恢复三类流程；
- README、计划、代码和简历表述一致。

完成后，项目可定位为：

> 面向电商售后争议的多阶段 Agent Harness，通过 Skill/Route/Stage 动态约束工具与上下文，以 Reducer 维护证据化 CaseState，结合真实 LLM Agent、确定性裁决、错误恢复和多 Skill 结果融合，生成可审计的处理建议与人工复检任务。
