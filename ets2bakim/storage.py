"""Kamyon durumlarını ve ayarları JSON olarak saklar (atomik yazma)."""
import json
import os
import re
import time

DEFAULT_SETTINGS = {
    "game_mode": "auto",           # oyun modu: auto (TruckersMP / Konvoy algılanınca Çok Oyunculu) | tek | cok
    "climate_mode": "auto",        # auto | month | fixed
    "climate_month": 1,
    "climate_fixed_c": 15.0,
    "weather_variability": True,
    "random_faults": True,
    "mp_watch_mode": "show",       # Çok Oyunculu mod: show (sadece gösterme) | full (tam izleme: arızada motor durur)
    "engine_key": "e",
    "hotel_load": True,
    "auto_service_on_repair": False,
    "repair_faults_on_game_repair": True,   # oyundaki serviste tamir yaptırınca simüle arızalı parçalar da onarılır
    "sound": True,
    "sound_brand": "auto",         # uyarı sesi: auto (tırın markasına göre) | sounds.BRANDS'tan biri
    "currency_mode": "auto",       # auto: oyunda seçili para birimi ve oyunun kuru · manual: aşağıdaki simge ve kur
    "currency": "€",               # elle: simge
    "currency_rate": 1.0,          # elle: 1 € = ? (uygulamanın fiyatları avro tabanlı)
    "language": "tr",              # tr | en | de
    "alert_level": "normal",       # minimal: yalnızca kritik · normal: kritik + dikkat (şerit/ses yalnız kritik) · all
    "fuel_price": 1.65,            # yolculuk maliyeti için, € / litre (gösterimde seçili para birimine çevrilir)
    "reset_temp_trucks": True,     # hızlı iş (geçici) tırların değerleri teslimatta sıfırlanır
    "hide_with_hud": True,         # oyunda HUD gizlenince (F3) katman da gizlenir
    "telltales": True,             # katmanda sanal gösterge lambaları (alt orta)
    "lamp_level": "onemsiz",       # gösterilecek lambalar: bu önem derecesi ve üstü (onemsiz|onemli|uyari|ciddi|kritik)
    "overlay_key": 0x77,           # katmanın tuşu (sanal tuş kodu, varsayılan F8); Shift/Ctrl/Alt kombinasyonları bununla
    "overlay_panel": "auto",       # oyun içi panel: auto (OptiScaler / DLSS 5 ya da donma görülürse kurulmaz) | on | off
    "update_check": True,          # açılışta yeni sürümü denetle (Drive'daki surum.json; Ayarlar → Genel → Güncelleme)
    "warnings_off": [],            # Ayarlar'da tek tek kapatılan uyarıların anahtarları (alerts.GROUPS)
    "lamps_off": [],               # kapatılan ikaz lambaları (telltales.ORDER kimlikleri)
    "adblue_with_fuel": True,      # oyunda yakıt alınınca AdBlue da pompadan tamamlanır
    "blowout_effect": True,        # tek oyunculu: lastik patlayınca oyunda ani sürüklenme, kayma, jant sürtmesi
    # azalma hızları (rates.py): 1 = gerçekçi, 0,5 = yarı hızda, 0 = hiç azalmaz; etkin hız = genel × sistem
    "rate_global": 1.0,
    "rate_oil": 1.0,               # yağ ömrü, değişim aralığı, yağ tüketimi, filtre
    "rate_coolant": 1.0,           # antifriz inhibitörü, değişim aralığı, kireçlenme, buharlaşma
    "rate_battery": 1.0,           # akü sağlığı, sülfatlaşma, kendi kendine boşalma
    "rate_drain": 1.0,             # akü boşalması (elektrik yükleri)
    "rate_tires": 1.0,             # lastik diş aşınması, doğal basınç kaybı
    "rate_dpf": 1.0,               # DPF is ve kül dolması
    "rate_adblue": 1.0,            # AdBlue tüketimi
    "rate_engine": 1.0,            # motorun normal aşınması
    "rate_transmission": 1.0,      # debriyaj balatası aşınması, şanzıman yağının yaşlanması
    "rate_faults": 1.0,            # rastgele arıza ve patlak sıklığı
    # sürüş modları (drivemode.py; oyun içi katman 1.8+ gazı moda göre düzeltir)
    "drive_modes": True,
    "drive_mode": "comfort",       # eco | comfort | sport
    "drive_mode_key": "key:121",   # mod değiştirme tuşu: key:<sanal tuş> | btn:<düğme> | pov:<yön> | "" (F10)
    # çekim modu (filming.py; yalnızca tek oyunculu): seçili arızayı düğmeyle ya da kısayol tuşuyla tetikler
    "film_mode": False,
    "film_fault": "oil_pump",      # filming.IDS
    "film_key": "",                # kısayol tuşu (sürüş modu tuşuyla aynı biçim); varsayılan yok: oyunda F tuşları dolu
    # değer güncelleme sıklığı (sn; 0 = gerçek zamanlı: simülasyon saniyede 20 adım, her adım yayınlanır). Uyarılar ve
    # ikaz lambaları seçilen aralığı beklemez. Varsayılanlar 1.3.1'deki hızlar: pencere 4/sn, oyun içi katman 10/sn.
    "ui_interval": 0.25,           # uygulama penceresi
    "overlay_interval": 0.1,       # oyun içi katman
}

