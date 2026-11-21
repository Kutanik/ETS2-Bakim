import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ets2bakim import geo  # noqa: E402
from ets2bakim.truck import TruckModel  # noqa: E402
from sim_harness import Harness  # noqa: E402


def make_app(**kw):
    """Demo uygulama nesnesi. Katman köprüsü ayrı paylaşılan bellek adları kullanır: testler, bilgisayarda açık olan
    gerçek uygulamanın oyun içi katman bloğuna dokunmaz."""
    import functools
    import tempfile
    from unittest import mock
    from ets2bakim import app as app_mod
    from ets2bakim.overlay_feed import OverlayBridge
    bridge = functools.partial(OverlayBridge, state_name="Local\\EBKTestState", ovl_name="Local\\EBKTestOvl")
    with mock.patch.object(app_mod, "OverlayBridge", bridge):
        return app_mod.App(demo=True, open_window=False, data_dir=tempfile.mkdtemp(), **kw)


def start_engine(h, wait_preheat=True):
    """Oyunda motoru çalıştırmayı taklit eder: kontak açılır, gerekiyorsa ön ısıtma lambası sönene kadar beklenir
    (süre gerçek saniye; düzenekte oyun saati 19 kat hızlı), sonra marş."""
    from ets2bakim.preheat import duration_s
    h.f.engine_on, h.f.electric_on = False, True
    wait = duration_s(h.t.thermal.t_cool) * 19 / 60 + 0.1 if wait_preheat else 0.1
    h.run(wait, engine=False)
    h.run(0.2, rpm=600, throttle=0.0, speed=0)


class GeoTests(unittest.TestCase):
    def test_round_trip(self):
        for lat, lon in [(52.52, 13.40), (41.01, 28.98), (59.91, 10.75)]:
            x, z = geo.latlon_to_game(lat, lon)
            la, lo = geo.game_to_latlon(x, z)
            self.assertAlmostEqual(la, lat, places=4)
            self.assertAlmostEqual(lo, lon, places=4)

    def test_calais_near_real(self):
        lat, lon = geo.game_to_latlon(-31100, -5500)
        self.assertLess(abs(lat - 50.95), 0.3)
        self.assertLess(abs(lon - 1.86), 0.6)


class StartTests(unittest.TestCase):
    def test_cold_thick_oil_fails_to_crank(self):
        h = Harness(ambient=-28, grade="15w40")
        h.t.thermal.t_oil = h.t.thermal.t_cool = -28
        h.t.battery.temp = -28
        start_engine(h)
        self.assertTrue(h.t.killed)
        self.assertEqual(h.t.analysis.failed_starts, 1)

    def test_thin_oil_starts_in_same_cold(self):
        h = Harness(ambient=-28, grade="5w30")
        h.t.thermal.t_oil = h.t.thermal.t_cool = -28
        h.t.battery.temp = -28
        h.t.battery.soc = 1.0
        start_engine(h)
        self.assertFalse(h.t.killed)

    def test_preheat_must_finish_in_deep_cold(self):
        h = Harness(ambient=-25, grade="5w30")
        h.t.thermal.t_oil = h.t.thermal.t_cool = -25
        h.t.battery.temp, h.t.battery.soc = -25, 1.0
        start_engine(h, wait_preheat=False)              # kontak açılır açılmaz marş
        self.assertTrue(h.t.killed)
        self.assertIn("ön ısıtma", str(h.t.kill_reason))
        h.f.engine_on = False
        h.run(0.1, engine=False)
        start_engine(h)                                  # lamba sönene kadar bekle
        self.assertFalse(h.t.killed)

    def test_early_start_in_mild_cold_wears(self):
        h = Harness(ambient=-5, grade="10w40")
        h.t.thermal.t_oil = h.t.thermal.t_cool = -5
        health = h.t.health.health
        start_engine(h, wait_preheat=False)
        self.assertFalse(h.t.killed)                     # -5 °C'de çalışır ama zorlanır
        self.assertLess(h.t.health.health, health)
        self.assertTrue(any("Ön ısıtma tamamlanmadan" in e["m"] for e in h.t.log))

    def test_faulty_preheater_no_start_and_lamp(self):
        import types as _t
        from ets2bakim.telltales import compute
        from ets2bakim.view import build_state
        h = Harness(ambient=-10, grade="5w30")
        h.t.thermal.t_oil = h.t.thermal.t_cool = -10
        h.t.battery.soc = 1.0
        h.t.faults.active.append("preheater")
        h.f.engine_on, h.f.electric_on = False, True
        h.run(0.5, engine=False)
        app = _t.SimpleNamespace(ambient=-10.0, expected_min=-15.0, lat=50.0, lon=10.0, city="", city_km=0.0,
                                 source_name="oyun", source=_t.SimpleNamespace(status=""), settings={}, last_message=None)
        S = build_state(app, h.t, h.f)
        self.assertEqual(compute(S).get("glow"), "c")    # arıza: kırmızı yanıp söner
        start_engine(h)
        self.assertTrue(h.t.killed)

    def test_preheat_lamp_while_heating_and_battery_draw(self):
        from ets2bakim.preheat import CURRENT_A
        h = Harness(ambient=-15)
        h.t.thermal.t_cool = -15
        h.f.engine_on, h.f.electric_on = False, True
        h.run(0.05, engine=False)
        self.assertTrue(h.t.preheat.active)
        self.assertGreaterEqual(h.t.flags["load_a"], CURRENT_A)

    def test_flat_battery_and_jump_start(self):
        h = Harness(ambient=10)
        h.t.battery.soc = 0.05
        start_engine(h)
        self.assertTrue(h.t.killed)
        ok, _ = h.t.action(h.f, "jump_start", {}) if not h.f.engine_on else (None, None)
        h.f.engine_on = False
        h.run(0.1, engine=False)
        ok, _ = h.t.action(h.f, "jump_start", {})
        self.assertTrue(ok)
        h.run(0.2, rpm=600, throttle=0.0, speed=0)
        self.assertFalse(h.t.killed)


class FailureTests(unittest.TestCase):
    def test_alternator_failure_stops_engine(self):
        h = Harness(ambient=15)
        h.t.faults.active.append("alternator")
        h.t.battery.soc = 0.3
        h.run(150, low=True, parking=True)
        self.assertTrue(h.t.killed)
        from ets2bakim.i18n import render
        self.assertIn("ECU", render(h.t.kill_reason))

    def test_no_oil_seizes_engine(self):
        h = Harness(ambient=15)
        h.t.oil.volume_l = 10.0
        h.run(20)
        self.assertIn("engine_seized", h.t.faults.active)
        self.assertTrue(h.t.killed)

    def test_water_only_freezes_and_cracks(self):
        h = Harness(ambient=-15)
        h.t.coolant.glycol = 0.0
        h.parked(12)
        self.assertIn("block_cracked", h.t.faults.active)

    def test_antifreeze_protects(self):
        h = Harness(ambient=-25)
        h.parked(12)
        self.assertEqual([f for f in h.t.faults.active if "crack" in f], [])

    def test_lights_on_overnight_drain_battery(self):
        h = Harness(ambient=15)
        h.t.battery.soc = 0.95
        h.parked(10, electric=True, low=True, parking=True)
        self.assertLess(h.t.battery.soc, 0.25)


class ServiceTests(unittest.TestCase):
    def test_service_requires_stopped_engine(self):
        h = Harness(ambient=15)
        h.run(1)
        ok, msg = h.t.action(h.f, "oil_change", {"grade": "10w40"})
        self.assertFalse(ok)
        h.f.engine_on, h.f.speed_kmh = False, 0
        ok, _ = h.t.action(h.f, "oil_change", {"grade": "5w30", "filter": True})
        self.assertTrue(ok)
        self.assertEqual(h.t.oil.grade, "5w30")
        self.assertGreater(h.t.costs_total, 0)

    def test_hot_radiator_cap_refused(self):
        h = Harness(ambient=15)
        h.run(30)
        h.f.engine_on, h.f.speed_kmh = False, 0
        ok, msg = h.t.action(h.f, "coolant_topup", {"fluid": "premix", "liters": 2})
        from ets2bakim.i18n import render
        self.assertFalse(ok)
        self.assertIn("sıcak", render(msg))

    def test_water_topup_lowers_protection(self):
        h = Harness(ambient=15)
        h.t.coolant.volume_l = 50
        h.f.engine_on, h.f.speed_kmh = False, 0
        before = h.t.coolant.freeze_point
        h.t.action(h.f, "coolant_topup", {"fluid": "distilled", "liters": 20})
        self.assertGreater(h.t.coolant.freeze_point, before + 10)

    def test_lab_report(self):
        h = Harness(ambient=15)
        h.f.engine_on, h.f.speed_kmh = False, 0
        ok, _ = h.t.action(h.f, "oil_sample", {})
        self.assertTrue(ok)
        self.assertEqual(len(h.t.reports["oil"]["rows"]), 14)


class EngineSelectionTests(unittest.TestCase):
    def test_model_default_applied(self):
        h = Harness(ambient=15)
        h.f.brand_id, h.f.truck_id, h.f.name = "scania", "vehicle.scania.s_2016", "S"
        t = TruckModel("x", {})
        t.first_time_setup(h.f, 15)
        self.assertEqual(t.spec.model_key, "scania_ng")
        self.assertEqual(t.spec.engine_id, "dc13_500")
        self.assertEqual(t.oil.capacity_l, 38)
        self.assertAlmostEqual(t.coolant.level_frac, 1.0)
        self.assertLessEqual(t.oil.level_frac, 1.0)

    def test_curve_honours_power_and_torque(self):
        from ets2bakim.engine import EngineSpec
        s = EngineSpec(power_kw=510 * 0.7355, torque_nm=2500, rated_rpm=1600)
        self.assertAlmostEqual(s.max_power_kw(1600), 510 * 0.7355, delta=2)
        self.assertAlmostEqual(s.max_torque_nm(1200), 2500, delta=1)

    def test_detects_engine_from_climb(self):
        from ets2bakim.telemetry import DemoSource
        h = Harness(ambient=15)
        h.f.brand_id, h.f.truck_id, h.f.name = "volvo", "vehicle.volvo.fh16_2012", "FH16 2012"
        t = TruckModel("x", {})
        t.first_time_setup(h.f, 15)
        self.assertEqual(t.spec.engine_id, "d13k500")
        demo = DemoSource()
        demo.speed = 85.0
        f = demo.f
        f.engine_on = f.electric_on = True
        f.throttle = 1.0
        for _ in range(400):
            demo._climb(0.1, 1.0)
            f.speed_kmh, f.rpm, f.gear = demo.speed, demo.rpm, demo.gear
            t.detector.feed(f, 0.1, True, t.spec)
        t._check_detection(f)
        self.assertEqual(t.spec.engine_id, "d13k540")


class OverlayFeedTests(unittest.TestCase):
    def _state(self):
        import types
        from ets2bakim.view import build_detail, build_state
        h = Harness(ambient=-5)
        h.f.brand, h.f.name, h.f.plate = "Volvo", "FH16 2012", "34 ETS 2026"
        h.run(20)
        app = types.SimpleNamespace(ambient=-5.0, expected_min=-12.0, lat=52.5, lon=13.4, city="Berlin", city_km=3.0,
                                    source_name="oyun", source=types.SimpleNamespace(status="Oyuna bağlı"),
                                    settings={"sound": True}, last_message=None)
        return build_state(app, h.t, h.f), build_detail(h.t)

    def test_payload_format(self):
        from ets2bakim.overlay_feed import build_payload
        S, D = self._state()
        hist = [{"cool": 80.0 + i * 0.1, "oil_t": 90.0, "oil_p": 3.5, "volt": 28.1, "rpm": 1200} for i in range(300)]
        data = build_payload(S, D, hist, {"sound": True}, 7).decode("utf-8")
        keys = {}
        lines = data.split("\n")
        for line in lines:
            parts = line.split("\t")
            if parts[0] == "k":
                self.assertEqual(len(parts), 5, line)
                self.assertIn(parts[3], "gwcmn")
                keys[parts[1]] = parts[2]
        for k in ("cool", "oilt", "oilp", "volt", "soc", "olife", "freeze", "health", "rpm", "engine", "score_s"):
            self.assertIn(k, keys)
        self.assertIn("°C", keys["cool"])
        self.assertTrue(any(line.startswith("h\tcool\t") for line in lines))
        self.assertTrue(any(line.startswith("m\t") for line in lines))

    def test_shared_memory_roundtrip_and_command(self):
        import struct
        from multiprocessing import shared_memory
        from ets2bakim.overlay_feed import HEADER, OverlayBridge
        S, D = self._state()
        b = OverlayBridge(state_name="Local\\EBKTestState", ovl_name="Local\\EBKTestOvl")
        try:
            b.publish(S, D, [], {"sound": False})
            r = shared_memory.SharedMemory(name="Local\\EBKTestState", create=False)
            magic = bytes(r.buf[0:8])
            seq, length = struct.unpack_from("<II", r.buf, 8)
            payload = bytes(r.buf[HEADER:HEADER + length]).decode("utf-8")
            self.assertEqual(magic, b"EBKSTAT1")
            self.assertEqual(seq % 2, 0)
            self.assertIn("cfg\tsound\t0", payload)
            self.assertTrue(b.ignition_off())
            self.assertFalse(b.ignition_off())  # bekleme süresi
            cmd_seq, code = struct.unpack_from("<II", r.buf, 16)
            self.assertEqual((cmd_seq, code), (1, 1))
            r.close()
        finally:
            b.close()

    def test_hud_sync_config(self):
        from ets2bakim.overlay_feed import build_payload
        S, D = self._state()
        data = build_payload(S, D, [], {"sound": True}, 1, 0x76).decode("utf-8").split("\n")
        self.assertIn("cfg\thudsync\t1", data)
        self.assertIn("cfg\thudkey\t118", data)
        data = build_payload(S, D, [], {"hide_with_hud": False}, 1).decode("utf-8").split("\n")
        self.assertIn("cfg\thudsync\t0", data)
        self.assertIn("cfg\thudkey\t114", data)  # varsayılan F3


class OverlayServiceTests(unittest.TestCase):
    """Oyun içi servis menüsü (Alt+F8): maddeler, komut kanalı ve uygulama."""

    def _parked(self):
        h = Harness(ambient=10)
        h.run(5)
        h.f.engine_on, h.f.speed_kmh, h.f.rpm = False, 0.0, 0.0
        return h

    def test_menu_items_and_flags(self):
        from ets2bakim import service_menu
        h = self._parked()
        h.t.oil.volume_l = h.t.oil.capacity_l - 3.0
        h.t.faults.active.append("alternator")
        items, (hint, lvl) = service_menu.build(h.t, h.f, {"currency": "€"})
        by = {i["key"]: i for i in items}
        self.assertEqual(lvl, "g")
        self.assertIn("oil_fill", by)
        self.assertIn("liters=3.0", by["oil_fill"]["cmd"])
        self.assertEqual(by["oil_change_10w40"]["flag"], "c")      # pahalı: onay ister
        self.assertEqual(by["batt_replace_std"]["flag"], "c")
        self.assertIn("rep_alternator", by)
        self.assertTrue(all(i["flag"] in "hdcn" for i in items))
        self.assertTrue(all("€" in i["detail"] for i in items if i["key"].startswith("oil_change")))
        # sürüş sırasında servis işlemleri kapalı, nedeni yazılı
        h.f.engine_on, h.f.speed_kmh = True, 60.0
        items, (hint, lvl) = service_menu.build(h.t, h.f, {})
        by = {i["key"]: i for i in items}
        self.assertEqual(lvl, "w")
        self.assertEqual(by["oil_add1"]["flag"], "d")
        self.assertEqual(by["oil_add1"]["detail"], hint)
        self.assertEqual(by["oil_sample"]["flag"], "d")

    def test_hot_engine_blocks_coolant_topup(self):
        from ets2bakim import service_menu
        h = self._parked()
        h.t.coolant.volume_l = h.t.coolant.capacity_l - 5
        h.t.thermal.t_cool = 85.0
        by = {i["key"]: i for i in service_menu.build(h.t, h.f, {})[0]}
        self.assertEqual(by["cool_fill"]["flag"], "d")

    def test_parse_command(self):
        from ets2bakim.service_menu import parse_command
        self.assertEqual(parse_command("oil_topup?grade=10w40&liters=1.5"), ("oil_topup", {"grade": "10w40", "liters": 1.5}))
        self.assertEqual(parse_command("oil_change?grade=5w30&filter=1"), ("oil_change", {"grade": "5w30", "filter": True}))
        self.assertEqual(parse_command("battery_charger?on=0"), ("battery_charger", {"on": False}))
        self.assertEqual(parse_command("truck_reset"), (None, None))      # listede olmayan işlem reddedilir
        self.assertEqual(parse_command(""), (None, None))

    def test_menu_commands_apply(self):
        from ets2bakim import service_menu
        h = self._parked()
        h.t.oil.volume_l = h.t.oil.capacity_l - 4.0
        by = {i["key"]: i for i in service_menu.build(h.t, h.f, {})[0]}
        for key in ("oil_fill", "oil_change_5w30", "batt_replace_agm", "cool_change_si_oat", "tire_drive_retread"):
            name, params = service_menu.parse_command(by[key]["cmd"])
            ok, _ = h.t.action(h.f, name, params)
            self.assertTrue(ok, key)
        self.assertEqual(h.t.oil.grade, "5w30")
        self.assertAlmostEqual(h.t.oil.level_frac, 1.0, places=2)
        self.assertEqual(h.t.battery.kind, "agm")
        self.assertEqual(h.t.coolant.type, "si_oat")
        self.assertEqual(h.t.tires.groups["drive"]["tier"], "retread")
        self.assertNotIn("tire_steer_retread", by)                        # kaplama ön dingile takılmaz

    def test_service_channel(self):
        import struct
        from multiprocessing import shared_memory
        from ets2bakim.overlay_feed import OverlayBridge, SVC_CMD_OFF, SVC_SEQ_OFF
        ovl = shared_memory.SharedMemory(name="Local\\EBKTestOvl2", create=True, size=4096)
        b = OverlayBridge(state_name="Local\\EBKTestState2", ovl_name="Local\\EBKTestOvl2")
        try:
            ovl.buf[0:8] = b"EBKOVL01"
            struct.pack_into("<I", ovl.buf, SVC_SEQ_OFF, 4)       # eski komut: açılışta uygulanmamalı
            b._poll_overlay()
            self.assertIsNone(b.take_service())
            cmd = b"oil_topup?grade=10w40&liters=1"
            ovl.buf[SVC_CMD_OFF:SVC_CMD_OFF + len(cmd) + 1] = cmd + b"\0"
            struct.pack_into("<I", ovl.buf, SVC_SEQ_OFF, 5)
            b._poll_overlay()
            self.assertEqual(b.take_service(), (5, "oil_topup?grade=10w40&liters=1"))
            self.assertIsNone(b.take_service())
            b.set_result(5, True, "1 L eklendi")
            S, D = OverlayFeedTests()._state()
            b.publish(S, D, [], {}, ([dict(key="a", cmd="oil_sample", label="X", detail="Y", flag="n")], ("ipucu", "g")))
            st = shared_memory.SharedMemory(name="Local\\EBKTestState2", create=False)
            length = struct.unpack_from("<I", st.buf, 12)[0]
            payload = bytes(st.buf[64:64 + length]).decode("utf-8").split("\n")
            self.assertIn("u\ta\toil_sample\tX\tY\tn", payload)
            self.assertIn("r\t5\t1\t1 L eklendi", payload)
            self.assertIn("k\tsvc_hint\tipucu\tg\t-1.0000", payload)
            st.close()
        finally:
            b.close()
            ovl.close()
            ovl.unlink()


class LevelColorTests(unittest.TestCase):
    """Değer renkleri: sınırda sarı (w), kritik kırmızı (c); uygulama penceresi ve katman aynı seviyeleri kullanır."""

    def _state(self, prep):
        import types
        from ets2bakim.view import build_detail, build_state
        h = Harness(ambient=-12)
        h.run(10)
        prep(h.t)
        app = types.SimpleNamespace(ambient=-12.0, expected_min=-18.0, lat=59.3, lon=18.1, city="Stockholm",
                                    city_km=4.0, source_name="oyun", source=types.SimpleNamespace(status="Oyuna bağlı"),
                                    settings={}, last_message=None)
        return build_state(app, h.t, h.f), build_detail(h.t)

    def test_low_oil_level_does_not_break_state(self):
        def prep(t):
            t.oil.volume_l = t.oil.capacity_l * 0.80   # MIN altı uyarısı (eskiden durum ekranını çökertiyordu)
            t.coolant.volume_l = t.coolant.capacity_l * 0.75
        S, _ = self._state(prep)
        self.assertEqual(S["levels"]["oil.level_pct"], "w")
        self.assertEqual(S["levels"]["coolant.level_pct"], "w")
        self.assertTrue(any("MIN" in w["text"] for w in S["warnings"]))

    def test_warn_and_crit_levels(self):
        def prep(t):
            t.thermal.t_cool, t.thermal.t_oil = 107.0, 138.0
            t.oil.fe = 120.0
            t.battery.soc, t.battery.soh = 0.45, 0.70
            t.coolant.glycol = 0.30          # donma -15 °C, bölgede beklenen en düşük -18 °C
        S, D = self._state(prep)
        lv = S["levels"]
        self.assertEqual(lv["thermal.t_cool"], "w")
        self.assertEqual(lv["thermal.t_oil"], "c")
        self.assertEqual(lv["oil.fe"], "c")
        self.assertEqual(lv["battery.soc"], "c")
        self.assertEqual(lv["battery.soh"], "w")
        self.assertEqual(lv["coolant.glycol"], "w")
        self.assertIn(lv["coolant.freeze"], ("w", "c"))
        self.assertTrue(set(lv.values()) <= set("gwcmn"))
        self.assertIn("idle", D["session_levels"])

    def test_overlay_uses_same_levels(self):
        from ets2bakim.overlay_feed import SHORT, build_payload
        S, D = self._state(lambda t: setattr(t.oil, "fe", 120.0))
        keys = {}
        for line in build_payload(S, D, [], {}, 1).decode("utf-8").split("\n"):
            p = line.split("\t")
            if p[0] == "k":
                keys[p[1]] = p[3]
        self.assertEqual(keys["fe"], "c")
        for short, path in SHORT.items():
            if short in keys:
                self.assertEqual(keys[short], S["levels"].get(path, "n"), short)


