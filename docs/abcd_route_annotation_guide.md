# ABCD逐对话Route盲标指南

## 目标

对已提交manifest中的200条ABCD对话，按照EcomDispute定义逐条标注，而不是使用ABCD subflow整体映射。

标注时隐藏：

- ABCD subflow；
- 原粗粒度Route；
- `gpt-5.6-luna`首轮预测。

## 启动

评审员1：

```bash
uv run python -m ecom_dispute abcd-annotation-web \
  --form evals/v3_abcd_200_rater1.json --port 8877
```

评审员2使用自己的仓库副本或不同端口：

```bash
uv run python -m ecom_dispute abcd-annotation-web \
  --form evals/v3_abcd_200_rater2.json --port 8878
```

浏览器打开对应地址。每次保存立即写回本地JSON，可中断后继续。

页面同时展示英文原文和由`gpt-5.6-luna`生成的中文辅助译文。译文不接触ABCD subflow、粗粒度Route、模型预测或人工标签，不能替代英文原文。评审若发现歧义，应勾选“中文辅助翻译存在疑义”；两位评审完成后，至少抽查40条（20%）英文原文，并复核所有被勾选或低置信度的对话。

若采用面试项目所需的AI辅助复核流程，可先生成独立草稿：

```bash
uv run python -m ecom_dispute --base-url "$ECOM_DISPUTE_BASE_URL" \
  --model gpt-5.6-luna abcd-preannotate
```

再运行`scripts/start_assistant_annotation.command`并打开`http://127.0.0.1:8879/`。页面将高置信单一Route标为“快速抽检”，将多意图、边界冲突和保守审计命中的样本标为“重点人工复核”。人工确认时必须勾选“我已对照原文确认或修正”。该流程必须披露为“AI预标注+人工复核”，不能表述为双人独立人工标注，也不能用该草稿直接计算最终准确率。

## 标注字段

- `supported`：当前26个业务Route是否能表达该问题；
- `has_business_exception`：对话中是否曾发生业务异常或处理结果争议；问题后来解决仍为`true`；
- `primary_route`：最合适的主Route，不支持时选`other`；
- `acceptable_routes`：存在合理第二选择时勾选，可包含primary；
- `evidence_turns`：支持判断的对话Turn编号；
- `reason`：一句话解释；
- `confidence`：低 / 中 / 高（保存值仍为`low` / `medium` / `high`）。
- `translation_uncertain`：中文辅助译文是否需要回看英文复核，不参与Route评分。

## 关键边界

- `return_request`：普通退货、买错、不合身、不喜欢和资格判断；
- `return_progress`：已提交退货后的标签、寄回、入库或验货进度；
- `received_item_mismatch`：必须有下单值和实收值的明确原文比较；
- `fulfillment_progress`：待发货、运输、延迟、丢失和送达进度；
- `delivered_not_received`：必须存在系统已送达/签收与用户未收到的冲突；
- 明确缺货优先`inventory_availability`；库存可用或未知但购物车状态异常才是`cart_issue`；
- 密码、2FA、身份资料修改和信贷延期属于`other`；
- 同一对话含多个问题时，primary选择当前主要诉求，其余放入acceptable。

## 汇总

两位评审完成后：

```bash
uv run python -m ecom_dispute abcd-annotation-agreement
```

该命令生成Consensus草案和：

- supported / has_business_exception / primary_route一致率；
- Cohen's Kappa；
- 需要共同解决的分歧清单。

共同填写Consensus中的未决项并将status改为`resolved`后：

```bash
uv run python -m ecom_dispute abcd-annotation-rescore
```

重评分直接使用已保存的首次模型输出，不重新调用模型。
