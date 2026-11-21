"""Sanal gösterge lambaları (oyun içi katmanın alt ortasındaki ikaz şeridi).

Oyunun kendi gösterge panelindeki ikaz lambaları oyunun iç değerlerine bağlıdır: SCS SDK kamyon değerlerini
yalnızca okumaya izin verir, panel lambası dışarıdan yakılamaz. Bu yüzden simülatörün bulduğu sorunlar katmanda
gerçek kamyon göstergesindeki gibi bir lamba şeridiyle gösterilir.

Lambalar gerçek araçtaki gibi sensörlerin göreceği şeye göre yanar: örneğin sızdıran su pompası seviye düşene kadar
lamba yakmaz, alternatör arızası ise şarj lambasını hemen yakar. Kontak kapalıyken gösterge karanlıktır. Yalnızca sarı
ve kırmızı ikaz lambaları vardır; yeşil / mavi / beyaz bilgi lambaları (sinyal, far, hız sabitleyici…) oyunun kendi
göstergesinde zaten görünür.

Önem dereceleri (Ayarlar → Gösterilecek lambalar: seçilen derece ve üstü yanar):
  1 önemsiz  bilgi: ön ısıtma sürüyor, DPF rejenerasyonu
  2 önemli   bakım zamanı: yağ / şanzıman yağı değişimi, debriyaj balatası, lastik dişi, akü sağlığı, motor sağlığı
  3 uyarı    sarı arıza ve sınır değerler: ABS, marş, park freni çekilmedi, sıcaklık yüksek, seviye düşük, yakıt az
  4 ciddi    kırmızı: şarj yok, fren aşırı sıcak, hava basıncı düşük, park freni çekiliyken hareket, direksiyon
             desteği yok, şanzıman / debriyaj aşırı sıcak, lastik patladı, DPF tıkalı, AdBlue bitti, donma
  5 kritik   motoru hemen durdurun: STOP, yağ basıncı, hararet ve kaynama, motor kilitlendi
Renk dereceden gelir: ciddi ve kritik kırmızı, diğerleri sarı. Kırmızı lambalar yanınca katmanda birkaç saniye, STOP
ise sürekli yanıp söner.
"""
import time

from .i18n import T
from .levels import _worst, value_levels

# katmandaki sıra (soldan sağa)
ORDER = ("stop", "batt", "glow", "start", "oil", "cool", "brake", "park", "abs", "steer", "gear", "tire", "eng", "dpf",
         "adblue", "fuel", "frost", "svc")
LABELS = {"stop": "DURUN", "batt": "AKÜ", "glow": "ISITMA", "start": "MARŞ", "oil": "YAĞ", "cool": "SOĞUTMA",
          "brake": "FREN", "park": "EL FRENİ", "abs": "ABS", "steer": "DİREKSİYON", "gear": "ŞANZIMAN",
          "tire": "LASTİK", "eng": "MOTOR", "dpf": "DPF", "adblue": "ADBLUE", "fuel": "YAKIT", "frost": "DONMA",
          "svc": "BAKIM"}
# önem dereceleri (ayar değeri -> derece) ve ciddi'den itibaren kırmızı
LEVELS = ("onemsiz", "onemli", "uyari", "ciddi", "kritik")
LEVEL_NAMES = {"onemsiz": "Önemsiz", "onemli": "Önemli", "uyari": "Uyarı", "ciddi": "Ciddi", "kritik": "Kritik"}
MINOR, NOTABLE, WARN, SERIOUS, CRITICAL = 1, 2, 3, 4, 5
# motor kontrol ünitesinin hata kodu olarak bildirdiği arızalar (diğerleri ancak belirtisi ölçülünce görünür)
ENGINE_FAULTS_STOP = {"engine_seized", "block_cracked"}
ENGINE_FAULTS_WARN = {"thermostat_open", "fan_clutch"}
BATTERY_FAULTS = {"alternator", "battery_frozen"}
TRANS_FAULTS = {"gearbox_cooler", "clutch_actuator"}   # şanzıman kontrol ünitesinin hata kodları
HOLD_S = 2.0  # eşik çevresinde titreşmesin diye yanan lamba en az bu kadar yanık kalır (derecesi hemen düşmez)


def min_rank(level):
    """Ayar değerinden ('onemsiz' … 'kritik') gösterilecek en düşük derece; bilinmeyen değer: hepsi."""
    return LEVELS.index(level) + 1 if level in LEVELS else MINOR