class TelltaleTests(unittest.TestCase):
    """Sanal gösterge lambaları: sensörün göreceği soruna göre sarı/kırmızı yanar, kontak kapalıyken karanlık."""

    def _state(self, prep=None):
        import types
        from ets2bakim.view import build_state
        h = Harness(ambient=15)
        h.run(10, rpm=1200, throttle=0.3, speed=50)
        if prep:
            prep(h.t, h.f)
        app = types.SimpleNamespace(ambient=15.0, expected_min=5.0, lat=50.0, lon=10.0, city="", city_km=0.0,
                                    source_name="oyun", source=types.SimpleNamespace(status=""), settings={},
                                    last_message=None)
        return build_state(app, h.t, h.f)

    def test_healthy_truck_has_no_lamps(self):
        from ets2bakim.telltales import compute
        self.assertEqual(compute(self._state()), {})

    def test_dark_with_ignition_off(self):
        from ets2bakim.telltales import Telltales, compute

        def prep(t, f):
            t.faults.active.append("alternator")
            f.electric_on = f.engine_on = False
        S = self._state(prep)
        self.assertIsNone(compute(S))
        self.assertEqual(Telltales().update(S), [])

    def test_lamps_follow_sensors(self):
        from ets2bakim.telltales import compute

        def prep(t, f):
            t.faults.active += ["alternator", "water_pump"]   # su pompası sızıntısı: seviye düşmeden lamba yok
            t.oil.volume_l = t.oil.capacity_l * 0.80          # MIN altı
            t.thermal.t_cool = 112.0                          # hararet
            f.brake_temp = 350.0
        lamps = compute(self._state(prep))
        self.assertEqual(lamps["batt"], "c")
        self.assertEqual(lamps["oil"], "w")
        self.assertEqual(lamps["cool"], "c")
        self.assertEqual(lamps["stop"], "c")
        self.assertEqual(lamps["brake"], "w")
        self.assertNotIn("eng", lamps)

    def test_hold_prevents_flicker(self):
        from ets2bakim.telltales import HOLD_S, Telltales
        bad = self._state(lambda t, f: setattr(t.oil, "volume_l", t.oil.capacity_l * 0.6))
        good = self._state()
        tt = Telltales()
        self.assertIn(("oil", "c"), tt.update(bad, now=100.0))
        self.assertIn(("oil", "c"), tt.update(good, now=100.0 + HOLD_S / 2))   # eşikte titremez
        self.assertEqual(tt.update(good, now=100.0 + HOLD_S + 0.1), [])

    def test_payload_lines_and_setting(self):
        from ets2bakim.overlay_feed import OverlayBridge
        S = self._state(lambda t, f: t.faults.active.append("alternator"))
        b = OverlayBridge(state_name="Local\\EBKTestLamps", ovl_name="Local\\EBKTestLampsOvl")
        try:
            def lamps(settings):
                b.publish(S, {}, [], settings)
                raw = bytes(b.shm.buf[64:64 + __import__("struct").unpack_from("<I", b.shm.buf, 12)[0]])
                return [ln.split("\t") for ln in raw.decode("utf-8").split("\n") if ln.startswith("t\t")]
            on = lamps({})
            self.assertIn(["t", "batt", "c", "AKÜ"], on)
            self.assertEqual(lamps({"telltales": False}), [])
        finally:
            b.close()


class TireFuelAdBlueTests(unittest.TestCase):
    """Lastik aşınması/basıncı/patlak, AdBlue tüketimi ve yakıtla dolum, yakıt uyarıları."""

    def _harness(self, **kw):
        from ets2bakim.telemetry import DemoSource
        h = Harness(ambient=15)
        h.f.wheels = DemoSource._wheels_6x2()
        h.f.adblue_cap, h.f.fuel_cap, h.f.fuel_l = 64.0, 800.0, 600.0
        h.f.trailer_attached, h.f.cargo_kg = True, 20000
        for k, v in kw.items():
            setattr(h.f, k, v)
        return h

    def test_layout_groups_and_lifted_axle(self):
        from ets2bakim.tires import layout_from_frame
        h = self._harness()
        lay = layout_from_frame(h.f)
        self.assertEqual(set(lay), {"steer", "drive", "tag"})
        self.assertEqual((lay["steer"]["tires"], lay["drive"]["tires"]), (2, 4))   # arkada çift lastik
        for w in h.f.wheels:
            if w["liftable"]:
                w["lift"] = 1.0
        self.assertTrue(layout_from_frame(h.f)["tag"]["lifted"])

    def test_wear_depends_on_pressure_and_surface(self):
        from ets2bakim.tires import Tires
        import random
        def wear(cold_bar=None, surface="road", km=500.0):
            h = self._harness()
            for w in h.f.wheels:
                w["substance"] = surface
            t = Tires()
            t.first_setup(h.f, 0.0, random.Random(1), 15.0)
            if cold_bar:
                t.groups["drive"]["cold_bar"] = cold_bar
            c = dict(ambient=15.0, speed=80.0, mass_t=35.0, decel=0.0, load=0.5, brake_temp=60.0,
                     rng=random.Random(2), random_faults=False)
            for _ in range(100):
                t.step(h.f, 18.0, km / 100, c)
            return t.groups["drive"]["new"] - t.groups["drive"]["tread"]
        base = wear()
        self.assertAlmostEqual(base / 500 * 1000, 0.09, delta=0.05)         # ~0,09 mm / 1000 km
        self.assertGreater(wear(cold_bar=6.0), base * 1.3)                   # düşük basınç omuzları yer
        self.assertGreater(wear(surface="gravel"), base * 1.8)               # çakıl yol

    def test_puncture_leak_and_service(self):
        h = self._harness()
        h.run(1, rpm=1200, throttle=0.4, speed=60)
        t = h.t
        t.tires.groups["drive"]["leak_bph"] = 1.0
        h.run(60 * 3, rpm=1200, throttle=0.4, speed=60)                     # ~3 saat oyun içi
        self.assertLess(t.tires.groups["drive"]["cold_bar"], 8.5 - 2.0)
        h.f.speed_kmh, h.f.engine_on = 0.0, False
        ok, _ = t.action(h.f, "tire_puncture", {})
        self.assertTrue(ok)
        self.assertEqual(t.tires.groups["drive"]["leak_bph"], 0.0)
        self.assertEqual(t.tires.groups["drive"]["cold_bar"], t.tires.groups["drive"]["nominal"])
        cost0 = t.costs_total
        ok, _ = t.action(h.f, "tire_replace", {"axle": "steer"})
        self.assertTrue(ok)
        from ets2bakim import prices
        self.assertAlmostEqual(t.costs_total - cost0, 2 * (prices.TIRE["steer"] + prices.TIRE_MOUNT))

    def test_adblue_consumption_and_station_fill(self):
        h = self._harness()
        h.run(60 * 2, rpm=1300, throttle=0.6, speed=85)
        t = h.t
        self.assertGreater(t.adblue.used_total_l, 0.5)
        ratio = t.adblue.used_total_l / max(1e-6, t.analysis.fuel_l)
        self.assertTrue(0.02 <= ratio <= 0.08, ratio)                         # yakıtın ~%3–7'si
        level = t.adblue.level_l
        t.station_refuel(h.f, 300.0, {"adblue_with_fuel": False})
        self.assertEqual(t.adblue.level_l, level)
        t.station_refuel(h.f, 300.0, {})
        self.assertAlmostEqual(t.adblue.level_l, t.adblue.capacity_l)

    def test_game_consuming_adblue_is_followed(self):
        from ets2bakim.adblue import AdBlue
        from ets2bakim.telemetry import Frame
        ab = AdBlue(level_l=40.0, capacity_l=60.0)
        f = Frame(adblue_cap=60.0, adblue_l=50.0)
        for i in range(10):
            f.adblue_l = 50.0 - i * 0.1
            ab.step(f, 0.0, 0.5, 300.0, True)
        self.assertEqual(ab.source, "game")
        self.assertAlmostEqual(ab.level_l, f.adblue_l)

    def test_warnings_and_lamps(self):
        import types as _t
        from ets2bakim.telltales import compute
        from ets2bakim.view import build_state
        h = self._harness(fuel_l=50.0)
        h.run(5, rpm=1200, throttle=0.3, speed=50)
        t = h.t
        t.adblue.level_l = 3.0
        t.tires.groups["steer"]["tread"] = 1.2
        app = _t.SimpleNamespace(ambient=15.0, expected_min=5.0, lat=50.0, lon=10.0, city="", city_km=0.0,
                                 source_name="oyun", source=_t.SimpleNamespace(status=""), settings={"alert_level": "all"},
                                 last_message=None)
        S = build_state(app, t, h.f)
        lamps = compute(S)
        self.assertEqual(lamps.get("fuel"), "w")
        self.assertEqual(lamps.get("adblue"), "w")
        self.assertEqual(lamps.get("tire"), "c")
        texts = " ".join(w["text"] for w in S["warnings"])
        self.assertIn("yasal", texts)
        self.assertIn("AdBlue", texts)
        self.assertIn("Yakıt", texts)


class CurrencyAndOptionsTests(unittest.TestCase):
    """Para birimi oyunun kaydından okunur ve tutarlar oyunun kuruyla çevrilir; yağ/akü/antifriz/lastik seçenekleri."""

    def _log(self, text, game="Euro Truck Simulator 2"):
        import tempfile
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, game))
        with open(os.path.join(d, game, "game.log.txt"), "w", encoding="utf-8") as fh:
            fh.write(text)
        return [d]

    def test_reads_game_currency_and_converts(self):
        from ets2bakim.currency import CurrencyMonitor, fmt
        docs = self._log('00:00:36.724 : uset g_currency "3"\n00:03:05.286 : uset g_currency "12"\n')
        c = CurrencyMonitor(docs).get({}, "ets2")
        self.assertEqual((c["code"], c["symbol"]), ("TRY", "₺"))                 # son satır geçerli
        self.assertTrue(fmt(1000, c).startswith("₺"))
        self.assertAlmostEqual(c["rate"], 48.729)
        self.assertEqual(CurrencyMonitor(self._log("")).get({}, "ets2")["code"], "EUR")   # kayıt yoksa avro
        usd = CurrencyMonitor(self._log('uset g_currency "0"', "American Truck Simulator")).get({}, "ats")
        self.assertEqual(usd["code"], "USD")
        self.assertGreater(usd["rate"], 1.0)                                       # avro tabanlı fiyat dolara
        man = CurrencyMonitor(docs).get({"currency_mode": "manual", "currency": "TL", "currency_rate": 50}, "ets2")
        self.assertEqual(fmt(10, man), "500 TL")

    def test_service_menu_uses_currency(self):
        from ets2bakim import service_menu
        from ets2bakim.currency import resolve
        h = Harness(ambient=15)
        h.f.speed_kmh, h.f.engine_on = 0.0, False
        code, sym, rate = resolve("ets2", 12)
        items, _ = service_menu.build(h.t, h.f, {}, {"symbol": sym, "rate": rate})
        self.assertTrue(all(i["detail"].startswith("₺") or not i["detail"][:1].isdigit() for i in items if i["flag"] != "h"))

    def test_battery_kinds_age_differently(self):
        from ets2bakim.battery import Battery
        res = {}
        for kind in ("std", "agm"):
            b = Battery(kind=kind)
            for _ in range(500):   # derin deşarj döngüleri
                b.step(600.0, dict(running=False, rpm=0, load_a=60.0, ambient=20.0, alternator_ok=True))
                b.soc = 0.9 if b.soc < 0.3 else b.soc
            res[kind] = (b.soh, b.sulfation)
        self.assertGreater(res["agm"][0], res["std"][0])         # AGM döngüye daha dayanıklı
        self.assertLess(res["agm"][1], res["std"][1])            # daha az sülfatlaşma

    def test_tire_tier_wear_and_price(self):
        import random
        from ets2bakim.tires import Tires
        f = Harness(ambient=15).f
        def wear(tier):
            t = Tires()
            t.first_setup(f, 0.0, random.Random(1), 15.0)
            t.replace("all", tier)
            c = dict(ambient=15.0, speed=80.0, mass_t=35.0, decel=0.0, load=0.5, brake_temp=60.0,
                     rng=random.Random(2), random_faults=False)
            for _ in range(50):
                t.step(f, 18.0, 10.0, c)
            return t.groups["drive"]["new"] - t.groups["drive"]["tread"], t.replace_cost("drive", tier)
        (wp, cp), (wb, cb) = wear("premium"), wear("budget")
        self.assertGreater(wb, wp * 1.2)
        self.assertLess(cb, cp)


class BlowoutEffectTests(unittest.TestCase):
    """Lastik patlaması: ilk anda sert sürüklenme, sonra jant sürtmesi; durunca ve çok oyunculuda etki yok."""

    def _setup(self, axle="steer"):
        from ets2bakim.blowout import BlowoutEffect
        from ets2bakim.telemetry import Frame
        from ets2bakim.tires import Tires
        import random
        t = Tires()
        f = Frame(ok=True, speed_kmh=80.0)
        f.wheels = [dict(steer=True), dict(steer=True), dict(powered=True), dict(powered=True)]
        t.first_setup(f, 0.0, random.Random(1), 15.0)
        t.groups[axle]["blown"] = True
        return BlowoutEffect(random.Random(3)), t, f

    def test_jolt_then_scrape_then_stop(self):
        from ets2bakim.blowout import JOLT_BRAKE, JOLT_S, SCRAPE_BRAKE
        fx, t, f = self._setup()
        b, s = fx.update(t, f, True, 100.0)
        self.assertEqual(b, JOLT_BRAKE)
        self.assertNotEqual(s, 0.0)
        self.assertLessEqual(abs(s), 0.05)               # ölçülü: tır savrulmaz
        b, _ = fx.update(t, f, True, 100.0 + JOLT_S + 0.5)
        self.assertEqual(b, SCRAPE_BRAKE)                # jant sürtmesi
        f.speed_kmh = 1.0
        self.assertEqual(fx.update(t, f, True, 110.0), (0.0, 0.0))

    def test_not_in_multiplayer_and_no_retrigger(self):
        from ets2bakim.blowout import JOLT_S
        fx, t, f = self._setup("drive")
        self.assertEqual(fx.update(t, f, False, 0.0), (0.0, 0.0))    # çok oyunculu / kapalı
        b, _ = fx.update(t, f, True, JOLT_S + 1.0)
        self.assertLess(b, 0.5)                                      # aynı patlak için yeniden sarsıntı yok

    def test_bridge_writes_axes(self):
        import struct
        from ets2bakim.overlay_feed import OverlayBridge
        b = OverlayBridge(state_name="Local\\EBKTestAxes", ovl_name="Local\\EBKTestAxesOvl")
        try:
            b.set_axes(0.55, -0.012)
            brake, steer, _tick = struct.unpack_from("<ffI", b.shm.buf, 28)
            self.assertAlmostEqual(brake, 0.55, places=5)
            self.assertAlmostEqual(steer, -0.012, places=5)
        finally:
            b.close()


class WiperTests(unittest.TestCase):
    """Silecek kademesi tuşlardan izlenir, telemetriyle düzeltilir; akü yükü kademeye göre değişir."""

    class _Inp:
        def __init__(self):
            self.q = []

        def drain(self):
            out, self.q = self.q, []
            return out

    def _frame(self, wipers, paused=False):
        from ets2bakim.telemetry import Frame
        return Frame(ok=True, paused=paused, wipers=wipers, electric_on=True)

    def test_parse_bindings(self):
        from ets2bakim.wipers import parse_bindings
        text = ('config_lines[1]: "mix wipers `keyboard.p?0 || short_press(joy.pov1_down?0) | semantical.wipers?0`"\n'
                'config_lines[2]: "mix wipersback `joy2.b7?0`"\n'
                'config_lines[3]: "mix wipers3 `keyboard.f9?0`"\n')
        b = parse_bindings(text)
        self.assertIn(("fwd", None, "key", ord("P"), False), b)
        self.assertIn(("fwd", None, "pov", "down", True), b)
        self.assertIn(("back", None, "btn", 7, False), b)
        self.assertIn(("set", 3, "key", 0x78, False), b)

    def test_stage_cycle_follows_game(self):
        from ets2bakim.wipers import FAST, INTERVAL, OFF, SLOW, WiperTracker
        inp = self._Inp()
        tr = WiperTracker(inp)
        t = 100.0
        self.assertEqual(tr.update(self._frame(False), now=t), OFF)
        for expect in (INTERVAL, SLOW, FAST):          # P: kapalı → aralıklı → yavaş → hızlı
            inp.q.append(("fwd", None, t))
            tr.update(self._frame(expect != INTERVAL), now=t + 0.05)  # telemetri bir adım geriden gelebilir
            t += 1.0
            self.assertEqual(tr.update(self._frame(True), now=t), expect)
        inp.q.append(("fwd", None, t))                 # hızlı → kapalı
        t += 1.0
        self.assertEqual(tr.update(self._frame(False), now=t), OFF)

    def test_quick_double_press_and_resync(self):
        from ets2bakim.wipers import INTERVAL, OFF, SLOW, WiperTracker
        inp = self._Inp()
        tr = WiperTracker(inp)
        inp.q += [("fwd", None, 10.0), ("fwd", None, 10.1)]
        tr.update(self._frame(False), now=10.15)       # telemetri henüz "kapalı": basışlar silinmez
        self.assertEqual(tr.update(self._frame(True), now=11.0), SLOW)
        self.assertEqual(tr.update(self._frame(False), now=20.0), OFF)   # oyun kapattı: kademe sıfır
        self.assertEqual(tr.update(self._frame(True), now=30.0), INTERVAL)  # basış kaçsa da en az aralıklı
        inp.q.append(("fwd", None, 31.0))
        self.assertEqual(tr.update(self._frame(True, paused=True), now=32.0), INTERVAL)  # menüde sayılmaz

    def test_battery_load_by_stage(self):
        from ets2bakim.battery import electrical_load_a
        from ets2bakim.wipers import FAST, INTERVAL, SLOW, wiper_current_a
        f = self._frame(True)
        loads = []
        for s in (INTERVAL, SLOW, FAST):
            f.wiper_stage = s
            loads.append(electrical_load_a(f, True, True, ambient=10.0))
        self.assertTrue(loads[0] < loads[1] < loads[2])
        self.assertGreater(wiper_current_a(FAST, -5.0), wiper_current_a(FAST, 5.0))   # kar/buz
        f.wipers = False
        self.assertLess(electrical_load_a(f, True, True), loads[0])


@unittest.skipUnless(sys.platform == "win32", "Windows'a özgü")
class AppControlTests(unittest.TestCase):
    """Akıllı Uygulama Denetimi: durum okuma, imza denetimi ve uygulama durumuna yansıması."""

    def test_signature_status(self):
        from ets2bakim.appcontrol import signature_status
        self.assertEqual(signature_status(sys.executable), "valid")       # python.org: PSF imzalı
        self.assertEqual(signature_status(os.path.abspath(__file__)), "unsigned")
        self.assertEqual(signature_status(r"C:\yok\yok.dll"), "missing")

    def test_check_shape_and_blocked_rule(self):
        from unittest import mock
        from ets2bakim import appcontrol
        with mock.patch.object(appcontrol, "sac_state", return_value="on"), \
                mock.patch.object(appcontrol, "steam_game_dirs", return_value=[]):
            info = appcontrol.check()
        self.assertEqual(info["sac"], "on")
        self.assertFalse(info["overlay_blocked"])           # kurulu katman yok: engellenecek dosya yok
        with mock.patch.object(appcontrol, "sac_state", return_value="on"), \
                mock.patch.object(appcontrol, "steam_game_dirs", return_value=["oyun"]), \
                mock.patch.object(appcontrol.os.path, "isfile", return_value=True), \
                mock.patch.object(appcontrol, "signature_status", return_value="unsigned"):
            info = appcontrol.check()
        self.assertTrue(info["overlay_blocked"])
        self.assertEqual(len(info["installed"]), 1)
        with mock.patch.object(appcontrol, "sac_state", return_value="off"), \
                mock.patch.object(appcontrol, "steam_game_dirs", return_value=["oyun"]), \
                mock.patch.object(appcontrol.os.path, "isfile", return_value=True), \
                mock.patch.object(appcontrol, "signature_status", return_value="unsigned"):
            self.assertFalse(appcontrol.check()["overlay_blocked"])   # denetim kapalıyken her şey yüklenir

    def test_status_in_app_state(self):
        app = make_app()
        try:
            ac = app._mode_status()["appcontrol"]
            self.assertIn(ac["sac"], ("on", "eval", "off", None))
            self.assertIn("overlay_blocked", ac)
        finally:
            app.bridge.close()


