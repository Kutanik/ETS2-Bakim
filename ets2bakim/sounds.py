"""Uyarı sesleri: tırın markasına göre kısa ikaz sesi, her uyarıda yalnızca bir kez.

Üreticilerin gösterge paneli ikaz seslerinin özgün kayıtları yayımlanmaz (telif hakkı üreticide), oyunun kendi sesleri
de paketli FMOD ses bankalarındadır. Bu yüzden her markanın tanınan ikaz sesi karakterine benzeyen kısa sesler burada
sentezlenir (Scania: sıcak "bong" · Volvo: yumuşak iki notalı zil · Mercedes-Benz: tiz "pling" · MAN: kısa elektronik
bip · DAF: iki tonlu yumuşak ses · Renault: üç notalı zil · Iveco: tek bip · Škoda/VW otomobil: gong · otobüs: "ding-dong").
Her markanın iki sesi vardır: dikkat (tek, yumuşak) ve kritik (daha acil desen); ikisi de bir kez çalar, tekrarlamaz.
Ayarlar'da tırın markası yerine istenen marka sesi de seçilebilir.

Kendi ses dosyanızı kullanmak için sesler\\ozel klasörüne <marka>_<seviye>.wav koyun (ör. scania_kritik.wav,
volvo_dikkat.wav); varsa o çalınır. Markalar: scania, volvo, mercedes, man, daf, renault, iveco, skoda, otobus, genel.

Ses yalnızca uygulamadan çalınır (oyun içi katman ve uygulama penceresi ayrıca ses çıkarmaz). Bir uyarı ilk çıktığında
bir kez çalar; içindeki değer değişse de (ör. "akü 25,1 V") yeniden çalmaz; kaybolup 60 sn içinde geri gelirse de çalmaz.

Çalma: sesler ayrı bir iş parçacığında sırayla ve sonuna kadar çalınır; çalan ses yeni bir uyarıyla kesilmez (eski
sürümde arka arkaya çıkan uyarılar sesi baştan başlatıp kesik kesik öttürüyordu). O sırada gelen aynı ya da daha düşük
seviyeli uyarı zaten öten sese katılır, kritik uyarı dikkat sesinin bitmesini bekler. Ses dosyalarının başında kısa bir
sessizlik vardır: bazı dizüstü ses kartları boştayken uyanırken sesin ilk ~100 ms'sini yutar.
"""
import io
import math
import os
import sys
import threading
import time
import wave
from array import array

RATE = 44100
VERSION = 2          # sentez değişince önbellek klasörü (sesler\v2) yenilenir
LEAD_S = 0.12        # baştaki sessizlik (ses kartının uyanma süresi)
TAIL_S = 0.10
PEAK = 0.85          # tepe genliği (tam ölçeğe göre)
ROLLOFF_HZ = 6000.0  # yüksek harmonikler yumuşatılır (tiz bipler kulak tırmalamasın)
GAP_S = 0.25         # iki ses arasında en az bu kadar boşluk
LEVEL_NAMES = {"crit": "kritik", "warn": "dikkat"}
LEVEL_RANK = {"warn": 1, "crit": 2}
BRANDS = ("scania", "volvo", "mercedes", "man", "daf", "renault", "iveco", "skoda", "otobus", "genel")
BRAND_NAMES = {"scania": "Scania", "volvo": "Volvo", "mercedes": "Mercedes-Benz", "man": "MAN", "daf": "DAF",
               "renault": "Renault", "iveco": "Iveco", "skoda": "Otomobil (gong)", "otobus": "Otobüs", "genel": "Genel"}
BELL = ((1.0, 1.0), (2.0, 0.35), (3.0, 0.12), (4.2, 0.05))          # çan benzeri (bong / gong)
SOFT = ((1.0, 1.0), (2.0, 0.12))                                       # yumuşak zil
SQUARE = ((1.0, 1.0), (3.0, 0.3), (5.0, 0.12), (7.0, 0.05))            # elektronik bip
VW_GONG = ((1.0, 1.0), (2.76, 0.25), (5.4, 0.06))


def _n(t, f, dur, decay, partials=SOFT, amp=1.0):
    return dict(t=t, f=f, dur=dur, decay=decay, partials=partials, amp=amp)


