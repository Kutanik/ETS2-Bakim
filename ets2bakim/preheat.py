"""Ön ısıtma (kızdırma bujisi / emme havası ızgara ısıtıcısı).

Dizel motorda buji yoktur; soğukta ilk ateşlemeyi kolaylaştırmak için kontak açılınca ön ısıtma yapılır. Kamyonlarda
çoğunlukla emme manifoldunda ızgara ısıtıcı, bazı motorlarda silindir başına kızdırma bujisi kullanılır. Gösterge
panelindeki sarı spiral lamba ısıtma sürerken yanar; sönünce marşa basılır. Süre motor (blok) sıcaklığına bağlıdır:
5 °C üstünde gerekmez, 0 °C'de ~12 sn, -20 °C'de ~30 sn. Isıtıcı aküden ~150 A çeker.

Süre gerçek zamanla sayılır (sürücünün bekleyişi gerçek saniyedir; oyun saati 19 kat hızlı akar). Lamba sönmeden marşa
basılırsa ateşleme zorlaşır (beyaz duman, ek aşınma); -15 °C altında yarıdan az ısıtılmış motor hiç ateşlemez.
Arızalı ön ısıtma soğukta ısıtmaz: lamba yanıp söner, motor zor çalışır ya da çalışmaz.
"""
from .util import clamp

NEED_BELOW_C = 5.0
CURRENT_A = 150.0
NO_FIRE_BELOW_C = -15.0     # bu sıcaklığın altında yeterince ısıtılmamış motor ateşlemez
FAULT_NO_FIRE_BELOW_C = -5.0


def duration_s(t_engine):
    """Gereken ön ısıtma süresi (gerçek saniye); 0 = gerekmiyor."""
    if t_engine >= NEED_BELOW_C:
        return 0.0
    return clamp(12.0 + (0.0 - t_engine) * 0.9, 8.0, 35.0)


class Preheat:
    """Anlık durum (kaydedilmez): kontak açık ve motor kapalıyken gerekiyorsa ısıtır."""

    def __init__(self):
        self.total_s = 0.0
        self.remaining_s = 0.0
        self.active = False
        self.ready = False

    def step(self, f, dt_real, t_engine):
        need = duration_s(t_engine)
        if not f.electric_on or f.engine_on:
            # kontak kapandı ya da motor çalıştı: bir sonraki marş için yeniden ısıtılır
            self.active = self.ready = False
            self.remaining_s = self.total_s = 0.0
            return
        if need <= 0:
            self.active, self.ready = False, True
            return
        if not self.active and not self.ready:
            self.active, self.total_s, self.remaining_s = True, need, need
        if self.active:
            # arızalı ısıtıcı da lambayı süre boyunca yakar (sürücü fark etmez), ama ısıtmaz
            self.remaining_s = max(0.0, self.remaining_s - dt_real)
            if self.remaining_s <= 0:
                self.active, self.ready = False, True

    def quality(self, t_engine, faulty):
        """Marş anında ne kadar ısıtılmıştı: 1 = tam (ya da gerekmiyor), 0 = hiç."""
        if duration_s(t_engine) <= 0:
            return 1.0
        if faulty:
            return 0.0
        if self.ready:
            return 1.0
        if self.active and self.total_s > 0:
            return clamp(1.0 - self.remaining_s / self.total_s, 0.0, 1.0)
        return 0.0   # kontak açılır açılmaz marş (oyunda doğrudan E)

    def current_a(self, faulty):
        return CURRENT_A if self.active and not faulty else 0.0
