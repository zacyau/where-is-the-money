(function () {
  const raw = document.getElementById("view-data");
  if (!raw) return;
  const view = JSON.parse(raw.textContent);
  const code = view.code;

  function renderAll() {
    window.renderSankey(document.getElementById("sankey"), view.flow);
    window.renderMetrics(document.getElementById("metrics"), view.metrics);
    document.getElementById("period-label").textContent = view.period.label;
  }
  renderAll();

  // ---- 桑基图下载为 PNG ----
  document.getElementById("dl-sankey").addEventListener("click", () => {
    const svgEl = document.querySelector("#sankey svg");
    if (!svgEl) return;
    const vb = (svgEl.getAttribute("viewBox") || "0 0 1180 640")
      .split(/[\s,]+/).map(Number);
    const xml = new XMLSerializer().serializeToString(svgEl);
    const img = new Image();
    img.onload = () => {
      const scale = 2;                       // 2 倍分辨率，文字更清晰
      const canvas = document.createElement("canvas");
      canvas.width = vb[2] * scale;
      canvas.height = vb[3] * scale;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#ffffff";             // SVG 透明背景 → 白底
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      const a = document.createElement("a");
      a.href = canvas.toDataURL("image/png");
      a.download = `${view.name}-资金流向-${view.period.key}.png`;
      a.click();
    };
    img.onerror = () => alert("图片生成失败，请重试");
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml);
  });

  const bar = document.getElementById("period-bar");
  bar.querySelectorAll(".pbtn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const key = btn.getAttribute("data-key");
      if (key === view.period.key) return;
      bar.querySelectorAll(".pbtn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      try {
        const [f, m] = await Promise.all([
          fetch(`/api/c/${code}/flow?period=${key}`).then((r) => r.json()),
          fetch(`/api/c/${code}/metrics?period=${key}`).then((r) => r.json()),
        ]);
        view.flow = f;
        view.metrics = m.metrics;
        view.period = m.period;
        renderAll();
        const url = new URL(window.location);
        url.searchParams.set("period", key);
        history.replaceState(null, "", url);
      } catch (e) {
        console.error(e);
      }
    });
  });
})();
