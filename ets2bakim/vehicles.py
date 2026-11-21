"""Araç sınıfları: tır, otobüs ve otomobil.

TruckersMP oyuna kendi araçlarını ekler: Škoda Superb ve Scout Extra_D Estate otomobilleri (vehicle.skoda.superb /
superb2; 1.8 TSI benzinli ya da 2.0 TDI dizel) ve HVT Tourvego 16 SHD otobüsü (vehicle.t16shd; OM 470, 24 V, AdBlue).
Telemetri bunları tır gibi bildirir; sınıf motor veritabanındaki modelden (engines.MODELS) gelir.

Otobüs tır gibi modellenir (24 V, dizel, 22,5" lastik); yolcu kliması/ısıtması için elektrik yükü daha yüksektir.
Otomobil: 12 V tek akü (start-stop AGM), daha küçük alternatör ve marş akımı, otomobil yağları (VW 504/507, 508/509,
502/505), G13 antifriz, 4 tekil lastik (ön/arka, ~2,5 bar, 8 mm diş), bağımsız oto servisi fiyatları; benzinli
motorda DPF, AdBlue ve ön ısıtma yoktur. TruckersMP otomobilinin oyun içi devir ölçeği tır gibidir (rölanti 500–700,
tork tepesi 1000–1300, sınır 3000 rpm); motor modeli bu ölçekte çalışır, gösterilen güç ve tork gerçek değerlerdir.

Tek oyunculu otomobil / otobüs modlarını (Togg, Passat, otobüsler…) telemetri tır gibi bildirir ve model veritabanı
tanımaz: Ayarlar → Araç tipi ile sınıf elle seçilir (spec.vehicle_override; "auto" = algılanan). Gerçek otomobil devir
ölçeğiyle (sınır 3000 rpm üstü) çalışan modlarda motor modeline devir rpm_scale() oranında küçültülerek verilir.
"""
KINDS = ("truck", "bus", "car")
CHOICES = ("auto",) + KINDS          # Ayarlar → Araç tipi
NAMES = {"truck": "Tır", "bus": "Otobüs", "car": "Otomobil"}
CAR_MODEL_RPM_MAX = 3000.0           # otomobil motor modelinin devir ölçeği (TruckersMP otomobilinin oyun içi sınırı)
BATTERY_SIZES = {"car": (60, 68, 72, 74, 80, 85, 95, 105)}
TRUCK_BATTERY_SIZES = (140, 155, 170, 180, 190, 200, 210, 220, 225, 230, 235, 240)
DEFAULT_OIL = {"car": "5w30vw"}
DEFAULT_COOLANT = {"car": "si_oat"}
DEFAULT_BATTERY_KIND = {"car": "agm"}
LOAD_SCALE = {"car": 0.6, "bus": 1.25}      # elektrik yükü (tıra göre)
# Ayarlar'da elle girilen kamyon özelliklerinin sınırları: form alanı -> (en az, en çok, adım). Devir oyun içi ölçektedir
# (otomobilde de tır gibi); otomobilin torku yalnızca gösterilir (model torku oyun içi devir ölçeğinde güçten türetir).
_TRUCK_LIMITS = dict(power_hp=(200, 820, 10), torque_nm=(0, 4500, 50), rated_rpm=(1300, 2300, 50),
                     displacement_l=(7, 17, 0.1), oil_capacity_l=(15, 60, 1), coolant_capacity_l=(25, 120, 1),
                     battery_ah=(100, 300, 5))
SPEC_LIMITS = {"truck": _TRUCK_LIMITS, "bus": _TRUCK_LIMITS,
               "car": dict(power_hp=(60, 400, 5), torque_nm=(0, 700, 10), rated_rpm=(1300, 2300, 50),
                           displacement_l=(0.9, 4.0, 0.1), oil_capacity_l=(3, 10, 0.1), coolant_capacity_l=(4, 15, 0.5),
                           battery_ah=(40, 120, 1))}


def kind_of(spec):
    """Araç sınıfı: Ayarlar → Araç tipi seçimi, "Otomatik"te motor veritabanındaki modelden algılanan."""
    k = getattr(spec, "vehicle_override", "auto")
    if k not in KINDS:
        k = getattr(spec, "vehicle", "truck")
    return k if k in KINDS else "truck"


def rpm_scale(kind, rpm_max):
    """Oyun devrinin motor modeline oranı. Otomobil modeli tır gibi devir ölçeğinde (sınır 3000) çalışır; daha yüksek
    sınırla, ör. gerçek otomobil devriyle (6000–7000 rpm) gelen modlarda devir bu oranla küçültülür. Tır, otobüs ve
    TruckersMP otomobili: 1."""
    if kind == "car" and rpm_max > CAR_MODEL_RPM_MAX:
        return rpm_max / CAR_MODEL_RPM_MAX
    return 1.0


def volts(kind):
    return 12 if kind == "car" else 24


def spec_limits(kind):
    return SPEC_LIMITS.get(kind, _TRUCK_LIMITS)


def battery_sizes(kind):
    return BATTERY_SIZES.get(kind, TRUCK_BATTERY_SIZES)


def load_scale(kind):
    return LOAD_SCALE.get(kind, 1.0)


def has_hotel_load(kind):
    """Uykuda park ısıtıcısı / kliması (otomobilde yok)."""
    return kind != "car"
