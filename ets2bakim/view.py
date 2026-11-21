"""Arayüze ve oyun içi katmana gönderilen durum, uyarılar, analiz ve bakım planı."""
from . import coolant as coolant_mod
from . import alerts, engines, i18n, prices, vehicles
from . import rates as rates_mod
from . import oil as oil_mod
from . import transmission as trans_mod
from .battery import KINDS as BATTERY_KINDS
from .battery import replace_cost as battery_replace_cost
from .dpf import DPF
from .engine import EngineHealth
from .faults import FAULTS, PART_GROUPS
from .i18n import T, render
from .levels import session_levels, value_levels
from .adblue import FREEZE_C as ADBLUE_FREEZE_C, PRICE_L as ADBLUE_PRICE_L, has_scr
from .levels import tire_group_levels
from .preheat import duration_s as preheat_duration_s
from .tires import GROUP_NAMES, GROUPS as TIRE_GROUPS, LEGAL_MM as TIRE_LEGAL_MM, WARN_TREAD_MM as TIRE_WARN_MM, Tires
from .tires import PRICE as TIRE_PRICE, TIERS as TIRE_TIERS, tier_of
from .util import clamp, fmt_minutes
from .wipers import OFF, SLOW, STAGE_NAMES, wiper_current_a

LEVEL_ORDER = {"crit": 0, "warn": 1, "info": 2}


def r(x, n=1):
    return None if x is None else round(float(x), n)


