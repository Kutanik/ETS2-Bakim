"""Sürüş modları: ECO / COMFORT / SPORT ve mod değiştirme tuşu.

Oyunun gaz kontrolü toplamadır (controls.sii: "mix aforward ... + semantical.aforward?0", "mix forward dforward +
aforward"). Oyun içi katman eklentisi (1.8+) semantik giriş cihazıyla gaza değer ekleyip çıkararak pedal haritasını
değiştirir: her karede oyuncunun gazını telemetriden okur ve modun istediği gaza göre düzeltir. Simülatör modu seçer ve
parametrelerini paylaşılan bellek başlığına yazar (overlay_feed.set_drive); simülatör kapanırsa eklenti 1,5 sn içinde
gaza karışmayı bırakır. Hız sabitleyici açıkken modlar gaza karışmaz.

ECO     : en fazla %75 güç, gaz en çok 0,6/sn hızla artar (yumuşak), 85 km/h hız sınırlayıcı (elle sürüşte)
COMFORT : güç sınırı yok, gaz en çok 1,5/sn hızla artar (yumuşak kalkış ve geçişler)
SPORT   : keskin pedal (gaz = 1 - (1 - pedal)^1,8: yarım pedalda ~%71), anında tepki

Mod değiştirme tuşu (ECO → COMFORT → SPORT → ECO) bir klavye tuşu ya da kumanda / direksiyon düğmesi (yön tuşu dahil)
olabilir; uygulamada "Tuş ata" ile seçilir ve yalnızca oyun penceresi öndeyken sayılır. Atama biçimi: "key:<sanal tuş
kodu>", "btn:<düğme no>", "pov:<up|down|left|right>"; boş = tuş yok.
"""
import os
import threading
import time
from collections import deque

from .gameinput import InputProbe, key_label
from .i18n import T

ORDER = ("eco", "comfort", "sport")
MODE_IDS = {"eco": 1, "comfort": 2, "sport": 3}
NAMES = {"eco": "ECO", "comfort": "COMFORT", "sport": "SPORT"}
DESCS = {
    "eco": "Güç %75 ile sınırlı, yumuşak gaz, 85 km/h hız sınırı",
    "comfort": "Yumuşak gaz tepkisi, güç sınırı yok",
    "sport": "Keskin pedal: yarım pedalda daha çok güç, anında tepki",
}
# cap: en yüksek gaz · rate: gazın en hızlı artışı (/sn, 0 = sınırsız) · vlim: hız sınırı (km/h, 0 = yok) · curve: pedal üssü
PARAMS = {
    "eco": dict(cap=0.75, rate=0.6, vlim=85.0, curve=1.0),
    "comfort": dict(cap=1.0, rate=1.5, vlim=0.0, curve=1.0),
    "sport": dict(cap=1.0, rate=0.0, vlim=0.0, curve=1.8),
}
DEFAULT_MODE = "comfort"
DEFAULT_KEY = "key:121"          # F10: oyunun varsayılan atamalarında boş
NO_BIND = {("key", 0x77), ("key", 0x1B)}   # katmanın tuşu (varsayılan F8), Esc atamayı iptal eder
POV_NAMES = {"up": "yukarı", "down": "aşağı", "left": "sol", "right": "sağ"}
CAPTURE_S = 10.0


def next_mode(mode):
    return ORDER[(ORDER.index(mode) + 1) % len(ORDER)] if mode in ORDER else DEFAULT_MODE


def header_params(settings, vehicle="truck"):
    """Paylaşılan bellek başlığına yazılacak (mod no, en yüksek gaz, artış hızı, hız sınırı, eğri); kapalıysa mod 0.
    Otomobilde ECO'nun 85 km/h hız sınırlayıcısı yoktur (tır / otobüs hız sınırı)."""
    mode = settings.get("drive_mode", DEFAULT_MODE)
    if not settings.get("drive_modes", True) or mode not in PARAMS:
        return 0, 1.0, 0.0, 0.0, 1.0
    p = PARAMS[mode]
    vlim = 0.0 if vehicle == "car" else p["vlim"]
    return MODE_IDS[mode], p["cap"], p["rate"], vlim, p["curve"]


