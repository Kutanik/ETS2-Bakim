"""Arıza tespiti (Motor Analizi): parça durumu yüzdeleri, yeni motor parçaları, parça değişimi ve yeni yağ / antifriz /
akü seçenekleri."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ets2bakim import battery, coolant, i18n, oil, prices  # noqa: E402
from ets2bakim.faults import FAULTS, PARTS, Faults  # noqa: E402
from sim_harness import Harness  # noqa: E402

NEW = ("turbo", "injector", "egr_valve", "intercooler", "air_filter", "fuel_filter", "radiator_leak", "belt")


def _app():
    return types.SimpleNamespace(ambient=15.0, expected_min=5.0, lat=50.0, lon=10.0, city="", city_km=0.0,
                                 source_name="oyun", source=types.SimpleNamespace(status=""), settings={}, last_message=None)


class ConditionTests(unittest.TestCase):
    def test_condition_follows_age(self):
        f = Faults()
        f.init_ages(0)
        self.assertAlmostEqual(f.condition(("alternator",)), 1.0)
        f.ages_km["alternator"] = FAULTS["alternator"]["mtbf_km"]
        self.assertAlmostEqual(f.condition(("alternator",)), 0.43, delta=0.02)
        f.active.append("alternator")
        self.assertEqual(f.condition(("alternator",)), 0.0)
        f.replace(("alternator",))
        self.assertEqual((f.condition(("alternator",)), f.has("alternator")), (1.0, False))

    def test_new_parts_start_young_on_old_trucks(self):
        f = Faults()
        f.init_ages(2_000_000)
        self.assertEqual(f.ages_km["air_filter"], 0.3 * FAULTS["air_filter"]["mtbf_km"])
        self.assertGreater(f.condition(("air_filter",)), 0.8)

    def test_parts_and_prices_complete(self):
        for pid, (name, keys) in PARTS.items():
            for k in keys:
                self.assertIn(k, FAULTS, pid)
        for k in NEW:
            self.assertTrue(FAULTS[k]["random"])
            self.assertGreater(prices.fault(k), 0)
            self.assertGreater(prices.fault(k, "car"), 0)
        i18n.set_lang("en")
        try:
            self.assertEqual(i18n.T(FAULTS["turbo"]["name"]), "Turbo failure (burning oil)")
            self.assertEqual(i18n.T("Radyatör"), "Radiator")
        finally:
            i18n.set_lang("tr")


class DiagnosisTests(unittest.TestCase):
    def test_state_has_diagnosis_and_replace_works(self):
        from ets2bakim.view import build_state
        h = Harness()
        h.run(1)
        h.t.faults.ages_km["turbo"] = FAULTS["turbo"]["mtbf_km"] * 2
        S = build_state(_app(), h.t, h.f)
        parts = {p["id"]: p for g in S["diag"]["groups"] for p in g["parts"]}
        self.assertIn("radiator", parts)
        self.assertIn("alternator", parts)
        self.assertLess(parts["turbo"]["pct"], 15)
        self.assertEqual(parts["turbo"]["lvl"], "c")
        self.assertTrue(S["diag"]["specs"] and S["diag"]["levels"])
        self.assertFalse(h.t.action(h.f, "part_replace", {"part": "turbo"})[0])   # sürerken olmaz
        h.f.speed_kmh, h.f.engine_on = 0.0, False
        ok, _ = h.t.action(h.f, "part_replace", {"part": "turbo"})
        self.assertTrue(ok)
        self.assertEqual(h.t.faults.condition(("turbo",)), 1.0)
        self.assertFalse(h.t.action(h.f, "part_replace", {"part": "yok"})[0])

    def test_turbo_burns_oil_and_belt_stops_charging(self):
        a, b = Harness(), Harness()
        b.t.faults.active += ["turbo", "belt"]
        a.run(20)
        b.run(20)
        self.assertGreater(b.t.oil.total_consumed_l, a.t.oil.total_consumed_l * 2)
        self.assertLess(b.t.battery.soc, a.t.battery.soc)


class OptionTests(unittest.TestCase):
    def test_more_choices(self):
        for g in ("0w30e6", "5w40e7", "10w40e11", "15w40ck4"):
            self.assertIn(g, oil.GRADES)
        for c in ("noat", "hoat_vcs", "si_oat_evo"):
            self.assertIn(c, coolant.TYPES)
        for k in ("gel", "agm_hd"):
            self.assertIn(k, battery.KINDS)
            self.assertGreater(battery.replace_cost(225, k), battery.replace_cost(225, "std"))


if __name__ == "__main__":
    unittest.main()