def warnings(t, f, amb, expected_min):
    """Tüm uyarılar (seviye: crit / warn / info). Gereksiz tekrarları önlemek için eşikler bilerek sıkı tutuldu."""
    w = []

    def add(level, key, msgid, /, _sub=None, **kw):  # yalnızca konumsal: metin parametreleri (ör. lvl=) çakışmasın
        # kimlik: aynı şablonun farklı nesneleri (arıza, dingil) ayrı uyarıdır; değeri değişen uyarı aynı kalır (ses bir kez)
        # key: kalıcı anahtar (alerts.GROUPS); Ayarlar'da kapatılan uyarılar bununla süzülür
        w.append({"level": level, "key": key, "text": T(msgid, **kw),
                  "id": msgid if _sub is None else f"{msgid}|{_sub}"})

    fl = t.flags
    running = fl["running"]
    o, c, th, b, d = t.oil, t.coolant, t.thermal, t.battery, t.dpf

    if t.spec.electric:
        add("info", "electric", "Elektrikli kamyon: bu simülatör dizel motorlar için tasarlandı.")
    if t.killed and f.engine_on:
        add("crit", "engine_dead", "MOTOR GERÇEKTE ÇALIŞMIYOR: {reason} Oyunda motoru kapatın.", reason=t.kill_reason)
    for k in t.faults.active:
        add(FAULTS[k].get("level", "crit"), f"fault:{k}", "{name_t}: {desc_t}", _sub=k, name_t=FAULTS[k]["name"], desc_t=FAULTS[k]["desc"])

    # yağ
    if running and t.oil_low_s >= oil_mod.LOW_P_DELAY_S:
        add("crit", "oil_pressure", "YAĞ BASINCI DÜŞÜK ({p:.1f} bar) — motoru hemen durdurun!", p=t.oil_pressure)
    if o.level_frac < 0.70:
        add("crit", "oil_level_crit", "Yağ seviyesi kritik (%{lvl:.0f}) — yağ pompası hava emiyor.", lvl=o.level_frac * 100)
    elif o.level_frac < o.min_frac:
        add("warn", "oil_level_low", "Yağ seviyesi MIN altında (%{lvl:.0f}, {v:.1f} L). Yağ ekleyin.", lvl=o.level_frac * 100, v=o.volume_l)
    elif o.level_frac > 1.06:
        add("warn", "oil_level_high", "Yağ seviyesi MAX üstünde: köpüklenme ve yağ yakma riski.")
    life, lim = o.life()
    if life <= 0:
        add("crit", "oil_life_end", "Yağ ömrü bitti ({lim_t}). Yağ ve filtreyi değiştirin.", lim_t=lim)
    elif life < 0.1:
        add("warn", "oil_life_low", "Yağ ömrü %{life:.0f} ({lim_t}). Değişim yaklaşıyor.", life=life * 100, lim_t=lim)
    if o.filter_bypass:
        add("warn", "oil_filter", "Yağ filtresi tıkalı: bypass valfi açık, yağ filtrelenmiyor.")
    if o.glycol > 50:
        add("crit", "oil_glycol", "Yağda soğutma suyu var (glikol)! Yataklar zarar görür.")

    # soğutma
    if th.boiling:
        add("crit", "coolant_boiling", "SOĞUTMA SUYU KAYNIYOR ({t:.0f} °C) — durun, motoru rölantide soğutun!", t=th.t_cool)
    elif th.t_cool > 110:
        add("crit", "overheat", "HARARET: {t:.0f} °C", t=th.t_cool)
    elif th.t_cool > 104:
        add("warn", "engine_hot", "Motor sıcaklığı yüksek: {t:.0f} °C", t=th.t_cool)
    if t.eng.p_ret > 50 and th.t_cool > 104:
        add("info", "retarder_heat", "Retarder hararet yapıyor: gerçek araçta retarder gücü bu sıcaklıkta düşürülür. Vites küçültüp motor freni kullanın.")
    if c.level_frac < 0.70:
        add("crit", "coolant_level_crit", "Soğutma suyu çok az (%{lvl:.0f}) — pompa kavitasyon yapıyor.", lvl=c.level_frac * 100)
    elif c.level_frac < 0.85:
        add("warn", "coolant_level_low", "Soğutma suyu seviyesi düşük (%{lvl:.0f}). Motor soğukken tamamlayın.", lvl=c.level_frac * 100)
    fp = c.freeze_point
    if amb < fp:
        add("crit", "freezing", "DONMA: hava {amb:.0f} °C, antifriz donma noktası {fp:.0f} °C!", amb=amb, fp=fp)
    elif expected_min < fp:
        add("warn", "antifreeze_low", "Antifriz yetersiz: donma noktası {fp:.0f} °C, bölgede beklenen en düşük {mn:.0f} °C.", fp=fp, mn=expected_min)
    if th.block_ice > 0.05 or th.rad_ice > 0.3:
        add("crit", "icing", "Soğutma sisteminde buzlanma (blok %{b:.0f}, radyatör %{r:.0f}).", b=th.block_ice * 100, r=th.rad_ice * 100)
    if c.inhibitor < 0.3:
        add("warn", "inhibitor", "Antifriz inhibitörü tükendi (%{i:.0f}): korozyon ve kireçlenme başladı.", i=c.inhibitor * 100)
    if c.scale > 0.25:
        add("info", "scale", "Radyatör/blok kireçlenmiş (%{s:.0f}): soğutma verimi düştü.", s=c.scale * 100)

    # akü
    if running and b.current < -5 and not t.faults.has("alternator"):
        add("info", "alternator_load", "Alternatör yükü karşılayamıyor (rölantide yüksek elektrik yükü).")
    if running and t.faults.has("alternator"):
        add("crit", "no_charge", "ŞARJ YOK: akü {v:.1f} V, %{soc:.0f}.", v=b.voltage, soc=b.soc * 100)
    if not running:
        visc = o.viscosity(th.t_oil)
        cv = b.crank_voltage(visc)
        if visc >= oil_mod.CRANK_LIMIT_CST:
            add("crit", "oil_too_thick", "Yağ bu soğukta çok koyu ({visc:,.0f} cSt): motor marşla dönmez. Daha ince yağ veya ısıtma gerekir.", visc=visc)
        elif cv < b.crank_min_v:
            add("crit", "crank_fail", "Akü bu koşulda motoru çeviremez (marşta ~{v:.1f} V). Şarj edin veya takviye yapın.", v=cv)
        elif cv < b.crank_slow_v:
            add("info", "crank_weak", "Zayıf marş bekleniyor (~{v:.1f} V).", v=cv)
        if f.electric_on and b.current < -5:
            h = b.hours_until(0.5, -b.current)
            if h is not None and h < 6:
                add("warn" if h < 2 else "info", "ignition_drain", "Kontak açık, {a:.0f} A çekiliyor: akü {h:.1f} saatte %50'ye iner.", a=-b.current, h=h)
        if b.soc < 0.5:
            add("warn", "battery_low", "Akü şarjı düşük (%{soc:.0f}). Sülfatlaşma riski.", soc=b.soc * 100)
    elif b.soc < 0.35:
        add("warn", "battery_low", "Akü şarjı düşük (%{soc:.0f}). Sülfatlaşma riski.", soc=b.soc * 100)
    if b.soh < 0.6:
        add("warn", "battery_health", "Akü sağlığı zayıf (%{soh:.0f}). Değişim önerilir.", soh=b.soh * 100)
    if amb < b.freeze_point + 3:
        add("warn", "battery_freeze", "Akü donma riski: bu şarjda elektrolit {fp:.0f} °C'de donar.", fp=b.freeze_point)

    # fren ve hava
    if f.brake_temp > 450:
        add("crit", "brakes_overheat", "FRENLER AŞIRI ISINDI ({t:.0f} °C) — fren gücü azaldı!", t=f.brake_temp)
    elif f.brake_temp > 320:
        add("warn", "brakes_hot", "Fren sıcaklığı yüksek ({t:.0f} °C): fren zayıflaması (fading) riski. Retarder ve motor frenini kullanın.", t=f.brake_temp)
    if f.air_warning and f.engine_on:
        add("crit" if f.air_emergency else "warn", "air_pressure", "Hava basıncı düşük ({p:.1f} bar): frenler kilitlenebilir.", p=f.air_bar)
    if fl.get("park_moving"):
        add("crit", "park_moving", "Park freni çekiliyken hareket ediliyor: frenler ısınır, balatalar yanar!")
    elif fl.get("park_warn"):
        add("warn", "park_not_set", "Park freni çekilmedi: motor kapalıyken tırı park frenine alın.")

    # direksiyon (hidrolik destek motordan; otomobilde elektrikli)
    if t.veh != "car":
        if not fl.get("steer_assist", True) and abs(f.speed_kmh) > 5 and not running:
            add("crit", "steer_no_assist", "Direksiyon hidrolik desteği yok (motor çalışmıyor): direksiyon çok ağır, yavaşlayıp güvenli bir yerde durun.")
        elif t.steer_fluid < 0.6:
            add("crit", "steer_fluid", "Direksiyon hidrolik yağı çok az (%{p:.0f}): destek azaldı, pompa zarar görüyor. Kaçağı onarın.",
                p=t.steer_fluid * 100)

    # şanzıman ve debriyaj
    tr = t.trans
    if tr.t_oil >= trans_mod.OIL_CRIT_C:
        add("crit", "gear_oil_crit", "ŞANZIMAN YAĞI AŞIRI SICAK ({t:.0f} °C): yükü azaltın, gerekirse durup motoru rölantide çalıştırarak soğutun!",
            t=tr.t_oil)
    elif tr.t_oil >= trans_mod.OIL_WARN_C:
        add("warn", "gear_oil_hot", "Şanzıman yağı sıcak ({t:.0f} °C): yükü ve retarder kullanımını azaltın.", t=tr.t_oil)
    if tr.t_clutch >= trans_mod.CLUTCH_CRIT_C:
        add("crit", "clutch_overheat", "DEBRİYAJ AŞIRI ISINDI ({t:.0f} °C): yarım debriyajla sürünmeyin; durun, motor rölantide debriyaj soğusun!",
            t=tr.t_clutch)
    elif tr.t_clutch >= trans_mod.CLUTCH_WARN_C:
        add("warn", "clutch_hot", "Debriyaj ısınıyor ({t:.0f} °C): kalkış ve manevraları azaltın, yarım debriyajla beklemeyin.", t=tr.t_clutch)
    if tr.clutch_wear >= 1.0:
        add("crit", "clutch_worn", "Debriyaj balatası bitti: yükte kayıyor. Debriyajı yenileyin.")
    elif tr.clutch_wear >= trans_mod.CLUTCH_WARN_WEAR:
        add("warn", "clutch_wear", "Debriyaj balatası %{w:.0f} aşındı: değişim yaklaşıyor.", w=tr.clutch_wear * 100)
    if tr.oil_used(t.veh) >= 1.0:
        add("warn", "gear_oil_change", "Şanzıman yağının değişim zamanı geldi ({km:,.0f} km).", km=tr.oil_km)

    # DPF
    if t.spec.has_dpf:
        if d.soot_frac >= 1.2:
            add("crit", "dpf_blocked", "DPF tıkalı (%{s:.0f}): gerçek araçta motor güç düşürür. Servis rejenerasyonu gerekli.", s=d.soot_frac * 100)
        elif d.soot_frac >= 1.0:
            add("warn", "dpf_full", "DPF dolu (%{s:.0f}). 40 km/h üstünde uzun sürüş yapın ya da servis rejenerasyonu yaptırın.", s=d.soot_frac * 100)
        if d.burning:
            add("info", "dpf_regen", "DPF aktif rejenerasyon yapıyor — motoru kapatmayın, sürüşe devam edin.")
        elif d.regen_active:
            add("info", "dpf_regen_wait", "DPF rejenerasyon bekliyor: 40 km/h üstünde sürüş gerekli.")
        if d.ash_frac > 0.85:
            add("warn", "dpf_ash", "DPF kül doluluğu %{a:.0f}: filtre temizliği gerekli.", a=d.ash_frac * 100)

    # ön ısıtma (kızdırma)
    if t.preheat.active:
        add("info", "preheat", "Ön ısıtma yapılıyor: lamba sönünce marşa basın (~{s:.0f} sn).", s=t.preheat.remaining_s)

    # yakıt, AdBlue, lastikler
    if f.fuel_cap > 0:
        pct = f.fuel_l / f.fuel_cap * 100
        if pct < 5:
            add("crit", "fuel_crit", "Yakıt bitmek üzere (%{p:.0f}, {l:.0f} L). Hemen yakıt alın.", p=pct, l=f.fuel_l)
        elif pct < max(15.0, f.fuel_warn_factor * 100):
            add("warn", "fuel_low", "Yakıt azaldı (%{p:.0f}, {l:.0f} L).", p=pct, l=f.fuel_l)
    if has_scr(t.spec, f):
        ab = t.adblue.frac * 100
        if ab <= 0:
            add("crit", "adblue_empty", "AdBlue bitti: gerçek araçta motor gücü düşürülür, yeniden çalıştırmada hız 20 km/h ile sınırlanır.")
        elif ab < 5:
            add("crit", "adblue_crit", "AdBlue bitmek üzere (%{p:.0f}). Yakıtla birlikte AdBlue alın.", p=ab)
        elif ab < 10:
            add("warn", "adblue_low", "AdBlue azaldı (%{p:.0f}).", p=ab)
        if amb < ADBLUE_FREEZE_C and not running:
            add("info", "adblue_freeze", "AdBlue {t:.0f} °C'de donar: motor çalışınca depo ısıtıcısı çözer, ilk dakikalarda püskürtme gecikir.",
                t=ADBLUE_FREEZE_C)
    for g, s in t.tires.groups.items():
        if s.get("lifted"):
            continue
        name = GROUP_NAMES[g]
        ratio = s["cold_bar"] / s["nominal"] if s["nominal"] else 1.0
        if s["blown"]:
            add("crit", "tire_blown", "LASTİK PATLADI ({grp_t})! Hemen güvenli bir yerde durun.", _sub=g, grp_t=name)
            continue
        if ratio < 0.75:
            add("crit", "tire_pressure_crit", "Lastik basıncı çok düşük: {grp_t} {p:.1f} bar (olması gereken {n:.1f}). Isınıp patlayabilir.",
                _sub=g, grp_t=name, p=s["cold_bar"], n=s["nominal"])
        elif s["leak_bph"] > 0:
            add("warn", "tire_leak", "Yavaş patlak: {grp_t} lastiği hava kaçırıyor ({p:.1f} bar).", _sub=g, grp_t=name, p=s["cold_bar"])
        elif ratio < 0.88:
            add("warn", "tire_pressure_low", "Lastik basıncı düşük: {grp_t} {p:.1f} bar (olması gereken {n:.1f}).",
                _sub=g, grp_t=name, p=s["cold_bar"], n=s["nominal"])
        if s["tread"] < TIRE_LEGAL_MM:
            add("crit", "tread_legal", "Lastik dişi yasal sınırın altında: {grp_t} {mm:.1f} mm. Lastikleri değiştirin.", _sub=g, grp_t=name,
                mm=s["tread"])
        elif s["tread"] < TIRE_WARN_MM[g]:
            add("warn", "tread_low", "Lastik dişi azaldı: {grp_t} {mm:.1f} mm. Değişim yaklaşıyor.", _sub=g, grp_t=name, mm=s["tread"])
        if s["temp"] > 115:
            add("crit", "tire_overheat", "Lastikler aşırı ısındı ({grp_t} {t:.0f} °C): yavaşlayın, basıncı kontrol edin.", _sub=g, grp_t=name,
                t=s["temp"])
        elif s["temp"] > 95:
            add("warn", "tire_hot", "Lastikler ısınıyor ({grp_t} {t:.0f} °C).", _sub=g, grp_t=name, t=s["temp"])

    # sürüş ve sürücü
    if fl["cold_load"]:
        add("info", "cold_load", "Soğuk motora yüklenme (yağ {t:.0f} °C): aşınma 3 kat.", t=th.t_oil)
    if fl["lugging"]:
        add("info", "lugging", "Düşük devirde tam yük (lugging): vites küçültün.")
    if fl["overrev"]:
        add("warn", "overrev", "Aşırı devir!")
    if t.idle_min > 15:
        add("info", "idling", "{m:.0f} dk'dır rölantide: yakıt, is ve yakıt seyrelmesi.", m=t.idle_min)
    if t.health.health < 40:
        add("warn", "engine_health", "Motor sağlığı %{h:.0f}: revizyon yaklaşıyor (yağ yakma, düşük basınç).", h=t.health.health)
    w.sort(key=lambda x: LEVEL_ORDER[x["level"]])
    return w


