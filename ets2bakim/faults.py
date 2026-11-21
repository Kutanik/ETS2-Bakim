"""Arızalar: yaşa bağlı rastgele parça arızaları (Weibull) ve kullanım hatasından doğan hasarlar.

level: uyarı seviyesi (crit: hemen müdahale · warn: sarı lamba, servise gidin). Arızaların etkisi ilgili modelde:
şanzıman soğutucusu ve debriyaj aktüatörü transmission.py, direksiyon kaçağı ve marş motoru truck.py, yağ pompası
oil.py (basınç) ve truck.py (yatak aşınması), ABS sensörü yalnızca lamba ve uyarı (oyunun ABS'i dışarıdan kapatılamaz).
random=False olanlar kullanım hatasından doğar ya da Ayarlar → Çekim modu ile elle tetiklenir (filming.py)."""
import math
from dataclasses import dataclass, field

from . import prices

FAULTS = {
    "alternator": dict(name="Alternatör arızası", random=True, mtbf_km=450000, cost=prices.FAULT["alternator"],
                       desc="Şarj yok: akü sürüş sırasında boşalır, voltaj düşünce motor stop eder."),
    "thermostat_closed": dict(name="Termostat kapalı takıldı", random=True, mtbf_km=900000, cost=prices.FAULT["thermostat_closed"],
                              desc="Radyatöre su gitmiyor; motor yük altında hızla hararet yapar."),
    "thermostat_open": dict(name="Termostat açık takıldı", random=True, mtbf_km=900000, cost=prices.FAULT["thermostat_open"],
                            desc="Motor çalışma sıcaklığına ulaşamaz; yakıt seyrelmesi ve aşınma artar."),
    "fan_clutch": dict(name="Fan kavraması arızası", random=True, mtbf_km=700000, cost=prices.FAULT["fan_clutch"],
                       desc="Fan devreye girmiyor; düşük hızda, yokuşta ve sıcak havada hararet."),
    "water_pump": dict(name="Su pompası sızdırıyor", random=True, mtbf_km=800000, cost=prices.FAULT["water_pump"],
                       desc="Soğutma suyu yavaş yavaş eksilir."),
    "oil_leak": dict(name="Karter contası sızıntısı", random=True, mtbf_km=600000, cost=prices.FAULT["oil_leak"],
                     desc="Yağ yavaş yavaş eksilir (park halinde bile damlar)."),
    "preheater": dict(name="Ön ısıtma (kızdırma bujisi / ızgara ısıtıcı) arızası", random=True, mtbf_km=550000, cost=prices.FAULT["preheater"],
                      desc="Soğukta motor zor çalışır ya da hiç ateşlemez, beyaz duman atar; ön ısıtma lambası yanıp söner."),
    "gearbox_cooler": dict(name="Şanzıman yağ soğutucusu arızası", random=True, mtbf_km=900000, level="warn",
                           cost=prices.FAULT["gearbox_cooler"],
                           desc="Yağ-su eşanjörü tıkandı: yokuşta ve retarder kullanımında şanzıman yağı aşırı ısınır."),
    "clutch_actuator": dict(name="Debriyaj aktüatörü arızası", random=True, mtbf_km=700000, level="warn",
                            cost=prices.FAULT["clutch_actuator"],
                            desc="Aktüatör hava kaçırıyor: debriyaj tam kavramıyor, yükte kayar; debriyaj ısınır ve hızla aşınır."),
    "steering_leak": dict(name="Direksiyon hidrolik kaçağı", random=True, mtbf_km=900000, level="warn",
                          cost=prices.FAULT["steering_leak"],
                          desc="Direksiyon pompası / hortumu sızdırıyor: hidrolik yağı eksilir; azalınca direksiyon ağırlaşır, pompa zarar görür."),
    "abs_sensor": dict(name="ABS tekerlek hızı sensörü arızası", random=True, mtbf_km=600000, level="warn",
                       cost=prices.FAULT["abs_sensor"],
                       desc="Sensör sinyali yok: ABS ve ESC devre dışı, sert frenlemede tekerlekler kilitlenebilir."),
    "starter": dict(name="Marş motoru arızası", random=True, mtbf_km=900000, level="warn", cost=prices.FAULT["starter"],
                    desc="Selenoid / kömürler aşınmış: marş motoru zaman zaman çevirmiyor, birkaç denemede çalışabilir."),
    # 1.3.0: motorun diğer parçaları (Motor Analizi → Arıza tespiti); etkileri truck.py, oil.py (yağ yakma), dpf.py (kurum)
    "turbo": dict(name="Turbo arızası (yağ yakıyor)", random=True, mtbf_km=700000, level="warn", cost=prices.FAULT["turbo"],
                  desc="Şaft keçeleri aşındı: turbo yağ yakar (mavi-siyah duman); yağ hızla eksilir, DPF çabuk dolar."),
    "injector": dict(name="Enjektör arızası", random=True, mtbf_km=600000, level="warn", cost=prices.FAULT["injector"],
                     desc="Bir enjektör damlatıyor: motor tekler, siyah duman atar; DPF hızla dolar, motor aşınması artar."),
    "egr_valve": dict(name="EGR valfi takıldı", random=True, mtbf_km=450000, level="warn", cost=prices.FAULT["egr_valve"],
                      desc="Valf kurumla tıkandı: yanma kirlenir, DPF daha çabuk dolar."),
    "intercooler": dict(name="Intercooler kaçağı", random=True, mtbf_km=900000, level="warn", cost=prices.FAULT["intercooler"],
                        desc="Şarj havası kaçıyor: güç düşer, egzoz sıcaklığı ve DPF kurumu artar."),
    "air_filter": dict(name="Hava filtresi tıkandı", random=True, mtbf_km=160000, level="warn", cost=prices.FAULT["air_filter"],
                       desc="Motor yeterli hava alamıyor: güç düşer, DPF kurumu ve motor aşınması artar."),
    "fuel_filter": dict(name="Yakıt filtresi tıkandı", random=True, mtbf_km=140000, level="warn", cost=prices.FAULT["fuel_filter"],
                        desc="Yakıt akışı kısıldı: yüksek yükte motor tekler ve güç düşer."),
    "radiator_leak": dict(name="Radyatör sızıntısı", random=True, mtbf_km=900000, cost=prices.FAULT["radiator_leak"],
                          desc="Radyatör peteği çürüdü: soğutma suyu sürüşte hızla eksilir."),
    "belt": dict(name="Kayış koptu (alternatör ve su pompası)", random=True, mtbf_km=450000, cost=prices.FAULT["belt"],
                 desc="Poly-V kayışı koptu: alternatör şarj etmez, su pompası ve fan dönmez; motor kısa sürede hararet yapar."),
    # yalnızca Ayarlar → Çekim modu ile (rastgele çıkmaz); etkisi oil.pressure_bar ve truck.py'de
    "oil_pump": dict(name="Yağ pompası arızası", random=False, cost=prices.FAULT["oil_pump"],
                     desc="Pompa yeterli basınç üretmiyor (aşınmış dişliler, açık kalan tahliye valfi): yağ basıncı "
                          "düşer, kırmızı yağ lambası yanar. Motoru durdurun; bu halde sürmek yatakları aşındırır."),
    "head_gasket": dict(name="Silindir kapak contası yandı", random=False, cost=prices.FAULT["head_gasket"],
                        desc="Hararet sonucu: yağa soğutma suyu karışıyor, su eksiliyor, sistem basınçlanıyor."),
    "engine_seized": dict(name="Motor kilitlendi (yatak sardı)", random=False, cost=prices.FAULT["engine_seized"],
                          desc="Yağsız çalışma veya aşırı hararet sonucu. Motor çalışmaz, revizyon gerekli."),
    "block_cracked": dict(name="Motor bloğu donarak çatladı", random=False, cost=prices.FAULT["block_cracked"],
                          desc="Antifrizsiz suyla donma sonucu. Büyük kaçak, motor değişimi gerekli."),
    "radiator_cracked": dict(name="Radyatör donarak çatladı", random=False, cost=prices.FAULT["radiator_cracked"],
                             desc="Antifrizsiz suyla donma sonucu. Soğutma suyu hızla kaçar."),
    "battery_frozen": dict(name="Akü dondu", random=False, cost=prices.FAULT["battery_frozen"],
                           desc="Boş akünün elektroliti dondu, plakalar hasar gördü. Aküler değiştirilmeli."),
}
_SHAPE = 1.6
_GAMMA = math.gamma(1 + 1 / _SHAPE)

