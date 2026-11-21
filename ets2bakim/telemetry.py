"""Telemetri kaynakları: oyun (RenCloud scs-sdk-plugin paylaşılan belleği) ve demo kamyon."""
import math
import random
import time
from dataclasses import dataclass, field

from . import geo
from .engine import ETA_IND, LHV_KJ_PER_L, EngineSpec
from .i18n import M


@dataclass
class Frame:
    ok: bool = False
    paused: bool = True
    game_minutes: int = 0
    scale: float = 19.0
    truck_key: str = ""
    brand: str = ""
    name: str = ""
    plate: str = ""
    engine_on: bool = False
    electric_on: bool = False
    rpm: float = 0.0
    rpm_max: float = 2500.0
    speed_kmh: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0
    cruise: bool = False
    gear: int = 0
    fuel_l: float = 0.0
    fuel_cap: float = 0.0
    odometer_km: float = 0.0
    retarder_level: int = 0
    retarder_steps: int = 0
    motor_brake: bool = False
    park_brake: bool = False
    wipers: bool = False
    wiper_stage: int = -1           # 0 kapalı, 1 aralıklı, 2 yavaş, 3 hızlı; -1 bilinmiyor (SDK vermez, tuşlardan izlenir)
    lights: dict = field(default_factory=lambda: dict(parking=False, low=False, high=False, aux_front=0,
                                                       aux_roof=0, beacon=False, brake=False, reverse=False,
                                                       hazard=False, blink_l=False, blink_r=False, dash=0.0))
    wear: dict = field(default_factory=lambda: dict(engine=0.0, transmission=0.0, cabin=0.0, chassis=0.0, wheels=0.0))
    game_oil_pressure: float = 0.0
    game_oil_temp: float = 0.0
    game_water_temp: float = 0.0
    game_battery_v: float = 0.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    cargo_kg: float = 0.0
    refuel: bool = False
    mp_offset: int = 0              # Konvoy (resmi çok oyunculu) oturumunda sıfırdan farklı
    brand_id: str = ""
    truck_id: str = ""
    clutch: float = 0.0
    gears_forward: int = 0
    gear_ratios: list = field(default_factory=list)
    gear_ratios_rev: list = field(default_factory=list)
    shifter_type: str = ""          # arcade | automatic | manual | hshifter
    diff_ratio: float = 0.0
    wheel_radius: float = 0.0
    pitch: float = 0.0              # tam tur cinsinden (SCS: 0.25 = 90°)
    trailer_attached: bool = False
    brake_temp: float = 0.0         # °C
    air_bar: float = 0.0
    air_warning: bool = False
    air_emergency: bool = False
    on_job: bool = False
    city_src: str = ""
    city_dst: str = ""
    cargo: str = ""
    nav_km: float = 0.0             # rota danışmanının kalan mesafesi
    nav_min: float = 0.0            # rota danışmanının tahmini süresi (dakika)
    speed_limit: float = 0.0        # rota danışmanının hız sınırı (km/h, 0 = yok)
    job_market: str = ""            # quick_job = oyunun verdiği geçici tır
    ev_delivered: bool = False      # olay bayrakları (eklenti her olayda değerini çevirir)
    ev_finished: bool = False
    ev_cancelled: bool = False
    game: int = 1                   # 1 ETS2, 2 ATS (para biriminin tabanı: EUR / USD)
    fuel_warning: bool = False      # oyunun düşük yakıt uyarısı
    fuel_warn_factor: float = 0.15  # uyarının yandığı doluluk oranı
    fuel_range_km: float = 0.0      # oyunun menzil tahmini
    adblue_l: float = 0.0           # ETS2 AdBlue'yu harcamaz (sabit); tüketim simülatörde hesaplanır
    adblue_cap: float = 0.0
    wheels: list = field(default_factory=list)  # kamyon tekerlekleri: steer, powered, liftable, lift, ground, steering, substance

    @property
    def mass_kg(self):
        """Tahmini toplam kütle: çekici ~8 t, dorse ~7 t + yük."""
        return 8000.0 + ((7000.0 + self.cargo_kg) if self.trailer_attached else 0.0)

    @staticmethod
    def from_raw(d):
        f = Frame()
        f.ok = bool(d.get("sdkActive"))
        f.paused = bool(d.get("paused"))
        f.game_minutes = int(d.get("time_abs", 0))
        f.scale = float(d.get("scale", 19.0)) or 19.0
        f.brand = d.get("truckBrand", "") or ""
        f.name = d.get("truckName", "") or ""
        f.plate = d.get("truckLicensePlate", "") or ""
        tid = d.get("truckId", "") or (f.brand + f.name)
        f.truck_key = f"{tid}|{f.plate}" if tid else ""
        f.engine_on = bool(d.get("engineEnabled"))
        f.electric_on = bool(d.get("electricEnabled"))
        rpm_max = float(d.get("engineRpmMax", 2500.0))
        f.rpm_max = rpm_max if math.isfinite(rpm_max) and rpm_max > 0 else 2500.0
        rpm = float(d.get("engineRpm", 0.0))
        # oyun nadiren tek karede saçma devir gönderiyor (ör. 9000+): devre bağlı hesaplar (yağ basıncı uyarısı, aşırı
        # devir hasarı) yanlış alarm vermesin diye en yüksek devrin %30 fazlasıyla sınırlanır
        f.rpm = min(max(rpm, 0.0), f.rpm_max * 1.3) if math.isfinite(rpm) else 0.0
        f.speed_kmh = float(d.get("speed", 0.0)) * 3.6
        f.throttle = float(d.get("gameThrottle", 0.0))
        f.brake = float(d.get("gameBrake", 0.0))
        f.cruise = bool(d.get("cruiseControl"))
        f.gear = int(d.get("gear", 0))
        f.fuel_l = float(d.get("fuel", 0.0))
        f.fuel_cap = float(d.get("fuelCapacity", 0.0))
        f.odometer_km = float(d.get("truckOdometer", 0.0))
        f.retarder_level = int(d.get("retarderBrake", 0))
        f.retarder_steps = int(d.get("retarderStepCount", 0))
        f.motor_brake = bool(d.get("motorBrake"))
        f.park_brake = bool(d.get("parkBrake"))
        f.wipers = bool(d.get("wipers"))
        f.lights = dict(
            parking=bool(d.get("lightsParking")), low=bool(d.get("lightsBeamLow")),
            high=bool(d.get("lightsBeamHigh")), aux_front=int(d.get("lightsAuxFront", 0)),
            aux_roof=int(d.get("lightsAuxRoof", 0)), beacon=bool(d.get("lightsBeacon")),
            brake=bool(d.get("lightsBrake")), reverse=bool(d.get("lightsReverse")),
            hazard=bool(d.get("lightsHazards")), blink_l=bool(d.get("blinkerLeftOn")),
            blink_r=bool(d.get("blinkerRightOn")), dash=float(d.get("lightsDashboard", 0.0)),
        )
        f.wear = dict(engine=float(d.get("wearEngine", 0.0)), transmission=float(d.get("wearTransmission", 0.0)),
                      cabin=float(d.get("wearCabin", 0.0)), chassis=float(d.get("wearChassis", 0.0)),
                      wheels=float(d.get("wearWheels", 0.0)))
        f.game_oil_pressure = float(d.get("oilPressure", 0.0))
        f.game_oil_temp = float(d.get("oilTemperature", 0.0))
        f.game_water_temp = float(d.get("waterTemperature", 0.0))
        f.game_battery_v = float(d.get("batteryVoltage", 0.0))
        f.x = float(d.get("coordinateX", 0.0))
        f.y = float(d.get("coordinateY", 0.0))
        f.z = float(d.get("coordinateZ", 0.0))
        f.cargo_kg = float(d.get("cargoMass", 0.0))
        f.refuel = bool(d.get("refuel"))
        f.mp_offset = int(d.get("multiplayerTimeOffset", 0) or 0)
        f.brand_id = d.get("truckBrandId", "") or ""
        f.truck_id = d.get("truckId", "") or ""
        f.clutch = float(d.get("gameClutch", 0.0))
        f.gears_forward = int(d.get("gears", 0))
        f.gear_ratios = [float(x) for x in (d.get("gearRatiosForward") or [])[: max(0, f.gears_forward)]]
        f.gear_ratios_rev = [float(x) for x in (d.get("gearRatiosReverse") or [])[: max(0, int(d.get("gears_reverse", 0) or 0))]]
        f.shifter_type = str(d.get("shifterType", "") or "").strip("\x00 ")
        f.diff_ratio = float(d.get("gearDifferential", 0.0))
        radii = d.get("truckWheelRadius") or []
        powered = d.get("truckWheelPowered") or []
        driven = [float(r) for r, p in zip(radii, powered) if p and r > 0]
        f.wheel_radius = max(driven) if driven else 0.0
        f.pitch = float(d.get("rotationY", 0.0))
        trailers = d.get("trailer") or []
        f.trailer_attached = bool(trailers and isinstance(trailers[0], dict) and trailers[0].get("attached"))
        f.brake_temp = float(d.get("brakeTemperature", 0.0))
        f.air_bar = float(d.get("airPressure", 0.0)) * 0.0689476
        f.air_warning = d.get("airPressureWarning") is True
        f.air_emergency = d.get("airPressureEmergency") is True
        f.on_job = bool(d.get("onJob"))
        f.city_src = d.get("citySrc", "") or ""
        f.city_dst = d.get("cityDst", "") or ""
        f.cargo = d.get("cargo", "") or ""
        f.nav_km = max(0.0, float(d.get("routeDistance", 0.0) or 0.0)) / 1000.0
        f.nav_min = max(0.0, float(d.get("routeTime", 0.0) or 0.0)) / 60.0
        f.speed_limit = max(0.0, float(d.get("speedLimit", 0.0) or 0.0)) * 3.6
        f.job_market = d.get("jobMarket", "") or ""
        f.ev_delivered = bool(d.get("jobDelivered"))
        f.ev_finished = bool(d.get("jobFinished"))
        f.ev_cancelled = bool(d.get("jobCancelled"))
        f.game = int(d.get("game", 1) or 1)
        f.fuel_warning = bool(d.get("fuelWarning"))
        f.fuel_warn_factor = float(d.get("fuelWarningFactor", 0.15) or 0.15)
        f.fuel_range_km = float(d.get("fuelRange", 0.0) or 0.0)
        f.adblue_l = float(d.get("adblue", 0.0) or 0.0)
        f.adblue_cap = float(d.get("adblueCapacity", 0.0) or 0.0)
        f.wheels = _wheels(d)
        return f