GAME_MODES = ("auto", "tek", "cok")
UPDATE_INTERVALS = (0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0)   # Ayarlar → Değer güncelleme sıklığı seçenekleri (sn)
# Tek ve Çok Oyunculu mod kendi ayarlarını ve tır kayıtlarını ayrı klasörde saklar; bu ayarlar ikisinde ortaktır
# (güncelleme sıklığı bilgisayarın tercihi: modla değişmez)
SHARED_KEYS = ("language", "game_mode", "ui_interval", "overlay_interval")
# Çok Oyunculu modun farklı varsayılanları: sürüş modları (gaz pedalına müdahale) kapalı gelir
MP_DEFAULTS = {"drive_modes": False}


def profile_dir(home, mode):
    """Modun veri klasörü: Tek Oyunculu home (data, data_demo), Çok Oyunculu home_mp (data_mp, data_demo_mp)."""
    home = os.path.normpath(home)
    return home + "_mp" if mode == "cok" else home


class Storage:
    def __init__(self, base_dir):
        self.base = base_dir
        self.trucks_dir = os.path.join(base_dir, "trucks")
        os.makedirs(self.trucks_dir, exist_ok=True)

    def _write(self, path, data):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        # Windows'ta virüs tarayıcısı ya da dizin oluşturucu dosyayı kısa süre açık tutabilir: birkaç kez yeniden dene
        for attempt in range(4):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 3:
                    raise
                time.sleep(0.05 * (attempt + 1))

    def _read(self, path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    @staticmethod
    def slug(key):
        s = re.sub(r"[^A-Za-z0-9._-]+", "_", key).strip("_")
        return s[:120] or "kamyon"

    def truck_path(self, key):
        return os.path.join(self.trucks_dir, self.slug(key) + ".json")

    def load_truck(self, key):
        return self._read(self.truck_path(key))

    def save_truck(self, key, data):
        self._write(self.truck_path(key), data)

    def delete_truck(self, key):
        try:
            os.remove(self.truck_path(key))
        except OSError:
            pass

    def load_settings(self, defaults=None):
        """defaults: modun farklı varsayılanları (Çok Oyunculu için MP_DEFAULTS)."""
        s = {k: list(v) if isinstance(v, list) else v for k, v in DEFAULT_SETTINGS.items()}  # listeler paylaşılmasın
        s.update(defaults or {})
        s.update(self._read(os.path.join(self.base, "ayarlar.json")) or {})
        s.pop("enforce", None)  # eski "motoru zorla durdur" ayarı: tek oyunculuda artık her zaman tam izleme
        return s

    def save_settings(self, s):
        self._write(os.path.join(self.base, "ayarlar.json"), s)

    def load_global(self):
        return self._read(os.path.join(self.base, "genel.json")) or {}

    def save_global(self, d):
        self._write(os.path.join(self.base, "genel.json"), d)
