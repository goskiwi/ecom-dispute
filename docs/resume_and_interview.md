# EcomDispute 简历与面试表达（待全量评测版）

## 当前可用项目名

**EcomDispute - LLM 增强的电商售后证据化裁决原型**

在新的 live 主链路完成全量有效评测前，不使用“生产级”“通用 Harness”或“完整 Multi-Agent 平台”等表述。

## 当前可安全使用的简历文案

- 实现面向退款与物流争议的 Conversation Agent，将对话拆为可核验 BusinessFact 与独立 InteractionAct；按 Skill 使用固定只读工具收集业务证据，每批 ToolResult 经 Reducer 更新 CaseState 后进入确定性裁决。
- 设计 `Skill Protocol + SkillRegistry + Decision Strategy`，Refund 与 Delivery 分别拥有工具边界、必需证据和裁决规则；通用 Evidence Fusion 负责证据引用校验、Finding 去重、对话/业务冲突合并和 Trace 生成。
- 建设订单、支付、退款、售后、物流和版本化政策六类 SQLite 查询工具，为空查询生成可引用的负向 Evidence；实现持久化人工复检任务，支持冲突证据、人工结论、责任方和备注保存。

## 暂时不能写入简历的指标

- “真实 LLM 责任方准确率 100%”。
- “多 Agent 准确率 95%+”。
- “日均处理 500+”。
- “覆盖多地区、多语言”。
- “生产级参数修复、重试和降级”。

历史 M2-M4 和旧 Luna 指标只属于旧合同实验。当前 split-contract 在 20 条项目内后置盲测对话上，用户/客服 BusinessFact F1 为 86.3%/85.7%，InteractionAct F1 为 94.7%/93.0%；可表述为固定构造集实验，不能称线上准确率。

端到端后置盲测中，Fixed Executor 与 ToolQuery Agent 在 19 个有效案例上均完成 19/19 裁决，但 ToolQuery 额外消耗约 21 万输入 Token且没有减少工具调用，因此默认采用固定执行器；该负向对照可作为架构取舍说明，不写成线上准确率。

## 一分钟介绍

EcomDispute 处理的是电商争议中对话说法、业务事实和政策版本不一致的问题。系统先由 Conversation Agent 理解用户主张和客服承诺，再由 Tool Query Agent 根据当前 CaseState 决定查询订单、退款、支付、售后、物流或政策。工具结果不会直接交给模型自由总结，而是先通过 Reducer 形成可回放的 Evidence 与时间线；最后由对应 Skill 的确定性策略计算政策时限和责任，冲突或证据不足会生成可操作的 Review Task。

## 与实习能力的关系

- 虫盯盯：借鉴执行循环、CaseState Reducer、Tool Registry、证据时间线和 Trace，但当前没有日志卸载或上下文回捞。
- SHEIN：借鉴规则与事实联合裁决、冲突合并和复检分流，但当前不是红线/业务/态度三 Agent 并行质检，也没有多地区批处理。

## 当前限制

- 业务数据为本地构造数据，不代表线上业务准确率。
- 固定 60 条案例是开发回归集，不能作为独立测试集。
- split-contract 盲测全项 Exact Match 为 11/20，Has Dispute 为 85%；后续不能在同一集合上调 Oracle 后重算成绩。
- 本地工具是 SQLite 只读查询，没有真实远程服务，因此没有证据支持增加通用重试或降级机制。
- Demo 默认使用 `live-llm`；无模型凭据时只能显式选择 `heuristic-test`，且该模式不代表 Agent 能力。
