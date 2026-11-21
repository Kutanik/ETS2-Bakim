"""Servis, parça ve onarım fiyatları (€, KDV hariç) — tek yerden ayarlanır.

2026 Batı Avrupa bağımsız ağır vasıta servisi seviyesinde: parça + işçilik (saat ücreti ~110 €). Tutarlar oyundaki
paranızdan düşülmez; uygulamanın kendi gider defterine (Servis & Arızalar → kayıt, Bakım planı) yazılır.
"""

# motor yağı (€/L, varil fiyatı; otomobil yağları 5 L bidon) ve yağ servisi
OIL_L = {"15w40": 5.2, "10w40": 9.0, "5w30": 10.5, "15w40e9": 5.8, "10w30e9": 7.6, "10w40e6": 9.3, "5w30e4": 11.8,
         "20w50": 4.2, "5w30vw": 13.5, "0w20vw": 16.0, "5w40vw": 11.0,
         "0w30e6": 13.2, "5w40e7": 8.4, "10w40e11": 8.0, "15w40ck4": 6.4}
OIL_FILTER = 55.0                        # yağ filtresi (kartuş)
OIL_CHANGE_LABOUR = 85.0                 # yağ + filtre değişimi işçiliği (~0,75 sa)
FILTER_LABOUR = 35.0                     # yalnız filtre değişimi işçiliği
OIL_SAMPLE = 45.0                        # laboratuvar yağ analizi

# soğutma sıvısı (€/L) ve işçilik
COOLANT_TYPE_L = {"oat": 3.9, "iat": 2.6, "hoat": 3.6, "si_oat": 4.6, "p_oat": 4.2,   # değişimde (50/50 karışım)
                  "noat": 3.4, "hoat_vcs": 4.4, "si_oat_evo": 5.6}
COOLANT_FLUID_L = {"premix": 3.9, "concentrate": 6.5, "distilled": 0.8, "tap": 0.0}
COOLANT_CHANGE_LABOUR = 110.0            # boşaltma, yıkama, doldurma, hava alma (~1 sa)
COOLANT_TEST = 15.0                      # refraktometre ölçümü

# akü ve elektrik
BATTERY_225AH_PAIR = 680.0               # 2 x 12 V 225 Ah ağır hizmet aküsü (kapasiteyle orantılı)
BATTERY_FIT = 40.0                       # takma ve kodlama
BATTERY_KIND = {"std": 1.0, "efb": 1.3, "agm": 1.75, "gel": 1.95, "agm_hd": 2.15}   # standarda göre fiyat katsayısı
JUMP_START = 150.0                       # yol yardımı / takviye
CHARGER = 20.0                           # şarj cihazı bağlama

# egzoz son işlem
DPF_REGEN = 290.0                        # serviste zorunlu rejenerasyon (teşhis cihazıyla)
DPF_CLEAN = 950.0                        # söküp termal kül temizliği ve takma
ADBLUE_L = 0.80                          # istasyon pompası

# lastikler (lastik başına; ön 315/80 R22.5, çekiş 315/70 R22.5, taşıyıcı 385/55 R22.5 kalite marka)
TIRE = {"steer": 560.0, "drive": 540.0, "tag": 470.0,
        "front": 165.0, "rear": 165.0}  # otomobil: 235/45 R18 (Škoda Superb)
TIRE_MOUNT = 40.0                        # sökme-takma, balans, sibop
PUNCTURE_REPAIR = 75.0                   # yavaş patlak: iç yama/mantar

