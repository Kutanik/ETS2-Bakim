"""Bir kamyonun tüm bakım/motor modellerini bir araya getirir."""
import math
import random
from dataclasses import asdict

from . import battery as battery_mod
from . import coolant as coolant_mod
from . import engines
from . import oil as oil_mod
from . import preheat as preheat_mod
from . import prices
from . import rates as rates_mod
from . import tires as tires_mod
from . import transmission as trans_mod
from . import vehicles
from .adblue import AdBlue, has_scr
from .analysis import Analysis
from .battery import Battery, electrical_load_a
from .coolant import Coolant
from .dpf import DPF
from .engine import EngineHealth, EngineSim, EngineSpec
from .faults import FAULTS, PARTS as FAULT_PARTS, Faults
from .oil import Oil
from .thermal import Thermal
from .tires import Tires
from .transmission import Transmission
from .i18n import M, upgrade_log_entry
from .util import clamp, load_dataclass

GAME_WEAR_KEYS = ("engine", "transmission", "cabin", "chassis", "wheels")
LOG_MAX = 400
TREND_EVERY_KM = 250.0
TREND_MAX = 600
STEER_LEAK_PER_H = 0.02      # direksiyon kaçağında hidrolik yağının saatte eksilen kısmı (motor çalışırken)
STEER_LOW = 0.6              # bunun altında direksiyon desteği azalır (kırmızı lamba)
PARK_REMIND_S = 3.0          # motor kapalı, kontak açık, tır duruyor ve park freni çekilmemişse bu kadar sn sonra uyarı
STARTER_FAIL_P = 0.4         # marş motoru arızasında bir marş denemesinin başarısız olma olasılığı
PUMP_WEAR_PER_S = 0.0015     # yağ pompası arızasıyla çalışırken motor sağlığı kaybı (% / oyun sn, yük çarpanıyla)


