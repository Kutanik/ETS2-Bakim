"""Renk testi: katmana sınırda (sarı) ve kritik (kırmızı) değerli sahte bir tır durumu gönderir.
Kullanım: color_feed.py <saniye>   (bu sürede test_host ile ekran görüntüsü alınır)"""
import os
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from ets2bakim.overlay_feed import OverlayBridge  # noqa: E402
from ets2bakim.telltales import Telltales  # noqa: E402
from ets2bakim.view import build_detail, build_state  # noqa: E402
from sim_harness import Harness  # noqa: E402

h = Harness(ambient=-12)
h.f.brand, h.f.name, h.f.plate = "Volvo", "FH16 2012", "34 ETS 2026"
h.run(30, rpm=2160, throttle=0.9, speed=70)
t = h.t
t.thermal.t_cool = 107.0          # sınırda
t.thermal.t_oil = 138.0           # kritik
t.oil.volume_l = t.oil.capacity_l * 0.80   # MIN altı: sınırda
t.oil.filter_km = 140000          # filtre: sınırda/kritik
t.oil.fe = 120.0                  # kritik
t.battery.soc = 0.45              # kritik
t.battery.soh = 0.70              # sınırda
t.coolant.glycol = 0.33           # sınırda; donma noktası -12 °C civarı -> kritik
t.dpf.soot_g = t.dpf.soot_cap * 1.1
t.health.health = 52.0            # sınırda
t.faults.active.append("alternator")
app = types.SimpleNamespace(ambient=-12.0, expected_min=-18.0, lat=59.3, lon=18.1, city="Stockholm", city_km=4.0,
                            source_name="oyun", source=types.SimpleNamespace(status="Oyuna bağlı"),
                            settings={"sound": False}, last_message=None)
b = OverlayBridge()
end = time.time() + float(sys.argv[1] if len(sys.argv) > 1 else 20)
S = build_state(app, t, h.f)
print({k: v for k, v in S["levels"].items() if v in ("w", "c")})
print("lambalar:", Telltales().update(S), flush=True)
while time.time() < end:
    S = build_state(app, t, h.f)
    b.publish(S, build_detail(t), [], {"sound": False})
    time.sleep(0.2)
b.close()
