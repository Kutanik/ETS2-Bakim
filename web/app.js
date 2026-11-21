/* ETS2 Bakım Simülatörü arayüzü */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
let S = null, D = null, H = [], tab = "ozet";
let optionsKey = null, settingsReady = false, specKey = null, lastMsgAt = 0, lineupKey = null, profileMode = null;
let showAllAlerts = false;
const DAYS = { tr: ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"], en: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], de: ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"] };

/* ---------------- yardımcılar ---------------- */
function get(o, path) {
  return path.split(".").reduce((a, k) => (a === null || a === undefined ? undefined : a[k]), o);
}
// sayı biçimleyicileri dil / basamak başına bir kez kurulur (toLocaleString her çağrıda yenisini kurar: yavaş)
const NF_CACHE = new Map();
function nf(v, d = 0, group = false) {
  if (v === null || v === undefined || Number.isNaN(v)) return null;
  if (Math.abs(v) < 0.5 * Math.pow(10, -d)) v = 0;
  const key = LANG + "|" + d + "|" + (group ? 1 : 0);
  let f = NF_CACHE.get(key);
  if (!f) {
    f = new Intl.NumberFormat(LOCALES[LANG], { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: group });
    NF_CACHE.set(key, f);
  }
  return f.format(Number(v));
}
// değişmeyen değer yeniden yazılmaz (aynı metni / sınıfı yazmak da sayfayı yeniden düzenletir)
function setClass(el, cls) { if (el.className !== cls) el.className = cls; }
function setTitle(el, text) { if (el.title !== text) el.title = text; }
// sayfadaki sabit öğe listeleri bir kez aranır (her yenilemede querySelectorAll yerine)
const QS_CACHE = new Map();
function $$c(sel) {
  let l = QS_CACHE.get(sel);
  if (!l) { l = $$(sel); QS_CACHE.set(sel, l); }
  return l;
}
function dur(min) {
  if (min === null || min === undefined) return "—";
  const m = Math.max(0, Math.round(min));
  return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}`;
}
function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }
// para birimi: oyunda seçili olan (ya da Ayarlar'da elle); uygulamanın tutarları avro tabanlı ve kurla çevrilir
function curInfo() { return (S && S.status && S.status.currency) || { symbol: "€", rate: 1 }; }
function cur() { return curInfo().symbol; }
function money(v, d = 0) {
  if (v === null || v === undefined) return "—";
  const c = curInfo(), s = nf(v * c.rate, d, true);
  return c.symbol.length === 1 ? c.symbol + s : `${s} ${c.symbol}`;
}

const ICON = {
  good: '<svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8.5l3 3 7-7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  warn: '<svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1.5l7 13H1z" fill="currentColor"/><path d="M8 6v4M8 12v.5" stroke="var(--surface)" stroke-width="1.8" stroke-linecap="round"/></svg>',
  crit: '<svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="7" fill="currentColor"/><path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="var(--surface)" stroke-width="1.8" stroke-linecap="round"/></svg>',
  info: '<svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="7" fill="currentColor"/><path d="M8 7v4.5M8 4.5v.5" stroke="var(--surface)" stroke-width="1.8" stroke-linecap="round"/></svg>',
  muted: '<svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
};
const LVL_COLOR = { crit: "var(--crit)", warn: "var(--warn)", info: "var(--accent)" };

/* durum kuralları: [seviye, Türkçe etiket] */
const RULES = {
  coolTemp: s => { const t = s.thermal.t_cool; return t < 60 ? ["muted", "Soğuk"] : t < 104 ? ["good", "Normal"] : t < 110 ? ["warn", "Yüksek"] : ["crit", s.thermal.boiling ? "Kaynıyor" : "Hararet"]; },
  oilTemp: s => { const t = s.thermal.t_oil; return t < 50 ? ["muted", "Soğuk"] : t < 120 ? ["good", "Normal"] : t < 135 ? ["warn", "Yüksek"] : ["crit", "Aşırı"]; },
  oilPress: s => { if (!s.live.running) return ["muted", "Motor kapalı"]; const p = s.oil.pressure, th = s.oil.low_thr; return p < th ? ["crit", "Düşük"] : p < th + 0.5 ? ["warn", "Sınırda"] : ["good", "Normal"]; },
  volt: s => { const v = s.battery.voltage, k = (s.battery.volts || 24) / 24; if (s.live.running) return v >= 27 * k ? ["good", "Şarj ediyor"] : v >= 25.5 * k ? ["warn", "Zayıf şarj"] : ["crit", "Şarj yok"]; return v >= 24.6 * k ? ["good", "Dolu"] : v >= 24.2 * k ? ["warn", "Yarı dolu"] : ["crit", "Boş"]; },
  life: s => { const v = s.oil.life; return v >= 30 ? ["good", "İyi"] : v >= 10 ? ["warn", "Değişim yakın"] : ["crit", "Değiştirin"]; },
  oilLevel: s => { const v = s.oil.level_pct; return v > 106 ? ["warn", "Fazla"] : v >= s.oil.min_pct ? ["good", "Normal"] : v >= 70 ? ["warn", "MIN altı"] : ["crit", "Kritik"]; },
  coolLevel: s => { const v = s.coolant.level_pct; return v >= 85 ? ["good", "Normal"] : v >= 70 ? ["warn", "Düşük"] : ["crit", "Kritik"]; },
  freeze: s => { const f = s.coolant.freeze, a = s.location.ambient, e = s.location.expected_min; return a < f ? ["crit", "Donuyor"] : e < f ? ["warn", "Yetersiz"] : ["good", "Yeterli"]; },
  inhibitor: s => { const v = s.coolant.inhibitor; return v >= 50 ? ["good", "İyi"] : v >= 30 ? ["warn", "Azalıyor"] : ["crit", "Tükendi"]; },
  soc: s => { const v = s.battery.soc; return v >= 75 ? ["good", "İyi"] : v >= 50 ? ["warn", "Düşük"] : ["crit", "Çok düşük"]; },
  soh: s => { const v = s.battery.soh; return v >= 80 ? ["good", "İyi"] : v >= 60 ? ["warn", "Yıpranmış"] : ["crit", "Değiştirin"]; },
  dpf: s => { if (!s.dpf.enabled) return ["muted", "DPF yok"]; const v = s.dpf.soot; return s.dpf.burning ? ["warn", "Rejenerasyon "] : v < 75 ? ["good", "Normal"] : v < 100 ? ["warn", "Dolu"] : ["crit", "Tıkalı"]; },
  ash: s => { const v = s.dpf.ash; return v < 70 ? ["good", "Normal"] : v < 85 ? ["warn", "Temizlik yakın"] : ["crit", "Temizlik gerekli"]; },
  health: s => { const v = s.engine.health; return v >= 60 ? ["good", "İyi"] : v >= 40 ? ["warn", "Yıpranmış"] : ["crit", "Revizyon"]; },
  brake: s => { const t = s.live.brake_temp || 0; return t < 250 ? ["good", "Normal"] : t < 450 ? ["warn", "Sıcak"] : ["crit", "Aşırı"]; },
  fuel: s => { const f = s.fuel || {}, v = f.pct; if (v === null || v === undefined) return ["muted", "—"]; return v < 5 ? ["crit", "Bitmek üzere"] : v < Math.max(15, f.warn_pct || 15) ? ["warn", "Az"] : ["good", "Yeterli"]; },
  adblue: s => { const a = s.adblue || {}; if (!a.enabled) return ["muted", "SCR yok"]; const v = a.pct; return v <= 0 ? ["crit", "Bitti"] : v < 5 ? ["crit", "Bitmek üzere"] : v < 10 ? ["warn", "Az"] : ["good", "Yeterli"]; },
  tire: s => { const t = s.tires || {}, lv = (s.levels || {})["tires.status"]; if (t.blown) return ["crit", "Patladı"]; if (t.leak) return ["warn", "Yavaş patlak"]; return lv === "c" ? ["crit", "Kritik"] : lv === "w" ? ["warn", "Dikkat"] : ["good", "İyi"]; },
  // şanzıman ve debriyaj (eşikler simülatördekiyle aynı: yağ 115/130 °C, debriyaj 250/320 °C, balata %85/%100)
  gear: s => { const t = s.trans || {};
    if (t.t_oil >= 130) return ["crit", "Yağ aşırı sıcak"]; if (t.t_clutch >= 320) return ["crit", "Debriyaj aşırı sıcak"];
    if (t.clutch_wear >= 100) return ["crit", "Debriyaj bitti"]; if (t.t_oil >= 115) return ["warn", "Yağ sıcak"];
    if (t.t_clutch >= 250) return ["warn", "Debriyaj ısınıyor"]; if (t.clutch_wear >= 85) return ["warn", "Debriyaj değişimi yakın"];
    return t.oil_used >= 100 ? ["warn", "Yağ değişimi "] : ["good", "İyi"]; },   // sondaki boşluk: "değişim zamanı" anlamı (Yağ sekmesindeki "Yağ değişimi" başlığından ayrı çeviri)
  gbox: s => { const t = (s.trans || {}).t_oil; if (t === null || t === undefined) return ["muted", "—"]; return t < 40 ? ["muted", "Soğuk"] : t < 115 ? ["good", "Normal"] : t < 130 ? ["warn", "Sıcak"] : ["crit", "Aşırı sıcak"]; },
  gboil: s => { const u = (s.trans || {}).oil_used || 0; return u < 90 ? ["good", "İyi"] : u < 100 ? ["warn", "Değişim yakın"] : ["crit", "Değiştirin"]; },
  clutchT: s => { const t = (s.trans || {}).t_clutch || 0; return t < 250 ? ["good", "Normal"] : t < 320 ? ["warn", "Isınıyor"] : ["crit", "Aşırı ısındı"]; },
  clutch: s => { const w = (s.trans || {}).clutch_wear || 0; return w < 85 ? ["good", "İyi"] : w < 100 ? ["warn", "Değişim yakın"] : ["crit", "Bitti"]; },
  // direksiyon, ABS, park freni, fren havası (katmandaki lambalarla aynı koşullar)
  steer: s => { const st = s.steering || {}, L = s.live || {};
    if (!st.hydraulic) return ["muted", "Elektrikli direksiyon (EPS)"];
    if (!L.running && (L.speed || 0) > 5) return ["crit", "Destek yok (motor çalışmıyor)"];
    if (st.fluid < 60) return ["crit", "Hidrolik yağı çok az"]; if (st.leak) return ["warn", "Hidrolik kaçağı"];
    return L.running ? ["good", "Normal"] : ["muted", "Motor kapalı"]; },
  abs: s => (s.faults || []).some(f => f.key === "abs_sensor") ? ["warn", "Arızalı (sensör)"] : ["good", "Normal"],
  park: s => { const L = s.live || {}; if (L.park_moving) return ["crit", "Çekili, tır hareket ediyor!"]; if (L.park_warn) return ["warn", "Çekilmedi!"];
    return L.park_brake ? ["good", "Çekili"] : ["muted", "Çekili değil"]; },
  air: s => { const L = s.live || {}; if (L.air_emergency) return ["crit", "Acil fren"]; if (L.air_warning) return ["crit", "Düşük"];
    return (L.air_bar || 0) > 0 ? ["good", "Normal"] : ["muted", "—"]; },
};
// bir dingilin durumu: en kötü ölçüt (patlama, kaldırılmış, patlak, diş, basınç, sıcaklık)
function tireState(g) {
  const lv = g.lv || {};
  if (g.blown) return ["crit", "Patladı"];
  if (g.lifted) return ["muted", "Kaldırılmış"];
  if (g.leak) return ["warn", "Yavaş patlak"];
  if (lv.tread === "c") return ["crit", "Diş yasal sınırın altında"];
  if (lv.pressure === "c") return ["crit", "Basınç çok düşük"];
  if (lv.temp === "c") return ["crit", "Aşırı sıcak"];
  if (lv.tread === "w") return ["warn", "Diş azaldı"];
  if (lv.pressure === "w") return ["warn", "Basınç ayarsız"];
  if (lv.temp === "w") return ["warn", "Sıcak"];
  return ["good", "İyi"];
}
function rule(name) { try { const [lvl, text] = RULES[name](S); return { lvl, text: tt(text).trim() }; } catch (e) { return { lvl: "muted", text: "—" }; } }
function statusHTML(st) { return `<span class="status ${st.lvl}">${ICON[st.lvl] || ""}<span></span></span>`; }

/* ---------------- bağlama ---------------- */
// yalnızca görünen sekmedeki (ve üst çubuktaki) öğeler yenilenir; sekme değişince render() o sekmeyi hemen doldurur
function visibleBound(sel) {
  const key = "vis|" + sel;
  let l = QS_CACHE.get(key);
  if (!l) { l = $$(sel).map(el => ({ el, sec: el.closest("section.tab") })); QS_CACHE.set(key, l); }
  const id = "tab-" + tab;
  return l.filter(x => !x.sec || x.sec.id === id).map(x => x.el);
}
function bindAll() {
  visibleBound("[data-v]").forEach(el => {
    const v = get(S, el.dataset.v);
    let out;
    if (el.dataset.b !== undefined) {
      const [yes, no] = el.dataset.b.split("|");
      out = tt(v ? yes : no);
    } else if (el.dataset.b2 !== undefined) {
      const map = Object.fromEntries(el.dataset.b2.split("|").map(x => x.split(":")));
      out = map[v] !== undefined ? tt(map[v]) : String(v);
    } else if (el.dataset.dur) {
      out = dur(v);
    } else if (typeof v === "number") {
      out = el.dataset.cur ? money(v, +(el.dataset.d || 0)) : nf(v, +(el.dataset.d || 0), !!el.dataset.g);
      if (el.dataset.sign && v > 0) out = "+" + out;
      if (el.dataset.pct) out = pct(out);
      if (el.dataset.u) out += " " + tu(el.dataset.u);
    } else if (v === null || v === undefined || v === "") {
      out = el.dataset.n || "—";
    } else out = String(v);
    if (el.textContent !== out) el.textContent = out;
    // değer rengi: sınırda sarı, kritik kırmızı (eşikler simülatörde, katmanla aynı)
    const lv = S.levels ? S.levels[el.dataset.v] : undefined;
    const cls = lv === "c" ? "lvl-c" : lv === "w" ? "lvl-w" : "";
    if (el._lv !== cls) {
      el.classList.remove("lvl-w", "lvl-c");
      if (cls) el.classList.add(cls);
      el._lv = cls;
    }
  });
  visibleBound("[data-m]").forEach(el => {
    const v = get(S, el.dataset.m);
    const lo = +(el.dataset.min || 0), hi = +(el.dataset.max || 100);
    const p = v === null || v === undefined ? 0 : Math.max(0, Math.min(1, (v - lo) / (hi - lo)));
    const w = (p * 100).toFixed(1) + "%";
    if (el._w !== w) { el._w = w; el.firstElementChild.style.width = w; }
    const st = el.dataset.st ? rule(el.dataset.st).lvl : "neutral";
    setClass(el, "meter " + (st === "good" ? "" : st === "muted" ? "neutral" : st));
  });
  visibleBound("[data-s]").forEach(el => {
    const st = rule(el.dataset.s);
    const key = st.lvl + st.text;
    if (el._k === key) return;
    el._k = key;
    el.innerHTML = statusHTML(st);
    el.querySelector("span span").textContent = st.text;
  });
}

/* ---------------- uyarılar ---------------- */
// ikaz sesini uygulama çalar (markaya göre, her uyarıda bir kez); pencere ayrıca ses çıkarmaz
async function soundTest(level) {
  const r = await post("/api/sound_test", { level });
  toast((r.ok ? "" : "✕ ") + r.message, 2500);
}
$("#snd-crit").addEventListener("click", () => soundTest("crit"));
$("#snd-warn").addEventListener("click", () => soundTest("warn"));

function renderAlerts() {
  const box = $("#alerts");
  const list = S.warnings || [];
  const key = LANG + (showAllAlerts ? "+" : "-") + JSON.stringify(list.map(w => [w.level, w.text]));
  if (box._k === key) return;   // aynı uyarılar: liste yeniden kurulmaz
  box._k = key;
  box.textContent = "";
  const shown = showAllAlerts ? list : list.slice(0, 3);
  shown.forEach(w => {
    const a = document.createElement("div");
    a.className = "alert " + w.level;
    a.innerHTML = `<span style="color:${LVL_COLOR[w.level]}">${ICON[w.level]}</span><span class="lvl"></span><span class="t"></span>`;
    a.querySelector(".lvl").textContent = tt(w.level === "crit" ? "Kritik" : w.level === "warn" ? "Dikkat" : "Bilgi");
    a.querySelector(".t").textContent = w.text;
    box.appendChild(a);
  });
  if (list.length > 3) {
    const m = document.createElement("div");
    m.className = "more";
    m.textContent = showAllAlerts ? tt("Daha az göster") : `+${list.length - 3} ${tt("uyarı daha")}`;
    m.onclick = () => { showAllAlerts = !showAllAlerts; renderAlerts(); };
    box.appendChild(m);
  }
}

/* onay penceresi: tarayıcının confirm() penceresi başlığı ve düğmeleri Windows dilinde (ör. "Tamam / İptal")
   gösterdiği için sayfa içi ve seçili dilde. Enter: devam, Esc ya da dışarı tıklama: vazgeç. */
function confirmBox(text) {
  return new Promise(resolve => {
    const bg = document.createElement("div");
    bg.className = "modal-bg";
    bg.innerHTML = '<div class="modal" role="dialog" aria-modal="true"><p></p><div class="actions">'
      + '<button class="btn ghost" data-r="0"></button><button class="btn" data-r="1"></button></div></div>';
    bg.querySelector("p").textContent = text;
    bg.querySelector('[data-r="0"]').textContent = tt("Vazgeç");
    bg.querySelector('[data-r="1"]').textContent = tt("Devam");
    const key = e => {
      if (e.key === "Escape") { e.preventDefault(); done(false); }
      else if (e.key === "Enter") { e.preventDefault(); done(true); }
    };
    const done = v => { document.removeEventListener("keydown", key, true); bg.remove(); resolve(v); };
    bg.addEventListener("click", e => {
      const b = e.target.closest("[data-r]");
      if (b) done(b.dataset.r === "1"); else if (e.target === bg) done(false);
    });
    document.addEventListener("keydown", key, true);
    document.body.appendChild(bg);
    bg.querySelector('[data-r="1"]').focus();
  });
}

function setText(el, text) { if (el.textContent !== text) el.textContent = text; }

function toast(text, ms = 4000) {
  const t = $("#toast");
  t.textContent = text;
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), ms);
}

/* ---------------- dil ---------------- */
function applyLanguage(lang) {
  if (!lang || lang === LANG || !LOCALES[lang]) return;
  LANG = lang;
  translateDom();
  $("#lang-sel").value = LANG;
  $("#theme-btn").title = tt("Tema");
  optionsKey = null; settingsReady = false; lineupKey = null; specKey = null;
  $$("[data-s]").forEach(el => (el._k = null));
  $("#lab-body")._rep = null; $("#fault-list")._k = null; $("#log-body")._k = null;
  if (S && S.truck) { render(); renderHistoryCharts(); renderDetail(); }
}

/* ---------------- başlık ---------------- */
function renderHeader() {
  const st = S.status;
  const chip = $("#h-chip");
  setClass(chip, "chip " + (st.source === "demo" ? "demo" : st.connected ? (st.paused ? "" : "ok") : "off"));
  const src = (st.source === "demo" ? tt("DEMO") : st.connected ? tt(st.paused ? "Oyun duraklatıldı" : "Oyuna bağlı") : st.text) || "";
  setText($("#h-src"), src);
  setTitle(chip, src);   // uzun metin üst çubukta "…" ile kısalır; tamamı ipucunda
  // etkin oyun modu (Tek / Çok Oyunculu) rozeti ve algılanan çok oyunculu oturum
  const mp = st.mode === "cok";
  const mode = $("#h-mode");
  setClass(mode, "chip mode " + (mp ? "mp" : "sp") + (!mp && st.multiplayer ? " warn" : ""));
  setText($("#h-mode-txt"), tt(mp ? "Çok oyunculu" : "Tek oyunculu") + (st.multiplayer ? ` · ${tt(st.multiplayer_label)}` : ""));
  setTitle(mode, tt(st.enforce_allowed ? "Tam izleme: arızada motor durdurulur" : "Sadece gösterme: motor durdurulmaz (yalnızca uyarı)"));
  setText($("#s-mode-now"), tt(mp ? "Çok Oyunculu" : "Tek Oyunculu") + (st.mode_setting === "auto" ? ` (${tt("otomatik seçildi")})` : "")
    + (st.multiplayer ? ` · ${tt(st.multiplayer_label)} ${tt("algılandı")}` : ""));
  // mod değişince (Otomatik'te TruckersMP algılanınca ya da elle) Ayarlar o modun kendi ayarlarıyla yeniden doldurulur
  if (st.mode && st.mode !== profileMode) {
    if (profileMode !== null) { settingsReady = false; alOff = null; alLang = null; }
    profileMode = st.mode;
  }
  // izleme modu seçeneği yalnızca Çok Oyunculu modda; Tek Oyunculu mod her zaman tam izlemedir
  $$c(".mp-only").forEach(el => { if (el.hidden !== !mp) el.hidden = !mp; });
  $$c(".sp-only").forEach(el => { if (el.hidden !== mp) el.hidden = mp; });
  renderDrive();
  if (!mp) renderFilm();
  if (S.truck) {
    setText($("#h-truck"), `${S.truck.brand || ""} ${S.truck.name || ""}`.trim() || tt("Kamyon"));
    setText($("#h-plate"), (S.truck.plate || "") + (S.truck.temporary ? " · " + tt("geçici tır (hızlı iş)") : "")
      + (S.live && S.live.killed ? " · " + tt("MOTOR DURDU") : ""));
  }
  if (S.location && S.location.lat !== null) {
    const L = S.location;
    const ns = L.lat >= 0 ? (LANG === "tr" ? "K" : "N") : (LANG === "tr" ? "G" : "S");
    const ew = L.lon >= 0 ? (LANG === "tr" ? "D" : "E") : (LANG === "tr" ? "B" : LANG === "de" ? "W" : "W");
    const near = LANG === "tr" ? `${L.city} ${tt("yakını")}` : `${tt("yakını")} ${L.city}`;
    setText($("#h-loc"), `${near} (${nf(Math.abs(L.lat), 1)}°${ns} ${nf(Math.abs(L.lon), 1)}°${ew})`);
  }
  if (st.message && st.message.at !== lastMsgAt) {
    lastMsgAt = st.message.at;
    toast(st.message.text, 6000);
  }
}

/* ---------------- formlar ---------------- */
function populateOptions() {
  const c = curInfo();
  const key = LANG + (S.options ? S.options.oil_grades.length : 0) + c.symbol + c.rate;
  if (optionsKey === key || !S.options) return;
  const fill = (sel, arr) => $$(sel).forEach(s => {
    const v = s.value;
    s.textContent = "";
    arr.forEach(o => { const op = document.createElement("option"); op.value = o.id; op.textContent = o.name + (o.price ? ` — ${money(o.price, 2)}/L` : ""); s.appendChild(op); });
    s.value = v || (arr[0] && arr[0].id);
  });
  fill(".grade-sel", S.options.oil_grades);
  fill(".ctype-sel", S.options.coolant_types);
  fill(".fluid-sel", S.options.fluids);
  const plain = (sel, arr) => { const s = $(sel), v = s.value; s.textContent = "";
    arr.forEach(o => { const op = document.createElement("option"); op.value = o.id; op.textContent = o.name; s.appendChild(op); });
    s.value = v || (arr[0] && arr[0].id); };
  const single = S.battery && S.battery.volts === 12;   // otomobil: tek 12 V akü (tır / otobüs: 2 x 12 V)
  plain("#br-ah", S.options.battery_sizes.map(ah => ({ id: String(ah), name: single ? `12 V ${ah} Ah` : `2 x ${ah} Ah` })));
  plain("#br-kind", S.options.battery_kinds);
  plain("#tr-tier", S.options.tire_tiers);
  if (optionsKey === null) {
    $$(".grade-sel").forEach(s => (s.value = S.oil.grade)); $("#cc-type").value = S.coolant.type;
    const ah = String(Math.round(S.truck.spec.battery_ah));
    if (S.options.battery_sizes.map(String).includes(ah)) $("#br-ah").value = ah;
    $("#br-kind").value = S.battery.kind || "std";
  }
  optionsKey = key;
}

function populateSettings() {
  const st = S.status.settings;
  if (!st || settingsReady) return;
  const ms = $("#s-cmonth");
  ms.textContent = "";
  MONTHS[LANG].forEach((m, i) => { const o = document.createElement("option"); o.value = i + 1; o.textContent = m; ms.appendChild(o); });
  $$("[data-set]").forEach(el => {
    const v = st[el.dataset.set];
    if (el.type === "checkbox") el.checked = !!v; else el.value = v;
  });
  renderRates();
  settingsReady = true;
}

function populateSpec() {
  if (!S.truck) return;
  const sp = S.truck.spec;
  const key = `${S.truck.key}|${sp.engine_id}|${sp.mode}|${sp.power_kw}|${sp.oil_capacity_l}|${LANG}`;
  if (specKey === key) return;
  specKey = key;
  // sınırlar araç sınıfına göre (otomobilde motor hacmi, yağ ve akü değerleri tırdan çok küçük)
  const lim = S.truck.spec_limits || {};
  $$("[data-spec]").forEach(el => { const l = lim[el.dataset.spec]; if (l) { el.min = l[0]; el.max = l[1]; el.step = l[2]; } });
  $("#p-name").value = sp.name;
  $("#p-hp").value = Math.round(sp.power_kw / 0.7355);
  $("#p-nm").value = Math.round(S.engine_db.torque);
  $("#p-rpm").value = sp.rated_rpm;
  $("#p-disp").value = sp.displacement_l;
  $("#p-oil").value = sp.oil_capacity_l;
  $("#p-cool").value = sp.coolant_capacity_l;
  $("#p-batt").value = sp.battery_ah;
  $("#p-dpf").checked = !!sp.has_dpf;
}

function renderEngineSel() {
  const E = S.engine_db;
  if (!E) return;
  const mode = $("#p-mode");
  if (document.activeElement !== mode) mode.value = E.mode;
  const sel = $("#p-engine");
  const lk = E.model_key + "|" + E.lineup.length + "|" + E.engine_id + "|" + LANG;
  if (lineupKey !== lk && document.activeElement !== sel) {
    lineupKey = lk;
    sel.textContent = "";
    if (!E.engine_id) {
      const o = document.createElement("option"); o.value = ""; o.textContent = tt("Özel (elle girilen değerler)"); sel.appendChild(o);
    }
    E.lineup.forEach(e => {
      const o = document.createElement("option");
      o.value = e.id;
      o.textContent = `${e.label} — ${e.hp} ${tu("hp")}, ${nf(e.nm, 0, true)} Nm, ${nf(e.disp, 1)} L`;
      sel.appendChild(o);
    });
    sel.value = E.engine_id || "";
    sel.disabled = !E.lineup.length;
  }
  const d = E.detect;
  let txt;
  if (!E.lineup.length) txt = tt("Model tanınmadığı için motor listesi yok.");
  else if (S.truck && S.truck.vehicle === "car") txt = tt("Otomobilde motor sürüşten algılanmaz: benzinli ya da dizel motoru listeden seçin.");
  else if (d.torque === null) txt = `${tt("Örnek toplanıyor")}: ${d.samples}/${d.need}. ${tt("Tam gazda, sabit viteste, 1000–1450 rpm aralığında sürün (dolu yükle yokuş idealdir).")}`;
  else {
    txt = `${tt("Ölçülen tepe tork")} ≈ ${nf(d.torque, 0, true)} Nm (${d.samples} ${tt("örnek")}) → ${tt("en yakın")}: ${d.suggest_label}`;
    txt += " · " + tt(d.confident ? "güvenilir" : "henüz kesin değil, ölçüm sürüyor");
    if (d.confident && E.mode !== "auto" && d.suggest_id !== E.engine_id) txt += " " + tt("(elle modda uygulanmaz)");
  }
  $("#p-detect").textContent = txt;
}

/* ---------------- güncelleme (Ayarlar → Genel) ---------------- */
const UPD_ERR = { info: "Sürüm bilgisi okunamadı.", sha: "İndirilen dosya doğrulanamadı; güncelleme yapılmadı.",
  program: "İndirilen paket beklenen dosyaları içermiyor.", net: "İnternete bağlanılamadı.", other: "Beklenmeyen hata." };
let updToast = false;
function renderUpdate() {
  const u = S.status.update || {};
  const notes = (u.notes || {})[LANG] || (u.notes || {}).tr || "";
  setText($("#upd-ver"), `${tt("Sürüm")} ${u.current || ""}`);
  setText($("#upd-text"), {
    off: tt("Güncelleme yalnızca kurulu uygulamada çalışır."),
    checking: tt("Yeni sürüm denetleniyor…"),
    latest: tt("Sürümünüz güncel."),
    available: `${tt("Yeni sürüm hazır")}: ${u.latest}${notes ? " — " + notes : ""}`,
    downloading: `${tt("İndiriliyor")}… ${pct(Math.round((u.progress || 0) * 100))}`,
    installing: tt("Kuruluyor; uygulama kapanıp yeniden açılacak."),
    error: `${tt("Güncelleme başarısız")}: ${tt(UPD_ERR[u.error] || UPD_ERR.other)}`
      + (u.detail && (u.error === "net" || u.error === "other") ? ` (${u.detail})` : ""),
  }[u.state] || "");
  const inst = $("#upd-install"), chk = $("#upd-check");
  if (inst.hidden !== (u.state !== "available")) inst.hidden = u.state !== "available";
  const off = ["off", "checking", "downloading", "installing"].includes(u.state);
  if (chk.disabled !== off) chk.disabled = off;
  if (u.state === "available" && !updToast) {
    updToast = true;
    toast(`${tt("Yeni sürüm hazır")}: ${u.latest} · ${tt("Ayarlar → Genel → İndir ve kur")}`, 8000);
  }
}

function renderOverlayStatus() {
  const o = S.status.overlay || {};
  const st = $("#ovl-status"), inp = $("#ovl-input");
  const ac = S.status.appcontrol || {};
  const K = o.key_label || "F8";
  $("#ovl-keys").textContent = `${K}: ${tt("kapalı → kompakt → detaylı")} · Shift+${K}: ${tt("sonraki sayfa")} · Ctrl+${K}: ${tt("köşe değiştir (sol üst → sağ üst → sağ alt → sol alt)")} · Ctrl+Shift+${K}: ${tt("boyut")} · Alt+${K}: ${tt("servis menüsü (yağ, antifriz, akü, DPF, onarım)")} · Ctrl+Alt+${K}: ${tt("fareyle taşı ve boyutlandır (panel ve lambalar)")}`;
  renderOvlKey();
  if (o.present) {
    st.textContent = `${tt("Oyunda çalışıyor")} · ${o.renderer || "DX11"} · ${o.width}×${o.height} · ${nf(o.fps, 0)} FPS`;
    st.style.color = "var(--good-ink)";
  } else if (o.skip) {
    // panel açılışta kurulmadı (Ayarlar, OptiScaler / DLSS 5 ya da önceki açılışta donma); giriş cihazı çalışır
    st.textContent = o.skip === "user" ? tt("Oyun içi panel Ayarlar'dan kapatıldı. Sürüş modları, motor durdurma ve lastik patlaması çalışır.")
      : o.skip === "injector" ? `${tt("Oyun klasöründe şu eklenti bulundu")}: ${o.skip_by}. ${tt("Oyun içi panel çakışmayı önlemek için kapalı; sürüş modları, motor durdurma ve lastik patlaması çalışır. Denemek isterseniz “Oyun içi panel”i “Açık” yapıp oyunu yeniden açın.")}`
      : tt("Oyun bir önceki açılışta düzgün kapanmadı (donma ya da çökme); oyun içi panel bu yüzden kapalı başladı. Sürüş modları, motor durdurma ve lastik patlaması çalışır. Panel sorun değilse “Oyun içi panel”i “Açık” yapıp oyunu yeniden açın.");
    st.style.color = "var(--warn-ink)";
  } else if (ac.overlay_blocked || (ac.sac === "on" && ac.build_blocked && !ac.installed)) {
    // Akıllı Uygulama Denetimi imzasız katman DLL'ini oyunda engeller; geri kalan her şey çalışır
    st.textContent = tt(ac.overlay_blocked
      ? "Akıllı Uygulama Denetimi açık: imzasız katman DLL'i oyunda engelleniyor. Simülatör, bu pencere ve motor durdurma (tuş yöntemi) çalışır. Katman için DLL'in güvenilir bir sertifikayla imzalanması ya da denetimin kapatılması gerekir (README)."
      : "Akıllı Uygulama Denetimi açık: imzasız katman oyuna kurulmadı (engellenirdi). Simülatör, bu pencere ve motor durdurma (tuş yöntemi) çalışır.");
    st.style.color = "var(--warn-ink)";
  } else {
    st.textContent = tt(S.status.packaged
      ? "Oyunda yüklü değil ya da oyun kapalı (Başlat menüsü → ETS2 Bakım → “Eklentileri kur”; oyun DirectX 11 ile çalışmalı)."
      : "Oyunda yüklü değil ya da oyun kapalı (EKLENTI_KUR.bat ile kurun; oyun DirectX 11 ile çalışmalı).");
    st.style.color = "var(--muted)";
  }
  if ((o.present || o.skip) && o.input) {
    inp.textContent = tt("Oyunun resmi giriş cihazı (kontağı kapat)") + " · " + tt(o.input_active ? "aktif" : "oyun odakta değil");
    inp.style.color = "var(--good-ink)";
  } else {
    inp.textContent = tt("Yedek yöntem: oyuna tuş gönderilir (yalnızca oyun penceresi öndeyken).");
    inp.style.color = "var(--muted)";
  }
}

/* ---------------- sekmeler ---------------- */
function histSeries(key) { return H.map(h => h[key]); }
function histX(n) {
  const out = [[0, `−${Math.round(n / 60)} ${tu("dk")}`]];
  if (n > 240) out.push([Math.round(n / 2), `−${Math.round(n / 120)} ${tu("dk")}`]);
  out.push([n - 1, tt("şimdi")]);
  return out;
}
function histLabel(i) {
  const h = H[i]; if (!h) return "";
  const gm = h.gm, d = Math.floor(gm / 1440) % 7, hh = Math.floor((gm % 1440) / 60), mm = gm % 60;
  return `${tt("Oyun saati")} ${DAYS[LANG][d]} ${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")} · ${h.speed} km/h`;
}
function renderHistoryCharts() {
  const x = H.map((_, i) => i);
  const common = { x, xTicks: histX, xLabel: histLabel };
  if (tab === "ozet") {
    Charts.line($("#ch-temp"), { ...common, title: tt("Sıcaklıklar"), unit: "°C", decimals: 1, series: [
      { name: tt("Soğutma suyu"), color: "--s1", values: histSeries("cool") },
      { name: tt("Yağ "), color: "--s2", values: histSeries("oil_t") },
      { name: tt("Dış hava "), color: "--s3", values: histSeries("amb") }] });
    Charts.line($("#ch-press"), { ...common, title: tt("Yağ basıncı"), unit: "bar", decimals: 2, yMin: 0, series: [{ name: tt("Yağ basıncı"), color: "--s1", values: histSeries("oil_p") }] });
    Charts.line($("#ch-volt"), { ...common, title: tt("Akü voltajı"), unit: "V", decimals: 2, series: [{ name: tt("Voltaj"), color: "--s1", values: histSeries("volt") }] });
    Charts.line($("#ch-rpm"), { ...common, title: tt("Motor devri"), unit: tu("rpm"), decimals: 0, yMin: 0, series: [{ name: tt("Devir "), color: "--s1", values: histSeries("rpm") }] });
  } else if (tab === "aku") {
    Charts.line($("#ch-volt2"), { ...common, title: tt("Akü voltajı"), unit: "V", decimals: 2, series: [{ name: tt("Voltaj"), color: "--s1", values: histSeries("volt") }] });
    Charts.line($("#ch-soc"), { ...common, title: tt("Şarj durumu"), unit: "%", decimals: 1, series: [{ name: tt("Şarj"), color: "--s1", values: histSeries("soc") }] });
    Charts.line($("#ch-amp"), { ...common, title: tt("Akü akımı (+ şarj / − deşarj)"), unit: "A", decimals: 1, series: [{ name: tt("Akım"), color: "--s1", values: histSeries("amp") }] });
  }
}