def color(rank):
    """Derecenin lamba rengi: 'c' kırmızı (ciddi, kritik) ya da 'w' sarı."""
    return "c" if rank >= SERIOUS else "w"


def ranks(S):
    """Yanması gereken lambalar ve önem dereceleri: {kimlik: 1..5}. Kontak kapalıysa None (gösterge karanlık)."""
    L = S["live"]
    if not (L.get("electric_on") or L.get("engine_on")):
        return None
    lv = S.get("levels") or value_levels(S)
    o, th, d = S["oil"], S["thermal"], S["dpf"]
    running = L.get("running")
    speed = L.get("speed") or 0
    faults = {f["key"] for f in S.get("faults", [])}
    out = {}

    def lamp(key, rank):
        if rank:
            out[key] = max(out.get(key, 0), rank)

    def by(level, warn_rank, crit_rank):
        """value_levels seviyesinden (w sınırda, c kritik) derece."""
        return crit_rank if level == "c" else warn_rank if level == "w" else 0

    # STOP: motoru hemen durdurmayı gerektiren durumlar
    ty = S.get("tires") or {}
    if L.get("killed") and L.get("engine_on"):
        lamp("stop", CRITICAL)
    if running and lv.get("oil.pressure") == "c":
        lamp("stop", CRITICAL)
    if lv.get("thermal.t_cool") == "c" or th.get("boiling"):
        lamp("stop", CRITICAL)
    if ty.get("blown") and speed > 3:
        lamp("stop", CRITICAL)                 # patlak lastikle hareket
    if L.get("air_emergency") and speed > 3:
        lamp("stop", CRITICAL)                 # fren havası bitiyor: yay frenleri devreye giriyor

    # akü / şarj
    if faults & BATTERY_FAULTS or (running and lv.get("battery.voltage") == "c"):
        lamp("batt", SERIOUS)
    if not running and lv.get("battery.min_start_soc") == "c":
        lamp("batt", SERIOUS)
    lamp("batt", by(lv.get("battery.soc"), 0, WARN))
    lamp("batt", by(lv.get("battery.temp"), 0, WARN))
    lamp("batt", by(lv.get("battery.soh"), 0, NOTABLE))

    # ön ısıtma (kızdırma): ısıtma sürerken yanar, sönünce marşa basılır (bilgi); arızada yanıp söner
    ph = S.get("preheat") or {}
    if ph.get("fault"):
        lamp("glow", SERIOUS if ph.get("needed") else NOTABLE)
    elif ph.get("active"):
        lamp("glow", MINOR)

    # marş motoru (arıza kodu)
    if "starter" in faults:
        lamp("start", WARN)

    # yağ basıncı / seviyesi
    if running and lv.get("oil.pressure") == "c":
        lamp("oil", CRITICAL)
    lamp("oil", by(lv.get("oil.level_pct"), WARN, SERIOUS))

    # soğutma: sıcaklık ve seviye
    lamp("cool", by(lv.get("thermal.t_cool"), WARN, CRITICAL))
    lamp("cool", by(lv.get("coolant.level_pct"), WARN, SERIOUS))
    if th.get("boiling"):
        lamp("cool", CRITICAL)

    # fren: sıcaklık (uyarı metinleriyle aynı eşikler) ve devre hava basıncı (oyunun düşük basınç uyarısı)
    bt = L.get("brake_temp") or 0
    lamp("brake", SERIOUS if bt >= 450 else WARN if bt >= 320 else 0)
    if L.get("air_warning"):
        lamp("brake", SERIOUS)

    # park freni: çekiliyken hareket ya da motor kapalıyken çekilmeden bırakılan tır
    if L.get("park_moving"):
        lamp("park", SERIOUS)
    elif L.get("park_warn"):
        lamp("park", WARN)

    # ABS (tekerlek hızı sensörü arıza kodu)
    if "abs_sensor" in faults:
        lamp("abs", WARN)

    # direksiyon: hidrolik destek motorla döner; motor dururken giderken ya da yağ azken destek yok
    st = S.get("steering") or {}
    if st.get("hydraulic"):
        if not running and speed > 5:
            lamp("steer", SERIOUS)
        lamp("steer", by(lv.get("steering.fluid"), WARN, SERIOUS))
        if st.get("leak"):
            lamp("steer", WARN)

    # şanzıman: yağ ve debriyaj sıcaklığı, balata, arıza kodları, yağ değişimi, oyunun şanzıman hasarı (%30+)
    tr = S.get("trans") or {}
    lamp("gear", by(lv.get("trans.t_oil"), WARN, SERIOUS))
    lamp("gear", by(lv.get("trans.t_clutch"), WARN, SERIOUS))
    lamp("gear", by(lv.get("trans.clutch_wear"), NOTABLE, SERIOUS))
    if faults & TRANS_FAULTS:
        lamp("gear", WARN)
    if (tr.get("oil_used") or 0) >= 100 or (tr.get("game_wear") or 0) >= 30:
        lamp("gear", NOTABLE)

    # lastik basınç izleme (TPMS): patlak / basınç, sıcaklık, diş (dingil başına)
    for g in ty.get("groups", []):
        glv = g.get("lv") or {}
        if g.get("blown"):
            lamp("tire", SERIOUS)
            continue
        lamp("tire", by(glv.get("pressure"), WARN, SERIOUS))
        lamp("tire", by(glv.get("temp"), WARN, SERIOUS))
        lamp("tire", by(glv.get("tread"), NOTABLE, SERIOUS))

    # motor arıza lambası
    if L.get("killed") or faults & ENGINE_FAULTS_STOP:
        lamp("eng", CRITICAL)
    if "head_gasket" in faults:
        lamp("eng", SERIOUS)
    if faults & ENGINE_FAULTS_WARN or lv.get("live.exh") == "c":
        lamp("eng", WARN)
    lamp("eng", by(lv.get("engine.health"), 0, NOTABLE))

    # DPF
    if d.get("enabled"):
        soot = d.get("soot") or 0
        lamp("dpf", SERIOUS if soot >= 120 else WARN if soot >= 100 else 0)
        lamp("dpf", by(lv.get("dpf.backpressure"), 0, WARN))
        lamp("dpf", by(lv.get("dpf.ash"), 0, NOTABLE))
        if d.get("regen") or d.get("burning"):
            lamp("dpf", MINOR)

    # AdBlue ve yakıt
    if (S.get("adblue") or {}).get("enabled"):
        ab = S["adblue"].get("pct") or 0
        lamp("adblue", SERIOUS if ab <= 0 else WARN if ab < 10 else 0)
    fu = S.get("fuel") or {}
    if fu.get("pct") is not None and (fu.get("game_warning") or fu["pct"] < max(15.0, fu.get("warn_pct") or 15.0)):
        lamp("fuel", WARN)

    # donma: antifriz yetersiz ya da sistemde buz
    lamp("frost", by(lv.get("coolant.freeze"), WARN, SERIOUS))
    lamp("frost", by(_worst(lv.get("thermal.block_ice", "g"), lv.get("thermal.rad_ice", "g")), WARN, SERIOUS))

    # bakım zamanı
    if (o.get("life") or 0) <= 0:
        lamp("svc", SERIOUS)
    if "c" in (lv.get("oil.life"), lv.get("oil.km"), lv.get("oil.filter_pct"), lv.get("coolant.inhibitor"),
               lv.get("coolant.age_days"), lv.get("coolant.km")):
        lamp("svc", NOTABLE)
    return out


