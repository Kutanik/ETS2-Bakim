"""Oyunun kendi tuş atamalarını okur (profil klasöründeki controls.sii).

Katman, oyunda HUD'u (rota ekranı, harita, hasar, bakiye) gizleyen tuşa basılınca kendini de gizler.
Varsayılan atama F3'tür ("mix showhud"); kullanıcı değiştirdiyse burada bulunur ve katmana iletilir.
"""
import ctypes
import os
import re
import time

GAME_DIRS = ("Euro Truck Simulator 2", "American Truck Simulator")
DEFAULT_HUD_VK = 0x72  # F3

_NAMED = {"del": 0x2E, "delete": 0x2E, "ins": 0x2D, "insert": 0x2D, "home": 0x24, "end": 0x23,
          "pgup": 0x21, "pageup": 0x21, "pgdn": 0x22, "pgdown": 0x22, "pagedown": 0x22, "tab": 0x09,
          "space": 0x20, "back": 0x08, "backspace": 0x08, "pause": 0x13, "scroll": 0x91}


def documents_dirs():
    """Belgeler klasörü adayları (OneDrive'a taşınmış 'Belgeler' dahil)."""
    out = []
    try:
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:  # CSIDL_PERSONAL
            out.append(buf.value)
    except Exception:
        pass
    home = os.path.expanduser("~")
    for rel in ("Documents", "Belgeler", os.path.join("OneDrive", "Documents"), os.path.join("OneDrive", "Belgeler"),
                os.path.join("OneDrive", "Dokumente")):
        out.append(os.path.join(home, rel))
    seen, res = set(), []
    for d in out:
        k = os.path.normcase(os.path.abspath(d))
        if k not in seen and os.path.isdir(d):
            seen.add(k)
            res.append(d)
    return res


def find_controls(docs=None):
    """En son değiştirilen profilin controls.sii yolu (oyun kontrolleri kaydederken dosyayı günceller)."""
    best, best_t = None, -1.0
    for doc in docs if docs is not None else documents_dirs():
        for game in GAME_DIRS:
            for kind in ("steam_profiles", "profiles"):
                base = os.path.join(doc, game, kind)
                try:
                    names = os.listdir(base)
                except OSError:
                    continue
                for n in names:
                    p = os.path.join(base, n, "controls.sii")
                    try:
                        t = os.path.getmtime(p)
                    except OSError:
                        continue
                    if t > best_t:
                        best, best_t = p, t
    return best


def key_to_vk(name):
    n = name.lower()
    m = re.fullmatch(r"f(\d{1,2})", n)
    if m and 1 <= int(m.group(1)) <= 24:
        return 0x70 + int(m.group(1)) - 1
    if len(n) == 1 and ("a" <= n <= "z" or "0" <= n <= "9"):
        return ord(n.upper())
    return _NAMED.get(n)


def parse_mix_key(text, mix="showhud"):
    """'mix showhud `keyboard.f3?0 | ...`' satırındaki ilk klavye tuşunun sanal tuş kodu."""
    m = re.search(r'"mix\s+' + re.escape(mix) + r"\s+`([^`]*)`", text)
    if not m:
        return None
    k = re.search(r"keyboard\.([a-z0-9_]+)\?", m.group(1), re.I)
    return key_to_vk(k.group(1)) if k else None


class HudKey:
    """HUD gizleme tuşunu dosya değiştikçe yeniden okur (en fazla 30 sn'de bir bakar)."""

    def __init__(self, docs=None):
        self.docs = docs
        self.vk = DEFAULT_HUD_VK
        self.path = None
        self._mtime = None
        self._checked = 0.0

    def get(self):
        now = time.monotonic()
        if now - self._checked < 30 and self._checked:
            return self.vk
        self._checked = now
        try:
            p = find_controls(self.docs)
            if not p:
                return self.vk
            t = os.path.getmtime(p)
            if p != self.path or t != self._mtime:
                self.path, self._mtime = p, t
                with open(p, encoding="utf-8", errors="replace") as fh:
                    vk = parse_mix_key(fh.read())
                self.vk = vk or DEFAULT_HUD_VK
        except Exception:
            pass
        return self.vk
