(function () {
  const input = document.getElementById("q");
  const box = document.getElementById("suggest");
  if (!input) return;

  let timer = null;
  let items = [];
  let active = -1;

  function go(code) {
    if (code) window.location.href = "/c/" + code;
  }

  function render() {
    if (!items.length) { box.hidden = true; return; }
    box.hidden = false;
    box.innerHTML = items.map((it, i) =>
      `<div class="item ${i === active ? "active" : ""}" data-code="${it.code}">` +
      `<span class="nm">${it.name}</span><span class="cd">${it.code}</span></div>`
    ).join("");
    box.querySelectorAll(".item").forEach((el) => {
      el.addEventListener("click", () => go(el.getAttribute("data-code")));
    });
  }

  function search(q) {
    fetch("/api/search?q=" + encodeURIComponent(q))
      .then((r) => r.json())
      .then((data) => { items = data.slice(0, 8); active = -1; render(); })
      .catch(() => { items = []; render(); });
  }

  input.addEventListener("input", () => {
    const q = input.value.trim();
    clearTimeout(timer);
    if (!q) { items = []; render(); return; }
    if (/^(sh|sz|hk)\d{4,6}$/i.test(q)) { go(q.toLowerCase()); return; }
    timer = setTimeout(() => search(q), 300);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { active = Math.min(active + 1, items.length - 1); render(); }
    else if (e.key === "ArrowUp") { active = Math.max(active - 1, 0); render(); }
    else if (e.key === "Enter") {
      if (active >= 0 && items[active]) go(items[active].code);
      else if (items[0]) go(items[0].code);
      else if (/^(sh|sz|hk)\d{4,6}$/i.test(input.value.trim())) go(input.value.trim().toLowerCase());
    } else if (e.key === "Escape") { box.hidden = true; }
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-box")) box.hidden = true;
  });
})();
