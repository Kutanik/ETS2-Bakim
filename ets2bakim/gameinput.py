"""Oyun penceresi öndeyken klavye tuşlarını ve kumanda / direksiyon düğmelerini (winmm) okuma.

Silecek kademesi (wipers.py) ve sürüş modu tuşu (drivemode.py) için ortak. Kumandalar winmm joyGetPosEx ile okunur
(DirectInput direksiyonlar dahil, en çok 32 düğme ve bir yön tuşu); takılan / çıkarılan kumandalar 5 sn'de bir aranır.
Silecek, sürüş modu ve çekim modu okuyucuları (her biri ~60 Hz) kumandaları tek ortak okumadan alır: kumanda başına
saniyede ~60 joyGetPosEx çağrısı ve 5 sn'de bir tek tarama (eskiden her okuyucu ayrı ayrı okuyor ve tarıyordu).
"""
import ctypes
import os
import threading

GAME_EXES = ("eurotrucks2.exe", "amtrucks.exe")
JOY_SCAN_S = 5.0        # takılan / çıkarılan kumandalar bu sıklıkla aranır (16 kimlik)
JOY_SHARE_S = 0.012     # bu süreden yeni okuma öbür okuyuculara aynen verilir
_joy_lock = threading.Lock()
_joy = {"ids": [], "scan": -1e9, "t": -1e9, "states": []}
POV_CENTER = {"up": 0, "right": 9000, "down": 18000, "left": 27000}
# atamada sayılmayan tuşlar: fare düğmeleri, sol/sağ ayrımı olmayan genel Shift/Ctrl/Alt (ayrıları sayılır),
# Windows tuşları ve sanal karakter tuşu
SKIP_VK = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x10, 0x11, 0x12, 0x5B, 0x5C, 0xE7, 0xFF}


class JOYINFOEX(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulong) for n in ("dwSize", "dwFlags", "dwXpos", "dwYpos", "dwZpos", "dwRpos", "dwUpos",
                                               "dwVpos", "dwButtons", "dwButtonNumber", "dwPOV", "dwReserved1",
                                               "dwReserved2")]


def pov_matches(pov, direction):
    if pov == 0xFFFF or pov > 36000:
        return False
    d = abs(pov - POV_CENTER[direction]) % 36000
    return min(d, 36000 - d) <= 4500   # çapraz basışlar da sayılır


def pov_direction(pov):
    """Yön tuşunun en yakın ana yönü (basılı değilse None)."""
    if pov == 0xFFFF or pov > 36000:
        return None
    return min(POV_CENTER, key=lambda k: min(abs(pov - POV_CENTER[k]) % 36000, 36000 - abs(pov - POV_CENTER[k]) % 36000))


class InputProbe:
    """Oyun penceresi önde mi, kumanda düğmeleri ve klavye tuşları basılı mı (yalnızca Windows)."""

    def __init__(self):
        self._fg_cache = (None, False)

    def _game_foreground(self):
        u, k = ctypes.windll.user32, ctypes.windll.kernel32
        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return False
        if self._fg_cache[0] == hwnd:
            return self._fg_cache[1]
        pid = ctypes.c_ulong()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        ok = False
        k.OpenProcess.restype = ctypes.c_void_p
        h = k.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if h:
            buf = ctypes.create_unicode_buffer(520)
            n = ctypes.c_ulong(520)
            if k.QueryFullProcessImageNameW(ctypes.c_void_p(h), 0, buf, ctypes.byref(n)):
                ok = os.path.basename(buf.value).lower() in GAME_EXES
            k.CloseHandle(ctypes.c_void_p(h))
        self._fg_cache = (hwnd, ok)
        return ok

    @staticmethod
    def _joy_states(now):
        """Bağlı kumandaların (düğmeler, yön tuşu) durumu; okuyucular arasında ortak (bkz. modül açıklaması)."""
        with _joy_lock:
            if 0 <= now - _joy["t"] < JOY_SHARE_S:
                return _joy["states"]
            winmm = ctypes.windll.winmm
            if now - _joy["scan"] > JOY_SCAN_S:  # takılan / çıkarılan kumandalar
                _joy["scan"] = now
                ids = []
                for i in range(16):
                    ji = JOYINFOEX(ctypes.sizeof(JOYINFOEX), 0xC0)
                    if winmm.joyGetPosEx(i, ctypes.byref(ji)) == 0:
                        ids.append(i)
                _joy["ids"] = ids
            states = []
            for i in _joy["ids"]:
                ji = JOYINFOEX(ctypes.sizeof(JOYINFOEX), 0xC0)  # JOY_RETURNBUTTONS | JOY_RETURNPOV
                if winmm.joyGetPosEx(i, ctypes.byref(ji)) == 0:
                    states.append((ji.dwButtons, ji.dwPOV))
            _joy["t"], _joy["states"] = now, states
            return states

    @staticmethod
    def _pressed(kind, value, joys):
        if kind == "key":
            return bool(ctypes.windll.user32.GetAsyncKeyState(value) & 0x8000)
        if kind == "btn":
            return any(b & (1 << (value - 1)) for b, _ in joys)
        return any(pov_matches(p, value) for _, p in joys)

    def all_pressed(self, now):
        """Şu an basılı tüm girişler: {("key", vk), ("btn", n), ("pov", yön)} (tuş atamada yeni basışı bulmak için)."""
        out = set()
        u = ctypes.windll.user32
        for vk in range(0x08, 0xFF):
            if vk not in SKIP_VK and u.GetAsyncKeyState(vk) & 0x8000:
                out.add(("key", vk))
        for buttons, pov in self._joy_states(now):
            for i in range(32):
                if buttons & (1 << i):
                    out.add(("btn", i + 1))
            d = pov_direction(pov)
            if d:
                out.add(("pov", d))
        return out


def key_label(vk):
    """Klavye tuşunun Windows'taki adı (ör. "F10", "Num 5"); bulunamazsa onaltılık kod."""
    if os.name == "nt":
        try:
            u = ctypes.windll.user32
            sc = u.MapVirtualKeyW(vk, 0)
            ext = vk in (0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x6F, 0xA3, 0xA5)
            buf = ctypes.create_unicode_buffer(64)
            if sc and u.GetKeyNameTextW((sc << 16) | (1 << 24 if ext else 0), buf, 64):
                return buf.value
        except Exception:
            pass
    return f"0x{vk:02X}"