function renderYag() {
  const br = S.oil.breakdown || {};
  const box = $("#oil-breakdown");
  const bk = JSON.stringify(br) + S.oil.limiting + LANG;
  if (box._k !== bk) {
  box._k = bk;
  box.textContent = "";
  Object.entries(br).sort((a, b) => a[1] - b[1]).forEach(([k, v]) => {
    const row = document.createElement("div");
    row.className = "row" + (k === S.oil.limiting ? " lim" : "");
    const a = document.createElement("span"); a.textContent = k;
    const m = document.createElement("div"); m.className = "meter " + (v >= 30 ? "" : v >= 10 ? "warn" : "crit");
    const i = document.createElement("i"); i.style.width = v + "%"; m.appendChild(i);
    const b = document.createElement("span"); b.textContent = pct(nf(v));
    row.append(a, m, b);
    box.appendChild(row);
  });
  }
  const rep = S.reports && S.reports.oil;
  const rk = rep ? rep.game_minutes + "-" + rep.odometer + LANG : null;
  if (!rep && $("#lab-body")._rep !== "empty" + LANG) {
    $("#lab-body")._rep = "empty" + LANG;
    $("#lab-body").textContent = tt("Henüz analiz yok. “Yağ numunesi al” ile laboratuvar raporu alın.");
  }
  if (rep && $("#lab-body")._rep !== rk) {
    $("#lab-body")._rep = rk;
    $("#lab-meta").textContent = `${rep.time} · ${nf(rep.odometer, 0, true)} km · ${nf(rep.oil_km, 0, true)} km · ${rep.grade}`;
    const body = $("#lab-body");
    body.className = "";
    body.textContent = "";
    const t = document.createElement("table"); t.className = "data";
    const head = document.createElement("thead");
    head.innerHTML = "<tr><th></th><th class='num'></th><th></th></tr>";
    ["Parametre", "Sonuç", "Değerlendirme"].forEach((h, i) => (head.rows[0].cells[i].textContent = tt(h)));
    t.appendChild(head);
    const tb = document.createElement("tbody");
    rep.rows.forEach(row => {
      const [name, val, st, stText] = row;
      const tr = document.createElement("tr");
      const lvl = st === "kritik" ? "crit" : st === "dikkat" ? "warn" : "good";
      tr.innerHTML = `<td></td><td class="num"></td><td>${statusHTML({ lvl })}</td>`;
      tr.children[0].textContent = name; tr.children[1].textContent = val;
      const label = stText || tt(st);
      tr.querySelector(".status span").textContent = label.charAt(0).toUpperCase() + label.slice(1);
      tb.appendChild(tr);
    });
    t.appendChild(tb); body.appendChild(t);
    const h = document.createElement("h3"); h.style.marginTop = "14px"; h.textContent = tt("Laboratuvar yorumu"); body.appendChild(h);
    const ul = document.createElement("ul"); ul.className = "note";
    rep.notes.forEach(n => { const li = document.createElement("li"); li.textContent = n; ul.appendChild(li); });
    body.appendChild(ul);
  }
}

