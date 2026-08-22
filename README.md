# EcomDispute

EcomDispute 是一个面向电商售后争议的证据化诊断项目。当前 MVP 聚焦退款争议：系统从客服对话中提取用户主张和客服承诺，查询订单、支付、退款、售后与事发时有效政策，再通过确定性融合输出责任方、处理建议、证据链和人工复检标记。

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
- `ConversationAgent`：支持真实 Responses API 严格结构化输出，也支持无密钥离线模式。
- `FactAgent` 与 `PolicyAgent`：并行查询独立信息源。
- `CaseStateReducer`：确定性投影 Evidence、Finding、时间线和 Trace。
- `EvidenceFusion`：过滤无证据 Finding、去重、检查必需证据、检测退款与支付冲突。
- 60 个固定案例：40 个退款、20 个物流延迟，覆盖多轮与模糊表达、错误客服承诺、政策宽限期、商家/物流责任、不可抗力和跨源冲突。
- 单 LLM Agent Function Calling 基线：完整回传 `function_call` / `function_call_output` 历史，支持并行工具调用、严格最终 Schema、轮数预算和 Evidence ID 校验。
- 语义 Evidence Fusion：LLM 输出 `business_type + has_dispute`、多标签 `statement_types[]` 和 `temporal_status`，代码核验客服所称退款/送达状态与业务记录，并为 `not_found` 查询生成负向 Evidence ID。

当前的 Fact/Policy 模块是确定性专项执行器，不包装成 LLM。真实评测显示当前网关单次短请求仍约含 4.7k 输入 Token，因此先验证一次语义调用的业务收益，再通过对照实验决定是否增加 LLM 调用。

## 快速开始

要求 Python 3.11+。

```bash
python -m ecom_dispute data rebuild
python -m ecom_dispute demo --case-id refund_conflict_001
python -m ecom_dispute eval --mode offline
python -m ecom_dispute web --port 8765
python -m pytest -q
```

真实 LLM 模式通过环境变量传入密钥，密钥不会写入仓库：

```bash
export ECOM_DISPUTE_API_KEY='your-key'
python -m ecom_dispute \
  --base-url 'https://your-openai-compatible-endpoint.example' \
  --model 'gpt-5.4-mini' \
  eval --mode compare
```

## 执行链路

```text
Case Intake / Skill Router
          |
          +--> ConversationAgent -- real LLM semantic extraction
          +--> FactAgent --------- Skill-scoped business tools
          +--> PolicyAgent ------- effective-time policy lookup
                              |
                       CaseState Reducer
                              |
                       Evidence Fusion
                              |
              DecisionReport / manual review
```

LLM 只读取会话，不接触评测 Oracle。业务查询结果由工具产生，政策生效时间、证据存在性、退款/支付冲突和最终复检条件由代码检查。

## 当前评测

2026-08-22 使用 `gpt-5.4-mini-2026-03-17` 对 20 个案例完成 Function Calling 对照：Hybrid 最终裁决 20/20，单 Agent 基线最终裁决 14/20，Baseline 使用约 2.32 倍输入 Token 和 3.33 倍模型累计延迟。

随后扩展至 40 个案例验证语义融合：最终裁决、责任方和复检均为 40/40，用户 statement type 召回 90.7%，客服承诺类型召回 97.6%，6 个对话-事实冲突的 Precision/Recall 均为 100%，全项通过 34/40。数据仍为人工与规则构造，不表述为线上业务准确率。

详见 [M2 对照评测报告](evals/compare_report_2026-08-22.md) 和 [原始逐案结果](evals/compare_gpt-5.4-mini_2026-08-22.json)。

M3 详见 [语义融合报告](evals/semantic_fusion_report_2026-08-22.md)、[原始首轮输出](evals/hybrid_semantic_gpt-5.4-mini_40cases_2026-08-22.json) 和 [审计后计分](evals/hybrid_semantic_rescored_40cases_2026-08-22.json)。

M4 扩展为 60 个跨 Skill 案例：确定性裁决、责任方、复检、业务类型和争议存在性均为 60/60；用户/客服类型召回分别为 95.7% 和 96.7%，冲突 Precision 70%、Recall 100%，全项通过 53/60。详见 [跨 Skill 评测报告](evals/multiskill_report_2026-08-22.md)。

本地 Demo 控制台启动后访问 `http://127.0.0.1:8765`，可以筛选 Refund/Delivery 案例并检查对话、时间线、Finding、Evidence 和完整执行轨迹。简历与面试表达见 [项目讲解文档](docs/resume_and_interview.md)。

M5 针对 M4 的三个冲突误报增加时态约束并完成真实 LLM 定向回归，详见 [时态回归报告](evals/temporal_regression_report_2026-08-22.md)。该回归不替代 60 案例首轮指标。
