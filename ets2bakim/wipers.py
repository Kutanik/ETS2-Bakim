"""Silecek kademesi (kapalı / aralıklı / yavaş / hızlı) ve silecek motorunun çektiği akım.

SCS SDK silecek için yalnızca açık/kapalı bildirir (truck.wipers); kademe oyunun silecek tuşlarından izlenir.
Profildeki controls.sii okunur: 'mix wipers' (sonraki kademe), 'wipersback' (önceki), 'wipers0..4' (doğrudan kademe).
Bu atamalardaki klavye tuşları ile kumanda/direksiyon düğmeleri ve yön tuşu (POV) yalnızca oyun penceresi öndeyken
saniyede ~60 kez okunur; başka hiçbir tuşa bakılmaz.

Oyunun sırası: kapalı → aralıklı → yavaş → hızlı → kapalı. Telemetri "kapalı" derse kademe sıfırlanır, "açık" derse
en az "aralıklı" sayılır; böylece kaçan bir basış en geç silecek kapanınca düzelir. Otomatik yağmur sensörü açıksa
(g_rain_sensor) kendiliğinden açılan silecek "yavaş" kabul edilir.
"""
import os
import re
import threading
import time
from collections import deque

from .gamecfg import documents_dirs, find_controls, key_to_vk
from .gameinput import GAME_EXES, InputProbe  # noqa: F401

OFF, INTERVAL, SLOW, FAST = 0, 1, 2, 3
STAGE_NAMES = {OFF: "kapalı", INTERVAL: "aralıklı", SLOW: "yavaş", FAST: "hızlı"}
# 24 V iki hızlı silecek motoru (iki kol, tek motor) ortalama akımı. Aralıklıda motor birkaç saniyede bir tek
# süpürme yapar (~%25 görev); kademe bilinmiyorsa yavaş kabul edilir.
CURRENT_A = {INTERVAL: 1.2, SLOW: 3.5, FAST: 5.5}
ICE_FACTOR = 1.25          # 0 °C altı: kar/buz yüzünden lastik camda zor kayar, motor daha çok akım çeker
SETTLE_S = 0.6             # tuşa basıldıktan sonra telemetrinin yetişmesi için beklenen süre
SHORT_PRESS_S = 0.45       # short_press(...): bu süreden kısa basılıp bırakılınca sayılır


def wiper_current_a(stage, ambient=None):
    """Silecek açıkken çekilen ortalama akım (A)."""
    a = CURRENT_A.get(stage, CURRENT_A[SLOW])
    if ambient is not None and ambient < 0:
        a *= ICE_FACTOR
    return a


# ---------------------------------------------------------------- tuş atamaları
def parse_bindings(text):
    """controls.sii metninden silecek atamaları: [(eylem, kademe, tür, değer, kısa_basış)].
    eylem: fwd | back | set · tür: key (sanal tuş kodu) | btn (düğme no, 1'den) | pov (yön: up/down/left/right)"""
    out = []
    actions = [("wipers", "fwd", None), ("wipersback", "back", None)] + [(f"wipers{i}", "set", i) for i in range(5)]
    for mix, action, stage in actions:
        m = re.search(r'"mix\s+' + mix + r"\s+`([^`]*)`", text)
        if not m:
            continue
        expr = m.group(1)
        for k in re.finditer(r"(short_press\(\s*)?keyboard\.([a-z0-9_]+)\?", expr, re.I):
            vk = key_to_vk(k.group(2))
            if vk:
                out.append((action, stage, "key", vk, bool(k.group(1))))
        for j in re.finditer(r"(short_press\(\s*)?joy\d*\.(?:pov\d+_(up|down|left|right)|b(\d+))\?", expr, re.I):
            short = bool(j.group(1))
            if j.group(2):
                out.append((action, stage, "pov", j.group(2).lower(), short))
            else:
                out.append((action, stage, "btn", int(j.group(3)), short))
    return out


def rain_sensor_on(docs=None):
    """Oyunun otomatik yağmur sensörü ayarı (config.cfg: g_rain_sensor)."""
    for d in docs if docs is not None else documents_dirs():
        for game in ("Euro Truck Simulator 2", "American Truck Simulator"):
            p = os.path.join(d, game, "config.cfg")
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    m = re.search(r'uset\s+g_rain_sensor\s+"(\d+)"', fh.read())
                if m:
                    return m.group(1) != "0"
            except OSError:
                continue
    return False


# ---------------------------------------------------------------- girişleri okuma (yalnızca oyun öndeyken)
class WiperInput(InputProbe):
    """Silecek tuşlarını arka planda okur ve basışları sıraya koyar (yalnızca Windows)."""

    POLL_S = 1 / 60

    def __init__(self, docs=None):
        super().__init__()
        self.docs = docs
        self.bindings = []
        self.events = deque(maxlen=32)
        self._path = self._mtime = None
        self._checked = 0.0
        self._down = {}           # bağlama -> basılma anı (basılı değilse yok)
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if os.name != "nt" or self._thread:
            return self
        self._thread = threading.Thread(target=self._run, name="silecek-girisi", daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()

    def drain(self):
        out = []
        while self.events:
            out.append(self.events.popleft())
        return out

    def _reload(self, now):
        if now - self._checked < 30 and self._checked:
            return
        self._checked = now
        try:
            p = find_controls(self.docs)
            if not p:
                return
            t = os.path.getmtime(p)
            if p != self._path or t != self._mtime:
                self._path, self._mtime = p, t
                with open(p, encoding="utf-8", errors="replace") as fh:
                    self.bindings = parse_bindings(fh.read())
                self._down.clear()
        except OSError:
            pass

    def _run(self):
        while not self._stop.wait(self.POLL_S):
            try:
                self.poll(time.monotonic())
            except Exception:  # giriş okunamazsa silecek telemetriye göre (yavaş) hesaplanır
                time.sleep(1.0)

    def poll(self, now):
        self._reload(now)
        if not self.bindings:
            return
        if not self._game_foreground():
            self._down.clear()
            return
        need_joy = any(b[2] != "key" for b in self.bindings)
        joys = self._joy_states(now) if need_joy else []
        for b in self.bindings:
            action, stage, kind, value, short = b
            down = self._pressed(kind, value, joys)
            t0 = self._down.get(b)
            if down and t0 is None:
                self._down[b] = now
                if not short:
                    self.events.append((action, stage, now))
            elif not down and t0 is not None:
                del self._down[b]
                if short and now - t0 < SHORT_PRESS_S:
                    self.events.append((action, stage, now))


# ---------------------------------------------------------------- kademe takibi
class WiperTracker:
    """Telemetri (açık/kapalı) + tuş basışlarından silecek kademesi."""

    def __init__(self, inp=None, rain_sensor=None):
        self.input = inp
        self.stage = OFF
        self.last_event = -1e9
        self.auto_stage = SLOW if (rain_sensor if rain_sensor is not None else False) else INTERVAL

    def update(self, f, now=None):
        now = time.monotonic() if now is None else now
        events = self.input.drain() if self.input else []
        if f.paused:
            events = []  # menüdeyken tuşlar sileceği değiştirmez
        for action, stage, t in events:
            if action == "fwd":
                self.stage = (self.stage + 1) % 4
            elif action == "back":
                self.stage = max(OFF, self.stage - 1)
            else:
                self.stage = min(FAST, stage)
            self.last_event = t
        if now - self.last_event > SETTLE_S:  # telemetri tuşa yetişti: ona uy
            if not f.wipers:
                self.stage = OFF
            elif self.stage == OFF:
                self.stage = self.auto_stage
        return self.stage if f.wipers else OFF