function renderSogutma() {
  const r = S.reports && S.reports.coolant;
  setText($("#cool-test"), r ? `${tt("Son ölçüm")} (${r.time || ""}): ${tt("antifriz")} ${pct(nf(r.glycol_pct))}, ${tt("donma")} ${nf(r.freeze_point)} °C, pH ${nf(r.ph, 1)}, ${tt("inhibitör")} ${pct(nf(r.inhibitor_pct))}, ${tt("kireç")} ${pct(nf(r.scale_pct))}.` : "");
}

function renderAku() {
  setText($("#charger-btn"), tt(S.battery.charger ? "Şarj cihazını sök" : "Şarj cihazı bağla"));
  setText($('[data-act="battery_replace"]'), tt(S.battery.volts === 12 ? "Aküyü değiştir" : "Aküleri değiştir"));
  const r = S.reports && S.reports.battery;
  setText($("#batt-test"), r ? `${tt("Son test")} (${r.time || ""}): ${tt("boşta")} ${nf(r.ocv, 2)} V, ${tt("şarj")} ${pct(nf(r.soc_pct))}, ${tt("sağlık")} ${pct(nf(r.soh_pct))}, CCA ${nf(r.cca)} A, ${tt("iç direnç")} ${nf(r.r_int_mohm, 1)} mΩ, ${tt("marş tahmini")} ${nf(r.crank_v, 1)} V, ${nf(r.efc, 1)} ${tt("döngü")}.` : "");
}

