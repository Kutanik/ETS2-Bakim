"""Dış ortam sıcaklığı modeli.

ETS2'de mevsim yok; mevsim gerçek takvimden (veya ayardan), günün saati oyun saatinden,
enlem/boylam kamyonun konumundan alınır. Üzerine yavaş değişen bir hava durumu sapması eklenir.
"""
import datetime
import math
import random
from dataclasses import dataclass

from .util import clamp

AY_ORTA_GUN = [15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349]


@dataclass
class ClimateState:
    weather_offset: float = 0.0


class Climate:
    TAU_S = 2 * 86400.0  # hava sapmasının korelasyon süresi (oyun saniyesi)
    SIGMA = 3.0

    def __init__(self, state=None):
        self.state = state or ClimateState()
        self.rng = random.Random()
        self.last = None

    def day_of_year(self, settings):
        if settings.get("climate_mode") == "month":
            return AY_ORTA_GUN[int(clamp(settings.get("climate_month", 1), 1, 12)) - 1]
        return datetime.date.today().timetuple().tm_yday

    def baseline(self, lat, lon, alt_m, doy, hour):
        annual = 32.0 - 0.42 * lat
        amp = clamp(6.5 + 0.17 * (lon + 5.0) + 0.05 * (lat - 50.0), 5.0, 14.0)
        season = -math.cos(2 * math.pi * (doy - 20) / 365.25)
        summer = (season + 1) / 2
        d_amp = 2.5 + 2.5 * summer
        if 5 <= hour < 15:
            diurnal = -math.cos(math.pi * (hour - 5) / 10)
        else:
            diurnal = math.cos(math.pi * ((hour - 15) % 24) / 14)
        return annual + amp * season + d_amp * diurnal - 0.0065 * max(0.0, alt_m)

    def update(self, dt_game_s, lat, lon, alt_m, game_minutes, wipers, settings):
        if settings.get("climate_mode") == "fixed":
            self.last = float(settings.get("climate_fixed_c", 15.0))
            return self.last
        if settings.get("weather_variability", True) and dt_game_s > 0:
            k = math.exp(-dt_game_s / self.TAU_S)
            self.state.weather_offset = (self.state.weather_offset * k
                                         + self.SIGMA * math.sqrt(1 - k * k) * self.rng.gauss(0, 1))
        hour = (game_minutes % 1440) / 60.0
        t = self.baseline(lat, lon, alt_m, self.day_of_year(settings), hour)
        if settings.get("weather_variability", True):
            t += self.state.weather_offset
        if wipers:
            t -= 1.5
        self.last = t
        return t
