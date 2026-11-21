"""ETS2 oyun koordinatlarını gerçek enlem/boylama çevirir.

ETS2 Avrupa haritası Lambert konformal konik projeksiyon kullanır (lat_1=37, lat_2=65,
lat_0=50, lon_0=15). Sabitler truckermudgeon/maps projesindeki tersine mühendislikten alınmıştır;
İngiltere bölgesi oyunda farklı ölçeklendiği için ayrıca düzeltilir.
"""
import math

R = 6370997.0
_LAT1, _LAT2, _LAT0, _LON0 = (math.radians(v) for v in (37.0, 65.0, 50.0, 15.0))
MAP_FACTOR = (-0.000171570875, 0.0001729241463)
MAP_OFFSET = (16660.0, 4150.0)
LEN_DEG = R * math.pi / 180.0
_UK_SCALE = 0.75
_CALAIS = (-31100.0, -5500.0)


def _t(phi):
    return math.tan(math.pi / 4 + phi / 2)


_N = math.log(math.cos(_LAT1) / math.cos(_LAT2)) / math.log(_t(_LAT2) / _t(_LAT1))
_F = math.cos(_LAT1) * _t(_LAT1) ** _N / _N
_RHO0 = R * _F / _t(_LAT0) ** _N


def _lcc_inverse(x, y):
    dy = _RHO0 - y
    rho = math.copysign(math.hypot(x, dy), _N)
    theta = math.atan2(x, dy)
    lat = 2 * math.atan((R * _F / rho) ** (1 / _N)) - math.pi / 2
    lon = _LON0 + theta / _N
    return math.degrees(lat), math.degrees(lon)


def _lcc_forward(lat, lon):
    rho = R * _F / _t(math.radians(lat)) ** _N
    theta = _N * (math.radians(lon) - _LON0)
    return rho * math.sin(theta), _RHO0 - rho * math.cos(theta)


def game_to_latlon(gx, gz):
    sx, sy = math.floor(gx / 4000), math.floor(gz / 4000)
    x, y = gx - MAP_OFFSET[0], gz - MAP_OFFSET[1]
    if sx <= -8 and sy <= -2 and not (sx == -8 and sy == -2):
        x = (x + _CALAIS[0] / 2) * _UK_SCALE
        y = (y + _CALAIS[1] / 2) * _UK_SCALE
    return _lcc_inverse(x * MAP_FACTOR[1] * LEN_DEG, y * MAP_FACTOR[0] * LEN_DEG)


def latlon_to_game(lat, lon):
    """Demo modu için ters dönüşüm (İngiltere düzeltmesi uygulanmaz)."""
    e, n = _lcc_forward(lat, lon)
    return e / (MAP_FACTOR[1] * LEN_DEG) + MAP_OFFSET[0], n / (MAP_FACTOR[0] * LEN_DEG) + MAP_OFFSET[1]


