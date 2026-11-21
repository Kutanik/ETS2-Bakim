"""Otomatik motor seçimi.

1) Model veritabanı: telemetrideki marka/model kimliğinden kamyon modelini bulur ve o modelin gerçek
   motor seçeneklerini (güç, tork, hacim, yağ/su kapasitesi) ve DPF olup olmadığını verir.
2) Sürüşten algılama: tam gazda, sabit viteste; vites oranı, diferansiyel, tekerlek yarıçapı, ivme,
   yol eğimi ve kütleden motor torkunu hesaplar ve modelin seçenekleri içinden en yakın motoru seçer.
"""
import math
import re
import statistics

from . import vehicles
from .engine import EngineSpec

# (id, ad, hp, Nm, hacim L, nominal devir, yağ L, su L)
_VOLVO_D13A = [("d13a420", "D13A 420", 420, 2100, 12.8, 1800, 34, 55), ("d13a460", "D13A 460", 460, 2300, 12.8, 1800, 34, 55),
               ("d13a500", "D13A 500", 500, 2500, 12.8, 1800, 34, 55), ("d16e550", "D16E 550", 550, 2650, 16.1, 1800, 42, 65),
               ("d16e600", "D16E 600", 600, 2800, 16.1, 1800, 42, 65), ("d16e700", "D16E 700", 700, 3150, 16.1, 1800, 42, 65)]
_VOLVO_D13K = [("d13k420", "D13K 420", 420, 2100, 12.8, 1800, 36, 55), ("d13k460", "D13K 460", 460, 2300, 12.8, 1800, 36, 55),
               ("d13k500", "D13K 500", 500, 2500, 12.8, 1800, 36, 55), ("d13k540", "D13K 540", 540, 2600, 12.8, 1800, 36, 55),
               ("d16k550", "D16K 550", 550, 2800, 16.1, 1800, 42, 65), ("d16k650", "D16K 650", 650, 3150, 16.1, 1800, 42, 65),
               ("d16k750", "D16K 750", 750, 3550, 16.1, 1800, 42, 65)]
_VOLVO_FH5 = [("d13k460", "D13K 460", 460, 2300, 12.8, 1800, 36, 55), ("d13k500", "D13K 500", 500, 2500, 12.8, 1800, 36, 55),
              ("d13k540", "D13K 540", 540, 2600, 12.8, 1800, 36, 55), ("d17_600", "D17 600", 600, 3000, 17.3, 1800, 44, 68),
              ("d17_700", "D17 700", 700, 3400, 17.3, 1800, 44, 68), ("d17_780", "D17 780", 780, 3800, 17.3, 1800, 44, 68)]
_SCANIA_R09 = [("dc13_400", "DC13 400", 400, 2100, 12.7, 1900, 38, 60), ("dc13_440", "DC13 440", 440, 2300, 12.7, 1900, 38, 60),
               ("dc13_480", "DC13 480", 480, 2500, 12.7, 1900, 38, 60), ("dc16_560", "DC16 V8 560", 560, 2700, 15.6, 1900, 43, 75),
               ("dc16_620", "DC16 V8 620", 620, 3000, 15.6, 1900, 43, 75), ("dc16_730", "DC16 V8 730", 730, 3500, 16.4, 1900, 43, 75)]
_SCANIA_SL = [("dc13_410", "DC13 410", 410, 2150, 12.7, 1900, 38, 60), ("dc13_450", "DC13 450", 450, 2350, 12.7, 1900, 38, 60),
              ("dc13_490", "DC13 490", 490, 2550, 12.7, 1900, 38, 60), ("dc16_520", "DC16 V8 520", 520, 2700, 16.4, 1900, 43, 75),
              ("dc16_580", "DC16 V8 580", 580, 2950, 16.4, 1900, 43, 75), ("dc16_730", "DC16 V8 730", 730, 3500, 16.4, 1900, 43, 75)]