def filter_warnings(ws, level):
    """Uyarı düzeyi ayarı: minimal = yalnızca kritik, normal = kritik + dikkat, all = hepsi."""
    allowed = {"minimal": ("crit",), "normal": ("crit", "warn")}.get(level, ("crit", "warn", "info"))
    return [w for w in ws if w["level"] in allowed]


# ---------------------------------------------------------------- bakım planı tahmini
def forecast(t, analysis, R=None):
    """Bir sonraki bakımlara kalan tahmini km / gün. R: azalma hızı çarpanları; kalan ömür çarpanlı (etkin) km/gün
    olarak hesaplanır ve şimdiki hızla gerçek km/güne çevrilir (hız 0 ise sınırsız)."""
    o, c, b, d = t.oil, t.coolant, t.battery, t.dpf
    R = R or {}
    items = []

    def real(v, key):
        rr = R.get(key, 1.0)
        return None if v is None or rr <= 0 else v / rr

    def item(name, km=None, days=None):
        lvl = "g"
        if km is not None:
            lvl = "c" if km <= 0 else "w" if km < 5000 else "g"
        if days is not None:
            lvl = max(lvl, "c" if days <= 0 else "w" if days < 30 else "g", key="gwc".index)
        items.append({"name": name, "km": None if km is None else max(0.0, km),
                      "days": None if days is None else max(0.0, days), "lvl": lvl})

    life, _ = o.life()
    eff_km = life * o.wear_km / (1 - life) if o.wear_km > 300 and life < 1 else life * o.spec["interval_km"]
    days_oil = (1 - o.wear_min / (oil_mod.INTERVAL_DAYS * 1440.0)) * oil_mod.INTERVAL_DAYS
    item("Yağ değişimi", real(eff_km, "oil"), real(days_oil, "oil"))
    item("Yağ filtresi", real((1 - min(1.0, o.filter_load)) * oil_mod.FILTER_KM / (1 + o.soot / 3.0), "oil"))
    inh = max(0.0, c.inhibitor - 0.3)
    item("Soğutma sıvısı değişimi", real(inh * c.spec["life_km"], "coolant"), real(inh * c.spec["life_days"], "coolant"))
    if t.spec.has_dpf:
        oil_per_km = o.consumed_l / o.km if o.km > 300 else 0.00015 * R.get("oil", 1.0)
        ash_per_km = oil_per_km * 880.0 * o.ash_pct / 100.0 * 0.9 * R.get("dpf", 1.0)
        item("DPF kül temizliği", (0.85 * DPF.ASH_CAP - d.ash_g) / ash_per_km if ash_per_km > 0 else None)
    item("Akü değişimi", None, real((b.soh - 0.6) / 0.06 * 365, "battery") if b.soh > 0.6 else 0.0)
    tr = t.trans
    if tr.ready:
        iv = trans_mod.OIL_INTERVAL_KM[t.veh]
        item("Şanzıman yağı", real(iv - tr.oil_wear_km, "transmission"))
        item("Debriyaj", tr.clutch_left_km(t.veh, R.get("transmission", 1.0)))
    km_per_h = analysis.distance_km / analysis.engine_h if analysis.engine_h > 1 else 70.0
    per_h = EngineHealth.BASE_PER_H * max(0.2, t.health.wear_rate_ema)
    item("Motor revizyonu", (real((t.health.health - 20) / per_h * km_per_h, "engine") if R.get("engine", 1.0) > 0 else None)
         if t.health.health > 20 else 0.0)
    items.sort(key=lambda x: (x["km"] if x["km"] is not None else 1e12, x["days"] if x["days"] is not None else 1e12))
    per_1000 = t.costs_total / analysis.distance_km * 1000 if analysis.distance_km > 100 else None
    return {"items": items, "cost_per_1000": per_1000}