class MultiplayerModeTests(unittest.TestCase):
    def test_convoy_detected_from_telemetry(self):
        from ets2bakim.multiplayer import MultiplayerDetector
        from ets2bakim.telemetry import Frame
        d = MultiplayerDetector()
        f = Frame(ok=True)
        self.assertIsNone(d.update(f))
        f.mp_offset = 1234
        self.assertEqual(d.update(f), "convoy")
        self.assertIsNone(d.update(f, source_is_game=False))  # demo hiçbir zaman çok oyunculu sayılmaz

    def test_module_scan_works(self):
        import sys
        from ets2bakim import multiplayer
        dll = f"python{sys.version_info.major}{sys.version_info.minor}.dll"
        self.assertTrue(multiplayer._has_module(os.getpid(), (dll,)))
        self.assertFalse(multiplayer._has_module(os.getpid(), ("core_ets2mp.dll",)))

    def _app(self, mode):
        return make_app(game_mode=mode)

    def test_watch_modes(self):
        sp, mp = self._app("tek"), self._app("cok")
        try:
            self.assertTrue(sp.enforce_allowed())               # tek oyunculu: her zaman tam izleme
            self.assertFalse(mp.enforce_allowed())              # çok oyunculu varsayılanı: sadece gösterme
            self.assertEqual(mp._mode_status()["watch_mode"], "show")
            mp.settings["mp_watch_mode"] = "full"               # çok oyunculunun kendi seçeneği
            self.assertTrue(mp.enforce_allowed())
            sp.mp.kind = "tmp"  # tek oyunculu uygulama TruckersMP'de açılırsa yalnızca gösterir
            self.assertFalse(sp.enforce_allowed())
            self.assertEqual(sp._mode_warnings()[0]["level"], "warn")
            self.assertEqual(sp._mode_status()["multiplayer"], "tmp")
        finally:
            sp.bridge.close()
            mp.bridge.close()

    def test_stop_engine_only_not_ignition(self):
        app = self._app("tek")
        try:
            sent = []
            app.bridge.input_ready = lambda: True
            app.bridge.send_command = lambda code, cooldown=2.5: sent.append(code) or True
            app._enforce_stop()
            app._enforce_stop()                                 # aç/kapa komutu tekrarlanmaz
            self.assertEqual(sent, [2])                         # 2 = motor durdur; 1 (kontağı kapat) gönderilmez
        finally:
            app.bridge.close()

    def test_multiplayer_full_waits_until_slow(self):
        app = self._app("cok")
        try:
            app.settings["mp_watch_mode"] = "full"
            app.truck = types.SimpleNamespace(killed=True)
            app.frame.engine_on, app.frame.speed_kmh = True, 70.0
            self.assertTrue(any(w["level"] == "crit" for w in app._mode_warnings()))   # önce "güvenli yerde durun"
            app.frame.speed_kmh = 4.0
            self.assertFalse(any(w["level"] == "crit" for w in app._mode_warnings()))
        finally:
            app.bridge.close()


class _FakeMP:
    """Çok oyunculu algılayıcının yerine: oturum türü testte elle verilir (demo hiçbir zaman çok oyunculu sayılmaz)."""

    def __init__(self):
        self.kind = None

    def update(self, frame, source_is_game=True):
        return self.kind

    def recheck(self):
        pass

    @property
    def label(self):
        return {"tmp": "TruckersMP", "convoy": "Konvoy"}.get(self.kind, "")


class GameModeTests(unittest.TestCase):
    """Tek uygulama, iki mod (Ayarlar → Oyun modu: Otomatik / Tek / Çok Oyunculu). Her modun ayarları ve tır kayıtları
    ayrı klasördedir (geçici klasör ve yanındaki _mp); dil ve oyun modu ortaktır. Otomatik'te TruckersMP / Konvoy
    algılanınca Çok Oyunculu moda geçilir."""

    def _frame(self, ok=True):
        from ets2bakim.telemetry import Frame
        return Frame(ok=ok, paused=False, truck_key="vehicle.scania.r|B GF 151" if ok else "", brand="Scania", name="R",
                     plate="B GF 151", brand_id="scania", truck_id="vehicle.scania.r", odometer_km=300000.0,
                     fuel_l=500.0, fuel_cap=1000.0, game_minutes=600, electric_on=True)

    def _tick(self, app, f, n=3):
        for _ in range(n):
            app.tick(f, 0.1)

    def test_auto_mode_follows_multiplayer_session(self):
        from ets2bakim import app as app_mod
        from ets2bakim.storage import Storage
        app = make_app()
        app.mp = _FakeMP()
        try:
            home, f = app.home_dir, self._frame()
            self._tick(app, f)
            self.assertEqual((app.mode_setting(), app.game_mode), ("auto", "tek"))
            self.assertEqual(os.path.normpath(app.storage.base), home)
            self.assertTrue(app.settings["drive_modes"])                     # Tek Oyunculu varsayılanı: açık
            app.truck.info["isaret"] = "tek"
            app.update_settings({"rate_global": 2.0})
            # TruckersMP algılandı: Çok Oyunculu modun kendi ayarları (sürüş modları kapalı) ve kendi tır kaydı
            app.mp.kind = "tmp"
            self._tick(app, f)
            self.assertEqual(app.game_mode, "cok")
            self.assertEqual(os.path.normpath(app.storage.base), home + "_mp")
            self.assertFalse(app.settings["drive_modes"])
            self.assertEqual(app.settings["rate_global"], 1.0)
            self.assertNotIn("isaret", app.truck.info)
            self.assertFalse(app.enforce_allowed())                           # sadece gösterme
            self.assertFalse(app.film_available())
            app.update_settings({"language": "de"})                           # ortak: Tek Oyunculu dosyasına da yazılır
            # algılama bir an kaçarsa hemen dönülmez; uzun süre algılanmazsa Tek Oyunculu'ya dönülür
            app.mp.kind = None
            self._tick(app, f)
            self.assertEqual(app.game_mode, "cok")
            self.assertFalse(app.enforce_allowed())                           # bu arada da motor durdurulmaz
            app._mp_seen -= app_mod.MODE_BACK_S + 1
            self._tick(app, f)
            self.assertEqual(app.game_mode, "tek")
            self.assertEqual(app.settings["rate_global"], 2.0)                 # Tek Oyunculu ayarları geri geldi
            self.assertEqual(app.settings["language"], "de")
            self.assertEqual(app.truck.info.get("isaret"), "tek")             # Tek Oyunculu tırın kendi kaydı
            self.assertTrue(os.path.isfile(Storage(home + "_mp").truck_path(f.truck_key)))   # Çok Oyunculu tır kaydedildi
            # oyun kapalıyken son mod korunur; yeni oturum (tek oyunculu) beklemeden Tek Oyunculu açılır
            app.mp.kind = "tmp"
            self._tick(app, f)
            app.mp.kind = None
            self._tick(app, self._frame(ok=False))
            self.assertEqual(app.game_mode, "cok")
            self._tick(app, f, 1)
            self.assertEqual(app.game_mode, "tek")
        finally:
            app.bridge.close()
            from ets2bakim import i18n
            i18n.set_lang("tr")

    def test_forced_modes_and_command_line(self):
        import json
        from ets2bakim.storage import Storage
        app = make_app(game_mode="cok")                                       # --mod cok: ayar olarak kaydedilir
        app.mp = _FakeMP()
        try:
            home = app.home_dir
            self.assertEqual(Storage(home).load_settings()["game_mode"], "cok")
            self._tick(app, self._frame())
            self.assertEqual(app.game_mode, "cok")                            # algılanmasa da Çok Oyunculu
            app.update_settings({"game_mode": "yok_boyle"})
            self.assertEqual(app.mode_setting(), "cok")                       # geçersiz değer kaydedilmez
            app.update_settings({"game_mode": "tek"})                         # elle seçim hemen uygulanır
            self.assertEqual((app.game_mode, os.path.normpath(app.storage.base)), ("tek", home))
            self.assertEqual(Storage(home + "_mp").load_settings()["game_mode"], "tek")   # ortak ayar iki dosyada
            app.mp.kind = "tmp"                                               # Tek Oyunculu'ya sabit + TruckersMP
            self._tick(app, self._frame())
            self.assertEqual(app.game_mode, "tek")
            self.assertFalse(app.enforce_allowed())                           # güvenlik: yalnızca gösterir
            self.assertIn("Oyun modu", app._mode_warnings()[0]["text"])
            app.update_settings({"game_mode": "auto"})                        # Otomatik'e dönünce o anki oturuma göre
            self.assertEqual(app.game_mode, "cok")
            st = json.loads(app.state_json)["status"]
            self.assertEqual((st["mode"], st["mode_setting"], st["settings"]["drive_modes"]), ("cok", "auto", False))
        finally:
            app.bridge.close()


class LocalServerTests(unittest.TestCase):
    def test_host_header_is_checked(self):
        """DNS yeniden bağlama: başka bir adla gelen istek (Host: kotu.example:<port>) 403 alır, yalnızca 127.0.0.1 ve
        localhost kabul edilir; POST'ta Origin denetimi de sürer. Ayrı, boş bir portta yalıtılmış sunucu (8723'e ve
        açık uygulamaya dokunulmaz)."""
        import http.client
        import json
        import threading
        from ets2bakim import app as app_mod
        app = make_app()
        httpd = app_mod.ExclusiveHTTPServer(("127.0.0.1", 0), app_mod.make_handler(app))
        threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        port = httpd.server_address[1]
        self.assertNotEqual(port, 8723)

        def req(method, path, host, origin=None, body=None):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            try:
                h = {"Host": host}
                if origin:
                    h["Origin"] = origin
                data = json.dumps(body).encode() if body is not None else None
                if data is not None:
                    h["Content-Type"] = "application/json"
                c.request(method, path, body=data, headers=h)
                r = c.getresponse()
                return r.status, r.read()
            finally:
                c.close()
        try:
            for host in (f"127.0.0.1:{port}", f"localhost:{port}", f"LOCALHOST:{port}"):
                self.assertEqual(req("GET", "/api/state", host)[0], 200, host)
            self.assertEqual(req("GET", "/", f"127.0.0.1:{port}")[0], 200)
            for host in (f"kotu.example:{port}", "127.0.0.1", f"127.0.0.1:{port + 1}", f"127.0.0.1.kotu.example:{port}", ""):
                for path in ("/api/state", "/api/detail", "/api/history", "/"):
                    self.assertEqual(req("GET", path, host)[0], 403, (host, path))
            self.assertEqual(req("POST", "/api/settings", f"kotu.example:{port}", body={"sound": False})[0], 403)
            self.assertEqual(req("POST", "/api/settings", f"127.0.0.1:{port}", origin="http://kotu.example",
                                 body={"sound": False})[0], 403)
            self.assertTrue(app.settings["sound"])                            # reddedilen istekler ayar değiştirmedi
            status, body = req("POST", "/api/settings", f"localhost:{port}", origin=f"http://localhost:{port}",
                               body={"sound": False})
            self.assertEqual(status, 200, body)
            self.assertFalse(app.settings["sound"])
        finally:
            httpd.shutdown()
            httpd.server_close()
            app.bridge.close()

    def test_post_length_is_checked(self):
        """Geçersiz (negatif / sayı olmayan) ya da çok büyük Content-Length hemen reddedilir; sunucu bağlantı kapanana
        kadar gövde beklemez."""
        import http.client
        import threading
        from ets2bakim import app as app_mod
        app = make_app()
        httpd = app_mod.ExclusiveHTTPServer(("127.0.0.1", 0), app_mod.make_handler(app))
        threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        port = httpd.server_address[1]
        try:
            for length, want in (("-1", 400), ("abc", 400), (str(app_mod.MAX_POST_BYTES + 1), 413)):
                c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                try:
                    c.putrequest("POST", "/api/settings", skip_host=True)
                    c.putheader("Host", f"127.0.0.1:{port}")
                    c.putheader("Content-Length", length)
                    c.endheaders()
                    self.assertEqual(c.getresponse().status, want, length)
                finally:
                    c.close()
            self.assertTrue(app.settings["sound"])
        finally:
            httpd.shutdown()
            httpd.server_close()
            app.bridge.close()


class GameServiceRepairTests(unittest.TestCase):
    def _truck(self):
        h = Harness(ambient=10)
        h.run(2)
        h.t.faults.active += ["alternator", "fan_clutch"]
        h.f.wear = dict(engine=0.20, transmission=0.05, cabin=0.1, chassis=0.1, wheels=0.02)
        h.run(0.2, engine=False, speed=0)   # oyun hasarlarının önceki değeri kaydedilir
        return h

    def test_repair_at_game_service_fixes_parts(self):
        h = self._truck()
        cost0 = h.t.costs_total
        h.f.wear = dict(engine=0.0, transmission=0.0, cabin=0.0, chassis=0.0, wheels=0.0)
        h.run(0.2, engine=False, speed=0)
        self.assertEqual(h.t.faults.active, [])
        self.assertGreater(h.t.costs_total, cost0)
        msgs = [e["m"] for e in h.t.log[-4:]]
        self.assertIn("Oyundaki serviste tamir yapıldı (oyun hasarı %{d:.0f} azaldı).", msgs)
        self.assertIn("Oyundaki serviste onarıldı: {name_t}.", msgs)

    def test_cabin_only_repair_is_detected(self):
        h = self._truck()
        h.f.wear = dict(h.f.wear, cabin=0.0)
        h.run(0.2, engine=False, speed=0)
        self.assertEqual(h.t.faults.active, [])

    def test_setting_off_keeps_faults(self):
        h = self._truck()
        h.settings["repair_faults_on_game_repair"] = False
        h.f.wear = dict(engine=0.0, transmission=0.0, cabin=0.0, chassis=0.0, wheels=0.0)
        h.run(0.2, engine=False, speed=0)
        self.assertEqual(sorted(h.t.faults.active), ["alternator", "fan_clutch"])


class GameControlsTests(unittest.TestCase):
    SII = ('SiiNunit\n{\ninput_config : .config {\n'
           ' config_lines[421]: "mix showmirrors `keyboard.f2?0 | semantical.showmirrors?0`"\n'
           ' config_lines[422]: "mix showhud `keyboard.%s?0 | semantical.showhud?0`"\n}\n}\n')

    def test_parse_and_keys(self):
        from ets2bakim import gamecfg
        self.assertEqual(gamecfg.parse_mix_key(self.SII % "f3"), 0x72)
        self.assertEqual(gamecfg.parse_mix_key(self.SII % "h"), ord("H"))
        self.assertEqual(gamecfg.parse_mix_key(self.SII % "del"), 0x2E)
        self.assertIsNone(gamecfg.parse_mix_key("mix other `keyboard.f3?0`"))
        self.assertEqual(gamecfg.key_to_vk("F12"), 0x7B)

    def test_latest_profile_is_used(self):
        import tempfile
        import time
        from ets2bakim import gamecfg
        with tempfile.TemporaryDirectory() as doc:
            old = os.path.join(doc, "Euro Truck Simulator 2", "profiles", "A1")
            new = os.path.join(doc, "Euro Truck Simulator 2", "steam_profiles", "B2")
            for d, key in ((old, "f3"), (new, "f10")):
                os.makedirs(d)
                with open(os.path.join(d, "controls.sii"), "w", encoding="utf-8") as fh:
                    fh.write(self.SII % key)
            t = time.time()
            os.utime(os.path.join(old, "controls.sii"), (t - 100, t - 100))
            self.assertEqual(gamecfg.find_controls([doc]), os.path.join(new, "controls.sii"))
            self.assertEqual(gamecfg.HudKey([doc]).get(), 0x79)
        self.assertEqual(gamecfg.HudKey([]).get(), gamecfg.DEFAULT_HUD_VK)


class I18nTests(unittest.TestCase):
    def tearDown(self):
        from ets2bakim import i18n
        i18n.set_lang("tr")

    def test_numbers_and_messages(self):
        from ets2bakim import i18n
        from ets2bakim.i18n import M, N, T, render
        msg = M("Yağ seviyesi MIN altında (%{lvl:.0f}, {v:.1f} L). Yağ ekleyin.", lvl=81, v=32.5)
        i18n.set_lang("tr")
        self.assertEqual(render(msg), "Yağ seviyesi MIN altında (%81, 32,5 L). Yağ ekleyin.")
        self.assertEqual(N(412350.6, 1), "412.350,6")
        i18n.set_lang("en")
        self.assertEqual(render(msg), "Oil level below MIN (81%, 32.5 L). Top up oil.")
        self.assertEqual(N(412350.6, 1), "412,350.6")
        i18n.set_lang("de")
        self.assertEqual(render(msg), "Ölstand unter MIN (81 %, 32,5 L). Öl nachfüllen.")
        self.assertEqual(T("ARIZA: {name_t} — {desc_t}", name_t="Alternatör arızası", desc_t="Soğutma suyu yavaş yavaş eksilir."),
                         "DEFEKT: Lichtmaschinendefekt — Kühlmittel geht langsam verloren.")
        self.assertEqual(i18n.city("Münih"), "München")

    def test_every_translation_formats(self):
        """Her çevirinin yer tutucuları Türkçe şablonla aynı olmalı."""
        import string
        from ets2bakim.i18n import TRANS
        names = lambda s: sorted(f[1] for f in string.Formatter().parse(s) if f[1])
        for msgid, (en, de) in TRANS.items():
            self.assertEqual(names(msgid), names(en), msgid)
            self.assertEqual(names(msgid), names(de), msgid)

    def test_events_follow_language(self):
        from ets2bakim import i18n
        from ets2bakim.view import build_state
        import types
        h = Harness(ambient=15)
        h.t.event(h.f, "info", __import__("ets2bakim.i18n", fromlist=["M"]).M("Yağ filtresi değişti."))
        app = types.SimpleNamespace(ambient=15.0, expected_min=0.0, lat=52.5, lon=13.4, city="Münih", city_km=3.0,
                                    source_name="oyun", source=types.SimpleNamespace(status="Oyuna bağlı"),
                                    settings={"alert_level": "all"}, last_message=None)
        i18n.set_lang("en")
        S = build_state(app, h.t, h.f)
        self.assertEqual(S["log"][0]["text"], "Oil filter changed.")
        self.assertEqual(S["location"]["city"], "Munich")
        self.assertEqual(S["status"]["text"], "Connected to game")

    def test_legacy_plain_log_entries_follow_language(self):
        """Çok dil desteğinden önceki düz Türkçe olay kayıtları şablona çevrilir, seçili dilde görünür."""
        from ets2bakim import i18n
        legacy = {"gm": 1, "odo": 71175.0, "level": "warn", "kind": "servis", "cost": 0,
                  "text": "Kamyon ilk kez görüldü (71.175 km). Bakım geçmişi bilinmiyor: yağ analizi ve genel kontrol "
                          "önerilir."}
        e = i18n.upgrade_log_entry(legacy)
        self.assertNotIn("text", e)
        i18n.set_lang("en")
        self.assertEqual(i18n.render({"m": e["m"], "a": e["a"]}),
                         "Truck seen for the first time (71,175 km). Service history unknown: an oil analysis and "
                         "general check are recommended.")
        i18n.set_lang("tr")
        self.assertEqual(i18n.render({"m": e["m"], "a": e["a"]}), legacy["text"])        # Türkçe birebir aynı
        odd = {"gm": 1, "text": "elle yazılmış, şablonu olmayan bir not"}
        self.assertEqual(i18n.upgrade_log_entry(odd), odd)                               # eşleşmeyen dokunulmaz
        h = Harness(ambient=15)
        d = h.t.to_dict()
        d["log"] = [legacy]
        self.assertIn("m", TruckModel.from_dict(d).log[0])                               # yüklerken çevrilir

    def test_window_title_and_cities_follow_language(self):
        from ets2bakim import i18n, window
        self.assertEqual(window.title(False, "en"), "ETS2 Maintenance Simulator")
        self.assertEqual(window.title(True, "de"), "ETS2 Wartungssimulator (Demo)")
        titles = window._all_titles()
        self.assertIn("ETS2 Bakım Simülatörü", titles)
        self.assertIn("ETS2 Wartung – Einzelspieler", titles)                          # 1.1'in açık penceresi de bulunur
        self.assertIn("ETS2 Maintenance – Multiplayer (Demo)", titles)
        i18n.set_lang("en")
        self.assertEqual(i18n.render(i18n.M("Yeni yolculuk: {src} → {dst}.", src="İstanbul", dst="Münih")),
                         "New trip: Istanbul → Munich.")

    def test_waiting_state_carries_language(self):
        """Oyun kapalıyken (bekleme ekranı, Ayarlar) seçilen dil de arayüze gitmeli; gitmezse sayfa Türkçe kalıyordu."""
        import json
        app = make_app()
        try:
            self.assertEqual(json.loads(app.state_json)["status"]["lang"], "tr")       # "Başlatılıyor…"
            app.update_settings({"language": "de"})
            app._publish_waiting()
            st = json.loads(app.state_json)["status"]
            self.assertEqual(st["lang"], "de")
            self.assertEqual(st["drive"]["modes"][0]["desc"], "Leistung auf 75 % begrenzt, sanftes Gas, 85 km/h Begrenzung")
        finally:
            app.bridge.close()

    def test_page_is_served_in_selected_language(self):
        """index.html seçili dille (<html lang>) verilir: sayfa ilk durum yanıtından önce de doğru dilde açılır."""
        import threading
        import urllib.request
        from ets2bakim import app as app_mod
        app = make_app()
        httpd = app_mod.ExclusiveHTTPServer(("127.0.0.1", 0), app_mod.make_handler(app))   # boş port: gerçek uygulamaya dokunmaz
        threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{httpd.server_address[1]}/"
            app.update_settings({"language": "en"})
            with urllib.request.urlopen(url, timeout=5) as r:
                self.assertIn('<html lang="en">', r.read().decode("utf-8"))
            app.update_settings({"language": "tr"})
            with urllib.request.urlopen(url, timeout=5) as r:
                self.assertIn('<html lang="tr">', r.read().decode("utf-8"))
        finally:
            httpd.shutdown()
            httpd.server_close()
            app.bridge.close()

    def test_web_dictionary_covers_page(self):
        """Arayüzdeki her sabit metnin web/i18n.js'de karşılığı olmalı ve sözlükte aynı anahtar iki kez geçmemeli (sonraki
        öncekini sessizce ezer: "Yağ değişimi" başlığı "Oil change due" görünüyordu)."""
        import json
        import re
        from html.parser import HTMLParser
        web = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
        with open(os.path.join(web, "i18n.js"), encoding="utf-8") as fh:
            src = fh.read()
        body = src[src.index("const I18N"):src.index("const MONTHS")]
        keys = [json.loads(f'"{k}"') for k in re.findall(r'(?:^|[{,\s])"((?:[^"\\\n]|\\.)*)"\s*:\s*\[', body)]
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        self.assertEqual(dupes, [])
        known = set(keys)
        void = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

        class Page(HTMLParser):
            # translateDom'un gezdiği metinler: data-v / data-s bağlı öğeler, .no-i18n ve dinamik listeler hariç
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.stack, self.missing = [], []

            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                skip = (tag in ("script", "style") or "data-v" in a or "data-s" in a
                        or "no-i18n" in (a.get("class") or "").split()
                        or a.get("id") in ("alerts", "log-body", "lab-body", "fault-list"))
                for v in (a.get("data-b") or "").split("|") + [x.split(":", 1)[-1] for x in (a.get("data-b2") or "").split("|")]:
                    if v and v not in known:
                        self.missing.append(v)
                if tag not in void:
                    self.stack.append((tag, skip))

            def handle_endtag(self, tag):
                for i in range(len(self.stack) - 1, -1, -1):
                    if self.stack[i][0] == tag:
                        del self.stack[i:]
                        break

            def handle_data(self, data):
                text = data.strip()
                if text and not any(s for _, s in self.stack) and re.search(r"[a-zçğıöşü]{3}", text, re.I) \
                        and text not in known:
                    self.missing.append(text)

        page = Page()
        with open(os.path.join(web, "index.html"), encoding="utf-8") as fh:
            page.feed(fh.read())
        as_is = {"ECO", "COMFORT", "SPORT", "Scania", "Volvo", "Mercedes-Benz", "MAN", "DAF", "Renault", "Iveco",
                 "ABS / ESC", "· MIN", "bar"}                                   # her dilde aynı adlar ve birimler
        self.assertEqual([t for t in page.missing if t not in as_is], [])

    def test_alert_levels(self):
        from ets2bakim.view import filter_warnings
        ws = [{"level": "crit"}, {"level": "warn"}, {"level": "info"}]
        self.assertEqual(len(filter_warnings(ws, "minimal")), 1)
        self.assertEqual(len(filter_warnings(ws, "normal")), 2)
        self.assertEqual(len(filter_warnings(ws, "all")), 3)