_SCANIA_NG = [("dc13_410", "DC13 410", 410, 2150, 12.7, 1900, 38, 62), ("dc13_450", "DC13 450", 450, 2350, 12.7, 1900, 38, 62),
              ("dc13_500", "DC13 500", 500, 2550, 12.7, 1900, 38, 62), ("dc13_540", "DC13 540", 540, 2700, 12.7, 1900, 38, 62),
              ("dc16_520", "DC16 V8 520", 520, 2700, 16.4, 1900, 43, 78), ("dc16_580", "DC16 V8 580", 580, 2950, 16.4, 1900, 43, 78),
              ("dc16_650", "DC16 V8 650", 650, 3300, 16.4, 1900, 43, 78), ("dc16_730", "DC16 V8 730", 730, 3500, 16.4, 1900, 43, 78),
              ("dc16_770", "DC16 V8 770", 770, 3700, 16.4, 1900, 43, 78)]
_MB_MP3 = [("om501_440", "OM501LA 440", 440, 2100, 11.9, 1800, 39, 55), ("om501_480", "OM501LA 480", 480, 2300, 11.9, 1800, 39, 55),
           ("om502_510", "OM502LA V8 510", 510, 2400, 15.9, 1800, 43, 65), ("om502_600", "OM502LA V8 600", 600, 2800, 15.9, 1800, 43, 65)]
_MB_MP4 = [("om471_449", "OM471 449", 449, 2200, 12.8, 1600, 41, 55), ("om471_476", "OM471 476", 476, 2300, 12.8, 1600, 41, 55),
           ("om471_510", "OM471 510", 510, 2500, 12.8, 1600, 41, 55), ("om473_580", "OM473 580", 580, 2800, 15.6, 1600, 45, 65),
           ("om473_625", "OM473 625", 625, 3000, 15.6, 1600, 45, 65)]
_MB_MP5 = [("om471_476", "OM471 476", 476, 2300, 12.8, 1600, 41, 55), ("om471_510", "OM471 510", 510, 2500, 12.8, 1600, 41, 55),
           ("om471_530", "OM471 530", 530, 2600, 12.8, 1600, 41, 55), ("om473_580", "OM473 580", 580, 2800, 15.6, 1600, 45, 65),
           ("om473_625", "OM473 625", 625, 3000, 15.6, 1600, 45, 65)]
_MAN_07 = [("d2676_440", "D2676 440", 440, 2100, 12.4, 1800, 40, 58), ("d2676_480", "D2676 480", 480, 2300, 12.4, 1800, 40, 58),
           ("d2676_540", "D2676 540", 540, 2500, 12.4, 1800, 40, 58), ("d2868_680", "D2868 V8 680", 680, 3000, 16.2, 1800, 45, 70)]
_MAN_E6 = [("d2676_440", "D2676 440", 440, 2100, 12.4, 1800, 40, 58), ("d2676_480", "D2676 480", 480, 2300, 12.4, 1800, 40, 58),
           ("d2676_500", "D2676 500", 500, 2400, 12.4, 1800, 40, 58), ("d3876_560", "D3876 560", 560, 2700, 15.2, 1800, 45, 68),
           ("d3876_640", "D3876 640", 640, 3000, 15.2, 1800, 45, 68)]
_MAN_20 = [("d2676_470", "D2676 470", 470, 2400, 12.4, 1800, 40, 58), ("d2676_510", "D2676 510", 510, 2600, 12.4, 1800, 40, 58),
           ("d3876_540", "D3876 540", 540, 2700, 15.2, 1800, 45, 68), ("d3876_640", "D3876 640", 640, 3000, 15.2, 1800, 45, 68)]
_DAF_105 = [("mx13_410", "MX-13 410", 410, 2000, 12.9, 1700, 40, 60), ("mx13_460", "MX-13 460", 460, 2300, 12.9, 1700, 40, 60),
            ("mx13_510", "MX-13 510", 510, 2500, 12.9, 1700, 40, 60)]
_DAF_E6 = [("mx11_440", "MX-11 440", 440, 2100, 10.8, 1700, 35, 55), ("mx13_460", "MX-13 460", 460, 2300, 12.9, 1700, 40, 60),
           ("mx13_510", "MX-13 510", 510, 2500, 12.9, 1700, 40, 60), ("mx13_530", "MX-13 530", 530, 2600, 12.9, 1700, 40, 60)]
