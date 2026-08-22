# Review A/B人工评审说明

评审文件：`evals/formal_review_40_blind_form.json`

请两位评审分别复制为本地文件：

```text
evals/formal_review_40_rater1.json
evals/formal_review_40_rater2.json
```

这两个文件和A/B key已加入`.gitignore`，评审完成前不要打开：

```text
evals/formal_review_40_ab_key.json
```

## 每个选项评分

对Option A和Option B分别填写1～5分：

- `evidence_correctness`：引用是否与摘要和问题一致；
- `conflict_coverage`：是否覆盖主要冲突或缺口；
- `question_actionability`：审核员是否能据此继续处理；
- `irrelevant_content`：5表示没有无关内容，1表示大量无关内容。

再填写：

- `overall_preference`：`A`、`B`或`tie`；
- `comment`：可选，说明偏好原因。

两位评审必须独立完成，不讨论具体案例。完成后才能使用key汇总固定模板和ReviewAgent的胜率、均分、一致率与Cohen's Kappa。

## 当前限制

40条真实可用候选的类别分布是5条冲突、4条证据缺失、31条合规。该分布不均衡，最终结果必须同时报告总体和分类别分数。