# arızalar (parça + işçilik)
FAULT = {
    "alternator": 880.0,                 # 24 V 110 A alternatör
    "thermostat_closed": 340.0,
    "thermostat_open": 340.0,
    "fan_clutch": 920.0,                 # viskoz fan kavraması
    "water_pump": 950.0,
    "oil_leak": 680.0,                   # karter contası (~5 sa işçilik)
    "preheater": 520.0,                  # ızgara ısıtıcı / röle
    "head_gasket": 5200.0,               # kapak sökme, yüzey taşlama, conta takımı
    "engine_seized": 26000.0,            # yenilenmiş kısa blok (krank, yataklar, pistonlar)
    "block_cracked": 32000.0,            # yenilenmiş komple motor
    "radiator_cracked": 1650.0,
    "battery_frozen": 0.0,               # aküler BATTERY_225AH_PAIR ile yenilenir
    "gearbox_cooler": 1150.0,            # şanzıman yağ-su eşanjörü, yağ tamamlama
    "clutch_actuator": 950.0,            # AMT debriyaj aktüatörü (pnömatik silindir ve valf)
    "steering_leak": 780.0,              # direksiyon pompası contaları / basınç hortumu, yağ ve hava alma
    "abs_sensor": 260.0,                 # tekerlek hızı sensörü ve klips
    "starter": 820.0,                    # 24 V yenilenmiş marş motoru
    "oil_pump": 1450.0,                  # yağ pompası ve tahliye valfi (karter sökülür, ~6 sa işçilik)
    "turbo": 2400.0,                     # yenilenmiş turbo, contalar, yağ hatları
    "injector": 1400.0,                  # arızalı enjektör, diğerlerinin testi ve kodlama
    "egr_valve": 1100.0,                 # EGR valfi ve soğutucu temizliği
    "intercooler": 1300.0,               # intercooler ve hortum kelepçeleri
    "air_filter": 120.0,                 # hava filtresi elemanı ve işçilik
    "fuel_filter": 110.0,                # yakıt filtresi / su ayırıcı ve hava alma
    "radiator_leak": 1500.0,             # radyatör, soğutma suyu tamamlama
    "belt": 260.0,                       # poly-V kayışı ve gergi kontrolü
}
OVERHAUL = 19500.0                       # yerinde motor revizyonu (gömlek, piston, segman, yataklar)

# şanzıman ve debriyaj
GEARBOX_OIL = 365.0                      # 15 L sentetik şanzıman yağı (75W-80) + filtre + ~1 sa işçilik
CLUTCH = 2600.0                          # debriyaj seti (balata, baskı plakası, rulman) + şanzıman sökme (~8 sa)

# ---------------------------------------------------------------- otomobil (TruckersMP Škoda Superb / Scout)
# bağımsız oto servisi (~75 €/sa), orta sınıf otomobil parçaları; tutulmayan kalemlerde tır fiyatı geçerlidir
CAR = {
    "OIL_FILTER": 16.0, "OIL_CHANGE_LABOUR": 35.0, "FILTER_LABOUR": 15.0,
    "COOLANT_CHANGE_LABOUR": 75.0, "COOLANT_TEST": 10.0,
    "BATTERY_FIT": 30.0, "JUMP_START": 90.0, "CHARGER": 15.0,
    "DPF_REGEN": 150.0, "DPF_CLEAN": 480.0,
    "TIRE_MOUNT": 22.0, "PUNCTURE_REPAIR": 30.0,
    "OVERHAUL": 6500.0,
    "GEARBOX_OIL": 220.0,                # DSG yağı ve filtresi (~6 L)
    "CLUTCH": 1100.0,                    # debriyaj seti / çift kavrama
}
CAR_FAULT = {
    "alternator": 420.0, "thermostat_closed": 190.0, "thermostat_open": 190.0,
    "fan_clutch": 320.0,                 # elektrikli fan / fan kontrol modülü
    "water_pump": 450.0, "oil_leak": 260.0,
    "preheater": 230.0,                  # kızdırma bujileri ve röle (dizel)
    "head_gasket": 1900.0, "engine_seized": 5500.0, "block_cracked": 7500.0,
    "radiator_cracked": 420.0, "battery_frozen": 0.0,
    "gearbox_cooler": 380.0, "clutch_actuator": 650.0,   # DSG mekatronik / debriyaj silindiri
    "steering_leak": 0.0,                # otomobilde elektrikli direksiyon (hidrolik yok)
    "abs_sensor": 160.0, "starter": 380.0,
    "oil_pump": 520.0,
    "turbo": 1300.0, "injector": 480.0, "egr_valve": 420.0, "intercooler": 450.0,
    "air_filter": 45.0, "fuel_filter": 60.0, "radiator_leak": 420.0, "belt": 160.0,
}
BATTERY_EUR_PER_AH = BATTERY_225AH_PAIR / 450.0   # 12 V blok başına €/Ah (ağır hizmet ve otomobil aküsü)


def v(name, vehicle="truck"):
    """Araç sınıfına göre fiyat: otomobilde oto servisi fiyatı, diğerlerinde tır fiyatı."""
    if vehicle == "car" and name in CAR:
        return CAR[name]
    return globals()[name]


def fault(key, vehicle="truck"):
    return (CAR_FAULT if vehicle == "car" else FAULT).get(key, 0.0)
