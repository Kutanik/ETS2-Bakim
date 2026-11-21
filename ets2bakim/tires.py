"""Lastikler: diş derinliği, basınç, sıcaklık, yavaş patlak ve patlama.

SCS telemetrisi lastikler için yalnızca oyunun genel tekerlek hasarını (wearWheels) ve tekerlek düzenini
(yönlendirilen, çekişli, kaldırılabilir dingil, yerde mi, yol yüzeyi, direksiyon açısı) verir. Diş derinliği, basınç
ve sıcaklık burada dingil grubu başına hesaplanır:

  ön (yönlendirilen)  · çekiş (tahrikli, çift lastik) · taşıyıcı (kaldırılabilir / yönlendirilen arka dingil)

Aşınma km başına; yük, hız, basınç (düşük basınç omuzları, yüksek basınç ortayı yer), lastik sıcaklığı, sert fren,
viraj (ön), çekiş (tahrikli) ve yol yüzeyi (toprak/çakıl 2 kat) ile değişir. Kaldırılmış dingil aşınmaz.
Basınç doğal olarak ayda ~0,15 bar düşer; yavaş patlak saatte 0,3–1,2 bar kaçırır. Sıcak basınç gaz yasasıyla
hesaplanır. Düşük basınçla hızlı giden lastik ısınır; ısınıp çok inen ya da dişi bitmiş lastik patlayabilir.
"""
import math
from dataclasses import dataclass, field

from . import prices
from .i18n import M
from .util import clamp

# tır / otobüs: ön (yönlendirilen), çekiş, taşıyıcı · otomobil: ön ve arka (tekil lastik, ~2,5 bar, 8 mm yeni diş)
GROUPS = ("steer", "drive", "tag", "front", "rear")
CAR_GROUPS = ("front", "rear")
GROUP_NAMES = {"steer": "ön dingil", "drive": "çekiş dingili", "tag": "taşıyıcı dingil",
               "front": "ön lastikler", "rear": "arka lastikler"}
NEW_TREAD_MM = {"steer": 16.0, "drive": 20.0, "tag": 16.0, "front": 8.0, "rear": 8.0}
NOMINAL_BAR = {"steer": 9.0, "drive": 8.5, "tag": 8.5, "front": 2.5, "rear": 2.4}   # soğuk basınç
WARN_TREAD_MM = {"steer": 4.0, "drive": 3.0, "tag": 3.0, "front": 3.0, "rear": 3.0}  # önerilen değişim
LEGAL_MM = 1.6                                               # AB yasal en az diş derinliği
# otomobilde önden çekiş: ön lastikler ~45.000 km, arkalar ~70.000 km dayanır
WEAR_MM_PER_1000KM = {"steer": 0.085, "drive": 0.09, "tag": 0.10, "front": 0.14, "rear": 0.09}
PRICE = prices.TIRE
MOUNT_PRICE = prices.TIRE_MOUNT
PUNCTURE_REPAIR_PRICE = prices.PUNCTURE_REPAIR
# lastik sınıfları: fiyat katsayısı, aşınma katsayısı, patlama sıcaklık eşiği; kaplama yalnız arka dingillere takılır
TIERS = {
    "premium": dict(name="Premium (Michelin, Continental, Bridgestone…)", price=1.0, wear=1.0, blow_temp=115.0, rear_only=False),
    "mid": dict(name="Orta sınıf", price=0.8, wear=1.12, blow_temp=115.0, rear_only=False),
    "budget": dict(name="Ekonomik", price=0.62, wear=1.35, blow_temp=110.0, rear_only=False),
    "retread": dict(name="Kaplama (yalnız arka dingiller)", price=0.45, wear=1.25, blow_temp=105.0, rear_only=True),
}
PUNCTURE_MTBF_KM = 90_000.0                                  # tır başına ortalama yavaş patlak aralığı
NATURAL_LOSS_FRAC_PER_MIN = 0.15 / 9.0 / (30 * 1440)          # ayda ayar basıncının ~%1,7'si (tırda ~0,15 bar)
REF_K = 293.15                                               # basınçların ayarlandığı sıcaklık (20 °C)


def _surface_factor(name):
    n = (name or "").lower()
    if any(s in n for s in ("dirt", "gravel", "grass", "sand", "mud")):
        return 2.0
    if "snow" in n or "ice" in n:
        return 0.7
    if "rumble" in n:
        return 1.3
    return 1.0


