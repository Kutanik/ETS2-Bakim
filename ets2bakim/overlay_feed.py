"""Oyun içi katmana (ets2bakim_overlay.dll) paylaşılan bellek köprüsü.

Durum bloğu  "Local\\ETS2BakimState"   (Python yazar, DLL okur)
  0  char[8]  "EBKSTAT1"
  8  u32      seq          (tek sayı = yazılıyor; seqlock)
  12 u32      length       (yük bayt sayısı)
  16 u32      cmd_seq      (her yeni komutta artar)
  20 u32      cmd_code     (1 = kontağı kapat, 2 = motor çalıştır/durdur)
  24 u32      beat         (her yayında artar)
  28 f32      fren ekseni  (0..1, lastik patlaması: oyuncunun frenine eklenir; 1.6+)
  32 f32      direksiyon   (-1..1, oyuncunun direksiyonuna eklenir)
  36 u32      eksen anı    (GetTickCount; 500 ms'den eski eksen değeri eklentide sıfırlanır)
  40 u32      sürüş modu   (0 kapalı, 1 ECO, 2 COMFORT, 3 SPORT; 1.8+, drivemode.py)
  44 f32      en yüksek gaz (0..1)      48 f32 gaz artış hızı (/sn, 0 = sınırsız)
  52 f32      hız sınırı (km/h, 0 = yok) 56 f32 pedal eğrisi üssü (1 = doğrusal)
  60 u32      mod anı      (GetTickCount; 1,5 sn'den eskiyse eklenti gaza karışmaz)
  64 ...      UTF-8 yük: sekmeyle ayrılmış satırlar (aşağıya bakın)

Katman bloğu "Local\\ETS2BakimOverlay" (DLL yazar, Python okur)
  0  char[8]  "EBKOVL01"
  12 u32      frames       16 u32 handled_cmd_seq   20 u32 flags
  24 u32      width        28 u32 height            36 char[28] renderer
  32 u32      panel_skip   (1.11+: oyun içi panel açılışta kurulmadıysa nedeni; alt bayt 1 ayar, 2 eklenti, 3 donma;
                            ikinci bayt bulunan eklenti: 1 OptiScaler, 2 DLSS 5)
  96 u32      svc_seq      100 char[160] svc_cmd    (oyun içi servis menüsünden seçilen işlem, 1.3+)
  260 u32     svc_tick     (gönderim anı, GetTickCount; 15 sn'den eski komut uygulanmaz)

Yük satırları:
  k  anahtar  metin  seviye  oran        tek değer (seviye: g/w/c/m/n, oran: 0..1 ya da -1)
  w  seviye   metin                       uyarı
  e  zaman    seviye  metin               olay kaydı
  b  ölçüt    yüzde                       yağ ömrü ölçütü
  f  ad       açıklama                    aktif arıza
  n  metin                                yağ analizi notu
  h  anahtar  min  max  v1,v2,...         son dakikaların grafiği
  m  40 sayı                              devir x yük haritası (dakika)
  u  anahtar  komut  etiket  ayrıntı  bayrak   servis menüsü maddesi (bayrak: h/d/c/n)
  r  sıra     1|0    mesaj                servis komutunun sonucu
  t  kimlik   seviye  etiket              yanan gösterge lambası (telltales.ORDER sırasıyla; w sarı, c kırmızı)
  y  dingil   diş  diş_sev  oran  ayrıntı  ayrıntı_sev  grup  tekerlek  lastik
                                          lastik satırı (dingil grubu başına; son üçü 1.11+)
"""
import struct
import time
from multiprocessing import shared_memory

from . import alerts, currency, i18n
from .gamecfg import DEFAULT_HUD_VK, HudKey
from .gameinput import key_label
from .i18n import N, T
from .levels import _worst, session_levels, value_levels
from .telltales import Telltales

STATE_NAME = "Local\\ETS2BakimState"
OVL_NAME = "Local\\ETS2BakimOverlay"
STATE_SIZE = 256 * 1024
HEADER = 64
CMD_IGNITION_OFF = 1
CMD_ENGINE_TOGGLE = 2
FLAG_HOOKED, FLAG_RENDERING, FLAG_INPUT_REG, FLAG_INPUT_ACTIVE = 1, 2, 4, 8
SKIP_REASONS = {1: "user", 2: "injector", 3: "crash"}
INJECTORS = {1: "OptiScaler", 2: "DLSS 5"}
DEFAULT_OVL_VK = 0x77            # F8
PANEL_MODES = ("auto", "on", "off")
SVC_SEQ_OFF, SVC_CMD_OFF, SVC_CMD_LEN, SVC_TICK_OFF = 96, 100, 160, 260
SVC_MAX_AGE_MS = 15000
RESULT_KEEP_S = 20.0