CITIES = [
    ("İstanbul", 41.01, 28.98), ("Edirne", 41.68, 26.56), ("Tekirdağ", 40.98, 27.51),
    ("Sofya", 42.70, 23.32), ("Plovdiv", 42.14, 24.75), ("Varna", 43.21, 27.91), ("Burgaz", 42.50, 27.47),
    ("Bükreş", 44.43, 26.10), ("Köstence", 44.18, 28.63), ("Kluj", 46.77, 23.60), ("Temeşvar", 45.75, 21.23),
    ("Belgrad", 44.79, 20.45), ("Selanik", 40.64, 22.94), ("Atina", 37.98, 23.73), ("Üsküp", 42.00, 21.43),
    ("Zagreb", 45.81, 15.98), ("Ljubljana", 46.06, 14.51), ("Budapeşte", 47.50, 19.04), ("Debrecen", 47.53, 21.63),
    ("Viyana", 48.21, 16.37), ("Graz", 47.07, 15.44), ("Linz", 48.31, 14.29), ("Salzburg", 47.81, 13.06),
    ("Innsbruck", 47.27, 11.40), ("Bratislava", 48.15, 17.11), ("Koşice", 48.72, 21.26), ("Prag", 50.08, 14.44),
    ("Brno", 49.20, 16.61), ("Ostrava", 49.82, 18.26), ("Varşova", 52.23, 21.01), ("Krakov", 50.06, 19.94),
    ("Poznan", 52.41, 16.93), ("Gdansk", 54.35, 18.65), ("Wroclaw", 51.11, 17.04), ("Lodz", 51.76, 19.46),
    ("Berlin", 52.52, 13.40), ("Hamburg", 53.55, 9.99), ("Münih", 48.14, 11.58), ("Köln", 50.94, 6.96),
    ("Frankfurt", 50.11, 8.68), ("Stuttgart", 48.78, 9.18), ("Dresden", 51.05, 13.74), ("Leipzig", 51.34, 12.37),
    ("Nürnberg", 49.45, 11.08), ("Hannover", 52.38, 9.73), ("Bremen", 53.08, 8.80), ("Dortmund", 51.51, 7.47),
    ("Kiel", 54.32, 10.14), ("Rostock", 54.09, 12.10), ("Amsterdam", 52.37, 4.90), ("Rotterdam", 51.92, 4.48),
    ("Brüksel", 50.85, 4.35), ("Anvers", 51.22, 4.40), ("Lüksemburg", 49.61, 6.13), ("Paris", 48.86, 2.35),
    ("Lyon", 45.76, 4.84), ("Marsilya", 43.30, 5.37), ("Bordo", 44.84, -0.58), ("Toulouse", 43.60, 1.44),
    ("Nantes", 47.22, -1.55), ("Lille", 50.63, 3.06), ("Calais", 50.95, 1.86), ("Strazburg", 48.57, 7.75),
    ("Madrid", 40.42, -3.70), ("Barselona", 41.39, 2.17), ("Valensiya", 39.47, -0.38), ("Sevilla", 37.39, -5.98),
    ("Bilbao", 43.26, -2.93), ("Lizbon", 38.72, -9.14), ("Porto", 41.15, -8.61), ("Milano", 45.46, 9.19),
    ("Torino", 45.07, 7.69), ("Venedik", 45.44, 12.33), ("Bologna", 44.49, 11.34), ("Roma", 41.90, 12.50),
    ("Napoli", 40.85, 14.27), ("Bari", 41.12, 16.87), ("Cenevre", 46.20, 6.14), ("Zürih", 47.37, 8.54),
    ("Bern", 46.95, 7.45), ("Londra", 51.51, -0.13), ("Birmingham", 52.49, -1.89), ("Manchester", 53.48, -2.24),
    ("Glasgow", 55.86, -4.25), ("Edinburgh", 55.95, -3.19), ("Kopenhag", 55.68, 12.57), ("Aarhus", 56.16, 10.20),
    ("Oslo", 59.91, 10.75), ("Bergen", 60.39, 5.32), ("Stavanger", 58.97, 5.73), ("Stockholm", 59.33, 18.07),
    ("Göteborg", 57.71, 11.97), ("Malmö", 55.60, 13.00), ("Sundsvall", 62.39, 17.31), ("Helsinki", 60.17, 24.94),
    ("Tampere", 61.50, 23.79), ("Turku", 60.45, 22.27), ("Kuopio", 62.89, 27.68), ("Tallinn", 59.44, 24.75),
    ("Riga", 56.95, 24.11), ("Vilnius", 54.69, 25.28), ("Kaunas", 54.90, 23.89), ("Klaipeda", 55.71, 21.14),
    ("St. Petersburg", 59.93, 30.36), ("Kaliningrad", 54.71, 20.51), ("Pskov", 57.82, 28.33),
]


def nearest_city(lat, lon):
    best, best_d = None, 1e18
    for name, clat, clon in CITIES:
        dlat = math.radians(lat - clat)
        dlon = math.radians(lon - clon) * math.cos(math.radians((lat + clat) / 2))
        d = dlat * dlat + dlon * dlon
        if d < best_d:
            best, best_d = name, d
    return best, math.sqrt(best_d) * 6371.0