def is_car_group(g):
    return g in CAR_GROUPS


def unit_cost(g, tier="premium"):
    """Bir lastiğin takılmış fiyatı (sınıfa göre)."""
    mount = prices.v("TIRE_MOUNT", "car") if is_car_group(g) else MOUNT_PRICE
    return PRICE[g] * TIERS[tier]["price"] + mount


def puncture_price(g):
    return prices.v("PUNCTURE_REPAIR", "car") if is_car_group(g) else PUNCTURE_REPAIR_PRICE


def layout_from_frame(f, car=False):
    """Telemetrideki tekerleklerden dingil grupları: {grup: dict(wheels, tires, lifted, steer_deg, surface)}.
    car: otomobil (ön / arka, tekil lastik)."""
    wheels = getattr(f, "wheels", None) or []
    out = {}
    for w in wheels:
        if car:
            g = "front" if w.get("steer") else "rear"
        else:
            g = "drive" if w.get("powered") else ("steer" if w.get("steer") and not w.get("liftable") else "tag")
        d = out.setdefault(g, dict(wheels=0, tires=0, lifted=True, steer_deg=0.0, surfaces={}))
        d["wheels"] += 1
        d["tires"] += 1 if (car or g == "steer") else 2   # tırın arka dingillerinde çift lastik varsayılır
        lifted = w.get("liftable") and (w.get("lift", 0.0) > 0.5 or not w.get("ground", True))
        d["lifted"] = d["lifted"] and bool(lifted)
        d["steer_deg"] = max(d["steer_deg"], abs(w.get("steering", 0.0)) * 360.0)
        s = w.get("substance", "")
        d["surfaces"][s] = d["surfaces"].get(s, 0) + 1
    if not out and car:  # telemetri tekerlek vermiyorsa: otomobil
        out = {"front": dict(wheels=2, tires=2, lifted=False, steer_deg=0.0, surfaces={}),
               "rear": dict(wheels=2, tires=2, lifted=False, steer_deg=0.0, surfaces={})}
    if not out:  # telemetri tekerlek vermiyorsa (demo / eski eklenti): 4x2 çekici
        out = {"steer": dict(wheels=2, tires=2, lifted=False, steer_deg=0.0, surfaces={}),
               "drive": dict(wheels=2, tires=4, lifted=False, steer_deg=0.0, surfaces={})}
    for d in out.values():
        surf = d.pop("surfaces", {})
        d["surface"] = max(surf.items(), key=lambda x: x[1])[0] if surf else ""   # dingilin çoğunun bastığı yüzey
    return out


def _new_group(g, tires, tier="premium"):
    return dict(tread=NEW_TREAD_MM[g], new=NEW_TREAD_MM[g], cold_bar=NOMINAL_BAR[g], nominal=NOMINAL_BAR[g],
                temp=20.0, km=0.0, tires=tires, leak_bph=0.0, blown=False, lifted=False, tier=tier)


def tier_of(s):
    return TIERS.get(s.get("tier", "premium"), TIERS["premium"])


def tier_allowed(g, tier):
    """Kaplama lastik yalnız tır / otobüs arka dingillerine takılır (otomobilde hiç)."""
    return tier in TIERS and not (TIERS[tier]["rear_only"] and (g == "steer" or is_car_group(g)))


