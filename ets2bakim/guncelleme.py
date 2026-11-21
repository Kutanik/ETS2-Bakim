"""Uygulama içi güncelleme: Drive'daki surum.json'a bakar; yeni sürüm varsa zip'i indirir, SHA-256 özetini doğrular,
açar ve içindeki kurulumu sessiz çalıştırır. Kurulum açık uygulamayı kaydedip kapatır, programı günceller (kullanıcı
verisi korunur) ve uygulamayı yeniden açar. Yalnızca dağıtım paketinden kurulu kopyada çalışır. İndirilen zip ve
açılmış paket, kurulumdan sonraki açılışın 2. dakikasında silinir (kurulum.log kalır).

surum.json (Drive'da "bağlantıya sahip olan herkes görüntüleyebilir"; paketle.py dagitim\\ klasörüne yazar, her sürümde
zip ile birlikte Drive'da "Sürümleri yönet"le değiştirilir, böylece iki bağlantı da aynı kalır):
    {"surum": "1.3.0", "zip": "<indirme adresi>", "sha256": "<zip'in özeti>", "boyut": 13452727,
     "notlar": {"tr": "...", "en": "...", "de": "..."}}
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import urllib.request
import zipfile

from . import __version__

DRIVE_DOWNLOAD = "https://drive.usercontent.google.com/download?id={id}&export=download&confirm=t"
INFO_ID = "1NCPerDRNXRxmR-jJqSolyVX8tjrbzNzK"      # Drive: surum.json
ZIP_ID = "1me1YT22vMsmQCI2D-8mkPm8qt-e54IJf"       # Drive: dağıtım zip'i (paketle.py surum.json'a yazar)
INFO_URL = DRIVE_DOWNLOAD.format(id=INFO_ID)
WORK_DIR = os.path.join(tempfile.gettempdir(), "ETS2Bakim-guncelleme")
TIMEOUT_S = 15


class UpdateError(Exception):
    """Arayüzde çevrilen hata kodu: info (surum.json okunamadı), sha (özet tutmadı), program (zip içeriği eksik)."""


def parse_version(v):
    """'1.3.0' → (1, 3, 0, 0); geçersizse None."""
    try:
        parts = tuple(int(p) for p in str(v).strip().split("."))
    except ValueError:
        return None
    return parts + (0,) * (4 - len(parts)) if 1 <= len(parts) <= 4 else None


def is_newer(latest, current=__version__):
    a, b = parse_version(latest), parse_version(current)
    return a is not None and b is not None and a > b


def _open(url, timeout=TIMEOUT_S):
    req = urllib.request.Request(url, headers={"User-Agent": f"ETS2Bakim/{__version__}"})
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_info(url=INFO_URL):
    """surum.json'u okuyup denetler; Drive dosya yerine bir sayfa döndürürse (paylaşım kapalı, kota) UpdateError."""
    with _open(url) as r:
        raw = r.read(1 << 16)
    try:
        info = json.loads(raw.decode("utf-8-sig"))
    except ValueError:                                                  # UnicodeDecodeError, JSONDecodeError
        raise UpdateError("info") from None
    if (not isinstance(info, dict) or parse_version(info.get("surum")) is None
            or not str(info.get("zip", "")).startswith("https://") or len(str(info.get("sha256", ""))) != 64):
        raise UpdateError("info")
    return info


def find_program(root):
    """Açılan zip'te kurulumun program\\ klasörü (<zip adı>\\program\\python\\python.exe ile)."""
    for d in [root] + [os.path.join(root, n) for n in sorted(os.listdir(root))]:
        p = os.path.join(d, "program")
        if os.path.isfile(os.path.join(p, "python", "python.exe")) and os.path.isdir(os.path.join(p, "ets2bakim")):
            return p
    return None


def _clear(folder, keep=("kurulum.log",)):
    """Klasördeki her şeyi siler (keep hariç); kullanımdaki dosyalar kalır, bir sonraki temizlikte silinir."""
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for n in names:
        p = os.path.join(folder, n)
        try:
            if n in keep:
                continue
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                os.remove(p)
        except OSError:
            pass