FORECAST_NAMES = {
    "Yağ değişimi": ("Oil change", "Ölwechsel"), "Yağ filtresi": ("Oil filter", "Ölfilter"),
    "Soğutma sıvısı değişimi": ("Coolant change", "Kühlmittelwechsel"), "DPF kül temizliği": ("DPF ash cleaning", "DPF-Ascheabreinigung"),
    "Akü değişimi": ("Battery replacement", "Batterietausch"), "Motor revizyonu": ("Engine overhaul", "Motorüberholung"),
    "Şanzıman yağı": ("Gearbox oil", "Getriebeöl"), "Debriyaj": ("Clutch", "Kupplung"),
}
i18n.TRANS.update(FORECAST_NAMES)


def trip_view(t, f, settings):
    s = t.trip.summary()
    ti = t.trip_info
    price = float(settings.get("fuel_price", 1.65))
    dur = (f.game_minutes - ti["start_gm"]) if ti.get("start_gm") is not None else None
    s.update(src=i18n.city(ti.get("src") or ""), dst=i18n.city(ti.get("dst") or ""), cargo=ti.get("cargo") or "",
             duration_min=dur,
             fuel_cost=s["fuel_l"] * price, idle_cost=s["idle_fuel_l"] * price, fuel_price=price)
    return s


def report_view(rep):
    """Laboratuvar raporunu seçili dile çevirir (eski biçimli raporlar da desteklenir)."""
    if not rep:
        return None
    out = dict(rep)
    out["time"] = fmt_minutes(rep.get("game_minutes", 0))
    out["grade"] = T(rep.get("grade", ""))
    out["limiting"] = T(rep.get("limiting", ""))
    rows = []
    for row in rep.get("rows", []):
        if len(row) == 6:
            name, val, dec, unit, st, txt = row
            value = T(txt) if txt else f"{i18n.N(val, dec)} {unit}".strip()
        else:
            name, value, st = row
        rows.append([T(name), value, st, T(st)])
    out["rows"] = rows
    out["notes"] = [T(n) for n in rep.get("notes", [])]
    return out