_DAF_21 = [("mx11_450", "MX-11 450", 450, 2200, 10.8, 1700, 35, 55), ("mx13_480", "MX-13 480", 480, 2500, 12.9, 1700, 40, 60),
           ("mx13_530", "MX-13 530", 530, 2800, 12.9, 1700, 40, 60)]
_DAF_XD = [("mx11_370", "MX-11 370", 370, 1900, 10.8, 1700, 35, 55), ("mx11_410", "MX-11 410", 410, 2100, 10.8, 1700, 35, 55),
           ("mx11_450", "MX-11 450", 450, 2200, 10.8, 1700, 35, 55)]
_IVECO_STR = [("c13_480", "Cursor 13 480", 480, 2300, 12.9, 1900, 33, 55), ("c13_500", "Cursor 13 500", 500, 2250, 12.9, 1900, 33, 55),
              ("c13_560", "Cursor 13 560", 560, 2500, 12.9, 1900, 33, 55)]
_IVECO_HW = [("c11_420", "Cursor 11 420", 420, 2000, 11.1, 1900, 30, 52), ("c11_460", "Cursor 11 460", 460, 2150, 11.1, 1900, 30, 52),
             ("c13_500", "Cursor 13 500", 500, 2250, 12.9, 1900, 33, 55), ("c13_560", "Cursor 13 560", 560, 2500, 12.9, 1900, 33, 55)]
_IVECO_SW = [("c11_480", "Cursor 11 480", 480, 2300, 11.1, 1900, 30, 52), ("c13_510", "Cursor 13 510", 510, 2300, 12.9, 1900, 33, 55),
             ("c13_570", "Cursor 13 570", 570, 2500, 12.9, 1900, 33, 55)]
_REN_MAG = [("dxi13_440", "DXi13 440", 440, 2100, 12.8, 1800, 36, 55), ("dxi13_480", "DXi13 480", 480, 2300, 12.8, 1800, 36, 55),
            ("dxi13_520", "DXi13 520", 520, 2550, 12.8, 1800, 36, 55)]
_REN_PREM = [("dxi11_380", "DXi11 380", 380, 1800, 10.8, 1800, 33, 50), ("dxi11_430", "DXi11 430", 430, 2040, 10.8, 1800, 33, 50),
             ("dxi11_450", "DXi11 450", 450, 2140, 10.8, 1800, 33, 50)]
_REN_T = [("dti11_430", "DTI 11 430", 430, 2050, 10.8, 1800, 33, 50), ("dti11_460", "DTI 11 460", 460, 2200, 10.8, 1800, 33, 50),
          ("dti13_480", "DTI 13 480", 480, 2400, 12.8, 1800, 36, 55), ("dti13_520", "DTI 13 520", 520, 2550, 12.8, 1800, 36, 55)]
# TruckersMP: otomobil (Škoda Superb, Scout Extra_D Estate) ve otobüs (HVT Tourvego 16 SHD). Değerler TruckersMP'nin
# araç tanımlarından (def/vehicle/truck/.../engine) ve üreticinin verilerinden. Otomobilin oyun içi devir ölçeği tır
# gibidir (sınır 3000): nominal devir bu ölçekte (tork eğrisinin güç tepesi ~1900); güç ve tork gerçek değerdir.
# (id, ad, hp, Nm, hacim L, nominal devir, yağ L, su L, yakıt)
_TMP_CAR = [("18tsi", "1.8 TSI 160 hp", 160, 250, 1.8, 1900, 4.6, 7.5, "petrol"),
            ("20tdi", "2.0 TDI 170 hp", 170, 320, 2.0, 1900, 4.3, 8.0, "diesel")]
