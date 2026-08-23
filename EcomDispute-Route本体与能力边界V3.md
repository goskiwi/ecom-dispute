# EcomDispute Route本体与能力边界 V3

## 1. 冻结原则

本文件是破坏性V3重构的唯一Route合同，不保留V2 Route ID兼容。

一个Route必须同时满足：

1. 能从用户对话中的主要诉求稳定识别；
2. 与相邻Route具有可说明的正反例边界；
3. 对应独立的证据集合、工具面或确定性策略；
4. Route描述问题入口，不提前写入最终责任或裁决结果；
5. 普通请求、业务异常和客服处理动作分别建模，不能互相替代。

`has_business_exception`只表示对话中是否曾发生业务异常或处理结果争议；即使客服最后解决，已经发生的异常仍为`true`。

## 2. 最终Skill与Route

### 2.1 funds-dispute（6）

| Route ID | 中文名 | 核心边界 |
|---|---|---|
| `refund_progress` | 退款进度与到账 | 已存在或应存在退款后的未发起、处理中、完成未到账和记录冲突 |
| `refund_amount_mismatch` | 退款金额不符 | 应退金额与实际退款或到账金额不一致 |
| `duplicate_charge` | 重复扣款 | 同一有效订单存在多笔重复成功扣款 |
| `payment_captured_order_failed` | 已扣款但订单失败 | 支付成功但没有有效订单或订单创建失败/取消 |
| `unrecognized_charge` | 陌生扣款 | 用户否认对应购买或授权关系 |
| `order_fee_dispute` | 订单费用争议 | 已收取的运费、处理费或服务费与订单/政策不一致 |

### 2.2 fulfillment-service（3）

| Route ID | 中文名 | 核心边界 |
|---|---|---|
| `fulfillment_progress` | 发货与配送进度 | 从订单待发货到运输、延迟、丢失和正常送达；商家未发货是裁决结果 |
| `delivered_not_received` | 显示送达但未收到 | 系统/物流声称送达，用户明确否认收到 |
| `order_cancellation` | 订单取消与关联退款 | 取消申请、揽收先后关系、取消结果及关联退款 |

### 2.3 item-after-sales（6）

| Route ID | 中文名 | 核心边界 |
|---|---|---|
| `return_request` | 退货申请与资格 | 普通退货、买错、不合身、不喜欢及时间/品类/状态资格 |
| `return_progress` | 退货处理与入库进度 | 已提交退货后的标签、寄回、仓库入库、验货和处理进度 |
| `exchange_request` | 换货申请 | 换颜色/尺码/商品，需库存、差价和资格证据 |
| `received_item_mismatch` | 实收商品与订单不符 | 对话明确比较下单与实收SKU/颜色/尺码/型号 |
| `missing_item` | 少件 | 实收数量少于订单数量 |
| `item_condition_issue` | 商品状况问题 | 破损、污渍、瑕疵和质量缺陷 |

`return_reason`是事实属性，不是Route：`buyer_selected_wrong_variant`、`fit_issue`、`preference_change`、`no_longer_needed`、`seller_mismatch_claim`、`unknown`。只有明确的下单值与实收值比较，或明确声称商家错发，才能进入`received_item_mismatch`。

### 2.4 order-operations（1）

| Route ID | 中文名 | 核心边界 |
|---|---|---|
| `order_management` | 订单信息与修改 | 核验或修改数量、地址、付款方式、配送等级/时间及现有订单商品 |

`operation_type`区分`verify_details`、`change_quantity`、`change_address`、`change_payment_method`、`change_shipping_level`、`change_delivery_time`、`add_item`、`remove_item`。

### 2.5 commerce-support（6）

| Route ID | 中文名 | 核心边界 |
|---|---|---|
| `product_information` | 商品信息 | 材质、尺码、防水、护理和目录属性 |
| `inventory_availability` | 库存可用性 | 缺货、补货时间、到货提醒和预订能力 |
| `price_adjustment` | 价格调整 | 价保、竞品匹配和购买后降价 |
| `promotion_support` | 优惠促销支持 | 优惠券无效、过期、门槛、限制和补发资格 |
| `shipping_options` | 配送方案咨询 | 下单前配送方式、报价、国际配送和预计时效 |
| `membership_support` | 会员权益 | 等级、权益、积分/额度和会员服务状态 |

### 2.6 site-reliability（4）

| Route ID | 中文名 | 核心边界 |
|---|---|---|
| `checkout_issue` | 结账故障 | 未成功扣款前的银行卡拒绝、结账失败和订单无法创建 |
| `cart_issue` | 购物车故障 | 商品无法加入/移除或购物车状态异常 |
| `search_issue` | 搜索故障 | 搜索结果无关、缺失或索引异常 |
| `site_performance` | 站点性能故障 | 页面缓慢、错误率、可用性和事故状态 |

结账失败且没有成功扣款属于`checkout_issue`；已经扣款但没有有效订单属于`payment_captured_order_failed`。

### 2.7 service-compliance（3）

| Route ID | 中文名 | 核心边界 |
|---|---|---|
| `business_statement_check` | 业务陈述核验 | 客服业务陈述是否与证据一致 |
| `promise_grounding_check` | 承诺依据核验 | 客服结果承诺是否得到事实与政策支持 |
| `escalation_requirement_check` | 必要升级核验 | 需要人工复检时是否完成明确升级 |

## 3. 明确拒识范围

- 用户名、密码和2FA找回；
- 修改账户姓名、手机号等身份资料；
- 信贷、账单延期和催收决策；
- 真实生产环境的自动扣款、退款和账户安全操作；
- 与电商订单、商品、履约、资金、站点可用性无关的通用客服请求。

拒识是明确产品边界，不得映射到相似Route凑覆盖率。

## 4. 动作与安全边界

查询、诊断和裁决默认只读。订单修改、换货、优惠券补发等模拟写操作只能在确定性决策之后生成ActionPlan；真正提交属于跨系统写边界，必须使用显式确认、事务、唯一请求号和幂等约束。不得把写工具放入VERIFY核心工具面而无条件执行。

## 5. 评测重建要求

- 删除ABCD subflow到Route的一对一粗映射；按逐对话语义评估支持范围；
- 机器预标注只读取英文原文，中文翻译只供人工辅助；
- 同模型预标注不得作为独立Oracle；
- 为每对相邻Route建立最小对照样本；
- 重建全部回归数据、E2E Oracle和报告，不沿用V2指标；
- 旧评测只作为`legacy ontology v2`历史结果保存。
