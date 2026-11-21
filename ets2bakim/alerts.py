"""Uyarı ve ikaz lambası kataloğu: Ayarlar → "Uyarılar ve ikaz lambaları" (her biri tek tek açılıp kapatılır).

Her uyarının kalıcı bir anahtarı vardır (view.warnings içinde add(seviye, anahtar, metin, ...)); metin değişse de
kaydedilmiş ayar bozulmaz. Kapatılan uyarılar (ayar "warnings_off") ne uygulama penceresinin listesinde ne oyun içi
katmanda görünür, ses de çıkarmaz. Kapatılan ikaz lambaları ("lamps_off") katmanın lamba şeridinde yanmaz.
Yalnızca gösterim değişir: simülasyon (aşınma, arızalar, motor durdurma) aynen sürer. Uyarı düzeyi (alert_level) ve
lamba önem süzgeci (lamp_level) bunlara ek olarak uygulanır.
"""
from .faults import FAULTS
from .i18n import T
from .telltales import LABELS as LAMP_LABELS, ORDER as LAMP_ORDER

# (grup anahtarı, grup adı, ((uyarı anahtarı, en yüksek seviyesi, kısa ad), ...)) — Ayarlar'daki sırayla
GROUPS = (
    ("engine", "Motor ve sürüş", (
        ("engine_dead", "crit", "Motor gerçekte çalışmıyor"),
        ("engine_health", "warn", "Motor sağlığı düşük (revizyon yaklaşıyor)"),
        ("overrev", "warn", "Aşırı devir"),
        ("lugging", "info", "Düşük devirde tam yük (lugging)"),
        ("cold_load", "info", "Soğuk motora yüklenme"),
        ("idling", "info", "Uzun süre rölanti"),
        ("preheat", "info", "Ön ısıtma yapılıyor"),
        ("electric", "info", "Elektrikli kamyon bilgisi"),
    )),
    ("oil", "Motor yağı", (
        ("oil_pressure", "crit", "Yağ basıncı düşük"),
        ("oil_level_crit", "crit", "Yağ seviyesi kritik"),
        ("oil_level_low", "warn", "Yağ seviyesi MIN altında"),
        ("oil_level_high", "warn", "Yağ seviyesi MAX üstünde"),
        ("oil_life_end", "crit", "Yağ ömrü bitti"),
        ("oil_life_low", "warn", "Yağ değişimi yaklaşıyor"),
        ("oil_filter", "warn", "Yağ filtresi tıkalı"),
        ("oil_glycol", "crit", "Yağda soğutma suyu (glikol)"),
    )),
    ("cooling", "Soğutma ve donma", (
        ("coolant_boiling", "crit", "Soğutma suyu kaynıyor"),
        ("overheat", "crit", "Hararet"),
        ("engine_hot", "warn", "Motor sıcaklığı yüksek"),
        ("retarder_heat", "info", "Retarder hararet yapıyor"),
        ("coolant_level_crit", "crit", "Soğutma suyu çok az"),
        ("coolant_level_low", "warn", "Soğutma suyu seviyesi düşük"),
        ("freezing", "crit", "Antifriz donuyor"),
        ("antifreeze_low", "warn", "Antifriz yetersiz (beklenen soğuğa göre)"),
        ("icing", "crit", "Soğutma sisteminde buzlanma"),
        ("inhibitor", "warn", "Antifriz inhibitörü tükendi"),
        ("scale", "info", "Radyatör / blok kireçlenmiş"),
    )),
    ("battery", "Akü ve elektrik", (
        ("no_charge", "crit", "Şarj yok"),
        ("alternator_load", "info", "Alternatör yükü karşılayamıyor"),
        ("crank_fail", "crit", "Akü motoru çeviremez"),
        ("oil_too_thick", "crit", "Yağ marş için çok koyu"),
        ("crank_weak", "info", "Zayıf marş bekleniyor"),
        ("ignition_drain", "warn", "Kontak açık, akü boşalıyor"),
        ("battery_low", "warn", "Akü şarjı düşük"),
        ("battery_health", "warn", "Akü sağlığı zayıf"),
        ("battery_freeze", "warn", "Akü donma riski"),
    )),
    ("brakes", "Frenler, hava ve park freni", (
        ("brakes_overheat", "crit", "Frenler aşırı ısındı"),
        ("brakes_hot", "warn", "Fren sıcaklığı yüksek"),
        ("air_pressure", "crit", "Hava basıncı düşük"),
        ("park_moving", "crit", "Park freni çekiliyken hareket"),
        ("park_not_set", "warn", "Park freni çekilmedi"),
    )),
    ("steering", "Direksiyon", (
        ("steer_no_assist", "crit", "Direksiyon desteği yok (motor çalışmıyor)"),
        ("steer_fluid", "crit", "Direksiyon hidrolik yağı çok az"),
    )),
    ("gearbox", "Şanzıman ve debriyaj", (
        ("gear_oil_crit", "crit", "Şanzıman yağı aşırı sıcak"),
        ("gear_oil_hot", "warn", "Şanzıman yağı sıcak"),
        ("clutch_overheat", "crit", "Debriyaj aşırı ısındı"),
        ("clutch_hot", "warn", "Debriyaj ısınıyor"),
        ("clutch_worn", "crit", "Debriyaj balatası bitti"),
        ("clutch_wear", "warn", "Debriyaj balatası aşınıyor"),
        ("gear_oil_change", "warn", "Şanzıman yağı değişim zamanı"),
    )),
    ("dpf", "DPF (partikül filtresi)", (
        ("dpf_blocked", "crit", "DPF tıkalı"),
        ("dpf_full", "warn", "DPF dolu"),
        ("dpf_ash", "warn", "DPF kül temizliği gerekli"),
        ("dpf_regen", "info", "DPF rejenerasyon yapıyor"),
        ("dpf_regen_wait", "info", "DPF rejenerasyon bekliyor"),
    )),
    ("fuel", "Yakıt ve AdBlue", (
        ("fuel_crit", "crit", "Yakıt bitmek üzere"),
        ("fuel_low", "warn", "Yakıt azaldı"),
        ("adblue_empty", "crit", "AdBlue bitti"),
        ("adblue_crit", "crit", "AdBlue bitmek üzere"),
        ("adblue_low", "warn", "AdBlue azaldı"),
        ("adblue_freeze", "info", "AdBlue donma bilgisi"),
    )),
    ("tires", "Lastikler", (
        ("tire_blown", "crit", "Lastik patladı"),
        ("tire_pressure_crit", "crit", "Lastik basıncı çok düşük"),
        ("tire_pressure_low", "warn", "Lastik basıncı düşük"),
        ("tire_leak", "warn", "Yavaş patlak"),
        ("tread_legal", "crit", "Lastik dişi yasal sınırın altında"),
        ("tread_low", "warn", "Lastik dişi azaldı"),
        ("tire_overheat", "crit", "Lastikler aşırı ısındı"),
        ("tire_hot", "warn", "Lastikler ısınıyor"),
    )),
    # parça arızaları: anahtar "fault:<arıza>", ad arıza adıyla aynı
    ("faults", "Parça arızaları", tuple((f"fault:{k}", v.get("level", "crit"), v["name"]) for k, v in FAULTS.items())),
    ("mode", "Tek / çok oyunculu bildirimleri", (
        ("mp_detected", "warn", "Tek Oyunculu modda çok oyunculu oturum algılandı"),
        ("sp_session", "info", "Çok Oyunculu modda tek oyunculu oturum"),
        ("mp_stop_pending", "crit", "Motor yavaşlayınca durdurulacak (çok oyunculu tam izleme)"),
    )),
)
WARNING_KEYS = frozenset(key for _, _, items in GROUPS for key, _, _ in items)
LAMP_KEYS = frozenset(LAMP_ORDER)
# katmandaki her lambanın ne zaman yandığı (Ayarlar'daki listede adının yanında)
LAMP_DESCS = {
    "stop": "Motoru hemen durdurun: yağ basıncı yok, hararet / kaynama, motor kilitlendi, patlak lastikle ya da fren "
            "havası bitmişken hareket",
    "batt": "Şarj yok; akü boş, zayıf ya da donma riskinde; marş için şarj yetersiz",
    "glow": "Ön ısıtma sürüyor (bilgi) ya da ön ısıtma arızası",
    "start": "Marş motoru arızası",
    "oil": "Yağ basıncı düşük ya da yağ seviyesi az",
    "cool": "Motor sıcaklığı yüksek ya da soğutma suyu az",
    "brake": "Frenler çok sıcak ya da fren havası düşük",
    "park": "Park freni çekiliyken hareket ya da motor kapalıyken çekilmemiş",
    "abs": "ABS sensörü arızası",
    "steer": "Direksiyon hidrolik desteği yok, yağı az ya da kaçak var",
    "gear": "Şanzıman yağı ya da debriyaj sıcaklığı, balata aşınması, arıza, yağ değişimi",
    "tire": "Lastik basıncı, sıcaklığı, dişi ya da patlak",
    "eng": "Motor arıza lambası: arıza kodu, conta, termostat, düşük motor sağlığı",
    "dpf": "DPF dolu ya da tıkalı, kül, rejenerasyon",
    "adblue": "AdBlue az ya da bitti",
    "fuel": "Yakıt az",
    "frost": "Antifriz yetersiz ya da soğutma sisteminde buz",
    "svc": "Bakım zamanı: yağ ömrü, yağ filtresi, antifriz",
}
SETTINGS = {"warnings_off": WARNING_KEYS, "lamps_off": LAMP_KEYS}