_TMP_BUS = [("om470_456", "OM 470 FE 456", 456, 2200, 10.7, 1700, 36, 75)]
# Ayarlar → Araç tipi ile otomobil / otobüs seçilen ve modeli tanınmayan araçlar (tek oyunculu Togg, Passat, otobüs
# modları): yaygın motorlar. Otomobil devirleri yukarıdaki gibi motor modelinin ölçeğinde (vehicles.rpm_scale).
_GENERIC_CAR = [("g10t", "1.0 turbo benzinli 110 hp", 110, 200, 1.0, 1900, 4.0, 6.0, "petrol"),
                ("g15t", "1.5 turbo benzinli 150 hp", 150, 250, 1.5, 1900, 4.0, 7.0, "petrol"),
                ("g20t", "2.0 turbo benzinli 190 hp", 190, 320, 2.0, 1900, 5.7, 8.5, "petrol"),
                ("g16d", "1.6 dizel 115 hp", 115, 250, 1.6, 1900, 4.3, 7.0, "diesel"),
                ("g20d150", "2.0 dizel 150 hp", 150, 340, 2.0, 1900, 4.6, 8.0, "diesel"),
                ("g20d190", "2.0 dizel 190 hp", 190, 400, 2.0, 1900, 4.6, 8.0, "diesel")]
_GENERIC_BUS = [("om470_394", "OM 470 394", 394, 1900, 10.7, 1700, 36, 75),
                ("om470_428", "OM 470 428", 428, 2100, 10.7, 1700, 36, 75),
                ("om470_456", "OM 470 FE 456", 456, 2200, 10.7, 1700, 36, 75),
                ("d2676_420", "MAN D2676 420", 420, 2100, 12.4, 1800, 40, 80),
                ("d2676_460", "MAN D2676 460", 460, 2300, 12.4, 1800, 40, 80),
                ("dc13_410", "Scania DC13 410", 410, 2150, 12.7, 1900, 38, 80),
                ("dc13_450", "Scania DC13 450", 450, 2350, 12.7, 1900, 38, 80),
                ("d13k_420", "Volvo D13K 420", 420, 2100, 12.8, 1800, 36, 80),
                ("d13k_460", "Volvo D13K 460", 460, 2300, 12.8, 1800, 36, 80)]

# ATS
_US_X15 = [("x15_450", "Cummins X15 450", 450, 1650 * 1.3558, 14.9, 1800, 40, 60), ("x15_505", "Cummins X15 505", 505, 1850 * 1.3558, 14.9, 1800, 40, 60),
           ("x15_565", "Cummins X15 565", 565, 2050 * 1.3558, 14.9, 1800, 40, 60), ("x15_605", "Cummins X15 605", 605, 2050 * 1.3558, 14.9, 1800, 40, 60)]
_US_MX13 = [("mx13_455", "PACCAR MX-13 455", 455, 1650 * 1.3558, 12.9, 1700, 40, 60), ("mx13_510", "PACCAR MX-13 510", 510, 1850 * 1.3558, 12.9, 1700, 40, 60)]
_US_DD = [("dd15_455", "Detroit DD15 455", 455, 1650 * 1.3558, 14.8, 1800, 42, 60), ("dd15_505", "Detroit DD15 505", 505, 1850 * 1.3558, 14.8, 1800, 42, 60),
          ("dd16_600", "Detroit DD16 600", 600, 2050 * 1.3558, 15.6, 1800, 44, 65)]
_US_VOLVO = [("d13_455", "Volvo D13 455", 455, 1650 * 1.3558, 12.8, 1800, 36, 55), ("d13_500", "Volvo D13 500", 500, 1850 * 1.3558, 12.8, 1800, 36, 55)]
_US_MACK = [("mp8_445", "Mack MP8 445", 445, 1760 * 1.3558, 12.8, 1800, 36, 55), ("mp8_505", "Mack MP8 505", 505, 1860 * 1.3558, 12.8, 1800, 36, 55)]