class QuickJobTests(unittest.TestCase):
    def _app(self):
        return make_app()

    def test_quick_job_truck_resets_on_delivery(self):
        app = self._app()
        try:
            h = Harness(ambient=15)
            h.f.on_job, h.f.job_market = True, "quick_job"
            app.frame, app.truck = h.f, h.t
            h.run(5)
            self.assertTrue(h.t.temporary)
            h.t.oil.volume_l = 20.0
            app._check_job_events(h.f)          # başlangıç bayrakları
            h.f.ev_delivered = not h.f.ev_delivered
            app._check_job_events(h.f)          # teslimat olayı
            self.assertIsNot(app.truck, h.t)
            self.assertGreater(app.truck.oil.volume_l, 30.0)
        finally:
            app.bridge.close()

    def test_own_truck_is_kept(self):
        app = self._app()
        try:
            h = Harness(ambient=15)
            h.f.on_job, h.f.job_market = True, "freight_market"
            app.frame, app.truck = h.f, h.t
            h.run(5)
            self.assertFalse(h.t.temporary)
            app._check_job_events(h.f)
            h.f.ev_delivered = not h.f.ev_delivered
            app._check_job_events(h.f)
            self.assertIs(app.truck, h.t)
        finally:
            app.bridge.close()


class RateTests(unittest.TestCase):
    """Azalma hızı çarpanları: genel × sistem; 0,5 yarı hızda, 0 hiç azalmaz; aralıklar ve bakım planı uzar."""

    def _harness(self, **rates):
        from ets2bakim.telemetry import DemoSource
        h = Harness(ambient=15, odo=200000)
        h.f.wheels = DemoSource._wheels_6x2()
        h.f.adblue_cap, h.f.fuel_cap, h.f.fuel_l = 64.0, 800.0, 600.0
        h.f.trailer_attached, h.f.cargo_kg = True, 20000
        h.t.spec.has_dpf = True
        h.settings.update({"rate_" + k.rstrip("_"): v for k, v in rates.items()})   # global_ -> rate_global
        return h

    def _snap(self, t):
        return dict(tbn=t.oil.tbn, soot=t.oil.soot, ox=t.oil.ox, vol=t.oil.volume_l, inh=t.coolant.inhibitor,
                    soh=t.battery.soh, sulf=t.battery.sulfation, health=t.health.health, dpf=t.dpf.soot_g,
                    ash=t.dpf.ash_g, adblue=t.adblue.level_l,
                    tread={g: s["tread"] for g, s in t.tires.groups.items()},
                    ages=dict(t.faults.ages_km), filt=t.oil.filter_km)

    def _drive(self, h, minutes=240):
        start_engine(h)
        s0 = self._snap(h.t)
        km0, okm0 = h.f.odometer_km, h.t.oil.km
        h.run(minutes)
        return s0, self._snap(h.t), h.f.odometer_km - km0, h.t.oil.km - okm0

    def test_rates_combine_and_clamp(self):
        from ets2bakim import rates
        self.assertAlmostEqual(rates.get({"rate_global": 0.5, "rate_oil": 2.0}, "oil"), 1.0)
        self.assertAlmostEqual(rates.get({}, "tires"), 1.0)
        self.assertAlmostEqual(rates.get({"rate_tires": 99}, "tires"), rates.MAX)
        self.assertAlmostEqual(rates.get({"rate_tires": "x"}, "tires"), 1.0)
        self.assertIsNone(rates.stretch(60000, 0.0))
        self.assertAlmostEqual(rates.stretch(60000, 0.5), 120000)
        self.assertAlmostEqual(rates.interval_end(20000, 20000, 60000, 0.5), 100000)   # kalan 40.000 -> 80.000 km
        self.assertIsNone(rates.interval_end(20000, 20000, 60000, 0.0))

    def test_settings_have_all_rates_and_are_clamped(self):
        from ets2bakim import rates
        from ets2bakim.storage import DEFAULT_SETTINGS
        for k in ("global",) + rates.KEYS:
            self.assertEqual(DEFAULT_SETTINGS["rate_" + k], 1.0)
        app = make_app()
        ok, _ = app.update_settings({"rate_oil": 9, "rate_tires": -1, "rate_dpf": "0.25"})
        self.assertTrue(ok)
        self.assertEqual((app.settings["rate_oil"], app.settings["rate_tires"], app.settings["rate_dpf"]),
                         (rates.MAX, 0.0, 0.25))

    def test_half_rate_halves_decline(self):
        a0, a1, km_a, okm_a = self._drive(self._harness())
        b0, b1, km_b, okm_b = self._drive(self._harness(global_=1.0, oil=0.5, coolant=0.5, tires=0.5, engine=0.5,
                                                        dpf=0.5, adblue=0.5))
        self.assertAlmostEqual(km_a, km_b, places=3)
        self.assertAlmostEqual(okm_a, okm_b, places=3)            # gidilen km gerçek kalır
        ratio = lambda k: (b0[k] - b1[k]) / (a0[k] - a1[k])
        import math
        self.assertAlmostEqual(math.log(b0["tbn"] / b1["tbn"]) / math.log(a0["tbn"] / a1["tbn"]), 0.5, delta=0.03)
        self.assertAlmostEqual((b1["soot"] - b0["soot"]) / (a1["soot"] - a0["soot"]), 0.5, delta=0.03)
        self.assertAlmostEqual(ratio("vol"), 0.5, delta=0.05)
        self.assertAlmostEqual(ratio("inh"), 0.5, delta=0.03)
        self.assertAlmostEqual(ratio("health"), 0.5, delta=0.05)
        self.assertAlmostEqual(ratio("adblue"), 0.5, delta=0.03)
        for g in a0["tread"]:
            if a0["tread"][g] > a1["tread"][g]:
                self.assertAlmostEqual((b0["tread"][g] - b1["tread"][g]) / (a0["tread"][g] - a1["tread"][g]), 0.5, delta=0.05)
        self.assertAlmostEqual((b1["filt"] - b0["filt"]) / (a1["filt"] - a0["filt"]), 0.5, places=3)

    def test_zero_rate_freezes_values(self):
        h = self._harness(global_=0.0)
        h.settings["random_faults"] = True
        s0, s1, km, _ = self._drive(h)
        self.assertGreater(km, 100)
        for k in ("tbn", "soot", "ox", "vol", "inh", "health", "adblue", "ash", "filt"):
            self.assertEqual(s0[k], s1[k], k)
        self.assertEqual(s0["tread"], s1["tread"])
        self.assertEqual(s0["ages"], s1["ages"])                 # parça yaşları ilerlemez: rastgele arıza yok
        self.assertLessEqual(s1["dpf"], s0["dpf"])                # DPF dolmaz (yalnız yanar)
        self.assertGreaterEqual(s1["soh"], s0["soh"])
        self.assertFalse(h.t.faults.active)
        self.assertEqual(h.t.oil.life_breakdown()["Değişim aralığı (km)"], 1 - h.t.oil.wear_km / h.t.oil.spec["interval_km"])

    def test_drain_rate_slows_parked_discharge(self):
        def drop(drain):
            h = Harness(ambient=15)
            h.settings["rate_drain"] = drain
            h.t.battery.soc = 0.9
            h.parked(4, electric=True, parking=True)
            return 0.9 - h.t.battery.soc
        full, half, none = drop(1.0), drop(0.5), drop(0.0)
        self.assertGreater(full, 0.05)
        self.assertAlmostEqual(half / full, 0.5, delta=0.05)
        self.assertLess(none, full * 0.05)                         # yalnız kendi kendine boşalma

    def test_forecast_and_intervals_stretch(self):
        from ets2bakim.view import forecast
        h = self._harness()
        start_engine(h)
        h.run(120)
        t = h.t
        def km_of(R, name):
            return next(i for i in forecast(t, t.analysis, R)["items"] if i["name"] == name)
        one, half = km_of({"oil": 1.0}, "Yağ değişimi"), km_of({"oil": 0.5}, "Yağ değişimi")
        self.assertAlmostEqual(half["km"], 2 * one["km"], delta=1)
        self.assertAlmostEqual(half["days"], 2 * one["days"], delta=0.1)
        self.assertIsNone(km_of({"oil": 0.0}, "Yağ değişimi")["km"])
        c1, c2 = km_of({"coolant": 1.0}, "Soğutma sıvısı değişimi"), km_of({"coolant": 0.25}, "Soğutma sıvısı değişimi")
        self.assertAlmostEqual(c2["km"], 4 * c1["km"], delta=1)
        b1, b2 = km_of({}, "Akü değişimi"), km_of({"battery": 0.5}, "Akü değişimi")
        self.assertAlmostEqual(b2["days"], 2 * b1["days"], delta=0.1)

    def test_state_shows_stretched_interval(self):
        from ets2bakim.view import build_state
        app = make_app()
        h = self._harness()
        start_engine(h)
        h.run(60)
        app.truck, app.frame = h.t, h.f
        app.settings.update(rate_global=1.0, rate_oil=0.5, rate_coolant=0.0)
        S = build_state(app, h.t, h.f)
        o, iv = h.t.oil, h.t.oil.spec["interval_km"]
        self.assertGreater(o.wear_km, 1000)                       # şimdiye kadar 1× hızda kullanılmış kısım
        self.assertAlmostEqual(S["oil"]["interval_km"], o.km + (iv - o.wear_km) / 0.5, delta=1)   # kalan iki katı
        app.settings["rate_oil"] = 1.0
        self.assertAlmostEqual(build_state(app, h.t, h.f)["oil"]["interval_km"], iv, delta=1)
        self.assertIsNone(S["coolant"]["life_km"])
        self.assertEqual(S["rates"]["oil"], 0.5)
        self.assertEqual(S["oil"]["interval_used"], round(h.t.oil.wear_km / h.t.oil.spec["interval_km"] * 100))

    def test_old_save_migrates_interval_counters(self):
        h = Harness(ambient=5, odo=300000)
        d = h.t.to_dict()
        for k in ("oil", "coolant"):
            d[k].pop("wear_km")
            d[k].pop("wear_min")
        t2 = TruckModel.from_dict(d)
        self.assertGreater(t2.oil.km, 0)
        self.assertEqual((t2.oil.wear_km, t2.oil.wear_min), (t2.oil.km, t2.oil.minutes_age))
        self.assertEqual((t2.coolant.wear_km, t2.coolant.wear_min), (t2.coolant.km, t2.coolant.minutes_age))
        self.assertAlmostEqual(t2.oil.life()[0], h.t.oil.life()[0])


class DriveModeTests(unittest.TestCase):
    """Sürüş modları (ECO / COMFORT / SPORT): parametreler, mod tuşu ataması, tuşla mod değiştirme, katman başlığı."""

    def test_params_and_cycle(self):
        from ets2bakim import drivemode as dm
        self.assertEqual(dm.header_params({}), (2, 1.0, 1.5, 0.0, 1.0))                  # varsayılan COMFORT
        self.assertEqual(dm.header_params({"drive_mode": "eco"}), (1, 0.75, 0.6, 85.0, 1.0))
        self.assertEqual(dm.header_params({"drive_mode": "sport"})[0], 3)
        self.assertEqual(dm.header_params({"drive_mode": "eco", "drive_modes": False})[0], 0)   # kapalı: gaza karışılmaz
        self.assertEqual([dm.next_mode(m) for m in dm.ORDER], ["comfort", "sport", "eco"])
        self.assertEqual(dm.next_mode("bilinmeyen"), "comfort")

    def test_bindings(self):
        from ets2bakim import drivemode as dm
        self.assertEqual(dm.parse_binding("key:121"), ("key", 121))
        self.assertEqual(dm.parse_binding("btn:5"), ("btn", 5))
        self.assertEqual(dm.parse_binding("pov:up"), ("pov", "up"))
        for bad in ("", None, "key:119", "key:27", "btn:0", "btn:40", "pov:x", "abc"):   # F8 ve Esc atanamaz
            self.assertIsNone(dm.parse_binding(bad), bad)
        self.assertEqual(dm.format_binding("btn", 7), "btn:7")
        self.assertIn("5", dm.binding_label("btn:5"))
        self.assertTrue(dm.binding_label("key:121"))

    def test_capture_and_presses(self):
        from ets2bakim.drivemode import DriveModeInput
        d = DriveModeInput()
        d.start_capture(now=0.0)
        d.poll(0.1, {("key", 0x41)})            # atama başlarken basılı tuş sayılmaz
        d.poll(0.2, {("key", 0x41)})
        self.assertIsNone(d.take_captured())
        d.poll(0.3, {("key", 0x41), ("key", 0x77)})   # F8 atanamaz
        self.assertTrue(d.capturing)
        d.poll(0.4, {("btn", 5)})
        self.assertFalse(d.capturing)
        self.assertEqual(d.take_captured(), "btn:5")
        d.start_capture(now=1.0)
        d.poll(1.1, set())
        d.poll(1.2, {("key", 0x1B)})            # Esc: iptal
        self.assertEqual(d.take_captured(), "")
        d.start_capture(now=2.0)
        d.poll(2.1, set())
        d.poll(13.0, set())                      # 10 sn doldu
        self.assertEqual(d.take_captured(), "")
        d.set_binding("btn:5")
        for t, pressed in [(20.0, {("btn", 5)}), (20.1, {("btn", 5)}), (20.2, set()), (20.3, {("btn", 5)})]:
            d.poll(t, pressed)
        self.assertEqual(d.drain(), 2)           # basılı tutmak tek basış sayılır
        self.assertEqual(d.drain(), 0)

    def test_app_cycles_mode_saves_key_and_writes_header(self):
        import struct
        app = make_app()
        app.frame.paused = False
        self.assertEqual(app.settings["drive_mode"], "comfort")
        app.drive.presses.extend([1.0, 1.1])     # iki basış: COMFORT → SPORT → ECO
        app._drive_step()
        self.assertEqual(app.settings["drive_mode"], "eco")
        self.assertIn("ECO", app.last_message["text"])
        mode, cap, rate, vlim, curve, tick = struct.unpack_from("<IffffI", app.bridge.shm.buf, 40)
        self.assertEqual((mode, round(cap, 2), round(rate, 2), vlim), (1, 0.75, 0.6, 85.0))
        app.frame.paused = True                  # menüdeyken tuş modu değiştirmez
        app.drive.presses.append(2.0)
        app._drive_step()
        self.assertEqual(app.settings["drive_mode"], "eco")
        ok, _ = app.drive_capture(True)
        self.assertTrue(ok and app.drive.capturing)
        self.assertTrue(app._drive_status()["capturing"])
        app.drive.poll(10.0, set())
        app.drive.poll(10.1, {("pov", "left")})
        app._drive_step()
        self.assertEqual(app.settings["drive_mode_key"], "pov:left")
        self.assertEqual(app.drive.binding, ("pov", "left"))
        app.update_settings({"drive_mode": "turbo", "drive_mode_key": "key:119"})   # geçersizler yok sayılır
        self.assertEqual((app.settings["drive_mode"], app.settings["drive_mode_key"]), ("eco", "pov:left"))
        app.update_settings({"drive_modes": False, "drive_mode_key": ""})
        app._drive_step()
        self.assertEqual(struct.unpack_from("<I", app.bridge.shm.buf, 40)[0], 0)   # kapalı: eklenti gaza karışmaz
        self.assertIsNone(app.drive.binding)
        self.assertFalse(app._drive_status()["enabled"])


def vehicle_harness(brand_id, truck_id, name, car_wheels=True, ambient=15.0, odo=0.0):
    """TruckersMP aracı (otomobil / otobüs) için düzenek: telemetrideki marka, kimlik ve tekerlek düzeniyle."""
    import random
    from ets2bakim.telemetry import Frame
    h = Harness.__new__(Harness)
    h.f = Frame(ok=True, paused=False, truck_key=truck_id, odometer_km=odo, fuel_l=50, rpm_max=3000, retarder_steps=0,
                brand_id=brand_id, truck_id=truck_id, name=name)
    w = lambda **k: dict(dict(steer=False, powered=False, liftable=False, lift=0.0, ground=True, steering=0.0,
                              substance="road"), **k)
    h.f.wheels = ([w(steer=True, powered=True), w(steer=True, powered=True), w(), w()] if car_wheels
                  else [w(steer=True), w(steer=True), w(powered=True), w(powered=True)])
    h.t = TruckModel(truck_id, {})
    h.t.first_time_setup(h.f, ambient)
    h.amb = ambient
    h.settings = dict(random_faults=False, hotel_load=True)
    h.rng = random.Random(1)
    return h


class TruckersMPVehicleTests(unittest.TestCase):
    """TruckersMP'nin otomobilleri (Škoda Superb, Scout Extra_D Estate) ve otobüsü (HVT Tourvego 16 SHD)."""

    def test_superb_is_a_12v_car_with_car_parts(self):
        from ets2bakim import oil as oil_mod
        h = vehicle_harness("skoda", "vehicle.skoda.superb", "Superb")
        t = h.t
        self.assertEqual((t.spec.model_key, t.veh, t.spec.engine_id, t.spec.fuel), ("tmp_superb", "car", "20tdi", "diesel"))
        self.assertTrue(t.spec.has_dpf)
        self.assertEqual((t.battery.volts, t.battery.capacity_ah, t.battery.kind), (12, 72.0, "agm"))
        self.assertIn(t.oil.grade, oil_mod.grades_for("car"))
        self.assertEqual(t.coolant.type, "si_oat")
        self.assertAlmostEqual(t.oil.capacity_l, 4.3)
        self.assertEqual(set(t.tires.groups), {"front", "rear"})
        self.assertEqual([t.tires.groups[g]["tires"] for g in ("front", "rear")], [2, 2])
        self.assertAlmostEqual(t.tires.groups["front"]["nominal"], 2.5)
        self.assertTrue(12.2 < t.battery.ocv() < 12.8)
        self.assertAlmostEqual(t.battery.ecu_min_v, 8.0)

    def test_car_runs_with_sane_values(self):
        h = vehicle_harness("skoda", "vehicle.skoda.superb", "Superb")
        start_engine(h)
        self.assertFalse(h.t.killed)
        h.run(120, rpm=1300, throttle=0.35, speed=110)
        t = h.t
        self.assertTrue(13.5 < t.battery.voltage < 14.8, t.battery.voltage)    # 12 V şarj voltajı
        self.assertTrue(75 < t.thermal.t_cool < 105, t.thermal.t_cool)
        self.assertLess(t.oil.fe, 30)                                          # küçük motorda az aşınma metali
        self.assertLess(t.tires.groups["front"]["temp"], 80)
        from ets2bakim.drivemode import header_params
        self.assertEqual(header_params({"drive_mode": "eco"}, "car")[3], 0.0)  # otomobilde ECO hız sınırı yok

    def test_petrol_engine_has_no_dpf_no_preheat(self):
        from ets2bakim import engines
        h = vehicle_harness("skoda", "vehicle.skoda.superb2", "Extra_D Estate", ambient=-15)
        t = h.t
        self.assertEqual(t.spec.model_key, "tmp_scout")
        t.set_engine(engines.engine_by_id(engines.model_by_key("tmp_scout"), "18tsi"))
        self.assertEqual((t.spec.fuel, t.spec.has_dpf), ("petrol", False))
        from ets2bakim.view import preheat_view
        self.assertFalse(preheat_view(t, h.f)["needed"])
        t.battery.temp = t.thermal.t_oil = t.thermal.t_cool = -15
        t.battery.soc = 1.0
        h.f.engine_on, h.f.electric_on = False, True
        h.run(0.1, engine=False)
        h.run(0.2, rpm=700, throttle=0.0, speed=0)                             # beklemeden marş: benzinli çalışır
        self.assertFalse(t.killed, t.kill_reason)

    def test_car_prices_and_menu(self):
        from ets2bakim import oil as oil_mod, service_menu
        h = vehicle_harness("skoda", "vehicle.skoda.superb", "Superb")
        t = h.t
        h.f.engine_on, h.f.speed_kmh = False, 0.0
        ok, _ = t.action(h.f, "oil_change", {"grade": "5w30vw"})
        self.assertTrue(ok)
        self.assertAlmostEqual(t.log[-1]["cost"], round(4.3 * 13.5 + 16 + 35, 2), places=1)
        ok, _ = t.action(h.f, "oil_change", {"grade": "10w40"})                # tır yağı otomobilde de seçilebilir (elle)
        self.assertTrue(ok)
        ok, _ = t.action(h.f, "battery_replace", {"ah": 72, "kind": "agm"})
        self.assertTrue(ok)
        self.assertTrue(180 < t.log[-1]["cost"] < 260, t.log[-1]["cost"])
        self.assertEqual(t.battery.volts, 12)
        items = service_menu.build(t, h.f, {}, None)
        keys = [i["key"] for i in items if "key" in i] if isinstance(items, list) else []
        text = str(items)
        for gid in oil_mod.grades_for("car"):
            self.assertIn(f"oil_change_{gid}", text)
        self.assertNotIn("oil_change_15w40", text)
        self.assertIn("tire_front_premium", text)
        self.assertNotIn("tire_rear_retread", text)                             # otomobile kaplama lastik yok
        del keys

    def test_tourvego_is_a_24v_bus(self):
        h = vehicle_harness("", "vehicle.t16shd", "Tourvego 16 SHD", car_wheels=False)
        t = h.t
        self.assertEqual((t.spec.model_key, t.veh, t.spec.engine_id), ("tmp_tourvego", "bus", "om470_456"))
        self.assertEqual((t.battery.volts, t.battery.capacity_ah), (24, 225.0))
        self.assertTrue(t.spec.has_dpf)
        self.assertNotIn(t.oil.grade, ("5w30vw", "0w20vw", "5w40vw"))
        self.assertEqual(set(t.tires.groups), {"steer", "drive"})

    def test_state_and_overlay_build_for_car(self):
        from ets2bakim.view import build_state
        from ets2bakim.overlay_feed import build_payload
        h = vehicle_harness("skoda", "vehicle.skoda.superb", "Superb")
        start_engine(h)
        h.run(10, rpm=1200, throttle=0.3, speed=60)
        app = make_app()
        app.truck, app.frame = h.t, h.f
        S = build_state(app, h.t, h.f)
        self.assertEqual((S["truck"]["vehicle"], S["battery"]["volts"]), ("car", 12))
        self.assertEqual(S["levels"]["battery.voltage"], "g")                 # 14 V şarj 12 V sistemde normal
        self.assertEqual(S["engine_db"]["torque"], 320)                       # gerçek tork gösterilir
        self.assertTrue(all(g["key"] in ("front", "rear") for g in S["tires"]["groups"]))
        self.assertTrue(build_payload(S, {}, [], {}, 1))


