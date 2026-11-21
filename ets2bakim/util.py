import dataclasses
import math


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def interp(x, xs, ys):
    """Parça parça doğrusal enterpolasyon (xs artan sırada)."""
    if x <= xs[0]:
        return ys[0]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]


def ema(prev, new, dt, tau):
    if prev is None or tau <= 0:
        return new
    a = 1.0 - math.exp(-dt / tau)
    return prev + a * (new - prev)


def load_dataclass(cls, data):
    """Kayıttan dataclass oluşturur; bilinmeyen alanları yok sayar, eksikleri varsayılanla doldurur."""
    obj = cls()
    if not isinstance(data, dict):
        return obj
    for f in dataclasses.fields(cls):
        if f.name in data:
            setattr(obj, f.name, data[f.name])
    return obj


def to_dict(obj):
    return dataclasses.asdict(obj)


def fmt_minutes(game_minutes):
    """Oyun dakikasını 'Gün SS:DD' biçimine çevirir (gün adı seçili dilde)."""
    from .i18n import day
    gm = int(game_minutes)
    h = (gm % 1440) // 60
    m = gm % 60
    return f"{day(gm // 1440)} {h:02d}:{m:02d}"
