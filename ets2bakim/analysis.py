"""Motor ve sürüş analizi: devir x yük haritası, hız aralığına göre tüketim, vites kullanımı,
fren enerjisi dağılımı, sürüş tarzı olayları ve sürüş puanı."""
from dataclasses import dataclass, field

from .util import clamp

RPM_EDGES = [0, 800, 1000, 1200, 1400, 1600, 1800, 2000, 99999]
RPM_LABELS = ["<800", "800-1000", "1000-1200", "1200-1400", "1400-1600", "1600-1800", "1800-2000", "2000+"]
LOAD_EDGES = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
LOAD_LABELS = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]
SPEED_EDGES = [0, 30, 50, 70, 80, 90, 999]
SPEED_LABELS = ["0-30", "30-50", "50-70", "70-80", "80-90", "90+"]
CO2_KG_PER_L = 2.64
MAX_GEARS = 25


def _bin(x, edges):
    for i in range(len(edges) - 1):
        if x < edges[i + 1]:
            return i
    return len(edges) - 2


@dataclass
class Analysis:
    engine_h: float = 0.0
    idle_h: float = 0.0
    drive_h: float = 0.0
    distance_km: float = 0.0
    fuel_l: float = 0.0
    idle_fuel_l: float = 0.0
    starts: int = 0
    cold_starts: int = 0
    failed_starts: int = 0
    rpm_load_min: list = field(default_factory=lambda: [[0.0] * 5 for _ in range(8)])
    speed_fuel_l: list = field(default_factory=lambda: [0.0] * 6)
    speed_km: list = field(default_factory=lambda: [0.0] * 6)
    gear_min: list = field(default_factory=lambda: [0.0] * MAX_GEARS)
    shifts: int = 0
    eco_min: float = 0.0
    lugging_min: float = 0.0
    overrev_min: float = 0.0
    overrev_events: int = 0
    cold_load_min: float = 0.0
    overheat_min: float = 0.0
    retarder_min: float = 0.0
    engine_brake_min: float = 0.0
    service_brake_min: float = 0.0
    cruise_min: float = 0.0
    coast_min: float = 0.0
    harsh_brake: int = 0
    e_service_kwh: float = 0.0
    e_retarder_kwh: float = 0.0
    e_engbrake_kwh: float = 0.0
    brake_hot_min: float = 0.0
    max_brake_temp: float = 0.0
    load_min_sum: float = 0.0
    rpm_min_sum: float = 0.0
    run_min: float = 0.0
    max_coolant: float = 0.0
    max_oil_temp: float = 0.0
    _overrev: bool = False
    _harsh: bool = False
    _gear: int = 0

    def step(self, dt_s, c):
        """c: running, rpm, load, speed_kmh, km, fuel_l, t_cool, t_oil, lugging, overrev, retarder, engine_brake,
        cruise, overrun, decel, gear, brake, brake_temp, p_ret, p_eb, mass_kg"""
        dt_min = dt_s / 60.0
        dt_h = dt_s / 3600.0
        speed = c["speed_kmh"]
        self.distance_km += c["km"]
        self.fuel_l += c["fuel_l"]
        if c["decel"] > 3.0 and not self._harsh:
            self.harsh_brake += 1
            self._harsh = True
        elif c["decel"] < 1.5:
            self._harsh = False
        bt = c.get("brake_temp", 0.0)
        self.max_brake_temp = max(self.max_brake_temp, bt)
        if bt > 300:
            self.brake_hot_min += dt_min
        moving = speed > 3
        if moving:
            b = _bin(speed, SPEED_EDGES)
            self.speed_km[b] += c["km"]
            self.speed_fuel_l[b] += c["fuel_l"]
            # fren enerjisi (kW·saat)
            self.e_retarder_kwh += c.get("p_ret", 0.0) * dt_h
            self.e_engbrake_kwh += c.get("p_eb", 0.0) * dt_h
            if c.get("brake", 0.0) > 0.02:
                self.service_brake_min += dt_min
                v = speed / 3.6
                m = c.get("mass_kg", 15000.0)
                p_total = m * max(0.0, c["decel"]) * v / 1000.0
                p_resist = (0.0065 * m * 9.81 + 0.5 * 1.2 * 6.0 * v * v) * v / 1000.0
                self.e_service_kwh += max(0.0, p_total - p_resist - c.get("p_ret", 0.0) - c.get("p_eb", 0.0)) * dt_h
        g = c.get("gear", 0)
        if moving and 0 < g < MAX_GEARS:
            self.gear_min[g] += dt_min
            if self._gear and g != self._gear:
                self.shifts += 1
        self._gear = g if g > 0 else self._gear
        if not c["running"]:
            self._overrev = False
            return
        self.engine_h += dt_h
        self.run_min += dt_min
        self.load_min_sum += c["load"] * dt_min
        self.rpm_min_sum += c["rpm"] * dt_min
        if moving:
            self.drive_h += dt_h
        elif c["load"] < 0.15:
            self.idle_h += dt_h
            self.idle_fuel_l += c["fuel_l"]
        self.rpm_load_min[_bin(c["rpm"], RPM_EDGES)][_bin(c["load"], LOAD_EDGES)] += dt_min
        if moving and c["load"] > 0.1 and 1000 <= c["rpm"] <= 1500:
            self.eco_min += dt_min
        if c["lugging"]:
            self.lugging_min += dt_min
        if c["overrev"]:
            self.overrev_min += dt_min
            if not self._overrev:
                self.overrev_events += 1
            self._overrev = True
        else:
            self._overrev = False
        if c["t_oil"] < 50 and c["load"] > 0.6:
            self.cold_load_min += dt_min
        if c["t_cool"] > 103:
            self.overheat_min += dt_min
        if c["retarder"]:
            self.retarder_min += dt_min
        if c["engine_brake"]:
            self.engine_brake_min += dt_min
        if c["cruise"]:
            self.cruise_min += dt_min
        if c["overrun"]:
            self.coast_min += dt_min
        self.max_coolant = max(self.max_coolant, c["t_cool"])
        self.max_oil_temp = max(self.max_oil_temp, c["t_oil"])

    def summary(self):
        drive_min = max(1e-6, self.drive_h * 60)
        eng_min = max(1e-6, self.engine_h * 60)
        per100 = 100.0 / max(1.0, self.distance_km)
        eco = clamp(self.eco_min / drive_min, 0, 1)
        idle = clamp(self.idle_h * 60 / eng_min, 0, 1)
        score = 100.0
        score -= (1 - eco) * 30
        score -= max(0.0, idle - 0.1) * 60
        score -= min(15.0, self.harsh_brake * per100 * 3)
        score -= min(15.0, self.lugging_min / drive_min * 150)
        score -= min(10.0, self.overrev_events * per100 * 5)
        score -= min(15.0, self.cold_load_min / eng_min * 300)
        score -= min(10.0, self.overheat_min / eng_min * 200)
        e_tot = self.e_service_kwh + self.e_retarder_kwh + self.e_engbrake_kwh
        bands = [(f * 100.0 / k) if k > 2.0 else None for f, k in zip(self.speed_fuel_l, self.speed_km)]
        gear_tot = sum(self.gear_min) or 1e-6
        gears = [{"gear": g, "pct": m / gear_tot * 100} for g, m in enumerate(self.gear_min) if m > 0.01]
        return {
            "engine_h": self.engine_h, "idle_h": self.idle_h, "drive_h": self.drive_h,
            "distance_km": self.distance_km, "fuel_l": self.fuel_l,
            "l_per_100km": self.fuel_l * per100 if self.distance_km > 1 else None,
            "eco_pct": eco * 100, "idle_pct": idle * 100,
            "cruise_pct": clamp(self.cruise_min / drive_min, 0, 1) * 100,
            "coast_pct": clamp(self.coast_min / drive_min, 0, 1) * 100,
            "retarder_pct": clamp(self.retarder_min / drive_min, 0, 1) * 100,
            "lugging_min": self.lugging_min, "overrev_events": self.overrev_events,
            "cold_load_min": self.cold_load_min, "overheat_min": self.overheat_min,
            "harsh_brake": self.harsh_brake, "starts": self.starts, "cold_starts": self.cold_starts,
            "failed_starts": self.failed_starts, "max_coolant": self.max_coolant,
            "max_oil_temp": self.max_oil_temp, "score": clamp(score, 0, 100),
            "rpm_load_min": self.rpm_load_min, "rpm_labels": RPM_LABELS, "load_labels": LOAD_LABELS,
            "avg_speed": self.distance_km / self.drive_h if self.drive_h > 0.01 else None,
            "avg_load": self.load_min_sum / self.run_min * 100 if self.run_min > 0.5 else None,
            "avg_rpm": self.rpm_min_sum / self.run_min if self.run_min > 0.5 else None,
            "idle_fuel_l": self.idle_fuel_l, "co2_kg": self.fuel_l * CO2_KG_PER_L,
            "speed_l100": bands, "speed_labels": SPEED_LABELS, "speed_km": self.speed_km,
            "gears": gears, "shifts_per_100": self.shifts * per100 if self.distance_km > 5 else None,
            "brake_service_pct": self.e_service_kwh / e_tot * 100 if e_tot > 0.05 else None,
            "brake_retarder_pct": self.e_retarder_kwh / e_tot * 100 if e_tot > 0.05 else None,
            "brake_engine_pct": self.e_engbrake_kwh / e_tot * 100 if e_tot > 0.05 else None,
            "brake_energy_kwh": e_tot, "service_brake_min": self.service_brake_min,
            "brake_hot_min": self.brake_hot_min, "max_brake_temp": self.max_brake_temp,
        }