const STAT_ROWS = [
  ["Motor çalışma süresi", "engine_h", 1, "sa"], ["Sürüş süresi", "drive_h", 1, "sa"], ["Mesafe", "distance_km", 0, "km"],
  ["Ortalama tüketim", "l_per_100km", 1, "L/100 km"], ["Eko bant (1000–1500 rpm)", "eco_pct", 0, "%"], ["Rölanti oranı", "idle_pct", 0, "%"],
  ["Hız sabitleyici", "cruise_pct", 0, "%"], ["Yakıtsız yuvarlanma", "coast_pct", 0, "%"], ["Retarder kullanımı", "retarder_pct", 0, "%"],
  ["Lugging (düşük devir tam yük)", "lugging_min", 0, "dk"], ["Aşırı devir olayı", "overrev_events", 0, ""], ["Soğuk motora yüklenme", "cold_load_min", 0, "dk"],
  ["Hararet süresi (>103 °C)", "overheat_min", 0, "dk"], ["Sert fren", "harsh_brake", 0, ""], ["Vites değişimi / 100 km", "shifts_per_100", 1, ""],
  ["Ortalama yük / devir", null], ["Marş / soğuk / başarısız", null], ["En yüksek su / yağ sıcaklığı", null],
];
function fmtStat(v, d, u) {
  if (v === null || v === undefined) return "—";
  const n = nf(v, d, true);
  return u === "%" ? pct(n) : u ? `${n} ${tu(u)}` : n;
}
function renderMotor() {
  setText($("#m-hp"), nf(S.truck.spec.power_kw / 0.7355));
  setText($("#m-regen"), S.dpf.burning ? tt("Rejenerasyon sürüyor") : S.dpf.regen ? tt("Rejenerasyon bekliyor (40 km/h üstü sürüş)") : tt("Yok"));
  renderDiag();
}

/* ---------------- arıza tespiti (Motor Analizi): motor bilgileri · parça durumu · seviyeler ---------------- */
function dgBar(p, lvl) {
  const c = lvl === "c" ? "var(--crit)" : lvl === "w" ? "var(--warn)" : "var(--good)";
  return `<span class="dg-bar"><i style="width:${Math.max(2, Math.min(100, p))}%;background:${c}"></i></span>`;
}
function renderDiag() {
  const g = S.diag, box = $("#dg-parts");
  if (!g) return;
  const key = JSON.stringify(g) + LANG;
  if (box._k === key) return;
  box._k = key;
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const ink = l => l === "c" ? "var(--crit)" : l === "w" ? "var(--warn-ink)" : "var(--good-ink)";
  $("#dg-specs").innerHTML = g.specs.map(x => `<div class="dg-kv"><span>${esc(x.name)}</span><span>${
    x.text !== undefined ? esc(x.text) : `${nf(x.value, x.digits || 0)} ${esc(tu(x.unit))}`}</span></div>`).join("");
  box.innerHTML = g.groups.map(grp => `<div class="dg-group">${esc(grp.name)}</div>` + grp.parts.map(p =>
    `<div class="dg-row"><span>${esc(p.name)}</span>${dgBar(p.pct, p.lvl)}<b style="color:${ink(p.lvl)}">${pct(nf(p.pct))}</b>${
      p.cost !== null && p.cost !== undefined
        ? `<button class="btn ghost" data-part="${esc(p.id)}" data-cost="${p.cost}">${esc(tt(p.failed ? "Onar" : "Değiştir"))}</button>`
        : "<span></span>"}</div>`).join("")).join("");
  $("#dg-levels").innerHTML = g.levels.map(x => {
    const l = x.pct < 25 ? "c" : x.pct < 50 ? "w" : "g";
    return `<div class="dg-row" style="grid-template-columns:1fr 1.2fr 52px"><span>${esc(x.name)}</span>${dgBar(x.pct, l)}<b>${
      x.value !== undefined ? `${nf(x.value, 0)} L` : pct(nf(x.pct))}</b></div>`;
  }).join("");
}
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-part]");
  if (!b) return;
  const name = b.closest(".dg-row").firstElementChild.textContent;
  if (!(await confirmBox(tt("{part} değiştirilecek: {cost}. Devam edilsin mi?").replace("{part}", name)
    .replace("{cost}", money(+b.dataset.cost))))) return;
  act("part_replace", { part: b.dataset.part });
});

