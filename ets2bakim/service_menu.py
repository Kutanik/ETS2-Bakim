"""Oyun içi katmanın servis menüsü (Alt+F8): maddeler, fiyatlar ve uygunluk kontrolleri.

Her madde: key (seçim için sabit anahtar), cmd ("işlem?anahtar=değer&..."), label, detail,
flag (h = başlık, d = şu an yapılamaz [detail nedeni söyler], c = onay ister, n = normal).
Komut katmandan geri geldiğinde parse_command() ile TruckModel.action() parametrelerine çevrilir.
"""
from urllib.parse import parse_qsl, urlencode

from . import coolant as coolant_mod
from . import currency
from . import oil as oil_mod
from . import prices
from .adblue import PRICE_L as ADBLUE_PRICE_L, has_scr
from .battery import KINDS, replace_cost as battery_replace_cost
from .faults import FAULTS
from .i18n import N, T
from .tires import GROUP_NAMES, GROUPS as TIRE_GROUPS, TIERS, puncture_price, tier_allowed
from .transmission import OIL_L

# katmandan gelebilecek işlemler (başka bir şey kabul edilmez)
ALLOWED = {"oil_topup", "oil_change", "oil_filter", "oil_sample", "coolant_topup", "coolant_change", "coolant_test",
           "battery_charger", "jump_start", "battery_test", "battery_replace", "dpf_regen", "dpf_clean", "repair",
           "overhaul", "adblue_fill", "tire_inflate", "tire_puncture", "tire_replace", "gearbox_oil", "clutch_replace"}


def _cmd(name, **params):
    return name + ("?" + urlencode(params) if params else "")


def parse_command(cmd):
    """'oil_topup?grade=10w40&liters=1.5' -> ('oil_topup', {'grade': '10w40', 'liters': 1.5}); geçersizse (None, None)."""
    name, _, query = (cmd or "").partition("?")
    if name not in ALLOWED:
        return None, None
    params = {}
    for k, v in parse_qsl(query):
        if k in ("filter", "on"):
            params[k] = v not in ("0", "false", "")
        else:
            try:
                params[k] = float(v)
            except ValueError:
                params[k] = v
    return name, params


def _short_grade(gid):
    return T(oil_mod.GRADES[gid]["name"]).split(" (")[0]


