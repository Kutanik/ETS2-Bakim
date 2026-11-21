"""Motor: tork eğrisi, yük, yakıt, ısı üretimi, egzoz sıcaklığı ve motor sağlığı.

Tüm süreç hızları OYUN zamanıyla (oyun saniyesi) hesaplanır; ETS2'nin kilometre ve yakıt
ekonomisi de oyun zamanına göre ölçeklenmiştir, böylece hepsi birbiriyle tutarlı kalır.
"""
import math
from dataclasses import dataclass

from .util import clamp, ema, interp

LHV_KJ_PER_L = 43000.0 * 0.835   # dizel alt ısıl değeri, kJ/L
ETA_IND = 0.47                   # endike verim


@dataclass
class EngineSpec:
    name: str = "Bilinmeyen motor (500 hp varsayıldı)"
    power_kw: float = 368.0
    rated_rpm: float = 1800.0
    idle_rpm: float = 600.0
    displacement_l: float = 13.0
    oil_capacity_l: float = 40.0
    coolant_capacity_l: float = 70.0
    battery_ah: float = 225.0
    has_dpf: bool = True
    torque_nm: float = 0.0          # 0 → güçten türetilir
    mode: str = "auto"              # auto: veritabanı + sürüşten algılama, manual: kullanıcı seçti
    engine_id: str = ""
    model_key: str = ""
    model_name: str = ""
    electric: bool = False
    vehicle: str = "truck"          # algılanan sınıf: truck | bus | car (vehicles.py)
    vehicle_override: str = "auto"  # Ayarlar → Araç tipi: auto (algılanan) | truck | bus | car
    fuel: str = "diesel"            # diesel | petrol
    real_torque_nm: float = 0.0     # otomobil, elle girilen motor: gösterilen gerçek tork (model kullanmaz)

    def _omega_rated(self):
        return self.rated_rpm * 2 * math.pi / 60

    def peak_torque_nm(self):
        if self.torque_nm > 0:
            return self.torque_nm
        return self.power_kw * 1000.0 / self._omega_rated() * 1.30

    def rated_torque_nm(self):
        return min(self.peak_torque_nm(), self.power_kw * 1000.0 / self._omega_rated())

    def max_torque_nm(self, rpm):
        r = self.rated_rpm
        tp, tr = self.peak_torque_nm(), self.rated_torque_nm()
        pe = min(1400.0, r - 100.0)
        return interp(rpm, [400, 900, 1000, pe, r, r + 300, r + 500],
                      [0.45 * tp, 0.92 * tp, tp, tp, tr, 0.7 * tr, 0.0])

    def max_power_kw(self, rpm):
        return self.max_torque_nm(rpm) * rpm * 2 * math.pi / 60 / 1000.0

    def friction_kw(self, rpm):
        if rpm < 50:
            return 0.0
        return self.displacement_l / 13.0 * (0.010 * rpm + 4e-6 * rpm * rpm)


