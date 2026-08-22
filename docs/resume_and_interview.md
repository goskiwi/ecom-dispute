# EcomDispute 简历与面试表达（待全量评测版）

## 当前可用项目名

**EcomDispute - LLM 增强的电商售后证据化裁决原型**

在新的 live 主链路完成全量有效评测前，不使用“生产级”“通用 Harness”或“完整 Multi-Agent 平台”等表述。

## 当前可安全使用的简历文案

- 实现面向退款与物流争议的两阶段 Agent 链路：Conversation Agent 将对话提取为业务类型、争议状态、原子语义和时态；Tool Query Agent 基于逐轮 CaseState 自主选择 Skill 允许的只读工具，每批 ToolResult 经 Reducer 更新后继续查询或停止。
- 设计 `Skill Protocol + SkillRegistry + Decision Strategy`，Refund 与 Delivery 分别拥有工具边界、必需证据和裁决规则；通用 Evidence Fusion 负责证据引用校验、Finding 去重、对话/业务冲突合并和 Trace 生成。
- 建设订单、支付、退款、售后、物流和版本化政策六类 SQLite 查询工具，为空查询生成可引用的负向 Evidence；实现持久化人工复检任务，支持冲突证据、人工结论、责任方和备注保存。

## 暂时不能写入简历的指标

- “真实 LLM 责任方准确率 100%”。
- “多 Agent 准确率 95%+”。
- “日均处理 500+”。
- “覆盖多地区、多语言”。
- “生产级参数修复、重试和降级”。

历史 M2-M4 数据只属于构造开发集实验。重构后的主链路目前只有一个真实端到端冒烟案例；30 条后置 holdout 已由 `gpt-5.6-luna` 完成一次完整语义评测，但三次重复因网关 502 未全部完成。

## 一分钟介绍

EcomDispute 处理的是电商争议中对话说法、业务事实和政策版本不一致的问题。系统先由 Conversation Agent 理解用户主张和客服承诺，再由 Tool Query Agent 根据当前 CaseState 决定查询订单、退款、支付、售后、物流或政策。工具结果不会直接交给模型自由总结，而是先通过 Reducer 形成可回放的 Evidence 与时间线；最后由对应 Skill 的确定性策略计算政策时限和责任，冲突或证据不足会生成可操作的 Review Task。

## 与实习能力的关系

- 虫盯盯：借鉴执行循环、CaseState Reducer、Tool Registry、证据时间线和 Trace，但当前没有日志卸载或上下文回捞。
- SHEIN：借鉴规则与事实联合裁决、冲突合并和复检分流，但当前不是红线/业务/态度三 Agent 并行质检，也没有多地区批处理。

## 当前限制

- 业务数据为本地构造数据，不代表线上业务准确率。
- 固定 60 条案例是开发回归集，不能作为独立测试集。
- 30 条后置语义 holdout 的完整 Run 1 全项精确匹配为 11/30；它不是公开数据，Run 2/3 又受网关 502 影响，暂不写入正式简历指标。
- 本地工具是 SQLite 只读查询，没有真实远程服务，因此没有证据支持增加通用重试或降级机制。
- Recorded Demo 使用保存的真实模型输出；只有 `live-llm` 模式会执行新的实时模型调用。
