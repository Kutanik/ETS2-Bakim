"""Çok oyunculu oturum algılama: TruckersMP ve oyunun resmi Konvoy modu.

- Konvoy: telemetrideki çok oyunculu zaman farkı (multiplayerTimeOffset) yalnızca Konvoy oturumunda sıfırdan farklıdır.
- TruckersMP: istemcisi oyun sürecine core_ets2mp.dll / core_atsmp.dll yükler; oyun sürecinin modüllerine bakılır.
Çok oyunculu oturumda motor zorla durdurulmaz (trafikte durdurmak kazaya ve kural ihlaline yol açar). Oyun modu
Otomatik iken uygulama böyle bir oturumda Çok Oyunculu moda geçer (app.App._wanted_mode).
"""
import ctypes
import sys
import time

GAME_EXES = ("eurotrucks2.exe", "amtrucks.exe")
TMP_MODULES = ("core_ets2mp.dll", "core_atsmp.dll")
LABELS = {"tmp": "TruckersMP", "convoy": "Konvoy"}

if sys.platform == "win32":
    from ctypes import wintypes

    TH32CS_SNAPPROCESS, TH32CS_SNAPMODULE, TH32CS_SNAPMODULE32 = 0x2, 0x8, 0x10
    INVALID = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    class MODULEENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("GlblcntUsage", wintypes.DWORD), ("ProccntUsage", wintypes.DWORD),
                    ("modBaseAddr", ctypes.c_void_p), ("modBaseSize", wintypes.DWORD), ("hModule", ctypes.c_void_p),
                    ("szModule", ctypes.c_wchar * 256), ("szExePath", ctypes.c_wchar * 260)]

    _k = ctypes.WinDLL("kernel32", use_last_error=True)
    _k.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    _k.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    _k.Process32FirstW.argtypes = (ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W))
    _k.Process32NextW.argtypes = (ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W))
    _k.Module32FirstW.argtypes = (ctypes.c_void_p, ctypes.POINTER(MODULEENTRY32W))
    _k.Module32NextW.argtypes = (ctypes.c_void_p, ctypes.POINTER(MODULEENTRY32W))
    _k.CloseHandle.argtypes = (ctypes.c_void_p,)


def _game_pids():
    snap = _k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID:
        return []
    pids = []
    try:
        e = PROCESSENTRY32W()
        e.dwSize = ctypes.sizeof(e)
        ok = _k.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            if e.szExeFile.lower() in GAME_EXES:
                pids.append(e.th32ProcessID)
            ok = _k.Process32NextW(snap, ctypes.byref(e))
    finally:
        _k.CloseHandle(snap)
    return pids


def _has_module(pid, names):
    snap = _k.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if not snap or snap == INVALID:
        return False
    try:
        m = MODULEENTRY32W()
        m.dwSize = ctypes.sizeof(m)
        ok = _k.Module32FirstW(snap, ctypes.byref(m))
        while ok:
            if m.szModule.lower() in names:
                return True
            ok = _k.Module32NextW(snap, ctypes.byref(m))
    finally:
        _k.CloseHandle(snap)
    return False


def truckersmp_running():
    """Oyun süreci TruckersMP istemcisiyle mi çalışıyor?"""
    if sys.platform != "win32":
        return False
    try:
        return any(_has_module(pid, TMP_MODULES) for pid in _game_pids())
    except Exception:
        return False


class MultiplayerDetector:
    CHECK_EVERY_S = 15.0

    def __init__(self):
        self.kind = None          # None | "tmp" | "convoy"
        self._tmp = False
        self._next = 0.0

    def update(self, frame, source_is_game=True):
        if not source_is_game:
            self.kind = None
            return None
        now = time.monotonic()
        if now >= self._next:
            self._next = now + self.CHECK_EVERY_S
            self._tmp = truckersmp_running()
        convoy = frame is not None and frame.ok and getattr(frame, "mp_offset", 0) != 0
        self.kind = "tmp" if self._tmp else "convoy" if convoy else None
        return self.kind

    def recheck(self):
        """Sonraki update() TruckersMP'yi beklemeden yeniden denetler (oyun yeniden açılınca eski sonuç kullanılmasın)."""
        self._next = 0.0

    @property
    def label(self):
        return LABELS.get(self.kind, "")
