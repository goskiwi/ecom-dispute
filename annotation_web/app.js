const state = { form: null, selected: 0 };
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const routeNames = {
  refund: "退款状态", refund_amount: "退款金额", duplicate_charge: "重复扣款",
  payment_order_failure: "付款成功但订单失败", delivery: "物流异常",
  merchant_not_shipped: "商家未发货", delivered_not_received: "显示送达但未收到",
  cancellation_in_transit: "运输中取消", return_eligibility: "退货资格",
  wrong_item: "错发商品", missing_item: "缺少商品", damaged_item: "商品破损", other: "其他 / 不支持",
};
const routeLabel = (route) => `${routeNames[route] || route} (${route})`;
const speakerLabel = { user: "用户", agent: "客服" };
const confidenceNames = { low: "低", medium: "中", high: "高" };

function complete(item) {
  const a = item.annotation;
  const labeled = typeof a.supported === "boolean" && typeof a.has_dispute === "boolean" && a.primary_route && a.reason && a.confidence;
  return labeled && (!item.assistant_review || a.human_verified === true);
}

function visibleIndexes() {
  const query = $("#search").value.trim().toLowerCase();
  const carefulOnly = $("#review-filter").checked;
  return state.form.items.map((item, index) => ({ item, index }))
    .filter(({ item }) => (!query || item.external_id.toLowerCase().includes(query)) && (!carefulOnly || item.assistant_review?.review_tier === "careful_review"))
    .map(({ index }) => index);
}

function renderList() {
  const visible = new Set(visibleIndexes());
  $("#items").innerHTML = state.form.items.map((item, index) => ({ item, index }))
    .filter(({ index }) => visible.has(index))
    .map(({ item, index }) => `<button class="item ${complete(item) ? "done" : ""} ${item.assistant_review?.review_tier === "careful_review" ? "careful" : ""} ${index === state.selected ? "active" : ""}" data-index="${index}">${escapeHtml(item.external_id)}</button>`).join("");
  $("#items").querySelectorAll("[data-index]").forEach((button) => button.addEventListener("click", () => { state.selected = Number(button.dataset.index); render(); }));
  const done = state.form.items.filter(complete).length;
  $("#progress").textContent = `${state.form.rater_id} · ${done} / ${state.form.items.length}`;
}

function render() {
  renderList();
  const item = state.form.items[state.selected];
  const a = item.annotation;
  const options = Object.keys(state.form.route_guide).map((route) => `<option value="${route}" ${a.primary_route === route ? "selected" : ""}>${escapeHtml(routeLabel(route))}</option>`).join("");
  const checks = Object.entries(state.form.route_guide).map(([route, guide]) => `<label title="${escapeHtml(guide)}"><input type="checkbox" value="${route}" ${a.acceptable_routes.includes(route) ? "checked" : ""}/> ${escapeHtml(routeLabel(route))}</label>`).join("");
  const auditReasons = item.assistant_review?.audit_reasons || [];
  const assistantBanner = item.assistant_review ? `<div class="assistant-banner ${item.assistant_review.review_tier}"><b>AI预标注：${item.assistant_review.review_tier === "careful_review" ? "重点人工复核" : "高置信快速抽检"}</b>${item.assistant_review.ambiguity ? `<span>${escapeHtml(item.assistant_review.ambiguity)}</span>` : ""}${auditReasons.map((reason) => `<span>${escapeHtml(reason)}</span>`).join("")}<small>该建议不是人工真值。</small></div>` : "";
  $("#workspace").innerHTML = `<div class="card"><h2>${escapeHtml(item.external_id)}</h2>${item.conversation.map((turn, index) => `<div class="turn"><b>${index} · ${escapeHtml(speakerLabel[turn.speaker] || turn.speaker)}</b><span><i>英文原文</i>${escapeHtml(turn.text)}${item.translation?.[index] ? `<em>中文辅助</em>${escapeHtml(item.translation[index].text)}` : ""}</span></div>`).join("")}</div>
  <div class="card">${assistantBanner}<div class="grid"><label>是否属于项目支持范围<select id="supported"><option value="">请选择</option><option value="true" ${a.supported === true ? "selected" : ""}>是</option><option value="false" ${a.supported === false ? "selected" : ""}>否</option></select></label><label>是否存在实际争议<select id="has-dispute"><option value="">请选择</option><option value="true" ${a.has_dispute === true ? "selected" : ""}>是</option><option value="false" ${a.has_dispute === false ? "selected" : ""}>否</option></select></label><label>主要争议路由<select id="primary"><option value="">请选择</option>${options}</select></label><label>判断置信度<select id="confidence"><option value="">请选择</option>${["low","medium","high"].map((v) => `<option value="${v}" ${a.confidence === v ? "selected" : ""}>${confidenceNames[v]}</option>`).join("")}</select></label></div><label class="translation-check"><input id="translation-uncertain" type="checkbox" ${a.translation_uncertain ? "checked" : ""}/> 中文辅助翻译存在疑义，需要英文复核</label>${item.assistant_review ? `<label class="translation-check human-check"><input id="human-verified" type="checkbox" ${a.human_verified ? "checked" : ""}/> 我已对照原文确认或修正该条标签</label>` : ""}<label>可接受路由（包含合理的第二选择）<div class="routes">${checks}</div></label><div class="grid"><label>证据对话轮次（逗号分隔）<input id="turns" value="${escapeHtml(a.evidence_turns.join(","))}"/></label><label>标注理由<textarea id="reason" rows="3">${escapeHtml(a.reason || "")}</textarea></label></div><button class="save" id="save">保存并下一条</button></div>
  <div class="card guide"><h3>路由定义</h3>${Object.entries(state.form.route_guide).map(([route, guide]) => `<p><b>${escapeHtml(routeLabel(route))}</b>：${escapeHtml(guide)}</p>`).join("")}</div>`;
  $("#save").addEventListener("click", save);
}

async function save() {
  const item = state.form.items[state.selected];
  const booleanValue = (selector) => $(selector).value === "" ? null : $(selector).value === "true";
  const annotation = {
    supported: booleanValue("#supported"), has_dispute: booleanValue("#has-dispute"),
    primary_route: $("#primary").value || null,
    acceptable_routes: [...document.querySelectorAll(".routes input:checked")].map((input) => input.value),
    evidence_turns: $("#turns").value.split(",").map((v) => Number(v.trim())).filter(Number.isInteger),
    reason: $("#reason").value.trim() || null, confidence: $("#confidence").value || null,
    translation_uncertain: $("#translation-uncertain").checked,
    human_verified: $("#human-verified")?.checked ?? false,
  };
  const response = await fetch(`/api/items/${encodeURIComponent(item.external_id)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(annotation) });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  item.annotation = annotation;
  const candidates = visibleIndexes().filter((index) => index !== state.selected);
  state.selected = candidates.find((index) => index > state.selected && !complete(state.form.items[index]))
    ?? candidates.find((index) => !complete(state.form.items[index]))
    ?? candidates[0]
    ?? state.selected;
  render();
}

async function boot() { state.form = await (await fetch("/api/form")).json(); render(); }
$("#search").addEventListener("input", renderList);
$("#review-filter").addEventListener("change", () => {
  const visible = visibleIndexes();
  if (!visible.includes(state.selected) && visible.length) state.selected = visible[0];
  render();
});
boot();