def build_state(app, t, f):
    th, o, c, b, d, e = t.thermal, t.oil, t.coolant, t.battery, t.dpf, t.eng
    amb = app.ambient
    R = rates_mod.all_rates(app.settings)
    life, lim = o.life()
    visc_now = o.viscosity(th.t_oil)
    speed = abs(f.speed_kmh)
    l100 = (e.fuel_lph / speed * 100) if (t.flags["running"] and speed > 5) else None
    torque = e.p_brake * 1000 / (e.rpm * 2 * 3.14159 / 60) if e.rpm > 100 else 0.0
    exp_min = app.expected_min
    ms = b.min_start_soc(visc_now)
    load_a = t.flags["load_a"]
    ws = (f.wiper_stage if f.wiper_stage > OFF else SLOW) if f.wipers else OFF
    wiper_a = wiper_current_a(ws, amb) if f.wipers and f.electric_on else 0.0
    wiper_text = (T("silecek {s_t} · {a:.1f} A", s_t=STAGE_NAMES[ws], a=wiper_a) if f.wipers
                  else T("silecek {s_t}", s_t=STAGE_NAMES[OFF]))
    all_w = warnings(t, f, amb, exp_min)
    level = app.settings.get("alert_level", "normal")
    shown_w = alerts.visible(filter_warnings(all_w, level), app.settings)   # uyarı düzeyi + Ayarlar'da kapatılanlar
    # yakıt / AdBlue menzili: kamyonun ölçülen uzun dönem tüketiminden (yoksa oyunun tahmini)
    an = t.analysis
    avg_l100 = an.fuel_l / an.distance_km * 100 if an.distance_km > 50 and an.fuel_l > 0 else None
    fuel_range = f.fuel_l / avg_l100 * 100 if avg_l100 else (f.fuel_range_km or None)
    scr, ab = has_scr(t.spec, f), t.adblue
    ab_range = ab.level_l / (avg_l100 / 100 * 0.05) if scr and avg_l100 else None
    tsum = t.tires.summary()
    tire_groups = []
    for g in TIRE_GROUPS:
        s = t.tires.groups.get(g)
        if not s:
            continue
        span = max(0.1, s["new"] - TIRE_LEGAL_MM)
        tire_groups.append({
            "key": g, "name": T(GROUP_NAMES[g]), "tires": s["tires"], "wheels": s.get("wheels", 2), "lifted": s["lifted"],
            "tread": r(s["tread"], 1), "new": s["new"], "warn_mm": TIRE_WARN_MM[g], "legal_mm": TIRE_LEGAL_MM,
            "tread_pct": r(clamp((s["tread"] - TIRE_LEGAL_MM) / span * 100, 0, 100), 0),
            "cold_bar": r(s["cold_bar"], 2), "hot_bar": r(Tires.hot_bar(s), 2), "nominal": s["nominal"],
            "temp": r(s["temp"], 0), "km": r(s["km"], 0), "leak": s["leak_bph"] > 0, "blown": s["blown"],
            "lv": tire_group_levels(g, s), "replace_cost": r(t.tires.replace_cost(g), 0),
            "tier": s.get("tier", "premium"), "tier_name": T(tier_of(s)["name"]), "unit_price": TIRE_PRICE[g]})
    reports = dict(t.reports)
    reports["oil"] = report_view(t.reports.get("oil"))
    for k in ("coolant", "battery"):
        if reports.get(k) and "gm" in reports[k]:
            reports[k] = dict(reports[k], time=fmt_minutes(reports[k]["gm"]))
    log = []
    for ev in reversed(t.log[-80:]):
        text = render({"m": ev["m"], "a": ev.get("a") or {}}) if "m" in ev else ev.get("text", "")
        log.append({"gm": ev.get("gm", 0), "time": fmt_minutes(ev.get("gm", 0)), "odo": ev.get("odo"),
                    "level": ev.get("level", "info"), "text": text, "cost": ev.get("cost", 0), "kind": ev.get("kind"),
                    "manual": bool(ev.get("manual"))})   # Ayarlar → Çekim modu ile elle yapıldı
    state = {
        "status": {
            "source": app.source_name, "text": render(app.source.status), "connected": f.ok,
            "paused": f.paused, "time": fmt_minutes(f.game_minutes), "scale": r(f.scale, 1),
            "settings": app.settings, "message": app.last_message, "lang": i18n.LANG,
        },
        "truck": {"key": t.key, "brand": f.brand, "name": f.name, "plate": f.plate,
                  "odometer": r(f.odometer_km, 1), "spec": dict(t.spec.__dict__, name=T(t.spec.name)),
                  "cargo_t": r(f.cargo_kg / 1000.0, 1), "temporary": t.temporary,
                  "vehicle": t.veh, "vehicle_name": T(vehicles.NAMES[t.veh]),
                  # Ayarlar → Araç tipi: seçim (auto | truck | bus | car) ve modelden algılanan sınıf
                  "vehicle_choice": t.spec.vehicle_override if t.spec.vehicle_override in vehicles.CHOICES else "auto",
                  "vehicle_detected": t.spec.vehicle if t.spec.vehicle in vehicles.KINDS else "truck",
                  "spec_limits": vehicles.spec_limits(t.veh)},   # Ayarlar'daki kamyon özellikleri formunun sınırları
        "location": {"lat": r(app.lat, 3), "lon": r(app.lon, 3), "city": i18n.city(app.city), "city_km": r(app.city_km, 0),
                     "ambient": r(amb, 1), "expected_min": r(exp_min, 0), "wipers": f.wipers},
        "live": {
            "engine_on": f.engine_on, "running": t.flags["running"], "killed": t.killed,
            "electric_on": f.electric_on, "rpm": r(e.rpm, 0), "rpm_max": r(f.rpm_max, 0), "load": r(e.load * 100, 0),
            "speed": r(speed, 0), "gear": f.gear, "power_kw": r(e.p_brake, 0), "torque_nm": r(torque, 0),
            "nav_km": r(f.nav_km, 0), "nav_min": r(f.nav_min, 0), "speed_limit": r(f.speed_limit, 0),
            "city_dst": i18n.city(f.city_dst) if f.city_dst else "", "cargo": f.cargo,
            "fuel_lph": r(e.fuel_lph, 1), "l100": r(l100, 1), "fuel_source": e.fuel_source,
            "exh": r(e.exh_temp, 0), "retarder_kw": r(e.p_ret, 0), "engine_brake_kw": r(e.p_eb, 0),
            "fuel_l": r(f.fuel_l, 0), "fuel_cap": r(f.fuel_cap, 0), "cruise": f.cruise,
            "idle_min": r(t.idle_min, 0), "brake_temp": r(f.brake_temp, 0), "air_bar": r(f.air_bar, 1),
            "air_warning": f.air_warning, "air_emergency": f.air_emergency, "mass_t": r(f.mass_kg / 1000.0, 1),
            "park_brake": f.park_brake, "park_warn": t.flags.get("park_warn", False),
            "park_moving": t.flags.get("park_moving", False),
        },
        "trans": trans_view(t, f, R),
        "steering": {"hydraulic": t.veh != "car", "fluid": r(t.steer_fluid * 100, 0),
                     "assist": bool(t.flags.get("steer_assist", True)), "leak": t.faults.has("steering_leak")},
        "thermal": {"t_cool": r(th.t_cool), "t_oil": r(th.t_oil), "thermostat": r(th.thermostat_open * 100, 0),
                    "fan": th.fan_on and not t.faults.has("fan_clutch"), "pressure": r(th.sys_pressure, 2),
                    "boil_point": r(c.boil_point(th.sys_pressure), 0), "boiling": th.boiling,
                    "block_ice": r(th.block_ice * 100, 0), "rad_ice": r(th.rad_ice * 100, 0)},
        "oil": {"grade": o.grade, "grade_name": T(o.spec["name"]), "level_pct": r(o.level_frac * 100, 0),
                "volume": r(o.volume_l, 1), "capacity": r(o.capacity_l, 0), "min_pct": r(o.min_frac * 100, 0),
                "pressure": r(t.oil_pressure, 2), "low_thr": r(o.low_pressure_threshold(e.rpm), 2),
                "visc_now": r(visc_now, 0), "visc100": r(o.viscosity(100.0), 1), "visc_chg": r(o.v100_change_pct(), 1),
                "life": r(life * 100, 0), "limiting": T(lim),
                "breakdown": {T(k): r(v * 100, 0) for k, v in o.life_breakdown().items()},
                "km": r(o.km, 0), "hours": r(o.hours, 0), "interval_km": r(rates_mod.interval_end(o.km, o.wear_km, o.spec["interval_km"], R["oil"]), 0),
                "interval_used": r(o.wear_km / o.spec["interval_km"] * 100, 0),
                "tbn": r(o.tbn, 1), "tbn_ref": r(o.tbn_ref, 1), "soot": r(o.soot, 2), "ox": r(o.ox, 1),
                "fuel_dil": r(o.fuel_dil, 2), "water": r(o.water, 0), "fe": r(o.fe, 0),
                "filter_pct": r(clamp(o.filter_load, 0, 1.5) * 100, 0), "consumed": r(o.consumed_l, 1),
                "consumption_l_1000": r(o.consumed_l / o.km * 1000, 2) if o.km > 200 else None},
        "coolant": {"type": c.type, "type_name": T(c.spec["name"]), "level_pct": r(c.level_frac * 100, 0),
                    "volume": r(c.volume_l, 1), "capacity": r(c.capacity_l, 0), "glycol": r(c.glycol * 100, 0),
                    "freeze": r(c.freeze_point, 0), "ph": r(c.ph, 2), "inhibitor": r(c.inhibitor * 100, 0),
                    "scale": r(c.scale * 100, 0), "age_days": r(c.minutes_age / 1440.0, 0),
                    "km": r(c.km, 0),
                    "life_days": r(rates_mod.interval_end(c.minutes_age / 1440.0, c.wear_min / 1440.0, c.spec["life_days"],
                                                          R["coolant"]), 0),
                    "life_km": r(rates_mod.interval_end(c.km, c.wear_km, c.spec["life_km"], R["coolant"]), 0),
                    "age_used": r(c.wear_min / 1440.0 / c.spec["life_days"] * 100, 0),
                    "km_used": r(c.wear_km / c.spec["life_km"] * 100, 0)},
        "battery": {"voltage": r(b.voltage, 2), "soc": r(b.soc * 100, 0), "soh": r(b.soh * 100, 0),
                    "volts": b.volts, "system": T("2 x 12 V seri, 24 V sistem") if b.blocks == 2 else T("12 V, tek akü"),
                    "current": r(b.current, 1), "load_a": r(load_a, 1), "alt_a": r(b.alt_current, 0),
                    "wiper_stage": ws, "wiper_a": r(wiper_a, 1), "wiper": wiper_text,
                    "temp": r(b.temp, 0), "capacity": r(b.capacity_ah, 0), "usable_ah": r(b.usable_ah, 0),
                    "sulfation": r(b.sulfation * 100, 1), "efc": r(b.efc, 1), "crank_v": r(b.crank_voltage(visc_now), 1),
                    "min_start_soc": r(ms * 100, 0) if ms is not None else None, "freeze": r(b.freeze_point, 0),
                    "charger": b.charger, "jump": b.jump, "frozen": b.frozen,
                    "kind": b.kind, "kind_name": T(b.k["name"]),
                    "hours_to_50": r(b.hours_until(0.5, -b.current * R["drain"]), 1) if b.current < -0.5 else None},
        "preheat": preheat_view(t, f),
        "fuel": {"l": r(f.fuel_l, 0), "cap": r(f.fuel_cap, 0),
                 "pct": r(f.fuel_l / f.fuel_cap * 100, 0) if f.fuel_cap > 0 else None,
                 "range_km": r(fuel_range, 0), "l100_avg": r(avg_l100, 1), "warn_pct": r(f.fuel_warn_factor * 100, 0),
                 "game_warning": f.fuel_warning},
        "adblue": {"enabled": scr, "l": r(ab.level_l, 1), "cap": r(ab.capacity_l, 0), "pct": r(ab.frac * 100, 0),
                   "rate_pct": r(ab.dosing_rate(e.load) * 100, 1), "range_km": r(ab_range, 0), "source": ab.source,
                   "used_l": r(ab.used_total_l, 1), "price_l": ADBLUE_PRICE_L,
                   "fill_cost": r((ab.capacity_l - ab.level_l) * ADBLUE_PRICE_L, 0)},
        "tires": {"groups": tire_groups, "min_tread": r(tsum["min_tread"], 1),
                  "min_tread_axle": T(GROUP_NAMES[tsum["min_tread_g"]]) if tsum["min_tread_g"] else "",
                  "min_pressure_pct": r(tsum["min_ratio"] * 100, 0) if tsum["min_ratio"] is not None else None,
                  "max_temp": r(tsum["max_temp"], 0), "leak": tsum["leak"], "blown": tsum["blown"],
                  "game_wear": r(f.wear.get("wheels", 0.0) * 100, 1),
                  "replace_all_cost": r(t.tires.replace_cost("all"), 0)},
        "dpf": {"enabled": t.spec.has_dpf, "soot": r(d.soot_frac * 100, 0), "ash": r(d.ash_frac * 100, 0),
                "regen": d.regen_active, "burning": d.burning, "count": d.regen_count,
                "km_since": r(d.km_since_regen, 0), "backpressure": r(d.backpressure_kpa, 0)},
        "engine": {"health": r(t.health.health, 1), "wear_rate": r(t.health.wear_rate_ema, 2),
                   "game_wear": {k: r(v * 100, 1) for k, v in f.wear.items()},
                   "hg_stress": r(t.health.head_gasket_stress * 100, 0), "seize_stress": r(t.health.seize_stress * 100, 0)},
        "engine_db": engine_db(t),
        "faults": [{"key": k, "name": T(FAULTS[k]["name"]), "desc": T(FAULTS[k]["desc"]), "cost": prices.fault(k, t.veh)}
                   for k in t.faults.active],
        "warnings": shown_w,
        "warnings_hidden": len(all_w) - len(shown_w),
        "log": log,
        "reports": reports,
        "costs_total": r(t.costs_total, 0),
        "rates": {k: r(v, 2) for k, v in R.items()},
        "options": {
            "oil_grades": [{"id": k, "name": T(v["name"]), "price": v["price"]} for k, v in oil_mod.grades_for(t.veh).items()],
            "battery_kinds": [{"id": k, "name": T(v["name"]),
                               "costs": {str(ah): r(battery_replace_cost(ah, k, b.volts), 0)
                                         for ah in vehicles.battery_sizes(t.veh)}}
                              for k, v in BATTERY_KINDS.items()],
            "battery_sizes": list(vehicles.battery_sizes(t.veh)),
            # kaplama lastik otomobile takılmaz (tırda yalnız arka dingiller)
            "tire_tiers": [{"id": k, "name": T(v["name"]), "price": v["price"], "rear_only": v["rear_only"]}
                           for k, v in TIRE_TIERS.items() if not (v["rear_only"] and t.veh == "car")],
            "tire_mount": prices.v("TIRE_MOUNT", t.veh),
            "overhaul_cost": prices.v("OVERHAUL", t.veh),   # onay penceresi (para birimine çevrilir)
            "coolant_types": [{"id": k, "name": T(v["name"])} for k, v in coolant_mod.TYPES.items()],
            "fluids": [{"id": k, "name": T(v["name"])} for k, v in coolant_mod.FLUIDS.items()],
        },
    }
    state["levels"] = value_levels(state)  # her değerin rengi: normal / sınırda (sarı) / kritik (kırmızı)
    state["diag"] = diagnosis(t, state)
    return state


