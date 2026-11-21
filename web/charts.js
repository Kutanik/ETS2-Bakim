/* Küçük, bağımlılıksız SVG grafikleri: çizgi grafik (artı imleç + ipucu) ve ısı haritası. */
const Charts = (() => {
  const NS = "http://www.w3.org/2000/svg";

  function svg(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function div(cls, parent, text) {
    const e = document.createElement("div");
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  const NFC = new Map();
  function nf(v, d) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    if (Math.abs(v) < 0.5 * Math.pow(10, -d)) v = 0;
    const k = LANG + "|" + d;
    let f = NFC.get(k);
    if (!f) { f = new Intl.NumberFormat(LOCALES[LANG] || "tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d }); NFC.set(k, f); }
    return f.format(v);
  }
  // birim dile göre: yüzde TR %42 · EN 42% · DE 42 %
  function withUnit(text, unit) { return unit === "%" ? pct(text) : unit ? `${text} ${unit}` : text; }
  function niceStep(span, n) {
    const raw = span / Math.max(1, n);
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const f = raw / mag;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * mag;
  }
  function ticks(min, max, n) {
    if (max - min < 1e-9) { min -= 1; max += 1; }
    const st = niceStep(max - min, n);
    const lo = Math.floor(min / st) * st, hi = Math.ceil(max / st) * st;
    const out = [];
    for (let v = lo; v <= hi + st * 0.001; v += st) out.push(+v.toFixed(6));
    return out;
  }

  /* opts: {title, unit, decimals, series:[{name, color, values}], x:[], xLabel(i), xTicks(n)->[[i,label]], height, yMin, yMax} */
  function line(el, o) {
    const hoverX = el._hoverX;
    el.textContent = "";
    const ttl = div("ttl", el);
    const tb = document.createElement("b"); tb.textContent = o.title; ttl.appendChild(tb);
    const last = o.series.map(s => s.values.length ? s.values[s.values.length - 1] : null);
    const latest = document.createElement("span");
    latest.textContent = o.series.length === 1 && last[0] !== null ? `${tt("şu an")} ${withUnit(nf(last[0], o.decimals), o.unit)}` : o.unit;
    ttl.appendChild(latest);
    if (o.series.length > 1) {
      const lg = div("legend", el);
      o.series.forEach(s => {
        const it = document.createElement("span");
        const i = document.createElement("i"); i.style.background = `var(${s.color})`;
        it.appendChild(i); it.appendChild(document.createTextNode(s.name));
        lg.appendChild(it);
      });
    }
    const n = o.x.length;
    if (n < 2) { div("empty", el, tt("Veri toplanıyor…")); return; }

    const W = Math.max(260, el.clientWidth - 32), H = o.height || 160;
    const m = { l: 44, r: 12, t: 8, b: 22 };
    const pw = W - m.l - m.r, ph = H - m.t - m.b;
    let lo = Infinity, hi = -Infinity;
    o.series.forEach(s => s.values.forEach(v => { if (v !== null) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }));
    if (o.yMin !== undefined) lo = Math.min(lo, o.yMin);
    if (o.yMax !== undefined) hi = Math.max(hi, o.yMax);
    const yt = ticks(lo, hi, 4);
    lo = yt[0]; hi = yt[yt.length - 1];
    const X = i => m.l + (i / (n - 1)) * pw;
    const Y = v => m.t + ph - ((v - lo) / (hi - lo)) * ph;

    const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, height: H, role: "img", "aria-label": o.title }, el);
    yt.forEach(v => {
      svg("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: "var(--grid)", "stroke-width": 1 }, root);
      const t = svg("text", { x: m.l - 6, y: Y(v) + 4, "text-anchor": "end", "font-size": 11, fill: "var(--muted)" }, root);
      t.textContent = nf(v, Math.abs(hi - lo) < 5 ? 1 : 0);
    });
    svg("line", { x1: m.l, x2: W - m.r, y1: m.t + ph, y2: m.t + ph, stroke: "var(--axis)", "stroke-width": 1 }, root);
    (o.xTicks ? o.xTicks(n) : []).forEach(([i, lab], k, arr) => {
      const t = svg("text", { x: X(i), y: H - 5, "font-size": 11, fill: "var(--muted)",
        "text-anchor": k === 0 ? "start" : k === arr.length - 1 ? "end" : "middle" }, root);
      t.textContent = lab;
    });

    const step = Math.max(1, Math.floor(n / 500));
    o.series.forEach(s => {
      let d = "", pen = false;
      for (let i = 0; i < n; i += step) {
        const v = s.values[i];
        if (v === null || v === undefined) { pen = false; continue; }
        d += (pen ? "L" : "M") + X(i).toFixed(1) + "," + Y(v).toFixed(1);
        pen = true;
      }
      const lv = s.values[n - 1];
      if (lv !== null && lv !== undefined) d += "L" + X(n - 1).toFixed(1) + "," + Y(lv).toFixed(1);
      svg("path", { d, fill: "none", stroke: `var(${s.color})`, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, root);
      if (lv !== null && lv !== undefined)
        svg("circle", { cx: X(n - 1), cy: Y(lv), r: 4, fill: `var(${s.color})`, stroke: "var(--surface)", "stroke-width": 2 }, root);
    });

    const cross = svg("line", { y1: m.t, y2: m.t + ph, stroke: "var(--ink-2)", "stroke-width": 1, visibility: "hidden" }, root);
    const dots = o.series.map(s => svg("circle", { r: 4, fill: `var(${s.color})`, stroke: "var(--surface)", "stroke-width": 2, visibility: "hidden" }, root));
    const hit = svg("rect", { x: m.l, y: m.t, width: pw, height: ph, fill: "transparent" }, root);
    const tip = div("tip", el);

    function show(px) {
      const i = Math.round(((px - m.l) / pw) * (n - 1));
      if (i < 0 || i >= n) return hide();
      el._hoverX = px;
      cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.setAttribute("visibility", "visible");
      tip.textContent = "";
      div("hd", tip, o.xLabel ? o.xLabel(i) : "");
      o.series.forEach((s, k) => {
        const v = s.values[i];
        if (v === null || v === undefined) { dots[k].setAttribute("visibility", "hidden"); return; }
        dots[k].setAttribute("cx", X(i)); dots[k].setAttribute("cy", Y(v)); dots[k].setAttribute("visibility", "visible");
        const row = div("row", tip);
        const key = document.createElement("i"); key.style.background = `var(${s.color})`; row.appendChild(key);
        const b = document.createElement("b"); b.textContent = withUnit(nf(v, o.decimals), o.unit); row.appendChild(b);
        const sp = document.createElement("span"); sp.textContent = s.name; row.appendChild(sp);
      });
      tip.style.display = "block";
      const scale = el.querySelector("svg").getBoundingClientRect().width / W;
      let left = 16 + X(i) * scale + 12;
      if (left + tip.offsetWidth > el.clientWidth - 8) left = 16 + X(i) * scale - tip.offsetWidth - 12;
      tip.style.left = left + "px";
      tip.style.top = (root.getBoundingClientRect().top - el.getBoundingClientRect().top + 6) + "px";
    }
    function hide() {
      el._hoverX = undefined;
      cross.setAttribute("visibility", "hidden");
      dots.forEach(d => d.setAttribute("visibility", "hidden"));
      tip.style.display = "none";
    }
    hit.addEventListener("pointermove", ev => {
      const r = root.getBoundingClientRect();
      show((ev.clientX - r.left) * (W / r.width));
    });
    hit.addEventListener("pointerleave", hide);
    if (hoverX !== undefined) show(hoverX);
  }

  /* opts: {title, rows:[labels alttan üste], cols:[labels], values[col][row], unit} */
  function heatmap(el, o) {
    el.textContent = "";
    const cols = o.cols.length, rows = o.rows.length;
    let total = 0, max = 0;
    o.values.forEach(c => c.forEach(v => { total += v; max = Math.max(max, v); }));
    if (total <= 0.01) { div("empty", el, tt("Henüz motor çalışma verisi yok.")); return; }
    const W = Math.max(300, el.clientWidth - 32), H = 210;
    const m = { l: 62, r: 6, t: 6, b: 38 };
    const cw = (W - m.l - m.r) / cols, chh = (H - m.t - m.b) / rows;
    const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, height: H, role: "img", "aria-label": tt("Devir x yük haritası") }, el);
    const steps = ["--seq-1", "--seq-2", "--seq-3", "--seq-4", "--seq-5", "--seq-6", "--seq-7"];
    const tip = div("tip", el);
    for (let c = 0; c < cols; c++) {
      for (let r = 0; r < rows; r++) {
        const v = o.values[c][r];
        const t = v <= 0 ? -1 : Math.min(steps.length - 1, Math.floor(Math.sqrt(v / max) * steps.length));
        const x = m.l + c * cw + 1, y = m.t + (rows - 1 - r) * chh + 1;
        const cell = svg("rect", { class: "cell", x, y, width: cw - 2, height: chh - 2, rx: 3,
          fill: t < 0 ? "var(--seq-0)" : `var(${steps[t]})`, tabindex: 0 }, root);
        const showTip = () => {
          tip.textContent = "";
          div("hd", tip, `${o.cols[c]} ${tu("rpm")} · ${tt("Yük")} ${o.rows[r]}`);
          const row = div("row", tip);
          const b = document.createElement("b"); b.textContent = `${nf(v, 0)} ${tu("dk")}`; row.appendChild(b);
          const sp = document.createElement("span"); sp.textContent = pct(nf(v / total * 100, 1)); row.appendChild(sp);
          tip.style.display = "block";
          const scale = root.getBoundingClientRect().width / W;
          let left = 16 + (x + cw) * scale;
          if (left + tip.offsetWidth > el.clientWidth - 8) left = 16 + x * scale - tip.offsetWidth - 4;
          tip.style.left = left + "px";
          tip.style.top = (y * scale) + "px";
        };
        cell.addEventListener("pointerenter", showTip);
        cell.addEventListener("focus", showTip);
        cell.addEventListener("pointerleave", () => (tip.style.display = "none"));
        cell.addEventListener("blur", () => (tip.style.display = "none"));
      }
    }
    o.cols.forEach((lab, c) => {
      const t = svg("text", { x: m.l + c * cw + cw / 2, y: H - m.b + 15, "text-anchor": "middle", "font-size": 10.5, fill: "var(--muted)" }, root);
      t.textContent = lab;
    });
    const xl = svg("text", { x: m.l + (W - m.l - m.r) / 2, y: H - 4, "text-anchor": "middle", "font-size": 11, fill: "var(--ink-2)" }, root);
    xl.textContent = `${tt("Devir")} (${tu("rpm")})`;
    o.rows.forEach((lab, r) => {
      const t = svg("text", { x: m.l - 8, y: m.t + (rows - 1 - r) * chh + chh / 2 + 4, "text-anchor": "end", "font-size": 10.5, fill: "var(--muted)" }, root);
      t.textContent = lab;
    });
  }

  /* sütun grafiği: {title, unit, decimals, labels:[], values:[], color, valueFmt(v)} */
  function bars(el, o) {
    el.textContent = "";
    const ttl = div("ttl", el);
    const tb = document.createElement("b"); tb.textContent = o.title; ttl.appendChild(tb);
    const us = document.createElement("span"); us.textContent = o.unit || ""; ttl.appendChild(us);
    const pts = o.labels.map((l, i) => [l, o.values[i]]).filter(p => p[1] !== null && p[1] !== undefined);
    if (!pts.length) { div("empty", el, tt("Veri toplanıyor…")); return; }
    const W = Math.max(260, el.clientWidth - 32), H = o.height || 170;
    const m = { l: 36, r: 8, t: 18, b: 22 };
    const pw = W - m.l - m.r, ph = H - m.t - m.b;
    const hi = Math.max(...pts.map(p => p[1])) * 1.1 || 1;
    const yt = ticks(0, hi, 3);
    const top = yt[yt.length - 1];
    const Y = v => m.t + ph - (v / top) * ph;
    const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, height: H, role: "img", "aria-label": o.title }, el);
    yt.forEach(v => {
      svg("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: "var(--grid)", "stroke-width": 1 }, root);
      const t = svg("text", { x: m.l - 6, y: Y(v) + 4, "text-anchor": "end", "font-size": 11, fill: "var(--muted)" }, root);
      t.textContent = nf(v, 0);
    });
    const slot = pw / pts.length, bw = Math.min(24, slot * 0.6);
    const tip = div("tip", el);
    pts.forEach(([lab, v], i) => {
      const x = m.l + slot * i + (slot - bw) / 2;
      const h = Math.max(1, ph - (Y(v) - m.t));
      const d = `M${x},${m.t + ph} V${Y(v) + 4} Q${x},${Y(v)} ${x + 4},${Y(v)} H${x + bw - 4} Q${x + bw},${Y(v)} ${x + bw},${Y(v) + 4} V${m.t + ph} Z`;
      const bar = svg("path", { d: h > 5 ? d : `M${x},${m.t + ph - h} h${bw} v${h} h${-bw} Z`, fill: `var(${o.color || "--s1"})` }, root);
      const vt = svg("text", { x: x + bw / 2, y: Y(v) - 5, "text-anchor": "middle", "font-size": 11, fill: "var(--ink-2)" }, root);
      vt.textContent = o.valueFmt ? o.valueFmt(v) : nf(v, o.decimals || 0);
      const lt = svg("text", { x: x + bw / 2, y: H - 5, "text-anchor": "middle", "font-size": 11, fill: "var(--muted)" }, root);
      lt.textContent = lab;
      const hit = svg("rect", { x: m.l + slot * i, y: m.t, width: slot, height: ph, fill: "transparent" }, root);
      hit.addEventListener("pointerenter", () => {
        bar.setAttribute("opacity", "0.8");
        tip.textContent = "";
        div("hd", tip, o.tipLabel ? o.tipLabel(lab) : lab);
        const row = div("row", tip);
        const b = document.createElement("b"); b.textContent = o.valueFmt ? o.valueFmt(v) + (o.unit ? " " + o.unit : "") : withUnit(nf(v, o.decimals || 0), o.unit);
        row.appendChild(b);
        tip.style.display = "block";
        const scale = root.getBoundingClientRect().width / W;
        tip.style.left = Math.min(el.clientWidth - tip.offsetWidth - 8, 16 + (x + bw) * scale) + "px";
        tip.style.top = (Y(v) * scale) + "px";
      });
      hit.addEventListener("pointerleave", () => { bar.removeAttribute("opacity"); tip.style.display = "none"; });
    });
    svg("line", { x1: m.l, x2: W - m.r, y1: m.t + ph, y2: m.t + ph, stroke: "var(--axis)", "stroke-width": 1 }, root);
  }

  return { line, heatmap, bars, nf };
})();
