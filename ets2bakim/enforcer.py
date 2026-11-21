"""Gerçekçi müdahale: motorun çalışmaması gereken durumlarda (akü bitik, motor kilitli,
yağsız kalma…) oyuna 'motor çalıştır/durdur' tuşunu gönderip motoru durdurur.

Telemetri SDK'sı salt okunur olduğu için tek yol klavye girdisidir. Güvenlik için tuş yalnızca
ön plandaki pencere eurotrucks2.exe / amtrucks.exe ise gönderilir.
"""
import ctypes
import os
import sys
import time

from .i18n import M

GAME_EXES = ("eurotrucks2.exe", "amtrucks.exe")

if sys.platform == "win32":
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.VkKeyScanW.argtypes = (wintypes.WCHAR,)
    user32.VkKeyScanW.restype = ctypes.c_short
    user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                    ctypes.POINTER(wintypes.DWORD))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)


def foreground_exe():
    if sys.platform != "win32":
        return ""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


def _scan_code(key):
    vk = user32.VkKeyScanW(key[0]) & 0xFF
    return user32.MapVirtualKeyW(vk, 0)


def _send(scan, up):
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.u.ki = KEYBDINPUT(0, scan, KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0), 0, 0)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


class Enforcer:
    COOLDOWN_S = 3.0

    def __init__(self):
        self.last_press = 0.0

    def stop_engine(self, key):
        """Motor durdurma tuşunu gönderir. Dönüş: (gönderildi_mi, açıklama)."""
        if sys.platform != "win32":
            return False, M("Yalnızca Windows'ta çalışır")
        now = time.monotonic()
        if now - self.last_press < self.COOLDOWN_S:
            return False, "bekleniyor"
        exe = foreground_exe()
        if exe not in GAME_EXES:
            return False, M("Oyun penceresi ön planda değil — motoru kendiniz durdurun")
        key = (key or "e").strip().lower()[:1] or "e"
        scan = _scan_code(key)
        _send(scan, False)
        time.sleep(0.06)
        _send(scan, True)
        self.last_press = now
        return True, M("'{key}' tuşu gönderildi", key=key.upper())
