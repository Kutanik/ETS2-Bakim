"""Şanzıman ve debriyaj: şanzıman yağı sıcaklığı ve ömrü, debriyaj ısınması ve balata aşınması.

Şanzıman yağı (oyun saatiyle, motorun ısıl modeliyle aynı ölçekte): dişli ve yatak kayıpları (doğrudan viteste
iletilen gücün ~%1,5'i, ara viteslerde ~%2,5'i) ve çalkalama kaybı yağı ısıtır. Retarderli tırlarda yağ-su eşanjörü
yağı motor soğutma suyuna bağlar (soğukta ısıtır, sıcakta soğutur); retardersizde yalnızca gövde ve kavrama muhafazası
üzerinden zayıf bir bağ vardır. Hidrodinamik retarder (intarder) şanzıman yağını paylaşır: frenleme gücünün küçük bir
kısmı yağda kalır. Yokuşta uzun süre tam yük ya da sıcak havada uzun retarder kullanımı yağı ısıtır; soğutucu arızası
bunu çok hızlandırır. Yağ 100 °C üstünde daha hızlı yaşlanır, yaşlı yağ kayıpları artırır.

Debriyaj (gerçek saniyeyle: kayma, oyunun gerçek zamanlı araç fiziğinden doğar): motor devri ile şanzıman giriş mili
devri (tekerlek hızı, vites oranı, diferansiyel ve tekerlek yarıçapından) arasındaki fark ve kavrama oranı kayma
gücünü verir. Yalnızca debriyaj gerçekten yarım kavrarken (kalkış, manevra, yarım debriyajla sürünme) hesaplanır; tam
kavramışken ölçüm hatası ısı sayılmaz. Isı balatada ve baskı plakasında birikir, dönen volanla soğur. Balata kayma
enerjisiyle aşınır, 200 °C üstünde hızla. Aktüatör arızasında ya da balata bitince debriyaj yükte kayar.
"""
import math
from dataclasses import dataclass

from .util import clamp

OIL_WARN_C, OIL_CRIT_C = 115.0, 130.0          # şanzıman yağı (ZF / I-Shift / Opticruise sınırları civarı)
CLUTCH_WARN_C, CLUTCH_CRIT_C = 250.0, 320.0    # debriyaj aşırı yük uyarısı
CLUTCH_WARN_WEAR = 0.85
OIL_INTERVAL_KM = {"truck": 450000.0, "bus": 450000.0, "car": 60000.0}   # sentetik şanzıman yağı / DSG yağı
OIL_L = {"truck": 15.0, "bus": 15.0, "car": 6.0}
CLUTCH_LIFE_KM = {"truck": 700000.0, "bus": 500000.0, "car": 180000.0}   # tahmin için olağan ömür
LIFE_MJ = {"truck": 20000.0, "bus": 16000.0, "car": 2500.0}              # balatanın kaldırdığı kayma enerjisi
C_OIL = {"truck": 120.0, "bus": 120.0, "car": 25.0}                       # kJ/K (yağ + dişliler + gövde)
C_CLUTCH = {"truck": 15.0, "bus": 15.0, "car": 4.0}                       # kJ/K (balata, baskı plakası, volan yüzü)
SIZE = {"truck": 1.0, "bus": 1.0, "car": 0.35}                            # soğutma ve çalkalama ölçeği


def gear_ratio(f):
    """Şu anki vitesin oranı (geri viteste geri oranı); bilinmiyorsa 0."""
    g = f.gear
    if g > 0 and g <= len(f.gear_ratios):
        return abs(f.gear_ratios[g - 1])
    rev = getattr(f, "gear_ratios_rev", None) or []
    if g < 0:
        if -g <= len(rev):
            return abs(rev[-g - 1])
        return abs(f.gear_ratios[0]) if f.gear_ratios else 0.0
    return 0.0


def slip_kw(c):
    """Debriyajda ısıya dönen kayma gücü (kW). c: running, rpm, p_kw, clutch, gear, ratio, speed, wheel_r, diff,
    peak_nm. Debriyaj 0 = tam kavramış, 1 = tam ayrık (oyunun etkin debriyaj değeri)."""
    if not c["running"] or c["gear"] == 0 or c["rpm"] < 300 or c["p_kw"] <= 0:
        return 0.0
    cl = c["clutch"]
    if not 0.03 < cl < 0.97:
        return 0.0
    if c["ratio"] <= 0 or c["diff"] <= 0 or c["wheel_r"] <= 0:
        return 0.0
    rpm_in = abs(c["speed"]) / 3.6 / c["wheel_r"] * c["ratio"] * c["diff"] * 60.0 / (2 * math.pi)
    slip = c["rpm"] - rpm_in
    if slip < max(60.0, 0.06 * c["rpm"]):
        return 0.0
    w_eng = c["rpm"] * 2 * math.pi / 60.0
    torque = min(c["p_kw"] * 1000.0 / w_eng, 1.8 * c["peak_nm"] * (1.0 - cl))   # kavrama oranı aktarılan torku sınırlar
    return torque * slip * 2 * math.pi / 60.0 / 1000.0


