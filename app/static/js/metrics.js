(function () {
  // 计算器图标（内联 SVG）
  const CALC_ICON = `<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
    <rect x="2.5" y="1" width="11" height="14" rx="2" fill="none"
      stroke="currentColor" stroke-width="1.3"/>
    <rect x="4.7" y="3" width="6.6" height="2.8" rx="0.6" fill="currentColor"/>
    <circle cx="5.4" cy="8.6" r="0.95" fill="currentColor"/>
    <circle cx="8" cy="8.6" r="0.95" fill="currentColor"/>
    <circle cx="10.6" cy="8.6" r="0.95" fill="currentColor"/>
    <circle cx="5.4" cy="11.6" r="0.95" fill="currentColor"/>
    <circle cx="8" cy="11.6" r="0.95" fill="currentColor"/>
    <circle cx="10.6" cy="11.6" r="0.95" fill="currentColor"/>
  </svg>`;

  function fmtVal(m) {
    if (m.value == null) return "—";
    if (m.unit === "天") return m.value.toFixed(1);
    return m.value.toFixed(2);
  }

  function yoyHtml(m) {
    if (m.yoy == null) return "";
    const up = m.yoy >= 0;
    const cls = up ? "up" : "down";
    const sign = up ? "+" : "-";
    const txt = m.yoy_kind === "pp"
      ? sign + Math.abs(m.yoy).toFixed(2) + "pp"
      : sign + Math.abs(m.yoy).toFixed(1) + "%";
    return `<div class="metric-yoy ${cls}">同比 ${txt}</div>`;
  }

  function cardHtml(m) {
    const formula = m.formula
      ? `<div class="metric-formula"><span class="fld">公式</span>${m.formula}</div>` : "";
    const calcBtn = m.process
      ? `<button class="calc-btn" title="查看计算过程" aria-label="查看计算过程">${CALC_ICON}</button>`
      : "";
    const detail = m.process
      ? `<div class="metric-detail"><span class="fld">过程</span>${m.process}</div>` : "";
    return `<div class="metric-card">
      <div class="metric-label">${m.label}</div>
      <div class="metric-value-row">
        <div class="metric-value">${fmtVal(m)}<span class="unit">${m.unit}</span></div>
        ${calcBtn}
      </div>
      ${yoyHtml(m)}
      ${formula}
      ${detail}
    </div>`;
  }

  window.renderMetrics = function (container, metrics) {
    // 按分类分组（后端已按分类排序，这里保持出现顺序）
    const groups = [];
    const byCat = {};
    metrics.forEach((m) => {
      const cat = m.category || "其他";
      if (!byCat[cat]) {
        byCat[cat] = [];
        groups.push({ cat, items: byCat[cat] });
      }
      byCat[cat].push(m);
    });
    container.innerHTML = groups.map((g) =>
      `<div class="metric-group">
        <div class="metric-group-title">${g.cat}</div>
        <div class="metric-grid">${g.items.map(cardHtml).join("")}</div>
      </div>`).join("");
  };

  // 计算过程展开/收起（事件委托，切换报告期重建 DOM 后依然有效）
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".calc-btn");
    if (!btn) return;
    const card = btn.closest(".metric-card");
    if (card) card.classList.toggle("calc-open");
  });
})();