def clean(name, value):
    """Ayardan gelen kapalılar listesi: yalnızca bilinen anahtarlar, tekrarsız, sırası korunur. Liste değilse None."""
    if not isinstance(value, (list, tuple)):
        return None
    known, out = SETTINGS[name], []
    for k in value:
        if isinstance(k, str) and k in known and k not in out:
            out.append(k)
    return out


def off(settings, name):
    """Kapatılmış anahtarlar kümesi (bozuk / eski ayar dosyasında da güvenli)."""
    return set(clean(name, (settings or {}).get(name)) or ())


def visible(warnings, settings):
    """Kapatılmamış uyarılar (sıra korunur)."""
    hidden = off(settings, "warnings_off")
    return [w for w in warnings if w.get("key") not in hidden] if hidden else list(warnings)


def visible_lamps(lamps, settings):
    """Kapatılmamış ikaz lambaları: [(kimlik, renk), ...]."""
    hidden = off(settings, "lamps_off")
    return [x for x in lamps if x[0] not in hidden] if hidden else list(lamps)


def catalog():
    """Ayarlar'daki liste, seçili dilde: gruplar (uyarılar) ve lambalar."""
    return {
        "groups": [{"key": g, "name": T(name),
                    "items": [{"key": k, "level": lvl, "label": T(label)} for k, lvl, label in items]}
                   for g, name, items in GROUPS],
        "lamps": [{"key": k, "label": T(LAMP_LABELS[k]), "desc": T(LAMP_DESCS[k])} for k in LAMP_ORDER],
    }
