"""Değer renk seviyeleri — uygulama penceresi ve oyun içi katman için tek kaynak.

Seviyeler: g = normal (iyi), w = sınırda (sarı), c = kritik (kırmızı), m = önemsiz / ölçülmüyor, n = nötr.
value_levels(S) anahtar olarak durum sözlüğündeki yolu kullanır (ör. "thermal.t_cool"); uygulama penceresi
data-v="..." ile gösterdiği her değeri bu sözlüğe bakarak renklendirir, katman da aynı seviyeleri kullanır.
"""
from . import oil as oil_mod


def _hi(v, warn, crit):
    """Büyüdükçe kötüleşen değer."""
    if v is None:
        return "m"
    return "c" if v >= crit else "w" if v >= warn else "g"


def _lo(v, warn, crit):
    """Küçüldükçe kötüleşen değer (warn > crit)."""
    if v is None:
        return "m"
    return "c" if v < crit else "w" if v < warn else "g"


def _band(v, warn_lo, warn_hi, crit_lo, crit_hi):
    """Bir aralıkta olması gereken değer."""
    if v is None:
        return "m"
    if v < crit_lo or v > crit_hi:
        return "c"
    if v < warn_lo or v > warn_hi:
        return "w"
    return "g"


def _worst(*lv):
    order = {"c": 3, "w": 2, "g": 1, "n": 0, "m": 0}
    return max(lv, key=lambda x: order.get(x, 0))