function renderMotorDetail() {
  if (!D || !D.session || tab !== "motor") return;
  $("#m-score-s").textContent = nf(D.session.score);
  $("#m-score-t").textContent = nf(D.analysis.score);
  const t = $("#m-stats");
  t.textContent = "";
  const head = document.createElement("thead");
  head.innerHTML = "<tr><th></th><th class='num'></th><th class='num'></th></tr>";
  head.rows[0].cells[1].textContent = tt("Bu oturum"); head.rows[0].cells[2].textContent = tt("Toplam");
  t.appendChild(head);
  const tb = document.createElement("tbody");
  STAT_ROWS.forEach(([lab, key, d, u]) => {
    const tr = document.createElement("tr");
    let a, b;
    const A = D.session, B = D.analysis;
    if (lab.startsWith("Marş")) {
      a = `${A.starts} / ${A.cold_starts} / ${A.failed_starts}`; b = `${B.starts} / ${B.cold_starts} / ${B.failed_starts}`;
    } else if (lab.startsWith("En yüksek")) {
      a = `${nf(A.max_coolant)} / ${nf(A.max_oil_temp)} °C`; b = `${nf(B.max_coolant)} / ${nf(B.max_oil_temp)} °C`;
    } else if (lab.startsWith("Ortalama yük")) {
      a = `${fmtStat(A.avg_load, 0, "%")} · ${fmtStat(A.avg_rpm, 0, "rpm")}`; b = `${fmtStat(B.avg_load, 0, "%")} · ${fmtStat(B.avg_rpm, 0, "rpm")}`;
    } else {
      a = fmtStat(A[key], d, u); b = fmtStat(B[key], d, u);
    }
    tr.innerHTML = "<td></td><td class='num'></td><td class='num'></td>";
    tr.children[0].textContent = tt(lab); tr.children[1].textContent = a; tr.children[2].textContent = b;
    // bu oturumun sürüş tarzı: sınırda sarı, kritik kırmızı
    const lvKey = { eco_pct: "eco", idle_pct: "idle", lugging_min: "lug", cold_load_min: "coldload", harsh_brake: "harsh",
                    overrev_events: "overrev", overheat_min: "overheat" }[key];
    const lv = lvKey && D.session_levels ? D.session_levels[lvKey] : null;
    if (lv === "w" || lv === "c") tr.children[1].classList.add(lv === "c" ? "lvl-c" : "lvl-w");
    tb.appendChild(tr);
  });
  t.appendChild(tb);
  const src = ($("input[name=heat-src]:checked") || {}).value || "session";
  const A = D[src];
  Charts.heatmap($("#ch-heat"), { cols: A.rpm_labels, rows: A.load_labels, values: A.rpm_load_min });
  const tr = D.trend || [];
  const x = tr.map(p => p.odo);
  const common = { x, xLabel: i => `${nf(tr[i].odo, 0, true)} km`, xTicks: n => [[0, nf(tr[0].odo, 0, true) + " km"], [n - 1, nf(tr[n - 1].odo, 0, true) + " km"]] };
  Charts.line($("#tr-health"), { ...common, title: tt("Motor sağlığı"), unit: "%", decimals: 1, series: [{ name: tt("Sağlık"), color: "--s1", values: tr.map(p => p.health) }] });
  Charts.line($("#tr-fe"), { ...common, title: tt("Yağda demir (Fe)"), unit: "ppm", decimals: 0, yMin: 0, series: [{ name: "Fe", color: "--s1", values: tr.map(p => p.fe) }] });
  Charts.line($("#tr-life"), { ...common, title: tt("Yağ ömrü"), unit: "%", decimals: 0, yMin: 0, yMax: 100, series: [{ name: tt("Yağ ömrü"), color: "--s1", values: tr.map(p => p.oil_life) }] });
  Charts.line($("#tr-soh"), { ...common, title: tt("Akü sağlığı"), unit: "%", decimals: 1, series: [{ name: tt("Akü sağlığı "), color: "--s1", values: tr.map(p => p.batt_soh) }] });
}

function renderYolculukDetail() {
  if (!D || !D.trip || tab !== "yolculuk") return;
  const T = D.trip;
  $("#trip-route").textContent = T.src ? `${T.src} → ${T.dst}${T.cargo ? " · " + T.cargo : ""}` : "—";
  $("#trip-dist").textContent = fmtStat(T.distance_km, 0, "km");
  $("#trip-l100").textContent = fmtStat(T.l_per_100km, 1, "L/100 km");
  $("#trip-score").textContent = nf(T.score) || "—";
  const rows = [
    ["Süre", dur(T.duration_min)], ["Ortalama hız", fmtStat(T.avg_speed, 0, "km/h")],
    ["Yakıt", fmtStat(T.fuel_l, 0, "L")], ["Yakıt maliyeti", money(T.fuel_cost)],
    ["CO₂ emisyonu", fmtStat(T.co2_kg, 0, "kg")], ["Rölanti (süre / yakıt)", `${fmtStat(T.idle_pct, 0, "%")} · ${fmtStat(T.idle_fuel_l, 1, "L")}`],
    ["Hız sabitleyici", fmtStat(T.cruise_pct, 0, "%")], ["Yakıtsız yuvarlanma", fmtStat(T.coast_pct, 0, "%")],
    ["Sert fren", fmtStat(T.harsh_brake, 0, "")], ["Vites değişimi / 100 km", fmtStat(T.shifts_per_100, 1, "")],
    ["Ortalama yük / devir", `${fmtStat(T.avg_load, 0, "%")} · ${fmtStat(T.avg_rpm, 0, "rpm")}`],
    ["En yüksek fren sıcaklığı", fmtStat(T.max_brake_temp, 0, "°C")],
  ];
  const tb = $("#trip-table");
  tb.textContent = "";
  rows.forEach(([k, v]) => {
    const tr = document.createElement("tr");
    tr.innerHTML = "<td></td><td></td>";
    tr.children[0].textContent = tt(k); tr.children[1].textContent = v;
    tb.appendChild(tr);
  });
  const split = [T.brake_service_pct, T.brake_retarder_pct, T.brake_engine_pct];
  const bar = $("#split-bar");
  bar.textContent = "";
  if (split[0] !== null && split[0] !== undefined) {
    const names = ["Servis freni", "Retarder", "Motor freni"], cols = ["--s2", "--s1", "--s3"];
    $("#trip-split").textContent = names.map((n, i) => `${tt(n)} ${pct(nf(split[i]))}`).join(" · ");
    split.forEach((v, i) => { const s = document.createElement("i"); s.style.width = v + "%"; s.style.background = `var(${cols[i]})`; s.title = tt(names[i]); bar.appendChild(s); });
  } else {
    $("#trip-split").textContent = tt("Veri toplanıyor…");
  }
  Charts.bars($("#ch-speed"), { title: tt("Hıza göre tüketim"), unit: "L/100 km", decimals: 1, labels: T.speed_labels.map(l => l + " km/h"), values: T.speed_l100, color: "--s1" });
  const gears = (T.gears || []).slice().sort((a, b) => a.gear - b.gear);
  Charts.bars($("#ch-gears"), { title: tt("Vites kullanımı"), unit: "%", decimals: 0, labels: gears.map(g => String(g.gear)), values: gears.map(g => g.pct), color: "--s3",
    valueFmt: v => nf(v, 0), tipLabel: l => `${tt("Vites")} ${l}` });
}

function renderServisDetail() {
  if (!D || !D.forecast) return;
  const t = $("#plan-table");
  t.textContent = "";
  const head = document.createElement("thead");
  head.innerHTML = "<tr><th></th><th class='num'></th></tr>";
  head.rows[0].cells[0].textContent = tt("Bakım"); head.rows[0].cells[1].textContent = tt("Kalan");
  t.appendChild(head);
  const tb = document.createElement("tbody");
  D.forecast.items.forEach(it => {
    const parts = [];
    if (it.km !== null) parts.push(`${nf(it.km, 0, true)} km`);
    if (it.days !== null) parts.push(`${nf(it.days, 0, true)} ${tu("gün")}`);
    const tr = document.createElement("tr");
    const lvl = it.lvl === "c" ? "crit" : it.lvl === "w" ? "warn" : "good";
    tr.innerHTML = `<td>${statusHTML({ lvl })}</td><td class="num"></td>`;
    tr.querySelector(".status span").textContent = it.label;
    tr.children[1].textContent = (it.km === 0 || it.days === 0) ? tt("şimdi") : parts.join(" / ") || "—";
    tb.appendChild(tr);
  });
  t.appendChild(tb);
  $("#plan-cost").textContent = D.forecast.cost_per_1000 !== null ? money(D.forecast.cost_per_1000) : "—";
}

function renderServis() {
  const fl = $("#fault-list");
  const faults = S.faults || [];
  const badge = $("#fault-badge");
  badge.hidden = !faults.length;
  badge.textContent = faults.length;
  const key = faults.map(f => f.key).join(",") + LANG;
  if (fl._k !== key) {
    fl._k = key;
    fl.textContent = "";
    fl.className = faults.length ? "" : "empty";
    if (!faults.length) fl.textContent = tt("Arıza yok.");
    faults.forEach(f => {
      const row = document.createElement("div");
      row.className = "alert crit";
      row.style.marginBottom = "6px";
      row.innerHTML = `<span style="color:var(--crit)">${ICON.crit}</span><span class="t" style="flex:1"><b></b><br><span class="note"></span></span>`;
      row.querySelector("b").textContent = f.name;
      row.querySelector(".note").textContent = f.desc;
      const btn = document.createElement("button");
      btn.className = "btn";
      if (f.key === "battery_frozen") { btn.textContent = tt("Aküleri değiştirin"); btn.disabled = true; }
      else {
        btn.textContent = `${tt("Onar")} (${money(f.cost)})`;
        btn.onclick = async () => {
          if (f.cost < 3000 || await confirmBox(`${f.name}: ${tt("onarımı")} ${money(f.cost)}. ${tt("Devam?")}`)) act("repair", { fault: f.key });
        };
      }
      row.appendChild(btn);
      fl.appendChild(row);
    });
  }
  const lb = $("#log-body");
  const lk = (S.log[0] || {}).gm + "-" + S.log.length + "-" + ((S.log[0] || {}).text || "") + LANG;
  if (lb._k !== lk) {
    lb._k = lk;
    lb.textContent = "";
    S.log.forEach(e => {
      const tr = document.createElement("tr");
      const lvl = e.level === "crit" ? "crit" : e.level === "warn" ? "warn" : "info";
      tr.innerHTML = `<td></td><td class="num"></td><td><span style="color:${LVL_COLOR[lvl]};margin-right:6px">${ICON[lvl]}</span><span></span></td><td class="num"></td>`;
      tr.children[0].textContent = e.time;
      tr.children[1].textContent = nf(e.odo, 0, true);
      tr.children[2].lastChild.textContent = e.text;
      if (e.manual) {   // Ayarlar → Çekim modu ile elle tetiklendi / onarıldı
        const tag = document.createElement("span");
        tag.className = "tag-manual";
        tag.textContent = tt("elle");
        tr.children[2].appendChild(tag);
      }
      tr.children[3].textContent = e.cost ? money(e.cost) : "";
      lb.appendChild(tr);
    });
  }
}

