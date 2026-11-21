"""Değerlerin azalma (aşınma, yaşlanma, tüketim) hızı çarpanları.

Ayarlar'da bir genel çarpan ve sistem başına çarpanlar vardır; etkin hız = genel × sistem.
1 = gerçekçi, 0,5 = yarı hızda (ör. yağ iki kat uzun dayanır), 2 = iki kat hızlı, 0 = o değer hiç azalmaz.
Yalnızca kendiliğinden azalan değerler ölçeklenir: kullanım hatasının verdiği hasar (hararet, yağsız kalma,
donma, ön ısıtmasız marş), arıza sonucu kaçaklar ve akünün şarj olması değişmez.
"""
from .util import clamp

KEYS = ("oil", "coolant", "battery", "drain", "tires", "dpf", "adblue", "engine", "transmission", "faults")
MAX = 5.0


def _num(settings, name):
    try:
        return clamp(float(settings.get(name, 1.0)), 0.0, MAX)
    except (TypeError, ValueError):
        return 1.0


def get(settings, key):
    """Bir sistemin etkin azalma hızı (genel × sistem)."""
    return _num(settings, "rate_global") * _num(settings, "rate_" + key)


def all_rates(settings):
    return {k: get(settings, k) for k in KEYS}


def stretch(value, rate):
    """Bir aralığın (km, gün) bu hızdaki karşılığı; hız 0 ise sınırsız (None)."""
    return None if rate <= 0 else value / rate


def interval_end(real, wear, limit, rate):
    """Gösterilecek aralık sonu (gerçek km/gün): şimdiye kadar gidilen + kalan aralık ÷ şimdiki hız.
    wear: aralığa sayılan (çarpanlı) kısım. Hız yolda değiştirilse de kalan miktar doğru görünür; 1× ve hiç
    değiştirilmemişse aralığın kendisidir. Hız 0 ise sınırsız (None)."""
    return None if rate <= 0 else real + (limit - wear) / rate