def _wheels(d):
    """Kamyonun tekerlek düzeni (yalnızca çekici; dorse tekerlekleri ayrı alanlardadır)."""
    n = min(int(d.get("truckWheelCount", 0) or 0), 16)
    subs = d.get("substances") or []

    def arr(key, default):
        a = d.get(key) or []
        return [a[i] if i < len(a) else default for i in range(n)]

    steer, powered, liftable = arr("truckWheelSteerable", False), arr("truckWheelPowered", False), arr("truckWheelLiftable", False)
    ground, lift, steering = arr("truckWheelOnGround", True), arr("truck_wheelLift", 0.0), arr("truck_wheelSteering", 0.0)
    sub = arr("truck_wheelSubstance", -1)
    out = []
    for i in range(n):
        si = int(sub[i]) if sub[i] is not None else -1
        out.append(dict(steer=bool(steer[i]), powered=bool(powered[i]), liftable=bool(liftable[i]),
                        lift=float(lift[i] or 0.0), ground=bool(ground[i]), steering=float(steering[i] or 0.0),
                        substance=str(subs[si]).strip("\x00 ") if 0 <= si < len(subs) else ""))
    return out


class _KeySpy(dict):
    """Frame.from_raw'ın hangi alanları okuduğunu kaydeder (hızlı okuyucu yalnızca bunları çözer)."""

    def __init__(self, d):
        super().__init__(d)
        self.used = set()

    def get(self, key, default=None):
        self.used.add(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self.used.add(key)
        return super().__getitem__(key)

    def __contains__(self, key):
        self.used.add(key)
        return super().__contains__(key)


def _layout(struct):
    """truck_telemetry DictStruct'ının alanları: ad -> (tür, ofset). Paketin kendi tanımlarından (sıra ve boyutlar)."""
    out, off = {}, 0
    for name, ft in struct._DictStruct__fields:
        if name:
            out[name] = (ft, off)
        off += ft.size
    return out


class FastParse:
    """Telemetri okuyucusu. truck_telemetry her okumada bütün yapıyı (10 dorse dahil ~3.700 değer) çözer; okuma başına
    ~0,8 ms ve binlerce nesne. Burada yalnızca Frame.from_raw'ın kullandığı alanlar (~120 değer; dorseden yalnızca ilkinin
    bağlı olup olmadığı) paketin kendi yerleşimiyle okunur. İlk okumada ve VERIFY_EVERY okumada bir aynı anlık görüntü
    hem tam hem hızlı çözülüp sonuç (Frame) karşılaştırılır: uyuşmazsa (paket ya da eklenti yerleşimi değişti) kalıcı
    olarak paketin tam çözümüne dönülür."""

    VERIFY_EVERY = 600

    def __init__(self, version):
        self.version = version
        self.root = _layout(version.struct_telemetry)
        self.trailer = None
        if "trailer" in self.root:
            ft, off = self.root["trailer"]
            lay = _layout(ft._ArraySruct__struct)
            if "attached" in lay:
                aft, aoff = lay["attached"]
                self.trailer = (aft, off + aoff)
        self.items = None
        self.count = 0
        self.ok = True

    def parse(self, buf):
        if not self.ok:
            return self.version.parse_data(buf)
        self.count += 1
        if self.items is None or self.count % self.VERIFY_EVERY == 0:
            return self._verify(buf)
        return self._fast(buf)

    def _fast(self, buf):
        d = {k: ft.unpack_from(buf, off) for k, ft, off in self.items}
        if self.trailer:
            ft, off = self.trailer
            d["trailer"] = [{"attached": ft.unpack_from(buf, off)}]
        return d

    def _verify(self, buf):
        snap = bytes(buf)                                 # iki çözüm aynı anın verisini görsün
        full = self.version.parse_data(snap)
        spy = _KeySpy(full)
        ref = Frame.from_raw(spy)
        keys = set(spy.used) | {k for k, _, _ in (self.items or ())}
        self.items = [(k, *self.root[k]) for k in sorted(keys) if k in self.root and k != "trailer"]
        try:
            same = repr(Frame.from_raw(self._fast(snap))) == repr(ref)   # repr: NaN değerler de eşit sayılır
        except Exception:
            same = False
        if not same:
            self.ok = False
        return full


def _fast_parser(tt):
    """truck_telemetry.init() sonrası hızlı okuyucu ve paylaşılan bellek; paketin iç yapısı beklenenden farklıysa None."""
    try:
        import importlib
        mod = importlib.import_module(tt.__name__ + ".truck_telemetry")
        if mod._telemetry_sdk_version is None or mod._mem is None:
            return None
        return FastParse(mod._telemetry_sdk_version), (lambda: mod._mem.buf)
    except Exception:
        return None


class GameSource:
    """ETS2/ATS paylaşılan belleğini okur (truck_telemetry paketi)."""

    def __init__(self):
        self.status = "Bağlanıyor…"
        self._ready = False
        self._next_try = 0.0
        self._tt = None
        self._fast = None
        self._pip = None

    def _install_package(self):
        """truck-telemetry eksikse arka planda bir kez kurar (uygulama kısayolla açıldığında da çalışsın diye)."""
        if self._pip is None:
            import subprocess
            import sys
            try:
                self._pip = subprocess.Popen(
                    [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", "truck-telemetry==0.0.3"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except OSError:
                self._pip = False
        if self._pip and self._pip.poll() is None:
            return "Eksik truck-telemetry paketi kuruluyor…"
        if self._pip and self._pip.returncode == 0:
            import importlib
            importlib.invalidate_caches()
            return "Eksik truck-telemetry paketi kuruluyor…"
        return "truck-telemetry paketi kurulamadı (internet bağlantısını kontrol edin)"

    def read(self):
        if not self._ready:
            if time.monotonic() < self._next_try:
                return None
            self._next_try = time.monotonic() + 2.0
            try:
                import truck_telemetry
                self._tt = truck_telemetry
                truck_telemetry.init()
                self._fast = _fast_parser(truck_telemetry)
                self._ready = True
                self.status = "Oyuna bağlı"
            except ImportError:
                self.status = self._install_package()
                return None
            except FileNotFoundError:
                self.status = "Oyun çalışmıyor ya da telemetri eklentisi (scs-telemetry.dll) kurulu değil"
                return None
            except Exception as e:  # sürüm uyumsuzluğu vb.
                self.status = M("Telemetri eklentisi uyumsuz: {err} (V.1.12.x gerekli)", err=str(e))
                return None
        try:
            raw = self._fast[0].parse(self._fast[1]()) if self._fast else self._tt.get_data()
        except Exception as e:
            self._ready = False
            self.status = M("Telemetri okunamadı: {err}", err=str(e))
            try:
                self._tt.deinit()
            except Exception:
                pass
            return None
        f = Frame.from_raw(raw)
        self.status = "Oyuna bağlı" if f.ok else "Oyun menüde / telemetri beklemede"
        return f


class DemoSource:
    """Oyun olmadan arayüzü ve modelleri denemek için sanal kamyon (Berlin → Münih → Berlin)."""

    ROUTE = [(52.52, 13.40), (51.34, 12.37), (50.32, 11.91), (49.45, 11.08), (48.14, 11.58)]
    PHASES = [
        # (ad, oyun dakikası)
        ("park_soguk", 40), ("kontak", 2), ("rolanti", 4), ("sehir", 18), ("otoyol", 150),
        ("yokus", 18), ("inis", 14), ("otoyol", 120), ("mola", 45), ("uyku", 0),
    ]

    # Volvo I-Shift 12 vites, 33 t'luk tır; demonun "gerçek" motoru D13K 540 (algılamayı denemek için)
    GEARS = [14.94, 11.73, 9.04, 7.09, 5.54, 4.35, 3.44, 2.70, 2.08, 1.63, 1.27, 1.00]
    DIFF, WHEEL_R, MASS, CARGO, GRADE = 2.64, 0.52, 33000.0, 18000.0, 0.05

    def __init__(self, speedup=1.0):
        self.status = "DEMO modu (sanal kamyon)"
        self.true_engine = EngineSpec(power_kw=540 * 0.7355, torque_nm=2600.0)
        self.gear = 0
        self.gear_t = 0.0
        self.speedup = speedup
        self.rng = random.Random(7)
        self.spec = EngineSpec()
        self.game_s = 6 * 3600.0 + 1440 * 60 * 2
        self.phase_i = 0
        self.phase_t = 0.0
        self.odo = 412_350.0
        self.fuel = 640.0
        self.dist_on_route = 0.0
        self.direction = 1
        self.speed = 0.0
        self.rpm = 0.0
        self.last = time.monotonic()
        self.f = Frame(ok=True, paused=False, truck_key="vehicle.volvo.fh16_2012|34 ETS 2026", brand="Volvo",
                       name="FH16 2012 (Demo)", plate="34 ETS 2026", fuel_cap=1100.0, retarder_steps=5,
                       rpm_max=2300.0, brand_id="volvo", truck_id="vehicle.volvo.fh16_2012",
                       gears_forward=12, gear_ratios=list(self.GEARS), diff_ratio=self.DIFF,
                       wheel_radius=self.WHEEL_R, trailer_attached=True, cargo_kg=self.CARGO,
                       adblue_cap=64.0, adblue_l=64.0, wheels=self._wheels_6x2())

    @staticmethod
    def _wheels_6x2():
        """Demo çekici: ön dingil, çekiş dingili ve kaldırılabilir taşıyıcı dingil (yüklüyken yerde)."""
        w = lambda **k: dict(dict(steer=False, powered=False, liftable=False, lift=0.0, ground=True, steering=0.0,
                                  substance="road"), **k)
        return [w(steer=True), w(steer=True), w(powered=True), w(powered=True), w(liftable=True), w(liftable=True)]

    def _climb(self, dt, thr):
        """%5 yokuşta tam gaz: tork, vites oranları, eğim, yuvarlanma ve hava direnciyle gerçek dinamik."""
        v = max(1.0, self.speed / 3.6)
        to_rpm = lambda g: v / self.WHEEL_R * self.GEARS[g - 1] * self.DIFF * 60 / (2 * math.pi)
        if self.gear == 0:
            self.gear = max([g for g in range(1, 13) if to_rpm(g) >= 1100] or [1])
            self.gear_t = 0.0
        if to_rpm(self.gear) < 1050 and self.gear > 1 and self.gear_t > 1.5:
            self.gear -= 1
            self.gear_t = 0.0
        elif to_rpm(self.gear) > 1500 and self.gear < 12 and self.gear_t > 1.5:
            self.gear += 1
            self.gear_t = 0.0
        rpm = to_rpm(self.gear)
        ratio = self.GEARS[self.gear - 1] * self.DIFF
        drive = self.true_engine.max_torque_nm(rpm) * thr * ratio * 0.93 / self.WHEEL_R
        th = math.atan(self.GRADE)
        m, g = self.MASS, 9.81
        resist = m * g * math.sin(th) + 0.0065 * m * g * math.cos(th) + 0.5 * 1.2 * 6.0 * v * v
        v = max(1.0, v + (drive - resist) / m * dt)
        self.speed = v * 3.6
        self.rpm = rpm
        self.f.pitch = th / (2 * math.pi)

    def _route_pos(self):
        pts = [geo.latlon_to_game(a, b) for a, b in self.ROUTE]
        seg = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)]
        total = sum(seg)
        d = (self.dist_on_route % (2 * total))
        if d > total:
            d = 2 * total - d
        for i, s in enumerate(seg):
            if d <= s:
                t = d / s
                return pts[i][0] + t * (pts[i + 1][0] - pts[i][0]), pts[i][1] + t * (pts[i + 1][1] - pts[i][1])
            d -= s
        return pts[-1]

    def read(self):
        now = time.monotonic()
        dt_real = min(0.5, now - self.last)     # araç fiziği gerçek zamanda
        self.last = now
        f = self.f
        scale = 19.0
        dt_g = dt_real * scale * self.speedup   # oyun saati hızlandırılabilir
        name, dur = self.PHASES[self.phase_i]
        self.phase_t += dt_g / 60.0
        if name == "uyku":
            self.game_s += 9 * 3600.0
            self.phase_i = 0
            self.phase_t = 0.0
            name, dur = self.PHASES[0]
        elif self.phase_t >= dur:
            self.phase_i = (self.phase_i + 1) % len(self.PHASES)
            self.phase_t = 0.0
            name, dur = self.PHASES[self.phase_i]
        self.game_s += dt_g
        n = lambda s: self.rng.gauss(0, s)

        L = dict(f.lights)
        hour = (self.game_s / 3600.0) % 24
        dark = hour < 7 or hour > 19
        L.update(parking=False, low=False, high=False, brake=False, aux_front=0, aux_roof=0, beacon=False)
        f.engine_on = name not in ("park_soguk", "kontak", "mola")
        f.electric_on = name != "park_soguk"
        f.park_brake = name in ("park_soguk", "kontak", "rolanti", "mola")
        target_v, thr, rpm_t, ret = 0.0, 0.0, 600.0, 0
        f.cruise = False
        f.motor_brake = False
        if name == "rolanti":
            thr, rpm_t = 0.0, 600 + n(5)
        elif name == "sehir":
            cyc = math.sin(self.phase_t / 1.5)
            target_v = max(0.0, 35 + 20 * cyc)
            thr = max(0.0, min(1.0, 0.45 + 0.4 * cyc + n(0.08)))
            rpm_t = 1000 + 500 * (0.5 + 0.5 * cyc)
            L["brake"] = cyc < -0.6
        elif name == "otoyol":
            target_v, thr, rpm_t = 85.0, max(0.0, min(1.0, 0.48 + n(0.06))), 1250 + n(15)
            f.cruise = True
        elif name == "yokus":
            target_v, thr, rpm_t = 52.0, 1.0, 1650 + n(20)
        elif name == "inis":
            target_v, thr, rpm_t, ret = 78.0, 0.0, 1500 + n(20), 3
            f.motor_brake = True
        elif name == "mola":
            L["parking"] = True
        if f.engine_on and dark:
            L["low"] = True
            L["parking"] = True
        f.lights = L
        f.retarder_level = ret
        self.gear_t += dt_real
        if name == "yokus":
            self._climb(dt_real, thr)
        else:
            self.gear = 0
            f.pitch = 0.0
            self.speed += (target_v - self.speed) * min(1.0, dt_real / 6.0)
            if not f.engine_on:
                self.speed = 0.0
            self.rpm = (self.rpm + (rpm_t - self.rpm) * min(1.0, dt_real / 1.0)) if f.engine_on else 0.0
        f.gear = self.gear
        f.throttle = thr if f.engine_on else 0.0
        f.rpm = self.rpm
        f.speed_kmh = self.speed

        if f.engine_on:
            p = thr * self.true_engine.max_power_kw(self.rpm)
            overrun = thr < 0.02 and self.rpm > 750 and self.speed > 3
            fuel_power = 0.0 if overrun else (p + self.spec.friction_kw(self.rpm) + 4.0) / ETA_IND
            self.fuel -= fuel_power / LHV_KJ_PER_L * dt_g
            if self.fuel < 80:
                self.fuel = 1050.0
        km = self.speed * dt_g / 3600.0
        self.odo += km
        self.dist_on_route += km * 1000.0 / 19.0
        f.x, f.z = self._route_pos()
        f.y = 120.0
        f.fuel_l = self.fuel
        f.odometer_km = self.odo
        f.game_minutes = int(self.game_s // 60)
        f.scale = scale * self.speedup
        f.wear = dict(engine=0.031, transmission=0.022, cabin=0.04, chassis=0.035, wheels=0.05)
        return f