@dataclass
class Tires:
    groups: dict = field(default_factory=dict)   # grup -> durum sözlüğü (bkz. _new_group)
    car: bool = False                            # otomobil lastikleri (ön / arka)
    puncture_km: float = -1.0                    # bir sonraki rastgele yavaş patlağa kalan km (< 0: henüz çekilmedi)

    # ------------------------------------------------------------------ kurulum
    def sync_layout(self, f):
        """Tekerlek düzenini telemetriyle eşler (yeni dingil yeni lastikle eklenir); grup düzenini döndürür."""
        lay = layout_from_frame(f, self.car)
        for g in [g for g in self.groups if is_car_group(g) != self.car]:   # araç sınıfı değişti (tır <-> otomobil)
            del self.groups[g]
        for g, d in lay.items():
            if g not in self.groups:
                self.groups[g] = _new_group(g, d["tires"])
            self.groups[g]["tires"] = d["tires"]
            self.groups[g]["lifted"] = d["lifted"]
        return lay

    def first_setup(self, f, odo, rnd, ambient):
        """İlk görülen kamyon: kilometresine göre makul diş ve basınç."""
        self.groups = {}
        self.sync_layout(f)
        for g, s in self.groups.items():
            if odo > 2000:
                usable = s["new"] - WARN_TREAD_MM[g]
                s["tread"] = round(s["new"] - usable * rnd.uniform(0.1, 0.65), 1)
                s["km"] = (s["new"] - s["tread"]) / WEAR_MM_PER_1000KM[g] * 1000
                s["cold_bar"] = round(s["nominal"] - rnd.uniform(0.0, 0.5), 2)
            s["temp"] = ambient

    # ------------------------------------------------------------------ adım
    def step(self, f, dt_game, km, c):
        """c: ambient, speed, mass_t, decel, load, brake_temp, rng, random_faults, rate (aşınma ve doğal basınç kaybı
        çarpanı), fault_rate (patlak sıklığı çarpanı). Dönüş: olay listesi [(seviye, M)]."""
        events = []
        wr = c.get("rate", 1.0)
        lay = self.sync_layout(f)
        amb, v = c["ambient"], c["speed"]
        dt_min, dt_h = dt_game / 60.0, dt_game / 3600.0
        load_t = 1.0 if self.car else clamp((c["mass_t"] / 40.0) ** 0.6, 0.45, 1.25)
        heat_k, fast_kmh = (0.30, 120.0) if self.car else (0.42, 80.0)
        braking = 1.0 + max(0.0, c["decel"] - 2.0) * 0.5
        for g, s in self.groups.items():
            info = lay.get(g, {})
            lifted = info.get("lifted", False)
            # basınç: doğal kayıp + patlak
            s["cold_bar"] = max(0.0, s["cold_bar"] - NATURAL_LOSS_FRAC_PER_MIN * s["nominal"] * dt_min * wr
                                - s["leak_bph"] * s["nominal"] / 9.0 * dt_h)
            if s["blown"]:
                s["cold_bar"] = 0.0
            ratio = s["cold_bar"] / s["nominal"] if s["nominal"] else 1.0
            under = max(0.0, 1.0 - ratio)
            # sıcaklık: hız, yük, düşük basınç ve fren ısısı
            if lifted or v < 1:
                t_eq = amb + (0.0 if lifted else 0.04 * max(0.0, c["brake_temp"] - amb))
            else:
                t_eq = amb + heat_k * v * load_t * (1 + 2.0 * under)
                if g != "tag":
                    t_eq += 0.10 * max(0.0, c["brake_temp"] - amb)
            tau = 8.0 if v > 1 else 20.0
            s["temp"] += (t_eq - s["temp"]) * (1 - math.exp(-dt_min / tau))
            if km <= 0 or lifted:
                continue
            # aşınma
            pressure_f = 1 + 2.5 * under + 1.5 * max(0.0, ratio - 1.0)
            speed_f = 1 + max(0.0, v - fast_kmh) / 60.0
            temp_f = 1 + max(0.0, s["temp"] - 90.0) / 30.0
            extra = 1.0
            if g == "steer":
                extra = 1 + 0.8 * clamp(info.get("steer_deg", 0.0) * v / 400.0, 0.0, 3.0)
            elif g == "drive":
                extra = 1 + (0.4 if v < 40 else 0.15) * c["load"]
            rate = WEAR_MM_PER_1000KM[g] / 1000.0 * load_t * pressure_f * speed_f * temp_f * braking * extra
            rate *= _surface_factor(info.get("surface", "")) * tier_of(s)["wear"] * wr
            s["tread"] = max(0.0, s["tread"] - rate * km)
            s["km"] += km
            # patlama: ısınmış ve çok inmiş ya da dişi bitmiş lastik yüksek hızda
            if not s["blown"] and v > 50 and ((s["temp"] > tier_of(s)["blow_temp"] and ratio < 0.65) or (s["tread"] < 0.5 and v > 70
                                                                                    and c["rng"].random() < 0.002 * km)):
                s["blown"], s["cold_bar"], s["leak_bph"] = True, 0.0, 0.0
                events.append(("crit", M("LASTİK PATLADI ({grp_t})! Hemen güvenli bir yerde durun.", grp_t=GROUP_NAMES[g])))
        # rastgele yavaş patlak (toprak/çakıl yolda 3 kat sık)
        if km > 0 and c.get("random_faults", True):
            rng = c["rng"]
            if self.puncture_km < 0:
                self.puncture_km = rng.expovariate(1.0 / PUNCTURE_MTBF_KM)
            rough = max((_surface_factor(d.get("surface", "")) for d in lay.values()), default=1.0)
            self.puncture_km -= km * (3.0 if rough >= 2 else 1.0) * c.get("fault_rate", 1.0)
            if self.puncture_km <= 0:
                self.puncture_km = rng.expovariate(1.0 / PUNCTURE_MTBF_KM)
                cand = [g for g, s in self.groups.items() if not s["blown"] and not lay.get(g, {}).get("lifted")]
                if cand:
                    weights = [self.groups[g]["tires"] for g in cand]
                    g = rng.choices(cand, weights=weights)[0]
                    self.groups[g]["leak_bph"] = round(rng.uniform(0.3, 1.2), 2)
                    events.append(("warn", M("Yavaş patlak: {grp_t} lastiği hava kaçırıyor.", grp_t=GROUP_NAMES[g])))
        return events

    def parked(self, dt_game, ambient, rate=1.0):
        """Uzun bekleme (uyku/feribot): soğuma, doğal basınç kaybı (rate: çarpan), patlaktan hava kaçağı."""
        dt_min = dt_game / 60.0
        for s in self.groups.values():
            s["cold_bar"] = max(0.0, s["cold_bar"] - NATURAL_LOSS_FRAC_PER_MIN * s["nominal"] * dt_min * rate
                                - s["leak_bph"] * s["nominal"] / 9.0 * dt_min / 60.0)
            s["temp"] = ambient

    # ------------------------------------------------------------------ servis
    def inflate(self):
        """Tüm lastikleri soğuk ayar basıncına getirir (patlak ve patlamış lastik hariç). Dönüş: ayarlanan grup sayısı."""
        n = 0
        for s in self.groups.values():
            if not s["blown"]:
                s["cold_bar"] = s["nominal"]
                n += 1
        return n

    def repair_puncture(self):
        """Yavaş patlakları tamir eder; maliyet döndürür."""
        cost = 0.0
        for g, s in self.groups.items():
            if s["leak_bph"] > 0 and not s["blown"]:
                s["leak_bph"] = 0.0
                s["cold_bar"] = s["nominal"]
                cost += puncture_price(g)
        return cost

    def replace(self, which="all", tier="premium"):
        """Bir dingil grubunun ya da tümünün lastiklerini yeniler; maliyet döndürür. Kaplama ön dingile takılmaz
        (tümü değişirken ön dingile premium takılır)."""
        cost = 0.0
        for g, s in self.groups.items():
            if which in ("all", g):
                t = tier if tier_allowed(g, tier) else "premium"
                cost += unit_cost(g, t) * s["tires"]
                self.groups[g] = dict(_new_group(g, s["tires"], t), temp=s["temp"], lifted=s["lifted"])
        return cost

    def replace_cost(self, which="all", tier="premium"):
        return sum(unit_cost(g, tier if tier_allowed(g, tier) else "premium") * s["tires"]
                   for g, s in self.groups.items() if which in ("all", g))

    # ------------------------------------------------------------------ özet
    @staticmethod
    def hot_bar(s):
        return s["cold_bar"] * (273.15 + s["temp"]) / REF_K

    def summary(self):
        """Gösterim ve uyarılar için: en düşük diş (oran ve mm), en düşük basınç oranı, en yüksek sıcaklık."""
        active = {g: s for g, s in self.groups.items() if not s.get("lifted")} or self.groups
        if not active:
            return dict(min_tread=None, min_tread_g=None, min_ratio=None, max_temp=None, leak=False, blown=False)
        tg = min(active, key=lambda g: active[g]["tread"] - WARN_TREAD_MM[g])
        return dict(min_tread=active[tg]["tread"], min_tread_g=tg,
                    min_ratio=min(s["cold_bar"] / s["nominal"] for s in active.values()),
                    max_temp=max(s["temp"] for s in active.values()),
                    leak=any(s["leak_bph"] > 0 for s in self.groups.values()),
                    blown=any(s["blown"] for s in self.groups.values()))