# (anahtar, marka kimlikleri, desen, ad, dpf, akü Ah, motorlar, varsayılan[, sınıf: truck | bus | car])
MODELS = [
    ("tmp_scout", ("skoda",), r"superb2|scout|extra", "Scout Extra_D Estate (TruckersMP)", True, 72, _TMP_CAR, "20tdi", "car"),
    ("tmp_superb", ("skoda",), r"superb", "Škoda Superb (TruckersMP)", True, 72, _TMP_CAR, "20tdi", "car"),
    ("tmp_tourvego", ("hvt", "t16shd", "tourvego"), r".", "HVT Tourvego 16 SHD (TruckersMP)", True, 225, _TMP_BUS,
     "om470_456", "bus"),
    ("volvo_vnl", ("volvo",), r"vnl", "Volvo VNL", True, 225, _US_VOLVO + _US_X15, "d13_500"),
    ("volvo_fh5", ("volvo",), r"2021|2024|aero|fh5|fh_2021|new fh", "Volvo FH (2021)", True, 225, _VOLVO_FH5, "d13k500"),
    ("volvo_fh12", ("volvo",), r"2012", "Volvo FH (2012)", True, 225, _VOLVO_D13K, "d13k500"),
    ("volvo_fh09", ("volvo",), r"fh", "Volvo FH16 (2009)", False, 225, _VOLVO_D13A, "d13a500"),
    ("scania_sl", ("scania",), r"streamline", "Scania Streamline", False, 225, _SCANIA_SL, "dc13_450"),
    ("scania_ng", ("scania",), r"2016|2024|scania\.s(\b|_)|^s$|super", "Scania R/S (2016)", True, 225, _SCANIA_NG, "dc13_500"),
    ("scania_r09", ("scania",), r".", "Scania R (2009)", False, 225, _SCANIA_R09, "dc13_480"),
    ("mb_mp5", ("mercedes",), r"2019|mp5|2024|actros_l|actros l", "Mercedes-Benz Actros (2019)", True, 225, _MB_MP5, "om471_510"),
    ("mb_mp4", ("mercedes",), r"2014|new", "Mercedes-Benz New Actros (2014)", True, 225, _MB_MP4, "om471_476"),
    ("mb_mp3", ("mercedes",), r".", "Mercedes-Benz Actros (2009)", False, 225, _MB_MP3, "om501_480"),
    ("man_20", ("man",), r"2020|new tgx", "MAN TGX (2020)", True, 225, _MAN_20, "d2676_510"),
    ("man_e6", ("man",), r"euro.?6", "MAN TGX Euro 6", True, 225, _MAN_E6, "d2676_480"),
    ("man_07", ("man",), r".", "MAN TGX (2007)", False, 225, _MAN_07, "d2676_480"),
    ("daf_xd", ("daf",), r"\bxd|daf\.xd|2022", "DAF XD", True, 225, _DAF_XD, "mx11_450"),
    ("daf_21", ("daf",), r"2021|xg|new xf", "DAF XF/XG (2021)", True, 225, _DAF_21, "mx13_480"),
    ("daf_e6", ("daf",), r"euro.?6", "DAF XF Euro 6", True, 225, _DAF_E6, "mx13_510"),
    ("daf_105", ("daf",), r".", "DAF XF 105", False, 225, _DAF_105, "mx13_460"),
    ("iveco_sw", ("iveco",), r"s.?way", "Iveco S-Way", True, 220, _IVECO_SW, "c13_510"),
    ("iveco_hw", ("iveco",), r"hi.?way", "Iveco Hi-Way", True, 220, _IVECO_HW, "c13_500"),
    ("iveco_str", ("iveco",), r".", "Iveco Stralis", False, 220, _IVECO_STR, "c13_480"),
    ("ren_mag", ("renault",), r"magnum", "Renault Magnum", False, 225, _REN_MAG, "dxi13_480"),
    ("ren_prem", ("renault",), r"premium", "Renault Premium", False, 225, _REN_PREM, "dxi11_430"),
    ("ren_t", ("renault",), r".", "Renault T", True, 225, _REN_T, "dti13_480"),
    ("pete", ("peterbilt",), r".", "Peterbilt", True, 200, _US_MX13 + _US_X15, "x15_505"),
    ("kw", ("kenworth",), r".", "Kenworth", True, 200, _US_MX13 + _US_X15, "x15_505"),
    ("fl", ("freightliner",), r".", "Freightliner", True, 200, _US_DD, "dd15_505"),
    ("ws", ("westernstar", "western_star"), r".", "Western Star", True, 200, _US_DD + _US_X15, "dd15_505"),
    ("intl", ("international", "intnational"), r".", "International", True, 200, _US_X15, "x15_505"),
    ("mack", ("mack",), r".", "Mack", True, 200, _US_MACK, "mp8_505"),
]
# sınıfa göre genel motor listesi (telemetriden eşleşmez; yalnızca Araç tipi elle seçilince). Tırda yok: tanınmayan tır
# bilinmeyen motor (500 hp) varsayar, değerler Ayarlar'dan girilir.
GENERIC = {
    "car": ("generic_car", (), r"(?!)", "Otomobil — genel motor listesi", True, 72, _GENERIC_CAR, "g20d150", "car"),
    "bus": ("generic_bus", (), r"(?!)", "Otobüs — genel motor listesi", True, 225, _GENERIC_BUS, "om470_428", "bus"),
}
_ENGINE_FIELDS = ("name", "power_kw", "rated_rpm", "idle_rpm", "displacement_l", "oil_capacity_l",
                  "coolant_capacity_l", "battery_ah", "has_dpf", "torque_nm", "engine_id", "model_key", "model_name",
                  "fuel", "real_torque_nm")
