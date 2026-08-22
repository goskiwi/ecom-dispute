# Semantic Holdout 状态

## 已完成

- 在主功能完成后新增 30 条中文对话 holdout，Refund/Delivery 各 15 条。
- 输入保存在 `data/semantic_holdout_inputs.json`，Oracle 单独保存在 `evals/semantic_holdout_oracle.json`。
- 评测 Prompt 只读取 conversation，不读取 Oracle。
- 评测器支持多次重复、逐案例 API 错误记录、Token 和延迟统计。

## 数据来源限制

原计划使用另一个模型生成 holdout，但当前网关对 `gpt-5.6`、`gpt-5.5`、`gpt-5.4` 的生成请求均返回 HTTP 502；`gpt-5.4-mini` 随后也返回 502。因此当前 30 条由实现完成后另行编写，属于 post-implementation authored holdout，不是外部数据或跨模型生成数据。

## 评测进展

`gpt-5.4-mini` 首次串行评测时 30/30 收到 HTTP 502。网关恢复后改用用户指定的 `gpt-5.6-luna`：Run 1 完成 30/30，Run 2 完成 23/30，Run 3 为 0/30。完整 Run 1 结果见 `semantic_holdout_gpt-5.6-luna_report_2026-08-22.md`。

网关恢复后执行：

```bash
export ECOM_DISPUTE_API_KEY='...'
python -m ecom_dispute \
  --base-url 'https://example.com' \
  --model 'gpt-5.6-luna' \
  holdout eval --repeats 3 --workers 1
```

当前已有一次完整 Run 1 指标，但三次重复稳定性评测未完成；API 502 不计入模型准确率。
