# EcomDispute

EcomDispute 是一个面向退款与物流争议的 LLM 增强型证据化裁决原型。真实运行模式由 Conversation Agent 提取对话语义，Tool Query Agent 根据逐轮 CaseState 选择只读工具，最终由 Skill Strategy 和确定性 Evidence Fusion 输出建议裁决与人工复检任务。

## 为什么是这个项目

项目将两类真实业务能力组合成一条独立产品链路：

| 能力来源 | 在 EcomDispute 中的落点 |
|---|---|
| 虫盯盯的诊断 Harness | CaseState、只读工具、事件时间线、证据引用、可回放 Trace |
| 虫盯盯的 Skill 机制 | `RefundDisputeSkill` 与 `DeliveryDelaySkill` 分别声明允许工具、必需证据和裁决路径 |
| SHEIN 的多阶段质检 | 对话分析、事实核验、政策选择、结果校验与复检分流 |
| SHEIN 的规则与事实裁决 | 对话证据、业务事实和版本化政策联合判断 |
| SHEIN 的结果融合 | Finding 校验、去重、退款/支付冲突检测和人工复检 |

它不是把“运维诊断”和“客服质检”简单拼接，而是把故障排查方法应用于售后争议：先重建事件和事实，再依据事发时有效政策裁决。

## 当前能力

- SQLite 中的订单、支付、退款、售后、物流和版本化政策数据。
- 6 个只读业务工具及 Case 级查询缓存。
- `ConversationAgent`：只负责真实 Responses API 结构化语义提取，不包含关键词降级。
- `ToolQueryAgent`：保留为 `--tool-mode agent` 对照模式；默认使用固定工具执行器，因为端到端盲测未观察到裁决或工具数量收益。
- `FixedFactExecutor` 与 `PolicyResolver`：仅用于确定性测试，不称为 Agent。
- `HeuristicConversationStub`：仅供测试，Trace 明确标记 `heuristic_test_stub`。
- `CaseStateReducer`：确定性投影 Evidence、Finding、时间线和 Trace。
- `EvidenceFusion`：过滤无证据 Finding、去重、检查必需证据、检测退款与支付冲突。
- 60 个固定案例：40 个退款、20 个物流延迟，覆盖多轮与模糊表达、错误客服承诺、政策宽限期、商家/物流责任、不可抗力和跨源冲突。
- 单 LLM Agent Function Calling 基线：完整回传 `function_call` / `function_call_output` 历史，支持并行工具调用、严格最终 Schema、轮数预算和 Evidence ID 校验。
- 语义 Evidence Fusion：LLM 分别输出 `business_facts[]` 与 `interaction_acts[]`；业务事实只包含 `fact_type + polarity + temporal_status + quote`，查询、动作、建议、承诺和解释独立建模，Fusion 只消费 BusinessFact。
- `SkillRegistry`：Refund/Delivery 各自拥有工具边界、必需证据和 Decision Strategy，Fusion 不按 Skill 名称分支。
- 持久化 Review Task：支持 pending/resolved、人工结论、责任方、备注和冲突证据引用。

项目没有上下文卸载、多地区、多语言或批处理 Worker；当前数据规模没有证明这些机制必要，因此不在 README 中声称已实现。

## 快速开始

要求 Python 3.11+。

```bash
python -m ecom_dispute data rebuild
python -m ecom_dispute demo --agent-mode heuristic-test --case-id refund_conflict_001
python -m ecom_dispute eval --mode deterministic
python -m ecom_dispute web --agent-mode heuristic-test --port 8765
python -m pytest -q
```

真实 LLM 模式通过环境变量传入密钥，密钥不会写入仓库：

```bash
export ECOM_DISPUTE_API_KEY='your-key'
python -m ecom_dispute \
  --base-url 'https://your-openai-compatible-endpoint.example' \
  --model 'gpt-5.4-mini' \
  demo --agent-mode live-llm --case-id refund_conflict_001
```

## 执行链路

```text
Case Intake / Skill Router
          |
     ConversationAgent -- real LLM semantic extraction
          |
     CaseState Reducer
          |
     FixedFactExecutor + PolicyResolver -- default scoped read-only tools
          |
     CaseState Reducer after every ToolResult
                              |
                       Evidence Fusion
                              |
              DecisionReport / manual review
```

LLM 不接触评测 Oracle。业务查询结果由工具产生，政策时效、跨源冲突和最终责任由代码计算。

## 当前评测

M2-M4 报告属于旧开发集实验，案例、规则和 Oracle 均由本仓库构造，不是独立准确率。它们保留用于展示架构取舍和失败分析，不能直接作为当前重构后主链路的最终指标。

随后扩展至 40 个案例验证语义融合：最终裁决、责任方和复检均为 40/40，用户 statement type 召回 90.7%，客服承诺类型召回 97.6%，6 个对话-事实冲突的 Precision/Recall 均为 100%，全项通过 34/40。数据仍为人工与规则构造，不表述为线上业务准确率。

详见 [M2 对照评测报告](evals/compare_report_2026-08-22.md) 和 [原始逐案结果](evals/compare_gpt-5.4-mini_2026-08-22.json)。

M3 详见 [语义融合报告](evals/semantic_fusion_report_2026-08-22.md)、[原始首轮输出](evals/hybrid_semantic_gpt-5.4-mini_40cases_2026-08-22.json) 和 [审计后计分](evals/hybrid_semantic_rescored_40cases_2026-08-22.json)。

当前重构后的 live 主链路已完成 `refund_conflict_001` 真实端到端冒烟：工具 Agent 用三轮查询订单/退款/支付/售后/政策，并保留逐轮 Response ID 和 CaseState Trace。全量重新评测尚未完成。

本地 Demo 默认使用 `live-llm`，必须配置模型接口；`--agent-mode heuristic-test` 只用于确定性测试。旧 Recorded Agent 和旧语义兼容层已经删除。控制台支持人工复检操作。

旧 Luna 和 AtomicFact 合同结果已移入 legacy/dev。当前 split-contract 使用新建的 20 条未见对话完成 `gpt-5.6-luna` Run 1：Business Type 100%，用户/客服 BusinessFact F1 约 86.3%/85.7%，InteractionAct F1 约 94.7%/93.0%，全项 Exact Match 11/20。Oracle 在运行后未调整。详见 [Split Contract Blind Run 1](evals/semantic_holdout_split-contract_report_2026-08-22.md)。

端到端 20 案例对照获得 19 个有效结果：Live ToolQuery 与 Fixed Executor 的裁决、责任方、复检、必需 Evidence 均为 19/19，平均工具调用同为 4.05；ToolQuery 额外消耗 209,720 输入 Token 和约 429 秒模型延迟。因此默认采用 Fixed Executor。详见 [E2E 对照报告](evals/e2e_blind_live-vs-fixed_report_2026-08-22.md)。

M5 针对 M4 的三个冲突误报增加时态约束并完成真实 LLM 定向回归，详见 [时态回归报告](evals/temporal_regression_report_2026-08-22.md)。该回归不替代 60 案例首轮指标。