# Arıza tespiti (Motor Analizi; Grand Truck Simulator 2'deki "Diagnosis" gibi): grup → parça (kimlik, ad, arıza türleri).
# Yüzde, parçanın yaşına göre arızasız kalma olasılığıdır (Weibull; yeni %100, ortalama ömründe ~%43), arızalıysa 0.
PART_GROUPS = (
    ("Motor", (("turbo", "Turbo", ("turbo",)), ("injector", "Enjektörler", ("injector",)),
               ("egr_valve", "EGR valfi", ("egr_valve",)), ("intercooler", "Intercooler", ("intercooler",)),
               ("air_filter", "Hava filtresi", ("air_filter",)), ("fuel_filter", "Yakıt filtresi", ("fuel_filter",)),
               ("preheater", "Ön ısıtma", ("preheater",)), ("oil_leak", "Karter contası", ("oil_leak",)))),
    ("Soğutma", (("radiator", "Radyatör", ("radiator_leak",)), ("water_pump", "Su pompası", ("water_pump",)),
                 ("thermostat", "Termostat", ("thermostat_closed", "thermostat_open")),
                 ("fan_clutch", "Fan kavraması", ("fan_clutch",)), ("belt", "Kayış", ("belt",)))),
    ("Elektrik", (("alternator", "Alternatör", ("alternator",)), ("starter", "Marş motoru", ("starter",)),
                  ("abs_sensor", "ABS sensörü", ("abs_sensor",)))),
    ("Aktarma ve direksiyon", (("clutch_actuator", "Debriyaj aktüatörü", ("clutch_actuator",)),
                               ("gearbox_cooler", "Şanzıman yağ soğutucusu", ("gearbox_cooler",)),
                               ("steering", "Direksiyon pompası", ("steering_leak",)))),
)
PARTS = {pid: (name, keys) for _, parts in PART_GROUPS for pid, name, keys in parts}