def trans_view(t, f, R):
    """Şanzıman yağı, debriyaj ve şanzıman yağı aralığı (aralık, azalma hızına göre gerçek km)."""
    tr, veh = t.trans, t.veh
    iv = trans_mod.OIL_INTERVAL_KM[veh]
    end = rates_mod.interval_end(tr.oil_km, tr.oil_wear_km, iv, R["transmission"])
    left = tr.clutch_left_km(veh, R["transmission"])
    return {"t_oil": r(tr.t_oil, 0), "t_clutch": r(tr.t_clutch, 0), "slip_kw": r(tr.slip_kw, 0),
            "clutch_wear": r(tr.clutch_wear * 100, 0), "clutch_left_km": None if left is None else round(left, -2),
            "oil_km": r(tr.oil_km, 0), "oil_interval_km": None if end is None else round(end, -2),   # 100 km'ye yuvarlı
            "oil_used": r(tr.oil_used(veh) * 100, 0), "game_wear": r(f.wear.get("transmission", 0.0) * 100, 1),
            "retarder": f.retarder_steps > 0, "oil_l": trans_mod.OIL_L[veh],
            "oil_cost": prices.v("GEARBOX_OIL", veh), "clutch_cost": prices.v("CLUTCH", veh)}


def preheat_view(t, f):
    """Ön ısıtma durumu: gerekli mi, ısıtıyor mu (kalan sn), hazır mı, arızalı mı."""
    p, t_eng = t.preheat, t.thermal.t_cool
    need = t.spec.fuel == "diesel" and preheat_duration_s(t_eng) > 0   # benzinli motorda ön ısıtma yok
    fault = t.faults.has("preheater")
    if fault and need:
        text = T("ARIZALI: soğukta ısıtmıyor")
    elif not f.electric_on:
        text = T("Kontak kapalı")
    elif f.engine_on or not need:
        text = T("Gerekmiyor (motor {t} °C)", t=f"{t_eng:.0f}")
    elif p.active:
        text = T("Isıtıyor, {s} sn kaldı", s=f"{p.remaining_s:.0f}")
    else:
        text = T("Hazır: marşa basabilirsiniz")
    return {"needed": need, "active": p.active, "remaining_s": r(p.remaining_s, 0), "ready": p.ready,
            "fault": fault, "text": text}


