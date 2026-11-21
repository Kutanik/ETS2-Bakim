"""Akü: tır/otobüste 24 V grup (2 x 12 V seri), otomobilde 12 V tek akü (kurşun-asit) + alternatör + elektrik yükleri.
Voltajlar, eşikler, iç direnç, alternatör ve marş akımı sistem voltajına (volts) ve kapasiteye göre ölçeklenir.

Şarj durumu (SoC), sağlık (SoH), sülfatlaşma, sıcaklık, iç direnç, Peukert etkisi,
şarj kabulü, marş akımı (yağ viskozitesine bağlı), donma ve ECU voltaj düşmesi modellenir.
"""
from dataclasses import dataclass

from . import prices
from .i18n import M
from .util import clamp, ema, interp
from .wipers import wiper_current_a

ECU_MIN_V = 16.0          # 24 V: motor çalışırken bunun altında ECU resetlenir (12 V'ta yarısı)
CRANK_MIN_V = 14.0        # 24 V: marş sırasında bunun altında motor ateşleme devrine çıkamaz
CRANK_SLOW_V = 17.0
_FREEZE_SOC = ([0.0, 0.25, 0.5, 0.75, 1.0], [-7.0, -15.0, -25.0, -40.0, -60.0])


def electrical_load_a(f, electric_on, running, ambient=None, scale=1.0):
    """Telemetri ışık/donanım durumlarından yük akımı (A; 24 V tır ölçeği, scale: otomobil 0,6 · otobüs 1,25).
    Silecek akımı kademeye (aralıklı/yavaş/hızlı) ve soğukta cam üstündeki kar/buza göre değişir."""
    return _load_a(f, electric_on, running, ambient) * scale if electric_on else 0.08 * scale


def _load_a(f, electric_on, running, ambient):
    a = 0.08  # takograf, alarm, uyku modundaki ECU'lar
    if not electric_on:
        return a
    a += 9.0
    if running:
        a += 22.0
    L = f.lights
    if L["parking"]:
        a += 2.5
    if L["low"]:
        a += 6.0
    if L["high"]:
        a += 6.0
    a += 3.0 * L["aux_front"] + 5.0 * L["aux_roof"]
    if L["beacon"]:
        a += 3.0
    if L["brake"]:
        a += 3.0
    if L["reverse"]:
        a += 1.0
    if L["hazard"]:
        a += 4.0
    elif L["blink_l"] or L["blink_r"]:
        a += 2.0
    if f.wipers:
        a += wiper_current_a(f.wiper_stage, ambient)
    a += 0.8 * L["dash"]
    return a


# akü tipleri: iç direnç, döngü ömrü (derin deşarj dayanımı), sülfatlaşma ve kendi kendine boşalma katsayıları
KINDS = {
    "std": dict(name="Standart ağır hizmet (SHD)", r=1.0, cycle=1.0, sulf=1.0, self_dis=1.0),
    "efb": dict(name="EFB (güçlendirilmiş sulu)", r=0.92, cycle=2.0, sulf=0.7, self_dis=0.85),
    "agm": dict(name="AGM (cam elyaf, bakımsız)", r=0.8, cycle=3.0, sulf=0.5, self_dis=0.6),
    "gel": dict(name="Jel (derin deşarja dayanıklı)", r=0.9, cycle=4.0, sulf=0.4, self_dis=0.5),
    "agm_hd": dict(name="AGM ağır hizmet (park klimalı tırlar, yüksek çevrim)", r=0.75, cycle=4.5, sulf=0.4, self_dis=0.55),
}


def replace_cost(capacity_ah, kind="std", volts=24):
    """Akü değişimi (takma dahil): 12 V blok başına €/Ah, sistemdeki blok sayısı, tip katsayısı."""
    blocks = 2 if volts >= 24 else 1
    fit = prices.v("BATTERY_FIT", "truck" if blocks == 2 else "car")
    return prices.BATTERY_EUR_PER_AH * blocks * capacity_ah * prices.BATTERY_KIND.get(kind, 1.0) + fit


