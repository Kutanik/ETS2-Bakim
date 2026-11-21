"""Kurulum ve kaldırma (dağıtım paketi): program, oyun eklentileri, kısayollar ve Windows "Uygulamalar" kaydı.

Dağıtım zip'indeki INSTALL.bat bunu paketin kendi Python'uyla çalıştırır:
    program\\python\\python.exe -X utf8 -m ets2bakim.kurulum kur
Kurulan programda:
    Ayarlar → Uygulamalar → Kaldır, Başlat menüsü → "… kaldır" ya da KALDIR.bat   ->  kurulum kaldir
    Başlat menüsü → "Eklentileri kur" ya da EKLENTI_KUR.bat                       ->  kurulum eklenti

Yönetici izni gerekmez: program %LOCALAPPDATA%\\Programs\\ETS2-Bakim klasörüne, kayıt HKCU'ya yazılır. Oyun eklentileri
Steam kütüphanelerindeki ETS2 / ATS bin\\win_x64\\plugins klasörlerine kopyalanır. Kurulumun yaptığı her şey
kurulum.json dosyasına yazılır; kaldırma yalnızca onları geri alır: kurulumdan önce başka bir sürümü olan telemetri
eklentisi yedeklenip geri konur, aynısı zaten kuruluysa (başka bir uygulamanın da olabilir) ona hiç dokunulmaz.

Tek / Çok Oyunculu mod aynı uygulamanın içinde seçilir: tek kısayol kurulur. 1.1'in iki ayrı uygulamasının kısayolları
güncellemede kaldırılır (kullanıcı verisi data ve data_mp klasörlerinde korunur).
Dosyalar içerik olarak kopyalanır: zip'ten gelen "internetten indirildi" işareti (Zone.Identifier) kurulan dosyalara
taşınmaz, kurulu program diğer programlar gibi çalışır.
"""
import argparse
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

from . import __version__, appcontrol, window

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # bu kopyanın kökü (paketin program\ klasörü ya da kurulu klasör)
DIR_NAME = "ETS2-Bakim"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ETS2Bakim"
MANIFEST = "kurulum.json"
TELEMETRY_DLL = "scs-telemetry.dll"
OVERLAY_DLL = appcontrol.DLL_NAME
BACKUP_SUFFIX = ".ets2bakim-yedek"
GAME_EXES = ("eurotrucks2.exe", "amtrucks.exe")
DATA_DIRS = ("data", "data_mp", "data_demo", "data_demo_mp")      # kullanıcı verisi: güncellemede korunur
REPLACE_DIRS = ("python", "ets2bakim", "web", "eklenti", "LISANSLAR")  # güncellemede silinip yeniden kopyalanır (sesler\ozel korunur)
REMOVED_DIRS = ("mod",)            # artık pakette olmayan klasörler, güncellemede silinir (1.3.0 denemelerinin teyp modu)
LEGACY_MODES = ("tek", "cok")      # 1.1'in iki ayrı uygulaması: kısayolları (lnk_tek / lnk_cok) güncellemede ve kaldırmada silinir
WEBVIEW2_ID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"

