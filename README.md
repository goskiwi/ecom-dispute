# EcomDispute

EcomDispute 是一个面向电商售后争议的证据化诊断项目。当前 MVP 聚焦退款争议：系统从客服对话中提取用户主张和客服承诺，查询订单、支付、退款、售后与事发时有效政策，再通过确定性融合输出责任方、处理建议、证据链和人工复检标记。

## 为什么是这个项目

项目将两类真实业务能力组合成一条独立产品链路：

| 能力来源 | 在 EcomDispute 中的落点 |
|---|---|
| 虫盯盯的诊断 Harness | CaseState、只读工具、事件时间线、证据引用、可回放 Trace |
| 虫盯盯的 Skill 机制 | `RefundDisputeSkill` 声明适用场景、允许工具和必需证据 |
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
- 20 个退款案例：10 个独立人工编写、10 个规则生成，覆盖未发起超时、处理中、到账超时、已完成、跨源冲突、证据缺失和历史政策版本。
- 单 LLM Agent Function Calling 基线：完整回传 `function_call` / `function_call_output` 历史，支持并行工具调用、严格最终 Schema、轮数预算和 Evidence ID 校验。

当前的 Fact/Policy 模块是确定性专项执行器，不包装成 LLM。真实评测显示当前网关单次短请求仍约含 4.7k 输入 Token，因此先验证一次语义调用的业务收益，再通过对照实验决定是否增加 LLM 调用。

## 快速开始

要求 Python 3.11+。

```bash
python -m ecom_dispute data rebuild
python -m ecom_dispute demo --case-id refund_conflict_001
python -m ecom_dispute eval --mode offline
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
Case Intake / Refund Skill
          |
          +--> ConversationAgent -- real LLM semantic extraction
          +--> FactAgent --------- order/payment/refund/after-sales tools
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

2026-08-22 使用 `gpt-5.4-mini-2026-03-17` 对 20 个固定案例完成首轮真实 LLM 对照。Hybrid 最终裁决、责任方和复检分流为 20/20，加入语义路由检查后全项通过 19/20；单 Agent Function Calling 基线全项通过 11/20，最终裁决正确 14/20。Baseline 使用约 2.32 倍输入 Token 和 3.33 倍模型累计延迟。数据仍为人工与规则构造，不表述为线上业务准确率。

详见 [M2 对照评测报告](evals/compare_report_2026-08-22.md) 和 [原始逐案结果](evals/compare_gpt-5.4-mini_2026-08-22.json)。
