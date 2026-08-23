# EcomDispute V3 简历与面试表达

## 项目名

**EcomDispute - 证据驱动的电商服务与站点诊断 Agent Harness**

## 简历文案

- 设计`Skill Pack → Route → Stage`分层Harness，以7个Skill、29个Route覆盖资金、履约、退换货、订单操作、商品/促销咨询、站点故障和客服合规；YAML声明动态工具面与证据合同，Python实现Strategy、Adapter、Reducer和Fusion。
- 实现Conversation、EvidenceGap、Review三个真实LLM Agent及29个Case-scoped Tool；Conversation输出业务异常、退货原因和商品不符双侧原文证据，Route只开放当前Stage工具，长尾Agent不能越过Lazy Tool边界。
- 建设31表可重建业务数据与90条Decision E2E，实际执行覆盖29个Route的97/97非人工Decision，并校验Party、Review、Evidence、Tool和ActionPlan；构建44条相邻Route边界集，真实`gpt-5.6-luna`首轮Route 44/44、业务异常43/44、退货原因3/3。
- 将订单修改、退换货、价保和促销修复输出为带确认要求和幂等键的ActionPlan；VERIFY阶段只读，跨系统写边界不由LLM直接执行。

## 一分钟介绍

EcomDispute处理“对话说法、系统事实、政策规则和站点事件不一致”的电商问题。ConversationAgent先识别具体Route并抽取有原文依据的事实；Harness按Skill/Route/Stage计算动态Tool Surface，核心工具确定性收集订单、支付、退款、物流、仓库、库存、促销和站点健康证据；Strategy再完成状态机、金额、SLA和责任判断。冲突案件进入ReviewAgent，三个合规Route独立检查客服陈述、承诺和升级，最终生成Evidence、Trace、ReviewTask和受控ActionPlan。

## 可使用的V3指标

- 7个Skill Pack、29个Route、29个Tool、31张SQLite表。
- 80项自动化测试通过。
- 90条主案例覆盖97/97确定性Decision，其中13条生成带确认与幂等键的ActionPlan。
- 26条缺失必需Evidence矩阵全部安全关闭为人工复检；工具超时和连接错误结构化进入Trace，不产生错误ActionPlan。
- 44条真实LLM边界集：Route 44/44，`has_business_exception` 43/44，`return_reason` 3/3，API错误0，模型修复0。
- 边界集累计Input/Output Token为314,780/8,050，模型累计延迟614,884ms。
- V3 ABCD从完整96个subflow轮转抽样200条，不再使用subflow粗映射；人工Consensus未完成前不报告外部Route Accuracy。

## 不能使用的表述

- 生产级电商自动执行平台。
- 线上业务准确率100%。
- 90条或44条代表真实生产分布。
- ABCD V3外部准确率已经得到。
- ReviewAgent已经提高人工效率。
- ActionPlan已经连接真实退款、扣款或订单修改接口。

## 常见追问

### 为什么Route从15个扩大到29个？

不是按关键词拆分。每个Route必须对应不同证据、工具面或确定性策略。例如结账失败没有成功扣款时查结账事件；已扣款但无有效订单时查支付、订单和撤销记录；两者不能共用同一入口。完整边界见根目录V3本体文件。

### 如何区分买家选错和商家错发？

买家选错、不合身或不喜欢进入`return_request`并填写`return_reason`。只有原文明示下单值与实收值不一致，才能进入`received_item_mismatch`；ordered/received值还要通过原文grounding校验。

### 为什么删除`merchant_not_shipped` Route？

它与通用履约进度使用相同订单、物流和政策工具。V3由`fulfillment_progress`进入，确定性Strategy再根据是否揽收与SLA输出商家延迟或承运商延迟，避免入口重叠。

### 为什么保留确定性Strategy？

金额、状态机、时间阈值、政策版本和责任条件需要可复现。LLM负责语言和开放性证据，不能自由计算或覆盖业务事实。

### 44/44说明什么？

只说明冻结本体下这44条预提交边界案例的Route全部命中。样本规模小且为人工最小对照，不能外推生产；唯一业务异常错误也被保留，没有继续针对本集调Prompt。

### 当前最大问题是什么？

每次Conversation调用注入完整Route与Fact合同，平均输入约7千Token；97个Decision也仍各只有一条主证据组合。下一步应增加缺失证据和跨源冲突变体，并用全新评测集验证分层Skill Router能否降Token且不降准确率。