# ---------------------------------------------------------------- iletiler (Windows'un arayüz dilinde)
TEXT = {
    "tr": {
        "product": "ETS2 Bakım Simülatörü", "folder": "ETS2 Bakım", "lnk_app": "ETS2 Bakım",
        "lnk_tek": "ETS2 Bakım - Tek Oyunculu", "lnk_cok": "ETS2 Bakım - Çok Oyunculu",
        "lnk_plugins": "Eklentileri kur", "lnk_demo": "Demo (oyunsuz deneme)", "lnk_uninstall": "ETS2 Bakım'ı kaldır",
        "yes": "e", "no": "h", "yn": "(E/H)",
        "h_install": "{product} {v} — kurulum", "h_uninstall": "{product} — kaldırma",
        "h_plugins": "{product} — oyun eklentilerini kur", "target": "Kurulum klasörü: {path}",
        "extract": "Program dosyaları bulunamadı. Zip dosyasını önce tamamen çıkarın (sağ tık → Tümünü ayıkla), sonra INSTALL.bat'ı çalıştırın.",
        "game_running": "Oyun açık ({exe}): eklenti dosyaları değiştirilemez. Oyunu kapatıp Enter'a basın (vazgeçmek için V yazın).",
        "game_running_quiet": "Oyun açık ({exe}): önce oyunu kapatın.",
        "app_closing": "ETS2 Bakım açık; kaydedilip kapatılıyor…",
        "app_stuck": "ETS2 Bakım kapanmadı. Uygulamayı kapatıp Enter'a basın (vazgeçmek için V yazın).",
        "cancelled": "Vazgeçildi; hiçbir şey değiştirilmedi.",
        "copying": "Program dosyaları kopyalanıyor…", "copied": "Program kuruldu: {path}",
        "game_found": "Oyun bulundu: {game}",
        "installed": "  KURULDU      {path}",
        "updated": "  GÜNCELLENDİ  {path}",
        "same_kept": "  DOKUNULMADI  {path} (aynı telemetri eklentisi zaten kurulu)",
        "backed_up": "  YEDEKLENDİ   {path} → {backup} (kaldırınca geri konur)",
        "sac_skip": "  ATLANDI      oyun içi katman: Akıllı Uygulama Denetimi açık ve katman DLL'i imzasız, oyun onu yükleyemez. "
                    "Simülatör, uygulama penceresi ve uyarılar katmansız çalışır.",
        "sac_removed": "  KALDIRILDI   {path} (Akıllı Uygulama Denetimi her oyun açılışında engelleyip bildirim çıkarıyordu)",
        "copy_failed": "  KOPYALANAMADI {path}: {err}. Oyunu kapatın; olmazsa INSTALL.bat'ı sağ tık → Yönetici olarak çalıştırın.",
        "no_game": "Oyun bulunamadı (Steam kütüphanelerinde Euro Truck Simulator 2 / American Truck Simulator yok). Oyunu "
                   "kurduktan sonra Başlat menüsü → {folder} → “{lnk}” ile eklentileri kurun. Steam dışı kurulumda "
                   "{src} klasöründeki iki DLL'i <oyun klasörü>\\bin\\win_x64\\plugins klasörüne kopyalayın.",
        "no_source": "Eklenti dosyası bulunamadı: {path}",
        "shortcuts": "Kısayollar: masaüstü ve Başlat menüsü → {folder}",
        "lnk_kept": "  DOKUNULMADI  {path} (aynı adlı kısayol başka bir kopyayı açıyor)",
        "registered": "Windows Ayarlar → Uygulamalar listesine eklendi (kaldırmak için oradan ya da Başlat menüsünden).",
        "no_webview": "Microsoft Edge WebView2 Runtime bulunamadı: uygulama kendi penceresi yerine Edge'de açılır. "
                      "Kurmak isterseniz: {url}",
        "done_install": "Kurulum tamamlandı.",
        "sdk_hint": "Oyunu açınca çıkan “Advanced SDK features” uyarısını OK ile onaylayın.",
        "launching": "Uygulama açılıyor…",
        "press_enter": "Kapatmak için Enter'a basın.",
        "failed": "İşlem yarıda kaldı: {err}",
        "confirm_uninstall": "{product} bu bilgisayardan tamamen kaldırılacak: program, oyun eklentileri, kısayollar, "
                             "ayarlar ve bakım kayıtları. Devam edilsin mi? {yn} ",
        "not_installed": "{product} bu klasörde kurulu görünmüyor: {path}",
        "removed": "  KALDIRILDI   {path}",
        "restored": "  GERİ KONDU   {path} (kurulumdan önceki telemetri eklentisi)",
        "teyp_removed": "  SİLİNDİ      {path} (teyp modu)",
        "remove_failed": "  SİLİNEMEDİ   {path}: {err}",
        "removed_shortcuts": "Kısayollar kaldırıldı.", "unregistered": "Uygulamalar listesinden çıkarıldı.",
        "folder_later": "Program klasörü birkaç saniye içinde silinecek: {path}",
        "done_uninstall": "Kaldırma tamamlandı.", "done_plugins": "Tamam.",
    },
    "en": {
        "product": "ETS2 Maintenance Simulator", "folder": "ETS2 Maintenance", "lnk_app": "ETS2 Maintenance",
        "lnk_tek": "ETS2 Maintenance - Singleplayer", "lnk_cok": "ETS2 Maintenance - Multiplayer",
        "lnk_plugins": "Install plugins", "lnk_demo": "Demo (try without the game)",
        "lnk_uninstall": "Uninstall ETS2 Maintenance",
        "yes": "y", "no": "n", "yn": "(Y/N)",
        "h_install": "{product} {v} — setup", "h_uninstall": "{product} — uninstall",
        "h_plugins": "{product} — install game plugins", "target": "Install folder: {path}",
        "extract": "Program files not found. Extract the whole zip first (right-click → Extract All), then run INSTALL.bat.",
        "game_running": "The game is running ({exe}): plugin files cannot be replaced. Close the game and press Enter "
                        "(type C to cancel).",
        "game_running_quiet": "The game is running ({exe}): close it first.",
        "app_closing": "ETS2 Maintenance is open; saving and closing it…",
        "app_stuck": "ETS2 Maintenance did not close. Close the app and press Enter (type C to cancel).",
        "cancelled": "Cancelled; nothing was changed.",
        "copying": "Copying program files…", "copied": "Program installed: {path}",
        "game_found": "Game found: {game}",
        "installed": "  INSTALLED    {path}",
        "updated": "  UPDATED      {path}",
        "same_kept": "  UNTOUCHED    {path} (the same telemetry plugin is already installed)",
        "backed_up": "  BACKED UP    {path} → {backup} (restored on uninstall)",
        "sac_skip": "  SKIPPED      in-game overlay: Smart App Control is on and the overlay DLL is unsigned, the game "
                    "cannot load it. The simulator, the app window and the warnings work without the overlay.",
        "sac_removed": "  REMOVED      {path} (Smart App Control blocked it with a notice at every game start)",
        "copy_failed": "  COPY FAILED  {path}: {err}. Close the game; if it still fails, right-click INSTALL.bat → Run as "
                       "administrator.",
        "no_game": "Game not found (no Euro Truck Simulator 2 / American Truck Simulator in the Steam libraries). After "
                   "installing the game, use Start menu → {folder} → “{lnk}”. For a non-Steam install copy the two DLLs "
                   "from {src} into <game folder>\\bin\\win_x64\\plugins.",
        "no_source": "Plugin file not found: {path}",
        "shortcuts": "Shortcuts: desktop and Start menu → {folder}",
        "lnk_kept": "  UNTOUCHED    {path} (a shortcut with this name opens another copy)",
        "registered": "Added to Windows Settings → Apps (uninstall from there or from the Start menu).",
        "no_webview": "Microsoft Edge WebView2 Runtime not found: the app opens in Edge instead of its own window. "
                      "To install it: {url}",
        "done_install": "Setup complete.",
        "sdk_hint": "When the game starts, confirm the “Advanced SDK features” prompt with OK.",
        "launching": "Starting the app…",
        "press_enter": "Press Enter to close.",
        "failed": "Stopped: {err}",
        "confirm_uninstall": "{product} will be removed completely: program, game plugins, shortcuts, settings and "
                             "maintenance records. Continue? {yn} ",
        "not_installed": "{product} does not seem to be installed in this folder: {path}",
        "removed": "  REMOVED      {path}",
        "restored": "  RESTORED     {path} (the telemetry plugin from before the installation)",
        "teyp_removed": "  DELETED      {path} (head unit mod)",
        "remove_failed": "  NOT REMOVED  {path}: {err}",
        "removed_shortcuts": "Shortcuts removed.", "unregistered": "Removed from the Apps list.",
        "folder_later": "The program folder will be deleted in a few seconds: {path}",
        "done_uninstall": "Uninstall complete.", "done_plugins": "Done.",
    },
    "de": {
        "product": "ETS2 Wartungssimulator", "folder": "ETS2 Wartung", "lnk_app": "ETS2 Wartung",
        "lnk_tek": "ETS2 Wartung - Einzelspieler", "lnk_cok": "ETS2 Wartung - Mehrspieler",
        "lnk_plugins": "Plugins installieren", "lnk_demo": "Demo (ohne Spiel testen)",
        "lnk_uninstall": "ETS2 Wartung deinstallieren",
        "yes": "j", "no": "n", "yn": "(J/N)",
        "h_install": "{product} {v} — Installation", "h_uninstall": "{product} — Deinstallation",
        "h_plugins": "{product} — Spiel-Plugins installieren", "target": "Installationsordner: {path}",
        "extract": "Programmdateien nicht gefunden. Zuerst das ganze Zip entpacken (Rechtsklick → Alle extrahieren), "
                   "dann INSTALL.bat ausführen.",
        "game_running": "Das Spiel läuft ({exe}): Plugin-Dateien können nicht ersetzt werden. Spiel schließen und Enter "
                        "drücken (A eingeben zum Abbrechen).",
        "game_running_quiet": "Das Spiel läuft ({exe}): zuerst schließen.",
        "app_closing": "ETS2 Wartung ist geöffnet; wird gespeichert und geschlossen…",
        "app_stuck": "ETS2 Wartung wurde nicht geschlossen. App schließen und Enter drücken (A eingeben zum Abbrechen).",
        "cancelled": "Abgebrochen; nichts wurde geändert.",
        "copying": "Programmdateien werden kopiert…", "copied": "Programm installiert: {path}",
        "game_found": "Spiel gefunden: {game}",
        "installed": "  INSTALLIERT  {path}",
        "updated": "  AKTUALISIERT {path}",
        "same_kept": "  UNVERÄNDERT  {path} (dasselbe Telemetrie-Plugin ist bereits installiert)",
        "backed_up": "  GESICHERT    {path} → {backup} (wird bei der Deinstallation zurückgelegt)",
        "sac_skip": "  ÜBERSPRUNGEN Spiel-Overlay: Intelligente App-Steuerung ist aktiv und die Overlay-DLL unsigniert, das "
                    "Spiel kann sie nicht laden. Simulator, App-Fenster und Warnungen funktionieren ohne Overlay.",
        "sac_removed": "  ENTFERNT     {path} (die App-Steuerung blockierte sie bei jedem Spielstart mit einer Meldung)",
        "copy_failed": "  FEHLER       {path}: {err}. Spiel schließen; sonst INSTALL.bat per Rechtsklick → Als Administrator "
                       "ausführen.",
        "no_game": "Spiel nicht gefunden (kein Euro Truck Simulator 2 / American Truck Simulator in den Steam-Bibliotheken). "
                   "Nach der Installation des Spiels: Startmenü → {folder} → „{lnk}“. Ohne Steam die zwei DLLs aus {src} "
                   "nach <Spielordner>\\bin\\win_x64\\plugins kopieren.",
        "no_source": "Plugin-Datei nicht gefunden: {path}",
        "shortcuts": "Verknüpfungen: Desktop und Startmenü → {folder}",
        "lnk_kept": "  UNVERÄNDERT  {path} (eine gleichnamige Verknüpfung öffnet eine andere Kopie)",
        "registered": "Zu Windows-Einstellungen → Apps hinzugefügt (dort oder im Startmenü deinstallieren).",
        "no_webview": "Microsoft Edge WebView2 Runtime nicht gefunden: Die App öffnet sich in Edge statt im eigenen Fenster. "
                      "Zum Installieren: {url}",
        "done_install": "Installation abgeschlossen.",
        "sdk_hint": "Beim Spielstart den Hinweis „Advanced SDK features“ mit OK bestätigen.",
        "launching": "App wird gestartet…",
        "press_enter": "Zum Schließen Enter drücken.",
        "failed": "Abgebrochen: {err}",
        "confirm_uninstall": "{product} wird vollständig entfernt: Programm, Spiel-Plugins, Verknüpfungen, Einstellungen "
                             "und Wartungsdaten. Fortfahren? {yn} ",
        "not_installed": "{product} scheint in diesem Ordner nicht installiert zu sein: {path}",
        "removed": "  ENTFERNT     {path}",
        "restored": "  ZURÜCKGELEGT {path} (das Telemetrie-Plugin von vor der Installation)",
        "teyp_removed": "  GELÖSCHT     {path} (Radio-Mod)",
        "remove_failed": "  NICHT ENTFERNT {path}: {err}",
        "removed_shortcuts": "Verknüpfungen entfernt.", "unregistered": "Aus der App-Liste entfernt.",
        "folder_later": "Der Programmordner wird in wenigen Sekunden gelöscht: {path}",
        "done_uninstall": "Deinstallation abgeschlossen.", "done_plugins": "Fertig.",
    },
}