def value_levels(S):
    vs = ((S.get("battery") or {}).get("volts") or 24) / 24.0   # 12 V otomobilde eşikler yarı
    th, o, c, b, d, L = S["thermal"], S["oil"], S["coolant"], S["battery"], S["dpf"], S["live"]
    loc, E = S["location"], S["engine"]
    running = L.get("running")
    faults = {f["key"] for f in S.get("faults", [])}
    lv = {}

    # sıcaklık, basınç, elektrik
    t = th["t_cool"]
    lv["thermal.t_cool"] = "m" if t < 60 else _hi(t, 104, 110)
    t = th["t_oil"]
    lv["thermal.t_oil"] = "m" if t < 50 else _hi(t, 120, 135)
    lv["thermal.block_ice"] = _hi(th.get("block_ice"), 0.5, 5)
    lv["thermal.rad_ice"] = _hi(th.get("rad_ice"), 1, 30)
    lv["thermal.pressure"] = "c" if th.get("boiling") else "n"
    if running:
        p, thr = o["pressure"], o["low_thr"]
        lv["oil.pressure"] = "c" if p < thr else "w" if p < thr + 0.5 else "g"
        lv["battery.voltage"] = _lo(b["voltage"], 27.0 * vs, 25.5 * vs)
    else:
        lv["oil.pressure"] = "m"
        lv["battery.voltage"] = _lo(b["voltage"], 24.6 * vs, 24.2 * vs)

    # motor
    rmax = L.get("rpm_max") or 2300
    lv["live.rpm"] = _hi(L.get("rpm"), 0.90 * rmax, 0.97 * rmax) if running else "m"
    lv["live.exh"] = "w" if d.get("burning") else _hi(L.get("exh"), 550, 650)
    lv["live.brake_temp"] = _hi(L.get("brake_temp") or 0, 250, 450)
    air = L.get("air_bar")
    lv["live.air_bar"] = "c" if L.get("air_warning") else _lo(air, 7.0, 5.5) if air else "m"
    lv["engine.health"] = _lo(E["health"], 60, 40)
    lv["engine.wear_rate"] = _hi(E.get("wear_rate"), 1.5, 3.0)
    lv["engine.hg_stress"] = _hi(E.get("hg_stress"), 20, 60)
    lv["engine.seize_stress"] = _hi(E.get("seize_stress"), 20, 60)
    for k, v in (E.get("game_wear") or {}).items():
        lv[f"engine.game_wear.{k}"] = _hi(v, 10, 30)

    # yağ
    lvl = o["level_pct"]
    olv = "w" if lvl > 106 else "g" if lvl >= o["min_pct"] else "w" if lvl >= 70 else "c"
    lv["oil.level_pct"] = lv["oil.volume"] = olv
    lv["oil.life"] = _lo(o["life"], 30, 10)
    ref = o.get("tbn_ref") or 1
    lv["oil.tbn"] = _lo(o.get("tbn", ref) / ref, 0.65, 0.5)
    limit = oil_mod.GRADES.get(o.get("grade"), oil_mod.GRADES["10w40"])["soot_limit"]
    lv["oil.soot"] = _hi((o.get("soot") or 0) / limit, 0.7, 1.0)
    lv["oil.fe"] = _hi(o.get("fe"), 60, 100)
    lv["oil.fuel_dil"] = _hi(o.get("fuel_dil"), 1.5, 2.5)
    lv["oil.water"] = _hi(o.get("water"), 1000, 2000)
    lv["oil.ox"] = _hi(o.get("ox"), 18, 25)
    lv["oil.filter_pct"] = _hi(o.get("filter_pct"), 85, 100)
    lv["oil.km"] = _hi((o.get("interval_used") or 0) / 100.0, 0.9, 1.0)   # aralığın kullanılan kısmı (hız çarpanlı)
    lv["oil.visc_chg"] = _band(o.get("visc_chg"), -10, 12, -15, 20)
    lv["oil.visc100"] = lv["oil.visc_now"] = lv["oil.visc_chg"]
    lv["oil.consumption_l_1000"] = _hi(o.get("consumption_l_1000"), 0.5, 1.0)

    # soğutma sıvısı
    lv["coolant.level_pct"] = lv["coolant.volume"] = _lo(c["level_pct"], 85, 70)
    fp, amb, exp = c["freeze"], loc["ambient"], loc["expected_min"]
    lv["coolant.freeze"] = "c" if amb < fp else "w" if exp < fp else "g"
    lv["coolant.glycol"] = _band(c.get("glycol"), 35, 65, 25, 70)
    lv["coolant.inhibitor"] = _lo(c["inhibitor"], 50, 30)
    lv["coolant.ph"] = _lo(c.get("ph"), 7.6, 7.2)
    lv["coolant.scale"] = _hi(c.get("scale"), 12, 25)
    lv["coolant.age_days"] = _hi((c.get("age_used") or 0) / 100.0, 0.9, 1.0)
    lv["coolant.km"] = _hi((c.get("km_used") or 0) / 100.0, 0.9, 1.0)

    # akü
    lv["battery.soc"] = _lo(b["soc"], 75, 50)
    lv["battery.soh"] = _lo(b["soh"], 80, 60)
    lv["battery.crank_v"] = _lo(b["crank_v"], 17 * vs, 14 * vs)
    ms = b.get("min_start_soc")
    lv["battery.min_start_soc"] = "c" if ms is None or ms > b["soc"] else "w" if ms > b["soc"] - 10 else "g"
    cur = b.get("current") or 0
    if running:
        lv["battery.current"] = "c" if "alternator" in faults else "w" if cur < -2 else "g"
    else:
        lv["battery.current"] = "w" if cur < -15 else "n"
    lv["battery.hours_to_50"] = _lo(b.get("hours_to_50"), 6, 2) if b.get("hours_to_50") is not None else "m"
    lv["battery.temp"] = _lo(b["temp"] - b["freeze"], 10, 5)
    lv["battery.sulfation"] = _hi(b.get("sulfation"), 8, 20)

    # DPF
    if d.get("enabled"):
        lv["dpf.soot"] = "w" if d.get("burning") else _hi(d["soot"], 75, 100)
        lv["dpf.ash"] = _hi(d["ash"], 70, 85)
        lv["dpf.backpressure"] = _hi(d.get("backpressure"), 25, 35)
    else:
        lv["dpf.soot"] = lv["dpf.ash"] = "m"

    # yakıt, AdBlue, lastikler
    fu = S.get("fuel") or {}
    lv["fuel.pct"] = lv["fuel.l"] = lv["fuel.range_km"] = _lo(fu.get("pct"), max(15.0, fu.get("warn_pct") or 15.0), 5.0)
    ab = S.get("adblue") or {}
    lv["adblue.pct"] = lv["adblue.l"] = _lo(ab.get("pct"), 10.0, 5.0) if ab.get("enabled") else "m"
    ty = S.get("tires") or {}
    worst = "g"
    for g in ty.get("groups", []):
        worst = _worst(worst, *g["lv"].values())
    lv["tires.status"] = worst
    lv["tires.min_tread"] = _worst("g", *(g["lv"]["tread"] for g in ty.get("groups", []))) if ty.get("groups") else "m"
    lv["tires.min_pressure_pct"] = (_worst("g", *(g["lv"]["pressure"] for g in ty.get("groups", [])))
                                    if ty.get("groups") else "m")
    lv["tires.max_temp"] = _hi(ty.get("max_temp"), 95, 115)
    lv["tires.game_wear"] = _hi(ty.get("game_wear"), 10, 30)

    # şanzıman ve debriyaj (eşikler transmission.py ile aynı), direksiyon hidroliği
    tr = S.get("trans") or {}
    t = tr.get("t_oil")
    lv["trans.t_oil"] = "m" if t is None or t < 40 else _hi(t, 115, 130)
    lv["trans.t_clutch"] = _hi(tr.get("t_clutch"), 250, 320)
    lv["trans.clutch_wear"] = _hi(tr.get("clutch_wear"), 85, 100)
    lv["trans.clutch_left_km"] = lv["trans.clutch_wear"]
    lv["trans.oil_used"] = lv["trans.oil_km"] = _hi((tr.get("oil_used") or 0) / 100.0, 0.9, 1.0) if tr else "m"
    lv["trans.game_wear"] = _hi(tr.get("game_wear"), 10, 30)
    st = S.get("steering") or {}
    lv["steering.fluid"] = _lo(st.get("fluid"), 85, 60) if st.get("hydraulic") else "m"
    return lv