class TruckModel:
    def __init__(self, key, info):
        self.key = key
        self.info = dict(info)
        self.spec = EngineSpec()
        self.oil = Oil()
        self.coolant = Coolant()
        self.thermal = Thermal()
        self.battery = Battery()
        self.dpf = DPF()
        self.tires = Tires()
        self.adblue = AdBlue()
        self.trans = Transmission()
        self.steer_fluid = 1.0       # direksiyon hidrolik yağı (oran)
        self.faults = Faults()
        self.health = EngineHealth()
        self.analysis = Analysis()
        self.session = Analysis()
        self.trip = Analysis()
        self.trip_info = {"src": "", "dst": "", "cargo": "", "start_gm": None, "start_odo": None}
        self.temporary = False   # oyunun hızlı iş için verdiği geçici tır
        self.log = []
        self.trend = []
        self.reports = {}
        self.costs_total = 0.0
        self.trend_last = None
        self.prev_game_wear = None
        self.prev_game_wears = None   # oturumdaki son oyun hasarları (kaydedilmez: kayıt yüklemede yanlış algı olmasın)
        self.initialized = False
        # anlık durum
        self.eng = EngineSim(self.spec)
        self.detector = engines.EngineDetector()
        self.detect_check = 0.0
        self.model_tried = False
        self.prev_engine_on = None
        self.killed = False
        self.kill_reason = ""
        self.idle_min = 0.0
        self.crank_msg = ""
        self.pending_stop = None
        self.oil_pressure = 0.0
        self.oil_low_s = 0.0                   # düşük yağ basıncı ne kadardır sürüyor (gerçek sn, uyarı gecikmesi)
        self.prev_fuel_l = None
        self.preheat = preheat_mod.Preheat()   # anlık durum (kaydedilmez)
        self.unsecured_s = 0.0                 # park freni çekilmeden duran tır (gerçek sn)
        self.ages_checked = False
        self.flags = dict(lugging=False, overrev=False, idle=False, cold_load=False, overheat=0.0,
                          running=False, load_a=0.0, park_warn=False, park_moving=False, steer_assist=True)

    # ------------------------------------------------------------------ kayıt
    def to_dict(self):
        return {
            "version": 1, "key": self.key, "info": self.info, "spec": asdict(self.spec),
            "oil": asdict(self.oil), "coolant": asdict(self.coolant), "thermal": asdict(self.thermal),
            "battery": asdict(self.battery), "dpf": asdict(self.dpf), "faults": asdict(self.faults),
            "tires": asdict(self.tires), "adblue": asdict(self.adblue),
            "transmission": asdict(self.trans), "steer_fluid": self.steer_fluid,
            "health": asdict(self.health), "analysis": asdict(self.analysis), "trip": asdict(self.trip),
            "trip_info": self.trip_info, "temporary": self.temporary, "log": self.log[-LOG_MAX:],
            "trend": self.trend[-TREND_MAX:], "reports": self.reports, "costs_total": self.costs_total,
            "trend_last": self.trend_last, "prev_game_wear": self.prev_game_wear, "initialized": self.initialized,
        }

    @classmethod
    def from_dict(cls, d):
        t = cls(d.get("key", ""), d.get("info", {}))
        t.spec = load_dataclass(EngineSpec, d.get("spec"))
        t.oil = load_dataclass(Oil, d.get("oil"))
        t.coolant = load_dataclass(Coolant, d.get("coolant"))
        t.thermal = load_dataclass(Thermal, d.get("thermal"))
        t.battery = load_dataclass(Battery, d.get("battery"))
        t.dpf = load_dataclass(DPF, d.get("dpf"))
        t.tires = load_dataclass(Tires, d.get("tires"))     # eski kayıtlarda yok: ilk adımda kurulur
        t.adblue = load_dataclass(AdBlue, d.get("adblue"))
        t.trans = load_dataclass(Transmission, d.get("transmission"))   # eski kayıtlarda yok: ilk adımda kurulur
        t.steer_fluid = clamp(float(d.get("steer_fluid", 1.0) or 0.0), 0.0, 1.0)
        t.faults = load_dataclass(Faults, d.get("faults"))
        t.health = load_dataclass(EngineHealth, d.get("health"))
        t.analysis = load_dataclass(Analysis, d.get("analysis"))
        t.trip = load_dataclass(Analysis, d.get("trip"))
        if "wear_km" not in (d.get("oil") or {}):
            t.oil.wear_km, t.oil.wear_min = t.oil.km, t.oil.minutes_age
        if "wear_km" not in (d.get("coolant") or {}):
            t.coolant.wear_km, t.coolant.wear_min = t.coolant.km, t.coolant.minutes_age
        t.trip_info.update(d.get("trip_info") or {})
        t.temporary = bool(d.get("temporary", False))
        t.log = [upgrade_log_entry(e) for e in d.get("log", [])]   # eski düz Türkçe kayıtlar da seçili dilde görünsün
        t.trend = d.get("trend", [])
        t.reports = d.get("reports", {})
        t.costs_total = d.get("costs_total", 0.0)
        t.trend_last = d.get("trend_last")
        t.prev_game_wear = d.get("prev_game_wear")
        t.initialized = d.get("initialized", True)
        t.eng = EngineSim(t.spec)
        t.battery.charger = False
        t.model_tried = bool(t.spec.model_key) or t.spec.mode != "auto"
        return t

    # ------------------------------------------------------------------ yardımcılar
    def event(self, f, level, msg, cost=0.0, kind="olay", manual=False):
        """msg: i18n M(...) sözlüğü; kayıtta şablon+parametre saklanır, gösterimde seçili dile çevrilir.
        manual: Ayarlar → Çekim modu ile elle yapıldı (kayıtta işaretlenir)."""
        if isinstance(msg, str):
            msg = M(msg)
        e = {"gm": f.game_minutes, "odo": round(f.odometer_km, 1), "level": level, "m": msg["m"],
             "a": msg.get("a") or {}, "cost": round(cost, 2), "kind": kind}
        if manual:
            e["manual"] = True
        self.log.append(e)
        if len(self.log) > LOG_MAX:
            del self.log[: len(self.log) - LOG_MAX]
        if cost:
            self.costs_total += cost
        return e

    @property
    def veh(self):
        """Araç sınıfı: truck | bus | car (TruckersMP otomobili / otobüsü; vehicles.py)."""
        return vehicles.kind_of(self.spec)

    def apply_spec(self):
        veh = self.veh
        self.oil.capacity_l = self.spec.oil_capacity_l
        self.coolant.capacity_l = self.spec.coolant_capacity_l
        self.battery.capacity_ah = self.spec.battery_ah
        self.battery.volts = vehicles.volts(veh)
        self.tires.car = veh == "car"
        self.eng.spec = self.spec
        if self.oil.grade not in oil_mod.grades_for(veh):
            # araç sınıfı değişti (ör. TruckersMP'de otomobile geçildi): sınıfa uygun yağ, otomobilde G13 ve AGM akü
            frac = self.oil.level_frac
            g = vehicles.DEFAULT_OIL.get(veh, "10w40")
            self.oil.change(g)
            self.oil.change(g)
            self.oil.volume_l = min(1.0, frac or 1.0) * self.oil.capacity_l
            if veh == "car":
                self.coolant.change(vehicles.DEFAULT_COOLANT["car"], max(0.4, self.coolant.glycol))
                self.battery.kind = vehicles.DEFAULT_BATTERY_KIND["car"]

    def first_time_setup(self, f, ambient):
        """Kamyon ilk kez görüldüğünde kilometresine göre makul bir başlangıç durumu kurar."""
        odo = f.odometer_km
        if self.spec.mode == "auto":
            self.auto_select(f)
        self.apply_spec()
        self.oil.volume_l = self.oil.capacity_l
        self.coolant.volume_l = self.coolant.capacity_l
        self.thermal.t_cool = self.thermal.t_oil = ambient
        self.battery.temp = ambient
        self.faults.init_ages(odo)
        self.trend_last = odo
        self.prev_game_wear = f.wear["engine"]
        self._setup_tires_adblue(f, ambient)
        if odo < 2000:
            self.event(f, "info", M("Yeni kamyon: tüm sıvılar ve akü yeni."), kind="servis")
        else:
            rnd = random.Random(hash(self.key) & 0xFFFF)
            self.health.health = clamp(100 - odo / 1_500_000 * 80, 25, 100)
            used = rnd.uniform(0.2, 0.55)
            km = used * self.oil.spec["interval_km"]
            self._pre_age_oil(km)
            self.coolant.inhibitor = clamp(1 - min(odo, 900000) / 1_200_000, 0.35, 1.0)
            self.coolant.minutes_age = rnd.uniform(0.3, 2.5) * 365 * 1440
            self.coolant.km = self.coolant.minutes_age / 1440 / 365 * 120000
            self.coolant.wear_km, self.coolant.wear_min = self.coolant.km, self.coolant.minutes_age
            self.battery.soh = rnd.uniform(0.78, 0.95)
            self.battery.soc = rnd.uniform(0.75, 0.9)
            self.battery.minutes_age = rnd.uniform(1.0, 3.0) * 365 * 1440
            # ~460 bin km'de bir kül temizliği yapılmış varsayılır
            self.dpf.ash_g = (odo * 0.0013) % (0.75 * self.dpf.ASH_CAP)
            self.dpf.soot_g = rnd.uniform(0.2, 0.5) * self.dpf.soot_cap
            self.event(f, "warn", M("Kamyon ilk kez görüldü ({odo:,.0f} km). Bakım geçmişi bilinmiyor: yağ analizi ve "
                                    "genel kontrol önerilir.", odo=odo), kind="servis")
        self.initialized = True

    def _setup_tires_adblue(self, f, ambient):
        """Lastikler ve AdBlue için kilometreye göre başlangıç (eski kayıtlarda da ilk adımda çağrılır)."""
        rnd = random.Random((hash(self.key) ^ 0x5A5A) & 0xFFFF)
        self.tires.first_setup(f, f.odometer_km, rnd, ambient)
        self.adblue.capacity_l = f.adblue_cap if f.adblue_cap > 0 else self.adblue.capacity_l
        self.adblue.level_l = self.adblue.capacity_l * (rnd.uniform(0.45, 0.95) if f.odometer_km > 2000 else 1.0)

    def auto_select(self, f):
        """Telemetrideki marka/modelden motor seçeneklerini bulur ve varsayılan motoru uygular."""
        self.model_tried = True
        m = engines.auto_spec(self.spec, f.brand_id, f.truck_id, f.name)
        if self.spec.electric:
            self.event(f, "warn", M("Elektrikli kamyon algılandı: bu simülatör dizel motorlar içindir, değerler anlamsız olabilir."))
        # model ve motor adları M(...) ile: genel motor listesinin adları (engines.GENERIC) seçili dilde görünsün
        if m and self.veh == "car":
            self.event(f, "info", M("Araç algılandı: {model} ({veh_t}). Varsayılan motor {engine}; benzinli / dizel motoru "
                                    "Ayarlar'dan seçebilirsiniz.", model=M(m[3]), veh_t=vehicles.NAMES["car"],
                                    engine=M(self.spec.name)), kind="servis")
        elif m:
            self.event(f, "info", M("Model algılandı: {model}. Varsayılan motor {engine} seçildi; tam gazda sürüşten "
                                    "gerçek motor algılanacak.", model=M(m[3]), engine=M(self.spec.name)), kind="servis")
        else:
            self.event(f, "warn", M("Kamyon modeli tanınmadı ({truck}). Ayarlar'dan motoru girin.", truck=f"{f.brand} {f.name}"))
        return m

    def set_engine(self, e):
        """Motoru değiştirir; yağ ve su seviyelerini oran olarak korur."""
        of, cf = self.oil.level_frac, self.coolant.level_frac
        engines.apply_engine(self.spec, e)
        self.apply_spec()
        self.oil.volume_l = of * self.oil.capacity_l
        self.coolant.volume_l = cf * self.coolant.capacity_l

    def set_vehicle(self, f, choice):
        """Ayarlar → Araç tipi: auto (motor veritabanındaki modelden algılanan) | truck | bus | car. Sınıf değişince o
        sınıfın varsayılanları kurulur: motor listesi ve varsayılan motor, akü (12 / 24 V), yağ, antifriz, lastikler.
        Yağ ve su seviyeleri oran olarak korunur. Dönüş: seçim geçerli mi."""
        if choice not in vehicles.CHOICES:
            return False
        old = self.veh
        self.spec.vehicle_override = choice
        if self.veh != old:
            of, cf = self.oil.level_frac, self.coolant.level_frac
            self.detector.reset()
            if engines.auto_spec(self.spec, f.brand_id, f.truck_id, f.name) is None:
                engines.reset_engine(self.spec)   # bu sınıfa uyan model yok (ör. otomobil modeli için tır seçildi)
            self.model_tried = True
            self.apply_spec()
            self.oil.volume_l = of * self.oil.capacity_l
            self.coolant.volume_l = cf * self.coolant.capacity_l
            # şanzıman ve debriyaj da yeni sınıfınki (tır yağ aralığıyla kurulmuş durum otomobilde hemen "değişim" derdi)
            t_oil, t_clutch = self.trans.t_oil, self.trans.t_clutch
            self.trans = Transmission()
            self.trans.first_setup(f.odometer_km, random.Random((hash(self.key) ^ 0x33CC) & 0xFFFF), t_oil, self.veh)
            self.trans.t_clutch = t_clutch
        if choice == "auto":
            msg = M("Araç tipi: otomatik algılama ({veh_t}). Motor: {engine}.", veh_t=vehicles.NAMES[self.veh],
                    engine=M(self.spec.name))
        else:
            msg = M("Araç tipi elle seçildi: {veh_t}. Motor: {engine}; Ayarlar'dan değiştirebilirsiniz.",
                    veh_t=vehicles.NAMES[self.veh], engine=M(self.spec.name))
        self.event(f, "info", msg, kind="servis")
        return True

    def _check_detection(self, f):
        # TruckersMP otomobilinde oyun içi tork sahte (iki motor da aynı): sürüşten algılanamaz, seçim Ayarlar'dan
        if self.spec.mode != "auto" or self.veh == "car":
            return
        m = engines.model_by_key(self.spec.model_key)
        best, est, confident = self.detector.suggest(m)
        if best and confident and best["id"] != self.spec.engine_id:
            old = self.spec.name
            self.set_engine(best)
            self.event(f, "info", M("Motor sürüşten algılandı: {engine} ({hp} hp, ölçülen tork ≈{nm:,.0f} Nm). "
                                    "Önceki seçim: {old}.", engine=best["label"], hp=best["hp"], nm=est, old=old),
                       kind="servis")

    def _pre_age_oil(self, km):
        o = self.oil
        e = km * 0.32 / o.capacity_l
        h = km / 75.0
        o.tbn *= math.exp(-0.001444 * o.spec["durability"] * e)
        o.soot = 0.0026 * e * 1.2
        o.ox = 0.025 * 0.8 / o.spec["ox_res"] * h
        o.shear = o.spec["shear_max"] * (1 - math.exp(-h / 600.0))
        o.fe, o.cr, o.pb, o.cu, o.al = 0.045 * h, 0.006 * h, 0.008 * h, 2 + 0.01 * h, 0.01 * h
        o.si = 3 + 0.015 * h
        o.km, o.hours, o.filter_km = km, h, km
        o.minutes_age = h * 60 * 2.5
        o.wear_km, o.wear_min = km, o.minutes_age
        o.volume_l = o.capacity_l * 0.95
        o.consumed_l = km * 0.00015

    def request_stop(self, f, reason, manual=False):
        if not self.killed:
            self.event(f, "crit", reason, manual=manual)
        self.killed = True
        self.kill_reason = reason
        self.pending_stop = reason

    # ------------------------------------------------------------------ olaylar
    def _on_start(self, f, env):
        self.analysis.starts += 1
        self.session.starts += 1
        t_oil = self.thermal.t_oil
        visc = self.oil.viscosity(t_oil)
        for k in ("engine_seized", "block_cracked"):
            if self.faults.has(k):
                self.analysis.failed_starts += 1
                self.request_stop(f, M("Marş başarısız: {reason}.", reason=M(FAULTS[k]["name"])))
                return
        # marş motoru arızası: selenoid / kömürler zaman zaman temas etmez (birkaç denemede çalışabilir)
        if self.faults.has("starter") and env["rng"].random() < STARTER_FAIL_P:
            self.analysis.failed_starts += 1
            self.session.failed_starts += 1
            self.request_stop(f, M("Marş başarısız: {reason}.",
                                   reason=M("marş motoru çevirmedi (selenoid / kömürler); motoru kapatıp tekrar deneyin")))
            return
        ok, msg, v = self.battery.crank(visc)
        self.crank_msg = msg
        if not ok:
            self.analysis.failed_starts += 1
            self.session.failed_starts += 1
            self.request_stop(f, M("Marş başarısız: {reason}.", reason=msg))
            return
        if msg:
            self.event(f, "warn", msg)
        # ön ısıtma: lamba sönmeden marş soğukta ateşlemeyi zorlaştırır, çok soğukta motor hiç ateşlemez
        t_eng = self.thermal.t_cool
        if self.spec.fuel == "diesel" and preheat_mod.duration_s(t_eng) > 0:
            faulty = self.faults.has("preheater")
            q = self.preheat.quality(t_eng, faulty)
            if (faulty and t_eng < preheat_mod.FAULT_NO_FIRE_BELOW_C) or (q < 0.5 and t_eng < preheat_mod.NO_FIRE_BELOW_C):
                self.analysis.failed_starts += 1
                self.session.failed_starts += 1
                why = (M("ön ısıtma arızalı, motor {t:.0f} °C'de ateşlemedi", t=t_eng) if faulty else
                       M("ön ısıtma lambası sönmeden marşa basıldı, motor {t:.0f} °C'de ateşlemedi; kontak açıkken lamba "
                         "sönene kadar bekleyip tekrar deneyin", t=t_eng))
                self.request_stop(f, M("Marş başarısız: {reason}.", reason=why))
                return
            if q < 1.0:
                self.health.damage(0.004 * (1.0 - q))
                self.event(f, "warn", M("Ön ısıtma tamamlanmadan marş ({t:.0f} °C): zor ateşleme, beyaz duman, ek aşınma.",
                                        t=t_eng))
        sev = self.oil.cold_start(t_oil)
        if t_oil < 40:
            self.analysis.cold_starts += 1
            self.session.cold_starts += 1
            if sev > 0.4:
                self.event(f, "info", M("Soğuk marş ({t:.0f} °C yağ, {visc:,.0f} cSt): ilk dakikalarda yüklenmeyin.",
                                        t=t_oil, visc=visc))

    def _on_stop(self):
        self.oil.engine_stopped(self.thermal.t_oil)
        self.idle_min = 0.0

    # ------------------------------------------------------------------ ana adım
    def step(self, f, dt_real, dt_game, env):
        """env: ambient, settings, rng, km, dfuel, decel"""
        st = env["settings"]
        amb = env["ambient"]
        R = rates_mod.all_rates(st)
        if self.prev_engine_on is None:
            self.prev_engine_on = f.engine_on
        if f.engine_on and not self.prev_engine_on:
            self.killed = False
            self._on_start(f, env)
        if not f.engine_on and self.prev_engine_on:
            self._on_stop()
        if not f.engine_on:
            self.killed = False
            self.pending_stop = None
        self.prev_engine_on = f.engine_on
        running = f.engine_on and not self.killed

        km = env["km"]
        dt_h = dt_game / 3600.0
        speed = abs(f.speed_kmh)

        # elektrik ve aksesuarlar
        load_a = electrical_load_a(f, f.electric_on, running, env["ambient"], vehicles.load_scale(self.veh))
        # ön ısıtma ~150 A çeker; gerçek saniyelerle çalıştığı için aküye oyun saatine göre ölçeklenmiş yük gider
        self.preheat.step(f, dt_real, self.thermal.t_cool if self.spec.fuel == "diesel" else 99.0)   # benzinlide ön ısıtma yok
        pre_a = self.preheat.current_a(self.faults.has("preheater"))
        batt_load_a = load_a + (pre_a * dt_real / dt_game if dt_game > 0 else 0.0)
        load_a += pre_a
        # gerçek devir ölçekli otomobil modunda (sınır ~6500 rpm) motor modeli küçültülmüş devirle çalışır (vehicles.py)
        rk = vehicles.rpm_scale(self.veh, f.rpm_max)
        fan_kw = 0.0
        if running and self.thermal.fan_on and not self.faults.has("fan_clutch"):
            fan_kw = 18.0 * (f.rpm / rk / 1800.0) ** 3
        acc_kw = 3.0 + self.battery.alt_current * 28.0 / 0.55 / 1000.0 + fan_kw

        # otomatik motor seçimi
        if self.spec.mode == "auto" and not self.model_tried and (f.truck_id or f.brand_id):
            of, cf = self.oil.level_frac, self.coolant.level_frac
            self.auto_select(f)
            self.apply_spec()
            self.oil.volume_l = of * self.oil.capacity_l
            self.coolant.volume_l = cf * self.coolant.capacity_l
        self.detector.feed(f, dt_real, running, self.spec)
        self.detect_check += dt_real
        if self.detect_check >= 3.0:
            self.detect_check = 0.0
            self._check_detection(f)

        # motor
        self.eng.feed_fuel(env["dfuel"], dt_game, running)
        self.eng.update(f, running, dt_game, amb, acc_kw, self.dpf.burning, rk)
        e = self.eng
        rpm, load = e.rpm, e.load
        lugging = running and rpm < 1000 and load > 0.8 and speed > 3
        overrev = running and rpm > min(f.rpm_max * 0.97, (self.spec.rated_rpm + 350) * rk)
        idle = running and speed < 3 and load < 0.15
        fuel_l = e.fuel_lps * dt_game
        self.idle_min = self.idle_min + dt_game / 60.0 if idle else 0.0

        # ısıl model
        hg = self.faults.has("head_gasket")
        belt_broken = self.faults.has("belt")          # kayış koptu: su pompası ve fan dönmez, alternatör şarj etmez
        soot_mult = 1.0                                # motor parçası arızalarının is artışı (DPF ve yağdaki kurum)
        for k, m in (("turbo", 2.0), ("injector", 1.8), ("egr_valve", 1.5), ("intercooler", 1.3), ("air_filter", 1.3)):
            if self.faults.has(k):
                soot_mult *= m
        boiled = self.thermal.step(dt_game, dict(
            running=running, rpm=rpm, speed_kmh=speed, q_cool=e.q_cool, q_oil=e.q_oil, ambient=amb,
            retarder_kw=e.p_ret, thermostat_closed=self.faults.has("thermostat_closed") or belt_broken,
            thermostat_open_fault=self.faults.has("thermostat_open"), fan_fail=self.faults.has("fan_clutch") or belt_broken,
            combustion_gas=hg), self.coolant, self.oil.volume_l)
        th = self.thermal
        if boiled > 0:
            self.coolant.lose(boiled)

        overheat = clamp((th.t_cool - 105.0) / 15.0, 0.0, 1.0)
        leak_lph = 0.0
        if self.faults.has("water_pump"):
            leak_lph += 0.25 if running else 0.03
        if self.faults.has("radiator_leak"):
            leak_lph += 0.6 if running else 0.05
        if hg:
            leak_lph += 0.15 if running else 0.02
        if self.faults.has("radiator_cracked"):
            leak_lph += 12.0 if running else 2.0
        if self.faults.has("block_cracked"):
            leak_lph += 20.0 if running else 4.0

        consumed_before = self.oil.total_consumed_l
        self.oil.step(dt_game, dict(
            running=running, rpm=rpm, load=load, t_oil=th.t_oil, fuel_l=fuel_l, km=km if running else 0.0,
            lugging=lugging, idle=idle, regen=self.dpf.burning, engine_wear=self.health.wear,
            overheat=overheat, glycol_leak_lph=0.15 if (hg and running) else 0.0,
            oil_leak=self.faults.has("oil_leak"), rate=R["oil"], burn_mult=4.0 if self.faults.has("turbo") else 1.0,
            soot_factor=(0.12 if self.spec.fuel == "petrol" else 1.0) * min(soot_mult, 2.0),
            metal_factor=self.spec.displacement_l / 13.0 if self.veh == "car" else 1.0))
        oil_used = self.oil.total_consumed_l - consumed_before
        self.coolant.step(dt_game, dict(running=running, km=km, t_cool=th.t_cool,
                                        aeration=self.coolant.level_frac < 0.85, combustion_gas=hg,
                                        leak_lph=leak_lph, rate=R["coolant"]))
        if self.spec.has_dpf:
            self.dpf.step(dt_game, dict(running=running, p_brake=e.p_brake, t_exh=e.exh_temp,
                                        speed_kmh=speed, cold=th.t_cool < 60, lugging=lugging,
                                        oil_consumed_l=oil_used, oil_ash_pct=self.oil.ash_pct,
                                        t_cool=th.t_cool, km=km, rate=R["dpf"], soot_mult=soot_mult))

        # şanzıman ve debriyaj (yağ oyun saatiyle, debriyaj gerçek saniyeyle; transmission.py)
        veh = self.veh
        tr = self.trans
        if not tr.ready:
            tr.first_setup(f.odometer_km, random.Random((hash(self.key) ^ 0x33CC) & 0xFFFF), amb, veh)
        ratio = trans_mod.gear_ratio(f)
        tr.step_oil(dt_game, dict(running=running, p_kw=e.p_brake + e.p_eb, gear=f.gear, ratio=ratio, speed=speed,
                                  t_cool=th.t_cool, ambient=amb, retarder_kw=e.p_ret, has_retarder=f.retarder_steps > 0,
                                  cooler_fault=self.faults.has("gearbox_cooler"), km=km, rate=R["transmission"], veh=veh))
        tr.step_clutch(dt_real, dict(running=running, rpm=rpm, p_kw=e.p_brake, load=load, clutch=f.clutch, gear=f.gear,
                                     ratio=ratio, speed=speed, wheel_r=f.wheel_radius, diff=f.diff_ratio,
                                     peak_nm=self.spec.peak_torque_nm() / rk, actuator_fault=self.faults.has("clutch_actuator"),
                                     ambient=amb, t_cool=th.t_cool, km=km, rate=R["transmission"], veh=veh))

        # direksiyon: hidrolik pompa motordan döner (otomobilde elektrikli direksiyon); kaçakta yağ eksilir
        hydraulic = veh != "car"
        if hydraulic and self.faults.has("steering_leak"):
            self.steer_fluid = max(0.0, self.steer_fluid - STEER_LEAK_PER_H * (1.0 if running else 0.1) * dt_h)
        steer_assist = not hydraulic or (running and self.steer_fluid >= STEER_LOW)

        # park freni: motor kapalı, kontak açık ve tır dururken çekilmemişse hatırlatma; çekiliyken hareket
        if f.electric_on and not f.engine_on and speed < 1.0 and not f.park_brake:
            self.unsecured_s += dt_real
        else:
            self.unsecured_s = 0.0

        # AdBlue (SCR), lastikler ve yakıt
        if has_scr(self.spec, f):
            was = self.adblue.frac
            self.adblue.step(f, fuel_l, load, e.exh_temp or 0.0, running, R["adblue"])
            if was > 0 and self.adblue.frac <= 0:
                self.event(f, "crit", M("AdBlue bitti: gerçek araçta motor gücü düşürülür, yeniden çalıştırmada hız "
                                        "20 km/h ile sınırlanır."))
        if not self.tires.groups:
            self.tires.first_setup(f, f.odometer_km, random.Random(hash(self.key) & 0xFFFF), amb)
        for lvl, msg in self.tires.step(f, dt_game, km, dict(
                ambient=amb, speed=speed, mass_t=f.mass_kg / 1000.0, decel=env["decel"], load=load,
                brake_temp=f.brake_temp, rng=env["rng"], random_faults=st.get("random_faults", True),
                rate=R["tires"], fault_rate=R["faults"])):
            self.event(f, lvl, msg)
        if f.fuel_cap > 0 and self.prev_fuel_l is not None and self.prev_fuel_l > 0.3 >= f.fuel_l:
            self.event(f, "crit", M("Yakıt bitti: dizel sistemine hava girdi (gerçek araçta yakıt alındıktan sonra el "
                                    "pompasıyla havası alınmadan motor çalışmaz)."))
        self.prev_fuel_l = f.fuel_l

        # akü
        if self.battery.charger and (f.engine_on or speed > 1):
            self.battery.charger = False
            self.event(f, "info", M("Akü şarj cihazı söküldü (motor çalıştırıldı / hareket edildi)."))
        was_frozen = self.battery.frozen
        self.battery.step(dt_game, dict(running=running, rpm=rpm, load_a=batt_load_a, ambient=amb,
                                        alternator_ok=not (self.faults.has("alternator") or belt_broken),
                                        rate=R["battery"], drain=R["drain"]))
        if self.battery.frozen and not was_frozen:
            self.faults.add("battery_frozen")
            self.event(f, "crit", M("Akü dondu ve hasar gördü (akü {t:.0f} °C, şarj %{soc:.0f}).",
                                    t=self.battery.temp, soc=self.battery.soc * 100))
        if running and self.battery.voltage < self.battery.ecu_min_v:
            self.request_stop(f, M("Akü voltajı {v:.1f} V'a düştü: ECU kapandı, motor stop etti.", v=self.battery.voltage))

        # yağ basıncı ve yağsız kalma
        p = self.oil.pressure_bar(rpm, th.t_oil, self.health.wear, running, self.faults.has("engine_seized"),
                                  self.faults.has("oil_pump"))
        self.oil_pressure = p
        self.oil_low_s = self.oil_low_s + dt_real if running and p < self.oil.low_pressure_threshold(rpm) else 0.0
        if running and self.faults.has("oil_pump"):
            self.health.damage(PUMP_WEAR_PER_S * dt_game * (0.5 + load))   # düşük basınçla yataklar aşınır
        if running and (p < 0.3 or self.oil.level_frac < 0.45):
            self.health.starvation_s += dt_game * (0.5 + load)
            self.oil.starvation_spike(dt_game / 60.0)
            self.health.damage(0.02 * dt_game * (0.5 + load))
            if self.health.starvation_s > 240 and self.faults.add("engine_seized"):
                self.request_stop(f, M("Yağ basıncı yok: krank yatakları sardı, MOTOR KİLİTLENDİ."))
        else:
            self.health.starvation_s = max(0.0, self.health.starvation_s - dt_game * 0.2)

        # hararet hasarı
        dt_min = dt_game / 60.0
        # (oyun saati 19x hızlı aktığı için eşikler, oyuncuya gerçek zamanda tepki payı bırakacak şekilde)
        if th.t_cool > 115 or (th.boiling and self.coolant.level_frac < 0.6):
            self.health.head_gasket_stress += dt_min * (max(th.t_cool - 115, 0) + 3) / 150.0
            if self.health.head_gasket_stress >= 1.0 and self.faults.add("head_gasket"):
                self.event(f, "crit", M("Aşırı hararet: silindir kapak contası yandı."))
        else:
            self.health.head_gasket_stress = max(0.0, self.health.head_gasket_stress - dt_min / 600.0)
        if th.t_cool > 125 or th.t_oil > 150:
            self.health.seize_stress += dt_min * (max(th.t_cool - 125, th.t_oil - 150, 0) + 2) / 150.0
            self.health.damage(0.03 * dt_min)
            if self.health.seize_stress >= 1.0 and self.faults.add("engine_seized"):
                self.request_stop(f, M("Aşırı hararet: pistonlar sardı, MOTOR KİLİTLENDİ."))

        # donma hasarı (antifrizsiz suda buz genleşmesi)
        if self.coolant.glycol < 0.25:
            if th.block_ice > 0.8 and self.faults.add("block_cracked"):
                self.event(f, "crit", M("Motor bloğundaki su dondu ve bloğu çatlattı!"))
            if th.rad_ice > 0.9 and self.faults.add("radiator_cracked"):
                self.event(f, "crit", M("Radyatördeki su dondu ve radyatörü çatlattı!"))

        # motor sağlığı
        cold_load = running and th.t_oil < 50 and load > 0.6
        mult = self.oil.lubrication_factor() * (1 + 2 * lugging + 1.5 * overrev + 2 * cold_load + 3 * overheat)
        mult *= (1.3 if self.faults.has("injector") else 1.0) * (1.2 if self.faults.has("air_filter") else 1.0)
        self.health.step(dt_h, running, mult * R["engine"])

        # arızalar (eski kayıtlarda yeni parçaların yaşı tırın kilometresinden başlar)
        if not self.ages_checked:
            self.faults.init_ages(f.odometer_km)
            self.ages_checked = True
        for k in self.faults.step(km * R["faults"], env["rng"], st.get("random_faults", True), skip=self.fault_skip()):
            self.event(f, FAULTS[k].get("level", "crit"),
                       M("ARIZA: {name_t} — {desc_t}", name_t=FAULTS[k]["name"], desc_t=FAULTS[k]["desc"]))

        # analiz
        ac = dict(running=running, rpm=rpm, load=load, speed_kmh=speed, km=km, fuel_l=fuel_l,
                  t_cool=th.t_cool, t_oil=th.t_oil, lugging=lugging, overrev=overrev,
                  retarder=e.p_ret > 0, engine_brake=e.p_eb > 0, cruise=f.cruise, overrun=e.overrun,
                  decel=env["decel"], gear=f.gear, brake=f.brake, brake_temp=f.brake_temp,
                  p_ret=e.p_ret, p_eb=e.p_eb, mass_kg=f.mass_kg)
        if f.on_job and f.job_market == "quick_job":
            self.temporary = True
        self.check_trip(f)
        self.analysis.step(dt_game, ac)
        self.session.step(dt_game, ac)
        self.trip.step(dt_game, ac)

        # oyundaki servis noktasında tamir: oyunun hasar değerlerinden biri (motor, şanzıman, kabin, şasi,
        # tekerlek) tır dururken belirgin düşerse tamir yapılmış demektir
        wears = {k: float(f.wear.get(k, 0.0)) for k in GAME_WEAR_KEYS}
        prev = self.prev_game_wears
        if prev and speed < 1.0:
            drop = max(prev.get(k, 0.0) - v for k, v in wears.items())
            if drop > 0.004:
                self.game_repair(f, st, drop, wheels=prev.get("wheels", 0.0) - wears["wheels"] > 0.004)
        self.prev_game_wears = wears
        self.prev_game_wear = wears["engine"]

        # trend
        if self.trend_last is None:
            self.trend_last = f.odometer_km
        if f.odometer_km - self.trend_last >= TREND_EVERY_KM:
            self.add_trend(f)

        self.flags = dict(lugging=lugging, overrev=overrev, idle=idle, cold_load=cold_load,
                          overheat=overheat, running=running, load_a=load_a,
                          park_warn=self.unsecured_s >= PARK_REMIND_S, park_moving=f.park_brake and speed > 3.0,
                          steer_assist=steer_assist)

    def parked_step(self, f, dt_game, amb, settings):
        """Uyku/feribot/tren gibi zaman atlamalarında motor kapalı geçen süre."""
        R = rates_mod.all_rates(settings)
        load_a = electrical_load_a(f, f.electric_on, False, amb, vehicles.load_scale(self.veh))
        if settings.get("hotel_load", True) and vehicles.has_hotel_load(self.veh):
            if amb < 5:
                load_a += 2.5   # park ısıtıcısı
            elif amb > 22:
                load_a += 10.0  # park kliması
        self.thermal.step(dt_game, dict(running=False, rpm=0, speed_kmh=0, q_cool=0, q_oil=0, ambient=amb,
                                        retarder_kw=0, thermostat_closed=False, thermostat_open_fault=False,
                                        fan_fail=False, combustion_gas=False), self.coolant, self.oil.volume_l)
        self.oil.step(dt_game, dict(running=False, oil_leak=self.faults.has("oil_leak"), rate=R["oil"]))
        self.coolant.step(dt_game, dict(running=False, km=0.0, t_cool=self.thermal.t_cool, aeration=False,
                                        combustion_gas=False, leak_lph=0.03 if self.faults.has("water_pump") else 0.0,
                                        rate=R["coolant"]))
        was_frozen = self.battery.frozen
        self.battery.step(dt_game, dict(running=False, rpm=0, load_a=load_a, ambient=amb, alternator_ok=True,
                                        rate=R["battery"], drain=R["drain"]))
        self.tires.parked(dt_game, amb, R["tires"])
        if self.trans.ready:
            self.trans.parked(dt_game, amb, self.thermal.t_cool, self.veh)
        if self.battery.frozen and not was_frozen:
            self.faults.add("battery_frozen")
            self.event(f, "crit", M("Gece akü dondu ve hasar gördü (şarj %{soc:.0f}).", soc=self.battery.soc * 100))
        if self.coolant.glycol < 0.25:
            if self.thermal.block_ice > 0.8 and self.faults.add("block_cracked"):
                self.event(f, "crit", M("Gece motor bloğundaki su dondu ve bloğu çatlattı!"))
            if self.thermal.rad_ice > 0.9 and self.faults.add("radiator_cracked"):
                self.event(f, "crit", M("Gece radyatördeki su dondu ve radyatörü çatlattı!"))

    def add_trend(self, f):
        life, _ = self.oil.life()
        a = self.analysis
        self.trend.append({
            "odo": round(f.odometer_km), "oil_life": round(life * 100, 1), "tbn": round(self.oil.tbn, 2),
            "soot": round(self.oil.soot, 3), "fe": round(self.oil.fe, 1), "pb": round(self.oil.pb, 1),
            "visc": round(self.oil.v100_change_pct(), 1), "inhibitor": round(self.coolant.inhibitor * 100, 1),
            "batt_soh": round(self.battery.soh * 100, 1), "health": round(self.health.health, 2),
            "dpf": round(self.dpf.soot_frac * 100, 1), "ash": round(self.dpf.ash_frac * 100, 1),
            "fuel_total": round(a.fuel_l, 1), "km_total": round(a.distance_km, 1),
        })
        if len(self.trend) > TREND_MAX:
            del self.trend[: len(self.trend) - TREND_MAX]
        self.trend_last = f.odometer_km

    def fault_skip(self):
        """Bu araçta olmayan parçalar: benzinli motorda ön ısıtma, otomobilde hidrolik direksiyon."""
        return (("preheater",) if self.spec.fuel == "petrol" else ()) + (("steering_leak",) if self.veh == "car" else ())

    def repair_fault(self, f, k, garage=False):
        """Bir arızayı onarır, bağlı sistemleri yeniler ve gideri kayda yazar."""
        cost = self.fix_part(k)
        if k == "battery_frozen":  # donmuş akü onarılmaz, serviste yenisi takılır
            tmpl = ("Oyundaki serviste donmuş aküler yenilendi (2 x 12 V {ah:.0f} Ah)." if self.battery.blocks == 2
                    else "Oyundaki serviste donmuş akü yenilendi (12 V {ah:.0f} Ah).")
            self.event(f, "info", M(tmpl, ah=self.spec.battery_ah), cost, "servis")
            return cost
        msg = "Oyundaki serviste onarıldı: {name_t}." if garage else "Onarıldı: {name_t}."
        self.event(f, "info", M(msg, name_t=FAULTS[k]["name"]), cost, "servis")
        return cost

    def fix_part(self, k):
        """Arızalı parçayı yeniler, bağlı sistemleri düzeltir; kayıt ve gider çağırana kalır. Dönüş: ücret."""
        if k == "battery_frozen":  # donmuş akü onarılmaz, yenisi takılır
            cost = self.battery.replace(self.spec.battery_ah, self.battery.kind)
            if k in self.faults.active:
                self.faults.active.remove(k)
            return cost
        self.faults.repair(k)
        cost = prices.fault(k, self.veh)
        if k == "engine_seized":
            self.health.health = max(self.health.health, 92.0)
            self.health.seize_stress = self.health.starvation_s = 0.0
            self.oil.change(self.oil.grade, True)
        elif k == "block_cracked":
            self.health = EngineHealth()
            self.oil.change(self.oil.grade, True)
            self.coolant.change(self.coolant.type, 0.5)
            self.thermal.block_ice = self.thermal.rad_ice = 0.0
        elif k == "head_gasket":
            self.health.head_gasket_stress = 0.0
            self.oil.change(self.oil.grade, True)
            self.coolant.change(self.coolant.type, max(0.4, self.coolant.glycol))
        elif k == "radiator_cracked":
            self.thermal.rad_ice = 0.0
            self.coolant.change(self.coolant.type, max(0.4, self.coolant.glycol))
        elif k == "steering_leak":
            self.steer_fluid = 1.0          # kaçak giderildi, hidrolik yağı tamamlandı, havası alındı
        return cost

    def game_repair(self, f, settings, drop, wheels=False):
        """Oyundaki servis noktasında tamir yapıldı: istenirse simülasyondaki arızalı parçalar da onarılır.
        wheels: oyunun tekerlek hasarı da onarıldı (lastikler yenilendi; ücreti oyun aldı)."""
        n = len(self.faults.active)
        self.event(f, "info", M("Oyundaki serviste tamir yapıldı (oyun hasarı %{d:.0f} azaldı).", d=drop * 100),
                   kind="servis")
        if settings.get("repair_faults_on_game_repair", True):
            for k in list(self.faults.active):
                self.repair_fault(f, k, garage=True)
            self.killed = False
            if wheels:
                self.tires.replace("all")
                self.event(f, "info", M("Oyundaki serviste lastikler yenilendi."), kind="servis")
        if settings.get("auto_service_on_repair"):
            self.auto_service(f)
        return n

    def station_refuel(self, f, liters, settings):
        """Oyunda yakıt alındı: istenirse AdBlue da pompadan tamamlanır (oyun AdBlue'yu kendisi harcamıyorsa)."""
        if not (settings.get("adblue_with_fuel", True) and has_scr(self.spec, f) and self.adblue.source == "sim"):
            return
        if self.adblue.frac < 0.97:
            added, cost = self.adblue.fill()
            self.event(f, "info", M("Yakıtla birlikte {l:.1f} L AdBlue alındı.", l=added), cost, "servis")

    def auto_service(self, f):
        cost = self.oil.change(self.oil.grade, True, prices.v("OIL_FILTER", self.veh))
        added, c2 = self.coolant.top_up("premix", self.coolant.capacity_l - self.coolant.volume_l)
        self.event(f, "info", M("Otomatik bakım: yağ + filtre değişti, {l:.1f} L antifriz eklendi.", l=added), cost + c2, "servis")

    # ------------------------------------------------------------------ yolculuk
    def check_trip(self, f):
        """Yeni bir iş (kalkış → varış) başladığında yolculuk analizini sıfırlar."""
        ti = self.trip_info
        if f.on_job and f.city_src and f.city_dst and (f.city_src, f.city_dst) != (ti.get("src"), ti.get("dst")):
            self.reset_trip(f)
            ti.update(src=f.city_src, dst=f.city_dst, cargo=f.cargo)
            self.event(f, "info", M("Yeni yolculuk: {src} → {dst}.", src=f.city_src, dst=f.city_dst))
        elif ti.get("start_gm") is None:
            ti.update(start_gm=f.game_minutes, start_odo=f.odometer_km)

    def reset_trip(self, f):
        self.trip = Analysis()
        self.trip_info.update(src="", dst="", cargo="", start_gm=f.game_minutes, start_odo=f.odometer_km)

    # ------------------------------------------------------------------ servis işlemleri
    def action(self, f, name, p):
        """Dönüş: (başarılı, mesaj) — mesaj i18n M(...) sözlüğüdür."""
        stationary = abs(f.speed_kmh) < 1.0
        engine_off = not f.engine_on
        free = ("oil_sample", "coolant_test", "battery_test", "battery_charger", "jump_start", "trip_reset", "tire_inflate")
        if name not in free and not (stationary and engine_off):
            return False, M("Bu işlem için kamyon durmuş ve motor kapalı olmalı.")
        if name in ("oil_sample", "coolant_test", "battery_test") and not stationary:
            return False, M("Ölçüm için kamyonu durdurun.")
        if name == "tire_inflate":
            if not stationary:
                return False, M("Lastik basıncı için kamyonu durdurun.")
            hot = max((s["temp"] for s in self.tires.groups.values()), default=20.0)
            n = self.tires.inflate()
            msg = M("Lastik basınçları ayarlandı ({n} dingil).", n=n)
            if hot > 45:
                msg = M("Lastik basınçları ayarlandı ({n} dingil). Lastikler sıcakken ayarlandı: soğuyunca basınç düşük "
                        "kalabilir.", n=n)
            self.event(f, "info", msg, 0.0, "servis")
            return True, msg
        if name == "tire_puncture":
            cost = self.tires.repair_puncture()
            if not cost:
                return False, M("Patlak lastik yok.")
            self.event(f, "info", M("Yavaş patlak tamir edildi, basınç ayarlandı."), cost, "servis")
            return True, M("Patlak tamir edildi.")
        if name == "tire_replace":
            axle, tier = p.get("axle", "all"), p.get("tier", "premium")
            if axle != "all" and axle not in self.tires.groups:
                return False, M("Bu dingil yok.")
            if tier not in tires_mod.TIERS:
                return False, M("Bilinmeyen lastik sınıfı.")
            if axle == "steer" and not tires_mod.tier_allowed("steer", tier):
                return False, M("Kaplama lastik ön (yönlendirilen) dingile takılmaz.")
            if self.tires.car and tires_mod.TIERS[tier]["rear_only"]:
                return False, M("Kaplama lastik otomobile takılmaz.")
            cost = self.tires.replace(axle, tier)
            tier_t = tires_mod.TIERS[tier]["name"]
            msg = (M("Tüm lastikler yenilendi ({tier_t}).", tier_t=tier_t) if axle == "all" else
                   M("Lastikler yenilendi: {grp_t}, {tier_t}.", grp_t=tires_mod.GROUP_NAMES[axle], tier_t=tier_t))
            self.event(f, "info", msg, cost, "servis")
            return True, msg
        if name == "adblue_fill":
            if not has_scr(self.spec, f):
                return False, M("Bu kamyonda AdBlue (SCR) yok.")
            added, cost = self.adblue.fill(p.get("liters"))
            msg = M("{l:.1f} L AdBlue eklendi (depo %{lvl:.0f}).", l=added, lvl=self.adblue.frac * 100)
            self.event(f, "info", msg, cost, "servis")
            return True, msg
        if name == "trip_reset":
            self.reset_trip(f)
            return True, M("Yolculuk sıfırlandı.")
        if name == "oil_change":
            grade = p.get("grade", self.oil.grade)
            if grade not in oil_mod.GRADES:
                return False, M("Bilinmeyen yağ tipi.")
            with_filter = bool(p.get("filter", True))
            cost = (self.oil.change(grade, with_filter, prices.v("OIL_FILTER", self.veh))
                    + prices.v("OIL_CHANGE_LABOUR", self.veh))
            msg = "Yağ değişti: {grade_t}, {l:.0f} L + yağ filtresi" if with_filter else "Yağ değişti: {grade_t}, {l:.0f} L"
            self.event(f, "info", M(msg, grade_t=oil_mod.GRADES[grade]["name"], l=self.oil.capacity_l), cost, "servis")
            return True, M("Yağ değiştirildi.")
        if name == "oil_topup":
            grade = p.get("grade", self.oil.grade)
            if grade not in oil_mod.GRADES:
                return False, M("Bilinmeyen yağ tipi.")
            liters = clamp(float(p.get("liters", 1.0)), 0.0, 20.0)
            cost = self.oil.top_up(grade, liters)
            tmpl = "{l:.1f} L {grade_t} eklendi (seviye %{lvl:.0f})."
            if self.oil.level_frac > 1.05:
                tmpl = "{l:.1f} L {grade_t} eklendi (seviye %{lvl:.0f}). Dikkat: yağ fazla! Köpüklenme ve yağ yakma riski."
            msg = M(tmpl, l=liters, grade_t=oil_mod.GRADES[grade]["name"], lvl=self.oil.level_frac * 100)
            self.event(f, "info", msg, cost, "servis")
            return True, msg
        if name == "oil_filter":
            self.oil.change_filter()
            cost = prices.v("OIL_FILTER", self.veh) + prices.v("FILTER_LABOUR", self.veh)
            self.event(f, "info", M("Yağ filtresi değişti."), cost, "servis")
            return True, M("Filtre değişti.")
        if name == "oil_sample":
            self.reports["oil"] = self.oil.lab_report(f.odometer_km, f.game_minutes)
            self.event(f, "info", M("Yağ numunesi alındı, laboratuvar raporu hazır."), prices.v("OIL_SAMPLE", self.veh), "servis")
            return True, M("Yağ analizi raporu hazır.")
        if name == "coolant_change":
            ctype = p.get("type", "oat")
            if ctype not in coolant_mod.TYPES:
                return False, M("Bilinmeyen sıvı.")
            conc = clamp(float(p.get("concentration", 0.5)), 0.3, 0.7)
            cost = self.coolant.change(ctype, conc, prices.v("COOLANT_CHANGE_LABOUR", self.veh))
            self.thermal.block_ice = self.thermal.rad_ice = 0.0
            self.event(f, "info", M("Soğutma sıvısı değişti: {type_t}, %{c:.0f} antifriz (donma {f:.0f} °C)",
                                    type_t=coolant_mod.TYPES[ctype]["name"], c=conc * 100, f=self.coolant.freeze_point),
                       cost, "servis")
            return True, M("Soğutma sıvısı değişti.")
        if name == "coolant_topup":
            fluid = p.get("fluid", "premix")
            if fluid not in coolant_mod.FLUIDS:
                return False, M("Bilinmeyen sıvı.")
            if self.thermal.t_cool > 60:
                return False, M("Motor sıcakken radyatör kapağını açmayın! (sıvı > 60 °C, basınç altında)")
            added, cost = self.coolant.top_up(fluid, float(p.get("liters", 5.0)))
            msg = M("{l:.1f} L {fluid_t} eklendi. Antifriz %{g:.0f}, donma noktası {f:.0f} °C.", l=added,
                    fluid_t=coolant_mod.FLUIDS[fluid]["name"], g=self.coolant.glycol * 100, f=self.coolant.freeze_point)
            self.event(f, "info", msg, cost, "servis")
            return True, msg
        if name == "coolant_test":
            r = self.coolant.test()
            r["gm"] = f.game_minutes
            self.reports["coolant"] = r
            self.event(f, "info", M("Antifriz ölçümü: %{g:.0f}, donma {f:.0f} °C, pH {ph:.1f}.", g=r["glycol_pct"],
                                    f=r["freeze_point"], ph=r["ph"]), prices.v("COOLANT_TEST", self.veh), "servis")
            return True, M("Refraktometre ölçümü yapıldı.")
        if name == "battery_replace":
            ah = clamp(float(p.get("ah", self.spec.battery_ah)), *((40.0, 120.0) if self.veh == "car" else (100.0, 300.0)))
            kind = p.get("kind", self.battery.kind)
            if kind not in battery_mod.KINDS:
                return False, M("Bilinmeyen akü tipi.")
            cost = self.battery.replace(ah, kind)
            self.spec.battery_ah = ah
            if "battery_frozen" in self.faults.active:
                self.faults.active.remove("battery_frozen")
            tmpl = ("Aküler değişti (2 x 12 V {ah:.0f} Ah, {kind_t})." if self.battery.blocks == 2
                    else "Akü değişti (12 V {ah:.0f} Ah, {kind_t}).")
            self.event(f, "info", M(tmpl, ah=ah, kind_t=battery_mod.KINDS[kind]["name"]), cost, "servis")
            return True, M("Aküler değişti." if self.battery.blocks == 2 else "Akü değişti.")
        if name == "battery_charger":
            on = bool(p.get("on", True))
            if on and not (stationary and engine_off):
                return False, M("Şarj cihazı için motor kapalı ve kamyon duruyor olmalı.")
            self.battery.charger = on
            self.event(f, "info", M("Akü şarj cihazı bağlandı ({a:.0f} A).", a=self.battery.charger_a) if on
                       else M("Akü şarj cihazı söküldü."), prices.v("CHARGER", self.veh) if on else 0.0, "servis")
            return True, M("Tamam.")
        if name == "jump_start":
            if not engine_off:
                return False, M("Motor zaten çalışıyor.")
            self.battery.jump = True
            self.event(f, "info", M("Takviye kablosu bağlandı: bir sonraki marş dış aküden yapılacak."), prices.v("JUMP_START", self.veh), "servis")
            return True, M("Takviye bağlandı — şimdi oyunda motoru çalıştırın.")
        if name == "battery_test":
            r = self.battery.test(self.oil.viscosity(self.thermal.t_oil))
            r["gm"] = f.game_minutes
            self.reports["battery"] = r
            self.event(f, "info", M("Akü testi: şarj %{soc:.0f}, sağlık %{soh:.0f}, CCA {cca:.0f} A.", soc=r["soc_pct"],
                                    soh=r["soh_pct"], cca=r["cca"]), 0.0, "servis")
            return True, M("Akü testi yapıldı.")
        if name == "dpf_regen":
            self.dpf.service_regen()
            cost = prices.v("DPF_REGEN", self.veh)
            self.event(f, "info", M("Serviste zorunlu DPF rejenerasyonu yapıldı."), cost, "servis")
            return True, M("DPF rejenerasyonu tamam.")
        if name == "dpf_clean":
            self.dpf.clean()
            cost = prices.v("DPF_CLEAN", self.veh)
            self.event(f, "info", M("DPF söküldü, kül temizliği yapıldı."), cost, "servis")
            return True, M("DPF temizlendi.")
        if name == "gearbox_oil":
            self.trans.change_oil()
            cost = prices.v("GEARBOX_OIL", self.veh)
            self.event(f, "info", M("Şanzıman yağı ve filtresi değişti ({l:.0f} L).", l=trans_mod.OIL_L[self.veh]),
                       cost, "servis")
            return True, M("Şanzıman yağı değiştirildi.")
        if name == "clutch_replace":
            self.trans.replace_clutch()
            cost = prices.v("CLUTCH", self.veh)
            self.event(f, "info", M("Debriyaj yenilendi (balata, baskı plakası, debriyaj rulmanı)."), cost, "servis")
            return True, M("Debriyaj yenilendi.")
        if name == "part_replace":   # Arıza tespiti: yıpranmış (ya da arızalı) parçayı önceden yenile
            part = FAULT_PARTS.get(p.get("part"))
            if part is None or any(k in self.fault_skip() for k in part[1]):
                return False, M("Bilinmeyen parça.")
            cost = prices.fault(part[1][0], self.veh)
            self.faults.replace(part[1])
            self.event(f, "info", M("Parça değiştirildi: {part_t}.", part_t=part[0]), cost, "servis")
            return True, M("Parça değiştirildi: {part_t}.", part_t=part[0])
        if name == "repair":
            k = p.get("fault")
            if k not in self.faults.active:
                return False, M("Bu arıza aktif değil.")
            if k == "battery_frozen":
                return False, M("Donmuş akü onarılamaz: aküleri değiştirin.")
            self.repair_fault(f, k)
            return True, M("Onarım tamamlandı.")
        if name == "overhaul":
            self.health = EngineHealth()
            self.oil.change(self.oil.grade, True)
            for k in ("engine_seized", "head_gasket"):
                if k in self.faults.active:
                    self.faults.active.remove(k)
            self.event(f, "info", M("Motor revizyonu yapıldı (gömlek, piston, segman, yataklar)."), prices.v("OVERHAUL", self.veh), "servis")
            return True, M("Revizyon tamamlandı.")
        return False, M("Bilinmeyen işlem.")