def ui_language():
    """Windows arayüz dili: tr / de, diğer her dil en."""
    try:
        primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
    except (AttributeError, OSError):
        return "en"
    return {0x1F: "tr", 0x07: "de"}.get(primary, "en")


class Console:
    """İletiler ve sorular; quiet: soru sorulmaz (varsayılan yanıtla sürer)."""

    def __init__(self, lang="tr", quiet=False, echo=True):
        self.lang = lang if lang in TEXT else "en"
        self.quiet = quiet
        self.echo = echo                                               # False: yalnızca lines'a yaz (testler)
        self.lines = []

    def t(self, key, **kw):
        tx = TEXT[self.lang]
        params = dict(product=tx["product"], folder=tx["folder"], yn=tx["yn"])
        params.update(kw)
        return tx[key].format(**params)

    def say(self, key, **kw):
        line = self.t(key, **kw)
        self.lines.append(line)
        if not self.echo:
            return
        try:
            print(line, flush=True)
        except (OSError, ValueError):
            pass

    def ask_yes(self, key, **kw):
        if self.quiet:
            return True
        try:
            a = input(self.t(key, **kw)).strip().lower()
        except (EOFError, OSError):
            return False
        return a[:1] in ("e", "y", "j")

    def wait_enter(self, key, **kw):
        """Bekleme sorusu: True devam, False vazgeç."""
        if self.quiet:
            return False
        try:
            a = input(self.t(key, **kw) + " ").strip().lower()
        except (EOFError, OSError):
            return False
        return a[:1] not in ("v", "c", "a", "q")

    def pause(self):
        if self.quiet:
            return
        try:
            input(self.t("press_enter") + " ")
        except (EOFError, OSError):
            pass


class Abort(Exception):
    """Kullanıcı vazgeçti ya da devam edilemez (ileti zaten yazıldı)."""


# ---------------------------------------------------------------- Windows yardımcıları (ctypes; ek paket gerekmez)
def _k32():
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = ctypes.c_void_p
    k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    k.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    k.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p,
                                            ctypes.POINTER(ctypes.c_ulong)]
    k.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    k.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    return k


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong), ("th32ProcessID", ctypes.c_ulong),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", ctypes.c_ulong), ("cntThreads", ctypes.c_ulong),
                ("th32ParentProcessID", ctypes.c_ulong), ("pcPriClassBase", ctypes.c_long), ("dwFlags", ctypes.c_ulong),
                ("szExeFile", ctypes.c_wchar * 260)]


