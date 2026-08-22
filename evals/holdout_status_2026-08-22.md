# Semantic Holdout 状态

## 已完成

- 在主功能完成后新增 30 条中文对话 holdout，Refund/Delivery 各 15 条。
- 输入保存在 `data/semantic_holdout_inputs.json`，Oracle 单独保存在 `evals/semantic_holdout_oracle.json`。
- 评测 Prompt 只读取 conversation，不读取 Oracle。
- 评测器支持多次重复、逐案例 API 错误记录、Token 和延迟统计。

## 数据来源限制

原计划使用另一个模型生成 holdout，但当前网关对 `gpt-5.6`、`gpt-5.5`、`gpt-5.4` 的生成请求均返回 HTTP 502；`gpt-5.4-mini` 随后也返回 502。因此当前 30 条由实现完成后另行编写，属于 post-implementation authored holdout，不是外部数据或跨模型生成数据。

## 评测阻塞

2026-08-22 运行 `gpt-5.4-mini` 串行评测时，30/30 请求均收到相同 HTTP 502。没有成功样本，因此不产生准确率，也不把 API 错误计为模型错误。

网关恢复后执行：

```bash
export ECOM_DISPUTE_API_KEY='...'
python -m ecom_dispute \
  --base-url 'https://example.com' \
  --model 'gpt-5.4-mini' \
  holdout eval --repeats 3 --workers 1
```

在获得有效输出前，项目没有独立 holdout 的真实 LLM 指标。
