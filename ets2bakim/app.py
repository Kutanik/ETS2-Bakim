"""Ana döngü: telemetriyi okur, modelleri ilerletir, durumu kaydeder ve web arayüzüne sunar."""
import json
import os
import random
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import (alerts, appcontrol, drivemode, engines, filming, geo, i18n, rates, service_menu, sounds, telltales,
               vehicles, window)
from .appcontrol import AppControlMonitor
from .blowout import BlowoutEffect
from .currency import CurrencyMonitor
from .i18n import M, T, render
from .climate import Climate, ClimateState
from .enforcer import Enforcer
from .multiplayer import MultiplayerDetector
from .gameinput import key_label
from .overlay_feed import PANEL_MODES, OverlayBridge, overlay_key, valid_overlay_key
from .guncelleme import Updater
from .kurulum import running_game
from .storage import (DEFAULT_SETTINGS, GAME_MODES, MP_DEFAULTS, SHARED_KEYS, UPDATE_INTERVALS, Storage,
                      profile_dir)
from .telemetry import DemoSource, Frame, GameSource
from .truck import TruckModel
from .util import clamp, load_dataclass
from .view import build_detail, build_state
from .wipers import WiperInput, WiperTracker, rain_sensor_on

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(ROOT, "web")
TICK_S = 0.1        # simülasyon adımı (10/sn)
TICK_FAST_S = 0.05  # Ayarlar → Değer güncelleme sıklığı "Gerçek zamanlı" seçiliyse (20/sn)
WAIT_OVL_S = 0.5    # oyun beklenirken katmana "bekleniyor" bilgisi en çok bu sıklıkta yazılır
DECEL_WINDOW_S = 0.095  # yavaşlama en az bu kadar zaman aralığından hesaplanır (adım hızından bağımsız, gürültüsüz)
MP_STOP_KMH = 10  # çok oyunculu tam izlemede motor ancak bu hızın altında durdurulur (trafikte tehlike yaratmasın)
MODE_BACK_S = 45.0  # Otomatik mod: oyun sürerken çok oyunculu oturum bu kadar algılanmazsa Tek Oyunculu'ya dönülür
JUMP_CHUNK_S = 300.0
MAX_PAUSE_ODO_KM = 0.5   # duraklatmadan dönüşte kilometre bundan çok değiştiyse başka kayıt yüklenmiştir (feribot km saymaz)
CITY_MOVE_DEG = 0.004    # en yakın şehir ancak bu kadar (~0,4 km) yer değişince yeniden aranır (her adımda yüzlerce şehir)


class Pacer:
    """Yayın zamanlayıcısı: seçilen aralığın ortalaması korunur (adım sapması aralığı uzatmaz; 0,25 sn aralık
    10/sn adımda 0,2 / 0,3 sn sırasıyla yayınlanır). Aralık 0 ya da adımdan kısa ise her adımda yayınlanır."""

    def __init__(self):
        self.next = 0.0

    def due(self, now, interval, tick):
        if interval <= 0:
            return True
        if now + tick / 2 >= self.next:
            self.next = self.next + interval if self.next + interval > now else now + interval
            return True
        return False


