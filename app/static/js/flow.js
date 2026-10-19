// 自研 SVG 桑基图渲染：固定列布局 + 三次贝塞尔缎带
(function () {
  const ROLE = {
    gray:  { band: "#cfcfcf", text: "#4a4a4a" },
    green: { band: "#9fd3a8", text: "#1b7a30" },
    red:   { band: "#f4a9a9", text: "#b02525" },
    blue:  { band: "#aacdec", text: "#155fa8" },
  };

  function fmt(v) {
    if (v == null) return "—";
    return (v / 1e8).toFixed(1);
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  window.renderSankey = function (container, flow) {
    const W = 1120, marginV = 26, marginH = 26;
    const nodeW = 66, gap = 10, maxCol = 10;
    const usableH = 560;
    const H = usableH + marginV * 2;
    const colGap = (W - marginH * 2 - nodeW) / maxCol;

    const scale = flow.scale || 1;
    const minH = 16;

    const byId = {};
    flow.nodes.forEach((n) => (byId[n.id] = n));
    const cols = {};
    flow.nodes.forEach((n) => {
      (cols[n.col] = cols[n.col] || []).push(n);
    });

    // 放置节点
    const place = {};
    Object.keys(cols).forEach((c) => {
      const list = cols[c];
      const hs = list.map((n) =>
        Math.max((Math.abs(n.value) / scale) * usableH, minH));
      const total = hs.reduce((a, b) => a + b, 0) + gap * (list.length - 1);
      let y = marginV + Math.max(0, (usableH - total) / 2);
      list.forEach((n, i) => {
        const h = hs[i];
        const x = marginH + Number(c) * colGap;
        place[n.id] = { x, y, h, w: nodeW };
        y += h + gap;
      });
    });

    // 链接分组
    const out = {}, inn = {};
    flow.links.forEach((l) => {
      (out[l.source] = out[l.source] || []).push(l);
      (inn[l.target] = inn[l.target] || []).push(l);
    });
    Object.values(out).forEach((arr) =>
      arr.sort((a, b) => byId[a.target].col - byId[b.target].col));
    Object.values(inn).forEach((arr) =>
      arr.sort((a, b) => byId[a.source].col - byId[b.source].col));

    const seg = {};
    flow.links.forEach((l) => {
      const s = place[l.source], t = place[l.target];
      const th = Math.max((Math.abs(l.value) / scale) * usableH, 1);
      seg[l.source] = seg[l.source] || s.y;
      l._sy = seg[l.source];
      seg[l.source] += th;
      seg["in:" + l.target] = seg["in:" + l.target] || t.y;
      l._ty = seg["in:" + l.target];
      seg["in:" + l.target] += th;
      l._th = th;
    });

    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" xmlns="http://www.w3.org/2000/svg">`;
    svg += `<title>${esc("资金流向桑基图")}</title>`;

    // 缎带
    flow.links.forEach((l, i) => {
      const s = place[l.source], t = place[l.target];
      const x0 = s.x + s.w, x1 = t.x;
      const cx = (x0 + x1) / 2;
      const sy0 = l._sy, ty0 = l._ty, th = l._th;
      const col = (ROLE[l.role] || ROLE.gray).band;
      const d = `M${x0},${sy0} C${cx},${sy0} ${cx},${ty0} ${x1},${ty0} ` +
        `L${x1},${ty0 + th} C${cx},${ty0 + th} ${cx},${sy0 + th} ${x0},${sy0 + th} Z`;
      svg += `<path class="rib" data-src="${l.source}" data-tgt="${l.target}" d="${d}" ` +
        `fill="${col}" fill-opacity="0.5"></path>`;
    });

    // 节点 + 标签
    flow.nodes.forEach((n) => {
      const p = place[n.id];
      const rc = ROLE[n.role] || ROLE.gray;
      svg += `<rect class="node" data-id="${n.id}" x="${p.x}" y="${p.y}" width="${p.w}" height="${p.h}" rx="3" ` +
        `fill="${rc.band}" fill-opacity="0.85"></rect>`;
      const cy = p.y + p.h / 2;
      if (p.h >= 30) {
        svg += `<text x="${p.x + p.w / 2}" y="${cy - 7}" text-anchor="middle" ` +
          `font-size="13" font-weight="700" fill="${rc.text}">${esc(n.label)}</text>`;
        svg += `<text x="${p.x + p.w / 2}" y="${cy + 9}" text-anchor="middle" ` +
          `font-size="12" fill="${rc.text}">${fmt(n.value)}</text>`;
      } else {
        const outside = n.col == 0 ? "end" : "start";
        const tx = n.col == 0 ? p.x - 6 : p.x + p.w + 6;
        const val = n.signed && n.value < 0
          ? fmt(n.value) : fmt(n.value);
        svg += `<text x="${tx}" y="${cy - 2}" text-anchor="${outside}" ` +
          `font-size="12" font-weight="600" fill="${rc.text}">${esc(n.label)}</text>`;
        svg += `<text x="${tx}" y="${cy + 12}" text-anchor="${outside}" ` +
          `font-size="12" fill="${rc.text}">${val}</text>`;
      }
    });

    svg += `</svg>`;
    container.innerHTML = svg;

    // 交互：hover 高亮同链
    const links = container.querySelectorAll(".rib");
    container.querySelectorAll(".node").forEach((node) => {
      node.addEventListener("mouseenter", () => {
        const id = node.getAttribute("data-id");
        links.forEach((rb) => {
          const hit = rb.getAttribute("data-src") === id ||
            rb.getAttribute("data-tgt") === id;
          rb.setAttribute("fill-opacity", hit ? "0.8" : "0.12");
        });
      });
      node.addEventListener("mouseleave", () => {
        links.forEach((rb) => rb.setAttribute("fill-opacity", "0.5"));
      });
    });
  };
})();
