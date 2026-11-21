"""Sürüş modu görüntü testi: color_feed.py'deki sahte tır durumunu yayınlar ve sürüş modunu sırayla değiştirir
(başta COMFORT, <değişim_sn> sonra ECO, iki katı sonra SPORT). Katmanın başlık etiketini ve mod bildirimini görmek için.
Kullanım: drive_feed.py <saniye> [değişim_sn]"""
import os
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from ets2bakim import drivemode  # noqa: E402
from ets2bakim.overlay_feed import OverlayBridge  # noqa: E402
from ets2bakim.view import build_detail, build_state  # noqa: E402
from sim_harness import Harness  # noqa: E402

h = Harness(ambient=12)
h.f.brand, h.f.name, h.f.plate = "Scania", "R", "34 ETS 2026"
h.run(20, rpm=1300, throttle=0.5, speed=80)
app = types.SimpleNamespace(ambient=12.0, expected_min=8.0, lat=53.5, lon=10.0, city="Hamburg", city_km=4.0,
                            source_name="oyun", source=types.SimpleNamespace(status="Oyuna bağlı"),
                            settings={"sound": False}, last_message=None)
b = OverlayBridge()
total = float(sys.argv[1] if len(sys.argv) > 1 else 20)
step = float(sys.argv[2] if len(sys.argv) > 2 else 4)
start = time.time()
while time.time() - start < total:
    k = int((time.time() - start) // step)
    mode = ("comfort", "eco", "sport")[min(k, 2)]
    S = build_state(app, h.t, h.f)
    b.publish(S, build_detail(h.t), [], {"sound": False})
    b.set_drive(*drivemode.header_params({"drive_mode": mode}))
    time.sleep(0.1)
b.close()
