"""Lastik patlamasının oyundaki fiziksel etkisi: ani sürüklenme, kayma ve jant sürtmesi (yalnızca tek oyunculu).

Oyunun SDK'sı lastiği patlatamaz; ama oyun içi eklentinin semantik giriş cihazı oyunun fren (abackward) ve direksiyon
(steering) girdisine değer EKLEYEBİLİR, oyuncunun kendi girişi korunur. Patlamada:
  1) ilk ~1,5 sn: jant yola gömülürken sert sürüklenme (fren 0,55) ve çekme; ön dingilde patlayan tarafa, arka
     dingillerde kuyruğun sallanması (kayma) şeklinde
  2) sonra tır durana kadar jant sürtmesi (fren ~0,18) ve titreşim
Değerler bilerek ölçülü: tır savrulmaz, kontrol oyuncuda kalır. Çok oyunculuda (TruckersMP, Konvoy) başka oyunculara
kaza yaptırmamak için hiç uygulanmaz. Simülatör kapanır ya da takılırsa eklenti etkiyi 0,5 sn içinde kaldırır.
"""
import math
import random

from .util import clamp

JOLT_S = 1.5
JOLT_BRAKE, SCRAPE_BRAKE = 0.55, 0.18
STEER_PULL = 0.015           # ön dingil patlaması: direksiyon ekseninde (-1..1) sürekli çekme
REAR_SWAY = 0.008            # arka dingil patlaması: kuyruk sallanması genliği
SWAY_HZ, SWAY_DECAY_S = 1.6, 3.0
JITTER, JITTER_HZ = 0.002, 9.0
STOP_KMH = 3.0
STEERED = ("steer", "front")  # yönlendirilen dingil: tırın ön dingili, otomobilin ön lastikleri


class BlowoutEffect:
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.known = set()       # zaten tepki verilmiş patlak dingiller
        self.axle = None
        self.side = 1.0
        self.t0 = 0.0

    def update(self, tires, f, allowed, now):
        """Dönüş: (fren 0..1, direksiyon -1..1); etki yoksa (0, 0)."""
        blown = {g for g, s in tires.groups.items() if s.get("blown") and not s.get("lifted")}
        new = blown - self.known
        self.known = blown
        if new:  # en kötüsü ön dingil patlaması
            front = [g for g in STEERED if g in new]
            self.axle = front[0] if front else sorted(new)[0]
            self.side = self.rng.choice((-1.0, 1.0))
            self.t0 = now
        v = abs(f.speed_kmh)
        if not allowed or not blown or v < STOP_KMH:
            return 0.0, 0.0
        dt = now - self.t0
        speed_f = clamp(v / 80.0, 0.3, 1.2)
        brake = JOLT_BRAKE if dt < JOLT_S else SCRAPE_BRAKE
        if self.axle in STEERED:
            steer = STEER_PULL * self.side * speed_f * (1.0 if dt < JOLT_S else 0.6)
        else:
            steer = (0.3 * STEER_PULL * self.side * speed_f
                     + REAR_SWAY * speed_f * math.sin(2 * math.pi * SWAY_HZ * dt) * math.exp(-dt / SWAY_DECAY_S))
        steer += JITTER * math.sin(2 * math.pi * JITTER_HZ * dt)   # jant sürtmesinin titreşimi
        return brake, clamp(steer, -0.05, 0.05)