def processes():
    """Çalışan süreçler: [(pid, ad, tam yol ya da "")]."""
    out = []
    try:
        k = _k32()
        snap = k.CreateToolhelp32Snapshot(2, 0)                       # TH32CS_SNAPPROCESS
        if not snap or snap == ctypes.c_void_p(-1).value:
            return out
        try:
            e = _PROCESSENTRY32W()
            e.dwSize = ctypes.sizeof(e)
            ok = k.Process32FirstW(ctypes.c_void_p(snap), ctypes.byref(e))
            while ok:
                out.append((e.th32ProcessID, e.szExeFile, _exe_path(k, e.th32ProcessID)))
                ok = k.Process32NextW(ctypes.c_void_p(snap), ctypes.byref(e))
        finally:
            k.CloseHandle(snap)
    except (AttributeError, OSError):
        pass
    return out


def _exe_path(k, pid):
    h = k.OpenProcess(0x1000, 0, pid)                                 # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = ctypes.c_ulong(1024)
        return buf.value if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ""
    finally:
        k.CloseHandle(h)


def running_game():
    """Açık oyunun exe adı ya da None."""
    for _, name, _ in processes():
        if name.lower() in GAME_EXES:
            return name
    return None


def _inside(path, folder):
    try:
        return os.path.commonpath([os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(folder))]) \
            == os.path.normcase(os.path.abspath(folder))
    except ValueError:
        return False


def app_pids(install_dir):
    """Bu klasördeki Python'la çalışan süreçler (kurulu uygulama); kendimiz hariç."""
    py = os.path.join(install_dir, "python")
    return [pid for pid, _, exe in processes() if exe and pid != os.getpid() and _inside(exe, py)]


def _close_windows(pids):
    u = ctypes.windll.user32
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]

    def cb(hwnd, _):
        wp = ctypes.c_ulong()
        u.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(wp))
        if wp.value in pids and u.IsWindowVisible(ctypes.c_void_p(hwnd)):
            u.PostMessageW(hwnd, 0x0010, None, None)                 # WM_CLOSE: uygulama kaydedip kapanır
        return True

    u.EnumWindows(proc(cb), None)


def _wait_exit(pids, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        alive = [p for p in pids if _alive(p)]
        if not alive:
            return True
        time.sleep(0.2)
    return False


def _alive(pid):
    k = _k32()
    h = k.OpenProcess(0x00100000, 0, pid)                             # SYNCHRONIZE
    if not h:
        return False
    try:
        return k.WaitForSingleObject(h, 0) == 0x102                   # WAIT_TIMEOUT: hâlâ çalışıyor
    finally:
        k.CloseHandle(h)


def _terminate(pids):
    k = _k32()
    for pid in pids:
        h = k.OpenProcess(0x0001, 0, pid)                             # PROCESS_TERMINATE
        if h:
            k.TerminateProcess(h, 1)
            k.CloseHandle(h)


def known_folder(guid):
    """Windows bilinen klasörü (OneDrive'a taşınmış masaüstü dahil)."""
    try:
        p = ctypes.c_void_p()
        sh = ctypes.windll.shell32
        sh.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(appcontrol._GUID), ctypes.c_ulong, ctypes.c_void_p,
                                            ctypes.POINTER(ctypes.c_void_p)]
        if sh.SHGetKnownFolderPath(ctypes.byref(appcontrol._GUID.parse(guid)), 0, None, ctypes.byref(p)) != 0:
            return None
        try:
            return ctypes.wstring_at(p.value)
        finally:
            ctypes.windll.ole32.CoTaskMemFree(p)
    except (AttributeError, OSError, ValueError):
        return None


FOLDER_DESKTOP = "B4BFCC3A-DB2C-424C-B029-7FE99A87C641"
FOLDER_PROGRAMS = "A77F5D77-2E2B-44C3-A6A2-ABA601054A51"            # Başlat menüsü\Programlar (kullanıcı)
FOLDER_LOCALAPPDATA = "F1B32785-6FBA-4FCF-9D55-7B8E7F157091"


# ---- kısayol (.lnk): IShellLinkW + görev çubuğu kimliği (AppUserModelID) + IPersistFile
_CLSID_SHELL_LINK = "00021401-0000-0000-C000-000000000046"
_IID_SHELL_LINK = "000214F9-0000-0000-C000-000000000046"
_IID_PERSIST_FILE = "0000010B-0000-0000-C000-000000000046"
_IID_PROPERTY_STORE = "886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"
_PKEY_AUMID = ("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3", 5)


class _PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", appcontrol._GUID), ("pid", ctypes.c_ulong)]


class _PROPVARIANT(ctypes.Structure):
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort),
                ("ptr", ctypes.c_void_p), ("pad", ctypes.c_void_p)]  # x64: 24 bayt


def _vcall(obj, index, restype, argtypes, *args):
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtbl[index])(obj, *args)


def _qi(obj, iid):
    out = ctypes.c_void_p()
    _vcall(obj, 0, ctypes.HRESULT, [ctypes.POINTER(appcontrol._GUID), ctypes.POINTER(ctypes.c_void_p)],
           ctypes.byref(appcontrol._GUID.parse(iid)), ctypes.byref(out))
    return out


def _release(obj):
    if obj:
        _vcall(obj, 2, ctypes.c_ulong, [])


class _Com:
    def __enter__(self):
        ole = ctypes.windll.ole32
        ole.CoInitializeEx.restype = ctypes.c_long
        self.init = ole.CoInitializeEx(None, 2) in (0, 1)              # S_OK / S_FALSE: bu iş parçacığında açıldı
        return self

    def __exit__(self, *exc):
        if self.init:
            ctypes.windll.ole32.CoUninitialize()


def _shell_link():
    ole = ctypes.windll.ole32
    ole.CoCreateInstance.argtypes = [ctypes.POINTER(appcontrol._GUID), ctypes.c_void_p, ctypes.c_ulong,
                                     ctypes.POINTER(appcontrol._GUID), ctypes.POINTER(ctypes.c_void_p)]
    ole.CoCreateInstance.restype = ctypes.HRESULT
    link = ctypes.c_void_p()
    ole.CoCreateInstance(ctypes.byref(appcontrol._GUID.parse(_CLSID_SHELL_LINK)), None, 1,
                         ctypes.byref(appcontrol._GUID.parse(_IID_SHELL_LINK)), ctypes.byref(link))
    return link


