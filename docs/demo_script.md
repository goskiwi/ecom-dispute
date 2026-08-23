# EcomDispute V3 三分钟Demo

## 启动

```bash
uv run python -m ecom_dispute data rebuild
uv run python -m ecom_dispute web --agent-mode heuristic-test --port 8765
```

浏览器打开 `http://127.0.0.1:8765`。案例列表加载不会执行Agent；选择案例后点击“运行当前Case”。

## Case 1：重复扣款

案例：`v3-duplicate_charge`

讲解重点：

1. Conversation阶段识别`duplicate_charge`。
2. VERIFY只开放订单、支付、退款和政策核心工具。
3. 两笔成功debit形成结构化Evidence。
4. Strategy输出`duplicate_charge_confirmed`和payment_channel责任。
5. Trace展示Stage、Tool Surface和CaseState更新。

## Case 2：签收未收到

案例：`v3-delivered_not_received`

讲解重点：

1. 对话中的“系统签收”和“用户未收到”是两个独立事实。
2. 系统查询订单、物流、签收证明和脱敏地址。
3. 主争议与客服合规分别执行，最后合并Finding。
4. 证据不足或收货冲突进入ReviewTask。

## Case 3：购物车状态故障

案例：`v3-cart_issue`

讲解重点：

1. Conversation将“有库存但无法加购”与“明确缺货”区分开。
2. VERIFY只开放购物车事件和站点健康工具。
3. 确定性Strategy输出`cart_state_conflict`并创建ReviewTask。
4. 展示站点故障Evidence、动态Tool Surface和人工复检闭环。

## 面试总结

> 项目的重点不是Agent数量，而是LLM与确定性系统的边界。Conversation负责理解，核心证据由代码稳定收集，Gap只处理长尾工具，Review只生成人审材料；所有结论必须回到CaseState和Evidence。
