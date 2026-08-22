# EcomDispute v1.0 三分钟Demo

## 启动

```bash
uv run python -m ecom_dispute data rebuild
uv run python -m ecom_dispute web --agent-mode heuristic-test --port 8765
```

浏览器打开 `http://127.0.0.1:8765`。案例列表加载不会执行Agent；选择案例后点击“运行当前Case”。

## Case 1：重复扣款

案例：`m6_duplicate_001`

讲解重点：

1. Conversation阶段识别`duplicate_charge`。
2. VERIFY只开放订单、支付、退款和政策核心工具。
3. 两笔成功debit形成结构化Evidence。
4. Strategy输出`duplicate_charge_confirmed`和payment_channel责任。
5. Trace展示Stage、Tool Surface和CaseState更新。

## Case 2：签收未收到

案例：`m6_not_received_001`

讲解重点：

1. 对话中的“系统签收”和“用户未收到”是两个独立事实。
2. 系统查询订单、物流、签收证明和脱敏地址。
3. 主争议与客服合规分别执行，最后合并Finding。
4. 证据不足或收货冲突进入ReviewTask。

## Case 3：退款/支付冲突

案例：`refund_conflict_001`

讲解重点：

1. 退款系统显示成功，但支付记录没有匹配credit。
2. 确定性Strategy输出`refund_record_conflict`，不让LLM自由定责。
3. live模式下ReviewAgent只引用已有Evidence生成复检材料。
4. 展示错误恢复、Evidence ID和人工复检闭环。

## 面试总结

> 项目的重点不是Agent数量，而是LLM与确定性系统的边界。Conversation负责理解，核心证据由代码稳定收集，Gap只处理长尾工具，Review只生成人审材料；所有结论必须回到CaseState和Evidence。