def parse_binding(text):
    """"key:121" → ("key", 121) · "btn:5" → ("btn", 5) · "pov:up" → ("pov", "up"); geçersiz ya da boşsa None."""
    try:
        kind, _, val = str(text or "").partition(":")
        if kind == "key":
            vk = int(val)
            return ("key", vk) if 0 < vk < 0xFF and ("key", vk) not in NO_BIND else None
        if kind == "btn":
            n = int(val)
            return ("btn", n) if 1 <= n <= 32 else None
        if kind == "pov" and val in POV_NAMES:
            return ("pov", val)
    except ValueError:
        pass
    return None


def set_overlay_key(vk):
    """Katmanın tuşu (Ayarlar → Oyun içi katman) sürüş ve çekim moduna atanamaz; F8'den başka tuş seçilince F8 boşalır."""
    global NO_BIND
    NO_BIND = {("key", int(vk)), ("key", 0x1B)}


def format_binding(kind, value):
    return f"{kind}:{value}"


def binding_label(text):
    """Atamanın okunur adı (seçili dilde)."""
    b = parse_binding(text)
    if not b:
        return T("Tuş yok")
    kind, val = b
    if kind == "key":
        return key_label(val)
    if kind == "btn":
        return T("Kumanda düğmesi {n}", n=val)
    return T("Kumanda yön tuşu: {d_t}", d_t=POV_NAMES[val])


class HotkeyInput(InputProbe):
    """Atanan tuşu arka planda (60 Hz) okur ve basışları sayar; atama sırasında ilk yeni basışı yakalar. Sürüş modu
    tuşu ve çekim modu tuşu (filming.py) için ayrı birer örnek kullanılır."""

    POLL_S = 1 / 60

    def __init__(self, name="surus-modu-tusu"):
        super().__init__()
        self.name = name
        self.binding = None
        self.presses = deque(maxlen=8)
        self.captured = None               # atama sonucu ("key:121" ...) ya da "" (iptal)
        self.capture_until = 0.0
        self._capture_base = None
        self._was_down = False
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if os.name != "nt" or self._thread:
            return self
        self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()

    def set_binding(self, text):
        self.binding = parse_binding(text)
        self._was_down = False

    @property
    def capturing(self):
        return self.capture_until > 0

    def start_capture(self, now=None):
        with self._lock:
            self.capture_until = (time.monotonic() if now is None else now) + CAPTURE_S
            self._capture_base = None
            self.captured = None

    def cancel_capture(self):
        with self._lock:
            self.capture_until = 0.0
            self._capture_base = None

    def drain(self):
        n = 0
        while self.presses:
            self.presses.popleft()
            n += 1
        return n

    def take_captured(self):
        with self._lock:
            c, self.captured = self.captured, None
            return c

    def _run(self):
        while not self._stop.wait(self.POLL_S):
            try:
                self.poll(time.monotonic())
            except Exception:  # giriş okunamazsa mod yalnızca uygulamadan değiştirilir
                time.sleep(1.0)

    def poll(self, now, pressed=None):
        """pressed: yalnızca test için şu an basılı girişler kümesi (verilmezse klavye ve kumandalar okunur)."""
        with self._lock:
            if self.capture_until:
                if now > self.capture_until:
                    self.capture_until = 0.0
                    self.captured = ""
                    return
                cur = pressed if pressed is not None else self.all_pressed(now)
                if self._capture_base is None:   # atama başlarken basılı olanlar sayılmaz
                    self._capture_base = cur
                    return
                new = cur - self._capture_base
                self._capture_base &= cur        # bırakılan tuş yeniden basılırsa sayılır
                if ("key", 0x1B) in new:         # Esc: iptal
                    self.capture_until = 0.0
                    self.captured = ""
                    return
                new -= NO_BIND
                if new:
                    kind, val = sorted(new, key=str)[0]
                    self.captured = format_binding(kind, val)
                    self.capture_until = 0.0
                return
        if not self.binding:
            return
        if pressed is None:
            if not self._game_foreground():
                self._was_down = False
                return
            joys = self._joy_states(now) if self.binding[0] != "key" else []
            down = self._pressed(*self.binding, joys)
        else:
            down = self.binding in pressed
        if down and not self._was_down:
            self.presses.append(now)
        self._was_down = down


DriveModeInput = HotkeyInput   # eski ad (sürüş modu tuşu)
