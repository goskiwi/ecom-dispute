const state = { cases: [], filtered: [], selected: null };
const els = {
  list: document.querySelector("#case-list"), count: document.querySelector("#case-count"),
  detail: document.querySelector("#detail"), search: document.querySelector("#case-search"),
  skill: document.querySelector("#skill-filter"), review: document.querySelector("#review-filter"),
  runState: document.querySelector("#run-state"),
};
const escapeHtml = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const label = (value) => String(value ?? "-").replaceAll("_", " ");
const json = (value) => escapeHtml(JSON.stringify(value, null, 2));

function filterCases() {
  const query = els.search.value.trim().toLowerCase();
  state.filtered = state.cases.filter((item) => {
    const skillMatch = els.skill.value === "all" || item.business_type === els.skill.value;
    const reviewMatch = els.review.value === "all"
      || (els.review.value === "unrun" ? item.run_status === "not_run"
        : els.review.value === "review" ? item.review_required === true
          : item.review_required === false);
    return skillMatch && reviewMatch && (!query || `${item.case_id} ${item.decision}`.toLowerCase().includes(query));
  });
  renderCases();
}

function renderCases() {
  els.count.textContent = `${state.filtered.length} / ${state.cases.length} CASES`;
  if (!state.filtered.length) {
    els.list.replaceChildren(document.querySelector("#empty-template").content.cloneNode(true));
    return;
  }
  els.list.innerHTML = state.filtered.map((item) => `
    <button class="case-item ${item.case_id === state.selected ? "active" : ""}" data-case="${escapeHtml(item.case_id)}">
      <strong>${escapeHtml(item.case_id)}</strong>
      <span class="case-meta">${escapeHtml(item.business_type)} <i class="dot"></i> ${escapeHtml(label(item.decision || "not run"))}${item.review_required ? '<b class="review-flag">REVIEW</b>' : ""}</span>
    </button>`).join("");
  els.list.querySelectorAll("[data-case]").forEach((button) => button.addEventListener("click", () => loadCase(button.dataset.case)));
}

