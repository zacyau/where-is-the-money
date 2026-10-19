// 自研 SVG 桑基图渲染 —— 对标「XX的钱去哪了」手工版式：
// 细竖条节点 + 标签外置（名称黑体/彩色数值/同比）+ 灰绿粉蓝四色缎带 + 主链水平对齐
(function () {
  const W = 1180, H = 640;
  const BW = 9;                       // 节点竖条宽
  const T_TOP = 24, T_BOT = 632;      // 版心上下界
  const GAP_SEG = 14, GAP_CHAIN = 6;  // 分部间隔 / 成本-毛利间隔

  // 列 x 坐标（竖条左缘）
  const XLUT = {
    seg: 26, rev: 244, cost: 442, gross: 442, other: 442,
    expense: 610, tax: 610, op: 610, impair: 610,
    nonbiz: 778, tp: 778, taxfee: 946, np: 946,
    minor: 1076, parent: 1076,
  };

  const C = {
    gray:  { rib: "#d8d8d8", bar: "#6e6e6e" },
    cost:  { rib: "#b7dab2", bar: "#2f9e44" },
    red:   { rib: "#f4b9b9", bar: "#e4403a" },
    blue:  { rib: "#b5d4f2", bar: "#4d9fe8" },
    rev:   { rib: "#f4b9b9", bar: "#b02525" },
  };
  const T = { black: "#1c1c1c", gray: "#8a8a8a", red: "#d5302f",
              green: "#1e8a3d", blue: "#2270c8" };

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }
  function yi(v) {                    // 元 → "1193.2亿"（带符号）
    const s = v < 0 ? "-" : "";
    return s + (Math.abs(v) / 1e8).toFixed(1) + "亿";
  }
  function pct(v) {                   // 同比 → "+36.7%"
    if (v == null) return null;
    return (v >= 0 ? "+" : "-") + Math.abs(v).toFixed(1) + "%";
  }

  // 各节点出/入缎带的上下排序（不存在的方向自动跳过）
  const OUT_ORDER = {
    rev: ["cost", "gross"], gross: ["expense", "tax", "op", "impair", "other"],
    op: ["tp", "nonbiz"], tp: ["np", "taxfee"], np: ["parent", "minor"],
  };
  const IN_ORDER = {
    op: ["gross", "other"], tp: ["op", "nonbiz"],
  };

  window.renderSankey = function (container, flow) {
    const byId = {};
    flow.nodes.forEach((n) => (byId[n.id] = n));
    const segs = flow.nodes.filter((n) => n.id.startsWith("seg")).slice()
      .sort((a, b) => b.value - a.value);
    const V = {};                     // 亿为单位
    flow.nodes.forEach((n) => (V[n.id] = Math.abs(n.value) / 1e8));

    const cost = V.cost, gross = V.gross, op = V.op, expense = V.expense,
      tax = V.tax, impair = V.impair, rev = V.rev, np = V.np,
      taxfee = V.taxfee, parent = V.parent, minor = V.minor;

    // ---- 二分求比例 s（px / 亿），保证所有列在版心内 ----
    function layout(s) {
      const T0 = Math.max(
        T_TOP,
        56 + (tax + expense) * s - GAP_CHAIN - cost * s - (gross - op) * s / 2
      );
      const yGC = T0 + GAP_CHAIN + cost * s + (gross * s) / 2;   // 主链中心
      const gb = T0 + GAP_CHAIN + cost * s + gross * s;          // 毛利底
      const bottoms = [
        gb + 31,                                                 // other 标签
        yGC + (op * s) / 2 + 21 + impair * s + 46,               // impair 标签
        yGC + (np * s) / 2 + 18 + Math.max(taxfee * s, 5) + 46,  // taxfee 标签
        yGC + (parent * s) / 2 + 18 + Math.max(minor * s, 5) + 46,
      ];
      const segBottom = T0 + rev * s + (segs.length - 1) * GAP_SEG;
      return {
        ok: Math.max(...bottoms) <= T_BOT && segBottom <= T_BOT + 4,
        T0, yGC,
      };
    }
    let lo = 0.02, hi = 3.0, best = layout(lo);
    for (let i = 0; i < 48; i++) {
      const mid = (lo + hi) / 2, r = layout(mid);
      if (r.ok) { lo = mid; best = r; } else { hi = mid; }
    }
    const s = lo, T0 = best.T0, yGC = best.yGC;

    // ---- 节点位置 ----
    const pos = {};
    function put(id, x, y, hgt) { pos[id] = { x, y, h: Math.max(hgt, 4) }; }
    const h = (v) => v * s;

    // 成本/毛利块 + 营业收入条
    put("cost", XLUT.cost, T0, Math.max(h(cost), 8));
    put("gross", XLUT.gross, T0 + h(cost) + GAP_CHAIN, Math.max(h(gross), 12));
    put("rev", XLUT.rev, T0, h(cost) + GAP_CHAIN + h(gross));
    // 分部
    let sy = T0;
    segs.forEach((n) => {
      put(n.id, XLUT.seg, sy, Math.max(h(V[n.id]), 3));
      sy += Math.max(h(V[n.id]), 3) + GAP_SEG;
    });
    // 主链（与毛利同中心）
    [["op", XLUT.op], ["tp", XLUT.tp], ["np", XLUT.np], ["parent", XLUT.parent]]
      .forEach(([id, x]) =>
        put(id, x, yGC - Math.max(h(V[id]), 12) / 2, Math.max(h(V[id]), 12)));
    // 上方：期间费用、税金及附加
    const opTop = pos.op.y;
    put("tax", XLUT.tax, opTop - 34 - Math.max(h(tax), 5), Math.max(h(tax), 5));
    put("expense", XLUT.expense, pos.tax.y - 12 - Math.max(h(expense), 5),
      Math.max(h(expense), 5));
    // 下方小节点
    put("impair", XLUT.impair, pos.op.y + pos.op.h + 16, Math.max(h(impair), 5));
    put("other", XLUT.other, pos.gross.y + pos.gross.h + 26, Math.max(h(V.other), 5));
    put("nonbiz", XLUT.nonbiz, pos.tp.y + pos.tp.h + 18, Math.max(h(V.nonbiz), 5));
    put("taxfee", XLUT.taxfee, pos.np.y + pos.np.h + 18, Math.max(h(taxfee), 5));
    if (minor > 0.01)
      put("minor", XLUT.minor, pos.parent.y + pos.parent.h + 18, Math.max(h(minor), 5));

    // ---- 缎带偏移 ----
    const links = flow.links.filter(
      (l) => l.value > 1 && pos[l.source] && pos[l.target]);
    const outs = {}, ins = {};
    links.forEach((l) => {
      (outs[l.source] = outs[l.source] || []).push(l);
      (ins[l.target] = ins[l.target] || []).push(l);
    });
    const orderSort = (arr, order, keyOf) => {
      if (!order) return arr;
      return arr.slice().sort((a, b) => {
        const ia = order.indexOf(keyOf(a));
        const ib = order.indexOf(keyOf(b));
        return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
      });
    };
    Object.keys(outs).forEach((id) => {
      outs[id] = orderSort(outs[id], OUT_ORDER[id], (l) => l.target);
    });
    Object.keys(ins).forEach((id) => {
      ins[id] = orderSort(ins[id], IN_ORDER[id], (l) => l.source);
    });
    // 分部入流按值降序（与自上而下布局一致）
    if (ins.rev) ins.rev.sort((a, b) => b.value - a.value);

    function assign(map, node, key) {
      let y = node.y;
      map.forEach((l) => {
        const th = Math.max((Math.abs(l.value) / 1e8) * s, 2);
        l[key] = y;
        y += th;
      });
    }
    Object.keys(outs).forEach((id) => assign(outs[id], pos[id], "_sy"));
    Object.keys(ins).forEach((id) => assign(ins[id], pos[id], "_ty"));

    // ---- 生成 SVG ----
    let svg = "";

    // 缎带
    links.forEach((l) => {
      const p = pos[l.source], q = pos[l.target];
      const x0 = p.x + BW, x1 = q.x, cx = (x0 + x1) / 2;
      const sy0 = l._sy, ty0 = l._ty;
      const th = Math.max((Math.abs(l.value) / 1e8) * s, 2);
      const col = (C[l.role] || C.gray).rib;
      const d = `M${x0},${sy0} C${cx},${sy0} ${cx},${ty0} ${x1},${ty0} ` +
        `L${x1},${ty0 + th} C${cx},${ty0 + th} ${cx},${sy0 + th} ${x0},${sy0 + th} Z`;
      svg += `<path class="rib" data-src="${l.source}" data-tgt="${l.target}" ` +
        `d="${d}" fill="${col}" fill-opacity="0.92"></path>`;
    });

    // 节点竖条
    flow.nodes.forEach((n) => {
      if (!pos[n.id]) return;
      const p = pos[n.id];
      const bar = (C[n.role] || C.gray).bar;
      svg += `<rect class="node" data-id="${n.id}" x="${p.x}" y="${p.y}" ` +
        `width="${BW}" height="${p.h}" rx="1.5" fill="${bar}"></rect>`;
    });

    // ---- 标签 ----
    const texts = [];
    let maxBottom = 0;   // 所有文字块的最大底部 y（含字高余量）
    function block(x, y, lines, anchor) {
      let cy = y;
      lines.forEach((ln) => {
        texts.push(
          `<text x="${x}" y="${cy}" text-anchor="${anchor}" font-size="${ln.size}" ` +
          `font-weight="${ln.weight}" fill="${ln.color}">${esc(ln.t)}</text>`);
        maxBottom = Math.max(maxBottom, cy + ln.size * 0.4);
        cy += ln.lh;
      });
    }
    const L = (t, size, color, weight, lh) =>
      ({ t, size, color, weight: weight || 400, lh: lh || 21 });
    // n 行文字块相对条居中的起始基线
    const centerBase = (nLines, hBar) => hBar / 2 - (nLines * 20) / 2 + 14;

    // 分部（带内右侧，防碰撞下推）
    let prevBottom = -1e9;
    segs.forEach((n) => {
      const p = pos[n.id];
      const yy = pct(n.yoy);
      const nL = yy ? 3 : 2;
      let ly = Math.max(p.y + centerBase(nL, p.h), prevBottom + 6);
      const lines = [L(n.label, 15, T.black, 700, 22),
        L(`${yi(n.value)} • ${((n.ratio || 0) * 100).toFixed(1)}%`, 13.5, T.gray, 400, 21)];
      if (yy) lines.push(L("同比" + yy, 13.5, T.gray, 400, 21));
      prevBottom = ly + (yy ? 63 : 41);
      block(p.x + BW + 18, ly, lines, "start");
    });

    // 营业收入（条下方左对齐）
    {
      const yy = pct(byId.rev.yoy);
      const lines = [L("营业收入", 16, T.black, 700, 23),
        L(yi(byId.rev.value), 15, T.black, 700, 21)];
      if (yy) lines.push(L("同比" + yy, 13.5, T.gray));
      block(pos.rev.x - 2, pos.rev.y + pos.rev.h + 30, lines, "start");
    }

    // 营业成本（条左侧右对齐，绿色）
    {
      const yy = pct(byId.cost.yoy);
      const lines = [L("营业成本", 16, T.green, 700, 23),
        L(yi(byId.cost.value), 15, T.green, 700, 21)];
      if (yy) lines.push(L("同比" + yy, 13.5, T.green));
      block(pos.cost.x - 14, pos.cost.y + centerBase(lines.length, pos.cost.h),
        lines, "end");
    }

    // 毛利（条右侧）
    block(pos.gross.x + BW + 14, pos.gross.y + centerBase(2, pos.gross.h),
      [L("毛利", 16, T.black, 700, 23), L(yi(byId.gross.value), 15, T.red, 700)],
      "start");

    // 期间费用（条上方居中）
    block(pos.expense.x + BW / 2, pos.expense.y - 40,
      [L("期间费用", 15, T.black, 700, 20),
       L(yi(byId.expense.value), 15, T.green, 700)], "middle");

    // 税金及附加（条右侧）
    block(pos.tax.x + BW + 12, pos.tax.y + centerBase(2, pos.tax.h),
      [L("税金及附加", 14.5, T.black, 700, 20),
       L(yi(byId.tax.value), 14.5, T.blue, 700)], "start");

    // 营业利润（条右侧）
    block(pos.op.x + BW + 14, pos.op.y + centerBase(2, pos.op.h),
      [L("营业利润", 16, T.black, 700, 23),
       L(yi(byId.op.value), 15, T.red, 700)], "start");

    // 减值及处置损失（条下方居中）
    block(pos.impair.x + BW / 2, pos.impair.y + pos.impair.h + 22,
      [L("减值及处置损失", 14.5, T.black, 700, 20),
       L(yi(byId.impair.value), 15, T.green, 700)], "middle");

    // 其他经营收益（条下方居中）
    block(pos.other.x + BW / 2, pos.other.y + pos.other.h + 22,
      [L("其他经营收益", 14.5, T.black, 700, 20),
       L(yi(byId.other.value), 15, T.red, 700)], "middle");

    // 营业外净收入（条下方居中）
    block(pos.nonbiz.x + BW / 2, pos.nonbiz.y + pos.nonbiz.h + 22,
      [L("营业外净收入", 14.5, T.black, 700, 20),
       L(yi(byId.nonbiz.value), 15, T.red, 700)], "middle");

    // 利润总额（条右侧）
    block(pos.tp.x + BW + 14, pos.tp.y + centerBase(2, pos.tp.h),
      [L("利润总额", 16, T.black, 700, 23),
       L(yi(byId.tp.value), 15, T.red, 700)], "start");

    // 净利润（条右侧，带同比）
    {
      const yy = pct(byId.np.yoy);
      const lines = [L("净利润", 16, T.black, 700, 23),
        L(yi(byId.np.value), 15, T.red, 700, 21)];
      if (yy) lines.push(L("同比" + yy, 13.5, T.red));
      block(pos.np.x + BW + 14, pos.np.y + centerBase(lines.length, pos.np.h),
        lines, "start");
    }

    // 所得税费用（条下方居中）
    block(pos.taxfee.x + BW / 2, pos.taxfee.y + pos.taxfee.h + 22,
      [L("所得税费用", 14.5, T.black, 700, 20),
       L(yi(byId.taxfee.value), 14.5, T.blue, 700)], "middle");

    // 归母净利润（条右侧）
    if (pos.parent)
      block(pos.parent.x + BW + 14, pos.parent.y + centerBase(2, pos.parent.h),
        [L("归母净利润", 16, T.black, 700, 23),
         L(yi(byId.parent.value), 15, T.red, 700)], "start");

    // 少数股东权益（条下方居中）
    if (pos.minor)
      block(pos.minor.x + BW / 2, pos.minor.y + pos.minor.h + 22,
        [L("少数股东权益", 14.5, T.black, 700, 20),
         L(yi(byId.minor.value), 15, T.red, 700)], "middle");

    svg += texts.join("");

    // 动态画布高度：底部标签可能超出固定版心（T_BOT=632），按实际内容扩展，避免文字被截断
    Object.keys(pos).forEach((id) => {
      maxBottom = Math.max(maxBottom, pos[id].y + pos[id].h);
    });
    const H2 = Math.max(H, Math.ceil(maxBottom + 14));
    container.innerHTML =
      `<svg viewBox="0 0 ${W} ${H2}" xmlns="http://www.w3.org/2000/svg">` +
      svg + `</svg>`;

    // 交互：hover 高亮同链
    const ribs = container.querySelectorAll(".rib");
    container.querySelectorAll(".node").forEach((node) => {
      node.addEventListener("mouseenter", () => {
        const id = node.getAttribute("data-id");
        ribs.forEach((rb) => {
          const hit = rb.getAttribute("data-src") === id ||
            rb.getAttribute("data-tgt") === id;
          rb.setAttribute("fill-opacity", hit ? "1" : "0.25");
        });
      });
      node.addEventListener("mouseleave", () => {
        ribs.forEach((rb) => rb.setAttribute("fill-opacity", "0.92"));
      });
    });
  };
})();