@dataclass
class Transmission:
    t_oil: float = 15.0
    t_clutch: float = 15.0
    clutch_wear: float = 0.0       # balata aşınması (0 yeni, 1 bitti)
    clutch_km: float = 0.0         # debriyaj takıldığından (ya da ilk görüldüğünden) beri km
    wear_acc: float = 0.0          # aynı dönemde eklenen aşınma (kalan ömür tahmini için)
    oil_km: float = 0.0            # şanzıman yağı km (gerçek)
    oil_wear_km: float = 0.0       # aralığa sayılan km (hız çarpanı ve sıcaklıkla)
    ready: bool = False
    slip_kw: float = 0.0           # anlık kayma gücü (gösterim)

    def first_setup(self, odo, rnd, ambient, veh="truck"):
        """İlk görülüşte kilometreye göre makul bir başlangıç (bakım geçmişi bilinmiyor)."""
        self.t_oil = self.t_clutch = ambient
        if odo >= 2000:
            self.oil_km = self.oil_wear_km = rnd.uniform(0.1, 0.8) * OIL_INTERVAL_KM[veh]
            self.clutch_wear = rnd.uniform(0.1, 0.55)
        self.ready = True

    def oil_used(self, veh):
        return self.oil_wear_km / OIL_INTERVAL_KM[veh]

    def clutch_left_km(self, veh, rate=1.0):
        """Tahmini kalan debriyaj ömrü (km): yeterli veri varsa bu tırın kendi aşınma hızından."""
        left = max(0.0, 1.0 - self.clutch_wear)
        if self.clutch_km > 1000 and self.wear_acc > 1e-4:
            return left * self.clutch_km / self.wear_acc
        return None if rate <= 0 else left * CLUTCH_LIFE_KM[veh] / rate

    def step_oil(self, dt, c):
        """Şanzıman yağı (dt: oyun sn). c: running, p_kw (motor + motor freni), gear, ratio, speed, t_cool, ambient,
        retarder_kw, has_retarder, cooler_fault, km, rate, veh"""
        veh, sz, v = c["veh"], SIZE[c["veh"]], abs(c["speed"])
        loss = 0.0
        if c["running"] and c["gear"] != 0:
            loss += (0.015 if abs(c["ratio"] - 1.0) < 0.06 else 0.025) * max(0.0, c["p_kw"])
        loss += sz * (0.15 * bool(c["running"]) + 0.6 * min(v, 130.0) / 90.0)
        loss *= 1.0 + 0.15 * clamp(self.oil_used(veh) - 1.0, 0.0, 2.0)      # yaşlı yağ: sürtünme artar
        if c["has_retarder"]:
            loss += 0.03 * max(0.0, c["retarder_kw"])
        ua_x = (0.25 if c["has_retarder"] else 0.10) * sz                     # eşanjör / yalnızca gövde bağı (kW/K)
        if c["cooler_fault"]:
            ua_x *= 0.15
        if not c["running"]:
            ua_x *= 0.3                                                        # su pompası durunca eşanjörde akış yok
        ua_air = sz * (0.04 + 0.08 * min(v / 90.0, 1.3) ** 0.8)              # kanatlı gövde, araç altı hava akışı
        ua = ua_x + ua_air
        t_ss = (loss + ua_x * c["t_cool"] + ua_air * c["ambient"]) / ua
        self.t_oil = t_ss + (self.t_oil - t_ss) * math.exp(-dt * ua / C_OIL[veh])
        km = c.get("km", 0.0)
        if km > 0:
            heat = 2.0 ** clamp((self.t_oil - 100.0) / 15.0, 0.0, 2.0)          # 100 °C üstünde hızlı yaşlanma
            self.oil_km += km
            self.oil_wear_km += km * c["rate"] * heat

    def step_clutch(self, dt_real, c):
        """Debriyaj (dt_real: gerçek sn). c: running, rpm, p_kw, load, clutch, gear, ratio, speed, wheel_r, diff,
        peak_nm, actuator_fault, ambient, t_cool, km, rate, veh"""
        veh = c["veh"]
        p = slip_kw(c)
        if c["running"] and c["gear"] != 0 and c["clutch"] <= 0.03:
            # aktüatör arızası ya da bitmiş balata: baskı yetmez, debriyaj yükte kayar
            if c["actuator_fault"] and c["load"] > 0.6:
                p += 0.03 * c["p_kw"]
            if self.clutch_wear >= 1.0 and c["load"] > 0.5:
                p += 0.06 * c["p_kw"]
        self.slip_kw = p
        ua = SIZE[veh] * (0.012 + (0.03 * min(c["rpm"] / 1500.0, 1.3) if c["running"] else 0.0))
        env = c["ambient"] + 0.5 * (c["t_cool"] - c["ambient"])              # kavrama muhafazası motora bitişik
        t_ss = env + p / ua
        self.t_clutch = t_ss + (self.t_clutch - t_ss) * math.exp(-dt_real * ua / C_CLUTCH[veh])
        if p > 0:
            hot = 1.0 + max(0.0, (self.t_clutch - 200.0) / 60.0) ** 2
            dw = p * dt_real / 1000.0 / LIFE_MJ[veh] * hot * c["rate"]
            self.clutch_wear = min(1.2, self.clutch_wear + dw)
            self.wear_acc += dw
        km = c.get("km", 0.0)
        if km > 0:
            self.clutch_km += km

    def parked(self, dt, ambient, t_cool, veh="truck"):
        """Motor kapalı geçen süre (uyku, feribot): yağ ve debriyaj dış sıcaklığa doğru soğur."""
        self.step_oil(dt, dict(running=False, p_kw=0.0, gear=0, ratio=0.0, speed=0.0, t_cool=t_cool, ambient=ambient,
                               retarder_kw=0.0, has_retarder=False, cooler_fault=False, km=0.0, rate=1.0, veh=veh))
        self.t_clutch = ambient + (self.t_clutch - ambient) * math.exp(-dt * 0.012 / C_CLUTCH[veh])
        self.slip_kw = 0.0

    def change_oil(self):
        self.oil_km = self.oil_wear_km = 0.0

    def replace_clutch(self):
        self.clutch_wear = self.clutch_km = self.wear_acc = 0.0