async function loadCase(caseId) {
  state.selected = caseId;
  renderCases();
  els.detail.innerHTML = '<div class="detail-loading"><div class="skeleton wide"></div><div class="skeleton"></div><div class="skeleton grid"></div></div>';
  try {
    const response = await fetch(`/api/cases/${encodeURIComponent(caseId)}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderDetail(await response.json());
    history.replaceState(null, "", `/?case=${encodeURIComponent(caseId)}`);
  } catch (error) {
    els.detail.innerHTML = `<div class="error-state"><strong>案例载入失败</strong><p>${escapeHtml(error.message)}</p></div>`;
  }
}

function renderDetail(data) {
  const input = data.input;
  const report = data.report;
  const review = data.review;
  if (!report) {
    els.detail.innerHTML = `<div class="detail-inner"><header class="detail-header"><div><p class="case-id">${escapeHtml(input.case_id)} · ${escapeHtml(input.source_type)}</p><h1>尚未运行</h1></div><div class="decision-state"><span>Agent模式</span><strong>${escapeHtml(label(els.runState.textContent.trim()))}</strong></div></header><div class="empty-state"><strong>按需执行单个Case</strong><p>案例列表不会触发模型调用。点击后只运行当前Case并缓存本次报告。</p><button id="run-case">运行当前Case</button></div></div>`;
    document.querySelector("#run-case").addEventListener("click", () => runCase(input.case_id));
    return;
  }
  const evidenceMap = Object.fromEntries(report.evidence.map((item) => [item.evidence_id, item]));
  const conflicts = report.conflicts.length
    ? report.conflicts.map((item) => `<div class="conflict">${escapeHtml(item)}</div>`).join("")
    : '<div class="empty-state"><strong>未发现冲突</strong><p>对话、业务事实和政策引用一致。</p></div>';
  const reviewPanel = review ? renderReview(review, report) : "";
  els.detail.innerHTML = `<div class="detail-inner">
    <header class="detail-header"><div><p class="case-id">${escapeHtml(input.case_id)} · ${escapeHtml(input.source_type)}</p><h1>${escapeHtml(label(report.decision))}</h1></div><div class="decision-state"><span>裁决状态</span><strong>${report.review_required ? "MANUAL REVIEW" : "AUTO DECISION"}</strong></div></header>
    <div class="metrics">${metric("Skill", report.dispute_type)}${metric("责任方", report.responsible_party)}${metric("Evidence", report.evidence_ids.length)}${metric("冲突", report.conflicts.length)}</div>
    ${reviewPanel}
    <div class="split">
      <section class="section"><div class="section-title"><h2>对话</h2><span>${input.conversation.length} MESSAGES</span></div><div class="panel">${input.conversation.map((message) => `<div class="message"><span class="speaker">${escapeHtml(message.speaker)}</span><p>${escapeHtml(message.text)}</p></div>`).join("")}</div></section>
      <section class="section"><div class="section-title"><h2>建议动作</h2></div><div class="panel action">${escapeHtml(report.recommended_action)}</div><div class="section"><div class="section-title"><h2>冲突</h2><span>${report.conflicts.length}</span></div>${conflicts}</div></section>
    </div>
    <section class="section"><div class="section-title"><h2>事件时间线</h2><span>${report.timeline.length} EVENTS</span></div><div class="panel timeline">${report.timeline.map((event) => `<div class="timeline-item"><time>${escapeHtml(event.occurred_at)}</time><div class="timeline-copy"><strong>${escapeHtml(event.kind)}</strong><p>${escapeHtml(event.summary)}</p></div></div>`).join("")}</div></section>
    <div class="split">
      <section class="section"><div class="section-title"><h2>Finding</h2><span>${report.findings.length}</span></div><div class="panel">${report.findings.map((finding) => `<article class="finding"><div class="finding-head"><span class="finding-code">${escapeHtml(finding.category)}</span><span class="finding-tags">${finding.fact_type ? `<b>${escapeHtml(finding.fact_type)}</b>` : ""}${finding.polarity ? `<b>${escapeHtml(finding.polarity)}</b>` : ""}${finding.fact_mode ? `<b>${escapeHtml(finding.fact_mode)}</b>` : ""}${finding.time_relation ? `<b>${escapeHtml(finding.time_relation)}</b>` : ""}${finding.speech_act ? `<b>${escapeHtml(finding.speech_act)}</b>` : ""}<i>${escapeHtml(finding.severity)}</i></span></div><p>${escapeHtml(finding.claim)}</p><div class="evidence-links">${finding.evidence_ids.map(escapeHtml).join(" · ")}</div></article>`).join("")}</div></section>
      <section class="section evidence"><div class="section-title"><h2>Evidence</h2><span>${report.evidence_ids.length}</span></div><div class="panel">${Object.entries(evidenceMap).map(([id, item]) => `<details><summary>${escapeHtml(id)}</summary><pre>${json(item)}</pre></details>`).join("")}</div></section>
    </div>
    <section class="section"><div class="section-title"><h2>执行轨迹</h2><span>${report.trace.length} STEPS</span></div><div class="panel">${report.trace.map((item) => `<div class="trace-row"><strong>${escapeHtml(item.stage)}</strong><code>${json(item)}</code></div>`).join("")}</div></section>
  </div>`;
  document.querySelectorAll("[data-review-action]").forEach((button) => {
    button.addEventListener("click", () => resolveReview(input.case_id, button.dataset.reviewAction));
  });
}

async function runCase(caseId) {
  const button = document.querySelector("#run-case");
  if (button) { button.disabled = true; button.textContent = "运行中…"; }
  try {
    const response = await fetch(`/api/cases/${encodeURIComponent(caseId)}/run`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    const summary = state.cases.find((item) => item.case_id === caseId);
    summary.decision = payload.report.decision;
    summary.responsible_party = payload.report.responsible_party;
    summary.review_required = payload.report.review_required;
    summary.conflict_count = payload.report.conflicts.length;
    summary.run_status = "completed";
    renderCases();
    renderDetail(payload);
  } catch (error) {
    els.detail.innerHTML = `<div class="error-state"><strong>Agent运行失败</strong><p>${escapeHtml(error.message)}</p></div>`;
  }
}

function metric(name, value) { return `<div class="metric"><span>${escapeHtml(name)}</span><strong>${escapeHtml(label(value))}</strong></div>`; }

function renderReview(review, report) {
  if (review.status === "resolved") {
    return `<section class="review-panel resolved"><div><strong>人工复检已完成</strong><p>${escapeHtml(review.reviewer_comment || "无备注")}</p></div><dl><dt>人工结论</dt><dd>${escapeHtml(label(review.reviewer_decision))}</dd><dt>责任方</dt><dd>${escapeHtml(label(review.reviewer_responsible_party))}</dd></dl></section>`;
  }
  return `<section class="review-panel"><div><strong>待人工复检</strong><p>${escapeHtml(review.reason)}</p><div class="review-evidence">${review.conflict_evidence_ids.map(escapeHtml).join(" · ")}</div></div><label for="review-comment">复检备注</label><textarea id="review-comment" rows="3" placeholder="说明确认或修改原因"></textarea><div class="review-actions"><button data-review-action="confirm">确认系统结论</button><button class="secondary" data-review-action="insufficient">标记证据不足</button></div></section>`;
}

async function resolveReview(caseId, action) {
  const selected = state.cases.find((item) => item.case_id === caseId);
  const payload = action === "confirm"
    ? { decision: selected.decision, responsible_party: selected.responsible_party }
    : { decision: "manual_review", responsible_party: "undetermined" };
  payload.comment = document.querySelector("#review-comment")?.value.trim() || "未填写备注";
  const response = await fetch(`/api/reviews/${encodeURIComponent(caseId)}/resolve`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || `HTTP ${response.status}`);
  }
  await loadCase(caseId);
}

async function boot() {
  try {
    const [response, metaResponse] = await Promise.all([fetch("/api/cases"), fetch("/api/meta")]);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    if (!metaResponse.ok) throw new Error(`HTTP ${metaResponse.status}`);
    const meta = await metaResponse.json();
    els.runState.innerHTML = `<span></span> ${escapeHtml(label(meta.agent_mode))}`;
    state.cases = await response.json();
    [...new Set(state.cases.map((item) => item.business_type))].sort().forEach((value) => {
      els.skill.insertAdjacentHTML("beforeend", `<option value="${escapeHtml(value)}">${escapeHtml(label(value))}</option>`);
    });
    filterCases();
    const requested = new URLSearchParams(location.search).get("case");
    await loadCase(state.cases.some((item) => item.case_id === requested) ? requested : state.cases[0].case_id);
  } catch (error) {
    els.detail.innerHTML = `<div class="error-state"><strong>控制台初始化失败</strong><p>${escapeHtml(error.message)}</p></div>`;
  }
}

[els.search, els.skill, els.review].forEach((element) => element.addEventListener("input", filterCases));
boot();