_ELECTRIC = re.compile(r"electric|e-?tech|etgx|e_tgx|eactros|e_actros|\bbev\b|_ev\b", re.I)


def find_model(brand_id, truck_id, name):
    hay = f"{truck_id} {name}".lower()
    b = (brand_id or "").lower()
    for m in MODELS:
        if any(bb in b or bb in truck_id.lower() for bb in m[1]) and re.search(m[2], hay):
            return m
    return None


def is_electric(truck_id, name):
    return bool(_ELECTRIC.search(f"{truck_id} {name}"))


def model_class(model):
    return model[8] if model is not None and len(model) > 8 else "truck"


def lineup(model):
    return [dict(id=e[0], label=e[1], hp=e[2], nm=round(e[3]), disp=e[4], rpm=e[5], oil=e[6], cool=e[7],
                 fuel=e[8] if len(e) > 8 else "diesel") for e in model[6]]


def engine_by_id(model, eid):
    for e in lineup(model):
        if e["id"] == eid:
            return e
    return None


def apply_engine(spec, e):
    spec.engine_id = e["id"]
    spec.name = e["label"]
    spec.power_kw = e["hp"] * 0.7355
    spec.torque_nm = float(e["nm"])
    spec.displacement_l = e["disp"]
    spec.rated_rpm = float(e["rpm"])
    spec.oil_capacity_l = float(e["oil"])
    spec.coolant_capacity_l = float(e["cool"])
    spec.fuel = e.get("fuel", "diesel")
    if vehicles.kind_of(spec) == "car":
        # oyun içi devir ölçeğinde güçle tutarlı tork modelden türetilir (gerçek tork motor adında ve listede gösterilir);
        # benzinli motorda DPF / AdBlue yok
        spec.torque_nm = 0.0
        spec.has_dpf = spec.fuel == "diesel"


def auto_spec(spec, brand_id, truck_id, name):
    """Model veritabanından varsayılan motoru ve kamyon özelliklerini uygular. Dönüş: model ya da None.
    spec.vehicle algılanan sınıf olur; Ayarlar → Araç tipi başka bir sınıf seçtiyse o sınıfın genel motor listesi
    kullanılır (tır seçilip model tanınmazsa None)."""
    m = find_model(brand_id, truck_id, name)
    spec.electric = is_electric(truck_id, name)
    spec.vehicle = model_class(m)
    want = vehicles.kind_of(spec)
    if m is None or model_class(m) != want:
        m = GENERIC.get(want)
    if m is None:
        spec.model_key = ""
        return None
    spec.model_key = m[0]
    spec.model_name = m[3]
    spec.has_dpf = m[4]
    spec.battery_ah = float(m[5])
    e = engine_by_id(m, m[7]) or lineup(m)[0]
    apply_engine(spec, e)
    return m