class WarningSoundTests(unittest.TestCase):
    """Markaya göre ikaz sesi; her uyarıda yalnızca bir kez."""

    def test_every_brand_sound_is_valid_wav(self):
        import io
        import wave
        from ets2bakim import sounds
        for brand in sounds.BRANDS:
            for level in ("warn", "crit"):
                data = sounds.synth(brand, level)
                with wave.open(io.BytesIO(data)) as w:
                    secs = w.getnframes() / w.getframerate()
                    self.assertEqual((w.getnchannels(), w.getsampwidth()), (1, 2))
                self.assertTrue(0.1 < secs < 1.6, (brand, level, secs))
        self.assertNotEqual(sounds.synth("scania", "crit"), sounds.synth("volvo", "crit"))   # markalar farklı

    def test_brand_mapping(self):
        from ets2bakim.sounds import brand_key
        self.assertEqual(brand_key("scania"), "scania")
        self.assertEqual(brand_key("mercedes"), "mercedes")
        self.assertEqual(brand_key("skoda", "car"), "skoda")
        self.assertEqual(brand_key("", "bus"), "otobus")
        self.assertEqual(brand_key("kenworth"), "genel")

    def test_each_warning_sounds_once(self):
        from ets2bakim.sounds import WarningBeeper
        b = WarningBeeper()
        w = lambda text, lvl="crit", wid="Akü {v}": {"level": lvl, "text": text, "id": wid}
        self.assertEqual(b.update([w("Akü 25,1 V")], 0.0), "crit")
        self.assertIsNone(b.update([w("Akü 24,9 V")], 1.0))                 # değer değişti: yeniden ötmez
        self.assertIsNone(b.update([w("Akü 24,8 V")], 2.0))
        self.assertIsNone(b.update([], 3.0))                                  # kayboldu
        self.assertIsNone(b.update([w("Akü 24,7 V")], 20.0))                 # 60 sn içinde döndü: ötmez
        self.assertIsNone(b.update([], 21.0))
        self.assertEqual(b.update([w("Akü 24,0 V")], 200.0), "crit")         # uzun süre sonra yeni uyarı
        self.assertIsNone(b.update([w("Akü"), w("Yağ az", "warn", "Yağ")], 201.0))   # dikkat: yalnız "Hepsi"de
        self.assertEqual(b.update([w("Akü"), w("Yağ az", "warn", "Yağ2")], 202.0, warn_too=True), "warn")

    def test_app_plays_once_and_is_silent_in_demo(self):
        app = make_app()
        self.assertFalse(app.sounds.enabled)
        played = []
        app.sounds.play = lambda brand, level: played.append((brand, level))
        app.frame.paused = False
        crit = [{"level": "crit", "text": "ŞARJ YOK: akü 25,0 V", "id": "ŞARJ YOK: akü {v:.1f} V, %{soc:.0f}."}]
        app._sound_step(crit)
        app._sound_step([dict(crit[0], text="ŞARJ YOK: akü 24,7 V")])
        self.assertEqual(played, [("genel", "crit")])
        app.settings["sound"] = False
        app._sound_step([{"level": "crit", "text": "x", "id": "yeni"}])
        self.assertEqual(len(played), 1)

    def test_clean_wav_with_lead_in_and_no_clicks(self):
        """44,1 kHz, başta sessizlik (ses kartı uyanırken yutulmasın), yumuşak bitiş, kırpılma yok."""
        import io
        import wave
        from array import array
        from ets2bakim import sounds
        for brand in sounds.BRANDS:
            for level in ("warn", "crit"):
                with wave.open(io.BytesIO(sounds.synth(brand, level))) as w:
                    rate = w.getframerate()
                    pcm = array("h", w.readframes(w.getnframes()))
                self.assertEqual(rate, 44100)
                lead = next(i for i, x in enumerate(pcm) if abs(x) > 50) / rate
                self.assertGreaterEqual(lead, 0.1, (brand, level))
                self.assertLessEqual(max(abs(x) for x in pcm), 0.86 * 32767)
                self.assertLess(max(abs(x) for x in pcm[-200:]), 50)          # sonda tık yok

    def test_player_never_cuts_a_playing_sound(self):
        """Çalan ses kesilmez: o sırada gelen aynı seviyeli istek katılır, kritik istek sıraya girer."""
        import tempfile
        import time as _time
        from ets2bakim.sounds import WarningSound
        played = []

        def fake(path):
            played.append(os.path.basename(path))
            _time.sleep(0.15)
        ws = WarningSound(tempfile.mkdtemp(), player=fake)
        self.assertTrue(ws.play("volvo", "warn"))
        _time.sleep(0.05)
        ws.play("volvo", "warn")             # çalarken aynı seviye: zaten ötüyor
        ws.play("volvo", "crit")             # daha acil: dikkat sesi bitince çalar
        ws.play("volvo", "crit")             # sıradakiyle aynı: katılır
        self.assertTrue(ws.idle(5.0))
        self.assertEqual(played, ["volvo_dikkat.wav", "volvo_kritik.wav"])
        ws.play("scania", "crit", test=True)  # "dinle" düğmesi her basışta çalar
        self.assertTrue(ws.idle(5.0))
        self.assertEqual(played[-1], "scania_kritik.wav")
        self.assertFalse(WarningSound(tempfile.mkdtemp(), enabled=False, player=fake).play("volvo", "crit"))

    def test_sound_brand_setting_and_last_vehicle(self):
        app = make_app()
        app.last_vehicle = {"brand_id": "scania", "veh": "truck"}
        self.assertEqual(app._sound_brand(), "scania")                       # oyun kapalı: son bilinen tır
        app.update_settings({"sound_brand": "volvo"})
        self.assertEqual(app._sound_brand(), "volvo")
        app.update_settings({"sound_brand": "yok_boyle"})                    # geçersiz değer kaydedilmez
        self.assertEqual(app.settings["sound_brand"], "volvo")

    def test_language_is_shared_by_both_modes(self):
        """Tek / Çok Oyunculu modda seçilen dil öbür modun ayar dosyasına da yazılır; öbür ayarlar ayrı kalır
        (geçici klasörde denenir)."""
        import json
        from ets2bakim.storage import Storage
        app = make_app(game_mode="cok")
        try:
            home = app.home_dir
            self.assertEqual(os.path.normpath(app.storage.base), home + "_mp")
            Storage(home).save_settings({**Storage(home).load_settings(), "sound": True})
            app.update_settings({"language": "en", "sound": False})
            with open(os.path.join(home, "ayarlar.json"), encoding="utf-8") as fh:
                other = json.load(fh)
            self.assertEqual(other["language"], "en")
            self.assertTrue(other["sound"])                                   # diğer ayarlar korunur (modlar ayrı)
            self.assertEqual(other["game_mode"], "cok")
        finally:
            app.bridge.close()

    def test_each_fault_and_axle_has_its_own_warning(self):
        """Aynı şablondaki iki arıza ayrı uyarıdır: ikincisi çıkınca da bir kez öter."""
        from ets2bakim.sounds import WarningBeeper
        from ets2bakim.view import warnings
        h = Harness(ambient=15)
        h.run(1, rpm=1200, throttle=0.3, speed=50)
        h.t.faults.active.append("alternator")
        b = WarningBeeper()
        self.assertEqual(b.update(warnings(h.t, h.f, 15.0, 5.0), 0.0), "crit")
        h.t.faults.active.append("water_pump")
        ids = [w["id"] for w in warnings(h.t, h.f, 15.0, 5.0)]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(b.update(warnings(h.t, h.f, 15.0, 5.0), 1.0), "crit")


def _state_of(h, ambient=15.0, settings=None):
    from ets2bakim.view import build_state
    app = types.SimpleNamespace(ambient=ambient, expected_min=ambient - 10, lat=50.0, lon=10.0, city="", city_km=0.0,
                                source_name="oyun", source=types.SimpleNamespace(status=""), settings=settings or {},
                                last_message=None)
    return build_state(app, h.t, h.f)


def _gear_truck(ambient=20.0, retarder=5):
    """12 vitesli (Volvo I-Shift oranları) dolu tır düzeneği."""
    h = Harness(ambient=ambient)
    f = h.f
    f.gear_ratios = [14.94, 11.73, 9.04, 7.09, 5.54, 4.35, 3.44, 2.70, 2.08, 1.63, 1.27, 1.00]
    f.diff_ratio, f.wheel_radius, f.gears_forward, f.retarder_steps = 2.64, 0.52, 12, retarder
    return h


def _real_steps(h, n, clutch, speed, gear=1, throttle=0.3, rpm=1000, ambient=20.0):
    """Gerçek zamanlı adımlar (0,1 sn; oyun saati 19 kat): debriyaj gibi hızlı süreçler için."""
    t, f = h.t, h.f
    for _ in range(n):
        f.engine_on = f.electric_on = True
        f.gear, f.clutch, f.speed_kmh, f.rpm, f.throttle = gear, clutch, speed, rpm, throttle
        t.step(f, 0.1, 1.9, dict(ambient=ambient, settings=h.settings, rng=h.rng, km=speed * 1.9 / 3600, dfuel=0.0,
                                 decel=0.0))


class TransmissionTests(unittest.TestCase):
    """Şanzıman yağı ve debriyaj ısıl modeli, aşınma, arızalar, servis ve ŞANZIMAN lambası."""

    def test_highway_normal_long_climb_warmer(self):
        h = _gear_truck()
        h.f.gear = 12
        h.run(60, rpm=1250, throttle=0.45, speed=85)
        self.assertTrue(60 < h.t.trans.t_oil < 90, h.t.trans.t_oil)
        c = _gear_truck(ambient=30.0, retarder=0)
        c.f.gear = 9
        c.run(40, rpm=1500, throttle=1.0, speed=50)
        self.assertGreater(c.t.trans.t_oil, h.t.trans.t_oil + 25)
        self.assertLess(c.t.trans.t_oil, 130)                                 # sağlam şanzıman kırmızıya çıkmaz

    def test_cooler_fault_overheats_on_retarder_descent(self):
        from ets2bakim.telltales import compute

        def descent(fault):
            h = _gear_truck(ambient=30.0)
            if fault:
                h.t.faults.active.append("gearbox_cooler")
            h.f.gear = 10
            h.run(20, rpm=1500, throttle=1.0, speed=50)
            h.f.retarder_level = 5
            h.run(30, rpm=1600, throttle=0.0, speed=70)
            return h
        ok, bad = descent(False), descent(True)
        self.assertLess(ok.t.trans.t_oil, 130)
        self.assertGreaterEqual(bad.t.trans.t_oil, 130)
        S = _state_of(bad, 30.0)
        self.assertEqual(compute(S)["gear"], "c")
        self.assertTrue(any(w["level"] == "crit" and "ŞANZIMAN YAĞI" in w["text"] for w in S["warnings"]))

    def test_clutch_heats_only_when_slipping(self):
        from ets2bakim.telltales import compute
        h = _gear_truck()
        _real_steps(h, 600, clutch=0.0, speed=2.0)                            # tam kavramış: devir farkı ısı sayılmaz
        self.assertLess(h.t.trans.t_clutch, 60)
        _real_steps(h, 1200, clutch=0.5, speed=2.0)                           # 2 dk yarım debriyajla sürünme
        self.assertGreaterEqual(h.t.trans.t_clutch, 320)
        S = _state_of(h)
        self.assertEqual(compute(S)["gear"], "c")
        self.assertTrue(any("DEBRİYAJ AŞIRI ISINDI" in w["text"] for w in S["warnings"]))
        w0 = h.t.trans.clutch_wear
        _real_steps(h, 100, clutch=0.5, speed=2.0)
        self.assertGreater(h.t.trans.clutch_wear, w0)                         # sıcak balata aşınır

    def test_launch_is_harmless(self):
        h = _gear_truck()
        t0 = h.t.trans.t_clutch
        for i in range(30):                                                   # 3 sn'lik dolu kalkış
            _real_steps(h, 1, clutch=max(0.0, 0.9 - i * 0.04), speed=min(6.0, i * 0.25), throttle=0.6, rpm=1100)
        self.assertLess(h.t.trans.t_clutch - t0, 30)

    def test_worn_clutch_service_and_gearbox_oil(self):
        from ets2bakim import prices
        from ets2bakim.telltales import compute
        h = _gear_truck()
        h.run(1, rpm=1200, throttle=0.3, speed=50)
        h.t.trans.clutch_wear = 0.9
        S = _state_of(h)
        self.assertEqual(compute(S)["gear"], "w")
        self.assertTrue(any("Debriyaj balatası %90" in w["text"] for w in S["warnings"]))
        h.run(0.1, engine=False)
        ok, _ = h.t.action(h.f, "clutch_replace", {})
        self.assertTrue(ok)
        self.assertEqual(h.t.trans.clutch_wear, 0.0)
        self.assertEqual(h.t.log[-1]["cost"], prices.CLUTCH)
        h.t.trans.oil_wear_km = h.t.trans.oil_km = 500000
        self.assertEqual(compute(_state_of(h))["gear"], "w")                  # yağ değişim zamanı
        ok, _ = h.t.action(h.f, "gearbox_oil", {})
        self.assertTrue(ok)
        self.assertEqual(h.t.trans.oil_km, 0.0)
        self.assertNotIn("gear", compute(_state_of(h)))

    def test_old_save_gets_transmission_and_persists(self):
        h = _gear_truck()
        h.run(5, rpm=1200, throttle=0.3, speed=50)
        d = h.t.to_dict()
        d.pop("transmission")
        old = TruckModel.from_dict(d)
        self.assertFalse(old.trans.ready)
        old.step(h.f, 0.1, 1.9, dict(ambient=20.0, settings=h.settings, rng=h.rng, km=0.0, dfuel=0.0, decel=0.0))
        self.assertTrue(old.trans.ready)
        h.t.trans.clutch_wear = 0.42
        again = TruckModel.from_dict(h.t.to_dict())
        self.assertAlmostEqual(again.trans.clutch_wear, 0.42)


class NewLampTests(unittest.TestCase):
    """Resimdeki kırmızı / sarı ikaz lambalarından eklenenler: el freni, direksiyon, ABS, marş, fren havası
    (şanzıman: TransmissionTests)."""

    def test_park_brake_reminder_and_driving_with_it(self):
        from ets2bakim.telltales import compute
        h = Harness(ambient=15)
        h.f.park_brake = False
        h.run(1.5, engine=False)                                              # kontak açık, motor kapalı, tır duruyor
        S = _state_of(h)
        self.assertEqual(compute(S).get("park"), "w")                          # uyarı (sarı)
        self.assertTrue(any(w["level"] == "warn" and "Park freni çekilmedi" in w["text"] for w in S["warnings"]))
        h.f.park_brake = True
        h.run(0.2, engine=False)
        self.assertNotIn("park", compute(_state_of(h)))
        h.run(0.5, rpm=1200, throttle=0.3, speed=20)                          # çekiliyken hareket: ciddi (kırmızı)
        S = _state_of(h)
        self.assertEqual(compute(S).get("park"), "c")
        self.assertTrue(any(w["level"] == "crit" and "çekiliyken hareket" in w["text"] for w in S["warnings"]))

    def test_steering_assist_lost_when_engine_stops_while_moving(self):
        from ets2bakim.telltales import compute
        h = Harness(ambient=15)
        h.run(2, rpm=1200, throttle=0.3, speed=60)
        self.assertNotIn("steer", compute(_state_of(h)))
        h.t.killed = True                                                     # motor yolda stop etti
        h.run(0.2, rpm=0, throttle=0.0, speed=40)
        S = _state_of(h)
        self.assertEqual(compute(S).get("steer"), "c")
        self.assertTrue(any("Direksiyon hidrolik desteği yok" in w["text"] for w in S["warnings"]))

    def test_steering_leak_amber_then_red_and_repair(self):
        from ets2bakim.telltales import compute
        h = Harness(ambient=15)
        h.t.faults.active.append("steering_leak")
        fluid = h.t.steer_fluid
        h.run(30, rpm=1200, throttle=0.3, speed=60)
        self.assertLess(h.t.steer_fluid, fluid)
        self.assertEqual(compute(_state_of(h)).get("steer"), "w")
        h.t.steer_fluid = 0.5
        self.assertEqual(compute(_state_of(h)).get("steer"), "c")
        h.run(0.1, engine=False)
        h.t.action(h.f, "repair", {"fault": "steering_leak"})
        self.assertEqual(h.t.steer_fluid, 1.0)

    def test_abs_starter_amber_and_air_red(self):
        from ets2bakim.telltales import compute
        h = Harness(ambient=15)
        h.run(1, rpm=1200, throttle=0.3, speed=50)
        h.t.faults.active += ["abs_sensor", "starter"]
        h.f.air_warning, h.f.air_bar = True, 5.0
        S = _state_of(h)
        lamps = compute(S)
        self.assertEqual((lamps.get("abs"), lamps.get("start"), lamps.get("brake")), ("w", "w", "c"))
        levels = {w["id"].split("|")[-1]: w["level"] for w in S["warnings"] if "|" in w["id"]}
        self.assertEqual((levels["abs_sensor"], levels["starter"]), ("warn", "warn"))   # sarı arızalar kritik değil

    def test_starter_fault_sometimes_does_not_crank(self):
        h = Harness(ambient=15)
        h.t.battery.soc = 1.0
        h.t.faults.active.append("starter")
        h.rng = types.SimpleNamespace(random=lambda: 0.1)                     # bu denemede çevirmez
        start_engine(h)
        self.assertTrue(h.t.killed)
        self.assertIn("marş motoru", str(h.t.kill_reason))
        h.f.engine_on = False
        h.run(0.1, engine=False)
        h.rng = types.SimpleNamespace(random=lambda: 0.9)                     # sonraki denemede çalışır
        start_engine(h)
        self.assertFalse(h.t.killed)

    def test_overlay_lines_for_new_lamps_and_rows(self):
        from ets2bakim.overlay_feed import build_payload
        from ets2bakim.telltales import LABELS, ORDER, Telltales
        self.assertTrue(all(k in LABELS for k in ORDER))
        h = _gear_truck()
        h.run(1, rpm=1200, throttle=0.3, speed=50)
        h.t.faults.active += ["abs_sensor", "starter", "gearbox_cooler"]
        S = _state_of(h)
        lines = build_payload(S, {}, [], {}, 1, lamps=Telltales().update(S)).decode("utf-8").split("\n")
        self.assertIn("t\tabs\tw\tABS", lines)
        self.assertIn("t\tstart\tw\tMARŞ", lines)
        self.assertIn("t\tgear\tw\tŞANZIMAN", lines)
        self.assertTrue(any(ln.startswith("k\tgbox\t") for ln in lines))
        self.assertTrue(any(ln.startswith("k\tclutch\t") for ln in lines))


