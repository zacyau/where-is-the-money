(function () {
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
    const process = m.process
      ? `<div class="metric-process"><span class="fld">过程</span>${m.process}</div>` : "";
    return `<div class="metric-card">
      <div class="metric-label">${m.label}</div>
      <div class="metric-value">${fmtVal(m)}<span class="unit">${m.unit}</span></div>
      ${yoyHtml(m)}
      ${formula}
      ${process}
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
})();
