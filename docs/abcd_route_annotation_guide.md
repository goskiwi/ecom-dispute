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
  --form evals/formal_abcd_200_rater1.json --port 8877
```

评审员2使用自己的仓库副本或不同端口：

```bash
uv run python -m ecom_dispute abcd-annotation-web \
  --form evals/formal_abcd_200_rater2.json --port 8878
```

浏览器打开对应地址。每次保存立即写回本地JSON，可中断后继续。

## 标注字段

- `supported`：当前12个主Route是否能表达该问题；
- `has_dispute`：是否存在实际业务异常或处理结果争议；
- `primary_route`：最合适的主Route，不支持时选`other`；
- `acceptable_routes`：存在合理第二选择时勾选，可包含primary；
- `evidence_turns`：支持判断的对话Turn编号；
- `reason`：一句话解释；
- `confidence`：low / medium / high。

## 关键边界

- `return_eligibility`：询问或办理是否满足退货条件；
- `wrong_item`：实际收到的SKU、颜色、型号与订单不一致；
- `delivery`：已发货后的运输延迟或物流异常；
- `delivered_not_received`：必须存在系统已送达/签收与用户未收到的冲突；
- 普通运费、材质、尺码等信息咨询且无异常，通常为`other`；
- 同一对话含多个问题时，primary选择当前主要诉求，其余放入acceptable。

## 汇总

两位评审完成后：

```bash
uv run python -m ecom_dispute abcd-annotation-agreement
```

该命令生成Consensus草案和：

- supported / has_dispute / primary_route一致率；
- Cohen's Kappa；
- 需要共同解决的分歧清单。

共同填写Consensus中的未决项并将status改为`resolved`后：

```bash
uv run python -m ecom_dispute abcd-annotation-rescore
```

重评分直接使用已保存的首次模型输出，不重新调用模型。
