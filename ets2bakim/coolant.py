"""Soğutma sıvısı (antifriz): glikol oranı, donma/kaynama noktası, inhibitör tükenmesi,
pH, kireç/korozyon birikimi, seviye ve kaçaklar.
"""
import math
import random
from dataclasses import dataclass

from . import prices
from .util import clamp, interp

# Etilen glikol / su karışımı (hacimce) donma noktası, °C
_FREEZE = ([0, .1, .2, .3, .4, .5, .55, .6, .65, .7, .8, .9, 1.0],
           [0, -3.5, -8, -15, -24, -37, -45, -52, -50, -45, -35, -25, -13])
# Atmosfer basıncında kaynama noktası, °C
_BOIL = ([0, .3, .4, .5, .6, .7, 1.0], [100, 104, 105.5, 107, 110, 114, 160])

# hard_scale: sert (musluk) suyla kireç bağlama eğilimi; fosfatlı tipler sert suda çok kireç bırakır
TYPES = {
    "oat": dict(name="OAT uzun ömürlü (organik asit)", life_days=4 * 365, life_km=800000, hard_scale=1.0,
                price_l=prices.COOLANT_TYPE_L["oat"]),
    "iat": dict(name="IAT konvansiyonel (silikatlı)", life_days=2 * 365, life_km=250000, hard_scale=1.3,
                price_l=prices.COOLANT_TYPE_L["iat"]),
    "hoat": dict(name="HOAT hibrit (silikat + organik asit, G11/G05)", life_days=3 * 365, life_km=500000, hard_scale=1.1,
                 price_l=prices.COOLANT_TYPE_L["hoat"]),
    "si_oat": dict(name="Si-OAT uzun ömürlü (G12++/G13)", life_days=5 * 365, life_km=1000000, hard_scale=1.0,
                   price_l=prices.COOLANT_TYPE_L["si_oat"]),
    "p_oat": dict(name="P-OAT fosfatlı organik asit", life_days=4 * 365, life_km=700000, hard_scale=1.8,
                  price_l=prices.COOLANT_TYPE_L["p_oat"]),
    # 1.3.0: ağır hizmet ve üretici onaylı antifrizler
    "noat": dict(name="NOAT nitritli organik asit (ıslak gömlekli ağır dizel)", life_days=3 * 365, life_km=600000,
                 hard_scale=1.1, price_l=prices.COOLANT_TYPE_L["noat"]),
    "hoat_vcs": dict(name="HOAT nitritsiz (Volvo VCS / Renault Type D)", life_days=4 * 365, life_km=700000,
                     hard_scale=1.1, price_l=prices.COOLANT_TYPE_L["hoat_vcs"]),
    "si_oat_evo": dict(name="Si-OAT G12evo (yeni nesil, ömür boyu dolum)", life_days=6 * 365, life_km=1200000,
                       hard_scale=1.0, price_l=prices.COOLANT_TYPE_L["si_oat_evo"]),
}
FLUIDS = {
    "premix": dict(glycol=0.5, inhibitor=1.0, hardness=0.0, name="50/50 hazır karışım", price_l=prices.COOLANT_FLUID_L["premix"]),
    "concentrate": dict(glycol=1.0, inhibitor=2.0, hardness=0.0, name="Konsantre antifriz", price_l=prices.COOLANT_FLUID_L["concentrate"]),
    "distilled": dict(glycol=0.0, inhibitor=0.0, hardness=0.0, name="Saf (demineralize) su", price_l=prices.COOLANT_FLUID_L["distilled"]),
    "tap": dict(glycol=0.0, inhibitor=0.0, hardness=1.0, name="Musluk suyu", price_l=prices.COOLANT_FLUID_L["tap"]),
}