def _tick_ms():
    """Windows GetTickCount (DLL ile aynı saat). Windows dışında None."""
    try:
        import ctypes
        return ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
    except (AttributeError, OSError):
        return None


def _clean(s):
    return str(s).replace("\t", " ").replace("\n", " ").replace("\r", " ")


def _frac(v, lo, hi):
    if v is None:
        return -1.0
    return max(0.0, min(1.0, (v - lo) / (hi - lo)))


def _pct(v, d=0):
    """Dile göre yüzde: tr %42 · en 42% · de 42 %"""
    if v is None:
        return "—"
    n = N(v, d)
    return f"%{n}" if i18n.LANG == "tr" else f"{n}%" if i18n.LANG == "en" else f"{n} %"


def _dur(minutes):
    if minutes is None:
        return "—"
    h, m = divmod(int(round(minutes)), 60)
    return f"{h}:{m:02d}"


# katman anahtarı -> durum yolu (seviyeler levels.value_levels ile hesaplanır; uygulama penceresiyle aynı)
SHORT = {
    "cool": "thermal.t_cool", "oilt": "thermal.t_oil", "oilp": "oil.pressure", "volt": "battery.voltage",
    "life": "oil.life", "olvl": "oil.level_pct", "clvl": "coolant.level_pct", "freeze": "coolant.freeze",
    "inhib": "coolant.inhibitor", "soc": "battery.soc", "soh": "battery.soh", "dpf": "dpf.soot", "ash": "dpf.ash",
    "health": "engine.health", "btmp": "live.brake_temp", "rpm": "live.rpm", "exh": "live.exh",
    "amp": "battery.current", "crank": "battery.crank_v", "minsoc": "battery.min_start_soc",
    "btemp": "battery.temp", "h50": "battery.hours_to_50", "visc": "oil.visc_chg", "tbn": "oil.tbn",
    "soot": "oil.soot", "fe": "oil.fe", "filter": "oil.filter_pct", "okm": "oil.km", "glycol": "coolant.glycol",
    "ph": "coolant.ph", "scale": "coolant.scale", "wear": "engine.wear_rate", "air": "live.air_bar",
    "fuel_lvl": "fuel.pct", "adblue": "adblue.pct", "tire": "tires.status", "tire_game": "tires.game_wear",
    "gbox": "trans.t_oil",
}


def _levels(S):
    src = S.get("levels") or value_levels(S)
    lv = {k: src.get(path, "n") for k, path in SHORT.items()}
    lv["ice"] = _worst(src.get("thermal.block_ice", "g"), src.get("thermal.rad_ice", "g"))
    lv["clutch"] = _worst(src.get("trans.t_clutch", "g"), src.get("trans.clutch_wear", "g"))
    return lv


def _hud_cfg(settings, hud_vk):
    """Katmanın oyunun HUD gizleme tuşuyla (varsayılan F3) birlikte gizlenmesi için ayar satırları."""
    on = 1 if (settings or {}).get("hide_with_hud", True) else 0
    return [f"cfg\thudsync\t{on}", f"cfg\thudkey\t{int(hud_vk or DEFAULT_HUD_VK)}"]


def valid_overlay_key(vk):
    """Katmanın tuşu olabilir mi: fare düğmeleri, Esc, Shift/Ctrl/Alt ve Windows tuşları olamaz (DLL ile aynı kural)."""
    return (isinstance(vk, int) and 0x08 <= vk < 0xFF and vk != 0x1B and not 0x10 <= vk <= 0x12
            and vk not in (0x5B, 0x5C) and not 0xA0 <= vk <= 0xA5)


def overlay_key(settings):
    vk = (settings or {}).get("overlay_key", DEFAULT_OVL_VK)
    return vk if valid_overlay_key(vk) else DEFAULT_OVL_VK


def _ovl_cfg(settings):
    """Katmanın tuşu (F8 ya da Ayarlar'da seçilen; adıyla) ve oyun içi panel ayarı (oyunun sonraki açılışında geçerli)."""
    vk = overlay_key(settings)
    mode = (settings or {}).get("overlay_panel", "auto")
    return [f"cfg\tovlkey\t{vk}\t{_clean(key_label(vk))}", f"cfg\tpanel\t{mode if mode in PANEL_MODES else 'auto'}"]


