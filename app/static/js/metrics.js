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
    const arrow = up ? "▲" : "▼";
    const txt = m.yoy_kind === "pp"
      ? Math.abs(m.yoy).toFixed(2) + "pp"
      : Math.abs(m.yoy).toFixed(1) + "%";
    return `<div class="metric-yoy ${cls}">${arrow} 同比 ${txt}</div>`;
  }

  function sparkline(history) {
    if (!history || history.filter((x) => x != null).length < 2) return "";
    const vals = history.filter((x) => x != null);
    const min = Math.min(...vals), max = Math.max(...vals);
    const span = max - min || 1;
    const w = 100, h = 34, pad = 3;
    const n = history.length;
    const pts = history.map((v, i) => {
      const x = pad + (i / (n - 1)) * (w - pad * 2);
      const y = h - pad - ((v == null ? min : v) - min) / span * (h - pad * 2);
      return [x, y];
    });
    const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
    const last = pts[pts.length - 1];
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" ` +
      `width="100%" height="${h}">` +
      `<path d="${d}" fill="none" stroke="#1c7ed6" stroke-width="1.5"></path>` +
      `<circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="2" fill="#1c7ed6"></circle>` +
      `</svg>`;
  }

  window.renderMetrics = function (container, metrics) {
    container.innerHTML = metrics.map((m) => {
      const cal = m.caliber
        ? `<div class="metric-cal" title="${m.caliber}">${m.caliber}</div>` : "";
      return `<div class="metric-card">
        <div class="metric-label">${m.label}</div>
        <div class="metric-value">${fmtVal(m)}<span class="unit">${m.unit}</span></div>
        ${yoyHtml(m)}
        <div class="metric-spark">${sparkline(m.history)}</div>
        ${cal}
      </div>`;
    }).join("");
  };
})();