@dataclass
class Coolant:
    type: str = "oat"
    capacity_l: float = 70.0
    volume_l: float = 70.0
    glycol: float = 0.5        # hacimce oran
    inhibitor: float = 1.0     # 1 = taze 50/50 karışımdaki seviye
    hardness: float = 0.0      # musluk suyundan gelen mineral (0..1)
    scale: float = 0.0         # kireç/korozyon birikimi (0..1), ısı transferini düşürür
    minutes_age: float = 0.0
    km: float = 0.0
    wear_min: float = 0.0      # değişim aralığına sayılan yaş ve km (azalma hızı çarpanıyla; 1× = gerçek)
    wear_km: float = 0.0
    lost_l: float = 0.0

    @property
    def spec(self):
        return TYPES.get(self.type, TYPES["oat"])

    @property
    def level_frac(self):
        return self.volume_l / self.capacity_l if self.capacity_l > 0 else 0.0

    @property
    def freeze_point(self):
        return interp(self.glycol, *_FREEZE)

    def boil_point(self, p_gauge_bar):
        base = interp(self.glycol, *_BOIL)
        return base + 20.2 * math.log2((1.013 + max(0.0, p_gauge_bar)) / 1.013)

    @property
    def ph(self):
        return 7.0 + 1.4 * clamp(self.inhibitor, 0.0, 1.2) - 0.5 * self.hardness * (1 - clamp(self.inhibitor, 0, 1))

    @property
    def heat_transfer_factor(self):
        return (1 - 0.6 * self.scale) * (1 - 0.5 * max(0.0, self.glycol - 0.6))

    def step(self, dt_s, c):
        """c: running, km, t_cool, aeration, combustion_gas, leak_lph, rate (azalma hızı çarpanı)"""
        dt_h = dt_s / 3600.0
        s = self.spec
        r = c.get("rate", 1.0)
        self.minutes_age += dt_s / 60.0
        self.km += c["km"]
        self.wear_min += dt_s / 60.0 * r
        self.wear_km += c["km"] * r
        rate = (dt_h / (s["life_days"] * 24.0) + c["km"] / s["life_km"]) * r
        f = 1.0
        if c["t_cool"] > 90:
            f *= 2 ** ((c["t_cool"] - 90) / 10.0)
        if c["aeration"]:
            f *= 2.0
        if c["combustion_gas"]:
            f *= 4.0
        self.inhibitor = max(0.0, self.inhibitor - rate * f)
        if self.inhibitor < 0.3:
            self.scale += (0.3 - self.inhibitor) / 0.3 * (c["km"] / 400000.0 + dt_h / 20000.0) * r
        if self.hardness > 0 and c["running"] and c["t_cool"] > 80:
            self.scale += self.hardness * dt_h / 8000.0 * s.get("hard_scale", 1.0) * r
        self.scale = min(1.0, self.scale)
        loss = 0.02 * c["km"] / 1000.0 * r + c["leak_lph"] * dt_h
        self.lose(loss)

    def lose(self, liters):
        liters = clamp(liters, 0.0, self.volume_l)
        self.volume_l -= liters
        self.lost_l += liters

    def top_up(self, fluid, liters):
        fl = FLUIDS[fluid]
        liters = clamp(liters, 0.0, max(0.0, self.capacity_l * 1.02 - self.volume_l))
        if liters <= 0:
            return 0.0, 0.0
        tot = self.volume_l + liters
        x = liters / tot
        self.glycol = (1 - x) * self.glycol + x * fl["glycol"]
        self.inhibitor = (1 - x) * self.inhibitor + x * fl["inhibitor"]
        self.hardness = (1 - x) * self.hardness + x * fl["hardness"]
        self.volume_l = tot
        return liters, liters * fl["price_l"]

    def change(self, ctype, concentration, labour=None):
        t = TYPES[ctype]
        conc = clamp(concentration, 0.3, 0.7)
        self.type = ctype
        self.glycol = conc
        self.inhibitor = 2.0 * conc
        self.hardness = 0.0
        self.scale *= 0.6   # yıkama birikimin bir kısmını alır
        self.volume_l = self.capacity_l
        self.minutes_age = self.km = self.wear_min = self.wear_km = 0.0
        return self.capacity_l * t["price_l"] * conc / 0.5 + (prices.COOLANT_CHANGE_LABOUR if labour is None else labour)

    def test(self):
        rnd = random.Random()
        g = clamp(self.glycol + rnd.gauss(0, 0.01), 0, 1)
        return {
            "glycol_pct": g * 100.0,
            "freeze_point": interp(g, *_FREEZE),
            "ph": self.ph + rnd.gauss(0, 0.05),
            "inhibitor_pct": clamp(self.inhibitor, 0, 2) * 100.0,
            "scale_pct": self.scale * 100.0,
            "level_pct": self.level_frac * 100.0,
        }