function render() {
  if (S.status && S.status.lang) applyLanguage(S.status.lang);
  renderHeader();
  const has = !!S.truck;
  // oyun beklenirken (menüde, TruckersMP sunucu listesinde…) yalnızca Gösterge (bekleme bilgisi) ve Ayarlar açılır
  const appEl = $("#app");
  if (appEl.hidden) appEl.hidden = false;
  appEl.classList.toggle("waiting", !has);
  $$c("#tabs button").forEach(b => {
    const off = !has && b.dataset.tab !== "ozet" && b.dataset.tab !== "ayar";
    if (b.hidden !== off) b.hidden = off;
  });
  renderUpdate();
  if (!has && tab !== "ozet" && tab !== "ayar") { $('#tabs button[data-tab="ozet"]').click(); return; }
  $("#waiting").hidden = has || tab !== "ozet";
  if (!has) {
    $("#wait-text").textContent = S.status.text;
    if (S.status.packaged) {   // dağıtım paketinden kurulu: eklenti ve demo Başlat menüsünde (bat dosyaları kurulum klasöründe)
      setText($("#wait-step1"), tt("Oyun eklentileri kurulumda yüklendi; oyun o sırada bulunamadıysa ya da sonradan kurulduysa: Başlat menüsü → ETS2 Bakım → “Eklentileri kur”."));
      setText($("#wait-demo"), tt("Oyun olmadan denemek için: Başlat menüsü → ETS2 Bakım → “Demo (oyunsuz deneme)”. Ayarlar sekmesi oyun beklenirken de kullanılabilir."));
    }
    populateSettings();
    if (tab === "ayar" && S.status.settings) { renderOverlayStatus(); renderCurrency(); renderRates(); loadAlerts(); }
    return;
  }
  populateOptions(); populateSettings(); populateSpec();
  renderAlerts();
  bindAll();
  renderServis();
  renderReplacePrices();
  const noAb = !(S.adblue && S.adblue.enabled), noHyd = !(S.steering && S.steering.hydraulic);
  $$c(".adblue-only").forEach(el => { if (el.hidden !== noAb) el.hidden = noAb; });  // SCR'siz (AdBlue'suz) motor
  $$c(".hyd-only").forEach(el => { if (el.hidden !== noHyd) el.hidden = noHyd; });  // otomobilde elektrikli direksiyon
  if (tab === "yag") renderYag();
  else if (tab === "sogutma") renderSogutma();
  else if (tab === "aku") renderAku();
  else if (tab === "lastik") renderLastik();
  else if (tab === "motor") renderMotor();
  else if (tab === "ayar") { renderVehicleSel(); renderEngineSel(); renderOverlayStatus(); renderCurrency(); renderRates(); loadAlerts(); }
  renderRateTags();
}
function renderDetail() { renderMotorDetail(); renderYolculukDetail(); renderServisDetail(); }

/* değişim fiyat etiketleri: akü (boyut x tip) ve lastik (dingil x sınıf); kaplama ön dingile takılmaz */
function renderReplacePrices() {
  if (!S.options || !S.options.battery_kinds) return;
  const kind = S.options.battery_kinds.find(k => k.id === $("#br-kind").value);
  const bc = kind ? kind.costs[$("#br-ah").value] : null;
  $("#br-price").textContent = bc !== undefined && bc !== null ? money(bc) : "";
  const tier = (S.options.tire_tiers || []).find(t => t.id === $("#tr-tier").value);
  const axle = $("#tr-axle").value, groups = (S.tires && S.tires.groups) || [];
  if (!tier || !groups.length) { $("#tr-price").textContent = ""; return; }
  const one = g => g.tires * (g.unit_price * (tier.rear_only && g.key === "steer" ? 1 : tier.price) + S.options.tire_mount);
  const cost = groups.filter(g => axle === "all" || g.key === axle).reduce((a, g) => a + one(g), 0);
  const bad = tier.rear_only && axle === "steer";
  $("#tr-price").textContent = bad ? tt("Kaplama ön dingile takılmaz") : money(cost);
}
["#br-ah", "#br-kind", "#tr-axle", "#tr-tier"].forEach(id => $(id).addEventListener("change", renderReplacePrices));

/* sürüş modu: üst çubuk etiketi (tıkla: sonraki mod), Ayarlar'daki mod düğmeleri ve tuş atama */
const DRIVE_ORDER = ["eco", "comfort", "sport"];
function renderDrive() {
  const d = S && S.status && S.status.drive;
  if (!d) return;
  const chip = $("#h-drive");
  if (chip.hidden === d.enabled) chip.hidden = !d.enabled;
  setClass(chip, "chip drive dm-" + d.mode);
  setText($("#h-drive-txt"), d.name);
  setTitle(chip, `${tt("Sürüş modu")}: ${d.name} — ${d.desc} (${tt("tıklayın: sonraki mod")})`);
  $$c(".drive-btn").forEach(b => {
    b.classList.toggle("on", d.enabled && b.dataset.drive === d.mode);
    if (b.disabled !== !d.enabled) b.disabled = !d.enabled;
    const m = d.modes.find(x => x.id === b.dataset.drive);
    if (m) setText(b.querySelector(".dm-desc"), m.desc);
  });
  const k = $("#dm-key");
  setText(k, d.capturing ? tt("tuşa basın…") : d.key_label);
  k.classList.toggle("capturing", d.capturing);
  setText($("#dm-bind"), tt(d.capturing ? "İptal" : "Tuş ata"));
  if ($("#dm-clear").disabled !== !d.key) $("#dm-clear").disabled = !d.key;
}
$$(".drive-btn").forEach(b => b.addEventListener("click", () => saveSetting("drive_mode", b.dataset.drive)));
$("#h-drive").addEventListener("click", () => {
  const d = S && S.status && S.status.drive;
  if (d) saveSetting("drive_mode", DRIVE_ORDER[(DRIVE_ORDER.indexOf(d.mode) + 1) % DRIVE_ORDER.length]);
});
$("#dm-bind").addEventListener("click", async () => {
  const d = S && S.status && S.status.drive;
  const r = await post("/api/drive_capture", { start: !(d && d.capturing) });
  toast((r.ok ? "" : "✕ ") + r.message, 4000);
  pollState();
});
$("#dm-clear").addEventListener("click", () => saveSetting("drive_mode_key", ""));

/* katmanın tuşu (F8 yerine): "Tuş ata"dan sonra bu pencerede basılan klavye tuşu; Esc iptal eder, Shift/Ctrl/Alt
   tek başına sayılmaz (kombinasyonlar onlarla yapılır). Tarayıcının keyCode'u Windows sanal tuş koduyla aynıdır. */
let ovlCap = 0;
function renderOvlKey() {
  const o = (S && S.status && S.status.overlay) || {};
  const k = $("#ovl-key");
  k.textContent = ovlCap ? tt("tuşa basın…") : (o.key_label || "F8");
  k.classList.toggle("capturing", !!ovlCap);
  $("#ovl-bind").textContent = tt(ovlCap ? "İptal" : "Tuş ata");
  $("#ovl-reset").disabled = (o.key || 119) === 119;
}
function stopOvlCapture() {
  clearTimeout(ovlCap);
  ovlCap = 0;
  window.removeEventListener("keydown", ovlKeyDown, true);
  renderOvlKey();
}
async function ovlKeyDown(e) {
  if (["Shift", "Control", "Alt", "AltGraph", "Meta"].includes(e.key)) return;
  e.preventDefault();
  e.stopPropagation();
  stopOvlCapture();
  if (e.keyCode === 27) return;
  const st = (S && S.status && S.status.settings) || {};
  if ([st.drive_mode_key, st.film_key].includes(`key:${e.keyCode}`)) {
    toast("✕ " + tt("Bu tuş sürüş modu ya da çekim modu tuşu olarak kullanılıyor."), 4000);
    return;
  }
  saveSetting("overlay_key", e.keyCode);
}
$("#ovl-bind").addEventListener("click", () => {
  if (ovlCap) { stopOvlCapture(); return; }
  window.addEventListener("keydown", ovlKeyDown, true);
  ovlCap = setTimeout(stopOvlCapture, 10000);
  renderOvlKey();
});
$("#ovl-reset").addEventListener("click", () => saveSetting("overlay_key", 119));
$("#upd-check").addEventListener("click", async () => {
  const r = await post("/api/update", { op: "check" });
  toast((r.ok ? "✓ " : "✕ ") + r.message, 2500); pollState();
});
$("#upd-install").addEventListener("click", async () => {
  if (!(await confirmBox(tt("Yeni sürüm indirilip kurulacak; uygulama kapanıp yeniden açılacak. Bakım kayıtları ve ayarlar korunur. Devam edilsin mi?")))) return;
  const r = await post("/api/update", { op: "install" });
  toast((r.ok ? "✓ " : "✕ ") + r.message, 5000); pollState();
});

/* çekim modu: seçili arızayı düğmeyle ya da kısayol tuşuyla tetikleme, ücretsiz "hepsini onar" (yalnızca tek oyunculu).
   Arıza listesi sunucudan gelir (/api/film: seçili dilde ve bu araca göre), seçim ve tuş ayarlardadır. */
let filmCat = null, filmKey = null;
async function loadFilm() {
  const t = S && S.truck;
  const key = [LANG, t ? t.key : "", t ? t.vehicle : "", t && t.spec ? t.spec.fuel : ""].join("|");
  if (filmKey === key) return;
  filmKey = key;
  try {
    const cat = await (await fetch("/api/film", { cache: "no-store" })).json();
    if (filmKey !== key) return;   // bu arada dil ya da araç değişti: yenisi istenecek
    filmCat = cat;
    buildFilm();
  } catch (e) { filmKey = null; }
}
function buildFilm() {
  const sel = $("#film-item");
  sel.textContent = "";
  filmCat.groups.forEach(g => {
    const og = document.createElement("optgroup");
    og.label = g.name;
    filmCat.items.filter(it => it.group === g.key).forEach(it => {
      const o = document.createElement("option");
      o.value = it.id;
      o.textContent = it.label + (it.available ? "" : " ✕");
      og.appendChild(o);
    });
    sel.appendChild(og);
  });
  const f = S && S.status && S.status.film;
  if (f) sel.value = f.item;
  renderFilmDesc();
}
function renderFilmDesc() {
  const it = filmCat && filmCat.items.find(x => x.id === $("#film-item").value);
  const parts = it ? [it.desc] : [];
  if (it && it.now.length) parts.push(`${tt("Hemen yanan lamba")}: ${it.now.join(", ")}`);
  if (it && it.later.length) parts.push(`${tt("Belirti çıkınca")}: ${it.later.join(", ")}`);
  if (it && !it.available) parts.push(`${tt("Bu araçta yok")}: ${it.why}`);
  setText($("#film-desc"), parts.join(" · "));
}
function renderFilm() {
  const f = S && S.status && S.status.film;
  if (!f) return;
  loadFilm();
  const sel = $("#film-item");
  if (filmCat && document.activeElement !== sel && sel.value !== f.item) { sel.value = f.item; renderFilmDesc(); }
  const k = $("#film-key");
  setText(k, f.capturing ? tt("tuşa basın…") : f.key_label);
  k.classList.toggle("capturing", f.capturing);
  setText($("#film-bind"), tt(f.capturing ? "İptal" : "Tuş ata"));
  $("#film-clear").disabled = !f.key;
  const ready = f.available && f.enabled && !!S.truck;
  $("#film-trigger").disabled = $("#film-repair").disabled = !ready;
  let st;
  if (!f.available) st = tt("Çok oyunculu oturumda çekim modu kullanılamaz.");
  else if (!f.enabled) st = tt("Çekim modu kapalı: kutuyu işaretleyin.");
  else if (!S.truck) st = tt("Oyuna bağlanınca kullanılabilir.");
  else st = `${tt("Hazır")} · ${f.key ? `${tt("oyunda kısayol")}: ${f.key_label}` : tt("kısayol tuşu atanmadı")}`;
  setText($("#film-state"), st);
}
$("#film-item").addEventListener("change", e => {
  const f = S && S.status && S.status.film;
  if (f) f.item = e.target.value;   // kayıt yanıtını beklerken yoklama seçimi geri çevirmesin
  renderFilmDesc();
  saveSetting("film_fault", e.target.value);
});
$("#film-bind").addEventListener("click", async () => {
  const f = S && S.status && S.status.film;
  const r = await post("/api/film_capture", { start: !(f && f.capturing) });
  toast((r.ok ? "" : "✕ ") + r.message, 4000);
  pollState();
});
$("#film-clear").addEventListener("click", () => saveSetting("film_key", ""));
async function filmAction(op) {
  const r = await post("/api/film", { op });
  toast((r.ok ? "✓ " : "✕ ") + r.message);
  pollState(); pollDetail();
}
$("#film-trigger").addEventListener("click", () => filmAction("trigger"));
$("#film-repair").addEventListener("click", () => filmAction("repair_all"));