@dataclass
class Battery:
    capacity_ah: float = 225.0
    kind: str = "std"
    volts: int = 24               # sistem voltajı: 24 (tır, otobüs: 2 x 12 V seri) ya da 12 (otomobil)
    soc: float = 0.95
    soh: float = 1.0
    sulfation: float = 0.0
    temp: float = 15.0
    ah_out_total: float = 0.0
    efc: float = 0.0              # eşdeğer tam döngü
    minutes_age: float = 0.0
    frozen: bool = False
    # anlık (kayda gerek yok ama zararsız)
    current: float = 0.0          # + şarj, - deşarj (A)
    voltage: float = 25.4
    alt_current: float = 0.0
    load_current: float = 0.0
    charger: bool = False
    jump: bool = False

    # ---- sistem voltajına göre ölçek (24 V'ta 1, 12 V'ta 0,5)
    @property
    def blocks(self):
        return 2 if self.volts >= 24 else 1

    @property
    def vs(self):
        return self.blocks / 2.0

    @property
    def ecu_min_v(self):
        return ECU_MIN_V * self.vs

    @property
    def crank_min_v(self):
        return CRANK_MIN_V * self.vs

    @property
    def crank_slow_v(self):
        return CRANK_SLOW_V * self.vs

    @property
    def alt_max_a(self):
        return 110.0 if self.blocks == 2 else 140.0     # 24 V 110 A · 12 V 140 A alternatör

    @property
    def charger_a(self):
        return 25.0 if self.blocks == 2 else 10.0

    def _r_scale(self):
        # iç direnç: 225 Ah'lık tır çifti 1 (tırda eski davranış korunur); otomobilde tek blok, kapasiteyle azalır
        return 1.0 if self.blocks == 2 else 0.5 * (225.0 / max(30.0, self.capacity_ah)) ** 0.6

    def ocv(self, soc=None):
        s = self.soc if soc is None else soc
        return self.blocks * (11.80 + 0.95 * clamp(s, 0.0, 1.0))

    def r_int(self, soc=None, temp=None):
        s = self.soc if soc is None else soc
        t = self.temp if temp is None else temp
        r = 0.0055 * self._r_scale() * (1 + 4 * (1 - clamp(s, 0, 1)) ** 3) * (1 + 0.0186 * max(0.0, 25 - t))
        r *= (1 / max(0.15, self.soh)) ** 0.8 * (1 + 2 * self.sulfation) * self.k["r"]
        return r

    @property
    def k(self):
        return KINDS.get(self.kind, KINDS["std"])

    @property
    def freeze_point(self):
        return interp(self.soc, *_FREEZE_SOC)

    @property
    def usable_ah(self):
        cold = clamp(1 + 0.008 * (self.temp - 25), 0.4, 1.05)
        return self.capacity_ah * self.soh * (1 - self.sulfation) * cold

    def crank_current(self, oil_visc_cst):
        base = 450.0 if self.blocks == 2 else 160.0     # tır dizeli · otomobil motoru
        return base * clamp((oil_visc_cst / 100.0) ** 0.2, 1.0, 2.4)

    def crank_voltage(self, oil_visc_cst):
        if self.frozen:
            return 0.0
        return self.ocv() - self.crank_current(oil_visc_cst) * self.r_int()

    def crank(self, oil_visc_cst):
        """Marş denemesi. Dönüş: (başarılı, mesaj (i18n M sözlüğü ya da None), min_voltaj)."""
        i = self.crank_current(oil_visc_cst)
        if self.jump:
            v = (25.0 - i * 0.004) * self.vs
            ok = oil_visc_cst < 14000.0
            self.jump = False
            return ok, M("Takviye ile marş" if ok else "Takviye ile marş — yağ çok koyu, motor yine de dönmedi"), v
        v = self.crank_voltage(oil_visc_cst)
        secs = 2.0 if v > self.crank_slow_v else 6.0
        self._draw_ah(i * secs / 3600.0)
        if self.frozen:
            return False, M("Akü donmuş/hasarlı — marş yok"), 0.0
        if oil_visc_cst >= 14000.0:
            return False, M("Yağ çok koyu ({visc:,.0f} cSt): marş motoru motoru çeviremiyor", visc=oil_visc_cst), v
        if v < self.crank_min_v:
            return False, M("Akü yetersiz: marşta voltaj {v:.1f} V'a düştü", v=v), v
        if v < self.crank_slow_v:
            return True, M("Zorlu marş ({v:.1f} V) — akü zayıf", v=v), v
        return True, None, v

    def _draw_ah(self, ah):
        cap = max(1.0, self.capacity_ah * self.soh)
        self.soc = clamp(self.soc - ah / cap, 0.0, 1.0)
        self.ah_out_total += ah
        self.efc += ah / max(1.0, self.capacity_ah)

    def step(self, dt_s, c):
        """c: running, rpm, load_a, ambient, alternator_ok,
        rate (yaşlanma, sülfatlaşma, kendi kendine boşalma çarpanı), drain (yüklerden boşalma çarpanı)"""
        dt_h = dt_s / 3600.0
        r = c.get("rate", 1.0)
        self.minutes_age += dt_s / 60.0
        self.temp = ema(self.temp, c["ambient"], dt_s, 3 * 3600.0)
        cap = max(1.0, self.capacity_ah * self.soh * (1 - self.sulfation))
        load = c["load_a"]
        self.load_current = load

        alt_max = 0.0
        if c["running"] and c["alternator_ok"]:
            alt_max = self.alt_max_a * clamp(0.2 + 0.8 * (c["rpm"] - 400) / 700.0, 0.0, 1.0)
        if self.charger and not c["running"]:
            alt_max = load + self.charger_a
        v_reg = clamp(28.2 - 0.03 * (self.temp - 25), 27.4, 29.0) * self.vs
        if self.charger and not c["running"]:
            v_reg = 28.8 * self.vs

        ocv = self.ocv()
        r_ch = ((0.015 + 0.6 * self.soc ** 6) * (1 + 0.03 * max(0.0, 25 - self.temp)) * (1 + 3 * self.sulfation)
                * self._r_scale())
        accept = max(0.0, v_reg - ocv) / r_ch
        surplus = alt_max - load
        if self.frozen:
            accept = 0.0
        if surplus > 0:
            i_ch = min(surplus, accept)
            self.alt_current = load + i_ch
            self.current = i_ch
            self.voltage = min(v_reg, ocv + i_ch * r_ch) if alt_max > 0 else ocv
            self.soc = min(1.0, self.soc + i_ch * 0.88 * dt_h / cap)
        else:
            i_dis = -surplus
            self.alt_current = alt_max
            self.current = -i_dis
            i20 = self.capacity_ah / 20.0
            peuk = clamp((i_dis / i20) ** 0.2, 0.6, 2.0) if i_dis > 0 else 1.0
            ah = i_dis * peuk * dt_h * c.get("drain", 1.0)
            self._draw_ah(ah)
            # boşalmanın sonunda konsantrasyon polarizasyonu: voltaj hızla çöker
            collapse = 12.0 * self.vs * max(0.0, (0.10 - self.soc) / 0.10) ** 2 * clamp(i_dis / 5.0, 0.0, 1.0)
            self.voltage = max(0.0, self.ocv() - i_dis * self.r_int() - collapse)

        # kendi kendine deşarj (20 °C'de ~%3/ay, her 10 °C'de iki katı)
        self.soc = max(0.0, self.soc - 0.03 / 720.0 * 2 ** ((self.temp - 20) / 10.0) * self.k["self_dis"] * dt_h * r)

        # yaşlanma
        stress = 1 + 3 * max(0.0, 0.5 - self.soc)
        self.soh -= 0.003 * stress * (max(0.0, -self.current) * dt_h / max(1.0, self.capacity_ah)) / self.k["cycle"] * r
        self.soh -= 0.05 / 8760.0 * 2 ** ((self.temp - 25) / 10.0) * dt_h * r
        if self.soc < 0.7:
            self.sulfation += (0.7 - self.soc) * 0.001 * self.k["sulf"] * dt_h * r
        elif self.soc > 0.95 and self.current > 0:
            self.sulfation -= 0.0005 * dt_h
        self.sulfation = clamp(self.sulfation, 0.0, 0.6)
        self.soh = clamp(self.soh, 0.0, 1.0)

        # elektrolit donması
        if not self.frozen and self.temp < self.freeze_point:
            self.frozen = True
            self.soh *= 0.3
        return self.frozen

    def hours_until(self, soc_target, load_a):
        """Mevcut yükle hedef şarja kaç saat (oyun saati) kalır."""
        if load_a <= 0.01 or self.soc <= soc_target:
            return None
        cap = self.capacity_ah * self.soh * (1 - self.sulfation)
        return (self.soc - soc_target) * cap / load_a

    def min_start_soc(self, oil_visc_cst):
        """Bu yağ viskozitesi ve akü sıcaklığında marş için gereken en düşük şarj."""
        i = self.crank_current(oil_visc_cst)
        lo, hi = 0.0, 1.0
        if self.ocv(1.0) - i * self.r_int(1.0) < self.crank_min_v:
            return None
        for _ in range(30):
            mid = (lo + hi) / 2
            if self.ocv(mid) - i * self.r_int(mid) >= self.crank_min_v:
                hi = mid
            else:
                lo = mid
        return hi

    def replace(self, capacity_ah, kind="std"):
        self.capacity_ah = capacity_ah
        self.kind = kind if kind in KINDS else "std"
        self.soc, self.soh, self.sulfation = 0.95, 1.0, 0.0
        self.ah_out_total = self.efc = self.minutes_age = 0.0
        self.frozen = False
        return replace_cost(capacity_ah, self.kind, self.volts)

    def test(self, oil_visc_cst):
        nominal = 1150.0 if self.blocks == 2 else 760.0 * self.capacity_ah / 72.0   # otomobil AGM 72 Ah ~760 A
        cca = nominal * self.soh * (1 - self.sulfation) * (0 if self.frozen else 1)
        return {
            "ocv": self.ocv(), "soc_pct": self.soc * 100, "soh_pct": self.soh * 100,
            "r_int_mohm": self.r_int() * 1000, "cca": cca, "crank_v": self.crank_voltage(oil_visc_cst),
            "sulfation_pct": self.sulfation * 100, "efc": self.efc, "temp": self.temp, "kind": self.kind,
        }