def tire_group_levels(g, s):
    """Bir dingil grubunun diş, basınç ve sıcaklık seviyeleri."""
    from .tires import LEGAL_MM, WARN_TREAD_MM
    ratio = s["cold_bar"] / s["nominal"] if s["nominal"] else 1.0
    pressure = ("c" if s["blown"] or ratio < 0.75 else
                "w" if ratio < 0.88 or ratio > 1.12 or s["leak_bph"] > 0 else "g")
    return {"tread": "c" if s["tread"] < LEGAL_MM else "w" if s["tread"] < WARN_TREAD_MM[g] else "g",
            "pressure": pressure, "temp": _hi(s["temp"], 95, 115)}


def session_levels(ss):
    """Oturum sürüş tarzı: rölanti, eko bant, lugging, soğuk motora yüklenme, sert fren."""
    ss = ss or {}
    eco = ss.get("eco_pct")
    return {
        "idle": _hi(ss.get("idle_pct"), 15, 30),
        "eco": "m" if eco is None or (ss.get("drive_h") or 0) < 0.1 else _lo(eco, 50, 25),
        "lug": _hi(ss.get("lugging_min"), 5, 15),
        "coldload": _hi(ss.get("cold_load_min"), 2, 10),
        "harsh": _hi(ss.get("harsh_brake"), 3, 8),
        "overrev": _hi(ss.get("overrev_events"), 3, 10),
        "overheat": _hi(ss.get("overheat_min"), 1, 5),
    }


__all__ = ["value_levels", "session_levels", "tire_group_levels", "_worst"]