class LampLevelTests(unittest.TestCase):
    """Gösterge lambalarının önem dereceleri (önemsiz, önemli, uyarı, ciddi, kritik) ve gösterme ayarı."""

    def _many(self):
        """Her dereceden lambası yanan tır: önemsiz (DPF rejenerasyonu), önemli (debriyaj balatası %90), uyarı (ABS),
        ciddi (fren 480 °C), kritik (hararet + STOP)."""
        h = _gear_truck()
        h.run(2, rpm=1200, throttle=0.3, speed=50)
        h.t.faults.active.append("abs_sensor")
        h.t.trans.clutch_wear = 0.9
        h.t.dpf.regen_active = True
        h.t.thermal.t_cool = 112.0
        h.f.brake_temp = 480.0
        return _state_of(h)

    def test_ranks_and_colors(self):
        from ets2bakim.telltales import CRITICAL, MINOR, NOTABLE, SERIOUS, WARN, color, ranks
        r = ranks(self._many())
        self.assertEqual((r["dpf"], r["gear"], r["abs"], r["brake"], r["cool"], r["stop"]),
                         (MINOR, NOTABLE, WARN, SERIOUS, CRITICAL, CRITICAL))
        self.assertEqual([color(x) for x in (1, 2, 3, 4, 5)], ["w", "w", "w", "c", "c"])   # ciddi'den itibaren kırmızı

    def test_setting_filters_lamps(self):
        from ets2bakim.telltales import Telltales
        S = self._many()
        shown = lambda lvl: {k for k, _ in Telltales().update(S, now=0.0, min_level=lvl)}
        self.assertTrue({"dpf", "gear", "abs", "brake", "cool", "stop"} <= shown("onemsiz"))
        self.assertNotIn("dpf", shown("onemli"))
        self.assertIn("gear", shown("onemli"))
        self.assertFalse({"dpf", "gear"} & shown("uyari"))
        self.assertIn("abs", shown("uyari"))
        self.assertEqual(shown("ciddi") & {"abs", "brake", "cool", "stop"}, {"brake", "cool", "stop"})
        self.assertEqual(shown("kritik") & {"brake", "cool", "stop"}, {"cool", "stop"})
        self.assertTrue(all(c == "c" for _, c in Telltales().update(S, now=0.0, min_level="ciddi")))

    def test_setting_saved_and_used_by_overlay(self):
        from ets2bakim.overlay_feed import OverlayBridge
        app = make_app()
        app.update_settings({"lamp_level": "ciddi"})
        self.assertEqual(app.settings["lamp_level"], "ciddi")
        app.update_settings({"lamp_level": "yok_boyle"})                     # geçersiz değer kaydedilmez
        self.assertEqual(app.settings["lamp_level"], "ciddi")
        S = self._many()
        b = OverlayBridge(state_name="Local\\EBKTestLampLvl", ovl_name="Local\\EBKTestLampLvlOvl")
        try:
            def lamps(settings):
                b.telltales = __import__("ets2bakim.telltales", fromlist=["Telltales"]).Telltales()
                b.publish(S, {}, [], settings)
                raw = bytes(b.shm.buf[64:64 + __import__("struct").unpack_from("<I", b.shm.buf, 12)[0]])
                return {ln.split("\t")[1] for ln in raw.decode("utf-8").split("\n") if ln.startswith("t\t")}
            self.assertIn("abs", lamps({}))                                    # varsayılan: hepsi
            self.assertNotIn("abs", lamps({"lamp_level": "ciddi"}))
            self.assertIn("brake", lamps({"lamp_level": "ciddi"}))
        finally:
            b.close()


class PersistenceTests(unittest.TestCase):
    def test_round_trip(self):
        h = Harness(ambient=5, odo=300000)
        h.run(30)
        d = h.t.to_dict()
        t2 = TruckModel.from_dict(d)
        self.assertAlmostEqual(t2.oil.tbn, h.t.oil.tbn)
        self.assertAlmostEqual(t2.battery.soc, h.t.battery.soc)
        self.assertEqual(t2.analysis.rpm_load_min, h.t.analysis.rpm_load_min)
        self.assertLess(t2.health.health, 100)


class BugFixTests(unittest.TestCase):
    """Hata taraması (2026-10-13) düzeltmeleri."""

    def _tick_app(self):
        from ets2bakim.telemetry import Frame
        app = make_app()
        f = Frame(ok=True, paused=False, truck_key="vehicle.volvo.fh16_2012|T 1", brand="Volvo", name="FH16",
                  plate="T 1", brand_id="volvo", truck_id="vehicle.volvo.fh16_2012", odometer_km=200000.0,
                  fuel_l=500.0, fuel_cap=1000.0, game_minutes=600, electric_on=True)
        for _ in range(3):
            app.tick(f, 0.1)
        return app, f

    @staticmethod
    def _jumps(app):
        return [e for e in app.truck.log if e.get("m", "").startswith("Zaman atlaması")]

    def test_time_jump_during_pause_is_applied(self):
        # feribot / tren: yolculuk yükleme ekranında (telemetri duraklatılmış) geçer, kilometre değişmez
        app, f = self._tick_app()
        try:
            app.truck.thermal.t_cool = app.truck.thermal.t_oil = 85.0
            f.paused = True
            app.tick(f, 0.1)
            f.game_minutes += 480
            app.tick(f, 0.1)
            f.paused = False
            app.tick(f, 0.1)
            self.assertEqual(len(self._jumps(app)), 1)
            self.assertLess(app.truck.thermal.t_cool, 60)          # 8 saatte motor soğudu
            app.tick(f, 0.1)
            self.assertEqual(len(self._jumps(app)), 1)              # bir kez
        finally:
            app.bridge.close()

    def test_loaded_save_during_pause_is_not_a_jump(self):
        app, f = self._tick_app()
        try:
            f.paused = True
            app.tick(f, 0.1)
            f.game_minutes += 3 * 1440                              # başka kayıt: 3 gün sonra, 900 km ötede
            f.odometer_km += 900.0
            f.paused = False
            app.tick(f, 0.1)
            self.assertEqual(self._jumps(app), [])
            self.assertEqual(app.truck.analysis.distance_km, 0.0)  # kayıt yüklemedeki km farkı yol sayılmaz
        finally:
            app.bridge.close()

    def test_small_fuel_increases_do_not_add_up_to_a_refuel(self):
        app, f = self._tick_app()
        try:
            for _ in range(3):                                     # kayıt yüklemelerinde 0,6 L'lik artışlar
                f.fuel_l += 0.6
                app.tick(f, 0.1)
                app.tick(f, 0.1)
            refuels = [e for e in app.truck.log if e.get("m", "").startswith("Yakıt alındı")]
            self.assertEqual(refuels, [])
            for _ in range(10):                                    # gerçek yakıt alımı
                f.fuel_l += 20.0
                app.tick(f, 0.1)
            app.tick(f, 0.1)
            refuels = [e for e in app.truck.log if e.get("m", "").startswith("Yakıt alındı")]
            self.assertEqual(len(refuels), 1)
            self.assertAlmostEqual(refuels[0]["a"]["l"], 200.0, places=3)
        finally:
            app.bridge.close()

    def test_truck_reset_needs_engine_off(self):
        app, f = self._tick_app()
        try:
            app.frame.engine_on = True
            ok, _ = app.do_action("truck_reset", {})
            self.assertFalse(ok)
            app.frame.engine_on = False
            ok, _ = app.do_action("truck_reset", {})
            self.assertTrue(ok)
        finally:
            app.bridge.close()

    def test_car_manual_spec_keeps_car_values(self):
        h = vehicle_harness("skoda", "vehicle.skoda.superb", "Superb")
        h.f.engine_on, h.f.speed_kmh = False, 0.0
        app = make_app()
        try:
            app.truck, app.frame = h.t, h.f
            ok, _ = app.update_spec({"name": "2.0 TDI", "power_hp": 170, "torque_nm": 320, "rated_rpm": 1900,
                                     "displacement_l": 2.0, "oil_capacity_l": 4.3, "coolant_capacity_l": 8.0,
                                     "battery_ah": 72, "has_dpf": True})
            self.assertTrue(ok)
            s = h.t.spec
            self.assertAlmostEqual(s.displacement_l, 2.0)          # eskiden tır sınırına (7 L) kırpılıyordu
            self.assertAlmostEqual(s.oil_capacity_l, 4.3)
            self.assertAlmostEqual(s.coolant_capacity_l, 8.0)
            self.assertAlmostEqual(s.battery_ah, 72.0)
            self.assertAlmostEqual(s.power_kw, 170 * 0.7355)
            self.assertEqual(s.torque_nm, 0.0)                     # model torku güçten türetir
            from ets2bakim.view import build_state
            S = build_state(app, h.t, h.f)
            self.assertEqual(S["engine_db"]["torque"], 320)        # girilen gerçek tork gösterilir
            self.assertEqual(S["truck"]["spec_limits"]["displacement_l"][:2], (0.9, 4.0))
            self.assertNotIn("retread", [x["id"] for x in S["options"]["tire_tiers"]])
            ok, _ = app.update_spec({"displacement_l": float("nan")})
            self.assertFalse(ok)
        finally:
            app.bridge.close()

    def test_truck_manual_spec_still_clamped_to_truck_ranges(self):
        h = Harness(ambient=15)
        h.f.engine_on, h.f.speed_kmh = False, 0.0
        app = make_app()
        try:
            app.truck, app.frame = h.t, h.f
            app.update_spec({"displacement_l": 2.0, "oil_capacity_l": 4.0, "power_hp": 9000})
            self.assertEqual((h.t.spec.displacement_l, h.t.spec.oil_capacity_l), (7, 15))
            self.assertAlmostEqual(h.t.spec.power_kw, 820 * 0.7355)
        finally:
            app.bridge.close()

    def test_car_battery_messages_and_no_retreads(self):
        h = vehicle_harness("skoda", "vehicle.skoda.superb", "Superb")
        h.f.engine_on, h.f.speed_kmh = False, 0.0
        t = h.t
        ok, msg = t.action(h.f, "battery_replace", {"ah": 72, "kind": "agm"})
        self.assertTrue(ok)
        self.assertEqual(t.log[-1]["m"], "Akü değişti (12 V {ah:.0f} Ah, {kind_t}).")
        self.assertEqual(msg["m"], "Akü değişti.")
        ok, _ = t.action(h.f, "tire_replace", {"axle": "rear", "tier": "retread"})
        self.assertFalse(ok)
        t.faults.add("battery_frozen")
        t.repair_fault(h.f, "battery_frozen", garage=True)
        self.assertEqual(t.log[-1]["m"], "Oyundaki serviste donmuş akü yenilendi (12 V {ah:.0f} Ah).")
        tr = Harness(ambient=15)
        tr.f.engine_on, tr.f.speed_kmh = False, 0.0
        tr.t.action(tr.f, "battery_replace", {"ah": 225, "kind": "std"})
        self.assertEqual(tr.t.log[-1]["m"], "Aküler değişti (2 x 12 V {ah:.0f} Ah, {kind_t}).")

    def test_command_sequence_survives_app_restart(self):
        # oyundaki eklenti durum bloğunu açık tuttuğu sürece blok yaşar; yeniden açılan uygulamanın ilk komutu
        # eklentinin son gördüğü sırayla aynı çıkmamalı
        import struct
        from ets2bakim.overlay_feed import OverlayBridge
        names = dict(state_name="Local\\EBKTestSeqState", ovl_name="Local\\EBKTestSeqOvl")
        plugin = OverlayBridge(**names)        # eklentinin açık tuttuğu blok yerine
        try:
            old = OverlayBridge(**names)
            self.assertTrue(old.send_command(2, cooldown=0))
            self.assertTrue(old.send_command(2, cooldown=0))
            old.close()
            new = OverlayBridge(**names)
            self.assertTrue(new.send_command(2, cooldown=0))
            self.assertEqual(struct.unpack_from("<I", new.shm.buf, 16)[0], 3)
            new.close()
        finally:
            plugin.close()

    def test_currency_log_is_read_only_when_changed(self):
        import tempfile
        from unittest import mock
        from ets2bakim import currency
        d = tempfile.mkdtemp()
        p = os.path.join(d, "Euro Truck Simulator 2")
        os.makedirs(p)
        log = os.path.join(p, "game.log.txt")
        with open(log, "w", encoding="utf-8") as fh:
            fh.write('uset g_currency "12"\n')
        mon = currency.CurrencyMonitor([d])
        with mock.patch.object(currency, "read_index", wraps=currency.read_index) as rd:
            self.assertEqual(mon.get({}, "ets2")["code"], "TRY")
            mon._checked.clear()
            self.assertEqual(mon.get({}, "ets2")["code"], "TRY")
            self.assertEqual(rd.call_count, 1)                    # değişmeyen dosya yeniden okunmadı
            with open(log, "a", encoding="utf-8") as fh:
                fh.write('uset g_currency "0"\n')
            mon._checked.clear()
            self.assertEqual(mon.get({}, "ets2")["code"], "EUR")
            self.assertEqual(rd.call_count, 2)

    def test_save_retries_and_failure_does_not_stop_the_app(self):
        import tempfile
        from unittest import mock
        from ets2bakim import storage
        st = storage.Storage(tempfile.mkdtemp())
        real = os.replace
        calls = []

        def flaky(a, b):
            calls.append(a)
            if len(calls) < 3:
                raise PermissionError("kilitli")
            return real(a, b)
        with mock.patch.object(storage.os, "replace", flaky):
            st.save_settings({"language": "de"})
        self.assertEqual(st.load_settings()["language"], "de")
        app, f = self._tick_app()
        try:
            with mock.patch.object(app.storage, "save_truck", side_effect=OSError("disk dolu")):
                app.save()                                         # hata yükselmez
            self.assertEqual(app.last_message["level"], "warn")
        finally:
            app.bridge.close()


class AlertToggleTests(unittest.TestCase):
    """Ayarlar → Uyarılar ve ikaz lambaları: her uyarı ve lamba tek tek kapatılabilir."""

    def test_every_warning_has_a_catalog_key(self):
        import ast
        from ets2bakim import alerts, i18n
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ets2bakim", "view.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        used = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "add":
                a = node.args[1]
                used.add(a.value if isinstance(a, ast.Constant) else "fault:*")
        mode = {"mp_detected", "sp_session", "mp_stop_pending"}           # app._mode_warnings
        static = {k for k in alerts.WARNING_KEYS if not k.startswith("fault:")} - mode
        self.assertEqual(used, static | {"fault:*"})
        # katalogdaki her ad ve açıklamanın çevirisi var
        need = [name for _, name, _ in alerts.GROUPS] + list(alerts.LAMP_DESCS.values())
        need += [label for _, _, items in alerts.GROUPS for _, _, label in items]
        self.assertEqual([s for s in need if s not in i18n.TRANS], [])
        self.assertEqual(set(alerts.LAMP_DESCS), alerts.LAMP_KEYS)

    def test_catalog_follows_language(self):
        from ets2bakim import alerts, i18n
        i18n.set_lang("en")
        try:
            c = alerts.catalog()
        finally:
            i18n.set_lang("tr")
        oil = next(g for g in c["groups"] if g["key"] == "oil")
        self.assertEqual(oil["name"], "Engine oil")
        self.assertEqual(oil["items"][0], {"key": "oil_pressure", "level": "crit", "label": "Low oil pressure"})
        self.assertEqual([x["key"] for x in c["lamps"]][:3], ["stop", "batt", "glow"])
        self.assertEqual(c["lamps"][0]["label"], "PULL OVER")

    @staticmethod
    def _payload(app):
        import struct
        buf = app.bridge.shm.buf
        n = struct.unpack_from("<I", buf, 12)[0]
        return bytes(buf[64:64 + n]).decode("utf-8")

    def test_disabled_warning_and_lamp_are_hidden(self):
        import json
        from ets2bakim.telemetry import Frame
        app = make_app()
        f = Frame(ok=True, paused=False, truck_key="vehicle.volvo.fh16_2012|T 2", brand="Volvo", name="FH16",
                  plate="T 2", brand_id="volvo", truck_id="vehicle.volvo.fh16_2012", odometer_km=200000.0,
                  fuel_l=100.0, fuel_cap=1000.0, game_minutes=600, electric_on=True)     # yakıt %10: uyarı + lamba
        try:
            for _ in range(3):
                app.tick(f, 0.1)
            app._publish(force=True)
            keys = lambda: [w.get("key") for w in json.loads(app.state_json)["warnings"]]
            self.assertIn("fuel_low", keys())
            self.assertIn("t\tfuel\t", self._payload(app))
            ok, _ = app.update_settings({"warnings_off": ["fuel_low", "yok_boyle", "fuel_low"], "lamps_off": ["fuel", 7]})
            self.assertTrue(ok)
            self.assertEqual(app.settings["warnings_off"], ["fuel_low"])          # bilinmeyen ve tekrarlanan atılır
            self.assertEqual(app.settings["lamps_off"], ["fuel"])
            self.assertNotIn("fuel_low", keys())                                   # listede, katmanda, seste yok
            self.assertNotIn("t\tfuel\t", self._payload(app))
            app.update_settings({"warnings_off": "bozuk"})                         # liste değil: dokunulmaz
            self.assertEqual(app.settings["warnings_off"], ["fuel_low"])
            self.assertEqual(app.storage.load_settings()["lamps_off"], ["fuel"])   # kaydedildi
            app.update_settings({"warnings_off": [], "lamps_off": []})
            self.assertIn("fuel_low", keys())
            self.assertIn("t\tfuel\t", self._payload(app))
        finally:
            app.bridge.close()

    def test_mode_warnings_can_be_disabled(self):
        from ets2bakim import alerts
        ws = [{"level": "warn", "key": "mp_detected", "text": "x"}, {"level": "crit", "key": "oil_pressure", "text": "y"}]
        self.assertEqual(alerts.visible(ws, {"warnings_off": ["mp_detected"]}), ws[1:])
        self.assertEqual(alerts.visible(ws, {"warnings_off": None}), ws)            # eski / bozuk ayar dosyası
        self.assertEqual(alerts.visible_lamps([("stop", "c"), ("fuel", "w")], {"lamps_off": ["stop"]}), [("fuel", "w")])