def _shown_torque(t, model):
    """Gösterilen tepe tork: otomobilde gerçek değer (model oyun içi devir ölçeğinde türetilmiş torku kullanır)."""
    if t.veh == "car":
        e = engines.engine_by_id(model, t.spec.engine_id) if model else None
        if e:
            return e["nm"]
        if t.spec.real_torque_nm > 0:   # elle girilen motor
            return t.spec.real_torque_nm
    return t.spec.peak_torque_nm()


def engine_db(t):
    sp = t.spec
    m = engines.model_by_key(sp.model_key)
    best, est, confident = t.detector.suggest(m)
    return {
        "mode": sp.mode, "model_key": sp.model_key, "model_name": T(sp.model_name) if m else None,
        "electric": sp.electric, "engine_id": sp.engine_id,
        # genel motor listesinin adları (ör. "2.0 dizel 150 hp") seçili dilde
        "lineup": [dict(e, label=T(e["label"])) for e in engines.lineup(m)] if m else [],
        "hp": r(sp.power_kw / 0.7355, 0), "torque": r(_shown_torque(t, m), 0),
        "detect": {"samples": len(t.detector.samples), "need": t.detector.MIN_SAMPLES, "torque": r(est, 0),
                   "suggest_id": best["id"] if best else None, "suggest_label": T(best["label"]) if best else None,
                   "confident": confident},
    }