class App:
    def __init__(self, demo=False, speedup=1.0, port=8723, open_window=True, data_dir=None, game_mode=None):
        # Tek uygulama, iki mod: tek (tek oyunculu, tam gerçekçilik) · cok (TruckersMP / Konvoy; motor zorla durdurulmaz).
        # Her modun ayarları ve tır kayıtları ayrıdır: Tek Oyunculu data_dir'de (data), Çok Oyunculu data_dir_mp'de
        # (data_mp). Dil ve oyun modu seçimi (Ayarlar → Oyun modu) ortaktır; açılışta Tek Oyunculu dosyasından okunur.
        # game_mode: komut satırındaki --mod (auto | tek | cok); verilirse ayar olarak kaydedilir.
        self.home_dir = os.path.normpath(data_dir or os.path.join(ROOT, "data_demo" if demo else "data"))
        home = Storage(self.home_dir)
        shared = home.load_settings()
        if game_mode in GAME_MODES and shared.get("game_mode") != game_mode:
            shared["game_mode"] = game_mode
            try:
                home.save_settings(shared)
            except OSError:
                pass
        self.game_mode = "cok" if shared.get("game_mode") == "cok" else "tek"   # etkin mod (Otomatik'te oyuna göre)
        if self.game_mode == "cok":
            self.storage = Storage(profile_dir(self.home_dir, "cok"))
            self.settings = self._profile_settings(self.storage, "cok", shared)
        else:
            self.storage, self.settings = home, shared
        self._mp_seen = None       # Otomatik mod: çok oyunculu oturumun son algılandığı an (monotonic)
        self._was_ok = False       # önceki karede oyun bağlı mıydı (yeni oyun oturumunda mod yeniden belirlenir)
        i18n.set_lang(self.settings.get("language", "tr"))
        g = self.storage.load_global()
        self.climate = Climate(load_dataclass(ClimateState, g.get("climate")))
        # son bilinen araç (marka, sınıf): oyun kapalıyken "sesi dinle" o aracın sesini çalsın
        self.last_vehicle = g.get("last_vehicle") if isinstance(g.get("last_vehicle"), dict) else {}
        self.source = DemoSource(speedup) if demo else GameSource()
        self.source_name = "demo" if demo else "oyun"
        self.port = port
        self.demo = demo
        self.open_window = "app" if open_window is True else open_window  # "app" | "browser" | False
        self.lock = threading.RLock()
        self.enforcer = Enforcer()
        self.mp = MultiplayerDetector()
        self.appctl = AppControlMonitor()  # Akıllı Uygulama Denetimi: imzasız katman DLL'i oyunda engellenir
        self.blowout = BlowoutEffect()
        self.currency = CurrencyMonitor()   # oyunda seçili para birimi (game.log: g_currency) ve oyunun kuru
        # silecek kademesi: oyunun silecek tuşları yalnızca oyun penceresi öndeyken okunur (demoda tuş yok)
        self.wipers = WiperTracker(None if demo else WiperInput().start(), rain_sensor=not demo and rain_sensor_on())
        self.bridge = OverlayBridge()
        self.updater = Updater(ROOT if appcontrol.PACKAGED and not demo else None, running_game)
        # uyarı sesi: markaya göre, her uyarıda bir kez (demoda sessiz: testler ve tanıtım bilgisayarda ötmesin)
        self.sounds = sounds.WarningSound(os.path.join(ROOT, "sesler"), enabled=not demo)
        self.beeper = sounds.WarningBeeper()
        # sürüş modu tuşu: klavye ya da kumanda düğmesi, yalnızca oyun öndeyken (demoda okunmaz, atama yine yapılabilir)
        self.drive = drivemode.HotkeyInput()
        if not demo:
            self.drive.start()
        drivemode.set_overlay_key(overlay_key(self.settings))
        self.drive.set_binding(self.settings.get("drive_mode_key", drivemode.DEFAULT_KEY))
        # çekim modu tuşu (filming.py): yalnızca Tek Oyunculu modda ve çekim modu açıkken bağlanır (mod oyunda değişebilir)
        self.film = drivemode.HotkeyInput("cekim-tusu")
        if not demo:
            self.film.start()
        self._film_bind()
        self.stop_stage = 0
        self.stop_time = 0.0
        self.prev_job_flags = None
        self.rng = random.Random()
        self.truck = None
        self.frame = Frame()
        self.ambient = 15.0
        self.expected_min = 5.0
        self.lat, self.lon, self.city, self.city_km = 50.0, 10.0, "", 0.0
        self.history = deque(maxlen=1800)
        self.prev = None
        self.gm_acc = 0.0
        self.refuel_acc = 0.0
        self.last_hist = self.last_save = self.last_wait_ovl = 0.0
        self.last_message = None
        # arayüz durumu: her adımda kurulur, JSON'a ancak okunacağı zaman çevrilir (pencere küçültülmüşken boşa iş yok);
        # pencereye canlı akışla (/api/stream) seçilen aralıkta gönderilir
        self._ui_cv = threading.Condition()
        self._ui_ver = 0
        self._ui_S = self._ui_D = None
        self._ui_dirty = False
        self.ui_pacer, self.ovl_pacer = Pacer(), Pacer()
        self._alarm_key = None            # görünen uyarılar ve ikaz lambaları (değişince aralık beklenmeden yayınlanır)
        self._spd_hist = deque(maxlen=24)  # (an, hız): yavaşlama DECEL_WINDOW_S aralığından
        self._sim_t = 0.0                 # adım sürelerinin toplamı (yavaşlama hesabının saati)
        self._city_at = None              # en yakın şehrin arandığı konum
        self.state_json = json.dumps({"status": {"source": self.source_name, "text": T("Başlatılıyor…"),
                                                 "connected": False, "lang": i18n.LANG}}).encode()
        self.detail_json = b"{}"
        self.running = True
        self._shut = False
        self._shutdown_lock = threading.Lock()

    # ------------------------------------------------------------------ kamyon yönetimi
    def switch_truck(self, f):
        if self.truck is not None:
            self.save()
        data = self.storage.load_truck(f.truck_key)
        if data:
            self.truck = TruckModel.from_dict(data)
        else:
            self.truck = TruckModel(f.truck_key, {"brand": f.brand, "name": f.name, "plate": f.plate})
        self.truck.info.update({"brand": f.brand, "name": f.name, "plate": f.plate})
        self.prev = None
        self.history.clear()

    def save(self):
        # yazılamazsa (disk dolu, dosya kilitli) simülasyon ve kapanış sürsün; sonraki kayıtta yeniden denenir
        try:
            if self.truck is not None and self.truck.initialized:
                self.storage.save_truck(self.truck.key, self.truck.to_dict())
            self.storage.save_global({"climate": self.climate.state.__dict__, "last_vehicle": self.last_vehicle})
        except OSError as ex:
            self.message("warn", M("Kayıt yazılamadı: {err}", err=str(ex)))

    def message(self, level, msg):
        self.last_message = {"level": level, "text": render(msg), "at": time.time()}

    # ------------------------------------------------------------------ simülasyon adımı
    def tick(self, f, dt_real):
        if f is None:
            self._was_ok = False
            self._publish_waiting()
            return
        self.frame = f
        f.wiper_stage = self.wipers.update(f)  # SDK yalnızca açık/kapalı verir; kademe tuşlardan izlenir
        self.mp.update(f, source_is_game=not self.demo)
        self._mode_step(f)                     # tır yüklenmeden önce: çok oyunculu oturumun tırı kendi kaydından gelsin
        if not f.ok or not f.truck_key:
            self.prev = None
            self._publish(force=True) if self.truck else self._publish_waiting()
            return
        if self.truck is None or self.truck.key != f.truck_key:
            self.switch_truck(f)
        t = self.truck
        if f.brand_id and t.initialized:
            self.last_vehicle = {"brand_id": f.brand_id, "veh": t.veh}
        if f.paused:
            # feribot / tren yolculuğu yükleme ekranında (oyun duraklatılmış) geçer: son oyun saati korunur ki dönüşte
            # atlanan saatler bulunabilsin; hareket farkları (km, yakıt, yavaşlama) dönüşte sayılmaz
            if self.prev is not None:
                self.prev["resume"] = True
            self._publish()
            return

        dt_game = dt_real * clamp(f.scale, 0.0, 1000.0)
        self.lat, self.lon = geo.game_to_latlon(f.x, f.z)
        here = self._city_at
        if here is None or abs(self.lat - here[0]) + abs(self.lon - here[1]) > CITY_MOVE_DEG:
            self._city_at = (self.lat, self.lon)
            self.city, self.city_km = geo.nearest_city(self.lat, self.lon)

        resumed = self.prev is not None and self.prev.get("resume", False)
        if resumed and abs(f.odometer_km - self.prev["odo"]) > MAX_PAUSE_ODO_KM:
            self.prev = None   # duraklatmada başka kayıt yüklendi (kilometre değişti): atlama sayılmaz

        # zaman atlaması (uyku, feribot, tren)
        if self.prev is not None:
            dgm = f.game_minutes - self.prev["gm"]
            self.gm_acc += dt_game / 60.0
            if dgm > 0:
                if dgm > self.gm_acc + 15 and t.initialized:
                    self._apply_jump(f, dgm - self.gm_acc)
                self.gm_acc = max(0.0, self.gm_acc - dgm)
            elif dgm < 0:
                self.gm_acc = 0.0

        amb = self.climate.update(dt_game, self.lat, self.lon, f.y, f.game_minutes, f.wipers, self.settings)
        self.ambient = amb
        self.expected_min = self._expected_min()
        now = time.monotonic()

        km = dfuel = decel = 0.0
        speed = abs(f.speed_kmh)
        self._sim_t += max(0.0, dt_real)   # adımların gerçek süresi (testlerde verilen dt): yavaşlamanın zaman ekseni
        if self.prev is not None and not self.prev.get("resume", False):
            dodo = f.odometer_km - self.prev["odo"]
            if 0.0 <= dodo <= abs(f.speed_kmh) * dt_game / 3600.0 * 3 + 0.05:
                km = dodo
            dfuel = self.prev["fuel"] - f.fuel_l
            decel = self._decel(self._sim_t, speed)
        else:
            self._spd_hist.clear()
        self._spd_hist.append((self._sim_t, speed))
        if dfuel < -0.05:
            self.refuel_acc += -dfuel
        else:
            if self.refuel_acc > 1.0:
                t.event(f, "info", M("Yakıt alındı: {l:.0f} L.", l=self.refuel_acc))
                t.station_refuel(f, self.refuel_acc, self.settings)
            self.refuel_acc = 0.0   # 1 L'den küçük artışlar (kayıt yükleme vb.) birikip sahte yakıt alımı sayılmasın

        if not t.initialized:
            t.first_time_setup(f, amb)
        t.step(f, dt_real, dt_game, dict(ambient=amb, settings=self.settings, rng=self.rng,
                                         km=km, dfuel=max(dfuel, -100.0) if dfuel > -0.05 else -1.0,
                                         decel=decel))
        # lastik patlaması: oyunda ani sürüklenme, kayma ve jant sürtmesi (yalnızca tek oyunculu)
        allowed = (not self.mp_session() and self.settings.get("blowout_effect", True)
                   and bool(self.bridge.input_ready()))
        self.bridge.set_axes(*self.blowout.update(t.tires, f, allowed, time.monotonic()))
        if t.killed and f.engine_on and self.enforce_allowed():
            # çok oyunculuda motor trafikte değil, tır yavaşlayınca durdurulur (o zamana kadar uyarı verilir)
            if not (self.mp_session() and abs(f.speed_kmh) >= MP_STOP_KMH):
                self._enforce_stop()
        elif not f.engine_on:
            self.stop_stage = 0

        self._check_job_events(f)
        self.prev = {"gm": f.game_minutes, "odo": f.odometer_km, "fuel": f.fuel_l, "speed": abs(f.speed_kmh)}
        if now - self.last_hist >= 1.0:
            self.last_hist = now
            self._sample(t, f)
        if now - self.last_save >= 15.0:
            self.last_save = now
            self.save()
        self._publish()

    def _check_job_events(self, f):
        """Hızlı iş (geçici tır) teslim edilince ya da iptal edilince o tırın değerlerini sıfırlar.
        Telemetri eklentisi olay bayraklarını her olayda çevirdiği için değişim izlenir."""
        flags = (f.ev_delivered, f.ev_finished, f.ev_cancelled)
        prev, self.prev_job_flags = self.prev_job_flags, flags
        if prev is None or flags == prev:
            return
        t = self.truck
        if not (t and t.temporary and self.settings.get("reset_temp_trucks", True)):
            return
        if flags[2] != prev[2]:
            msg = M("İş iptal edildi: geçici tırın (hızlı iş) bakım değerleri sıfırlandı.")
        else:
            msg = M("Teslimat tamamlandı: geçici tırın (hızlı iş) bakım değerleri sıfırlandı.")
        self.reset_truck(f, msg)
        self.message("info", msg)

    def reset_truck(self, f, msg):
        """Bu tırın kayıtlı durumunu siler ve yeni bir başlangıç durumu kurar."""
        key = self.truck.key
        choice = self.truck.spec.vehicle_override
        self.storage.delete_truck(key)
        t = TruckModel(key, {"brand": f.brand, "name": f.name, "plate": f.plate})
        t.spec.vehicle_override = choice   # Ayarlar → Araç tipi seçimi sıfırlamada korunur (otomobil modu otomobil kalır)
        t.first_time_setup(f, self.ambient)
        t.event(f, "info", msg)
        self.truck = t
        self.history.clear()
        self.save()

    # ------------------------------------------------------------------ oyun modu (Tek / Çok Oyunculu)
    def mode_setting(self):
        """Ayarlar → Oyun modu: auto (TruckersMP / Konvoy algılanınca Çok Oyunculu) | tek | cok."""
        m = self.settings.get("game_mode")
        return m if m in GAME_MODES else "auto"

    def _wanted_mode(self, f):
        """Etkin mod. Otomatik'te çok oyunculu oturum algılanınca hemen Çok Oyunculu; oyun sürerken algılama bir an
        kaçarsa (TruckersMP denetimi 15 sn'de bir) hemen dönülmez. Oyun kapalıyken son mod korunur."""
        setting = self.mode_setting()
        if setting != "auto":
            return setting
        now = time.monotonic()
        if self.mp.kind:
            self._mp_seen = now
            return "cok"
        if not f.ok:
            return self.game_mode
        if self.game_mode == "cok" and self._mp_seen is not None and now - self._mp_seen < MODE_BACK_S:
            return "cok"
        return "tek"

    def _mode_step(self, f):
        """Oyun yeniden bağlanınca (yeni oyun oturumu) TruckersMP hemen yeniden denetlenir ve mod beklemeden belirlenir:
        TruckersMP'den çıkıp tek oyunculu açılınca tek oyunculu tır Çok Oyunculu kayda yazılmasın."""
        if f.ok and not self._was_ok:
            self._mp_seen = None
            if not self.demo:
                self.mp.recheck()
                self.mp.update(f, source_is_game=True)
        self._was_ok = f.ok
        self._switch_profile(self._wanted_mode(f))

    @staticmethod
    def _profile_settings(storage, mode, shared):
        s = storage.load_settings(MP_DEFAULTS if mode == "cok" else None)
        s.update({k: shared[k] for k in SHARED_KEYS if k in shared})   # dil ve oyun modu iki modda ortak
        return s

    def _switch_profile(self, mode):
        """Etkin modu değiştirir (kilit tutulurken): o anki tır ve genel durum kendi klasörüne kaydedilir, öbür modun
        ayarları, iklim durumu ve tır kayıtları yüklenir. Tır bir sonraki karede o modun kaydından gelir."""
        if mode == self.game_mode:
            return
        self.save()
        shared = {k: self.settings.get(k) for k in SHARED_KEYS}
        self.game_mode = mode
        self.storage = Storage(profile_dir(self.home_dir, mode))
        self.settings = self._profile_settings(self.storage, mode, shared)
        try:
            self.storage.save_settings(self.settings)   # ilk geçişte modun ayar dosyası kurulur (ortak ayarlar eşitlenir)
        except OSError:
            pass
        g = self.storage.load_global()
        self.climate = Climate(load_dataclass(ClimateState, g.get("climate")))
        self.last_vehicle = g.get("last_vehicle") if isinstance(g.get("last_vehicle"), dict) else {}
        self.truck = None
        self.prev = None
        self.prev_job_flags = None
        self.history.clear()
        self.gm_acc = self.refuel_acc = 0.0
        self.stop_stage = 0
        self.drive.cancel_capture()
        self.film.cancel_capture()
        drivemode.set_overlay_key(overlay_key(self.settings))
        self.drive.set_binding(self.settings.get("drive_mode_key", drivemode.DEFAULT_KEY))
        self._film_bind()
        self.message("info", M("Oyun modu: {mode_t} — bu modun kendi ayarları ve bakım kayıtları yüklendi.",
                               mode_t=window.MODE_NAMES[mode]))

    def mp_session(self):
        """Çok Oyunculu mod ya da Tek Oyunculu modda algılanan TruckersMP / Konvoy oturumu."""
        return self.game_mode == "cok" or bool(self.mp.kind)

    def watch_mode(self):
        """'full' (tam izleme: uyarı + arızada motor durdurulur) ya da 'show' (sadece gösterme: değerler ve uyarılar).
        Tek Oyunculu mod her zaman tam izlemedir; seçenek yalnızca Çok Oyunculu moddadır (varsayılan: sadece gösterme).
        Tek Oyunculu'ya sabitlenmiş mod çok oyunculu oturum algılarsa güvenlik için yalnızca gösterir."""
        if self.game_mode == "cok":
            return "full" if self.settings.get("mp_watch_mode") == "full" else "show"
        return "show" if self.mp.kind else "full"

    def enforce_allowed(self):
        return self.watch_mode() == "full"

    def _mode_warnings(self):
        w = []
        f, t = self.frame, self.truck
        if self.mp.kind and self.game_mode == "tek":
            w.append({"level": "warn", "key": "mp_detected", "text": T(
                "{mp_t} oturumu algılandı: güvenlik için motor zorla durdurulmuyor. Ayarlar → Oyun modu: Otomatik ya da "
                "Çok Oyunculu seçin.", mp_t=self.mp.label)})
        elif (self.mode_setting() == "cok" and not self.demo and self.frame.ok and not self.mp.kind
              and self.settings.get("alert_level") == "all"):
            w.append({"level": "info", "key": "sp_session", "text": T(
                "Tek oyunculu oturum: tam gerçekçilik (motor durdurma) için Ayarlar → Oyun modu: Otomatik ya da Tek "
                "Oyunculu seçin.")})
        if (t is not None and t.killed and f.engine_on and self.enforce_allowed() and self.mp_session()
                and abs(f.speed_kmh) >= MP_STOP_KMH):
            w.append({"level": "crit", "key": "mp_stop_pending", "text": T(
                "Motor çalışmaz durumda: güvenli bir yere çekip yavaşlayın; tır {v} km/h altına inince motor durdurulacak "
                "(kontak ve ışıklar açık kalır).", v=MP_STOP_KMH)})
        return w

    def _drive_step(self):
        """Sürüş modu: tuşa basış (oyun öndeyken) modu sırayla değiştirir (ECO → COMFORT → SPORT), atanan tuş kaydedilir,
        parametreler her adımda katmana yazılır (simülatör kapanınca eklenti 1,5 sn içinde gaza karışmayı bırakır)."""
        d = self.drive
        if d.capturing and not d._thread:   # demoda arka plan okuyucu yok: atama burada okunur
            d.poll(time.monotonic())
        presses = d.drain()
        if presses and self.settings.get("drive_modes", True) and not self.frame.paused:
            m = self.settings.get("drive_mode", drivemode.DEFAULT_MODE)
            for _ in range(presses):
                m = drivemode.next_mode(m)
            self.settings["drive_mode"] = m
            self.storage.save_settings(self.settings)
            self.message("info", M("Sürüş modu: {name} — {desc_t}", name=drivemode.NAMES[m], desc_t=drivemode.DESCS[m]))
        cap = d.take_captured()
        if cap is not None:
            if cap and cap == self.settings.get("film_key"):
                self.message("warn", M("Bu tuş çekim modu tuşu olarak atanmış; başka bir tuş seçin."))
            elif cap:
                self.settings["drive_mode_key"] = cap
                d.set_binding(cap)
                self.storage.save_settings(self.settings)
                self.message("info", M("Sürüş modu tuşu atandı: {key}", key=drivemode.binding_label(cap)))
            else:
                self.message("warn", M("Tuş atama iptal edildi ya da süre doldu."))
        self.bridge.set_drive(*drivemode.header_params(self.settings, self.truck.veh if self.truck else "truck"))

    # ------------------------------------------------------------------ çekim modu (filming.py)
    def film_available(self):
        """Çekim modu yalnızca Tek Oyunculu modda ve çok oyunculu oturum algılanmamışken kullanılabilir."""
        return self.game_mode == "tek" and not self.mp.kind

    def _film_bind(self):
        """Çekim modu açıkken kısayol tuşu dinlenir; kapalıyken (ve Çok Oyunculu modda) tuş yok sayılır."""
        on = self.game_mode == "tek" and self.settings.get("film_mode")
        self.film.set_binding(self.settings.get("film_key", "") if on else "")

    def _film_step(self):
        """Çekim modu tuşu: basış (oyun öndeyken) seçili arızayı tetikler; atama sonucu kaydedilir."""
        k = self.film
        if k.capturing and not k._thread:   # demoda arka plan okuyucu yok: atama burada okunur
            k.poll(time.monotonic())
        if k.drain() and self.settings.get("film_mode") and self.film_available() and not self.frame.paused:
            ok, msg = self._film_trigger(self.settings.get("film_fault", filming.DEFAULT_ITEM))
            self.message("info" if ok else "warn", msg)
        cap = k.take_captured()
        if cap is not None:
            if cap and cap == self.settings.get("drive_mode_key"):
                self.message("warn", M("Bu tuş sürüş modu tuşu olarak atanmış; başka bir tuş seçin."))
            elif cap:
                self.settings["film_key"] = cap
                self._film_bind()
                self.storage.save_settings(self.settings)
                self.message("info", M("Çekim modu tuşu atandı: {key}", key=drivemode.binding_label(cap)))
            else:
                self.message("warn", M("Tuş atama iptal edildi ya da süre doldu."))

    def _film_trigger(self, item):
        """Seçili arızayı tetikler (kilit tutulurken). Dönüş: (başarılı, M ileti)."""
        if self.truck is None or not self.truck.initialized:
            return False, M("Henüz kamyon verisi yok.")
        ok, msg = filming.trigger(self.truck, self.frame, item)
        if ok:
            self.beeper.rearm()   # onarılıp yeniden tetiklenen arıza da hemen ötsün (çekim tekrarı)
            self.save()
        return ok, msg

    def film_action(self, op, item=None):
        """Ayarlar → Çekim modu: "trigger" (seçili ya da verilen arıza) | "repair_all" (hepsini ücretsiz onar)."""
        with self.lock:
            if not self.film_available():
                return False, render(M("Çekim modu yalnızca tek oyunculu oturumda kullanılabilir."))
            if not self.settings.get("film_mode"):
                return False, render(M("Çekim modu kapalı: Ayarlar → Çekim modu kutusunu işaretleyin."))
            if op == "trigger":
                ok, msg = self._film_trigger(item or self.settings.get("film_fault", filming.DEFAULT_ITEM))
            elif op == "repair_all":
                if self.truck is None or not self.truck.initialized:
                    return False, render(M("Henüz kamyon verisi yok."))
                ok, msg = filming.repair_all(self.truck, self.frame)
                if ok:
                    self.save()
            else:
                return False, render(M("Bilinmeyen işlem."))
            self._publish(force=True)
            return ok, render(msg)

    def film_capture(self, start):
        with self.lock:
            if start:
                if self.game_mode != "tek":
                    return False, render(M("Çekim modu yalnızca tek oyunculu oturumda kullanılabilir."))
                self.drive.cancel_capture()   # aynı basış iki tuşa birden atanmasın
                self.film.start_capture()
                msg = M("Atamak istediğiniz klavye tuşuna ya da direksiyon / kumanda düğmesine basın (10 sn, Esc iptal).")
            else:
                self.film.cancel_capture()
                msg = M("Tuş atama iptal edildi.")
            self._publish(force=True) if self.truck else self._publish_waiting()
            return True, render(msg)

    def _film_status(self):
        key, item = self.settings.get("film_key", ""), self.settings.get("film_fault", filming.DEFAULT_ITEM)
        return {"available": self.film_available(), "enabled": bool(self.settings.get("film_mode")),
                "item": item if item in filming.IDS else filming.DEFAULT_ITEM, "key": key,
                "key_label": drivemode.binding_label(key), "capturing": self.film.capturing}

    def _sound_brand(self):
        """Ses ailesi: Ayarlar'da seçilen marka, yoksa tırın markası (oyun kapalıyken son bilinen araç)."""
        sel = self.settings.get("sound_brand", "auto")
        if sel in sounds.BRANDS:
            return sel
        if self.frame.brand_id:
            return sounds.brand_key(self.frame.brand_id, self.truck.veh if self.truck else "truck")
        lv = self.last_vehicle or {}
        return sounds.brand_key(lv.get("brand_id", ""), lv.get("veh", "truck"))

    def _sound_step(self, warnings):
        """Yeni uyarıda markaya göre ikaz sesi; her uyarı bir kez (dikkat uyarıları yalnızca "Hepsi" düzeyinde)."""
        on = self.settings.get("sound", True)
        lvl = self.beeper.update(warnings if on else [], time.monotonic(), self.settings.get("alert_level") == "all")
        if lvl and not self.frame.paused:
            self.sounds.play(self._sound_brand(), lvl)

    def sound_test(self, level):
        level = level if level in ("crit", "warn") else "crit"
        brand = self._sound_brand()
        ok = self.sounds.play(brand, level, test=True)
        if not ok:
            return False, render(M("Ses çalınamadı (demo modunda ses kapalı)."))
        msg = M("Uyarı sesi: {brand_t} ({lvl_t}).", brand_t=sounds.BRAND_NAMES[brand], lvl_t=sounds.LEVEL_NAMES[level])
        if not self.settings.get("sound", True):
            msg = M("Uyarı sesi: {brand_t} ({lvl_t}). Sesli uyarı kapalı: oyunda ötmesi için “Sesli uyarı” kutusunu "
                    "işaretleyin.", brand_t=sounds.BRAND_NAMES[brand], lvl_t=sounds.LEVEL_NAMES[level])
        return True, render(msg)

    def drive_capture(self, start):
        with self.lock:
            if start:
                self.film.cancel_capture()    # aynı basış iki tuşa birden atanmasın
                self.drive.start_capture()
                msg = M("Atamak istediğiniz klavye tuşuna ya da direksiyon / kumanda düğmesine basın (10 sn, Esc iptal).")
            else:
                self.drive.cancel_capture()
                msg = M("Tuş atama iptal edildi.")
            self._publish(force=True) if self.truck else self._publish_waiting()
            return True, render(msg)

    def _drive_status(self):
        m = self.settings.get("drive_mode", drivemode.DEFAULT_MODE)
        m = m if m in drivemode.ORDER else drivemode.DEFAULT_MODE
        key = self.settings.get("drive_mode_key", "")
        return {"enabled": bool(self.settings.get("drive_modes", True)), "mode": m, "name": drivemode.NAMES[m],
                "desc": T(drivemode.DESCS[m]), "key": key, "key_label": drivemode.binding_label(key),
                "capturing": self.drive.capturing,
                "modes": [{"id": k, "name": drivemode.NAMES[k], "desc": T(drivemode.DESCS[k])} for k in drivemode.ORDER]}

    def _mode_status(self):
        """Hem kamyonlu hem bekleme durumuna eklenir. Dil de burada: oyun kapalıyken (bekleme ekranı, Ayarlar) seçilen
        dil arayüze ancak böyle ulaşır; yoksa sayfa Türkçe kalır."""
        ac = self.appctl.get()
        return {"lang": i18n.LANG, "packaged": appcontrol.PACKAGED,   # paketli kurulum: yönergeler Başlat menüsünü gösterir
                "mode": self.game_mode, "mode_setting": self.mode_setting(),   # etkin mod ve Ayarlar → Oyun modu seçimi
                "multiplayer": self.mp.kind, "multiplayer_label": self.mp.label,
                "enforce_allowed": bool(self.enforce_allowed()), "watch_mode": self.watch_mode(),
                "drive": self._drive_status(), "film": self._film_status(),
                "update": dict(self.updater.status),                    # Ayarlar → Genel → Güncelleme
                "currency": self.currency.get(self.settings, "ats" if self.frame.game == 2 else "ets2"),
                "appcontrol": {"sac": ac.get("sac"), "overlay_blocked": ac.get("overlay_blocked"),
                               "build_blocked": ac.get("build_blocked"),
                               "installed": bool(ac.get("installed")), "build_signature": ac.get("build_signature")}}

    def _enforce_stop(self):
        """Yalnızca motoru durdurur; kontak, ekranlar ve ışıklar açık kalır. 1) oyun içi eklentiyle motor durdur
        komutu, 2) 2,5 sn içinde etkisiz kalırsa yedek olarak oyuna motor tuşu. Motor komutu aç/kapa olduğu için
        eklenti komutu tekrarlanmaz."""
        now = time.monotonic()
        if self.bridge.input_ready() and self.stop_stage == 0:
            if self.bridge.engine_toggle(cooldown=0):
                self.stop_stage, self.stop_time = 1, now
                self.message("info", M("Motor durduruluyor (oyun içi eklenti); kontak ve ekranlar açık kalır."))
            return
        if self.stop_stage == 1 and now - self.stop_time <= 2.5:
            return
        self.stop_stage = 3
        ok, msg = self.enforcer.stop_engine(self.settings.get("engine_key", "e"))
        if msg != "bekleniyor":
            self.message("crit" if not ok else "info", M("Motor durduruldu: {msg}", msg=msg) if ok else msg)

    def _apply_jump(self, f, minutes):
        t = self.truck
        total = minutes * 60.0
        start_gm = f.game_minutes - minutes
        done = 0.0
        while done < total:
            step = min(JUMP_CHUNK_S, total - done)
            gm = start_gm + (done + step) / 60.0
            amb = self.climate.update(step, self.lat, self.lon, f.y, gm, False, self.settings)
            t.parked_step(f, step, amb, self.settings)
            done += step
        b = t.battery
        t.event(f, "info", M("Zaman atlaması {h:.1f} saat (uyku/feribot): motor {t:.0f} °C'ye soğudu, akü %{soc:.0f}.",
                             h=minutes / 60, t=t.thermal.t_cool, soc=b.soc * 100))

    def _decel(self, now, speed):
        """Yavaşlama (m/s²), en az DECEL_WINDOW_S önceki hızdan: gerçek zamanlı (20/sn) adımda da 10/sn'deki gibi hesaplanır,
        oyunun kare zamanlamasından gelen gürültü sert fren sayısını şişirmez."""
        ref = None
        for t0, v0 in reversed(self._spd_hist):
            if now - t0 >= DECEL_WINDOW_S:
                ref = (t0, v0)
                break
        if ref is None:
            if not self._spd_hist:
                return 0.0
            ref = self._spd_hist[0]
        dt = now - ref[0]
        return (ref[1] - speed) / 3.6 / dt if dt > 1e-3 else 0.0

    def _expected_min(self):
        if self.settings.get("climate_mode") == "fixed":
            return float(self.settings.get("climate_fixed_c", 15.0))
        doy = self.climate.day_of_year(self.settings)
        base = min(self.climate.baseline(self.lat, self.lon, self.frame.y, doy + d, 5.0) for d in range(0, 30, 5))
        return base - (6.0 if self.settings.get("weather_variability", True) else 0.0)

    def _sample(self, t, f):
        th, b, e = t.thermal, t.battery, t.eng
        self.history.append({
            "gm": f.game_minutes, "cool": round(th.t_cool, 1), "oil_t": round(th.t_oil, 1),
            "oil_p": round(t.oil_pressure, 2), "volt": round(b.voltage, 2), "soc": round(b.soc * 100, 1),
            "rpm": round(e.rpm), "load": round(e.load * 100), "speed": round(abs(f.speed_kmh)),
            "amb": round(self.ambient, 1), "fuel": round(e.fuel_lph, 1), "exh": round(e.exh_temp or 0),
            "amp": round(b.current, 1),
        })

    # ------------------------------------------------------------------ yayın (pencere ve oyun içi katman)
    def interval(self, key):
        """Ayarlar → Değer güncelleme sıklığı (sn; 0 = gerçek zamanlı). key: ui_interval | overlay_interval."""
        dv = DEFAULT_SETTINGS[key]
        try:
            v = float(self.settings.get(key, dv))
        except (TypeError, ValueError):
            return dv
        return v if v in UPDATE_INTERVALS else dv

    def tick_s(self):
        """Simülasyon adımı: pencere ya da katman "Gerçek zamanlı" ise 20/sn, değilse 10/sn."""
        return TICK_FAST_S if 0.0 in (self.interval("ui_interval"), self.interval("overlay_interval")) else TICK_S

    def _publish(self, force=False):
        """Durum her adımda kurulur (uyarı sesleri ve ikaz lambaları gecikmesin). Pencereye ve katmana seçilen aralıkta
        gönderilir; yeni bir uyarı ya da lamba yanınca / sönünce ve bir işlemden sonra (force) aralık beklenmez."""
        if self.truck is None or not self.truck.initialized:
            self._publish_waiting(force)
            return
        now, tick = time.monotonic(), self.tick_s()
        try:
            S = build_state(self, self.truck, self.frame)
            D = build_detail(self.truck, self.frame, self.settings)
            S["status"]["overlay"] = self._overlay_status()
            S["status"].update(self._mode_status())
            S["warnings"] = alerts.visible(self._mode_warnings(), self.settings) + list(S.get("warnings") or [])
            self._sound_step(S["warnings"])
            lamps = self.bridge.lamps(S, self.settings)
        except Exception as ex:  # arayüz hatası simülasyonu durdurmasın
            self.state_json = json.dumps({"status": {"source": self.source_name, "text": T("Durum hatası: {err}", err=str(ex)),
                                                     "connected": False, "lang": i18n.LANG}}).encode()
            self._ui_push()
            return
        akey = (tuple((w.get("level"), w.get("key")) for w in S["warnings"]), tuple(lamps))
        alarm = akey != self._alarm_key
        self._alarm_key = akey
        self._set_ui(S, D, push=force or alarm or self.ui_pacer.due(now, self.interval("ui_interval"), tick))
        if force or alarm or self.ovl_pacer.due(now, self.interval("overlay_interval"), tick):
            try:
                menu = service_menu.build(self.truck, self.frame, self.settings, S["status"].get("currency"))
                self.bridge.publish(S, D, self.history, self.settings, menu, lamps=lamps)
            except Exception as ex:
                self.message("warn", M("Oyun içi katmana veri gönderilemedi: {err}", err=str(ex)))
        else:
            self.bridge.heartbeat()   # katman "simülatör kapalı" sanmasın; servis menüsü komutları okunur

    def _overlay_status(self):
        """Katmanın durumu ve seçili katman tuşu (Ayarlar'da ve kısayol yazılarında gösterilir)."""
        vk = overlay_key(self.settings)
        return dict(self.bridge.status, key=vk, key_label=key_label(vk))

    def _publish_waiting(self, force=False):
        S = {"status": {"source": self.source_name, "text": render(self.source.status), "connected": False,
                        "settings": self.settings, "overlay": self._overlay_status(), **self._mode_status()}}
        now = time.monotonic()
        self._alarm_key = None
        self._set_ui(S, None, push=force or self.ui_pacer.due(now, max(self.interval("ui_interval"), TICK_S), self.tick_s()))
        if force or now - self.last_wait_ovl >= WAIT_OVL_S:
            self.last_wait_ovl = now
            self.bridge.publish_waiting(render(self.source.status), self.settings)

    def _set_ui(self, S, D, push):
        """Pencerenin son durumu (JSON'a okunurken çevrilir). push: canlı akıştaki pencereye gönderilsin."""
        with self.lock:
            self._ui_S = S
            if D is not None:
                self._ui_D = D
            self._ui_dirty = True
        if push:
            self._ui_push()

    def _ui_push(self):
        with self._ui_cv:
            self._ui_ver += 1
            self._ui_cv.notify_all()

    def _serialize_ui(self):
        if self._ui_dirty:
            self._ui_dirty = False
            self._state_json = json.dumps(self._ui_S, ensure_ascii=False).encode()
            if self._ui_D is not None:
                self._detail_json = json.dumps(self._ui_D, ensure_ascii=False).encode()

    @property
    def state_json(self):
        with self.lock:
            self._serialize_ui()
            return self._state_json

    @state_json.setter
    def state_json(self, value):
        with self.lock:
            self._state_json = value
            self._ui_dirty = False

    @property
    def detail_json(self):
        with self.lock:
            self._serialize_ui()
            return self._detail_json

    @detail_json.setter
    def detail_json(self, value):
        with self.lock:
            self._detail_json = value

    def wait_ui(self, seen, timeout):
        """Canlı akış: seen'den yeni bir durum yayınlanana kadar (en çok timeout sn) bekler. Dönüş: (sürüm, JSON | None)."""
        with self._ui_cv:
            if self._ui_ver == seen and self.running:
                self._ui_cv.wait(timeout)
            ver = self._ui_ver
        if ver == seen:
            return ver, None
        return ver, self.state_json

    # ------------------------------------------------------------------ API işlemleri
    def do_action(self, name, params):
        with self.lock:
            if self.truck is None or not self.truck.initialized:
                return False, render(M("Henüz kamyon verisi yok."))
            if name == "truck_reset":
                if abs(self.frame.speed_kmh) >= 1.0 or self.frame.engine_on:
                    return False, render(M("Bu işlem için kamyon durmuş ve motor kapalı olmalı."))
                self.reset_truck(self.frame, M("Bu tırın bakım değerleri elle sıfırlandı."))
                self._publish(force=True)
                return True, render(M("Bu tırın bakım değerleri elle sıfırlandı."))
            ok, msg = self.truck.action(self.frame, name, params or {})
            if ok:
                self.save()
            self._publish(force=True)
            return ok, render(msg)

    def update_action(self, op):
        """Ayarlar → Güncelleme: check (yeni sürümü denetle) | install (indirip kur)."""
        if op == "check":
            if self.updater.check():
                return True, render(M("Yeni sürüm denetleniyor…"))
            return False, render(M("Güncelleme sürüyor.") if self.updater.install_dir
                                 else M("Güncelleme yalnızca kurulu uygulamada çalışır."))
        r = self.updater.install() if op == "install" else "none"
        msg = {"ok": M("Yeni sürüm indiriliyor; kurulunca uygulama kapanıp yeniden açılacak."),
               "game": M("Oyun açıkken güncellenemez; oyunu kapatıp tekrar deneyin."),
               "off": M("Güncelleme yalnızca kurulu uygulamada çalışır."),
               "busy": M("Güncelleme sürüyor."), "none": M("Kurulacak yeni sürüm yok.")}[r]
        return r == "ok", render(msg)

    def update_settings(self, d):
        with self.lock:
            old_mode = self.mode_setting()
            for k, v in d.items():
                if k not in DEFAULT_SETTINGS:
                    continue
                dv = DEFAULT_SETTINGS[k]
                if k in alerts.SETTINGS:   # kapatılan uyarılar / ikaz lambaları: bilinen anahtarların listesi
                    v = alerts.clean(k, v)
                    if v is not None:
                        self.settings[k] = v
                    continue
                try:
                    if isinstance(dv, bool):
                        v = bool(v)
                    elif isinstance(dv, int):
                        v = int(v)
                    elif isinstance(dv, float):
                        v = float(v)
                    else:
                        v = str(v)
                except (TypeError, ValueError):
                    continue
                if k.startswith("rate_"):
                    v = clamp(v, 0.0, rates.MAX) if v == v else 1.0
                if k == "drive_mode" and v not in drivemode.ORDER:
                    continue
                if k == "drive_mode_key" and v and (not drivemode.parse_binding(v) or v == self.settings.get("film_key")):
                    continue
                if k == "film_key" and v and (not drivemode.parse_binding(v) or v == self.settings.get("drive_mode_key")):
                    continue
                if k == "film_fault" and v not in filming.IDS:
                    continue
                if k == "overlay_key" and (not valid_overlay_key(v) or f"key:{v}" in (
                        self.settings.get("drive_mode_key"), self.settings.get("film_key"))):
                    continue
                if k == "overlay_panel" and v not in PANEL_MODES:
                    continue
                if k == "sound_brand" and v != "auto" and v not in sounds.BRANDS:
                    continue
                if k == "lamp_level" and v not in telltales.LEVELS:
                    continue
                if k == "game_mode" and v not in GAME_MODES:
                    continue
                if k in ("ui_interval", "overlay_interval") and v not in UPDATE_INTERVALS:
                    continue
                self.settings[k] = v
            drivemode.set_overlay_key(overlay_key(self.settings))
            self.drive.set_binding(self.settings.get("drive_mode_key", ""))
            self._film_bind()
            i18n.set_lang(self.settings.get("language", "tr"))
            self.storage.save_settings(self.settings)
            if "ui_interval" in d:
                self.ui_pacer = Pacer()    # yeni aralık hemen geçerli (eski uzun aralığın sonu beklenmez)
            if "overlay_interval" in d:
                self.ovl_pacer = Pacer()
            if any(k in d for k in SHARED_KEYS):
                self._sync_shared()
            if "language" in d:
                window.retitle(window.title(self.demo))
            if self.mode_setting() != old_mode:
                # elle seçim hemen uygulanır (Otomatik'e dönülünce o anki oturuma göre)
                setting = self.mode_setting()
                self._mp_seen = None
                self._switch_profile(setting if setting != "auto" else "cok" if self.mp.kind else "tek")
            self._publish(force=True)
            return True, render(M("Ayarlar kaydedildi."))

    def _sync_shared(self):
        """Dil ve oyun modu iki modda ortaktır: öbür modun ayar dosyasına da yazılır. Tek Oyunculu dosyası her zaman
        yazılır (açılışta dil ve oyun modu oradan okunur); Çok Oyunculu dosyası yalnızca varsa (yoksa o moda ilk
        geçişte ortak ayarlarla kurulur)."""
        other_mode = "tek" if self.game_mode == "cok" else "cok"
        other = profile_dir(self.home_dir, other_mode)
        if other_mode == "cok" and not os.path.isfile(os.path.join(other, "ayarlar.json")):
            return
        try:
            st = Storage(other)
            s = st.load_settings(MP_DEFAULTS if other_mode == "cok" else None)
            changed = {k: self.settings.get(k) for k in SHARED_KEYS if s.get(k) != self.settings.get(k)}
            if changed:
                s.update(changed)
                st.save_settings(s)
        except OSError:
            pass

    def update_spec(self, d):
        with self.lock:
            t = self.truck
            if t is None:
                return False, render(M("Henüz kamyon yok."))
            s = t.spec
            if d.get("redetect"):
                t.detector.reset()
                s.mode = "auto"
                of, cf = t.oil.level_frac, t.coolant.level_frac
                t.auto_select(self.frame)
                t.apply_spec()
                t.oil.volume_l = of * t.oil.capacity_l
                t.coolant.volume_l = cf * t.coolant.capacity_l
                self.save()
                self._publish(force=True)
                return True, render(M("Otomatik algılama yeniden başlatıldı."))
            if "vehicle" in d and len(d) == 1:
                # Ayarlar → Araç tipi: sınıfın varsayılanları için aracın telemetri kimliği gerekir (oyunda bu araçla)
                if not self.frame.ok or self.frame.truck_key != t.key:
                    return False, render(M("Araç tipini değiştirmek için oyunda bu araçla bağlı olun."))
                if not t.set_vehicle(self.frame, str(d["vehicle"])):
                    return False, render(M("Bilinmeyen araç tipi."))
                self.save()
                self._publish(force=True)
                return True, render(M("Araç tipi: {veh_t}.", veh_t=vehicles.NAMES[t.veh]))
            if "mode" in d and d["mode"] in ("auto", "manual") and len(d) == 1:
                s.mode = d["mode"]
                self.save()
                self._publish(force=True)
                return True, render(M("Motor seçim modu: otomatik" if s.mode == "auto" else "Motor seçim modu: elle"))
            if d.get("engine_id"):
                m = engines.model_by_key(s.model_key)
                e = engines.engine_by_id(m, d["engine_id"]) if m else None
                if not e:
                    return False, render(M("Bu modelde böyle bir motor yok."))
                t.set_engine(e)
                s.mode = "manual"
                self.save()
                self._publish(force=True)
                return True, render(M("Motor seçildi: {engine} (otomatik algılama kapatıldı).", engine=e["label"]))
            s.mode = "manual"
            s.engine_id = ""
            lim = vehicles.spec_limits(t.veh)   # araç sınıfına göre (otomobil değerleri tır sınırlarına kırpılmasın)

            def num(k):
                v = float(d[k])
                if v != v:
                    raise ValueError(k)
                return clamp(v, lim[k][0], lim[k][1])
            try:
                if "name" in d:
                    s.name = str(d["name"])[:80]
                if "power_hp" in d:
                    s.power_kw = num("power_hp") * 0.7355
                if "displacement_l" in d:
                    s.displacement_l = num("displacement_l")
                if "torque_nm" in d:
                    if t.veh == "car":
                        s.real_torque_nm = num("torque_nm")   # yalnızca gösterim: model torku güçten türetir
                    else:
                        s.torque_nm = num("torque_nm")
                if "rated_rpm" in d:
                    s.rated_rpm = num("rated_rpm")
                if "oil_capacity_l" in d:
                    new = num("oil_capacity_l")
                    t.oil.volume_l *= new / t.oil.capacity_l
                    s.oil_capacity_l = new
                if "coolant_capacity_l" in d:
                    new = num("coolant_capacity_l")
                    t.coolant.volume_l *= new / t.coolant.capacity_l
                    s.coolant_capacity_l = new
                if "battery_ah" in d:
                    s.battery_ah = num("battery_ah")
                if "has_dpf" in d:
                    s.has_dpf = bool(d["has_dpf"])
            except (TypeError, ValueError):
                return False, render(M("Geçersiz değer."))
            t.apply_spec()
            self.save()
            self._publish(force=True)
            return True, render(M("Kamyon özellikleri kaydedildi."))

    def _run_overlay_service(self):
        """Oyun içi servis menüsünden (Alt+F8) gelen işlemi uygular, sonucu katmana bildirir."""
        pending = self.bridge.take_service()
        if not pending:
            return
        seq, cmd = pending
        name, params = service_menu.parse_command(cmd)
        if name is None:
            ok, msg = False, render(M("Bilinmeyen işlem."))
        else:
            ok, msg = self.do_action(name, params)
        self.bridge.set_result(seq, ok, msg)
        with self.lock:
            self._publish(force=True)

    # ------------------------------------------------------------------ çalıştırma
    def loop(self):
        last = time.monotonic()
        while self.running:
            start = time.monotonic()
            dt = min(1.0, start - last)
            last = start
            try:
                f = self.source.read()
                with self.lock:
                    self.tick(f, dt)
                    self._drive_step()
                    self._film_step()
                self._run_overlay_service()
            except Exception as ex:
                import traceback
                traceback.print_exc()
                self.message("crit", M("Simülasyon hatası: {err}", err=str(ex)))
            time.sleep(max(0.0, self.tick_s() - (time.monotonic() - start)))

    def serve(self):
        handler = make_handler(self)
        httpd = None
        for p in range(self.port, self.port + 10):
            try:
                httpd = ExclusiveHTTPServer(("127.0.0.1", p), handler)
                self.port = p
                break
            except OSError:
                continue
        if httpd is None:
            raise SystemExit("Boş port bulunamadı.")
        # kısa yoklama aralığı: kapanışta sunucu ~50 ms içinde durur (varsayılan 0,5 sn)
        threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        return httpd

    def run(self):
        httpd = self.serve()
        if self.settings.get("update_check", True):
            self.updater.check()                                       # arka planda; yeni sürüm Ayarlar'da ve bildirimde
        if self.updater.install_dir:
            cleanup = threading.Timer(120, self.updater.cleanup)       # önceki güncellemenin geçici dosyaları
            cleanup.daemon = True
            cleanup.start()
        url = f"http://127.0.0.1:{self.port}/"
        port_file = os.path.join(self.home_dir, "port.txt")
        try:
            with open(port_file, "w", encoding="utf-8") as fh:
                fh.write(str(self.port))
        except OSError:
            pass
        native = self.open_window == "app" and window.available()
        print(f"ETS2 Bakım Simülatörü çalışıyor: {url}"
              + ("  (pencereyi kapatınca kaydedip çıkar)" if native else "  (kapatmak için bu pencerede Ctrl+C)"))
        try:
            if native:
                # arayüz kendi penceresinde: simülasyon arka iş parçacığında, pencere ana iş parçacığında
                worker = threading.Thread(target=self.loop, daemon=True)
                worker.start()
                try:
                    window.run(url, window.title(self.demo), os.path.join(self.home_dir, "arayuz"),
                               on_closed=lambda: self.shutdown(httpd, fast_exit=True))
                except Exception as ex:
                    print(f"Uygulama penceresi açılamadı ({ex}); tarayıcı penceresine geçiliyor.")
                    open_app_window(url)
                    while worker.is_alive():
                        worker.join(0.5)
            else:
                if self.open_window:
                    open_app_window(url)
                self.loop()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown(httpd)

    def shutdown(self, httpd, fast_exit=False):
        """Kaydedip kapatır (bir kez). fast_exit: pencere kapanınca çağrılır; kayıttan sonra süreç hemen biter."""
        with self._shutdown_lock:
            if self._shut:
                return
            self._shut = True
        t0 = time.perf_counter()
        self.running = False
        self._ui_push()   # canlı akıştaki pencere bağlantıları beklemeden kapansın
        with self.lock:
            self.save()
        t1 = time.perf_counter()
        self.drive.stop()
        self.film.stop()
        self.bridge.close()
        httpd.shutdown()
        t2 = time.perf_counter()
        print(f"Kaydedildi, çıkılıyor. (kayıt {(t1 - t0) * 1000:.0f} ms, sunucu {(t2 - t1) * 1000:.0f} ms)", flush=True)
        if fast_exit:
            hard_exit()


