"""Motor yağı: viskozite, TBN, is (soot), oksidasyon, yakıt seyrelmesi, su/glikol,
aşınma metalleri, filtre, tüketim, basınç ve laboratuvar analizi raporu.
"""
import math
import random
from dataclasses import dataclass

from . import prices
from .util import clamp

LOW_P_DELAY_S = 1.5   # düşük yağ basıncı uyarısı ancak bu kadar gerçek saniye sürerse çıkar (tek karelik sıçrama alarm vermez)
PUMP_FAULT_FRAC = 0.7  # yağ pompası arızasında basınç, devrin düşük basınç eşiğinin bu katında kalır

GRADES = {
    "15w40": dict(name="15W-40 Mineral (ACEA E7)", v_m20=8000.0, v40=108.0, v100=14.3, tbn=10.0,
                  ash=1.4, interval_km=60000, durability=1.0, ox_res=1.0, soot_limit=3.0,
                  shear_max=12.0, price=prices.OIL_L["15w40"]),
    "10w40": dict(name="10W-40 Sentetik (ACEA E4/E7)", v_m20=4000.0, v40=90.0, v100=14.0, tbn=15.0,
                  ash=1.8, interval_km=150000, durability=0.42, ox_res=2.5, soot_limit=3.5,
                  shear_max=6.0, price=prices.OIL_L["10w40"]),
    "5w30": dict(name="5W-30 Sentetik Low-SAPS (ACEA E6)", v_m20=1800.0, v40=70.0, v100=11.8, tbn=9.5,
                 ash=0.95, interval_km=120000, durability=0.55, ox_res=2.5, soot_limit=3.0,
                 shear_max=5.0, price=prices.OIL_L["5w30"]),
    # düşük küllü (Low-SAPS) yağlar DPF'yi daha geç doldurur; yüksek TBN'li E4 uzun aralık ama DPF'de çok kül bırakır
    "15w40e9": dict(name="15W-40 Low-SAPS (ACEA E9)", v_m20=7500.0, v40=112.0, v100=14.6, tbn=10.0,
                    ash=1.0, interval_km=60000, durability=0.95, ox_res=1.2, soot_limit=3.2,
                    shear_max=10.0, price=prices.OIL_L["15w40e9"]),
    "10w30e9": dict(name="10W-30 Low-SAPS (ACEA E9 / API CK-4)", v_m20=3600.0, v40=80.0, v100=11.6, tbn=10.0,
                    ash=1.0, interval_km=90000, durability=0.65, ox_res=1.8, soot_limit=3.2,
                    shear_max=7.0, price=prices.OIL_L["10w30e9"]),
    "10w40e6": dict(name="10W-40 Sentetik Low-SAPS (ACEA E6)", v_m20=4200.0, v40=92.0, v100=14.2, tbn=10.0,
                    ash=0.95, interval_km=120000, durability=0.5, ox_res=2.4, soot_limit=3.3,
                    shear_max=6.0, price=prices.OIL_L["10w40e6"]),
    "5w30e4": dict(name="5W-30 Tam Sentetik Uzun Ömürlü (ACEA E4)", v_m20=1700.0, v40=72.0, v100=12.0, tbn=15.0,
                   ash=1.9, interval_km=150000, durability=0.4, ox_res=2.8, soot_limit=3.5,
                   shear_max=5.0, price=prices.OIL_L["5w30e4"]),
    # 1.3.0: daha fazla ağır hizmet yağı (yeni nesil düşük küllü ve çok soğuk iklim için ince yağlar)
    "0w30e6": dict(name="0W-30 Tam Sentetik Low-SAPS (ACEA E6, çok soğuk iklim)", v_m20=1250.0, v40=62.0, v100=11.0,
                   tbn=10.0, ash=0.95, interval_km=150000, durability=0.45, ox_res=2.9, soot_limit=3.2,
                   shear_max=5.0, price=prices.OIL_L["0w30e6"]),
    "5w40e7": dict(name="5W-40 Sentetik (ACEA E7/E9)", v_m20=2200.0, v40=88.0, v100=14.1, tbn=11.0,
                   ash=1.1, interval_km=100000, durability=0.6, ox_res=2.0, soot_limit=3.3,
                   shear_max=6.0, price=prices.OIL_L["5w40e7"]),
    "10w40e11": dict(name="10W-40 Low-SAPS (ACEA E11 / API CK-4)", v_m20=4000.0, v40=95.0, v100=14.3, tbn=10.0,
                     ash=1.0, interval_km=110000, durability=0.55, ox_res=2.2, soot_limit=3.6,
                     shear_max=6.0, price=prices.OIL_L["10w40e11"]),
    "15w40ck4": dict(name="15W-40 Yarı Sentetik (API CK-4)", v_m20=7000.0, v40=110.0, v100=14.5, tbn=10.0,
                     ash=1.0, interval_km=75000, durability=0.85, ox_res=1.4, soot_limit=3.4,
                     shear_max=9.0, price=prices.OIL_L["15w40ck4"]),
    # eski motorlar için kalın mineral yağ: soğukta (-20 °C'de ~20.000 cSt) marş motoru çeviremez
    "20w50": dict(name="20W-50 Mineral (API CF, eski motorlar)", v_m20=20000.0, v40=165.0, v100=18.5, tbn=9.0,
                  ash=1.3, interval_km=30000, durability=1.4, ox_res=0.8, soot_limit=2.6,
                  shear_max=14.0, price=prices.OIL_L["20w50"]),
    # otomobil yağları (TruckersMP Škoda): VW onaylı; LongLife yağlar 30.000 km / 2 yıl, 502/505 15.000 km / 1 yıl
    "5w30vw": dict(name="5W-30 LongLife III (VW 504.00/507.00)", v_m20=1700.0, v40=68.0, v100=11.8, tbn=7.5,
                   ash=0.8, interval_km=30000, durability=0.6, ox_res=2.4, soot_limit=2.5,
                   shear_max=5.0, price=prices.OIL_L["5w30vw"], car=True),
    "0w20vw": dict(name="0W-20 LongLife IV (VW 508.00/509.00)", v_m20=950.0, v40=44.0, v100=8.4, tbn=7.0,
                   ash=0.75, interval_km=30000, durability=0.62, ox_res=2.6, soot_limit=2.3,
                   shear_max=4.0, price=prices.OIL_L["0w20vw"], car=True),
    "5w40vw": dict(name="5W-40 (VW 502.00/505.01)", v_m20=2300.0, v40=85.0, v100=13.8, tbn=10.0,
                   ash=1.2, interval_km=15000, durability=0.9, ox_res=1.5, soot_limit=2.5,
                   shear_max=8.0, price=prices.OIL_L["5w40vw"], car=True),
}