def create_shortcut(path, target, args="", workdir="", icon="", desc="", app_id=""):
    """Kısayol oluşturur (varsa üzerine yazar). app_id: pencerenin görev çubuğu kimliğiyle aynı olmalı ki sabitlenen
    kısayol ve açık pencere tek simgede birleşsin."""
    W, H = ctypes.c_wchar_p, ctypes.HRESULT
    with _Com():
        link = _shell_link()
        store = pf = None
        try:
            _vcall(link, 20, H, [W], target)                          # SetPath
            _vcall(link, 11, H, [W], args)                            # SetArguments
            _vcall(link, 9, H, [W], workdir)                          # SetWorkingDirectory
            _vcall(link, 7, H, [W], desc[:259])                       # SetDescription
            if icon:
                _vcall(link, 17, H, [W, ctypes.c_int], icon, 0)       # SetIconLocation
            if app_id:
                store = _qi(link, _IID_PROPERTY_STORE)
                key = _PROPERTYKEY(appcontrol._GUID.parse(_PKEY_AUMID[0]), _PKEY_AUMID[1])
                buf = ctypes.create_unicode_buffer(app_id)
                pv = _PROPVARIANT(31, 0, 0, 0, ctypes.cast(buf, ctypes.c_void_p), None)   # VT_LPWSTR
                _vcall(store, 6, H, [ctypes.POINTER(_PROPERTYKEY), ctypes.POINTER(_PROPVARIANT)],
                       ctypes.byref(key), ctypes.byref(pv))            # SetValue
                _vcall(store, 7, H, [])                                # Commit
            pf = _qi(link, _IID_PERSIST_FILE)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            _vcall(pf, 6, H, [W, ctypes.c_int], path, 1)              # Save
        finally:
            _release(pf)
            _release(store)
            _release(link)


def read_shortcut(path):
    """Kısayolun hedefi, bağımsız değişkenleri ve görev çubuğu kimliği (doğrulama ve testler için)."""
    W, H = ctypes.c_wchar_p, ctypes.HRESULT
    with _Com():
        link = _shell_link()
        store = pf = None
        try:
            pf = _qi(link, _IID_PERSIST_FILE)
            _vcall(pf, 5, H, [W, ctypes.c_ulong], path, 0)            # Load
            target = ctypes.create_unicode_buffer(1024)
            _vcall(link, 3, H, [W, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong], target, 1024, None, 0x4)  # GetPath (RAWPATH)
            args = ctypes.create_unicode_buffer(1024)
            _vcall(link, 10, H, [W, ctypes.c_int], args, 1024)        # GetArguments
            store = _qi(link, _IID_PROPERTY_STORE)
            key = _PROPERTYKEY(appcontrol._GUID.parse(_PKEY_AUMID[0]), _PKEY_AUMID[1])
            pv = _PROPVARIANT()
            _vcall(store, 5, H, [ctypes.POINTER(_PROPERTYKEY), ctypes.POINTER(_PROPVARIANT)],
                   ctypes.byref(key), ctypes.byref(pv))                # GetValue
            app_id = ctypes.wstring_at(pv.ptr) if pv.vt == 31 and pv.ptr else ""
            ctypes.windll.ole32.PropVariantClear(ctypes.byref(pv))
            return {"target": target.value, "args": args.value, "app_id": app_id}
        finally:
            _release(pf)
            _release(store)
            _release(link)


# ---- Uygulamalar listesi (HKCU, yönetici izni gerekmez)
def register(key, values):
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_WRITE) as k:
        for name, v in values.items():
            if isinstance(v, int):
                winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, v)
            else:
                winreg.SetValueEx(k, name, 0, winreg.REG_SZ, str(v))


def unregister(key):
    import winreg
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
        return True
    except OSError:
        return False