def hard_exit(code=0):
    """Her şey kaydedildikten sonra süreci hemen bitirir. Normal çıkışta Windows yüklü .NET/WebView2
    bileşenlerini kapatırken ~2 sn bekler; pencere kaybolsa da süreç yaşar ve kısayol "zaten açık" sanar."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.flush()
        except Exception:
            pass
    if sys.platform == "win32":
        import ctypes
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        k.TerminateProcess(k.GetCurrentProcess(), code)
    os._exit(code)


class ExclusiveHTTPServer(ThreadingHTTPServer):
    """Windows'ta SO_REUSEADDR aynı portu ikinci bir sürece de verir; bu yüzden port özel olarak alınır."""
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def open_app_window(url):
    """Edge/Chrome'u adres çubuğu olmayan uygulama penceresi olarak açar."""
    candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        shutil.which("msedge") or "", shutil.which("chrome") or "",
    ]
    for exe in candidates:
        if exe and os.path.isfile(exe):
            try:
                subprocess.Popen([exe, f"--app={url}", "--window-size=1500,950"])
                return
            except OSError:
                pass
    webbrowser.open(url)


MAX_POST_BYTES = 1 << 20   # arayüzün istekleri birkaç KB; daha büyüğü okunmaz


def make_handler(app):
    mime = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
            ".ico": "image/x-icon", ".json": "application/json"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode())

        def _stream(self):
            """Server-Sent Events: pencere durumu yoklamadan, yayınlandığı anda alır (Ayarlar → Değer güncelleme sıklığı).
            Pencere bağlantıyı kapatınca (sayfa gizlendi, uygulama kapandı) biter; 15 sn'de bir boş satır gider ki
            kopan bağlantı fark edilsin. Tarayıcı kopan akışa 1 sn sonra kendiliğinden yeniden bağlanır."""
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            seen = -1
            try:
                self.wfile.write(b"retry: 1000\n\n")
                self.wfile.flush()
                while app.running:
                    ver, body = app.wait_ui(seen, 15.0)
                    if body is None:
                        self.wfile.write(b": \n\n")
                    else:
                        seen = ver
                        self.wfile.write(b"data: " + body + b"\n\n")
                    self.wfile.flush()
            except (OSError, ValueError):
                pass   # pencere bağlantıyı kapattı

        def _host_ok(self):
            """Yalnızca 127.0.0.1:<port> ve localhost:<port>. DNS yeniden bağlamayla (rebinding) başka bir sitenin adı
            bu sunucuya yönlendirilse de tarayıcı o sitenin adını Host başlığında gönderir: istek reddedilir, site
            /api/state gibi verileri okuyamaz."""
            port = self.server.server_address[1]
            return (self.headers.get("Host") or "").strip().lower() in (f"127.0.0.1:{port}", f"localhost:{port}")

        def do_GET(self):
            if not self._host_ok():
                return self._json(403, {"ok": False, "message": "izin yok"})
            path = urlparse(self.path).path
            if path == "/api/state":
                return self._send(200, app.state_json)
            if path == "/api/stream":   # canlı akış: durum seçilen aralıkta (gerçek zamanlıda her adımda) gelir
                return self._stream()
            if path == "/api/detail":
                return self._send(200, app.detail_json)
            if path == "/api/alerts":   # Ayarlar'daki uyarı ve ikaz lambası listesi (seçili dilde)
                return self._json(200, alerts.catalog())
            if path == "/api/film":     # Ayarlar → Çekim modu: tetiklenebilecek arızalar (seçili dilde, bu araca göre)
                with app.lock:
                    t = app.truck if app.truck is not None and app.truck.initialized else None
                    data = filming.catalog(t)
                return self._json(200, data)
            if path == "/api/history":
                with app.lock:
                    data = list(app.history)
                return self._json(200, data)
            if path == "/":
                path = "/index.html"
            fp = os.path.normpath(os.path.join(WEB_DIR, path.lstrip("/")))
            if not fp.startswith(WEB_DIR) or not os.path.isfile(fp):
                return self._send(404, b"not found", "text/plain")
            with open(fp, "rb") as fh:
                body = fh.read()
            if path == "/index.html":
                # sayfa ilk açılışta seçili dilde başlasın (ilk durum yanıtını beklerken Türkçe görünmesin)
                body = body.replace(b'<html lang="tr">', f'<html lang="{i18n.LANG}">'.encode(), 1)
            self._send(200, body, mime.get(os.path.splitext(fp)[1], "application/octet-stream"))

        def do_POST(self):
            # gövde her yanıttan önce okunur: okunmadan kapanan bağlantıyı Windows sıfırlar, istemci 403 yerine bağlantı
            # hatası görür (negatif ya da çok büyük uzunluk okunmaz: bağlantı kapanana kadar beklemesin)
            try:
                n = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                n = -1
            if not 0 <= n <= MAX_POST_BYTES:
                return self._json(413 if n > 0 else 400, {"ok": False, "message": "geçersiz istek"})
            raw = self.rfile.read(n) if n else b""
            if not self._host_ok():
                return self._json(403, {"ok": False, "message": "izin yok"})
            path = urlparse(self.path).path
            # yalnızca kendi arayüzümüzden gelen istekler (başka sitelerin yerel API'ye yazmasını engeller)
            port = self.server.server_address[1]
            origin = self.headers.get("Origin")
            if origin and origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
                return self._json(403, {"ok": False, "message": "izin yok"})
            try:
                body = json.loads(raw or b"{}")
            except (ValueError, json.JSONDecodeError):
                return self._json(400, {"ok": False, "message": "geçersiz istek"})
            if path == "/api/action":
                ok, msg = app.do_action(body.get("name", ""), body.get("params", {}))
            elif path == "/api/settings":
                ok, msg = app.update_settings(body)
            elif path == "/api/spec":
                ok, msg = app.update_spec(body)
            elif path == "/api/sound_test":
                ok, msg = app.sound_test(body.get("level", "crit"))
            elif path == "/api/drive_capture":
                ok, msg = app.drive_capture(bool(body.get("start", True)))
            elif path == "/api/film":
                ok, msg = app.film_action(body.get("op", ""), body.get("item"))
            elif path == "/api/film_capture":
                ok, msg = app.film_capture(bool(body.get("start", True)))
            elif path == "/api/update":
                ok, msg = app.update_action(body.get("op", ""))
            else:
                return self._json(404, {"ok": False, "message": "yok"})
            self._json(200, {"ok": ok, "message": msg})

    return Handler