# marka -> seviye -> notalar (başlangıç sn, frekans Hz, süre, sönüm sabiti, harmonikler)
STYLES = {
    "scania": {"warn": [_n(0.0, 622, 1.0, 0.42, BELL)],
               "crit": [_n(0.0, 784, 0.6, 0.30, BELL), _n(0.30, 622, 1.0, 0.42, BELL)]},
    "volvo": {"warn": [_n(0.0, 1319, 0.35, 0.16), _n(0.17, 1047, 0.5, 0.22)],
              "crit": [_n(0.0, 1568, 0.3, 0.12), _n(0.13, 1319, 0.3, 0.12), _n(0.26, 1047, 0.5, 0.22)]},
    "mercedes": {"warn": [_n(0.0, 1760, 0.35, 0.12, SOFT)],
                 "crit": [_n(0.0, 1760, 0.2, 0.08), _n(0.16, 1760, 0.2, 0.08), _n(0.32, 1760, 0.35, 0.12)]},
    "man": {"warn": [_n(0.0, 2000, 0.09, 1.0, SQUARE, 0.6), _n(0.14, 2000, 0.09, 1.0, SQUARE, 0.6)],
            "crit": [_n(i * 0.11, 2200, 0.07, 1.0, SQUARE, 0.6) for i in range(4)]},
    "daf": {"warn": [_n(0.0, 880, 0.3, 0.18), _n(0.2, 659, 0.45, 0.22)],
            "crit": [_n(i * 0.15, 988, 0.1, 1.0, SQUARE, 0.55) for i in range(3)]},
    "renault": {"warn": [_n(0.0, 1047, 0.2, 0.1), _n(0.1, 1319, 0.2, 0.1), _n(0.2, 1568, 0.4, 0.18)],
                "crit": [_n(0.0, 1568, 0.2, 0.1), _n(0.1, 1319, 0.2, 0.1), _n(0.2, 1047, 0.2, 0.1), _n(0.3, 784, 0.45, 0.2)]},
    "iveco": {"warn": [_n(0.0, 1700, 0.18, 1.0, SQUARE, 0.55)],
              "crit": [_n(0.0, 1700, 0.15, 1.0, SQUARE, 0.55), _n(0.22, 1700, 0.15, 1.0, SQUARE, 0.55)]},
    "skoda": {"warn": [_n(0.0, 1046, 0.8, 0.35, VW_GONG)],
              "crit": [_n(i * 0.22, 1046, 0.45, 0.18, VW_GONG) for i in range(3)]},
    "otobus": {"warn": [_n(0.0, 784, 0.45, 0.25, BELL), _n(0.32, 622, 0.7, 0.35, BELL)],
               "crit": [_n(i * 0.18, 1200, 0.12, 1.0, SQUARE, 0.55) for i in range(3)]},
    "genel": {"warn": [_n(0.0, 1000, 0.15, 1.0, SOFT, 0.7)],
              "crit": [_n(i * 0.2, 1000, 0.12, 1.0, SOFT, 0.7) for i in range(3)]},
}


def brand_key(brand_id, vehicle="truck"):
    """Telemetrideki marka kimliğinden ses ailesi."""
    if vehicle == "bus":
        return "otobus"
    b = (brand_id or "").lower()
    for k in ("scania", "volvo", "mercedes", "man", "daf", "renault", "iveco", "skoda"):
        if k in b:
            return k
    return "skoda" if vehicle == "car" else "genel"


def synth(brand, level):
    """16 bit mono WAV baytları (44,1 kHz). Notalar yumuşak başlar ve biter (tık sesi yok); Nyquist sınırının üstüne
    çıkan harmonikler atılır (eski 22 kHz sentezde MAN/Iveco biplerinde cızırtı yapan katlanma), tizler yumuşatılır."""
    notes = STYLES.get(brand, STYLES["genel"]).get(level) or STYLES["genel"][level]
    body = max(n["t"] + n["dur"] for n in notes)
    total = int((LEAD_S + body + TAIL_S) * RATE)
    buf = [0.0] * total
    w = 2 * math.pi / RATE
    for n in notes:
        start, count = int((LEAD_S + n["t"]) * RATE), int(n["dur"] * RATE)
        att = max(1, int(0.004 * RATE))
        rel = max(1, int(min(0.04, n["dur"] * 0.3) * RATE))
        parts = [(n["f"] * k * w, a / (1.0 + (n["f"] * k / ROLLOFF_HZ) ** 2))
                 for k, a in n["partials"] if n["f"] * k < 0.45 * RATE]
        decay = n["decay"] * RATE
        for i in range(min(count, total - start)):
            env = math.exp(-i / decay)
            if i < att:
                env *= 0.5 - 0.5 * math.cos(math.pi * i / att)
            left = count - i
            if left < rel:
                env *= 0.5 - 0.5 * math.cos(math.pi * left / rel)
            buf[start + i] += n["amp"] * env * sum(a * math.sin(om * i) for om, a in parts)
    gain = PEAK / max(1e-9, max(abs(x) for x in buf))
    pcm = array("h", (int(round(max(-1.0, min(1.0, x * gain)) * 32767)) for x in buf))
    if sys.byteorder == "big":
        pcm.byteswap()
    bio = io.BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(pcm.tobytes())
    return bio.getvalue()