def service_lines(menu=None, result=None):
    """Servis menüsü maddeleri (u), ipucu (k svc_hint) ve son komutun sonucu (r)."""
    lines = []
    if menu:
        items, (hint, lvl) = menu
        lines.append(f"k\tsvc_hint\t{_clean(hint)}\t{lvl}\t-1.0000")
        for it in items:
            lines.append("u\t" + "\t".join(_clean(it[k]) for k in ("key", "cmd", "label", "detail")) + f"\t{it['flag']}")
    if result:
        seq, ok, msg = result
        lines.append(f"r\t{seq}\t{1 if ok else 0}\t{_clean(msg)}")
    return lines


def build_payload(S, D, history, settings, beat, hud_vk=DEFAULT_HUD_VK, menu=None, result=None, lamps=None):
    level = settings.get("alert_level", "normal")
    lines = ["v\t1", f"cfg\tsound\t{1 if settings.get('sound', True) else 0}", f"cfg\tlang\t{i18n.LANG}",
             f"cfg\tbanner\t{'w' if level == 'all' else 'c'}", *_hud_cfg(settings, hud_vk), *_ovl_cfg(settings),
             f"hb\t{beat}"]
    lv = _levels(S)
    th, o, c, b, d, L = S["thermal"], S["oil"], S["coolant"], S["battery"], S["dpf"], S["live"]
    st, tk, loc, E = S["status"], S["truck"], S["location"], S["engine"]
    edb = S.get("engine_db") or {}

    def k(key, text, level="n", frac=-1.0):
        lines.append(f"k\t{key}\t{_clean(text)}\t{level}\t{frac:.4f}")

    k("truck", f"{tk.get('brand', '')} {tk.get('name', '')}".strip() or "—")
    k("plate", tk.get("plate", ""))
    k("time", st.get("time", ""))
    k("odo", f"{N(tk.get('odometer'))} km")
    k("loc", T("{city} yakını", city=loc["city"]) if loc.get("city") else "—")
    k("amb", f"{N(loc['ambient'], 1)} °C")
    conn = T("DEMO") if st.get("source") == "demo" else (T("Duraklatıldı") if st.get("paused") else T("Bağlı")) if st.get("connected") else T("Bağlı değil")
    k("conn", conn, "n" if st.get("source") == "demo" else "w" if st.get("paused") else "g" if st.get("connected") else "c")
    killed = L["killed"] and L["engine_on"]
    k("run", T("DURDU") if killed else T("Çalışıyor") if L["running"] else T("Kapalı"), "c" if killed else "g" if L["running"] else "m")
    # motor
    k("rpm", f"{N(L['rpm'])} rpm", lv["rpm"], _frac(L["rpm"], 0, L.get("rpm_max") or 2300))
    k("load", _pct(L["load"]), "n", _frac(L["load"], 0, 100))
    k("gear", T("vites {g}", g=L["gear"]) if L.get("gear") else T("vites —"))
    k("speed", f"{N(L['speed'])} km/h")
    nav = L.get("nav_km") or 0   # rota danışmanının değerleri (1.11+)
    k("nav_dst", L.get("city_dst") or "—")
    k("nav_dist", f"{N(nav)} km" if nav > 0 else "—")
    k("nav_eta", _dur(L.get("nav_min")) if nav > 0 else "—")
    k("nav_limit", N(L["speed_limit"]) if L.get("speed_limit") else "")
    k("nav_cargo", L.get("cargo") or "")
    k("power", f"{N(L['power_kw'])} kW")
    k("torque", f"{N(L['torque_nm'])} Nm")
    k("fuel", f"{N(L['fuel_lph'], 1)} L/h")
    k("l100", f"{N(L['l100'], 1)} L/100 km" if L.get("l100") is not None else "—")
    k("exh", f"{N(L['exh'])} °C", lv["exh"], _frac(L["exh"], 0, 650))
    k("ret", f"{N(L['retarder_kw'])} kW" if L["retarder_kw"] else (T("motor freni {kw} kW", kw=N(L["engine_brake_kw"])) if L["engine_brake_kw"] else "—"))
    # sıcaklık / yağ / akü
    k("cool", f"{N(th['t_cool'])} °C", lv["cool"], _frac(th["t_cool"], 40, 125))
    k("oilt", f"{N(th['t_oil'])} °C", lv["oilt"], _frac(th["t_oil"], 40, 150))
    k("oilp", f"{N(o['pressure'], 1)} bar", lv["oilp"], _frac(o["pressure"], 0, 6))
    vsc = (b.get("volts") or 24) / 24.0
    k("volt", f"{N(b['voltage'], 1)} V", lv["volt"], _frac(b["voltage"], 20 * vsc, 29 * vsc))
    k("amp", f"{'+' if b['current'] > 0.5 else ''}{N(b['current'])} A", lv["amp"])
    k("soc", _pct(b["soc"]), lv["soc"], _frac(b["soc"], 0, 100))
    k("soh", _pct(b["soh"]), lv["soh"], _frac(b["soh"], 0, 100))
    k("crank", f"{N(b['crank_v'], 1)} V", lv["crank"])
    k("minsoc", _pct(b["min_start_soc"]) if b.get("min_start_soc") is not None else T("marş imkânsız"),
      lv["minsoc"])
    k("bload", T("{a} A · alternatör {b} A", a=N(b["load_a"]), b=N(b["alt_a"]))
      + (f" · {b['wiper']}" if b.get("wiper_stage") else ""))
    k("btemp", T("{t} °C · donma {f} °C", t=N(b["temp"]), f=N(b["freeze"])), lv["btemp"])
    k("h50", T("{n} sa", n=N(b["hours_to_50"], 1)) if b.get("hours_to_50") is not None else "—", lv["h50"])
    k("olife", _pct(o["life"]), lv["life"], _frac(o["life"], 0, 100))
    k("olim", o.get("limiting", ""))
    k("olvl", f"{N(o['volume'], 1)} / {N(o['capacity'])} L", lv["olvl"], _frac(o["level_pct"], 0, 110))
    k("visc", T("{v} cSt · 100 °C'de {w}", v=N(o["visc_now"]), w=N(o["visc100"], 1)), lv["visc"])
    k("tbn", f"{N(o['tbn'], 1)} / {N(o['tbn_ref'], 1)}", lv["tbn"])
    k("soot", _pct(o["soot"], 2), lv["soot"])
    k("fe", f"{N(o['fe'])} ppm", lv["fe"])
    k("filter", _pct(o["filter_pct"]), lv["filter"], _frac(o["filter_pct"], 0, 100))
    k("okm", f"{N(o['km'])} / {N(o['interval_km'])} km", lv["okm"])
    k("grade", o.get("grade_name", ""))
    k("clvl", _pct(c["level_pct"]), lv["clvl"], _frac(c["level_pct"], 0, 100))
    k("glycol", _pct(c["glycol"]), lv["glycol"])
    k("freeze", f"{N(c['freeze'])} °C", lv["freeze"])
    k("expmin", f"{N(loc['expected_min'])} °C")
    k("ph", N(c["ph"], 2), lv["ph"])
    k("inhib", _pct(c["inhibitor"]), lv["inhib"])
    k("scale", _pct(c["scale"]), lv["scale"])
    k("thermo", _pct(th["thermostat"]))
    k("fan", T("Devrede") if th["fan"] else T("Kapalı"), "w" if th["fan"] else "n")
    k("sysp", T("{p} bar · kaynama {b} °C", p=N(th["pressure"], 2), b=N(th["boil_point"])), "c" if th["boiling"] else "n")
    k("ice", T("blok %{b} · radyatör %{r}", b=N(th["block_ice"]), r=N(th["rad_ice"])),
      lv["ice"])
    k("ctype", c.get("type_name", ""))
    # yakıt, AdBlue, lastikler
    fu, ab, ty = S.get("fuel") or {}, S.get("adblue") or {}, S.get("tires") or {}
    k("fuel_lvl", (f"{_pct(fu['pct'])} · " if fu.get("pct") is not None else "") + f"{N(fu.get('l'))} L",
      lv["fuel_lvl"], _frac(fu.get("pct"), 0, 100))
    k("fuel_range", T("~{n} km", n=N(fu["range_km"])) if fu.get("range_km") else "—")
    k("fuel_avg", f"{N(fu['l100_avg'], 1)} L/100 km" if fu.get("l100_avg") else "—")
    if ab.get("enabled"):
        k("adblue", f"{_pct(ab.get('pct'))} · {N(ab.get('l'), 1)} L", lv["adblue"], _frac(ab.get("pct"), 0, 100))
        k("adblue_rate", T("yakıtın %{p}'i", p=N(ab.get("rate_pct"), 1)))
        k("adblue_range", T("~{n} km", n=N(ab["range_km"])) if ab.get("range_km") else "—")
    else:
        k("adblue", T("yok (SCR'siz motor)"), "m")
    if ty.get("groups"):
        k("tire", T("{mm} mm · basınç {p}", mm=N(ty.get("min_tread"), 1), p=_pct(ty.get("min_pressure_pct"))), lv["tire"])
        k("tire_game", _pct(ty.get("game_wear"), 1), lv["tire_game"])
        for g in ty["groups"]:
            gl = g["lv"]
            detail = T("{c} bar (şu an {h}) · {t} °C", c=N(g["cold_bar"], 1), h=N(g["hot_bar"], 1), t=N(g["temp"]))
            if g["blown"]:
                detail = T("PATLADI")
            elif g["lifted"]:
                detail += " · " + T("kaldırılmış")
            elif g["leak"]:
                detail += " · " + T("patlak")
            frac = (g["tread"] - g["legal_mm"]) / max(0.1, g["new"] - g["legal_mm"])
            lines.append(f"y\t{_clean(g['name'])}\t{N(g['tread'], 1)} mm\t{gl['tread']}\t{max(0.0, frac):.3f}"
                         f"\t{_clean(detail)}\t{_worst(gl['pressure'], gl['temp'])}"
                         f"\t{g['key']}\t{g.get('wheels', 2)}\t{g['tires']}")
    k("dpf", _pct(d["soot"]), lv["dpf"], _frac(d["soot"], 0, 130))
    k("ash", _pct(d["ash"]), lv["ash"], _frac(d["ash"], 0, 100))
    k("regen", T("Aktif") if d["burning"] else T("Bekliyor") if d["regen"] else T("Yok"), "w" if d["regen"] else "n")
    k("health", _pct(E["health"], 1), lv["health"], _frac(E["health"], 0, 100))
    k("wear", f"x{N(E['wear_rate'], 2)}", lv["wear"])
    tr = S.get("trans") or {}
    if tr:
        k("gbox", f"{N(tr.get('t_oil'))} °C", lv["gbox"], _frac(tr.get("t_oil"), 40, 140))
        k("clutch", T("%{w} aşınmış · {t} °C", w=N(tr.get("clutch_wear")), t=N(tr.get("t_clutch"))), lv["clutch"],
          _frac(100 - (tr.get("clutch_wear") or 0), 0, 100))
    k("engine", f"{tk.get('spec', {}).get('name', '')} · {T('{n} hp', n=N(edb.get('hp')))} · {N(edb.get('torque'))} Nm")
    k("model", f"{edb.get('model_name') or T('Model tanınmadı')} · {T('otomatik') if edb.get('mode') == 'auto' else T('elle')}")
    det = edb.get("detect") or {}
    if det.get("torque") is not None:
        k("detect", T("ölçülen ≈{nm} Nm → {e}", nm=N(det["torque"]), e=det.get("suggest_label")) + (" ✓" if det.get("confident") else ""))
    else:
        k("detect", T("örnek {n}/{k}", n=det.get("samples", 0), k=det.get("need", 60)))
    cur = st.get("currency") or {"symbol": "€", "rate": 1.0}   # oyunda seçili para birimi (tutarlar avro tabanlı)
    money = lambda v: currency.fmt(v, cur)
    k("cost", money(S.get("costs_total")))
    # fren ve hava
    bt = L.get("brake_temp") or 0
    k("btmp", f"{N(bt)} °C", lv["btmp"], _frac(bt, 0, 600))
    k("air", f"{N(L.get('air_bar'), 1)} bar", lv["air"], _frac(L.get("air_bar") or 0, 0, 12.5))
    k("mass", f"{N(L.get('mass_t'), 1)} t")
    if D:
        ss, ta, tp = D.get("session") or {}, D.get("analysis") or {}, D.get("trip") or {}
        sc = ss.get("score") or 0
        k("score_s", N(ss.get("score")), "g" if sc >= 75 else "w" if sc >= 50 else "c")
        k("score_t", N(ta.get("score")))
        sl = session_levels(ss)
        k("eco", _pct(ss.get("eco_pct")), sl["eco"])
        k("idle", _pct(ss.get("idle_pct")), sl["idle"])
        k("cruise", _pct(ss.get("cruise_pct")))
        k("harsh", N(ss.get("harsh_brake")), sl["harsh"])
        k("lug", T("{n} dk", n=N(ss.get("lugging_min"))), sl["lug"])
        k("coldload", T("{n} dk", n=N(ss.get("cold_load_min"))), sl["coldload"])
        k("hours", T("{h} sa · {d} km", h=N(ss.get("engine_h"), 1), d=N(ss.get("distance_km"))))
        k("l100avg", f"{N(ss.get('l_per_100km'), 1)} L/100 km" if ss.get("l_per_100km") is not None else "—")
        k("starts", f"{ss.get('starts', 0)} / {ss.get('cold_starts', 0)} / {ss.get('failed_starts', 0)}")
        k("avgload", _pct(ss.get("avg_load")))
        k("avgrpm", f"{N(ss.get('avg_rpm'))} rpm" if ss.get("avg_rpm") is not None else "—")
        k("shifts", N(ss.get("shifts_per_100"), 1) if ss.get("shifts_per_100") is not None else "—")
        grid = ss.get("rpm_load_min") or []
        if grid:
            lines.append("m\t" + ",".join(f"{v:.2f}" for col in grid for v in col))
        if tp:
            route = f"{tp['src']} → {tp['dst']}" if tp.get("src") else "—"
            k("trip_route", route)
            k("trip_cargo", tp.get("cargo") or "—")
            k("trip_dist", f"{N(tp.get('distance_km'))} km")
            k("trip_time", _dur(tp.get("duration_min")))
            k("trip_avgspd", f"{N(tp.get('avg_speed'))} km/h" if tp.get("avg_speed") else "—")
            k("trip_l100", f"{N(tp.get('l_per_100km'), 1)} L/100 km" if tp.get("l_per_100km") is not None else "—")
            k("trip_fuel", f"{N(tp.get('fuel_l'))} L · {money(tp.get('fuel_cost'))}")
            k("trip_co2", f"{N(tp.get('co2_kg'))} kg CO₂")
            k("trip_idle", f"{_pct(tp.get('idle_pct'))} · {N(tp.get('idle_fuel_l'), 1)} L")
            k("trip_score", N(tp.get("score")), "g" if (tp.get("score") or 0) >= 75 else "w" if (tp.get("score") or 0) >= 50 else "c")
            split = [tp.get("brake_service_pct"), tp.get("brake_retarder_pct"), tp.get("brake_engine_pct")]
            if split[0] is not None:
                lines.append("x\t" + ",".join(f"{v:.1f}" for v in split))
            k("srvbrk", T("{n} dk", n=N(tp.get("service_brake_min"))))
            k("hotbrk", T("{n} dk", n=N(tp.get("brake_hot_min"))), "w" if (tp.get("brake_hot_min") or 0) > 1 else "n")
            k("maxbrk", f"{N(tp.get('max_brake_temp'))} °C")
            for lab, val in zip(tp.get("speed_labels", []), tp.get("speed_l100", [])):
                if val is not None:
                    lines.append(f"s\t{lab}\t{val:.1f}")
            for g in sorted(tp.get("gears", []), key=lambda x: -x["pct"])[:8]:
                lines.append(f"g\t{g['gear']}\t{g['pct']:.1f}")
        fc = D.get("forecast") or {}
        for it in fc.get("items", []):
            parts = []
            if it.get("km") is not None:
                parts.append(f"{N(it['km'])} km")
            if it.get("days") is not None:
                parts.append(T("{n} gün", n=N(it["days"])))
            text = T("şimdi") if (it.get("km") == 0 or it.get("days") == 0) else " / ".join(parts) or "—"
            lines.append(f"p\t{_clean(it['label'])}\t{_clean(text)}\t{it['lvl']}")
        if fc.get("cost_per_1000") is not None:
            k("cost1000", f"{money(fc['cost_per_1000'])} / 1000 km")
    for w in S.get("warnings", [])[:8]:
        lines.append(f"w\t{w['level']}\t{_clean(w['text'])}")
    for e in S.get("log", [])[:8]:
        lines.append(f"e\t{_clean(e['time'])}\t{e['level']}\t{_clean(e['text'])}")
    for name, pct in sorted((o.get("breakdown") or {}).items(), key=lambda x: x[1])[:6]:
        lines.append(f"b\t{_clean(name)}\t{pct}")
    for fl in S.get("faults", []):
        lines.append(f"f\t{_clean(fl['name'])}\t{_clean(fl['desc'])}")
    rep = (S.get("reports") or {}).get("oil")
    if rep:
        for note in rep.get("notes", [])[:3]:
            lines.append(f"n\t{_clean(note)}")
    hist = list(history)[-600:]
    if len(hist) >= 2:
        step = max(1, len(hist) // 120)
        sample = hist[::step]
        vsc = ((S.get("battery") or {}).get("volts") or 24) / 24.0
        for key, lo, hi in (("cool", 20, 120), ("oil_t", 20, 140), ("oil_p", 0, 6), ("volt", 22 * vsc, 29 * vsc),
                            ("rpm", 0, 2200)):
            vals = [h[key] for h in sample]
            lines.append(f"h\t{key}\t{min(lo, min(vals))}\t{max(hi, max(vals))}\t" + ",".join(f"{v:.1f}" for v in vals))
    lines += service_lines(menu, result)
    for key, lvl in lamps or ():
        lines.append(f"t\t{key}\t{lvl}\t{_clean(Telltales.label(key))}")
    return "\n".join(lines).encode("utf-8")[: STATE_SIZE - HEADER - 1]


class OverlayBridge:
    def __init__(self, state_name=STATE_NAME, ovl_name=OVL_NAME):
        self.state_name, self.ovl_name = state_name, ovl_name
        self.shm = None
        self.ovl = None
        self.beat = 0
        self.cmd_seq = 0
        self.last_cmd_time = 0.0
        self.status = {"present": False, "rendering": False, "input": False, "width": 0, "height": 0,
                       "renderer": "", "fps": 0.0, "skip": "", "skip_by": ""}
        self._frames_prev = None
        self._frames_t = 0.0
        self._last_ovl_try = 0.0
        self.hud = HudKey()
        self.svc_seen = None          # katmandaki son servis komutu sırası (ilk okumada yalnızca kaydedilir)
        self.pending_service = None   # (sıra, komut) — App uygulayacak
        self.result = None            # (sıra, başarılı, mesaj)
        self.result_time = 0.0
        self.telltales = Telltales()
        try:
            try:
                self.shm = shared_memory.SharedMemory(name=self.state_name, create=True, size=STATE_SIZE)
                created = True
            except FileExistsError:
                self.shm = shared_memory.SharedMemory(name=self.state_name, create=False)
                created = False
            buf = self.shm.buf
            buf[0:8] = b"EBKSTAT1"
            if created:
                struct.pack_into("<IIIII", buf, 8, 0, 0, 0, 0, 0)
            else:
                # blok oyundaki eklenti açık tuttuğu için yaşıyor (uygulama yeniden açıldı): komut sırası kaldığı yerden
                # sürer; sıfırlansaydı ilk komut eklentinin son gördüğü sırayla aynı çıkabilir ve yok sayılırdı
                self.cmd_seq = struct.unpack_from("<I", buf, 16)[0]
        except Exception:
            self.shm = None

    def lamps(self, S, settings):
        """Yanan gösterge lambaları: Ayarlar'daki önem derecesi ve üstü (önemsiz … kritik), tek tek kapatılanlar hariç.
        Her simülasyon adımında çağrılır (yanık kalma süreleri adım adım izlenir; yayın aralığından bağımsız)."""
        if not S or "thermal" not in S or not settings.get("telltales", True):
            return []
        return alerts.visible_lamps(self.telltales.update(S, min_level=settings.get("lamp_level", "onemsiz")), settings)

    def publish(self, S, D, history, settings, menu=None, lamps=None):
        if self.shm is None or not S or "thermal" not in S:
            self._poll_overlay()
            return
        if lamps is None:
            lamps = self.lamps(S, settings)
        self.beat = (self.beat + 1) & 0xFFFFFFFF
        payload = build_payload(S, D, history, settings, self.beat, self.hud.get(), menu, self._live_result(), lamps)
        self._write(payload)
        self._poll_overlay()

    def heartbeat(self):
        """Yük yazılmadan yalnızca canlılık sayacı artar: katman yayın aralığı uzunken (Ayarlar → Değer güncelleme
        sıklığı) eklenti 3 sn içinde sayaç değişmeyince "simülatör kapalı" sanmasın. Katmanın durumu ve servis menüsü
        komutları her adımda okunur."""
        if self.shm is not None:
            self.beat = (self.beat + 1) & 0xFFFFFFFF
            struct.pack_into("<I", self.shm.buf, 24, self.beat)
        self._poll_overlay()

    def _live_result(self):
        if self.result and time.monotonic() - self.result_time < RESULT_KEEP_S:
            return self.result
        return None

    def take_service(self):
        """Katmanın servis menüsünden gelen, henüz uygulanmamış komut: (sıra, komut) ya da None."""
        cmd, self.pending_service = self.pending_service, None
        return cmd

    def set_result(self, seq, ok, msg):
        self.result = (seq, ok, msg)
        self.result_time = time.monotonic()

    def publish_waiting(self, text, settings=None):
        """Kamyon verisi yokken (oyun menüde/kapalı) katmana 'bekleniyor' bilgisi gönderir."""
        if self.shm is None:
            self._poll_overlay()
            return
        self.beat = (self.beat + 1) & 0xFFFFFFFF
        lines = ["v\t1", f"cfg\tlang\t{i18n.LANG}", *_hud_cfg(settings, self.hud.get()), *_ovl_cfg(settings),
                 f"hb\t{self.beat}",
                 f"k\twaiting\t{_clean(text)}\tw\t-1"]
        payload = "\n".join(lines).encode("utf-8")
        self._write(payload)
        self._poll_overlay()

    def _write(self, payload):
        buf = self.shm.buf
        seq = ((struct.unpack_from("<I", buf, 8)[0] + 1) | 1) & 0xFFFFFFFF
        struct.pack_into("<I", buf, 8, seq)                       # yazılıyor (tek)
        buf[HEADER:HEADER + len(payload)] = payload
        struct.pack_into("<I", buf, 12, len(payload))
        struct.pack_into("<I", buf, 24, self.beat)
        struct.pack_into("<I", buf, 8, (seq + 1) & 0xFFFFFFFF)   # tamam (çift)

    def _poll_overlay(self):
        now = time.monotonic()
        if self.ovl is None:
            if now - self._last_ovl_try < 2.0:
                return
            self._last_ovl_try = now
            try:
                self.ovl = shared_memory.SharedMemory(name=self.ovl_name, create=False)
            except (FileNotFoundError, OSError, ValueError):
                self.status.update(present=False, rendering=False, input=False, skip="", skip_by="")
                return
        try:
            buf = self.ovl.buf
            if bytes(buf[0:8]) != b"EBKOVL01":
                return
            frames, handled, flags, w, h, skip = struct.unpack_from("<IIIIII", buf, 12)
            renderer = bytes(buf[36:64]).split(b"\0")[0].decode("ascii", "replace")
        except Exception:
            self.ovl = None
            return
        if self._frames_prev is None or now - self._frames_t >= 1.0:
            if self._frames_prev is not None:
                fps = (frames - self._frames_prev) / (now - self._frames_t)
                self.status["fps"] = max(0.0, fps)
                self.status["present"] = fps > 0.5
            self._frames_prev, self._frames_t = frames, now
        self.status.update(rendering=bool(flags & FLAG_RENDERING), input=bool(flags & FLAG_INPUT_REG),
                           input_active=bool(flags & FLAG_INPUT_ACTIVE), width=w, height=h,
                           renderer=renderer, handled=handled, skip=SKIP_REASONS.get(skip & 0xFF, ""),
                           skip_by=INJECTORS.get((skip >> 8) & 0xFF, ""))
        self._poll_service(buf)

    def _poll_service(self, buf):
        """Katman 1.3+ servis menüsünden yeni bir komut yazdıysa sıraya alır."""
        if len(buf) < SVC_TICK_OFF + 4:
            return
        seq = struct.unpack_from("<I", buf, SVC_SEQ_OFF)[0]
        if seq == 0 or seq == self.svc_seen:
            return
        first = self.svc_seen is None
        self.svc_seen = seq
        sent, now = struct.unpack_from("<I", buf, SVC_TICK_OFF)[0], _tick_ms()
        fresh = now is not None and ((now - sent) & 0xFFFFFFFF) < SVC_MAX_AGE_MS
        if first and not fresh:  # açılışta bulunan eski komut tekrar uygulanmaz
            return
        raw = bytes(buf[SVC_CMD_OFF:SVC_CMD_OFF + SVC_CMD_LEN]).split(b"\0")[0]
        self.pending_service = (seq, raw.decode("utf-8", "replace"))

    def input_ready(self):
        return self.status.get("present") and self.status.get("input")

    def send_command(self, code, cooldown=2.5):
        """Oyun içi semantik giriş cihazına komut gönderir. Dönüş: gönderildi mi."""
        if self.shm is None:
            return False
        now = time.monotonic()
        if now - self.last_cmd_time < cooldown:
            return False
        self.last_cmd_time = now
        self.cmd_seq = (self.cmd_seq + 1) & 0xFFFFFFFF
        if self.cmd_seq == 0:
            self.cmd_seq = 1
        struct.pack_into("<II", self.shm.buf, 16, self.cmd_seq, code)
        return True

    def set_axes(self, brake=0.0, steer=0.0):
        """Oyunun fren ve direksiyon girdisine eklenecek değerler (lastik patlaması). Her adımda yazılmalı:
        eklenti 500 ms'den eski değeri sıfırlar."""
        if self.shm is None:
            return
        tick = _tick_ms() or 0
        struct.pack_into("<ffI", self.shm.buf, 28, float(brake), float(steer), tick)

    def set_drive(self, mode=0, cap=1.0, rate=0.0, vlim=0.0, curve=1.0):
        """Sürüş modu parametreleri (drivemode.header_params). Her adımda yazılmalı: eklenti 1,5 sn'den eski modu
        yok sayar (simülatör kapanınca gaza karışmaz)."""
        if self.shm is None:
            return
        tick = _tick_ms() or 0
        struct.pack_into("<IffffI", self.shm.buf, 40, int(mode), float(cap), float(rate), float(vlim), float(curve), tick)

    def ignition_off(self, cooldown=2.5):
        return self.send_command(CMD_IGNITION_OFF, cooldown)

    def engine_toggle(self, cooldown=2.5):
        return self.send_command(CMD_ENGINE_TOGGLE, cooldown)

    def close(self):
        try:
            self.set_axes(0.0, 0.0)
            self.set_drive(0)
        except Exception:
            pass
        for m in (self.shm, self.ovl):
            try:
                if m is not None:
                    m.close()
            except Exception:
                pass