@unittest.skipUnless(sys.platform == "win32", "Windows kısayol ve kayıt defteri")
class KurulumTests(unittest.TestCase):
    """Dağıtım paketinin kurulumu ve kaldırması: geçici klasörler, sahte oyun klasörü ve deneme kayıt anahtarı (gerçek
    oyuna, masaüstüne ve Uygulamalar listesine dokunulmaz)."""
    KEY = r"Software\ETS2Bakim-Test\Uninstall\KurulumTests"

    def setUp(self):
        import tempfile
        from unittest import mock
        from ets2bakim import kurulum
        self.k = kurulum
        self.tmp = tempfile.mkdtemp()
        j = lambda *p: os.path.join(self.tmp, *p)
        self.src = j("zip", "program")
        for rel, data in (("python/python.exe", b"exe"), ("python/pythonw.exe", b"exe"), ("ets2bakim/app.ico", b"ico"),
                          ("ets2bakim/app_mp.ico", b"ico"), ("web/index.html", b"<html>"), ("paket.json", b"{}"),
                          ("eklenti/scs-telemetry.dll", b"TEL-YENI"), ("eklenti/ets2bakim_overlay.dll", b"OVL")):
            os.makedirs(os.path.dirname(os.path.join(self.src, rel)), exist_ok=True)
            with open(os.path.join(self.src, rel), "wb") as fh:
                fh.write(data)
        self.game = j("steam", "steamapps", "common", "Euro Truck Simulator 2", "bin", "win_x64")
        self.plug = os.path.join(self.game, "plugins")
        os.makedirs(self.plug)
        with open(os.path.join(self.plug, "scs-telemetry.dll"), "wb") as fh:
            fh.write(b"TEL-ESKI")                                            # başka bir aracın eski sürümü
        self.paths = kurulum.Paths(j("inst"), j("desk"), j("start"), j("prefs"), [self.game], self.KEY)
        self.patches = [mock.patch.object(kurulum, "running_game", return_value=None),
                        mock.patch.object(kurulum, "app_pids", return_value=[]),
                        mock.patch.object(kurulum.appcontrol, "sac_state", return_value="off"),
                        mock.patch.object(kurulum, "webview2_installed", return_value=True)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        import shutil
        for p in self.patches:
            p.stop()
        self.k.unregister(self.KEY)
        for key in (r"Software\ETS2Bakim-Test\Uninstall", r"Software\ETS2Bakim-Test"):
            self.k.unregister(key)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def con(self, quiet=True):
        return self.k.Console("tr", quiet, echo=False)

    def read(self, *p):
        with open(os.path.join(*p), "rb") as fh:
            return fh.read()

    def test_install_update_and_uninstall(self):
        import json
        import winreg
        from ets2bakim import window
        k, P = self.k, self.paths
        k.install(P, self.con(), src=self.src, launch=False)
        self.assertEqual(self.read(self.plug, "scs-telemetry.dll"), b"TEL-YENI")
        self.assertEqual(self.read(self.plug, "scs-telemetry.dll" + k.BACKUP_SUFFIX), b"TEL-ESKI")   # yedeklendi
        self.assertEqual(self.read(self.plug, "ets2bakim_overlay.dll"), b"OVL")
        desk = os.path.join(P.desktop, "ETS2 Bakım.lnk")                       # tek kısayol: mod uygulamada seçilir
        lnk = k.read_shortcut(desk)
        self.assertEqual(os.path.normcase(lnk["target"]), os.path.normcase(P.pythonw))
        self.assertEqual((lnk["args"], lnk["app_id"]), ("-m ets2bakim", window.APP_ID))
        self.assertEqual([f for f in os.listdir(P.desktop)], ["ETS2 Bakım.lnk"])
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY) as rk:
            self.assertEqual(winreg.QueryValueEx(rk, "DisplayName")[0], "ETS2 Bakım Simülatörü")
            self.assertIn("ets2bakim.kurulum kaldir", winreg.QueryValueEx(rk, "UninstallString")[0])
        with open(os.path.join(P.install, "data", "ayarlar.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["language"], "tr")                # ilk dil: Windows'un dili
        # kullanıcı verisi (iki modun klasörü) ve kendi sesleri güncellemede korunur
        for rel in ("data/trucks/kamyon.json", "data_mp/trucks/kamyon.json", "sesler/ozel/scania_kritik.wav"):
            os.makedirs(os.path.dirname(os.path.join(P.install, rel)), exist_ok=True)
            with open(os.path.join(P.install, rel), "wb") as fh:
                fh.write(b"kullanici")
        # 1.1'den yükseltme: iki ayrı uygulamanın kısayolları kaldırılır, başka kopyayı açan aynı adlı kısayola dokunulmaz
        old_tek = os.path.join(P.desktop, "ETS2 Bakım - Tek Oyunculu.lnk")
        old_cok = os.path.join(P.start_menu, "ETS2 Bakım", "ETS2 Bakım - Çok Oyunculu.lnk")
        for lnk in (old_tek, old_cok):
            k.create_shortcut(lnk, P.pythonw, "-m ets2bakim --mod tek")
        m = k.load_manifest(P.install)
        k.save_manifest(P.install, {**m, "modes": ["tek", "cok"], "shortcuts": m["shortcuts"] + [old_cok]})
        foreign = os.path.join(P.desktop, "ETS2 Bakım - Çok Oyunculu.lnk")
        k.create_shortcut(foreign, sys.executable, "-m ets2bakim --mod cok")
        k.install(P, self.con(), src=self.src, launch=False)
        self.assertEqual(self.read(P.install, "data", "trucks", "kamyon.json"), b"kullanici")
        self.assertEqual(self.read(P.install, "data_mp", "trucks", "kamyon.json"), b"kullanici")
        self.assertEqual(self.read(P.install, "sesler", "ozel", "scania_kritik.wav"), b"kullanici")
        self.assertFalse(os.path.exists(old_tek))
        self.assertFalse(os.path.exists(old_cok))
        self.assertEqual(os.path.normcase(k.read_shortcut(foreign)["target"]), os.path.normcase(sys.executable))
        m = k.load_manifest(P.install)
        self.assertNotIn("modes", m)
        self.assertNotIn(foreign, m["shortcuts"])
        self.assertNotIn(old_cok, m["shortcuts"])
        self.assertTrue(os.path.isfile(os.path.join(P.start_menu, "ETS2 Bakım", "ETS2 Bakım.lnk")))
        # kaldırma: eklentiler geri alınır, eski telemetri eklentisi geri konur, kayıt / kısayollar / ayarlar silinir
        os.makedirs(P.prefs)
        k.uninstall(P, self.con(), delete_folder=False)
        self.assertEqual(sorted(os.listdir(self.plug)), ["scs-telemetry.dll"])
        self.assertEqual(self.read(self.plug, "scs-telemetry.dll"), b"TEL-ESKI")
        self.assertFalse(os.path.exists(desk))
        self.assertTrue(os.path.isfile(foreign))                                # başkasının kısayolu kalır
        self.assertFalse(os.path.exists(os.path.join(P.start_menu, "ETS2 Bakım")))
        self.assertFalse(os.path.exists(P.prefs))
        with self.assertRaises(OSError):
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY)

    def test_same_telemetry_plugin_is_left_alone(self):
        k, P = self.k, self.paths
        with open(os.path.join(self.plug, "scs-telemetry.dll"), "wb") as fh:
            fh.write(b"TEL-YENI")                                            # aynısı zaten kurulu (başka bir araç)
        con = self.con()
        k.install(P, con, src=self.src, launch=False)
        self.assertTrue(any("DOKUNULMADI" in line for line in con.lines))
        self.assertFalse(os.path.exists(os.path.join(self.plug, "scs-telemetry.dll" + k.BACKUP_SUFFIX)))
        k.uninstall(P, self.con(), delete_folder=False)
        self.assertEqual(self.read(self.plug, "scs-telemetry.dll"), b"TEL-YENI")   # silinmedi
        self.assertFalse(os.path.exists(os.path.join(self.plug, "ets2bakim_overlay.dll")))

    def test_unsigned_overlay_is_skipped_with_smart_app_control(self):
        from unittest import mock
        k, P = self.k, self.paths
        with open(os.path.join(self.plug, "ets2bakim_overlay.dll"), "wb") as fh:
            fh.write(b"OVL-ESKI")                                            # her oyun açılışında engellenirdi
        with mock.patch.object(k.appcontrol, "sac_state", return_value="on"), \
                mock.patch.object(k.appcontrol, "signature_status", return_value="unsigned"):
            con = self.con()
            k.install(P, con, src=self.src, launch=False)
        self.assertFalse(os.path.exists(os.path.join(self.plug, "ets2bakim_overlay.dll")))
        self.assertTrue(any("ATLANDI" in line for line in con.lines))
        self.assertEqual(self.read(self.plug, "scs-telemetry.dll"), b"TEL-YENI")  # telemetri yine kurulur

    def test_uninstall_asks_first_and_game_must_be_closed(self):
        from unittest import mock
        k, P = self.k, self.paths
        k.install(P, self.con(), src=self.src, launch=False)
        with mock.patch("builtins.input", return_value="h"):
            with self.assertRaises(k.Abort):
                k.uninstall(P, self.con(quiet=False), delete_folder=False)
        self.assertEqual(self.read(self.plug, "ets2bakim_overlay.dll"), b"OVL")    # hiçbir şey silinmedi
        with mock.patch.object(k, "running_game", return_value="eurotrucks2.exe"):
            with self.assertRaises(k.Abort):
                k.uninstall(P, self.con(), delete_folder=False)          # sessiz: oyun açıkken durur
        self.assertTrue(os.path.isfile(os.path.join(P.desktop, "ETS2 Bakım.lnk")))
        k.uninstall(P, self.con(), delete_folder=False)
        self.assertFalse(os.path.exists(os.path.join(self.plug, "ets2bakim_overlay.dll")))

    def test_needs_extracted_package(self):
        import shutil
        k = self.k
        shutil.rmtree(os.path.join(self.src, "python"))
        con = self.con()
        with self.assertRaises(k.Abort):
            k.install(self.paths, con, src=self.src, launch=False)
        self.assertIn("Tümünü ayıkla", con.lines[-1])
        self.assertFalse(os.path.exists(self.paths.install))


class OilPressureAlarm(unittest.TestCase):
    """Videoda görülen "YAĞ BASINCI DÜŞÜK (6,0 bar)" yanlış alarmı: oyundan gelen tek karelik devir sıçraması."""

    @staticmethod
    def has_alarm(h):
        from ets2bakim.view import warnings
        return any(w["key"] == "oil_pressure" for w in warnings(h.t, h.f, h.amb, h.amb - 6))

    def test_rpm_spike_from_game_is_clamped(self):
        from ets2bakim.telemetry import Frame
        self.assertEqual(Frame.from_raw({"sdkActive": True, "engineRpm": 9200.0, "engineRpmMax": 2500.0}).rpm, 3250.0)
        self.assertEqual(Frame.from_raw({"sdkActive": True, "engineRpm": float("nan"), "engineRpmMax": 2500.0}).rpm, 0.0)
        f = Frame.from_raw({"sdkActive": True, "engineRpm": 1400.0, "engineRpmMax": float("nan")})
        self.assertEqual((f.rpm, f.rpm_max), (1400.0, 2500.0))

    def test_threshold_stays_below_relief_pressure(self):
        oil = Harness().t.oil
        self.assertEqual(oil.low_pressure_threshold(9000), 2.5)
        self.assertAlmostEqual(oil.low_pressure_threshold(1500), 0.5 + 0.0007 * 900)

    def test_healthy_engine_never_alarms_on_rpm_spike(self):
        h = Harness()
        h.run(3)
        h.run(0.6, rpm=9000)        # eski eşik 9000 devirde 6,4 bar: 6 barla sınırlı sağlam basınç "düşük" sayılıyordu
        self.assertFalse(self.has_alarm(h))

    def test_real_low_pressure_alarms_after_a_moment(self):
        h = Harness()
        h.run(3)
        self.assertFalse(self.has_alarm(h))
        h.t.oil.volume_l = 0.0      # pompa hava emiyor: basınç çöker
        h.run(0.1)                  # 3 adım ≈ 0,3 gerçek sn: henüz uyarı yok
        self.assertFalse(self.has_alarm(h))
        h.run(0.6)                  # ≈ 1,9 gerçek sn daha
        self.assertTrue(self.has_alarm(h))


def _film_truck(ambient=20.0):
    """Çalışan, ısınmış tır (çekim modu testleri)."""
    h = Harness(ambient=ambient)
    start_engine(h)
    h.run(8, rpm=1300, throttle=0.5, speed=80)
    return h


def _keys(h):
    from ets2bakim.view import warnings
    return {w["key"] for w in warnings(h.t, h.f, h.amb, h.amb - 6)}


def _film_app(game_mode="tek"):
    """Kamyonu kurulmuş demo uygulama (ayrı veri klasörü ve paylaşılan bellek adları) ve oyun karesi."""
    from ets2bakim.telemetry import Frame
    app = make_app(game_mode=game_mode)
    f = Frame(ok=True, paused=False, truck_key="vehicle.volvo.fh16_2012|T 3", brand="Volvo", name="FH16",
              plate="T 3", brand_id="volvo", truck_id="vehicle.volvo.fh16_2012", odometer_km=200000.0,
              fuel_l=500.0, fuel_cap=1000.0, game_minutes=600, electric_on=True)
    for _ in range(3):
        app.tick(f, 0.1)
    return app, f


class FilmModeTests(unittest.TestCase):
    """Ayarlar → Çekim modu: seçilen arıza istenen anda tetiklenir ve gerçek arıza gibi işler (uyarı, lamba, ses, sonuç,
    ücretli onarım); kayıtta "elle" diye işaretlenir; "hepsini onar" ücretsizdir; yalnızca tek oyunculu."""

    def tearDown(self):
        from ets2bakim import i18n
        i18n.set_lang("tr")

    def test_catalog_lists_every_item_and_is_translated(self):
        import ast
        from ets2bakim import filming, i18n
        from ets2bakim.faults import FAULTS
        c = filming.catalog()
        self.assertEqual([it["id"] for it in c["items"]], list(filming.IDS))
        self.assertTrue(all(it["available"] for it in c["items"]))             # oyun kapalı: hepsi seçilebilir
        self.assertLessEqual(set(filming.IDS) - set(filming.TIRE_ITEMS), set(FAULTS))
        self.assertEqual({it["group"] for it in c["items"]}, {g for g, _ in filming.GROUPS})
        self.assertIn(filming.DEFAULT_ITEM, filming.IDS)
        # adlar, açıklamalar, gruplar ve dosyadaki her M(...) / T(...) iletisinin İngilizcesi ve Almancası var
        need = [n for _, n in filming.GROUPS] + list(filming.TIRE_NAMES.values()) + list(filming.TIRE_DESCS.values())
        need += [FAULTS["oil_pump"]["name"], FAULTS["oil_pump"]["desc"]]
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ets2bakim", "filming.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        need += [n.args[0].value for n in ast.walk(tree) if isinstance(n, ast.Call) and n.args
                 and getattr(n.func, "id", None) in ("M", "T") and isinstance(n.args[0], ast.Constant)]
        self.assertEqual([s for s in need if s not in i18n.TRANS], [])
        i18n.set_lang("de")
        pump = filming.catalog()["items"][0]
        self.assertEqual((pump["label"], pump["now"], pump["level"]), ("Ölpumpendefekt", ["ÖL", "ANHALTEN"], "crit"))
        self.assertEqual(filming.catalog()["groups"][0]["name"], "Motor und Schmierung")

    def test_triggered_fault_works_like_a_real_one(self):
        from ets2bakim import filming, prices, telltales
        h = _film_truck()
        t = h.t
        ok, msg = filming.trigger(t, h.f, "alternator")
        self.assertTrue(ok)
        self.assertEqual(msg["m"], "Tetiklendi: {name_t}.")
        e = t.log[-1]
        self.assertEqual((e["level"], e["m"], e.get("manual")), ("crit", "ARIZA (elle tetiklendi): {name_t} — {desc_t}", True))
        h.run(1)
        self.assertIn("fault:alternator", _keys(h))                            # aynı uyarı
        self.assertIn("no_charge", _keys(h))                                   # aynı sonuç: şarj yok
        self.assertLess(t.battery.current, 0)                                  # akü boşalıyor
        self.assertEqual(telltales.ranks(_state_of(h))["batt"], telltales.SERIOUS)   # aynı lamba
        self.assertEqual(filming.trigger(t, h.f, "alternator")[0], False)      # zaten var
        h.f.engine_on, h.f.speed_kmh = False, 0.0
        ok, _ = t.action(h.f, "repair", {"fault": "alternator"})               # gerçek arıza gibi ücretli onarım
        self.assertTrue(ok)
        self.assertEqual((t.log[-1]["cost"], t.log[-1].get("manual")), (prices.fault("alternator", "truck"), None))
        self.assertNotIn("alternator", t.faults.active)

    def test_oil_pump_low_pressure_alarm_without_instant_seizure(self):
        from ets2bakim import filming, telltales
        h = _film_truck()
        t = h.t
        self.assertNotIn("oil_pressure", _keys(h))
        filming.trigger(t, h.f, "oil_pump")
        h.run(1, rpm=1300, throttle=0.5, speed=80)                             # ≈ 3 gerçek sn
        self.assertLess(t.oil_pressure, t.oil.low_pressure_threshold(1300))
        self.assertIn("oil_pressure", _keys(h))                                # YAĞ BASINCI DÜŞÜK
        r = telltales.ranks(_state_of(h))
        self.assertEqual((r["oil"], r["stop"]), (telltales.CRITICAL, telltales.CRITICAL))
        h.run(3, rpm=600, throttle=0.0, speed=0)                               # sıcak rölantide de basınç var
        self.assertGreaterEqual(t.oil_pressure, 0.3)
        self.assertNotIn("engine_seized", t.faults.active)
        before = t.health.health
        h.run(10, rpm=1300, throttle=0.6, speed=80)
        self.assertLess(t.health.health, before - 0.5)                         # bu halde sürmek yatakları aşındırır

    def test_engine_seized_stops_engine_and_tyre_items(self):
        from ets2bakim import filming
        h = _film_truck()
        t = h.t
        ok, _ = filming.trigger(t, h.f, "engine_seized")
        self.assertTrue(ok and t.killed)                                       # motor durdurulur (App zorla durdurmaya uyar)
        self.assertTrue(all(e.get("manual") for e in t.log[-2:]))
        self.assertEqual(t.log[-1]["m"], "Krank yatakları sardı, MOTOR KİLİTLENDİ.")
        ok, _ = filming.trigger(t, h.f, "blowout_front")
        self.assertTrue(ok and t.tires.groups["steer"]["blown"])
        self.assertEqual(filming.trigger(t, h.f, "blowout_front")[0], False)
        ok, _ = filming.trigger(t, h.f, "puncture_rear")
        self.assertTrue(ok)
        self.assertEqual(t.tires.groups["drive"]["leak_bph"], filming.PUNCTURE_BPH)
        self.assertEqual(filming.trigger(t, h.f, "puncture_rear")[0], False)
        self.assertLessEqual({"tire_blown", "tire_leak"}, _keys(h))
        self.assertEqual(filming.trigger(t, h.f, "yok_boyle")[0], False)

    def test_car_items_and_front_blowout_pulls(self):
        from ets2bakim import engines, filming
        from ets2bakim.blowout import BlowoutEffect, JOLT_BRAKE, STEER_PULL
        import random
        h = vehicle_harness("skoda", "vehicle.skoda.superb", "Superb")
        t = h.t
        t.set_engine(engines.engine_by_id(engines.model_by_key("tmp_superb"), "18tsi"))   # benzinli
        avail = {it["id"]: it["available"] for it in filming.catalog(t)["items"]}
        self.assertFalse(avail["steering_leak"])                               # otomobilde elektrikli direksiyon
        self.assertFalse(avail["preheater"])                                   # benzinlide ön ısıtma yok
        self.assertEqual(filming.trigger(t, h.f, "steering_leak")[0], False)
        ok, _ = filming.trigger(t, h.f, "blowout_front")
        self.assertTrue(ok and t.tires.groups["front"]["blown"])
        h.f.speed_kmh = 80.0
        brake, steer = BlowoutEffect(random.Random(3)).update(t.tires, h.f, True, 10.0)
        self.assertEqual(brake, JOLT_BRAKE)
        self.assertGreater(abs(steer), 0.5 * STEER_PULL)                       # ön lastik: direksiyon patlayan tarafa çeker

    def test_repair_all_is_free_and_marked_manual(self):
        from ets2bakim import filming
        h = _film_truck()
        t = h.t
        for it in ("engine_seized", "steering_leak", "blowout_front", "puncture_rear"):
            filming.trigger(t, h.f, it)
        t.steer_fluid = 0.4
        costs = t.costs_total
        ok, msg = filming.repair_all(t, h.f)
        self.assertTrue(ok)
        self.assertEqual(msg["a"]["n"], 4)
        self.assertEqual((t.faults.active, t.killed, t.costs_total, t.steer_fluid), ([], False, costs, 1.0))
        self.assertFalse(any(s["blown"] or s["leak_bph"] for s in t.tires.groups.values()))
        self.assertEqual((t.log[-1]["cost"], t.log[-1].get("manual"), t.log[-1]["kind"]), (0.0, True, "servis"))
        self.assertEqual(filming.repair_all(t, h.f)[0], False)                 # onarılacak bir şey kalmadı

    def test_app_trigger_hotkey_and_settings(self):
        import json
        app, f = _film_app()
        try:
            st = json.loads(app.state_json)["status"]["film"]
            self.assertEqual((st["available"], st["enabled"], st["item"], st["key"]), (True, False, "oil_pump", ""))
            ok, msg = app.film_action("trigger")
            self.assertFalse(ok)                                               # çekim modu kapalı
            self.assertIn("Çekim modu kapalı", msg)
            app.update_settings({"film_mode": True, "film_fault": "abs_sensor"})
            app.update_settings({"film_fault": "uydurma"})                    # bilinmeyen arıza yok sayılır
            self.assertEqual(app.settings["film_fault"], "abs_sensor")
            app.beeper.cleared["eski"] = 0.0
            ok, msg = app.film_action("trigger")
            self.assertTrue(ok, msg)
            self.assertIn("abs_sensor", app.truck.faults.active)
            self.assertEqual(app.beeper.cleared, {})                           # yeniden tetiklenen arıza da öter
            self.assertTrue(app.truck.log[-1]["manual"])
            log = json.loads(app.state_json)["log"]
            self.assertTrue(log[0]["manual"] and not log[-1]["manual"])        # arayüze "elle" işaretiyle gider
            self.assertIn("abs_sensor", app.storage.load_truck(app.truck.key)["faults"]["active"])   # kaydedildi
            # kısayol tuşu: sürüş modu tuşuyla (F10) aynı olamaz; çekim modu kapalıyken tuş dinlenmez
            app.update_settings({"film_key": "key:121"})
            self.assertEqual(app.settings["film_key"], "")
            app.update_settings({"film_key": "btn:3", "film_fault": "starter"})
            self.assertEqual(app.film.binding, ("btn", 3))
            app.film.presses.append(1.0)
            app._film_step()
            self.assertIn("starter", app.truck.faults.active)
            self.assertIn("Tetiklendi", app.last_message["text"])
            app.update_settings({"film_mode": False})
            self.assertIsNone(app.film.binding)
            app.film.presses.append(2.0)
            app.update_settings({"film_fault": "fan_clutch"})
            app._film_step()
            self.assertNotIn("fan_clutch", app.truck.faults.active)
            # tuş atama (sürüş modu tuşu gibi); sürüş modu tuşu reddedilir
            app.update_settings({"film_mode": True})
            ok, _ = app.film_capture(True)
            self.assertTrue(ok and app._film_status()["capturing"])
            app.film.poll(10.0, set())
            app.film.poll(10.1, {("key", 121)})
            app._film_step()
            self.assertEqual(app.settings["film_key"], "btn:3")
            self.assertIn("sürüş modu", app.last_message["text"])
            app.film_capture(True)
            app.film.poll(20.0, set())
            app.film.poll(20.1, {("pov", "down")})
            app._film_step()
            self.assertEqual((app.settings["film_key"], app.film.binding), ("pov:down", ("pov", "down")))
            self.assertEqual(app.storage.load_settings()["film_key"], "pov:down")
            ok, msg = app.film_action("repair_all")
            self.assertTrue(ok, msg)
            self.assertEqual(app.truck.faults.active, [])
            self.assertEqual(app.film_action("ucur")[0], False)
        finally:
            app.bridge.close()

    def test_multiplayer_blocks_film_mode(self):
        import json
        mp_app = make_app(game_mode="cok")
        try:
            mp_app.update_settings({"film_mode": True, "film_key": "btn:2"})
            self.assertFalse(mp_app.film_available())
            self.assertIsNone(mp_app.film.binding)                             # çok oyunculu uygulamada tuş dinlenmez
            self.assertFalse(mp_app.film_action("trigger")[0])
            self.assertFalse(mp_app.film_capture(True)[0])
            mp_app._publish_waiting()
            self.assertFalse(json.loads(mp_app.state_json)["status"]["film"]["available"])
        finally:
            mp_app.bridge.close()
        app, f = _film_app()
        try:
            app.update_settings({"film_mode": True, "film_fault": "alternator"})
            app.mp.kind = "tmp"                                                # tek oyunculu uygulamada TruckersMP algılandı
            self.assertFalse(app.film_action("trigger")[0])
            app.film.presses.append(1.0)
            app._film_step()
            self.assertNotIn("alternator", app.truck.faults.active)
        finally:
            app.bridge.close()

    def test_http_endpoints(self):
        import json
        import threading
        import urllib.request
        from ets2bakim import app as app_mod
        app, f = _film_app()
        httpd = app_mod.ExclusiveHTTPServer(("127.0.0.1", 0), app_mod.make_handler(app))   # boş port
        threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        def post(path, body):
            req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read())
        try:
            with urllib.request.urlopen(base + "/api/film", timeout=5) as r:
                cat = json.loads(r.read())
            self.assertEqual(cat["items"][0]["id"], "oil_pump")
            app.update_settings({"film_mode": True})
            r = post("/api/film", {"op": "trigger", "item": "gearbox_cooler"})
            self.assertTrue(r["ok"], r)
            self.assertIn("gearbox_cooler", app.truck.faults.active)
            self.assertTrue(post("/api/film", {"op": "repair_all"})["ok"])
            self.assertTrue(post("/api/film_capture", {"start": False})["ok"])
        finally:
            httpd.shutdown()
            httpd.server_close()
            app.bridge.close()