@dataclass
class Faults:
    active: list = field(default_factory=list)
    ages_km: dict = field(default_factory=dict)

    def init_ages(self, odometer_km):
        """Yaşı bilinmeyen parçalar (yeni kayıt ya da sonradan eklenen parça): tırın km'si, en fazla ömrünün %30'u
        (ikinci el tırda parçaların bir kısmı zaten yenilenmiştir; yeni eklenen parçalar hemen arıza yapmasın)."""
        for k, d in FAULTS.items():
            if d["random"]:
                self.ages_km.setdefault(k, min(float(odometer_km), 0.3 * d["mtbf_km"]))

    def has(self, key):
        return key in self.active

    def add(self, key):
        if key not in self.active:
            self.active.append(key)
            return True
        return False

    def repair(self, key):
        if key in self.active:
            self.active.remove(key)
        if FAULTS[key]["random"]:
            self.ages_km[key] = 0.0
        return FAULTS[key]["cost"]

    def condition(self, keys):
        """Parçanın durumu 0..1: arızalıysa 0, değilse yaşına göre arızasız kalma olasılığı (türlerin çarpımı)."""
        c = 1.0
        for k in keys:
            if k in self.active:
                return 0.0
            eta = FAULTS[k]["mtbf_km"] / _GAMMA
            c *= math.exp(-(max(self.ages_km.get(k, 0.0), 0.0) / eta) ** _SHAPE)
        return c

    def replace(self, keys):
        """Parça değişimi (Arıza tespiti): arıza giderilir, yaş sıfırlanır; arızalı olmasa da önceden yenilenebilir."""
        for k in keys:
            self.repair(k)

    def step(self, km, rng, enabled, skip=()):
        """Gidilen km'ye göre parça yaşını artırır ve rastgele arıza üretir. Yeni arızaları döndürür."""
        new = []
        if km <= 0:
            return new
        for k, d in FAULTS.items():
            if not d["random"]:
                continue
            age = self.ages_km.get(k, 0.0) + km
            self.ages_km[k] = age
            if not enabled or k in self.active or k in skip:
                continue
            if k == "thermostat_open" and "thermostat_closed" in self.active:
                continue
            if k == "thermostat_closed" and "thermostat_open" in self.active:
                continue
            eta = d["mtbf_km"] / _GAMMA
            hazard = _SHAPE / eta * (max(age, 1.0) / eta) ** (_SHAPE - 1)
            if rng.random() < hazard * km:
                self.active.append(k)
                new.append(k)
        return new
