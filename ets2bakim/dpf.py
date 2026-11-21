"""Dizel partikül filtresi (DPF): is birikimi, pasif/aktif rejenerasyon ve yağdan gelen kül."""
from dataclasses import dataclass

from . import prices
from .util import clamp


@dataclass
class DPF:
    soot_g: float = 30.0
    ash_g: float = 0.0
    regen_active: bool = False
    burning: bool = False
    regen_count: int = 0
    km_since_regen: float = 0.0

    SOOT_CAP = 180.0
    ASH_CAP = 800.0
    REGEN_PRICE = prices.DPF_REGEN
    CLEAN_PRICE = prices.DPF_CLEAN

    @property
    def soot_cap(self):
        return self.SOOT_CAP * (1 - 0.5 * clamp(self.ash_g / self.ASH_CAP, 0.0, 1.0))

    @property
    def soot_frac(self):
        return self.soot_g / self.soot_cap

    @property
    def ash_frac(self):
        return self.ash_g / self.ASH_CAP

    @property
    def backpressure_kpa(self):
        return 5.0 + 25.0 * self.soot_frac + 15.0 * self.ash_frac

    def step(self, dt_s, c):
        """c: running, p_brake, t_exh, speed_kmh, cold, lugging, oil_consumed_l, oil_ash_pct, t_cool, km,
        rate (is ve kül dolma hızı çarpanı), soot_mult (motor parçası arızalarının is artışı: turbo, enjektör, EGR…)"""
        dt_h = dt_s / 3600.0
        r = c.get("rate", 1.0)
        self.km_since_regen += c["km"]
        self.ash_g += c["oil_consumed_l"] * 880.0 * c["oil_ash_pct"] / 100.0 * 0.9 * r
        if not c["running"]:
            self.burning = False
            return
        out = (0.09 * c["p_brake"] + 0.8) * (1 + 2 * c["lugging"] + 1.5 * c["cold"]) * r * c.get("soot_mult", 1.0)
        passive = self.soot_g * 0.6 * clamp((c["t_exh"] - 250.0) / 200.0, 0.0, 1.0) ** 1.5
        if not self.regen_active and self.soot_frac >= 0.75 and c["speed_kmh"] > 40 and c["t_cool"] > 60:
            self.regen_active = True
        self.burning = self.regen_active and c["speed_kmh"] > 15 and c["t_cool"] > 60
        active = self.soot_g * 2.5 if self.burning else 0.0
        self.soot_g = clamp(self.soot_g + (out - passive - active) * dt_h, 0.0, 1.6 * self.soot_cap)
        if self.regen_active and self.soot_frac < 0.10:
            self.regen_active = self.burning = False
            self.regen_count += 1
            self.km_since_regen = 0.0

    def service_regen(self):
        self.soot_g = 0.05 * self.soot_cap
        self.regen_active = self.burning = False
        self.regen_count += 1
        self.km_since_regen = 0.0
        return self.REGEN_PRICE

    def clean(self):
        self.soot_g = 0.0
        self.ash_g = 0.0
        self.regen_active = self.burning = False
        return self.CLEAN_PRICE