class VehicleTypeTests(unittest.TestCase):
    """Ayarlar → Araç tipi: tek oyunculu otomobil / otobüs modları (telemetri tır bildirir) elle otomobil ya da otobüs
    yapılır; otomobil varsayılanları (12 V, otomobil yağı, antifrizi, sınırları, motorları) kurulur."""

    def tearDown(self):
        from ets2bakim import i18n
        i18n.set_lang("tr")

    def test_unknown_car_mod_gets_car_defaults(self):
        from ets2bakim import engines, oil as oil_mod, vehicles
        h = vehicle_harness("togg", "vehicle.togg.t10x", "T10X")
        t = h.t
        self.assertEqual((t.veh, t.battery.volts, t.spec.model_key), ("truck", 24, ""))    # tanınmayan: tır sanılır
        self.assertTrue(t.set_vehicle(h.f, "car"))
        self.assertEqual((t.veh, t.spec.vehicle, t.spec.vehicle_override), ("car", "truck", "car"))
        self.assertEqual((t.battery.volts, t.battery.capacity_ah, t.battery.kind), (12, 72.0, "agm"))
        self.assertIn(t.oil.grade, oil_mod.grades_for("car"))
        self.assertEqual(t.coolant.type, "si_oat")
        self.assertEqual((t.spec.model_key, t.spec.engine_id, t.spec.fuel), ("generic_car", "g20d150", "diesel"))
        self.assertAlmostEqual(t.oil.capacity_l, 4.6)
        self.assertAlmostEqual(t.oil.level_frac, 1.0, places=2)
        self.assertEqual(vehicles.spec_limits(t.veh)["battery_ah"], (40, 120, 1))
        self.assertIn("Araç tipi elle seçildi", t.log[-1]["m"])
        lineup = engines.lineup(engines.model_by_key(t.spec.model_key))
        self.assertGreaterEqual(len({e["fuel"] for e in lineup}), 2)          # benzinli ve dizel seçilebilir
        t.set_engine(engines.engine_by_id(engines.model_by_key(t.spec.model_key), "g15t"))
        self.assertEqual((t.spec.fuel, t.spec.has_dpf, t.spec.torque_nm), ("petrol", False, 0.0))
        h.run(0.1, engine=False)
        self.assertEqual(set(t.tires.groups), {"front", "rear"})              # otomobil lastikleri (2,5 bar)
        start_engine(h)
        h.run(60, rpm=1300, throttle=0.35, speed=100)
        self.assertFalse(t.killed)
        self.assertTrue(13.5 < t.battery.voltage < 14.8, t.battery.voltage)  # 12 V şarj voltajı
        self.assertTrue(70 < t.thermal.t_cool < 105, t.thermal.t_cool)

    def test_back_to_auto_and_known_truck(self):
        from ets2bakim import oil as oil_mod
        h = vehicle_harness("togg", "vehicle.togg.t10x", "T10X")
        t = h.t
        t.set_vehicle(h.f, "car")
        t.set_vehicle(h.f, "auto")                                             # geri: tanınmayan tır varsayılanları
        self.assertEqual((t.veh, t.battery.volts, t.spec.model_key, t.spec.battery_ah), ("truck", 24, "", 225.0))
        self.assertIn(t.oil.grade, oil_mod.grades_for("truck"))
        self.assertAlmostEqual(t.oil.capacity_l, 40.0)
        self.assertIn("otomatik algılama", t.log[-1]["m"])
        v = vehicle_harness("volvo", "vehicle.volvo.fh16_2012", "FH16", car_wheels=False, odo=400000.0)
        v.t.trans.oil_wear_km = 300000.0                                       # tır aralığında (450.000 km) olağan
        v.t.set_vehicle(v.f, "car")                                            # tanınan tır da otomobil yapılabilir
        self.assertEqual((v.t.veh, v.t.spec.model_key), ("car", "generic_car"))
        self.assertLess(v.t.trans.oil_used("car"), 1.0)                        # şanzıman da otomobilinki: hemen "değişim" yok
        v.t.set_vehicle(v.f, "auto")
        self.assertEqual((v.t.veh, v.t.spec.model_key, v.t.spec.engine_id), ("truck", "volvo_fh12", "d13k500"))
        self.assertFalse(v.t.set_vehicle(v.f, "tank"))
        s = vehicle_harness("skoda", "vehicle.skoda.superb", "Superb")       # TruckersMP otomobili tır seçilirse
        s.t.set_vehicle(s.f, "truck")
        self.assertEqual((s.t.veh, s.t.battery.volts, s.t.spec.model_key), ("truck", 24, ""))

    def test_bus_override_uses_bus_engines(self):
        from ets2bakim import vehicles
        h = vehicle_harness("setra", "vehicle.setra.s516", "S 516 HD", car_wheels=False)
        t = h.t
        t.set_vehicle(h.f, "bus")
        self.assertEqual((t.veh, t.battery.volts, t.spec.model_key, t.spec.engine_id),
                         ("bus", 24, "generic_bus", "om470_428"))
        self.assertEqual(vehicles.load_scale(t.veh), 1.25)

    def test_choice_survives_save_and_reset(self):
        from ets2bakim.truck import TruckModel
        h = vehicle_harness("togg", "vehicle.togg.t10x", "T10X")
        h.t.set_vehicle(h.f, "car")
        t2 = TruckModel.from_dict(h.t.to_dict())
        self.assertEqual((t2.veh, t2.spec.vehicle_override, t2.battery.volts), ("car", "car", 12))
        self.assertTrue(t2.model_tried)                                        # yeniden algılamada tıra dönmez
        h.f.engine_on = True
        h.f.electric_on = True
        t2.step(h.f, 0.1, 1.9, dict(ambient=15.0, settings={}, rng=h.rng, km=0.0, dfuel=0.0, decel=0.0))
        self.assertEqual(t2.veh, "car")

    def test_app_vehicle_choice(self):
        import json
        from ets2bakim import i18n
        from ets2bakim.telemetry import Frame
        app = make_app()
        f = Frame(ok=True, paused=False, truck_key="vehicle.togg.t10x|34 TG 1", brand="Togg", name="T10X",
                  plate="34 TG 1", brand_id="togg", truck_id="vehicle.togg.t10x", odometer_km=1000.0,
                  fuel_l=40.0, fuel_cap=50.0, game_minutes=600, electric_on=True)
        try:
            for _ in range(3):
                app.tick(f, 0.1)
            ok, msg = app.update_spec({"vehicle": "car"})
            self.assertTrue(ok, msg)
            app.tick(f, 0.1)
            S = json.loads(app.state_json)
            self.assertEqual((S["truck"]["vehicle"], S["truck"]["vehicle_choice"], S["truck"]["vehicle_detected"]),
                             ("car", "car", "truck"))
            self.assertEqual(S["battery"]["volts"], 12)
            self.assertEqual(S["truck"]["spec_limits"]["power_hp"], [60, 400, 5])
            self.assertFalse(app.update_spec({"vehicle": "uzay gemisi"})[0])
            i18n.set_lang("en")
            app._publish(force=True)
            E = json.loads(app.state_json)["engine_db"]
            self.assertEqual(E["model_name"], "Car — generic engine list")
            self.assertIn("2.0 diesel 150 hp", [e["label"] for e in E["lineup"]])
            i18n.set_lang("tr")
            f.engine_on, f.speed_kmh = False, 0.0
            ok, _ = app.do_action("truck_reset", {})                           # sıfırlamada seçim korunur
            self.assertTrue(ok)
            self.assertEqual((app.truck.veh, app.truck.spec.vehicle_override), ("car", "car"))
            app.frame = Frame(ok=False)
            self.assertFalse(app.update_spec({"vehicle": "auto"})[0])          # oyunda bu araçla bağlı olmalı
        finally:
            app.bridge.close()

    def test_real_rpm_car_mod_is_scaled(self):
        from ets2bakim import vehicles
        self.assertEqual(vehicles.rpm_scale("car", 3000.0), 1.0)              # TruckersMP otomobili: değişmez
        self.assertEqual(vehicles.rpm_scale("car", 2500.0), 1.0)              # telemetri devir sınırı vermezse
        self.assertEqual(vehicles.rpm_scale("truck", 6500.0), 1.0)
        self.assertEqual(vehicles.rpm_scale("bus", 3500.0), 1.0)
        self.assertAlmostEqual(vehicles.rpm_scale("car", 6600.0), 2.2)
        runs = []
        for rpm_max, rpm in ((6600.0, 2800), (3000.0, 2800 / 2.2)):          # gerçek ölçekli mod · TruckersMP ölçeği
            h = vehicle_harness("togg", "vehicle.togg.t10x", "T10X")
            h.f.rpm_max = rpm_max
            h.t.set_vehicle(h.f, "car")
            start_engine(h)
            h.run(60, rpm=rpm, throttle=0.5, speed=110)
            runs.append(h)
        real, tmp = runs[0].t, runs[1].t
        self.assertFalse(real.flags["overrev"])                                # 2800 rpm otomobilde aşırı devir değil
        self.assertEqual(real.eng.rpm, 2800)                                   # gösterilen devir oyunun devri
        self.assertTrue(40 < real.eng.p_brake < 110, real.eng.p_brake)        # 150 hp motorda yarım gazda güç
        self.assertAlmostEqual(real.eng.p_brake, tmp.eng.p_brake, delta=0.5)  # model aynı noktada çalışır
        self.assertAlmostEqual(real.thermal.t_cool, tmp.thermal.t_cool, delta=1.0)
        self.assertTrue(75 < real.thermal.t_cool < 105, real.thermal.t_cool)
        runs[0].run(0.2, rpm=6300, throttle=1.0, speed=150)
        self.assertTrue(real.flags["overrev"])


class OverlayKeyPanelTests(unittest.TestCase):
    """Katmanın tuşu (F8 yerine) ve oyun içi panel ayarı (otomatik / açık / kapalı) katmana cfg satırlarıyla gider."""

    def tearDown(self):
        from ets2bakim import drivemode
        drivemode.set_overlay_key(0x77)

    def test_cfg_lines(self):
        from ets2bakim import overlay_feed as of
        self.assertEqual(of._ovl_cfg({})[1], "cfg\tpanel\tauto")
        self.assertTrue(of._ovl_cfg({})[0].startswith("cfg\tovlkey\t119\t"))           # varsayılan F8
        lines = of._ovl_cfg({"overlay_key": 0x78, "overlay_panel": "off"})
        self.assertTrue(lines[0].startswith("cfg\tovlkey\t120\t"))
        self.assertEqual(lines[1], "cfg\tpanel\toff")
        for bad in (0x1B, 0x10, 0x11, 0x12, 0x5B, 0xA0, 0x01, 300, "x"):               # Esc, Shift/Ctrl/Alt, Win, fare
            self.assertEqual(of.overlay_key({"overlay_key": bad}), 0x77, bad)
        self.assertEqual(of._ovl_cfg({"overlay_panel": "?"})[1], "cfg\tpanel\tauto")

    def test_overlay_key_frees_f8_for_drive_mode(self):
        from ets2bakim import drivemode
        self.assertIsNone(drivemode.parse_binding("key:119"))                          # F8 katmanın
        drivemode.set_overlay_key(0x78)
        self.assertEqual(drivemode.parse_binding("key:119"), ("key", 119))             # F9 seçilince F8 boşalır
        self.assertIsNone(drivemode.parse_binding("key:120"))
        self.assertIsNone(drivemode.parse_binding("key:27"))                           # Esc hiçbir zaman


class UpdateRateTests(unittest.TestCase):
    """Ayarlar → Değer güncelleme sıklığı (1.3.2): pencere ve katman ayrı aralıkta, 0 = gerçek zamanlı (20/sn); uyarılar
    aralığı beklemez; pencere durumu canlı akışla (/api/stream) alır."""

    def _app(self, fuel=500.0):
        from ets2bakim.telemetry import Frame
        app = make_app()
        f = Frame(ok=True, paused=False, truck_key="vehicle.volvo.fh16_2012|T 3", brand="Volvo", name="FH16",
                  plate="T 3", brand_id="volvo", truck_id="vehicle.volvo.fh16_2012", odometer_km=200000.0,
                  fuel_l=fuel, fuel_cap=1000.0, game_minutes=600, electric_on=True)
        for _ in range(3):
            app.tick(f, 0.1)
        return app, f

    def test_pacer_keeps_average_interval(self):
        from ets2bakim.app import Pacer
        times = [i / 10 for i in range(101)]                       # 10 sn, 10/sn adım
        p = Pacer()
        self.assertAlmostEqual(sum(p.due(t, 0.25, 0.1) for t in times), 41, delta=1)   # 0,25 sn: 10 sn'de ~40
        p = Pacer()
        self.assertEqual(sum(p.due(t, 5.0, 0.1) for t in times), 3)                   # 0, 5 ve 10. saniye
        p = Pacer()
        self.assertTrue(all(p.due(t, 0.0, 0.05) for t in times))                      # gerçek zamanlı: her adım

    def test_setting_is_validated_shared_and_sets_tick(self):
        from ets2bakim.storage import Storage
        app = make_app()
        try:
            self.assertEqual((app.interval("ui_interval"), app.interval("overlay_interval"), app.tick_s()),
                             (0.25, 0.1, 0.1))                                         # 1.3.1'deki hızlar
            app.update_settings({"ui_interval": "0", "overlay_interval": 0.33})
            self.assertEqual(app.settings["ui_interval"], 0.0)
            self.assertEqual(app.settings["overlay_interval"], 0.1)                    # listede olmayan kaydedilmez
            self.assertEqual(app.tick_s(), 0.05)                                       # gerçek zamanlı: 20/sn
            self.assertEqual(Storage(app.home_dir).load_settings()["ui_interval"], 0.0)
            app.settings["ui_interval"] = "bozuk"                                       # elle bozulmuş dosya
            self.assertEqual(app.interval("ui_interval"), 0.25)
        finally:
            app.bridge.close()

    def test_overlay_waits_for_interval_but_not_for_warnings(self):
        import struct
        app, f = self._app()
        try:
            app.update_settings({"overlay_interval": 5.0})
            app.tick(f, 0.1)                                         # yeni aralığın ilk yayını
            buf = app.bridge.shm.buf
            seq0, beat0 = struct.unpack_from("<I", buf, 8)[0], struct.unpack_from("<I", buf, 24)[0]
            for _ in range(5):
                app.tick(f, 0.1)
            self.assertEqual(struct.unpack_from("<I", buf, 8)[0], seq0)        # değerler 5 sn'de bir yazılır
            self.assertGreater(struct.unpack_from("<I", buf, 24)[0], beat0)    # canlılık sayacı her adımda
            f.fuel_l = 100.0                                                    # %10: uyarı + lamba yanar
            app.tick(f, 0.1)
            self.assertNotEqual(struct.unpack_from("<I", buf, 8)[0], seq0)     # aralık beklenmeden yayınlandı
            self.assertIn("t\tfuel\t", AlertToggleTests._payload(app))
        finally:
            app.bridge.close()

    def test_window_state_is_serialized_only_when_read(self):
        import json
        app, f = self._app()
        try:
            app.tick(f, 0.1)
            self.assertTrue(app._ui_dirty)                           # kuruldu ama henüz JSON'a çevrilmedi
            st = json.loads(app.state_json)
            self.assertFalse(app._ui_dirty)
            self.assertEqual(st["truck"]["plate"], "T 3")
            self.assertIn("forecast", json.loads(app.detail_json))
        finally:
            app.bridge.close()

    def test_stream_pushes_states(self):
        import json
        import threading
        import urllib.request
        from ets2bakim import app as app_mod, i18n
        app = make_app()
        httpd = app_mod.ExclusiveHTTPServer(("127.0.0.1", 0), app_mod.make_handler(app))   # boş port
        threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        r = None
        try:
            r = urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_address[1]}/api/stream", timeout=5)
            self.assertTrue(r.headers.get("Content-Type", "").startswith("text/event-stream"))

            def event():
                while True:
                    line = r.readline().decode("utf-8")
                    if line.startswith("data: "):
                        return json.loads(line[6:])
            self.assertIn("status", event())                       # bağlanınca o anki durum
            app.update_settings({"language": "en"})                # işlemden sonra beklemeden gönderilir
            self.assertEqual(event()["status"]["lang"], "en")
        finally:
            app.running = False
            app._ui_push()
            if r is not None:
                r.close()
            httpd.shutdown()
            httpd.server_close()
            app.bridge.close()
            i18n.set_lang("tr")

    def test_decel_uses_same_window_at_any_tick_rate(self):
        app = make_app()
        try:
            for i in range(10):                                    # 20/sn: her 0,05 sn'de 0,5 km/h yavaşlıyor
                app._spd_hist.append((i * 0.05, 80.0 - i * 0.5))
            self.assertAlmostEqual(app._decel(0.5, 75.0), 1.0 / 3.6 / 0.1, places=3)   # 0,1 sn önceki hızdan
            app._spd_hist.clear()
            self.assertEqual(app._decel(1.0, 50.0), 0.0)
        finally:
            app.bridge.close()


class FastTelemetryTests(unittest.TestCase):
    """Telemetri yalnızca kullanılan alanlarla okunur (1.3.2); sonuç paketin tam çözümüyle aynı olmalı."""

    def _buffer(self):
        import random
        from truck_telemetry.telemetry_version import v1_12, unpack as U
        root = v1_12.struct_telemetry
        buf = bytearray(random.Random(7).randbytes(root.size))

        def strings(st, off):          # metin alanları geçerli UTF-8 ve sıfırla bitmeli (paket öyle okur)
            if isinstance(st, U.DictStruct):
                for _, ft in st._DictStruct__fields:
                    strings(ft, off)
                    off += ft.size
            elif isinstance(st, U.ArraySruct):
                inner = st._ArraySruct__struct
                for i in range(st._ArraySruct__count):
                    strings(inner, off + i * inner.size)
            elif isinstance(st, U.StringStruct):
                buf[off:off + st.size] = (b"abc" + bytes([65 + off % 26]) + b"\0" * st.size)[:st.size]
        strings(root, 0)
        return v1_12, buf

    def test_same_frame_as_full_parse(self):
        from ets2bakim.telemetry import FastParse, Frame
        v, buf = self._buffer()
        fp = FastParse(v)
        full = fp.parse(buf)                                       # ilk okuma: karşılaştırma
        fast = fp.parse(buf)
        self.assertTrue(fp.ok)
        self.assertLess(len(fp.items), 150)                        # ~3.700 değer yerine
        self.assertEqual(repr(Frame.from_raw(fast)), repr(Frame.from_raw(full)))

    def test_layout_mismatch_falls_back_to_full_parse(self):
        from ets2bakim.telemetry import FastParse
        v, buf = self._buffer()
        fp = FastParse(v)
        ft, off = fp.root["speed"]
        fp.root["speed"] = (ft, off + 4)                            # yerleşim değişmiş gibi
        d = fp.parse(buf)
        self.assertFalse(fp.ok)
        self.assertEqual(repr(d), repr(v.parse_data(buf)))         # paketin tam çözümü (repr: NaN'lar da eşit)


class TranslationCoverageTests(unittest.TestCase):
    """Diller eşit kalsın (1.3.2): koddaki her metnin İngilizce ve Almanca karşılığı olmalı."""

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _web_dict(self):
        import json
        import re
        with open(os.path.join(self.ROOT, "web", "i18n.js"), encoding="utf-8") as fh:
            src = fh.read()
        body = src[src.index("const I18N"):src.index("const MONTHS")]
        s = r'"((?:[^"\\]|\\.)*)"'
        pairs = re.findall(r'(?:^|[{,\s])' + s + r'\s*:\s*\[\s*' + s + r'\s*,\s*' + s + r'\s*\]', body)
        return {json.loads(f'"{k}"'): (json.loads(f'"{a}"'), json.loads(f'"{b}"')) for k, a, b in pairs}

    def test_web_code_texts_are_translated(self):
        import json
        import re
        words = self._web_dict()
        self.assertEqual([k for k, (a, b) in words.items() if not a.strip() or not b.strip()], [])
        missing = []
        for name in ("app.js", "charts.js"):
            with open(os.path.join(self.ROOT, "web", name), encoding="utf-8") as fh:
                code = fh.read()
            for lit in re.findall(r'\btt\(\s*"((?:[^"\\]|\\.)*)"\s*\)', code):
                text = json.loads(f'"{lit}"')
                if re.search(r"[A-Za-zçğıöşüÇĞİÖŞÜ]{3}", text) and text not in words and text.strip() not in words:
                    missing.append(f"{name}: {text}")
        self.assertEqual(missing, [])

    def test_python_messages_are_translated(self):
        import ast
        import re
        from ets2bakim import i18n, view  # noqa: F401  (view kendi adlarını sözlüğe ekler)
        missing = []
        pkg = os.path.join(self.ROOT, "ets2bakim")
        for name in sorted(os.listdir(pkg)):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(pkg, name), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    continue
                fn = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
                text = node.args[0].value
                plain = re.sub(r"\{[^}]*\}", "", text)          # yer tutucular hariç (ör. "~{n} km" dilden bağımsız)
                if fn in ("T", "M") and re.search(r"[A-Za-zçğıöşüÇĞİÖŞÜ]{3}", plain) and text not in i18n.TRANS:
                    missing.append(f"{name}:{node.lineno}: {text}")
        self.assertEqual(missing, [])
        self.assertEqual([k for k, (en, de) in i18n.TRANS.items() if not en.strip() or not de.strip()], [])

    def test_overlay_texts_have_three_languages(self):
        import re
        with open(os.path.join(self.ROOT, "overlay", "src", "ebk_overlay.cpp"), encoding="utf-8") as fh:
            code = re.sub(r"//[^\n]*", "", fh.read())
        defs = re.findall(r"\b(T_[A-Z0-9_]+)\s*\{([^}]*)\}", code)
        self.assertGreater(len(defs), 100)
        bad = [n for n, body in defs if len(re.findall(r'"(?:[^"\\]|\\.)*"', body)) != 3
               or any(not s.strip('"') for s in re.findall(r'"(?:[^"\\]|\\.)*"', body))]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