def diagnosis(t, s):
    """Arıza tespiti (Motor Analizi; Grand Truck Simulator 2'deki "Diagnosis" gibi): motor bilgileri, parça durumu ve
    seviyeler. Ana bileşenlerin yüzdesi kendi modelinden, diğer parçalarınki yaşa bağlı güvenilirlikten
    (faults.Faults.condition); arızalı parça 0. Değiştirilebilen parçaların ücreti Servis'teki onarımla aynıdır."""
    sp, b, skip = t.spec, t.battery, t.fault_skip()

    def row(pid, name, pct, cost=None, failed=False):
        pct = max(0.0, min(100.0, pct))
        return {"id": pid, "name": T(name), "pct": r(pct, 0), "failed": failed, "cost": cost,
                "lvl": "c" if failed or pct < 15 else "w" if pct < 40 else "g"}

    core = [row("engine", "Motor", s["engine"]["health"]), row("oil", "Yağ", s["oil"]["life"]),
            row("coolant", "Soğutma suyu", 100 - max(s["coolant"]["age_used"], s["coolant"]["km_used"])),
            row("battery", "Akü", s["battery"]["soh"])]
    if s["dpf"]["enabled"]:
        core.append(row("dpf", "DPF (kül)", 100 - s["dpf"]["ash"]))
    core.append(row("clutch", "Debriyaj balatası", (1 - t.trans.clutch_wear) * 100))
    groups = [{"name": T("Ana bileşenler"), "parts": core}]
    for gname, parts in PART_GROUPS:
        groups.append({"name": T(gname), "parts": [
            row(pid, name, t.faults.condition(keys) * 100, prices.fault(keys[0], t.veh), any(t.faults.has(k) for k in keys))
            for pid, name, keys in parts if not any(k in skip for k in keys)]})
    kind = BATTERY_KINDS.get(b.kind, BATTERY_KINDS["std"])
    specs = [{"name": T("Motor"), "text": T(sp.name)},
             {"name": T("Yakıt türü"), "text": T("Benzinli" if sp.fuel == "petrol" else "Dizel")},
             {"name": T("Silindir hacmi"), "value": sp.displacement_l, "digits": 1, "unit": "L"},
             {"name": T("Güç"), "value": round(sp.power_kw / 0.7355), "unit": "hp"},
             {"name": T("Tork"), "value": round(sp.peak_torque_nm()), "unit": "Nm"},
             {"name": T("Devir"), "value": sp.rated_rpm, "unit": "rpm"},
             {"name": T("Yağ"), "text": s["oil"]["grade_name"]},
             {"name": T("Antifriz"), "text": s["coolant"]["type_name"]},
             {"name": T("Akü"), "text": f"{'2 x ' if b.volts > 12 else ''}{round(b.capacity_ah)} Ah · {T(kind['name'])}"}]
    levels = [{"name": T("Motor yağı"), "value": s["oil"]["volume"], "cap": s["oil"]["capacity"], "pct": s["oil"]["level_pct"]},
              {"name": T("Soğutma suyu"), "value": s["coolant"]["volume"], "cap": s["coolant"]["capacity"],
               "pct": s["coolant"]["level_pct"]}]
    if s["adblue"]["enabled"]:
        levels.append({"name": T("AdBlue"), "value": s["adblue"]["l"], "cap": s["adblue"]["cap"], "pct": s["adblue"]["pct"]})
    if s["steering"]["hydraulic"]:
        levels.append({"name": T("Direksiyon yağı"), "pct": s["steering"]["fluid"]})
    if s["fuel"]["cap"]:
        levels.append({"name": T("Yakıt"), "value": s["fuel"]["l"], "cap": s["fuel"]["cap"],
                       "pct": r(s["fuel"]["l"] / s["fuel"]["cap"] * 100, 0)})
    return {"specs": specs, "groups": groups, "levels": levels}


def build_detail(t, f=None, settings=None):
    fc = forecast(t, t.analysis, rates_mod.all_rates(settings or {}))
    for it in fc["items"]:
        it["label"] = T(it["name"])
    session = t.session.summary()
    return {"analysis": t.analysis.summary(), "session": session, "session_levels": session_levels(session),
            "trend": t.trend, "trip": trip_view(t, f, settings or {}) if f is not None else None, "forecast": fc}
