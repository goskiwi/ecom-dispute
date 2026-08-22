# EcomDispute 简历与面试表达

## 项目名

**EcomDispute - 证据驱动的电商争议 Agent Harness**

## 简历文案

- 设计 `Skill Pack → Route → Stage` 分层Harness，以4个Skill、15个Route组织资金、履约、商品售后和客服合规场景；通过YAML声明工具面与证据要求，Python实现Strategy、Adapter、Reducer和Fusion，支持业务资源独立演进。
- 实现Conversation、EvidenceGap、Review三个真实LLM Agent：核心证据由14个只读工具确定性收集，长尾Agent仅能访问当前Route的Lazy Tool，复检Agent严格校验Evidence ID；删除无收益的全量ToolQueryAgent路径。
- 建设AgentRunState与证据化CaseState，工具结果经StateDelta和Reducer形成时间线、事实、冲突及证据缺口；实现Case Scope注入、Schema准入、模型瞬时重试和grounding单次修复，并记录完整Trace。
- 建设152条确定性回归案例和ABCD外部对话适配器；真实`gpt-5.6-luna`冒烟验证Conversation+Gap及Conversation+Review链路，分别获得正确Route与业务结论，同时保留Token、延迟和失败分析。

## 一分钟介绍

EcomDispute解决的是电商争议中“对话说法、系统事实和政策版本不一致”的问题。系统先由ConversationAgent提取具体Route、业务事实和客服行为，再按Route确定性查询核心业务证据；只有存在长尾证据空间时才调用EvidenceGapAgent。所有ToolResult经过Adapter和Reducer更新CaseState，最终由确定性Strategy完成金额、SLA和责任计算。主争议之外，系统还独立执行客服错误陈述、无依据承诺和缺少升级三类合规检查；冲突案件再由ReviewAgent生成引用真实Evidence的人工复检材料。

## 最有价值的架构取舍

旧版让LLM规划全部工具，但在19个有效案例中与固定执行器结果和工具数量完全相同，却额外增加约21万输入Token和429秒延迟。因此新版删除全量ToolQueryAgent，将模型规划收敛到Route范围内的Evidence Gap。这个决定来自真实消融，不是为了减少Agent数量。

## 可以使用的指标

- 4个Skill Pack、15个Route、14个只读业务Tool。
- 152条确定性回归案例，152/152通过。
- 63项自动化测试通过。
- ABCD适配器实测选择50条官方test对话。
- `m6_refund_amount_001`真实Agent链路：Conversation + EvidenceGap，10,145输入Token、379输出Token、26.9秒模型延迟，Route与结论正确。
- `refund_conflict_001`真实Agent链路：Conversation + Review，10,289输入Token、810输出Token、56.8秒模型延迟，Route与结论正确。
- 8条新Route holdout首轮路由8/8，但全项Exact Match 0/8；失败集中于旧FactType本体和InteractionAct标注边界，不能表述成业务准确率。
- 破坏性扩展Fact ontology后，第二批8条新holdout的FactType-only P/R为90.9%/100%，用户InteractionAct P/R为88.9%/100%，客服为100%/100%；全项Exact 2/8，主要受TemporalStatus边界影响。

## 不能使用的表述

- 生产级电商裁决平台。
- 线上业务准确率100%。
- 真实企业订单或客服流量。
- 152条真实LLM准确率。
- 日均处理量、采纳率或人工提效比例。
- 多地区、多语言已经完成。
- 所有14个工具都是远程微服务。

## 常见追问

### 为什么不是所有步骤都交给LLM？

金额、时间、政策版本和责任条件是确定性业务规则；交给LLM会降低可复现性。LLM只用于自然语言、证据缺口和复检材料这三类非结构化任务。

### 为什么需要Skill和Route？

Skill是领域能力包，Route是具体业务场景。4个Skill拥有不同证据类型和责任体系，15个Route各自声明核心工具、Lazy Tool、证据要求和Strategy。新增Route不修改Harness主循环。

### 为什么使用YAML？

YAML只保存稳定声明并由Pydantic加载；真正业务判断仍在Python。这样Runtime不硬编码每个Route，同时避免在配置中发明复杂逻辑DSL。

### 152/152说明什么？

只说明构造数据、工具和确定性Strategy回归一致，不说明LLM或线上准确率。LLM能力必须使用独立盲测单独报告。

### 当前最大问题是什么？

真实LLM串行成本和延迟较高，尤其复检链路约57秒；独立Route盲测仍未完成。这些是下一阶段评测和优化重点。
