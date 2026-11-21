"""Akıllı Uygulama Denetimi (Smart App Control) uyumu.

Denetim açıkken Windows, Microsoft'un tanımadığı ve güvenilir bir sertifika kuruluşunca (Microsoft Trusted Root
Program) imzalanmamış her DLL'i engeller; kendi oluşturulmuş (self-signed) imza da imzasız sayılır. Bu uygulamada:
  - Python (python.org, PSF imzalı), pencere bileşenleri ve telemetri eklentisi (scs-telemetry.dll) geçer.
  - Oyun içi katman (ets2bakim_overlay.dll) her derlemede yeni bir dosya olduğu için tanınmaz; imzasızsa oyun onu
    yükleyemez. Simülatör, uygulama penceresi ve motor durdurma (tuş yöntemi) yine çalışır.
Bu modül denetimin durumunu ve katman DLL'inin imzasını okur; arayüz ve kurulum betiği buna göre davranır.
"""
import ctypes
import os
import sys
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DLL_NAME = "ets2bakim_overlay.dll"
# katman DLL'inin kaynağı: dağıtım paketinde (kurulu programda) eklenti\, geliştirme klasöründe overlay\build\
BUILD_DLL = next((p for p in (os.path.join(ROOT, "eklenti", DLL_NAME), os.path.join(ROOT, "overlay", "build", DLL_NAME))
                  if os.path.isfile(p)), os.path.join(ROOT, "overlay", "build", DLL_NAME))
PACKAGED = os.path.isfile(os.path.join(ROOT, "paket.json"))         # dağıtım paketinden kurulmuş program
GAMES = ("Euro Truck Simulator 2", "American Truck Simulator")
CHECK_EVERY_S = 60.0

# WinVerifyTrust sonuçları
TRUST_E_NOSIGNATURE = 0x800B0100
TRUST_E_SUBJECT_FORM_UNKNOWN = 0x800B0003
TRUST_E_PROVIDER_UNKNOWN = 0x800B0001
CRYPT_E_FILE_ERROR = 0x80092003


def sac_state():
    """'on' (zorunlu), 'eval' (değerlendirme), 'off' ya da None (bu Windows'ta yok / okunamadı)."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy") as k:
            v = winreg.QueryValueEx(k, "VerifiedAndReputablePolicyState")[0]
    except OSError:
        return None
    return {0: "off", 1: "on", 2: "eval"}.get(int(v))


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort), ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, s):
        b = uuid.UUID(s).bytes_le
        g = cls()
        ctypes.memmove(ctypes.byref(g), b, 16)
        return g


class _WintrustFileInfo(ctypes.Structure):
    _fields_ = [("cbStruct", ctypes.c_ulong), ("pcwszFilePath", ctypes.c_wchar_p),
                ("hFile", ctypes.c_void_p), ("pgKnownSubject", ctypes.c_void_p)]


class _WintrustData(ctypes.Structure):
    _fields_ = [("cbStruct", ctypes.c_ulong), ("pPolicyCallbackData", ctypes.c_void_p),
                ("pSIPClientData", ctypes.c_void_p), ("dwUIChoice", ctypes.c_ulong),
                ("fdwRevocationChecks", ctypes.c_ulong), ("dwUnionChoice", ctypes.c_ulong),
                ("pFile", ctypes.POINTER(_WintrustFileInfo)), ("dwStateAction", ctypes.c_ulong),
                ("hWVTStateData", ctypes.c_void_p), ("pwszURLReference", ctypes.c_wchar_p),
                ("dwProvFlags", ctypes.c_ulong), ("dwUIContext", ctypes.c_ulong),
                ("pSignatureSettings", ctypes.c_void_p)]


_GENERIC_VERIFY_V2 = "00AAC56B-CD44-11d0-8CC2-00C04FC295EE"


def signature_status(path):
    """Dosyaya gömülü Authenticode imzası: 'valid' (güvenilir kökten), 'unsigned', 'untrusted' (ör. self-signed),
    'missing' ya da 'unknown'. Ağa çıkmaz (iptal listesi denetlenmez). Windows'un katalogla imzalı sistem dosyaları
    burada 'unsigned' görünür; yalnızca kendi DLL'imiz için kullanılır."""
    if not os.path.isfile(path):
        return "missing"
    if sys.platform != "win32":
        return "unknown"
    try:
        fi = _WintrustFileInfo(ctypes.sizeof(_WintrustFileInfo), path, None, None)
        wd = _WintrustData()
        wd.cbStruct = ctypes.sizeof(_WintrustData)
        wd.dwUIChoice = 2              # WTD_UI_NONE
        wd.fdwRevocationChecks = 0     # WTD_REVOKE_NONE
        wd.dwUnionChoice = 1           # WTD_CHOICE_FILE
        wd.pFile = ctypes.pointer(fi)
        wd.dwStateAction = 1           # WTD_STATEACTION_VERIFY
        wd.dwProvFlags = 0x1000        # WTD_CACHE_ONLY_URL_RETRIEVAL (ağa çıkma)
        action = _GUID.parse(_GENERIC_VERIFY_V2)
        wvt = ctypes.windll.wintrust.WinVerifyTrust
        wvt.argtypes = [ctypes.c_void_p, ctypes.POINTER(_GUID), ctypes.POINTER(_WintrustData)]
        wvt.restype = ctypes.c_long
        res = wvt(ctypes.c_void_p(-1), ctypes.byref(action), ctypes.byref(wd)) & 0xFFFFFFFF  # INVALID_HANDLE_VALUE
        wd.dwStateAction = 2           # WTD_STATEACTION_CLOSE
        wvt(ctypes.c_void_p(-1), ctypes.byref(action), ctypes.byref(wd))
    except (OSError, AttributeError, ValueError):
        return "unknown"
    if res == 0:
        return "valid"
    if res in (TRUST_E_NOSIGNATURE, TRUST_E_SUBJECT_FORM_UNKNOWN, TRUST_E_PROVIDER_UNKNOWN):
        return "unsigned"
    if res == CRYPT_E_FILE_ERROR:
        return "missing"
    return "untrusted"   # imzalı ama güvenilmez (tanınmayan kök sertifika, kırık zincir, açıkça güvenilmeyen)