class EngineSim:
    """Her karede yeniden hesaplanan anlık motor büyüklükleri (kaydedilmez)."""

    def __init__(self, spec):
        self.spec = spec
        self.fuel_meas_lps = None
        self._acc_fuel = 0.0
        self._acc_dt = 0.0
        self.exh_temp = 20.0
        self.rpm = self.load = self.p_brake = self.p_fric = 0.0
        self.p_eb = self.p_ret = self.fuel_lps = self.fuel_power = 0.0
        self.q_cool = self.q_oil = 0.0
        self.overrun = False
        self.fuel_source = "model"

    def feed_fuel(self, dfuel_l, dt_game, running):
        """Oyunun yakıt göstergesinden gerçek tüketimi ölçer (depo dolumunda sıfırlanır)."""
        if dfuel_l < -0.05 or not running:
            self._acc_fuel = self._acc_dt = 0.0
            if not running:
                self.fuel_meas_lps = None
            return
        self._acc_fuel += max(0.0, dfuel_l)
        self._acc_dt += dt_game
        if self._acc_dt >= 20.0:
            rate = self._acc_fuel / self._acc_dt
            self.fuel_meas_lps = ema(self.fuel_meas_lps, rate, self._acc_dt, 30.0)
            self._acc_fuel = self._acc_dt = 0.0

    def update(self, f, running, dt_game, ambient, accessory_kw, regen_active, rpm_k=1.0):
        """rpm_k: oyun devrinin motor modelinin devir ölçeğine oranı (gerçek devir ölçekli otomobil modunda > 1;
        vehicles.rpm_scale). Gösterilen devir oyununki, güç ve sürtünme küçültülmüş devirden."""
        s = self.spec
        self.rpm = f.rpm if running else 0.0
        mr = self.rpm / rpm_k
        self.load = clamp(f.throttle, 0.0, 1.0) if running else 0.0
        pmax = s.max_power_kw(mr)
        self.p_brake = self.load * pmax
        self.p_fric = s.friction_kw(mr)
        self.overrun = running and self.load < 0.02 and mr > s.idle_rpm + 150 and abs(f.speed_kmh) > 3
        if running and not self.overrun:
            est_power = (self.p_brake + self.p_fric + accessory_kw) / ETA_IND
        else:
            est_power = 0.0
        est_lps = est_power / LHV_KJ_PER_L
        meas = self.fuel_meas_lps
        # oyunun ölçülen tüketimi ancak modelle makul uyumdaysa kullanılır (yakıt tüketimi kapalı vb. durumlar)
        if (running and meas is not None and not self.overrun and est_lps > 0
                and 0.35 * est_lps <= meas <= 3.0 * est_lps):
            self.fuel_lps = meas
            self.fuel_source = "oyun"
        else:
            self.fuel_lps = est_lps
            self.fuel_source = "model"
        self.fuel_power = self.fuel_lps * LHV_KJ_PER_L

        self.p_eb = 0.0
        if running and f.motor_brake and self.load < 0.02:
            self.p_eb = 250.0 * s.displacement_l / 13.0 * clamp((mr - 900) / 1100, 0.0, 1.0)
        self.p_ret = 0.0
        if f.retarder_steps > 0 and f.retarder_level > 0:
            self.p_ret = 450.0 * (f.retarder_level / f.retarder_steps) * clamp(abs(f.speed_kmh) / 80.0, 0.0, 1.0)

        self.q_cool = 0.21 * self.fuel_power + 0.5 * self.p_fric + 0.25 * self.p_eb + self.p_ret
        self.q_oil = 0.02 * self.fuel_power + 0.4 * self.p_fric

        if running:
            if self.overrun:
                target = ambient + (200.0 if self.p_eb > 0 else 80.0)
            else:
                target = ambient + 110.0 + 360.0 * self.load
            if regen_active:
                target = max(target, 580.0)
            tau = 60.0
        else:
            target, tau = ambient, 600.0
        self.exh_temp = ema(self.exh_temp if self.exh_temp is not None else ambient, target, dt_game, tau)

    @property
    def fuel_lph(self):
        return self.fuel_lps * 3600.0


@dataclass
class EngineHealth:
    health: float = 100.0          # % (100 = yeni motor)
    head_gasket_stress: float = 0.0
    seize_stress: float = 0.0
    starvation_s: float = 0.0
    wear_rate_ema: float = 1.0     # son dönem aşınma çarpanı

    BASE_PER_H = 0.004  # normal kullanımda % / motor saati  (~20.000 saatte revizyon)

    @property
    def wear(self):
        return clamp(1.0 - self.health / 100.0, 0.0, 1.0)

    def step(self, dt_h, running, mult):
        if not running or dt_h <= 0:
            return
        self.wear_rate_ema = ema(self.wear_rate_ema, mult, dt_h, 20.0)
        self.health = max(0.0, self.health - self.BASE_PER_H * mult * dt_h)

    def damage(self, pct):
        self.health = max(0.0, self.health - pct)
