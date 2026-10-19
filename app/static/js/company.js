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
