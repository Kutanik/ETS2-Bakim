"""Isıl model: soğutma suyu + motor bloğu düğümü, yağ düğümü, termostat, viskoz fan,
radyatör hava akışı, kabin kaloriferi, basınç kapağı, kaynama ve donma (blok/radyatör buzu).
"""
import math
from dataclasses import dataclass

from .util import clamp

LATENT_FUSION = 334.0    # kJ/kg
LATENT_VAPOR = 2260.0    # kJ/kg


@dataclass
class Thermal:
    t_cool: float = 15.0
    t_oil: float = 15.0
    fan_on: bool = False
    rad_ice: float = 0.0
    block_ice: float = 0.0
    sys_pressure: float = 0.0
    boiling: bool = False
    thermostat_open: float = 0.0

    UA_RAD_MAX = 3.2       # kW/K, tam hava akışında
    T_OPEN, T_FULL = 83.0, 95.0
    FAN_ON, FAN_OFF = 95.0, 89.0
    CAP_BAR = 0.75

    def step(self, dt_s, c, coolant, oil_volume_l):
        """c: running, rpm, speed_kmh, q_cool, q_oil, ambient, retarder_kw,
        thermostat_closed, thermostat_open_fault, fan_fail, combustion_gas
        Dönüş: kaynamayla kaybolan sıvı (L)."""
        n = max(1, int(math.ceil(dt_s / (5.0 if c["running"] else 60.0))))
        h = dt_s / n
        boiled = 0.0
        for _ in range(n):
            boiled += self._substep(h, c, coolant, oil_volume_l)
        return boiled

    def _substep(self, dt, c, coolant, oil_volume_l):
        amb = c["ambient"]
        running = c["running"]
        v = abs(c["speed_kmh"])
        rpm = c["rpm"]
        mass_cool = max(1.0, coolant.volume_l) * 1.07
        c_cool = mass_cool * 3.4 + 600.0
        c_oil = max(2.0, oil_volume_l) * 0.87 * 2.0 + 50.0
        lf = coolant.level_frac

        # termostat
        op = clamp((self.t_cool - self.T_OPEN) / (self.T_FULL - self.T_OPEN), 0.0, 1.0)
        if c["thermostat_closed"]:
            op = 0.0
        elif c["thermostat_open_fault"]:
            op = 1.0
        self.thermostat_open = op

        # viskoz fan (retarder kullanımında da devreye girer)
        if self.t_cool >= self.FAN_ON or c["retarder_kw"] > 100:
            self.fan_on = True
        elif self.t_cool < self.FAN_OFF and c["retarder_kw"] <= 50:
            self.fan_on = False
        fan = 0.0
        if running and self.fan_on and not c["fan_fail"]:
            fan = 0.6 * clamp(rpm / 1500.0, 0.35, 1.0)
        airflow = 0.06 + 0.7 * clamp(v / 90.0, 0.0, 1.3) ** 0.8 + fan

        # su pompası debisi
        flow = 0.0
        if running:
            flow = 1.0
            if lf < 0.6:
                flow *= clamp((lf - 0.3) / 0.3, 0.05, 1.0)   # kavitasyon
            flow *= 1.0 - self.block_ice
            if self.boiling:
                flow *= 0.6
        level_f = clamp((lf - 0.5) / 0.35, 0.05, 1.0)
        htf = coolant.heat_transfer_factor

        if running:
            q_rad = (self.UA_RAD_MAX * airflow * max(op, 0.03) * flow * level_f * htf
                     * (1 - self.rad_ice) * (self.t_cool - amb))
        else:
            q_rad = self.UA_RAD_MAX * 0.02 * level_f * (1 - self.rad_ice) * (self.t_cool - amb)
        q_loss = 0.10 * (1 + 0.5 * min(v, 100.0) / 90.0) * (self.t_cool - amb)
        q_oc = (1.6 * max(flow, 0.2) if running else 0.4) * (self.t_oil - self.t_cool)
        q_oil_loss = 0.03 * (1 + v / 90.0) * (self.t_oil - amb)
        q_heater = 0.0
        if running:
            q_heater = clamp((15 - amb) / 20.0, 0.0, 1.0) * 6.0 * clamp((self.t_cool - 40) / 30.0, 0.0, 1.0)

        q_net_cool = c["q_cool"] - q_rad - q_loss + q_oc - q_heater
        q_net_oil = c["q_oil"] - q_oc - q_oil_loss

        self.t_oil += q_net_oil / c_oil * dt

        # donma / çözülme (blok)
        tf = coolant.freeze_point
        latent = mass_cool * (1 - coolant.glycol) * LATENT_FUSION * 0.6 + 1.0
        new_t = self.t_cool + q_net_cool / c_cool * dt
        # faz değişimi (enerji korunumlu): donma noktasının altına inen ısı buza dönüşür, üstüne çıkan buzu eritir
        if new_t < tf and self.block_ice < 1.0:
            deficit = (tf - new_t) * c_cool
            freeze = min(1.0 - self.block_ice, deficit / latent)
            self.block_ice += freeze
            new_t = tf - (deficit - freeze * latent) / c_cool
        elif new_t > tf and self.block_ice > 0.0:
            surplus = (new_t - tf) * c_cool
            melt = min(self.block_ice, surplus / latent)
            self.block_ice -= melt
            new_t = tf + (surplus - melt * latent) / c_cool
        self.t_cool = new_t

        # radyatör buzu (termostat kapalıyken radyatördeki sıvı dış sıcaklığa iner)
        through = flow * max(op, 0.0)
        if amb < tf:
            self.rad_ice = min(1.0, self.rad_ice + (tf - amb) / (5.0 if not running else 10.0) * dt / 3600.0 * (1 - through))
        if through > 0.05 and self.t_cool > tf:
            self.rad_ice = max(0.0, self.rad_ice - through * (self.t_cool - tf) / 40.0 * dt / 60.0)

        # basınç ve kaynama
        if c["combustion_gas"] and running:
            p = self.CAP_BAR
        else:
            p = self.CAP_BAR * clamp((self.t_cool - 20.0) / 80.0, 0.0, 1.0) * clamp(lf / 0.8, 0.0, 1.0)
        self.sys_pressure = p
        bp = coolant.boil_point(p)
        boiled = 0.0
        self.boiling = False
        if self.t_cool > bp:
            excess_kj = (self.t_cool - bp) * c_cool
            self.t_cool = bp
            boiled = excess_kj / LATENT_VAPOR
            self.boiling = True
        return boiled
