"""Yeni lambalar testi (1.10): ŞANZIMAN, DİREKSİYON, MARŞ, ABS, EL FRENİ ve hava basıncında kırmızı FREN lambası yanan
sahte bir tır durumunu test adlı paylaşılan belleğe yazar (bilgisayarda açık simülatöre dokunmaz).
Kullanım: yeni_lamba_feed.py <saniye> <durum blok adı> <katman blok adı> [önem derecesi]"""
import os
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from ets2bakim.levels import value_levels  # noqa: E402
from ets2bakim.overlay_feed import OverlayBridge  # noqa: E402
from ets2bakim.telltales import Telltales  # noqa: E402
from ets2bakim.view import build_detail, build_state  # noqa: E402
from sim_harness import Harness  # noqa: E402

secs, state_name, ovl_name = float(sys.argv[1]), sys.argv[2], sys.argv[3]
lamp_level = sys.argv[4] if len(sys.argv) > 4 else "onemsiz"
from ets2bakim import i18n  # noqa: E402
i18n.set_lang(sys.argv[5] if len(sys.argv) > 5 else "tr")
h = Harness(ambient=24)
h.f.brand, h.f.name, h.f.plate = "Scania", "R 2016", "34 ETS 2026"
h.f.gear_ratios, h.f.diff_ratio, h.f.wheel_radius, h.f.gears_forward = [14.94, 11.73, 9.04, 7.09, 5.54, 4.35, 3.44, 2.70,
                                                                        2.08, 1.63, 1.27, 1.00], 2.64, 0.52, 12
h.f.gear = 9
h.run(20, rpm=1500, throttle=1.0, speed=50)
t = h.t
t.faults.active += ["abs_sensor", "starter", "steering_leak", "gearbox_cooler"]
t.trans.t_oil, t.trans.t_clutch, t.trans.clutch_wear = 133.0, 265.0, 0.62
t.steer_fluid = 0.5
h.f.air_warning, h.f.air_bar, h.f.park_brake = True, 5.2, False
app = types.SimpleNamespace(ambient=24.0, expected_min=10.0, lat=59.3, lon=18.1, city="Stockholm", city_km=4.0,
                            source_name="oyun", source=types.SimpleNamespace(status="Oyuna bağlı"),
                            settings={"sound": False}, last_message=None)


def state():
    S = build_state(app, t, h.f)
    S["live"]["park_warn"] = True          # motor kapalıyken park freni çekilmemiş gibi (EL FRENİ lambası)
    S["levels"] = value_levels(S)
    return S


b = OverlayBridge(state_name=state_name, ovl_name=ovl_name)
settings = {"sound": False, "lamp_level": lamp_level}
print("lambalar:", Telltales().update(state(), min_level=lamp_level), flush=True)
end = time.time() + secs
while time.time() < end:
    b.publish(state(), build_detail(t), [], settings)
    time.sleep(0.2)
b.close()
