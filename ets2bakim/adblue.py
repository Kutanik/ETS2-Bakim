"""AdBlue (DEF, %32,5 üre): SCR katalizörlü dizellerde egzoz NOx'unu azaltmak için püskürtülür.

Telemetri AdBlue miktarını ve depo hacmini verir, ama ETS2 AdBlue'yu harcamaz (değer sabit kalır). Bu yüzden
tüketim burada hesaplanır: katalizör ısınınca (egzoz > 200 °C) yakıtın ~%3–7'si kadar, yük arttıkça daha çok
(NOx yükle artar). Oyun bir gün AdBlue'yu kendisi harcarsa (telemetri değeri sürüşte azalırsa) oyunun değeri izlenir.
Depo boşalınca gerçek araçta motor gücü düşürülür ve yeniden çalıştırmada hız 20 km/h ile sınırlanır; oyunda bu
uygulanamadığı için uyarı ve gösterge lambası verilir. AdBlue -11 °C'de donar (depo ısıtıcısı motor çalışınca çözer).
"""
from dataclasses import dataclass

from . import prices
from .util import clamp

PRICE_L = prices.ADBLUE_L
DEFAULT_CAP_L = 60.0
FREEZE_C = -11.0
WARN_FRAC, CRIT_FRAC = 0.10, 0.05


def has_scr(spec, f):
    """AdBlue'lu (SCR) dizel mi: oyun depo hacmi veriyorsa ya da kamyon DPF'li (Euro 6) ise."""
    return not spec.electric and (getattr(f, "adblue_cap", 0.0) > 0 or spec.has_dpf)


@dataclass
class AdBlue:
    level_l: float = 50.0
    capacity_l: float = DEFAULT_CAP_L
    source: str = "sim"          # sim: simülatör harcar · game: oyun kendisi harcıyor (telemetri izlenir)
    used_total_l: float = 0.0
    last_game_l: float = -1.0
    game_drop_l: float = 0.0

    @property
    def frac(self):
        return clamp(self.level_l / self.capacity_l, 0.0, 1.0) if self.capacity_l > 0 else 0.0

    def dosing_rate(self, load):
        """Yakıt litresi başına AdBlue litresi."""
        return clamp(0.055 * (0.5 + 0.9 * load), 0.02, 0.08)

    def step(self, f, fuel_l, load, exh_temp, running, rate=1.0):
        """rate: tüketim çarpanı (yalnız simülatör harcarken; oyun harcıyorsa oyunun değeri izlenir)."""
        if getattr(f, "adblue_cap", 0.0) > 0:
            if abs(f.adblue_cap - self.capacity_l) > 0.5:
                self.level_l = self.frac * f.adblue_cap
            self.capacity_l = f.adblue_cap
        game = getattr(f, "adblue_l", 0.0)
        if self.last_game_l >= 0 and running and game < self.last_game_l - 1e-4:
            self.game_drop_l += self.last_game_l - game
            if self.game_drop_l > 0.3:
                self.source = "game"
        self.last_game_l = game
        if self.source == "game":
            self.level_l = clamp(game, 0.0, self.capacity_l)
            return
        if running and exh_temp > 200 and fuel_l > 0:
            dose = min(self.level_l, fuel_l * self.dosing_rate(load) * rate)
            self.level_l -= dose
            self.used_total_l += dose

    def fill(self, liters=None):
        """Doldurur (liters None: depoyu tamamlar). Dönüş: (eklenen L, maliyet)."""
        room = max(0.0, self.capacity_l - self.level_l)
        add = room if liters is None else clamp(float(liters), 0.0, room)
        self.level_l += add
        return add, add * PRICE_L