def build(t, f, settings, cur=None):
    """Dönüş: (maddeler, (ipucu metni, seviye)). cur: currency.CurrencyMonitor.get() (yoksa avro)."""
    cur = cur or {"symbol": "€", "rate": 1.0}
    money = lambda v: currency.fmt(v, cur)
    stationary = abs(f.speed_kmh) < 1.0
    engine_off = not f.engine_on
    ready = stationary and engine_off
    not_ready = T("Tır durmalı ve motor kapalı olmalı")
    items = []

    def head(key, label):
        items.append(dict(key=key, cmd="", label=label, detail="", flag="h"))

    def item(key, cmd, label, detail="", need_ready=True, confirm=False, block=None):
        flag = "c" if confirm else "n"
        if need_ready and not ready:
            flag, detail = "d", not_ready
        elif block:
            flag, detail = "d", block
        items.append(dict(key=key, cmd=cmd, label=label, detail=detail, flag=flag))

    stop_first = None if stationary else T("Önce tırı durdurun")

    # ---- yağ
    veh = t.veh
    o = t.oil
    g = o.grade if o.grade in oil_mod.GRADES else "10w40"
    price = oil_mod.GRADES[g]["price"]
    head("h_oil", T("YAĞ · {v} / {c} L · ömür %{life}", v=N(o.volume_l, 1), c=N(o.capacity_l), life=N(o.life()[0] * 100)))
    item("oil_add1", _cmd("oil_topup", grade=g, liters=1), T("1 L yağ ekle ({grade})", grade=_short_grade(g)), money(price))
    need = round(max(0.0, o.capacity_l - o.volume_l), 1)
    if need >= 0.3:
        item("oil_fill", _cmd("oil_topup", grade=g, liters=need), T("Yağı MAX'a tamamla (+{l} L)", l=N(need, 1)),
             money(need * price))
    for gid, gd in oil_mod.grades_for(veh).items():
        cost = o.capacity_l * gd["price"] + prices.v("OIL_FILTER", veh) + prices.v("OIL_CHANGE_LABOUR", veh)
        item(f"oil_change_{gid}", _cmd("oil_change", grade=gid, filter=1),
             T("Yağ + filtre değiştir: {grade}", grade=_short_grade(gid)), money(cost), confirm=True)
    item("oil_filter", "oil_filter", T("Yalnız yağ filtresini değiştir"), money(prices.v("OIL_FILTER", veh) + prices.v("FILTER_LABOUR", veh)), confirm=True)
    item("oil_sample", "oil_sample", T("Yağ numunesi al (analiz)"), money(prices.v("OIL_SAMPLE", veh)), need_ready=False, block=stop_first)

    # ---- soğutma
    c = t.coolant
    head("h_cool", T("SOĞUTMA · seviye %{lvl} · donma {f} °C", lvl=N(c.level_frac * 100), f=N(c.freeze_point)))
    hot = T("Motor sıcak: radyatör kapağını açmayın") if t.thermal.t_cool > 60 else None
    cneed = round(max(0.0, c.capacity_l - c.volume_l), 1)
    if cneed >= 0.3:
        item("cool_fill", _cmd("coolant_topup", fluid="premix", liters=cneed),
             T("Antifriz tamamla, 50/50 (+{l} L)", l=N(cneed, 1)),
             money(cneed * coolant_mod.FLUIDS["premix"]["price_l"]), block=hot)
    # şu anki tip önce
    order = [c.type] + [k for k in coolant_mod.TYPES if k != c.type] if c.type in coolant_mod.TYPES else list(coolant_mod.TYPES)
    for cid in order:
        cd = coolant_mod.TYPES[cid]
        ccost = c.capacity_l * cd["price_l"] + prices.v("COOLANT_CHANGE_LABOUR", veh)
        item(f"cool_change_{cid}", _cmd("coolant_change", type=cid, concentration=0.5),
             T("Soğutma sıvısını değiştir: %50 {type_t}", type_t=cd["name"]), money(ccost), confirm=True)
    item("cool_test", "coolant_test", T("Antifriz ölçümü (refraktometre)"), money(prices.v("COOLANT_TEST", veh)), need_ready=False, block=stop_first)

    # ---- akü
    b = t.battery
    head("h_batt", T("AKÜ · şarj %{soc} · sağlık %{soh}", soc=N(b.soc * 100), soh=N(b.soh * 100)))
    if b.charger:
        item("charger", _cmd("battery_charger", on=0), T("Şarj cihazını sök"), need_ready=False)
    else:
        item("charger", _cmd("battery_charger", on=1), T("Şarj cihazı bağla ({a} A)", a=N(b.charger_a)),
             money(prices.v("CHARGER", veh)))
    item("jump", "jump_start", T("Takviye kablosu bağla"), money(prices.v("JUMP_START", veh)), need_ready=False,
         block=None if engine_off else T("Motor zaten çalışıyor"))
    item("batt_test", "battery_test", T("Akü testi"), "", need_ready=False, block=stop_first)
    ah = t.spec.battery_ah
    for kid, kd in KINDS.items():
        label = (T("Aküleri yenile: 2 x {ah} Ah, {kind_t}", ah=N(ah), kind_t=kd["name"]) if b.blocks == 2
                 else T("Aküyü yenile: 12 V {ah} Ah, {kind_t}", ah=N(ah), kind_t=kd["name"]))
        item(f"batt_replace_{kid}", _cmd("battery_replace", ah=round(ah), kind=kid), label,
             money(battery_replace_cost(ah, kid, b.volts)), confirm=True)

    # ---- lastikler
    ts = t.tires
    groups = [g for g in TIRE_GROUPS if g in ts.groups]
    if groups:
        sm = ts.summary()
        head("h_tires", T("LASTİK · en az diş {mm} mm · en düşük basınç %{p}", mm=N(sm["min_tread"], 1),
                          p=N((sm["min_ratio"] or 0) * 100)))
        item("tire_inflate", "tire_inflate", T("Lastik basınçlarını ayarla"), T("ücretsiz"), need_ready=False,
             block=stop_first)
        leaks = sum(1 for s in ts.groups.values() if s["leak_bph"] > 0 and not s["blown"])
        if leaks:
            cost = sum(puncture_price(g) for g, s in ts.groups.items() if s["leak_bph"] > 0 and not s["blown"])
            item("tire_puncture", "tire_puncture", T("Yavaş patlağı tamir et"), money(cost))
        # menü kısa kalsın diye katmanda premium, ekonomik ve (arkada) kaplama; orta sınıf uygulama penceresinde
        for g in groups:
            s = ts.groups[g]
            for tier in ("premium", "budget", "retread"):
                if not tier_allowed(g, tier):
                    continue
                item(f"tire_{g}_{tier}", _cmd("tire_replace", axle=g, tier=tier),
                     T("Lastik: {grp_t} ({n} adet, {mm} mm) → {tier_t}", grp_t=GROUP_NAMES[g], n=s["tires"],
                       mm=N(s["tread"], 1), tier_t=TIERS[tier]["name"]),
                     money(ts.replace_cost(g, tier)), confirm=True)

    # ---- AdBlue
    if has_scr(t.spec, f):
        ab = t.adblue
        head("h_adblue", T("ADBLUE · %{p} · {l} / {c} L", p=N(ab.frac * 100), l=N(ab.level_l, 1), c=N(ab.capacity_l)))
        aneed = round(max(0.0, ab.capacity_l - ab.level_l), 1)
        if aneed >= 0.5:
            item("adblue_fill", "adblue_fill", T("AdBlue tamamla (+{l} L)", l=N(aneed, 1)), money(aneed * ADBLUE_PRICE_L))

    # ---- şanzıman ve debriyaj
    tr = t.trans
    head("h_gear", T("ŞANZIMAN · yağ {t} °C · debriyaj %{w} aşınmış", t=N(tr.t_oil), w=N(tr.clutch_wear * 100)))
    item("gearbox_oil", "gearbox_oil", T("Şanzıman yağını değiştir ({l} L + filtre)", l=N(OIL_L[veh])),
         money(prices.v("GEARBOX_OIL", veh)), confirm=True)
    item("clutch_replace", "clutch_replace", T("Debriyajı yenile (balata, baskı plakası, rulman)"),
         money(prices.v("CLUTCH", veh)), confirm=True)

    # ---- DPF
    if t.spec.has_dpf:
        head("h_dpf", T("DPF · is %{s} · kül %{a}", s=N(t.dpf.soot_frac * 100), a=N(t.dpf.ash_frac * 100)))
        item("dpf_regen", "dpf_regen", T("Servis rejenerasyonu"), money(prices.v("DPF_REGEN", veh)), confirm=True)
        item("dpf_clean", "dpf_clean", T("DPF kül temizliği"), money(prices.v("DPF_CLEAN", veh)), confirm=True)

    # ---- onarım
    head("h_rep", T("ONARIM · motor sağlığı %{h}", h=N(t.health.health)))
    for k in t.faults.active:
        if k == "battery_frozen":
            continue
        item(f"rep_{k}", _cmd("repair", fault=k), T("Onar: {name_t}", name_t=FAULTS[k]["name"]),
             money(prices.fault(k, veh)), confirm=True)
    item("overhaul", "overhaul", T("Motor revizyonu"), money(prices.v("OVERHAUL", veh)), confirm=True)

    hint = (T("Tır duruyor, motor kapalı: servis yapılabilir."), "g") if ready else (not_ready, "w")
    return items, hint