class Updater:
    """Arayüze giden durum (status): state = off (kurulu kopya değil) | idle | checking | latest | available |
    downloading | installing | error; current, latest, notes, progress (0..1), error (kod), detail."""

    def __init__(self, install_dir, game_running=lambda: None, info_url=INFO_URL, work_dir=WORK_DIR):
        self.install_dir = install_dir                                  # None: geliştirme kopyası, güncellenmez
        self.game_running = game_running
        self.info_url = info_url
        self.work_dir = work_dir
        self.info = None
        self.lock = threading.Lock()
        self.busy = False
        self.status = dict(state="idle" if install_dir else "off", current=__version__)

    def _set(self, **kw):
        with self.lock:
            self.status = dict(self.status, **kw)

    def _run(self, fn, background, **state):
        with self.lock:
            if self.busy:
                return False
            self.busy = True
            self.status = dict(self.status, error="", detail="", **state)

        def work():
            try:
                fn()
            except Exception as ex:   # ağ, Drive, disk: Ayarlar'daki durum satırında gösterilir
                code = ex.args[0] if isinstance(ex, UpdateError) else "net" if isinstance(ex, OSError) else "other"
                self._set(state="error", error=code, detail=str(ex))
            finally:
                with self.lock:
                    self.busy = False
        if background:
            threading.Thread(target=work, daemon=True).start()
        else:
            work()
        return True

    def check(self, background=True):
        """Yeni sürümü denetler. False: kurulu kopya değil ya da başka bir işlem sürüyor."""
        return bool(self.install_dir) and self._run(self._check, background, state="checking")

    def _check(self):
        info = fetch_info(self.info_url)
        self.info = info
        notes = info.get("notlar") if isinstance(info.get("notlar"), dict) else {}
        self._set(state="available" if is_newer(info["surum"]) else "latest", latest=info["surum"], notes=notes)

    def cleanup(self):
        """Önceki güncellemenin indirdiği zip ve açılmış paketi siler (kurulum bitince gereksiz); bir işlem sürerken
        dokunmaz. False: işlem sürüyor."""
        with self.lock:
            if self.busy:
                return False
            self.busy = True
        try:
            _clear(self.work_dir)
        finally:
            with self.lock:
                self.busy = False
        return True

    def install(self, background=True):
        """Yeni sürümü indirip kurar: ok | off (kurulu kopya değil) | game (oyun açık) | none | busy."""
        if not self.install_dir:
            return "off"
        if self.game_running():
            return "game"
        if not self.info or not is_newer(self.info["surum"]):
            return "none"
        return "ok" if self._run(self._install, background, state="downloading", progress=0.0) else "busy"

    def _install(self):
        info = self.info
        _clear(self.work_dir)                                           # önceki güncellemelerden kalanlar
        os.makedirs(self.work_dir, exist_ok=True)
        zpath = os.path.join(self.work_dir, f"ETS2Bakim-{info['surum']}.zip")
        h, done = hashlib.sha256(), 0
        with _open(info["zip"], timeout=60) as r, open(zpath + ".tmp", "wb") as fh:
            total = int(r.headers.get("Content-Length") or info.get("boyut") or 0)
            for chunk in iter(lambda: r.read(1 << 16), b""):
                fh.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if total:
                    self._set(progress=min(1.0, done / total))
        if h.hexdigest() != str(info["sha256"]).lower():
            os.remove(zpath + ".tmp")
            raise UpdateError("sha")
        os.replace(zpath + ".tmp", zpath)
        out = os.path.join(self.work_dir, info["surum"])
        shutil.rmtree(out, ignore_errors=True)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(out)
        prog = find_program(out)
        if not prog:
            raise UpdateError("program")
        self._set(state="installing", progress=1.0)
        self.launch(prog)

    def launch(self, prog):
        """Paketin kendi Python'uyla sessiz kurulum: uygulamayı kaydedip kapatır, günceller, yeniden açar (çıktı
        work_dir\\kurulum.log'a)."""
        with open(os.path.join(self.work_dir, "kurulum.log"), "w", encoding="utf-8") as log:
            subprocess.Popen([os.path.join(prog, "python", "python.exe"), "-X", "utf8", "-m", "ets2bakim.kurulum",
                              "kur", "--sessiz", "--hedef", self.install_dir],
                             cwd=prog, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=0x00000008 | 0x00000200)    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