/* araç tipi (Ayarlar → Bu kamyonun motoru): otomatik (modelden) ya da elle tır / otobüs / otomobil */
const VEH_NAMES = { truck: "Tır", bus: "Otobüs", car: "Otomobil" };
let vehPending = false;   // onay penceresi açıkken / istek sürerken seçim yoklamayla geri çevrilmesin
function renderVehicleSel() {
  const t = S && S.truck;
  if (!t) return;
  const sel = $("#p-veh");
  if (document.activeElement !== sel && !vehPending) sel.value = t.vehicle_choice || "auto";
  setText($("#p-veh-det"), `${tt("Algılanan")}: ${tt(VEH_NAMES[t.vehicle_detected] || "Tır")} · ${tt("şu an")}: ${t.vehicle_name}.`);
}
$("#p-veh").addEventListener("change", async e => {
  const t = S && S.truck, v = e.target.value;
  if (!t) return;
  const next = v === "auto" ? t.vehicle_detected : v;
  vehPending = true;
  try {
    if (next !== t.vehicle && !(await confirmBox(tt("Araç tipi değişince bu aracın motoru, aküsü (12 / 24 V), yağı, antifrizi, lastikleri ve şanzımanı yeni tipin varsayılanlarına göre yeniden kurulur. Devam edilsin mi?")))) {
      e.target.value = t.vehicle_choice || "auto";
      return;
    }
    const r = await post("/api/spec", { vehicle: v });
    toast((r.ok ? "✓ " : "✕ ") + r.message);
    if (!r.ok) e.target.value = t.vehicle_choice || "auto";
    lineupKey = null; specKey = null; optionsKey = null;
  } finally {
    vehPending = false;
    e.target.blur();
    pollState();
  }
});

/* azalma hızları: kaydırıcılar (genel × sistem), hazır ayarlar ve sekme başlıklarındaki hız etiketleri */
function rateWords(eff) {
  const kat = x => nf(x, Math.abs(x - Math.round(x)) < 0.05 ? 0 : 1);
  if (eff <= 0) return { cls: "stop", text: tt("hiç azalmaz") };
  if (Math.abs(eff - 1) < 0.005) return { cls: "", text: tt("gerçekçi") };
  if (eff < 1) return { cls: "slow", text: tt("{n} kat uzun dayanır").replace("{n}", kat(1 / eff)) };
  return { cls: "fast", text: tt("{n} kat hızlı").replace("{n}", kat(eff)) };
}
function renderRates() {
  const g = +$("#r-global").value;
  $$("[data-rate]").forEach(out => {
    const k = out.dataset.rate, v = +$("#r-" + k).value;
    const eff = k === "global" ? g : g * v;
    const w = rateWords(eff);
    let txt = `${nf(v, 2)}×`;
    if (k !== "global" && Math.abs(eff - v) >= 0.005) txt += ` → ${nf(eff, 2)}×`;
    out.textContent = `${txt} · ${w.text}`;
    out.className = "no-i18n " + w.cls;
  });
}
function renderRateTags() {
  const R = S.rates || {};
  $$("[data-rate-tag]").forEach(el => {
    const k = el.dataset.rateTag, v = R[k];
    const show = v !== undefined && v !== null && Math.abs(v - 1) >= 0.005;
    if (el.hidden === show) el.hidden = !show;
    if (show) {
      const txt = `${tt(k === "drain" ? "boşalma" : "azalma hızı")} ${nf(v, 2)}×`;
      if (el.textContent !== txt) el.textContent = txt;
    }
  });
}
$$("#rates-card input[type=range]").forEach(el => el.addEventListener("input", renderRates));
$$("[data-rate-preset]").forEach(b => b.addEventListener("click", async () => {
  const g = +b.dataset.ratePreset, body = { rate_global: g };
  if (g === 1) $$("#rates-card input[type=range]").forEach(el => (body[el.dataset.set] = 1));
  Object.entries(body).forEach(([k, v]) => { const el = $(`#rates-card [data-set="${k}"]`); if (el) el.value = v; });
  renderRates();
  const r = await post("/api/settings", body);
  toast((r.ok ? "✓ " : "✕ ") + r.message, 2000);
  pollState();
}));

/* uyarılar ve ikaz lambaları: liste sunucudan seçili dilde gelir (/api/alerts), kapalılar ayarlardadır. Seçimler burada
   tutulur ve her tıkta kaydedilir; ayarlardan yalnızca ilk kurulumda okunur (yoklama kutuları geri çevirmesin). */
let alCat = null, alLang = null, alOff = null;
async function loadAlerts() {
  if (alLang === LANG || !S || !S.status || !S.status.settings) return;
  alLang = LANG;
  try {
    const cat = await (await fetch("/api/alerts", { cache: "no-store" })).json();
    if (alLang !== LANG) return;   // bu arada dil değişti: yenisi istenecek
    alCat = cat;
    if (!alOff) {
      const st = S.status.settings;
      alOff = { warnings_off: new Set(st.warnings_off || []), lamps_off: new Set(st.lamps_off || []) };
    }
    buildAlerts();
  } catch (e) { alLang = null; }
}
function buildAlerts() {
  const lvName = { crit: "Kritik", warn: "Dikkat", info: "Bilgi" };
  const groups = $("#al-groups"), lamps = $("#al-lamps");
  const open = new Set($$("#al-groups details[open]").map(d => d.dataset.group));
  groups.textContent = "";
  alCat.groups.forEach(g => {
    const d = document.createElement("details");
    d.className = "al-group"; d.dataset.group = g.key; d.open = open.has(g.key);
    const sm = document.createElement("summary");
    sm.innerHTML = '<label class="chk"><input type="checkbox"><b></b></label><span class="al-n"></span>';
    sm.querySelector("input").dataset.alGroup = g.key;
    sm.querySelector("b").textContent = g.name;
    const box = document.createElement("div");
    box.className = "al-items";
    g.items.forEach(it => {
      const l = document.createElement("label");
      l.className = "chk al-item";
      l.innerHTML = '<input type="checkbox"><i class="al-lv"></i><span></span>';
      l.querySelector("input").dataset.al = it.key;
      const lv = l.querySelector("i");
      lv.classList.add(it.level); lv.title = tt(lvName[it.level]);
      l.querySelector("span").textContent = it.label;
      box.appendChild(l);
    });
    d.append(sm, box);
    groups.appendChild(d);
  });
  lamps.textContent = "";
  const all = document.createElement("label");
  all.className = "chk al-all";
  all.innerHTML = '<input type="checkbox" id="al-lamps-all"><b></b>';
  all.querySelector("b").textContent = tt("Tüm lambalar");
  const list = document.createElement("div");
  list.className = "al-lamp-list";
  alCat.lamps.forEach(x => {
    const l = document.createElement("label");
    l.className = "chk al-item";
    l.innerHTML = '<input type="checkbox"><b class="al-lamp"></b><span class="note small"></span>';
    l.querySelector("input").dataset.lamp = x.key;
    l.querySelector("b").textContent = x.label;
    l.querySelector("span").textContent = x.desc;
    list.appendChild(l);
  });
  lamps.append(all, list);
  syncAlerts();
}
function syncAlerts() {
  if (!alCat || !alOff) return;
  const W = alOff.warnings_off, L = alOff.lamps_off;
  let on = 0, n = 0;
  alCat.groups.forEach(g => {
    const k = g.items.filter(it => !W.has(it.key)).length;
    on += k; n += g.items.length;
    const gi = $(`#al-groups input[data-al-group="${g.key}"]`);
    gi.checked = k === g.items.length;
    gi.indeterminate = k > 0 && k < g.items.length;
    gi.closest("summary").querySelector(".al-n").textContent = `${k}/${g.items.length}`;
  });
  $$("#al-groups input[data-al]").forEach(i => (i.checked = !W.has(i.dataset.al)));
  $$("#al-lamps input[data-lamp]").forEach(i => (i.checked = !L.has(i.dataset.lamp)));
  const ln = alCat.lamps.length, lon = alCat.lamps.filter(x => !L.has(x.key)).length;
  const la = $("#al-lamps-all");
  la.checked = lon === ln;
  la.indeterminate = lon > 0 && lon < ln;
  $("#al-sum").textContent = `${on}/${n} ${tt("uyarı açık")} · ${lon}/${ln} ${tt("lamba açık")}`;
}
async function saveAlerts(...names) {
  syncAlerts();
  const body = {};
  names.forEach(k => (body[k] = [...alOff[k]]));
  const r = await post("/api/settings", body);
  toast((r.ok ? "✓ " : "✕ ") + r.message, 1500);
}
$("#alerts-card").addEventListener("change", e => {
  const t = e.target;
  if (!alOff || !alCat) return;
  const W = alOff.warnings_off, L = alOff.lamps_off;
  const set = (bag, key, on) => (on ? bag.delete(key) : bag.add(key));
  if (t.dataset.al) { set(W, t.dataset.al, t.checked); saveAlerts("warnings_off"); }
  else if (t.dataset.alGroup) {
    alCat.groups.find(g => g.key === t.dataset.alGroup).items.forEach(it => set(W, it.key, t.checked));
    saveAlerts("warnings_off");
  } else if (t.dataset.lamp) { set(L, t.dataset.lamp, t.checked); saveAlerts("lamps_off"); }
  else if (t.id === "al-lamps-all") { alCat.lamps.forEach(x => set(L, x.key, t.checked)); saveAlerts("lamps_off"); }
});
$("#al-on").addEventListener("click", () => {
  if (!alOff) return;
  alOff.warnings_off.clear(); alOff.lamps_off.clear();
  saveAlerts("warnings_off", "lamps_off");
});
$("#al-off").addEventListener("click", async () => {
  if (!alOff || !alCat) return;
  if (!(await confirmBox(tt("Tüm uyarılar ve ikaz lambaları kapatılacak (kritik olanlar dahil). Devam edilsin mi?")))) return;
  alCat.groups.forEach(g => g.items.forEach(it => alOff.warnings_off.add(it.key)));
  alCat.lamps.forEach(x => alOff.lamps_off.add(x.key));
  saveAlerts("warnings_off", "lamps_off");
});

/* para birimi: otomatikte oyundan okunan, elle seçimde girilen simge ve kur */
function renderCurrency() {
  const c = curInfo(), auto = c.source !== "manual";
  $$(".cur-manual").forEach(el => (el.hidden = auto));
  const game = c.game === "ats" ? "American Truck Simulator" : "Euro Truck Simulator 2";
  $("#cur-info").textContent = auto
    ? `${tt("Oyundan okunan")}: ${c.code} (${c.symbol}) · 1 € = ${nf(c.rate, 4)} · ${game}. ${tt("Oyunda para birimini değiştirirseniz en geç bir sonraki oyun açılışında burası da güncellenir.")}`
    : `1 € = ${nf(c.rate, 4)} ${c.symbol}`;
}