def webview2_installed():
    import winreg
    for root, sub in ((winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_ID}"),
                      (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_ID}"),
                      (winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_ID}")):
        try:
            with winreg.OpenKey(root, sub) as k:
                pv = winreg.QueryValueEx(k, "pv")[0]
            if pv and pv != "0.0.0.0":
                return True
        except OSError:
            continue
    return False


# ---------------------------------------------------------------- yollar (testlerde geçici klasörlere yönlendirilir)
class Paths:
    def __init__(self, install_dir=None, desktop=None, start_menu=None, prefs_dir=None, games=None,
                 registry_key=UNINSTALL_KEY):
        local = known_folder(FOLDER_LOCALAPPDATA) or os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
        self.install = os.path.abspath(install_dir or os.path.join(local, "Programs", DIR_NAME))
        self.desktop = os.path.abspath(desktop or known_folder(FOLDER_DESKTOP) or os.path.join(os.path.expanduser("~"), "Desktop"))
        self.start_menu = os.path.abspath(start_menu or known_folder(FOLDER_PROGRAMS) or os.path.join(
            os.environ.get("APPDATA", local), r"Microsoft\Windows\Start Menu\Programs"))
        self.prefs = os.path.abspath(prefs_dir or os.path.join(local, "ETS2Bakim"))   # oyun içi katmanın overlay.ini'si
        self._games = [os.path.normpath(g) for g in games] if games is not None else None
        self.registry_key = registry_key

    def games(self):
        """ETS2 / ATS bin\\win_x64 klasörleri."""
        return list(self._games) if self._games is not None else appcontrol.steam_game_dirs()

    @property
    def python(self):
        return os.path.join(self.install, "python", "python.exe")

    @property
    def pythonw(self):
        return os.path.join(self.install, "python", "pythonw.exe")


def load_manifest(install_dir):
    try:
        with open(os.path.join(install_dir, MANIFEST), encoding="utf-8") as fh:
            m = json.load(fh)
        return m if isinstance(m, dict) else {}
    except (OSError, ValueError):
        return {}


def save_manifest(install_dir, m):
    os.makedirs(install_dir, exist_ok=True)
    tmp = os.path.join(install_dir, MANIFEST + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(install_dir, MANIFEST))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_file(src, dst):
    """Yalnızca içeriği kopyalar: alternatif veri akışları (zip'ten gelen Zone.Identifier) taşınmaz."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".kurulum-tmp"
    with open(src, "rb") as a, open(tmp, "wb") as b:
        shutil.copyfileobj(a, b, 1 << 20)
    os.replace(tmp, dst)


def _copy_tree(src, dst):
    n = 0
    for base, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        rel = os.path.relpath(base, src)
        for f in files:
            if f.endswith((".pyc", ".kurulum-tmp")):
                continue
            _copy_file(os.path.join(base, f), os.path.normpath(os.path.join(dst, rel, f)))
            n += 1
    return n


def _rmtree(path):
    """Klasörü siler; virüs tarayıcısı bir dosyayı kısa süre açık tutuyorsa birkaç kez yeniden dener."""
    for attempt in range(5):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt == 4:
                raise
            time.sleep(0.5)


def _game_name(bin_dir):
    return os.path.basename(os.path.dirname(os.path.dirname(bin_dir)))


# ---------------------------------------------------------------- oyun eklentileri
def install_plugins(paths, src_dir, manifest, con):
    """Telemetri eklentisini ve oyun içi katmanı bulunan her oyuna kurar; yapılanları manifest["plugins"]'e yazar.
    Dönüş: kurulan oyun sayısı (oyun bulunamadıysa 0)."""
    plugins = {p["path"].lower(): p for p in manifest.get("plugins", [])}
    tel_src = os.path.join(src_dir, TELEMETRY_DLL)
    ovl_src = os.path.join(src_dir, OVERLAY_DLL)
    sac_on = appcontrol.sac_state() == "on"
    ovl_blocked = sac_on and os.path.isfile(ovl_src) and appcontrol.signature_status(ovl_src) != "valid"
    games = paths.games()
    if not games:
        con.say("no_game", lnk=TEXT[con.lang]["lnk_plugins"], src=src_dir)
        return 0
    for src in (tel_src, ovl_src):
        if not os.path.isfile(src):
            con.say("no_source", path=src)
    tel_hash = _sha256(tel_src) if os.path.isfile(tel_src) else None
    for bin_dir in games:
        con.say("game_found", game=_game_name(bin_dir))
        plug = os.path.join(bin_dir, "plugins")
        # telemetri eklentisi (RenCloud scs-sdk-plugin)
        dst = os.path.join(plug, TELEMETRY_DLL)
        rec = plugins.get(dst.lower())
        try:
            if tel_hash is None:
                pass
            elif not os.path.isfile(dst):
                _copy_file(tel_src, dst)
                plugins[dst.lower()] = {"path": dst, "ours": True, "backup": (rec or {}).get("backup")}
                con.say("installed", path=dst)
            elif rec and rec.get("ours"):
                if _sha256(dst) != tel_hash:
                    _copy_file(tel_src, dst)
                    con.say("updated", path=dst)
                else:
                    con.say("same_kept", path=dst)
            elif _sha256(dst) == tel_hash:
                plugins[dst.lower()] = {"path": dst, "ours": False, "backup": None}   # başkasının da olabilir: dokunma
                con.say("same_kept", path=dst)
            else:
                backup = dst + BACKUP_SUFFIX
                if not os.path.exists(backup):
                    os.replace(dst, backup)
                _copy_file(tel_src, dst)
                plugins[dst.lower()] = {"path": dst, "ours": True, "backup": backup}
                con.say("backed_up", path=dst, backup=os.path.basename(backup))
        except OSError as ex:
            con.say("copy_failed", path=dst, err=ex.strerror or ex)
        # oyun içi katman (imzasızsa Akıllı Uygulama Denetimi açıkken kurulmaz)
        dst = os.path.join(plug, OVERLAY_DLL)
        try:
            if not os.path.isfile(ovl_src):
                pass
            elif ovl_blocked:
                con.say("sac_skip")
                if os.path.isfile(dst) and appcontrol.signature_status(dst) != "valid":
                    os.remove(dst)
                    plugins.pop(dst.lower(), None)
                    con.say("sac_removed", path=dst)
            else:
                existed = os.path.isfile(dst)
                _copy_file(ovl_src, dst)
                plugins[dst.lower()] = {"path": dst, "ours": True, "backup": None}
                con.say("updated" if existed else "installed", path=dst)
        except OSError as ex:
            con.say("copy_failed", path=dst, err=ex.strerror or ex)
    manifest["plugins"] = sorted(plugins.values(), key=lambda p: p["path"].lower())
    return len(games)


def remove_plugins(paths, manifest, con):
    """Kurulumun koyduğu eklentileri siler, yedeklenmiş telemetri eklentisini geri koyar. Kayıtta olmasa da oyun
    klasörlerindeki ets2bakim_overlay.dll (adı yalnızca bize ait) silinir."""
    recs = list(manifest.get("plugins", []))
    known = {r["path"].lower() for r in recs}
    for bin_dir in paths.games():
        p = os.path.join(bin_dir, "plugins", OVERLAY_DLL)
        if p.lower() not in known and os.path.isfile(p):
            recs.append({"path": p, "ours": True, "backup": None})
    ok = True
    for r in recs:
        path, backup = r["path"], r.get("backup")
        if not r.get("ours"):
            continue
        try:
            if os.path.isfile(path):
                os.remove(path)
                con.say("removed", path=path)
            if backup and os.path.isfile(backup):
                os.replace(backup, path)
                con.say("restored", path=path)
        except OSError as ex:
            ok = False
            con.say("remove_failed", path=path, err=ex.strerror or ex)
    return ok


# ---------------------------------------------------------------- kurulum
def remove_teyp_mod(manifest, con):
    """1.3.0 denemelerinin kurduğu teyp modunu siler; kullanıcı dosyayı değiştirdiyse (özet farklı) dokunmaz."""
    m = manifest.get("teyp_mod") or {}
    path = m.get("path")
    try:
        if path and os.path.isfile(path) and _sha256(path) == m.get("sha256"):
            os.remove(path)
            con.say("teyp_removed", path=path)
    except OSError as ex:
        con.say("remove_failed", path=path, err=ex.strerror or ex)


def _program_files(src):
    """Kurulacak öğeler: kaynaktaki her şey (kullanıcı verisi ve kurulum kaydı hariç)."""
    skip = set(DATA_DIRS) | {MANIFEST, "__pycache__", "port.txt"}
    return [n for n in os.listdir(src) if n not in skip]


def _ensure_closed(paths, con, need_game_closed=True):
    while need_game_closed:
        exe = running_game()
        if not exe:
            break
        if con.quiet:
            con.say("game_running_quiet", exe=exe)
            raise Abort()
        if not con.wait_enter("game_running", exe=exe):
            con.say("cancelled")
            raise Abort()
    pids = app_pids(paths.install)
    if pids:
        con.say("app_closing")
        _close_windows(set(pids))
        if not _wait_exit(pids, 15):
            while True:
                if con.quiet:
                    _terminate(pids)
                    _wait_exit(pids, 5)
                    break
                if not con.wait_enter("app_stuck"):
                    con.say("cancelled")
                    raise Abort()
                pids = app_pids(paths.install)
                if not pids:
                    break


def _first_language(install_dir, lang):
    """İlk kurulumda uygulamanın dili Windows'un dili olsun (Tek ve Çok Oyunculu modun; ayar dosyası varsa dokunulmaz)."""
    for d in ("data", "data_mp"):
        f = os.path.join(install_dir, d, "ayarlar.json")
        if not os.path.exists(f):
            os.makedirs(os.path.dirname(f), exist_ok=True)
            with open(f, "w", encoding="utf-8") as fh:
                json.dump({"language": lang}, fh, ensure_ascii=False, indent=1)


def _shortcut_specs(paths, tx):
    pw, py, inst = paths.pythonw, paths.python, paths.install
    icon = os.path.join(inst, "ets2bakim", "app.ico")
    menu = os.path.join(paths.start_menu, tx["folder"])
    app = dict(target=pw, args="-m ets2bakim", workdir=inst, icon=icon, desc=tx["product"], app_id=window.APP_ID)
    return [
        (os.path.join(paths.desktop, tx["lnk_app"] + ".lnk"), app),
        (os.path.join(menu, tx["lnk_app"] + ".lnk"), app),
        (os.path.join(menu, tx["lnk_plugins"] + ".lnk"),
         dict(target=py, args="-X utf8 -m ets2bakim.kurulum eklenti", workdir=inst, icon=icon, desc=tx["lnk_plugins"])),
        (os.path.join(menu, tx["lnk_demo"] + ".lnk"),
         dict(target=pw, args="-m ets2bakim --demo --hiz 4", workdir=inst, icon=icon, desc=tx["lnk_demo"])),
        (os.path.join(menu, tx["lnk_uninstall"] + ".lnk"),
         dict(target=py, args="-X utf8 -m ets2bakim.kurulum kaldir", workdir=inst, icon=icon, desc=tx["lnk_uninstall"])),
    ]


def _legacy_shortcuts(paths, menus):
    """1.1'in iki ayrı uygulamasının (Tek / Çok Oyunculu) her dildeki kısayol yolları: masaüstü ve Başlat menüsü."""
    out = []
    for tx in TEXT.values():
        for m in LEGACY_MODES:
            out += [os.path.join(d, tx["lnk_" + m] + ".lnk") for d in [paths.desktop] + [x for x in menus if x]]
    return out


def _dir_size_kb(path):
    total = 0
    for base, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(base, f))
            except OSError:
                pass
    return total // 1024


