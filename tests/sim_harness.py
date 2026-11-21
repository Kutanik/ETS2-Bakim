"""Modelleri oyun olmadan sabit koşullarda koşturan yardımcı düzenek."""
import random
from ets2bakim.telemetry import Frame
from ets2bakim.truck import TruckModel


class Harness:
    def __init__(self, ambient=15.0, grade="10w40", odo=0.0):
        self.f = Frame(ok=True, paused=False, truck_key="test", odometer_km=odo, fuel_l=1000, rpm_max=2300,
                       retarder_steps=5)
        self.t = TruckModel("test", {})
        self.t.oil.grade = grade
        self.t.first_time_setup(self.f, ambient)
        if grade != "10w40":
            self.t.oil.change(grade)
            self.t.oil.change(grade)
        self.amb = ambient
        self.settings = dict(random_faults=False, hotel_load=True)
        self.rng = random.Random(1)

    def run(self, minutes, engine=True, electric=True, rpm=1250, throttle=0.45, speed=85, dt=2.0, **lights):
        f = self.f
        f.engine_on, f.electric_on = engine, electric
        f.rpm = rpm if engine else 0
        f.throttle = throttle if engine else 0
        f.speed_kmh = speed if engine else 0
        f.lights.update(lights)
        steps = int(minutes * 60 / dt)
        for _ in range(steps):
            km = f.speed_kmh * dt / 3600.0
            f.odometer_km += km
            f.game_minutes += 0  # tam dakika takibi gerekmiyor
            self.t.step(f, dt / 19.0, dt, dict(ambient=self.amb, settings=self.settings, rng=self.rng,
                                               km=km, dfuel=0.0, decel=0.0))
        return self.t

    def parked(self, hours, electric=False, **lights):
        f = self.f
        f.engine_on, f.electric_on, f.speed_kmh, f.rpm = False, electric, 0, 0
        f.lights.update(lights)
        for _ in range(int(hours * 12)):
            self.t.parked_step(f, 300.0, self.amb, self.settings)
        return self.t