def model_by_key(key):
    for m in MODELS + list(GENERIC.values()):
        if m[0] == key:
            return m
    return None


def reset_engine(spec):
    """Motor ve kapasite değerlerini varsayılana döndürür (tanınmayan tır: 500 hp varsayılır); sınıf seçimi korunur."""
    d = EngineSpec()
    for k in _ENGINE_FIELDS:
        setattr(spec, k, getattr(d, k))


class EngineDetector:
    """Tam gaz anlarında yol dinamiğinden motorun tepe torkunu kestirir."""

    TRACTOR_T = 8000.0
    TRAILER_T = 7000.0
    G = 9.81
    MIN_SAMPLES = 60

    def __init__(self):
        self.samples = []
        self.prev_speed = None
        self.prev_gear = None
        self.gear_since = 0.0
        self.acc = None

    def reset(self):
        self.__init__()

    def feed(self, f, dt_real, running, spec):
        v = abs(f.speed_kmh) / 3.6
        if self.prev_speed is not None and dt_real > 0:
            a = (v - self.prev_speed) / dt_real
            self.acc = a if self.acc is None else self.acc + (a - self.acc) * min(1.0, dt_real / 0.6)
        self.prev_speed = v
        if f.gear != self.prev_gear:
            self.prev_gear = f.gear
            self.gear_since = 0.0
        else:
            self.gear_since += dt_real
        ok = (running and f.throttle >= 0.95 and f.clutch < 0.05 and f.brake < 0.02 and f.retarder_level == 0
              and f.gear > 0 and f.gear >= max(3, f.gears_forward // 2) and self.gear_since > 1.5
              and 1000 <= f.rpm <= min(1450, spec.rated_rpm - 100) and 15 / 3.6 < v < 85 / 3.6
              and self.acc is not None and f.wheel_radius > 0.2 and f.gear <= len(f.gear_ratios))
        if not ok:
            return
        ratio = f.gear_ratios[f.gear - 1] * f.diff_ratio
        if ratio <= 0:
            return
        rpm_calc = v / f.wheel_radius * ratio * 60 / (2 * math.pi)
        if abs(rpm_calc - f.rpm) / f.rpm > 0.08:
            return  # kavrama kayıyor veya veri tutarsız
        m = self.TRACTOR_T + ((self.TRAILER_T + f.cargo_kg) if f.trailer_attached else 0.0)
        th = f.pitch * 2 * math.pi
        cda = 6.0 if f.trailer_attached else 5.0
        force = (m * self.acc + m * self.G * math.sin(th) + 0.0065 * m * self.G * math.cos(th)
                 + 0.5 * 1.2 * cda * v * v)
        torque = force * f.wheel_radius / (ratio * 0.93)
        if torque <= 0:
            return
        self.samples.append(torque / f.throttle)
        if len(self.samples) > 400:
            del self.samples[:100]

    def estimate(self):
        if len(self.samples) < self.MIN_SAMPLES:
            return None, None
        med = statistics.median(self.samples)
        mad = statistics.median(abs(s - med) for s in self.samples)
        return med, mad / med if med > 0 else 1.0

    def suggest(self, model):
        """(önerilen motor, kestirilen tork, güvenilir_mi)"""
        est, spread = self.estimate()
        if est is None or model is None:
            return None, est, False
        engines = sorted(lineup(model), key=lambda e: abs(e["nm"] - est))
        best = engines[0]
        d_best = abs(best["nm"] - est)
        others = [abs(e["nm"] - est) for e in engines[1:] if e["nm"] != best["nm"]]
        tied = any(e["nm"] == best["nm"] for e in engines[1:])
        d_second = min(others) if others else float("inf")
        confident = (not tied and spread < 0.08 and d_best <= 0.06 * best["nm"] and d_best < 0.6 * d_second)
        return best, est, confident