def compute(S):
    """Yanması gereken lambalar ve renkleri: {kimlik: 'w' | 'c'}. Kontak kapalıysa None."""
    r = ranks(S)
    return None if r is None else {k: color(v) for k, v in r.items()}


class Telltales:
    """Lambaların yanık kalma süresini (titreşme önleme) ve önem süzgecini yönetir."""

    def __init__(self):
        self.lit = {}  # kimlik -> (derece, o derecenin en son gerektiği an)

    def update(self, S, now=None, min_level="onemsiz"):
        """Gösterilecek lambalar [(kimlik, renk)] ORDER sırasıyla; min_level altındaki dereceler gösterilmez."""
        now = time.monotonic() if now is None else now
        cur = ranks(S)
        if cur is None:  # kontak kapandı: gösterge hemen kararır
            self.lit.clear()
            return []
        for k, rank in cur.items():
            old = self.lit.get(k)
            if old and rank < old[0] and now - old[1] < HOLD_S:
                continue  # derecesi hemen düşmesin (ör. kırmızıdan sarıya)
            self.lit[k] = (rank, now)
        for k in [k for k, (_, t) in self.lit.items() if k not in cur and now - t >= HOLD_S]:
            del self.lit[k]
        lo = min_rank(min_level)
        return [(k, color(self.lit[k][0])) for k in ORDER if k in self.lit and self.lit[k][0] >= lo]

    @staticmethod
    def label(key):
        return T(LABELS.get(key, key))