def grades_for(vehicle):
    """Araç sınıfına uygun yağlar: otomobile otomobil yağları, tır ve otobüse ağır vasıta yağları."""
    car = vehicle == "car"
    return {k: g for k, g in GRADES.items() if bool(g.get("car")) == car}
INTERVAL_DAYS = 365          # takvim sınırı (oyun günü)
FILTER_KM = 150000           # filtre doluluk referansı
FILTER_PRICE = prices.OIL_FILTER
RESIDUAL = 0.08              # değişimde motorda kalan eski yağ oranı
CRANK_LIMIT_CST = 14000.0    # bu viskozitenin üstünde marş motoru motoru ateşleme devrine çıkaramaz

LIMITS = {
    "tbn_frac": 0.5, "soot": None, "ox": 25.0, "fuel_dil": 2.5, "water": 2000.0, "glycol": 100.0,
    "fe": 100.0, "cu": 40.0, "pb": 30.0, "al": 20.0, "cr": 15.0, "si": 25.0, "k": 20.0,
    "visc_hi": 20.0, "visc_lo": -15.0,
}


def _walther_z(v):
    return math.log10(math.log10(v + 0.7))


def _walther_line(t1, v1, t2, v2):
    z1, z2 = _walther_z(v1), _walther_z(v2)
    l1, l2 = math.log10(t1 + 273.15), math.log10(t2 + 273.15)
    b = (z1 - z2) / (l2 - l1)
    a = z1 + b * l1
    return a, b