def _winsound_play(path):
    """Dosyayı sonuna kadar çalar (çağıran iş parçacığını ses bitene kadar bekletir)."""
    import winsound
    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_NODEFAULT)


class WarningSound:
    """Marka seslerini (ilk kullanımda) üretip klasörde saklar ve arka planda sırayla çalar.

    player: dosya yolunu alıp ses bitene kadar bekleyen işlev (testlerde sahtesi verilir; Windows'ta winsound)."""

    def __init__(self, folder, enabled=True, player=None):
        self.folder = folder
        self.enabled = enabled
        self._player = player or (_winsound_play if os.name == "nt" else None)
        self._lock = threading.Lock()        # dosya üretimi
        self._cv = threading.Condition()
        self._pending = None                 # (marka, seviye): sıradaki tek ses (en acil olanı)
        self._playing = None                 # şu an çalan (ya da arkasındaki boşlukta olan) sesin seviyesi
        self._thread = None
        self.played = 0

    def path(self, brand, level):
        name = f"{brand}_{LEVEL_NAMES[level]}.wav"
        custom = os.path.join(self.folder, "ozel", name)
        if os.path.exists(custom):
            return custom
        p = os.path.join(self.folder, f"v{VERSION}", name)
        if not os.path.exists(p):
            with self._lock:
                if not os.path.exists(p):
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    tmp = p + ".tmp"
                    with open(tmp, "wb") as fh:
                        fh.write(synth(brand, level))
                    os.replace(tmp, p)
        return p

    def play(self, brand, level, test=False):
        """Sesi çalınmak üzere sıraya alır (hemen döner). Çalan ses kesilmez; o sırada gelen aynı ya da daha düşük
        seviyeli istek zaten öten sese katılır, daha acil olan sıraya girer. test: Ayarlar'daki "dinle" düğmesi (her
        basışta çalar). Dönüş: kabul edildi mi (ses kapalıysa ya da çalıcı yoksa False)."""
        if not self.enabled or self._player is None or level not in LEVEL_NAMES:
            return False
        with self._cv:
            busy = max(LEVEL_RANK.get(self._playing, 0), LEVEL_RANK.get(self._pending[1], 0) if self._pending else 0)
            if test or LEVEL_RANK[level] > busy:
                self._pending = (brand, level)
                self._cv.notify()
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="uyari-sesi", daemon=True)
                self._thread.start()
        return True

    def idle(self, timeout=5.0):
        """Sıradaki ve çalan ses bitene kadar bekler (testler için). Dönüş: boşaldı mı."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self._cv:
                if self._pending is None and self._playing is None:
                    return True
            time.sleep(0.01)
        return False

    def _run(self):
        while True:
            with self._cv:
                while self._pending is None:
                    self._cv.wait()
                brand, level = self._pending
                self._pending = None
                self._playing = level
            try:
                self._player(self.path(brand, level))
                self.played += 1
            except Exception:
                pass
            time.sleep(GAP_S)
            with self._cv:
                self._playing = None


class WarningBeeper:
    """Uyarı başına tek ses: yeni çıkan uyarı (kimliğiyle) bir kez çalınır. Değeri değişen aynı uyarı yeniden çalmaz;
    kaybolup REARM_S içinde geri gelen uyarı da çalmaz (eşik çevresinde gidip gelen değerler için)."""

    REARM_S = 60.0

    def __init__(self):
        self.active = {}
        self.cleared = {}

    def update(self, warnings, now, warn_too=False):
        """Çalınacak seviye: "crit", "warn" ya da None."""
        cur = {}
        for w in warnings or ():
            lvl = w.get("level")
            if lvl == "crit" or (lvl == "warn" and warn_too):
                cur[w.get("id") or w.get("text")] = lvl
        play = None
        for key, lvl in cur.items():
            if key in self.active:
                continue
            last = self.cleared.get(key)
            if last is not None and now - last < self.REARM_S:
                continue
            play = "crit" if (lvl == "crit" or play == "crit") else "warn"
        for key in self.active:
            if key not in cur:
                self.cleared[key] = now
        self.active = cur
        return play

    def rearm(self):
        """Yeniden çıkan her uyarı hemen ötsün (çekim modunda elle tetikleme: onarılıp yeniden tetiklenen arıza da öter)."""
        self.cleared.clear()