/* lastik tablosu (dingil başına) ve lastik değişimi seçimi */
function renderLastik() {
  const T = S.tires || {}, groups = T.groups || [];
  const body = $("#tire-body");
  const key = JSON.stringify(groups) + LANG;
  if (body._k !== key) {
    body._k = key;
    body.textContent = "";
    const lvCls = l => (l === "c" ? "lvl-c" : l === "w" ? "lvl-w" : "");
    groups.forEach(g => {
      const tr = document.createElement("tr");
      const cells = [
        [`${g.name} · ${g.tires} ${tt("adet")}`, ""],
        [`${nf(g.tread, 1)} mm`, "num " + lvCls(g.lv.tread)],
        [g.blown ? "0 bar" : `${nf(g.cold_bar, 1)} / ${nf(g.hot_bar, 1)} bar`, "num " + lvCls(g.lv.pressure)],
        [`${nf(g.temp, 0)} °C`, "num " + lvCls(g.lv.temp)],
        [`${nf(g.km, 0, true)} km`, "num"],
      ];
      cells.forEach(([text, cls]) => { const td = document.createElement("td"); td.textContent = text; td.className = cls; tr.appendChild(td); });
      const [lvl, text] = tireState(g);
      const td = document.createElement("td");
      td.innerHTML = statusHTML({ lvl, text });
      td.querySelector("span span").textContent = tt(text);
      tr.appendChild(td);
      body.appendChild(tr);
    });
  }
  const sel = $("#tr-axle");
  const opts = [["all", tt("Tüm lastikler")]]
    .concat(groups.map(g => [g.key, `${g.name} (${g.tires} ${tt("adet")}) · ${tt("şu an")}: ${g.tier_name}`]));
  const okey = JSON.stringify(opts);
  if (sel._k !== okey) {
    const keep = sel.value;
    sel.textContent = "";
    opts.forEach(([v, t]) => { const o = document.createElement("option"); o.value = v; o.textContent = t; sel.appendChild(o); });
    if (opts.some(o => o[0] === keep)) sel.value = keep;
    sel._k = okey;
    renderReplacePrices();
  }
}

/* ---------------- işlemler ---------------- */
async function post(url, body) {
  try {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    return await r.json();
  } catch (e) { return { ok: false, message: tt("Sunucu kapalı") }; }
}
async function act(name, params = {}) {
  const r = await post("/api/action", { name, params });
  toast((r.ok ? "✓ " : "✕ ") + r.message);
  pollState(); pollDetail();
}
function paramsFor(name) {
  switch (name) {
    case "oil_change": return { grade: $("#oc-grade").value, filter: $("#oc-filter").checked };
    case "oil_topup": return { grade: $("#ot-grade").value, liters: +$("#ot-l").value };
    case "coolant_change": return { type: $("#cc-type").value, concentration: +$("#cc-conc").value };
    case "coolant_topup": return { fluid: $("#ct-fluid").value, liters: +$("#ct-l").value };
    case "battery_replace": return { ah: +$("#br-ah").value, kind: $("#br-kind").value };
    case "tire_replace": return { axle: $("#tr-axle").value, tier: $("#tr-tier").value };
    default: return {};
  }
}
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-act]");
  if (!b) return;
  // onay metinlerindeki tutar oyunda seçili para birimiyle (araç sınıfının fiyatı: tır / otobüs / otomobil)
  const cost = (S && S.options && S.options.overhaul_cost) || 19500;
  const tr = (S && S.trans) || {};
  const ask = { overhaul: () => tt("Motor revizyonu yaklaşık {cost} tutar. Devam edilsin mi?").replace("{cost}", money(cost)),
    gearbox_oil: () => tt("Şanzıman yağı ve filtresi değişecek ({l} L): {cost}. Devam edilsin mi?").replace("{l}", nf(tr.oil_l || 15))
      .replace("{cost}", money(tr.oil_cost)),
    clutch: () => tt("Debriyaj yenilenecek (şanzıman sökülür): {cost}. Devam edilsin mi?").replace("{cost}", money(tr.clutch_cost)),
    reset: () => tt("Bu tırın tüm bakım değerleri ve kaydı silinip baştan başlanacak. Devam edilsin mi?") }[b.dataset.confirm];
  if (ask && !(await confirmBox(ask()))) return;
  act(b.dataset.act, paramsFor(b.dataset.act));
});
$("#charger-btn").onclick = () => act("battery_charger", { on: !(S && S.battery.charger) });
async function saveSetting(key, v) {
  const r = await post("/api/settings", { [key]: v });
  toast((r.ok ? "✓ " : "✕ ") + r.message, 2000);
  pollState();
}
$$("[data-set]").forEach(el => el.addEventListener("change", () => {
  const v = el.type === "checkbox" ? el.checked : el.type === "number" ? +el.value : el.value;
  saveSetting(el.dataset.set, v);
}));
$("#lang-sel").addEventListener("change", e => saveSetting("language", e.target.value));
$("#p-mode").addEventListener("change", async e => {
  const r = await post("/api/spec", { mode: e.target.value });
  toast((r.ok ? "✓ " : "✕ ") + r.message); lineupKey = null;
});
$("#p-engine").addEventListener("change", async e => {
  if (!e.target.value) return;
  const r = await post("/api/spec", { engine_id: e.target.value });
  toast((r.ok ? "✓ " : "✕ ") + r.message); lineupKey = null; e.target.blur();
});
$("#p-redetect").onclick = async () => {
  const r = await post("/api/spec", { redetect: true });
  toast((r.ok ? "✓ " : "✕ ") + r.message); lineupKey = null;
};
$("#spec-save").onclick = async () => {
  const body = {};
  $$("[data-spec]").forEach(el => { body[el.dataset.spec] = el.type === "checkbox" ? el.checked : el.type === "number" ? +el.value : el.value; });
  const r = await post("/api/spec", body);
  toast((r.ok ? "✓ " : "✕ ") + r.message);
  specKey = null;
};
$$("input[name=heat-src]").forEach(r => r.addEventListener("change", () => S && renderMotorDetail()));
$$("#tabs button").forEach(b => b.addEventListener("click", () => {
  tab = b.dataset.tab;
  $$("#tabs button").forEach(x => x.classList.toggle("on", x === b));
  $$("section.tab").forEach(s => s.classList.toggle("on", s.id === "tab-" + tab));
  store("tab", tab);
  if (S && S.truck) { render(); renderHistoryCharts(); renderDetail(); }
  else if (S && S.status) render();
}));

/* ---------------- tema ---------------- */
function applyTheme(t) {
  if (t === "dark" || t === "light") document.documentElement.setAttribute("data-theme", t);
  else document.documentElement.removeAttribute("data-theme");
}
$("#theme-btn").onclick = () => {
  const c = store("theme") || "auto";
  const next = c === "auto" ? "dark" : c === "dark" ? "light" : "auto";
  store("theme", next); applyTheme(next);
  if (S && S.truck) { renderHistoryCharts(); renderDetail(); }
};
applyTheme(store("theme") || "auto");
// sunucu sayfayı seçili dille verir (<html lang>): ilk durum yanıtı gelmeden de doğru dilde başlar
applyLanguage(document.documentElement.lang);
const savedTab = store("tab");
if (savedTab && $(`#tabs button[data-tab="${savedTab}"]`)) $(`#tabs button[data-tab="${savedTab}"]`).click();

/* ---------------- canlı veri ---------------- */
// Ayarlar → Değer güncelleme sıklığı (ui_interval, sn; 0 = gerçek zamanlı): durum sunucudan canlı akışla (/api/stream)
// seçilen aralıkta gelir, yeni uyarı ya da bir işlem sonrası hemen. Akış çalışmazsa (ör. bir güvenlik yazılımı yanıtı
// tamponluyorsa) aynı aralıkta yoklanır. Pencere simge durumuna küçültülünce akış ve yoklamalar durur, açılınca sürer.
let stateBusy = false;  // önceki istek bitmeden yenisi başlamasın (yavaş anlarda istekler üst üste binmez)
let es = null, esBroken = !window.EventSource, esLast = 0, pollTimer = null, renderPending = false;
let lastHist = 0, lastDetail = 0;
function uiInterval() {
  const v = S && S.status && S.status.settings ? Number(S.status.settings.ui_interval) : 0.25;
  return Number.isFinite(v) && v >= 0 ? v : 0.25;
}
function serverDown() {
  setText($("#h-src"), tt("Sunucu kapalı"));
  setClass($("#h-chip"), "chip off");
}
// art arda gelen durumlar bir kez çizilir (ekran yenilemesine bağlı); pencere kare üretmiyorsa (ör. başka bir
// pencerenin altında) en geç 250 ms'de
function scheduleRender() {
  if (renderPending) return;
  renderPending = true;
  const run = () => { if (!renderPending) return; renderPending = false; if (S) render(); };
  requestAnimationFrame(run);
  setTimeout(run, 250);
}
async function pollState() {
  if (stateBusy) return;
  stateBusy = true;
  try {
    const r = await fetch("/api/state", { cache: "no-store" });
    S = await r.json();
    render();
  } catch (e) {
    serverDown();
  } finally {
    stateBusy = false;
  }
}
async function pollHistory() {
  if (!S || !S.truck || (tab !== "ozet" && tab !== "aku")) return;
  try { H = await (await fetch("/api/history", { cache: "no-store" })).json(); renderHistoryCharts(); } catch (e) { /* tekrar denenecek */ }
}
async function pollDetail() {
  if (!S || !S.truck) return;
  try { D = await (await fetch("/api/detail", { cache: "no-store" })).json(); renderDetail(); } catch (e) { /* tekrar denenecek */ }
}
function startStream() {
  if (es || esBroken || document.hidden) return;
  esLast = Date.now();
  es = new EventSource("/api/stream");
  es.onmessage = e => {
    esLast = Date.now();
    try { S = JSON.parse(e.data); } catch (err) { return; }
    scheduleRender();
  };
  es.onerror = () => { if (es && es.readyState !== EventSource.OPEN) serverDown(); };   // kendiliğinden yeniden bağlanır
}
function stopStream() {
  if (es) { es.close(); es = null; }
}
function schedulePoll() {   // akış yoksa: seçilen aralıkta yoklama (gerçek zamanlıda 10/sn)
  clearTimeout(pollTimer);
  if (!esBroken || document.hidden) return;
  pollTimer = setTimeout(async () => { await pollState(); schedulePoll(); }, Math.max(100, uiInterval() * 1000));
}
function startLive() {
  if (document.hidden) return;
  if (esBroken) schedulePoll(); else startStream();
}
document.addEventListener("visibilitychange", () => {
  if (document.hidden) { stopStream(); clearTimeout(pollTimer); return; }
  pollState(); pollDetail(); startLive();
});
setInterval(() => {
  if (document.hidden) return;
  const now = Date.now(), iv = uiInterval() * 1000;
  // akış açık görünüp hiç veri gelmiyorsa (sunucu en geç aralıkta ya da 15 sn'de bir yazar) yoklamaya geçilir
  if (es && es.readyState === EventSource.OPEN && now - esLast > Math.max(20000, iv * 3)) {
    stopStream(); esBroken = true; schedulePoll();
  }
  // grafikler 1/sn (her saniye bir örnek), analiz 2 sn'de bir; seçilen aralık daha uzunsa o aralıkta
  if (now - lastHist >= Math.max(1000, iv)) { lastHist = now; pollHistory(); }
  if (now - lastDetail >= Math.max(2000, iv)) { lastDetail = now; pollDetail(); }
}, 250);
pollState(); pollDetail(); startLive();
window.addEventListener("resize", () => { if (S && S.truck) { renderHistoryCharts(); renderDetail(); } });
