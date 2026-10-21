(function () {
  const raw = document.getElementById("view-data");
  if (!raw) return;
  const view = JSON.parse(raw.textContent);
  const code = view.code;

  function renderAll() {
    window.renderSankey(document.getElementById("sankey"), view.flow);
    window.renderMetrics(document.getElementById("metrics"), view.metrics);
    document.getElementById("period-label").textContent = view.period.label;
    renderDerive();                       // 面板展开时随报告期刷新内容
  }

  // ---- 桑基图推导过程（声明须在 renderAll() 首次调用之前）----
  const deriveBtn = document.getElementById("derive-btn");
  const derivePanel = document.getElementById("derive");
  let deriveOpen = false;

  function renderDerive() {
    if (!deriveOpen) return;
    derivePanel.innerHTML = buildDerivation(view.flow);
  }

  // ---- 桑基图下载为 PNG ----
  const dlBtn = document.getElementById("dl-sankey");

  renderAll();

  deriveBtn.addEventListener("click", () => {
    deriveOpen = !deriveOpen;
    deriveBtn.classList.toggle("active", deriveOpen);
    derivePanel.hidden = !deriveOpen;
    if (deriveOpen) renderDerive();
  });

  dlBtn.addEventListener("click", () => {
    const svgEl = document.querySelector("#sankey svg");
    if (!svgEl) return;
    const vb = (svgEl.getAttribute("viewBox") || "0 0 1180 640")
      .split(/[\s,]+/).map(Number);
    const HDR = 40;                                  // 顶部标题带高度
    const esc = (s) => String(s).replace(/[&<>"]/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    const title = esc(
      (view.name || view.code) +
      (view.period && view.period.label ? " · " + view.period.label : "")
    );
    // 在 SVG 顶部注入股票名称（含报告期）标题，内容整体下移，页内显示不变
    const xml =
      `<svg xmlns="http://www.w3.org/2000/svg" ` +
      `viewBox="0 0 ${vb[2]} ${vb[3] + HDR}" ` +
      `font-family="PingFang SC, Microsoft YaHei, Hiragino Sans GB, sans-serif">` +
      `<text x="26" y="28" font-size="20" font-weight="700" fill="#1c1c1c">${title}</text>` +
      `<g transform="translate(0, ${HDR})">${svgEl.innerHTML}</g>` +
      `</svg>`;
    const img = new Image();
    img.onload = () => {
      const scale = 2;                       // 2 倍分辨率，文字更清晰
      const canvas = document.createElement("canvas");
      canvas.width = vb[2] * scale;
      canvas.height = (vb[3] + HDR) * scale;
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

  // ---- 桑基图数据推导过程（六步，与图上节点一一对应）----
  function buildDerivation(flow) {
    const byId = {};
    flow.nodes.forEach((n) => (byId[n.id] = n));
    const segs = flow.nodes.filter((n) => /^seg\d+$/.test(n.id));
    const val = (id) => (byId[id] ? byId[id].value : 0);
    const yi2 = (v) => (Math.abs(v) / 1e8).toFixed(2) + "亿";   // 等式右侧分量：用绝对值，符号由 ± 运算符表达
    const signed2 = (v) => (v < 0 ? "−" : "") + (Math.abs(v) / 1e8).toFixed(2) + "亿"; // 等式左侧总项：带符号

    // 渲染一行等式：leftLabel leftVal = term1 ± term2 ...
    // terms: [{label, v, kind, nloss?}]，v 为对左侧的实际贡献（带符号）
    //   kind="sub"：成本类，恒负向，量值恒正，显示为「− 名称 量值亿」
    //   kind="add"：收益类，可正可负；负值把负号内联到数字上（如「营业利润 −125.13亿」），避免读作「减去正数」
    function eq(no, title, leftLabel, leftVal, terms, note) {
      let right = "", sum = 0;
      terms.forEach((t, i) => {
        const neg = t.v < 0;
        const label = neg && t.nloss ? t.nloss : t.label;
        let sep, num;
        if (t.kind === "sub") {
          sep = i === 0 ? "" : " − ";
          num = yi2(Math.abs(t.v));
        } else {
          sep = i === 0 ? "" : " + ";
          num = (neg && t.nloss) ? yi2(Math.abs(t.v)) : signed2(t.v);
        }
        right += `${sep}<b>${label}</b> ${num}`;
        sum += t.v;
      });
      const diff = (leftVal - sum) / 1e8;
      const diffNote = Math.abs(diff) >= 0.005
        ? `<span class="derive-diff">（因四舍五入，右侧各项之和与左侧相差约 ${Math.abs(diff).toFixed(2)} 亿）</span>`
        : "";
      return `<div class="derive-step">
        <div class="derive-title"><span class="no">${no}</span>${title}</div>
        <div class="derive-eq">${leftLabel} <b>${signed2(leftVal)}</b> = ${right}${diffNote}</div>
        ${note ? `<div class="derive-note">注：${note}</div>` : ""}
      </div>`;
    }

    const rev = val("rev"), cost = val("cost"), gross = val("gross"),
      tax = val("tax"), expense = val("expense"), other = val("other"),
      impair = val("impair"), op = val("op"), nonbiz = val("nonbiz"),
      tp = val("tp"), taxfee = val("taxfee"), np = val("np"),
      parent = val("parent"), minor = val("minor");

    let html = `<div class="derive-head">单位：亿元（保留 2 位小数）。以下推导与桑基图
      各节点一一对应，等式右侧各项为左侧金额的构成。</div>`;

    // 1 收入端
    const segTerms = segs.map((s) => ({ label: s.label, v: s.value, kind: "add" }));
    html += eq(1, "收入端（最左侧）", "营业收入", rev, segTerms,
      "营业收入由各业务分部构成；「其他(含抵销)」为抵销项及未单独列示分部的合计。");

    // 2 毛利端
    html += eq(2, "毛利端", "毛利", gross,
      [{ label: "营业收入", v: rev, kind: "add" },
       { label: "营业成本", v: -cost, kind: "sub" }],
      "营业成本指与生产经营直接相关的成本（如原料、包装、人工、制造费用等）。");

    // 3 营业利润端
    html += eq(3, "营业利润端", "营业利润", op,
      [{ label: "毛利", v: gross, kind: "add" },
       { label: "税金及附加", v: -tax, kind: "sub" },
       { label: "期间费用", v: -expense, kind: "sub" },
       { label: "其他经营收益", v: other, kind: "add", nloss: "其他经营损失" },
       { label: "减值及处置损失", v: -impair, kind: "sub" }],
      "期间费用通常包含销售费用、管理费用、研发费用和财务费用；" +
      "税金及附加主要为消费税、城建税等经营相关税费；" +
      "减值及处置损失为资产减值损失与处置损失合计。");

    // 4 利润总额端
    html += eq(4, "利润总额端", "利润总额", tp,
      [{ label: "营业利润", v: op, kind: "add" },
       { label: "营业外净收入", v: nonbiz, kind: "add", nloss: "营业外净支出" }],
      "营业外收支指与主营业务无关的收入或支出，如政府补助、非流动资产毁损报废等。");

    // 5 净利润端
    html += eq(5, "净利润端", "净利润", np,
      [{ label: "利润总额", v: tp, kind: "add" },
       { label: "所得税费用", v: -taxfee, kind: "sub" }],
      "所得税费用为当期确认的所得税，与会计利润的差额源于税会差异。");

    // 6 净利润分配
    html += eq(6, "净利润分配（最右侧）", "净利润", np,
      [{ label: "归母净利润", v: parent, kind: "add" },
       { label: "少数股东权益", v: minor, kind: "add", nloss: "少数股东亏损" }],
      "归母净利润归属于母公司股东；少数股东权益归属于控股子公司中的其他小股东。");

    return html;
  }

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
