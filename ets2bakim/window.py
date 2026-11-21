"""Masaüstü uygulama penceresi.

Arayüz, Windows'un yerleşik WebView2 bileşeniyle (Edge motoru) kendi penceresinde açılır: tarayıcı, adres
çubuğu ya da konsol penceresi yoktur. Pencere kapanınca uygulama kaydedip kapanır. WebView2 ya da pywebview
yoksa eski yönteme (Edge/Chrome uygulama penceresi) dönülür.
"""
import ctypes
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
MODES = ("tek", "cok")
MODE_NAMES = {"tek": "Tek Oyunculu", "cok": "Çok Oyunculu"}
ICON = os.path.join(_HERE, "app.ico")
ICONS = {"tek": ICON, "cok": os.path.join(_HERE, "app_mp.ico")}   # app_mp.ico: tanıtım görselleri
APP_ID = "ETS2Bakim"   # görev çubuğu kimliği; kurulum kısayola da aynısını yazar (pencere kısayolla gruplanır)


def icon(mode="tek"):
    p = ICONS.get(mode, ICON)
    return p if os.path.isfile(p) else ICON


def _tr(s, lang):
    from .i18n import TRANS
    e = TRANS.get(s) if lang != "tr" else None
    return e[0 if lang == "en" else 1] if e else s


def title(demo=False, lang=None):
    """Pencere başlığı seçili dilde (lang verilmezse şu anki dil). Oyun modu başlıkta değil, arayüzün üst çubuğunda
    görünür: başlık sabit kalır (ör. OBS pencere yakalaması mod değişince kopmasın)."""
    from . import i18n
    lg = lang or i18n.LANG
    t = _tr("ETS2 Bakım Simülatörü", lg)
    return t + " (Demo)" if demo else t


def _all_titles():
    """Açık pencereyi bulmak için başlığın her dildeki hâli (dil sonradan değiştirilmiş olabilir); 1.1 ve öncesinin
    iki ayrı uygulamasının başlıkları da ("ETS2 Bakım – Tek Oyunculu" …) tanınır."""
    from .i18n import LANGS
    titles = {title(d, lg) for d in (False, True) for lg in LANGS}
    for lg in LANGS:
        for m in MODES:
            old = f"{_tr('ETS2 Bakım', lg)} – {_tr(MODE_NAMES[m], lg)}"
            titles |= {old, old + " (Demo)"}
    return titles


_win = None


def retitle(new_title):
    """Dil değişince açık pencerenin başlığını günceller."""
    try:
        if _win is not None:
            _win.set_title(new_title)
    except Exception:
        pass


def available():
    if sys.platform != "win32":
        return False
    try:
        import webview  # noqa: F401
        return True
    except Exception:
        return False


def _dark_mode():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def _visible_windows(titles, pid=None):
    """Başlığı eşleşen görünür üst düzey pencereler (WebView2 aynı başlıkla gizli yardımcı pencere de açar)."""
    u = ctypes.windll.user32
    found = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(hwnd, _):
        if u.IsWindowVisible(hwnd):
            n = u.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value in titles:
                if pid is not None:
                    wp = ctypes.c_ulong()
                    u.GetWindowThreadProcessId(hwnd, ctypes.byref(wp))
                    if wp.value != pid:
                        return True
                found.append(hwnd)
        return True

    u.EnumWindows(proc(cb), None)
    return found


def _set_icon(win_title):
    """Pencere ve görev çubuğu simgesi (pythonw.exe simgesi yerine)."""
    try:
        u = ctypes.windll.user32
        wins = _visible_windows({win_title}, os.getpid())
        hwnd = wins[0] if wins else None
        ico = icon()
        if not hwnd or not os.path.isfile(ico):
            return
        LR_LOADFROMFILE, IMAGE_ICON, WM_SETICON = 0x10, 1, 0x80
        u.LoadImageW.restype = ctypes.c_void_p
        u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        big = u.LoadImageW(None, ico, IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
        small = u.LoadImageW(None, ico, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        if big:
            u.SendMessageW(hwnd, WM_SETICON, 1, big)
        if small:
            u.SendMessageW(hwnd, WM_SETICON, 0, small)
    except Exception:
        pass


def run(url, win_title, storage_dir, on_closed=None):
    """Pencereyi açar ve kapanana kadar bekler (ana iş parçacığında çağrılmalı).

    on_closed: pencere kapanır kapanmaz çağrılır. Pencere motorunun (WebView2/.NET) kontrolü geri vermesi
    pencere kaybolduktan sonra 1-2 saniye sürebildiği için kapanış işi beklemeden burada yapılır."""
    import webview
    try:  # görev çubuğunda pythonw.exe yerine uygulamanın kendi grubu (kısayolla aynı kimlik)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass
    dark = _dark_mode()
    global _win
    win = webview.create_window(win_title, url, width=1500, height=950, min_size=(980, 640),
                                background_color="#131417" if dark else "#f9f9f7", text_select=True)
    _win = win
    win.events.shown += lambda: _set_icon(win_title)
    if on_closed:
        win.events.closed += on_closed
    os.makedirs(storage_dir, exist_ok=True)
    # private_mode=False: tema gibi arayüz tercihleri (localStorage) oturumlar arasında saklanır
    webview.start(gui="edgechromium", private_mode=False, storage_path=storage_dir)


# ---------------------------------------------------------------- tek kopya
_mutex = None


def find_window():
    try:
        wins = _visible_windows(_all_titles())
        return wins[0] if wins else 0
    except Exception:
        return 0


def single_instance():
    """Simülatör zaten açıksa onun penceresini öne getirir ve False döner.

    Uygulama (ve demo) bir kez açılabilir: hepsi aynı telemetriyi okur ve oyun içi katmanın paylaşılan belleğine yazar.
    Tek / Çok Oyunculu mod artık aynı uygulamanın içinde seçilir.
    """
    global _mutex
    if sys.platform != "win32":
        return True
    k = ctypes.windll.kernel32
    k.CreateMutexW.restype = ctypes.c_void_p
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    _mutex = k.CreateMutexW(None, False, "Local\\ETS2BakimApp")
    if k.GetLastError() != 183:  # ERROR_ALREADY_EXISTS
        return True
    hwnd = find_window()
    # Penceresi yok ama süreç hâlâ var: büyük ihtimalle az önce kapatıldı ve çıkıyor; birkaç saniye bekle
    for _ in range(30):
        if hwnd:
            break
        k.CloseHandle(_mutex)
        import time
        time.sleep(0.1)
        _mutex = k.CreateMutexW(None, False, "Local\\ETS2BakimApp")
        if k.GetLastError() != 183:
            return True
        hwnd = find_window()
    if hwnd:
        u = ctypes.windll.user32
        u.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        u.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        if u.IsIconic(ctypes.c_void_p(hwnd)):
            u.ShowWindow(hwnd, 9)  # SW_RESTORE
        u.SetForegroundWindow(hwnd)
    return False