def steam_game_dirs():
    """Kurulu ETS2/ATS oyunlarının bin\\win_x64 klasörleri (Steam kütüphanelerinden)."""
    libs = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            libs.append(winreg.QueryValueEx(k, "SteamPath")[0].replace("/", "\\"))
    except OSError:
        pass
    libs.append(r"C:\Program Files (x86)\Steam")
    for base in list(libs):
        vdf = os.path.join(base, "steamapps", "libraryfolders.vdf")
        try:
            with open(vdf, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith('"path"'):
                        libs.append(line.split('"')[3].replace("\\\\", "\\"))
        except (OSError, IndexError):
            pass
    out, seen = [], set()
    for lib in libs:
        for g in GAMES:
            b = os.path.normpath(os.path.join(lib, "steamapps", "common", g, "bin", "win_x64"))
            if b.lower() not in seen and os.path.isdir(b):
                seen.add(b.lower())
                out.append(b)
    return out


def check():
    """Denetim durumu ve katman DLL'lerinin (derlenen + oyunlara kurulu) imzaları."""
    state = sac_state()
    installed = []
    for b in steam_game_dirs():
        p = os.path.join(b, "plugins", DLL_NAME)
        if os.path.isfile(p):
            installed.append({"path": p, "game": os.path.basename(os.path.dirname(os.path.dirname(b))),
                              "signature": signature_status(p)})
    build = signature_status(BUILD_DLL)
    blocked = state == "on" and any(i["signature"] != "valid" for i in installed)
    return {"sac": state, "build_signature": build, "installed": installed, "overlay_blocked": blocked,
            "build_blocked": state == "on" and build not in ("valid", "missing")}


class AppControlMonitor:
    """Durumu seyrek yeniler (kayıt defteri + birkaç dosyanın imzası; ~ms)."""

    def __init__(self):
        self.info = None
        self._t = -1e9

    def get(self, now=None):
        now = time.monotonic() if now is None else now
        if self.info is None or now - self._t >= CHECK_EVERY_S:
            self._t = now
            try:
                self.info = check()
            except Exception:  # denetim bilgisi alınamazsa uygulama etkilenmesin
                self.info = {"sac": None, "overlay_blocked": False, "installed": [], "build_signature": "unknown",
                             "build_blocked": False}
        return self.info


if __name__ == "__main__":  # python -m ets2bakim.appcontrol : durum raporu
    info = check()
    names = {"on": "AÇIK (zorunlu)", "eval": "değerlendirme", "off": "kapalı", None: "yok / okunamadı"}
    print(f"Akıllı Uygulama Denetimi: {names.get(info['sac'])}")
    print(f"Derlenen katman ({BUILD_DLL}): imza {info['build_signature']}")
    for i in info["installed"]:
        print(f"Oyuna kurulu katman ({i['game']}): imza {i['signature']}")
    if info["overlay_blocked"]:
        print("SONUÇ: oyun içi katman engellenir (imzasız). Simülatör, uygulama penceresi ve motor durdurma çalışır.")
    elif info["sac"] == "on":
        print("SONUÇ: denetim açık; kurulu katman imzalı ya da kurulu değil — engellenecek dosya yok.")
    else:
        print("SONUÇ: denetim kapalı; her şey çalışır.")