def install(paths, con, src=ROOT, launch=True):
    con.say("h_install", v=__version__)
    if not os.path.isfile(os.path.join(src, "python", "python.exe")) and os.path.normcase(src) != os.path.normcase(paths.install):
        con.say("extract")
        raise Abort()
    con.say("target", path=paths.install)
    _ensure_closed(paths, con)
    manifest = load_manifest(paths.install)
    # 1) program (güncellemede eski program klasörleri silinip yenisi kopyalanır; kullanıcı verisi korunur)
    if os.path.normcase(os.path.abspath(src)) != os.path.normcase(paths.install):
        con.say("copying")
        for name in _program_files(src):
            old = os.path.join(paths.install, name)
            if name in REPLACE_DIRS and os.path.isdir(old):
                _rmtree(old)
            s = os.path.join(src, name)
            if os.path.isdir(s):
                _copy_tree(s, old)
            else:
                _copy_file(s, old)
        for name in REMOVED_DIRS:
            if os.path.isdir(os.path.join(paths.install, name)):
                _rmtree(os.path.join(paths.install, name))
        con.say("copied", path=paths.install)
    _first_language(paths.install, con.lang)
    # 2) oyun eklentileri
    install_plugins(paths, os.path.join(paths.install, "eklenti"), manifest, con)
    # 3) kısayollar (1.1'in Tek / Çok Oyunculu kısayolları kaldırılır: mod artık uygulamanın içinde seçilir)
    shortcuts = list(manifest.get("shortcuts", []))
    names = TEXT[manifest.get("lang") if manifest.get("lang") in TEXT else con.lang]   # ilk kurulumun dili: tek Başlat klasörü
    menus = [manifest.get("start_menu"), os.path.join(paths.start_menu, names["folder"])]
    for lnk in _legacy_shortcuts(paths, menus):
        if os.path.isfile(lnk) and (lnk in shortcuts or _points_into(lnk, paths.install)):
            try:
                os.remove(lnk)
                con.say("removed", path=lnk)
            except OSError as ex:
                con.say("remove_failed", path=lnk, err=ex.strerror or ex)
        if lnk in shortcuts and not os.path.isfile(lnk):
            shortcuts.remove(lnk)
    for lnk, spec in _shortcut_specs(paths, names):
        if os.path.isfile(lnk) and lnk not in shortcuts and not _points_into(lnk, paths.install):
            con.say("lnk_kept", path=lnk)                              # ör. geliştirme klasörünü açan aynı adlı kısayol
            continue
        create_shortcut(lnk, **spec)
        if lnk not in shortcuts:
            shortcuts.append(lnk)
    con.say("shortcuts", folder=names["folder"])
    # 4) Ayarlar → Uygulamalar kaydı
    register(paths.registry_key, {
        "DisplayName": names["product"], "DisplayVersion": __version__, "Publisher": "ETS2 Bakım",
        "DisplayIcon": os.path.join(paths.install, "ets2bakim", "app.ico"), "InstallLocation": paths.install,
        "UninstallString": f'"{paths.python}" -X utf8 -m ets2bakim.kurulum kaldir',
        "QuietUninstallString": f'"{paths.python}" -X utf8 -m ets2bakim.kurulum kaldir --sessiz',
        "NoModify": 1, "NoRepair": 1, "EstimatedSize": _dir_size_kb(paths.install),
        "InstallDate": time.strftime("%Y%m%d"),
    })
    con.say("registered")
    manifest.pop("modes", None)                                        # 1.1: kurulan uygulamalar (tek / cok)
    manifest.update(version=__version__, shortcuts=shortcuts, registry_key=paths.registry_key,
                    lang=manifest.get("lang") if manifest.get("lang") in TEXT else con.lang,
                    start_menu=os.path.join(paths.start_menu, names["folder"]), installed=time.strftime("%Y-%m-%d %H:%M"))
    save_manifest(paths.install, manifest)
    if not webview2_installed():
        con.say("no_webview", url=WEBVIEW2_URL)
    con.say("done_install")
    con.say("sdk_hint")
    if launch:
        con.say("launching")
        subprocess.Popen([paths.pythonw, "-m", "ets2bakim"], cwd=paths.install,
                         creationflags=0x00000008 | 0x00000200)        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    return manifest