def walther(t_c, v_m20, v40, v100):
    """ASTM D341 (Walther) — -20/40/100 °C noktalarından parça parça viskozite (cSt)."""
    if t_c < 40.0:
        a, b = _walther_line(-20.0, v_m20, 40.0, v40)
    else:
        a, b = _walther_line(40.0, v40, 100.0, v100)
    z = a - b * math.log10(max(200.0, t_c + 273.15))
    return 10 ** (10 ** z) - 0.7


@dataclass
class Oil:
    grade: str = "10w40"
    capacity_l: float = 40.0
    volume_l: float = 40.0
    v_m20: float = 4000.0
    v40: float = 90.0
    v100: float = 14.0
    tbn: float = 15.0
    tbn_ref: float = 15.0
    ash_pct: float = 1.8
    soot: float = 0.0           # %
    ox: float = 0.0             # FTIR A/cm
    shear: float = 0.0          # % viskozite kaybı
    fuel_dil: float = 0.0       # %
    water: float = 0.0          # ppm
    glycol: float = 0.0         # ppm
    fe: float = 0.0
    cu: float = 2.0
    pb: float = 0.0
    al: float = 0.0
    cr: float = 0.0
    si: float = 3.0
    k: float = 0.0
    km: float = 0.0             # bu yağla gidilen km
    hours: float = 0.0          # bu yağla motor saati
    minutes_age: float = 0.0    # takvim yaşı (oyun dakikası)
    wear_km: float = 0.0        # değişim aralığına sayılan km (azalma hızı çarpanıyla; 1× = km)
    wear_min: float = 0.0       # değişim aralığına sayılan takvim yaşı (oyun dakikası, çarpanlı)
    filter_km: float = 0.0      # filtre dolmasına sayılan km (çarpanlı)
    consumed_l: float = 0.0
    total_consumed_l: float = 0.0

    # ---- türetilmiş özellikler ----
    @property
    def spec(self):
        return GRADES.get(self.grade, GRADES["10w40"])

    @property
    def level_frac(self):
        return self.volume_l / self.capacity_l if self.capacity_l > 0 else 0.0

    @property
    def min_frac(self):
        return 0.85

    def _visc_mult(self):
        return ((1 - self.shear / 100.0) * (1 + 0.045 * self.soot) * (1 - 0.04 * self.fuel_dil)
                * (1 + 0.006 * self.ox))

    def viscosity(self, t_c):
        m = self._visc_mult()
        return walther(t_c, self.v_m20 * m, self.v40 * m, self.v100 * m)

    def v100_change_pct(self):
        return (self._visc_mult() - 1.0) * 100.0

    def visc_ratio(self):
        return self._visc_mult()

    @property
    def filter_load(self):
        return self.filter_km / FILTER_KM * (1 + self.soot / 3.0)

    @property
    def filter_bypass(self):
        return self.filter_load >= 1.0

    def pressure_bar(self, rpm, t_oil, engine_wear, running, seized=False, pump_fault=False):
        if not running or seized or rpm < 100:
            return 0.0
        nu = self.viscosity(t_oil)
        p = 0.000563 * rpm * nu ** 0.6 * (1 - 0.4 * engine_wear)
        lf = self.level_frac
        if lf < 0.70:
            level_f = 0.3 + 0.7 * clamp((lf - 0.45) / 0.25, 0.0, 1.0) if lf >= 0.45 else 0.3 * lf / 0.45
            p *= level_f
        if pump_fault:
            # pompa arızası: basınç her devirde uyarı eşiğinin altında kalır (alarm), tek başına sıfıra düşmez
            p = min(p, PUMP_FAULT_FRAC * self.low_pressure_threshold(rpm))
        return min(6.0, p)

    def low_pressure_threshold(self, rpm):
        # tavan 2,5 bar: basınç tahliye valfinde 6 barla sınırlı; eşik onu aşınca sağlam motorda da "düşük" uyarısı çıkıyordu
        return min(2.5, 0.5 + 0.0007 * max(0.0, rpm - 600))

    def lubrication_factor(self):
        """Yağ kalitesinin motor aşınmasına etkisi (1 = ideal)."""
        g = self.spec
        f = 1.0
        f += 1.5 * max(0.0, self.soot / g["soot_limit"] - 0.7) / 0.3
        f += 2.0 * max(0.0, 0.85 - self.visc_ratio()) / 0.15
        f += 1.0 * max(0.0, 1.0 - self.tbn / (0.4 * self.tbn_ref))
        f += 1.0 * max(0.0, self.fuel_dil - 2.5)
        f += 3.0 if self.glycol > 200 else 0.0
        f += 2.0 * max(0.0, self.min_frac - self.level_frac) / 0.2
        f += 0.8 if self.filter_bypass else 0.0
        f += 0.5 * max(0.0, self.ox / LIMITS["ox"] - 0.8)
        return f

    # ---- zaman adımı ----
    def step(self, dt_s, c):
        """c: running, rpm, load, t_oil, fuel_l, km, lugging, idle, regen, engine_wear, overheat,
        glycol_leak_lph, oil_leak, rate (azalma hızı çarpanı; yaşlanma, kirlenme ve tüketimi ölçekler)"""
        dt_h = dt_s / 3600.0
        r = c.get("rate", 1.0)
        rh = dt_h * r
        self.minutes_age += dt_s / 60.0
        self.wear_min += dt_s / 60.0 * r
        if not c["running"]:
            # motor dururken: sadece sızıntı ve takvim yaşlanması
            if c.get("oil_leak"):
                self._lose(0.004 * dt_h)
            return
        g = self.spec
        v = max(5.0, self.volume_l)
        scale = 40.0 / v
        t = c["t_oil"]
        rpm = c["rpm"]
        load = c["load"]
        self.hours += dt_h
        self.km += c["km"]
        self.wear_km += c["km"] * r
        self.filter_km += c["km"] * r

        # yakıt/yağ maruziyeti
        e = c["fuel_l"] / v * r
        self.tbn *= math.exp(-0.001444 * g["durability"] * e * (1 + 0.5 * c["engine_wear"]))
        soot_mult = 1 + 2.0 * c["lugging"] + 1.5 * (t < 60) + 1.0 * c["idle"] + 2.0 * c["engine_wear"]
        self.soot += 0.0026 * e * soot_mult * c.get("soot_factor", 1.0)
        self.ox += 0.025 * 2 ** ((t - 100.0) / 10.0) / g["ox_res"] * rh
        self.shear += (g["shear_max"] - self.shear) * min(1.0, rh / 600.0 * (rpm / 1400.0) ** 2)

        # yakıt seyrelmesi ve su
        if c["idle"]:
            self.fuel_dil += 0.010 * rh
        if t < 60:
            self.fuel_dil += 0.08 * (60 - t) / 40.0 * rh
            self.water += 30.0 * rh
        if c["regen"]:
            self.fuel_dil += 0.12 * rh
        if t > 85:
            self.fuel_dil -= self.fuel_dil * 0.15 * (t - 85) / 20.0 * dt_h
        if t > 80:
            self.water *= math.exp(-dt_h * 1.5 * (t - 80) / 20.0)
        self.fuel_dil = max(0.0, self.fuel_dil)

        # soğutma suyu kaçağı (silindir kapak contası)
        if c["glycol_leak_lph"] > 0:
            leak_l = c["glycol_leak_lph"] * dt_h
            ppm = leak_l / v * 1e6
            self.glycol += ppm * 0.5
            self.water += ppm * 0.5
            self.k += ppm * 0.5 * 0.004

        # aşınma metalleri
        lub = self.lubrication_factor()
        cold = 1 + 2 * clamp((40 - t) / 60.0, 0.0, 1.0)
        base = rh * scale * lub * c.get("metal_factor", 1.0)
        self.fe += 0.045 * base * (0.6 + 0.8 * load) * cold * (1 + 1.5 * c["lugging"])
        self.cr += 0.006 * base * (1 + self.soot / 2.0)
        self.pb += 0.008 * base * (1 + 2 * max(0.0, 1 - self.tbn / (0.5 * self.tbn_ref))) * (1 + self.fuel_dil / 1.5) * (1 + 2 * c["lugging"])
        self.cu += 0.010 * base * (1 + 2 * max(0.0, 1 - self.tbn / (0.5 * self.tbn_ref)))
        self.al += 0.010 * base * (1 + 4 * c["overheat"])
        self.si += 0.015 * base * (1.5 if self.filter_bypass else 1.0)

        # tüketim
        f = (1 + 2 * max(0.0, (rpm - 1800) / 400)) * (1 + 3 * c["engine_wear"])
        f *= 1 + max(0.0, t - 115) / 15.0
        f *= 1 + 1.5 * max(0.0, 0.85 - self.visc_ratio()) / 0.15
        f *= 1 + 3 * max(0.0, self.level_frac - 1.05) / 0.1
        f *= c.get("burn_mult", 1.0)                       # turbo arızası: keçelerden yağ yakar
        loss = c["fuel_l"] * 0.0004 * f * r
        if c.get("oil_leak"):
            loss += 0.4 * c["km"] / 1000.0 + 0.02 * dt_h
        self._lose(loss)

    def _lose(self, liters):
        liters = min(liters, self.volume_l)
        self.volume_l -= liters
        self.consumed_l += liters
        self.total_consumed_l += liters

    def cold_start(self, t_oil):
        sev = clamp((50 - t_oil) / 70.0, 0.0, 1.0) * clamp((self.viscosity(t_oil) / 500.0) ** 0.25, 0.5, 2.5)
        self.fe += 0.4 * sev * 40.0 / max(5.0, self.volume_l)
        self.water += 20.0 * sev
        return sev

    def engine_stopped(self, t_oil):
        if t_oil < 70:
            self.water += (70 - t_oil) / 70.0 * 150.0

    def starvation_spike(self, severity):
        s = 40.0 / max(5.0, self.volume_l)
        self.pb += 3.0 * severity * s
        self.cu += 2.0 * severity * s
        self.fe += 2.0 * severity * s

    # ---- servis işlemleri ----
    def change(self, grade, filter_too=True, filter_price=None):
        g = GRADES[grade]
        r = RESIDUAL
        mix = lambda new, old: (1 - r) * new + r * old
        self.v_m20 = math.exp(mix(math.log(g["v_m20"]), math.log(self.v_m20)))
        self.v40 = math.exp(mix(math.log(g["v40"]), math.log(self.v40)))
        self.v100 = math.exp(mix(math.log(g["v100"]), math.log(self.v100)))
        self.tbn = mix(g["tbn"], self.tbn)
        self.tbn_ref = g["tbn"]
        self.ash_pct = g["ash"]
        for k in ("soot", "ox", "shear", "fuel_dil", "water", "glycol", "fe", "cu", "pb", "al", "cr", "k"):
            setattr(self, k, r * getattr(self, k))
        self.si = mix(3.0, self.si)
        self.grade = grade
        self.volume_l = self.capacity_l
        self.km = self.hours = self.minutes_age = self.consumed_l = self.wear_km = self.wear_min = 0.0
        if filter_too:
            self.filter_km = 0.0
        return self.capacity_l * g["price"] + ((FILTER_PRICE if filter_price is None else filter_price) if filter_too else 0.0)

    def top_up(self, grade, liters):
        g = GRADES[grade]
        liters = max(0.0, liters)
        v0 = self.volume_l
        tot = v0 + liters
        if tot <= 0:
            return 0.0
        x = liters / tot
        mixl = lambda old, new: math.exp((1 - x) * math.log(old) + x * math.log(new))
        self.v_m20 = mixl(self.v_m20, g["v_m20"])
        self.v40 = mixl(self.v40, g["v40"])
        self.v100 = mixl(self.v100, g["v100"])
        self.tbn = (1 - x) * self.tbn + x * g["tbn"]
        self.tbn_ref = (1 - x) * self.tbn_ref + x * g["tbn"]
        self.ash_pct = (1 - x) * self.ash_pct + x * g["ash"]
        for k in ("soot", "ox", "fuel_dil", "water", "glycol", "fe", "cu", "pb", "al", "cr", "k"):
            setattr(self, k, getattr(self, k) * (1 - x))
        self.shear *= (1 - x)
        self.si = (1 - x) * self.si + x * 3.0
        self.volume_l = tot
        return liters * g["price"]

    def change_filter(self):
        self.filter_km = 0.0
        return FILTER_PRICE

    # ---- değerlendirme ----
    def life_breakdown(self):
        g = self.spec
        tbn_lim = LIMITS["tbn_frac"] * self.tbn_ref
        vchg = self.v100_change_pct()
        items = {
            "TBN (asit nötrleme)": (self.tbn - tbn_lim) / max(0.01, self.tbn_ref - tbn_lim),
            "İs (soot)": 1 - self.soot / g["soot_limit"],
            "Oksidasyon": 1 - self.ox / LIMITS["ox"],
            "Yakıt seyrelmesi": 1 - self.fuel_dil / LIMITS["fuel_dil"],
            "Viskozite": 1 - (vchg / LIMITS["visc_hi"] if vchg >= 0 else vchg / LIMITS["visc_lo"]),
            "Su": 1 - self.water / LIMITS["water"],
            "Değişim aralığı (km)": 1 - self.wear_km / g["interval_km"],
            "Değişim aralığı (takvim)": 1 - self.wear_min / (INTERVAL_DAYS * 1440.0),
        }
        if self.glycol > LIMITS["glycol"]:
            items["Glikol kirliliği"] = 0.0
        return {k: clamp(v, 0.0, 1.0) for k, v in items.items()}

    def life(self):
        br = self.life_breakdown()
        key = min(br, key=br.get)
        return br[key], key

    @staticmethod
    def _status(val, warn, crit):
        if val >= crit:
            return "kritik"
        if val >= warn:
            return "dikkat"
        return "normal"

    def lab_report(self, odometer, game_minutes):
        """Gerçek bir yağ analizi laboratuvar raporu gibi ölçüm (küçük ölçüm hatasıyla)."""
        rnd = random.Random()
        n = lambda x, rel=0.04, ab=0.0: max(0.0, x * (1 + rnd.gauss(0, rel)) + rnd.gauss(0, ab))
        g = self.spec
        tbn_frac = self.tbn / self.tbn_ref
        v100 = self.viscosity(100.0)
        vchg = self.v100_change_pct()
        # satır: (ölçüt msgid, değer, ondalık, birim, durum, değer yerine metin msgid)
        rows = [
            ("Viskozite @100°C", n(v100, 0.01), 1, "cSt", "kritik" if (vchg > 20 or vchg < -15) else "dikkat" if (vchg > 12 or vchg < -10) else "normal", None),
            ("TBN", n(self.tbn, 0.03), 1, "mg KOH/g", "kritik" if tbn_frac < 0.5 else "dikkat" if tbn_frac < 0.65 else "normal", None),
            ("İs (soot)", n(self.soot, 0.05), 2, "%", self._status(self.soot / g["soot_limit"], 0.7, 1.0), None),
            ("Oksidasyon", n(self.ox, 0.05), 1, "A/cm", self._status(self.ox, 18, 25), None),
            ("Yakıt seyrelmesi", n(self.fuel_dil, 0.08, 0.05), 1, "%", self._status(self.fuel_dil, 1.5, 2.5), None),
            ("Su", n(self.water, 0.1, 20), 0, "ppm", self._status(self.water, 1000, 2000), None),
            ("Glikol", None, 0, "", "kritik" if self.glycol > 50 else "normal", "Pozitif" if self.glycol > 50 else "Negatif"),
            ("Demir (Fe)", n(self.fe, 0.05, 0.5), 0, "ppm", self._status(self.fe, 60, 100), None),
            ("Krom (Cr)", n(self.cr, 0.08, 0.2), 0, "ppm", self._status(self.cr, 8, 15), None),
            ("Kurşun (Pb)", n(self.pb, 0.08, 0.3), 0, "ppm", self._status(self.pb, 15, 30), None),
            ("Bakır (Cu)", n(self.cu, 0.06, 0.3), 0, "ppm", self._status(self.cu, 25, 40), None),
            ("Alüminyum (Al)", n(self.al, 0.08, 0.3), 0, "ppm", self._status(self.al, 10, 20), None),
            ("Silisyum (Si)", n(self.si, 0.06, 0.3), 0, "ppm", self._status(self.si, 15, 25), None),
            ("Potasyum (K)", n(self.k, 0.1, 0.3), 0, "ppm", self._status(self.k, 10, 20), None),
        ]
        notes = []
        if self.glycol > 50:
            notes.append("Yağda soğutma sıvısı (glikol + potasyum) var: silindir kapak contası / yağ soğutucusu kaçağı. Motoru çalıştırmayın, acil servis.")
        if self.soot / g["soot_limit"] >= 0.7:
            notes.append("İs yüksek: uzun rölanti ve düşük devirde yüksek yük (lugging) azaltılmalı; enjektör/EGR kontrolü önerilir.")
        if self.fuel_dil >= 1.5:
            notes.append("Yakıt seyrelmesi: kısa mesafe, soğuk çalışma ve uzun rölanti yağa yakıt karıştırır. Motoru tam ısıtacak sürüşler yapın.")
        if tbn_frac < 0.65:
            notes.append("TBN düşüyor: yağın asit nötrleme rezervi azaldı, korozif aşınma riski artıyor. Yağ değişimi planlayın.")
        if self.fe >= 60:
            notes.append("Demir yüksek: gömlek/segman/eksantrik aşınması. Soğuk motora yüklenme ve yağ kalitesi kontrol edilmeli.")
        if self.pb >= 15 or self.cu >= 25:
            notes.append("Kurşun/bakır yüksek: yatak aşınması işareti (düşük yağ basıncı, lugging, yakıt seyrelmesi).")
        if self.al >= 10:
            notes.append("Alüminyum yüksek: piston aşınması, motor aşırı ısınmış olabilir.")
        if self.si >= 15:
            notes.append("Silisyum yüksek: toz girişi; hava filtresi ve yağ filtresi (bypass) kontrol edilmeli.")
        if self.water >= 1000:
            notes.append("Su yüksek: yoğuşma (kısa sürüşler) veya sızıntı. Uzun ve sıcak bir sürüş suyu buharlaştırır.")
        if not notes:
            notes.append("Yağ ve motor durumu normal. Mevcut bakım aralığına devam edilebilir.")
        life, limiting = self.life()
        return {
            "version": 2, "odometer": odometer, "game_minutes": game_minutes, "grade": g["name"],
            "oil_km": self.km, "oil_hours": self.hours, "rows": rows, "notes": notes,
            "life": life, "limiting": limiting,
        }
