"""Tanıtım görselleri için oyun içi katmana sahne verisi yazar (kapak resimleri: katman_ciz.py çağırır).

Gerçek simülatör modelinden (sim_harness) bir tır durumu kurulur, sahneye göre değerler, uyarı şeridi ve ikaz lambaları
ayarlanır ve test adlı paylaşılan belleğe yazılır: bilgisayarda açık simülatöre ve oyuna dokunmaz.
Kullanım: katman_besle.py <sahne> <saniye> <durum blok adı> <katman blok adı> [dil]
"""
import math
import os
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from ets2bakim import drivemode, i18n  # noqa: E402
from ets2bakim.i18n import M, T  # noqa: E402
from ets2bakim.levels import value_levels  # noqa: E402
from ets2bakim.overlay_feed import OverlayBridge, build_payload  # noqa: E402
from ets2bakim.telltales import ORDER  # noqa: E402
from ets2bakim.view import build_detail, build_state  # noqa: E402
from sim_harness import Harness  # noqa: E402

scene, secs, state_name, ovl_name = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4]
i18n.set_lang(sys.argv[5] if len(sys.argv) > 5 else "tr")   # tr | en | de


def killed(reason):
    return T("MOTOR GERÇEKTE ÇALIŞMIYOR: {reason} Oyunda motoru kapatın.", reason=reason)


# sahne: ortam, şehir, değer değişiklikleri, uyarı şeridi, lambalar (sol → sağ, katmandaki sırayla), sürüş modu
SCENES = {
    "kritik": dict(
        amb=14.0, city="Berlin", drive="comfort",
        values={("thermal", "t_cool"): 113, ("thermal", "t_oil"): 136, ("oil", "pressure"): 0.4, ("oil", "low_thr"): 0.9,
                ("battery", "voltage"): 27.9, ("oil", "level_pct"): 64},
        warnings=[("crit", killed(M("Yağ basıncı yok: krank yatakları sardı, MOTOR KİLİTLENDİ."))),
                  ("crit", T("YAĞ BASINCI DÜŞÜK ({p:.1f} bar) — motoru hemen durdurun!", p=0.4))],
        lamps={"stop": "c", "oil": "c", "cool": "c", "eng": "c"}),
    "kis": dict(
        amb=-25.0, city="Oslo", drive="comfort", time="Pzt 06:12",
        values={("thermal", "t_cool"): -24, ("thermal", "t_oil"): -24, ("oil", "pressure"): 0.0,
                ("battery", "voltage"): 24.1, ("battery", "soc"): 58},
        warnings=[("crit", killed(M("Marş başarısız: {reason}.", reason=M(
                      "Yağ çok koyu ({visc:,.0f} cSt): marş motoru motoru çeviremiyor", visc=21400)))),
                  ("crit", T("Yağ bu soğukta çok koyu ({visc:,.0f} cSt): motor marşla dönmez. Daha ince yağ veya ısıtma "
                             "gerekir.", visc=21400))],
        lamps={"stop": "c", "batt": "c", "glow": "w", "frost": "c"}),
    "aku": dict(
        amb=4.0, city="Hamburg", drive="comfort", time="Cum 23:40",
        values={("battery", "voltage"): 22.6, ("battery", "soc"): 9, ("battery", "current"): -26.0},
        warnings=[("crit", killed(M("Marş başarısız: {reason}.", reason=M("Akü yetersiz: marşta voltaj {v:.1f} V'a düştü",
                                                                          v=15.2)))),
                  ("warn", T("Kontak açık, {a:.0f} A çekiliyor: akü {h:.1f} saatte %50'ye iner.", a=26, h=0.3))],
        lamps={"stop": "c", "batt": "c"}),
    "cok": dict(
        amb=19.0, city="Rotterdam", drive="eco",
        values={("live", "brake_temp"): 471, ("live", "air_bar"): 5.2},
        warnings=[("crit", T("FRENLER AŞIRI ISINDI ({t:.0f} °C) — fren gücü azaldı!", t=471)),
                  ("crit", T("Hava basıncı düşük ({p:.1f} bar): frenler kilitlenebilir.", p=5.2))],
        lamps={"brake": "c", "park": "w", "tire": "w", "fuel": "w"}),
    "hepsi": dict(
        amb=12.0, city="Prag", drive="sport", values={}, warnings=[],
        lamps={k: ("c" if k in ("stop", "batt", "oil", "cool", "brake", "steer", "gear", "frost") else "w") for k in ORDER}),
}
sc = SCENES[scene]

h = Harness(ambient=sc["amb"])
h.f.brand, h.f.name, h.f.plate = "Volvo", "FH", "34 ETS 2026"
h.f.gear_ratios, h.f.diff_ratio, h.f.wheel_radius, h.f.gears_forward = [14.94, 11.73, 9.04, 7.09, 5.54, 4.35, 3.44, 2.70,
                                                                        2.08, 1.63, 1.27, 1.00], 2.64, 0.52, 12
h.f.gear = 10
h.run(25, rpm=1350, throttle=0.6, speed=78)
app = types.SimpleNamespace(ambient=sc["amb"], expected_min=sc["amb"] - 6, lat=52.5, lon=13.4, city=sc["city"], city_km=3.0,
                            source_name="oyun", source=types.SimpleNamespace(status="Oyuna bağlı"),
                            settings={"sound": False, "alert_level": "all"}, last_message=None)
settings = {"sound": False, "alert_level": "all", "lamp_level": "onemsiz"}
# "son dakikalar" grafiği: soğutma suyu ve yağ sahneye doğru tırmanır
n = 160
hist = []
for i in range(n):
    k = i / (n - 1)
    cool = sc["values"].get(("thermal", "t_cool"), 90)
    oil = sc["values"].get(("thermal", "t_oil"), 96)
    hist.append({"cool": 88 + (cool - 88) * k ** 3 + math.sin(i / 7) * 0.8, "oil_t": 94 + (oil - 94) * k ** 3,
                 "oil_p": 3.4 - 2.9 * k ** 4, "volt": 28.2 - 0.6 * k, "rpm": 1350 + 120 * math.sin(i / 9)})


def state():
    S = build_state(app, h.t, h.f)
    for (sec, key), v in sc["values"].items():
        S[sec][key] = v
    if "time" in sc:
        S["status"]["time"] = sc["time"]
    S["location"]["ambient"] = sc["amb"]
    S["warnings"] = [{"level": lv, "text": tx} for lv, tx in sc["warnings"]]
    S["levels"] = value_levels(S)
    return S


lamps = [(k, sc["lamps"][k]) for k in ORDER if k in sc["lamps"]]
b = OverlayBridge(state_name=state_name, ovl_name=ovl_name)
drive = drivemode.header_params({"drive_modes": True, "drive_mode": sc["drive"]}, "truck")
D = build_detail(h.t)
end = time.time() + secs
while time.time() < end:
    b.beat = (b.beat + 1) & 0xFFFFFFFF
    b._write(build_payload(state(), D, hist, settings, b.beat, lamps=lamps))
    b.set_drive(*drive)
    time.sleep(0.2)
b.close()