def plugins_only(paths, con):
    """Yalnızca oyun eklentilerini kurar / onarır (oyun sonradan kurulduysa, yeniden kurulduysa)."""
    con.say("h_plugins")
    _ensure_closed(paths, con)
    manifest = load_manifest(paths.install)
    src = os.path.join(paths.install, "eklenti")
    if not os.path.isdir(src):
        src = os.path.join(ROOT, "eklenti")
    install_plugins(paths, src, manifest, con)
    if manifest.get("version"):
        save_manifest(paths.install, manifest)
    con.say("done_plugins")
    con.say("sdk_hint")


# ---------------------------------------------------------------- kaldırma
def _delete_later(folder):
    """Klasörü bu süreç bittikten sonra siler (çalışan python.exe kendi klasörünü silemez)."""
    loop = (f'for /l %i in (1,1,40) do @(if exist "{folder}" (rd /s /q "{folder}" 2>nul & '
            f'ping -n 2 127.0.0.1 >nul))')
    subprocess.Popen(f'cmd.exe /d /s /c "{loop}"', cwd=tempfile.gettempdir(),
                     creationflags=0x08000000 | 0x00000200)              # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP


def uninstall(paths, con, delete_folder=True):
    con.say("h_uninstall")
    manifest = load_manifest(paths.install)
    if not manifest and not os.path.isdir(os.path.join(paths.install, "ets2bakim")):
        con.say("not_installed", path=paths.install)
        raise Abort()
    if not con.ask_yes("confirm_uninstall"):
        con.say("cancelled")
        raise Abort()
    try:
        os.chdir(tempfile.gettempdir())                               # klasör çalışma dizini olarak kilitli kalmasın
    except OSError:
        pass
    _ensure_closed(paths, con)
    remove_plugins(paths, manifest, con)
    remove_teyp_mod(manifest, con)
    # kısayollar (kayıttakiler + uygulamanın ve 1.1'in iki uygulamasının her dildeki olası adları) ve Başlat menüsü klasörü
    menus = {manifest.get("start_menu")} | {os.path.join(paths.start_menu, tx["folder"]) for tx in TEXT.values()}
    lnks = set(manifest.get("shortcuts", [])) | set(_legacy_shortcuts(paths, menus))
    lnks |= {os.path.join(paths.desktop, tx["lnk_app"] + ".lnk") for tx in TEXT.values()}
    for lnk in sorted(lnks):
        if os.path.isfile(lnk) and (lnk in manifest.get("shortcuts", []) or _points_into(lnk, paths.install)):
            try:
                os.remove(lnk)
            except OSError as ex:
                con.say("remove_failed", path=lnk, err=ex.strerror or ex)
    for menu in menus:
        if menu and os.path.isdir(menu) and all(_points_into(os.path.join(menu, f), paths.install)
                                                 for f in os.listdir(menu) if f.lower().endswith(".lnk")):
            shutil.rmtree(menu, ignore_errors=True)
    con.say("removed_shortcuts")
    if unregister(manifest.get("registry_key") or paths.registry_key):
        con.say("unregistered")
    shutil.rmtree(paths.prefs, ignore_errors=True)                    # oyun içi katmanın ayarları (overlay.ini)
    if delete_folder:
        con.say("folder_later", path=paths.install)
    con.say("done_uninstall")


def _points_into(lnk, folder):
    try:
        return _inside(read_shortcut(lnk)["target"], folder)
    except OSError:
        return False


# ---------------------------------------------------------------- komut satırı
def main(argv=None):
    p = argparse.ArgumentParser(prog="ets2bakim.kurulum")
    p.add_argument("islem", choices=("kur", "kaldir", "eklenti"))
    p.add_argument("--mod", help=argparse.SUPPRESS)                     # 1.1'in KUR.bat'ı (tek / cok): yok sayılır
    p.add_argument("--dil", choices=tuple(TEXT), default=None)
    p.add_argument("--sessiz", action="store_true", help="soru sorma (kaldırmada onay da istenmez)")
    p.add_argument("--acma", action="store_true", help="kurulumdan sonra uygulamayı açma")
    # testler ve özel durumlar için yol yönlendirmeleri
    p.add_argument("--hedef")
    p.add_argument("--masaustu")
    p.add_argument("--baslat")
    p.add_argument("--katman-ayar")
    p.add_argument("--oyun", action="append")
    p.add_argument("--kayit", default=UNINSTALL_KEY)
    a = p.parse_args(argv)
    if a.islem != "kur" and not a.hedef and os.path.isfile(os.path.join(ROOT, MANIFEST)):
        a.hedef = ROOT                                                 # kurulu kopyadan çalışıyor
    paths = Paths(a.hedef, a.masaustu, a.baslat, a.katman_ayar, a.oyun if a.oyun else None, a.kayit)
    con = Console(a.dil or ui_language(), a.sessiz)
    code, removed = 0, False
    try:
        if a.islem == "kur":
            install(paths, con, launch=not a.acma)
        elif a.islem == "eklenti":
            plugins_only(paths, con)
        else:
            uninstall(paths, con)
            removed = True
    except Abort:
        code = 1
    except Exception as ex:  # beklenmeyen hata: pencere hemen kapanmasın, ne olduğu görünsün
        con.say("failed", err=f"{type(ex).__name__}: {ex}")
        code = 2
    con.pause()
    if removed:
        _delete_later(paths.install)                                  # kullanıcı Enter'a bastıktan sonra: bu süreç biter bitmez
    return code


if __name__ == "__main__":
    sys.exit(main())
