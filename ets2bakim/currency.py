"""Para birimi: oyundaki seçimle otomatik eşleşir. Uygulamanın fiyatları avro tabanlıdır (prices.py) ve oyunun kendi
kurlarıyla oyunda seçili para birimine çevrilir; yalnızca simge değil tutar da değişir.

Oyun para birimi seçimini şifreli profilde tutar, ama profil yüklenince game.log.txt'ye `uset g_currency "N"` yazar;
seçim buradan okunur. ETS2 / ATS ayrımı telemetriden gelir. Sıra ve kurlar oyunun kendi değerleridir (SCS Modding Wiki:
g_currency; Truck Simulator Wiki: Economy, oyun 1.57). ETS2'nin tabanı EUR, ATS'ninki USD.
"""
import os
import re
import time

from .gamecfg import documents_dirs

# (kod, simge, 1 taban birim = ? bu para birimi)
ETS2 = [("EUR", "€", 1.0), ("CHF", "CHF", 0.9234), ("CZK", "Kč", 24.3209), ("GBP", "£", 0.8678),
        ("PLN", "zł", 4.2387), ("HUF", "Ft", 389.02), ("DKK", "kr", 7.4692), ("SEK", "kr", 10.941),
        ("NOK", "kr", 11.676), ("RUB", "₽", 94.423), ("BGN", "лв", 1.9558), ("RON", "lei", 5.0834),
        ("TRY", "₺", 48.729), ("ALL", "L", 96.603), ("BAM", "KM", 1.9558), ("MKD", "ден", 61.591),
        ("RSD", "DIN", 117.19), ("ISK", "kr", 150.0)]
ATS = [("USD", "$", 1.0), ("EUR", "€", 0.8672), ("CAD", "$", 1.405), ("MXN", "$", 18.482)]  # 2-3 sırası doğrulanmadı
ATS_EUR_PER_USD = 0.8672
GAME_DIRS = {"ets2": "Euro Truck Simulator 2", "ats": "American Truck Simulator"}
_RE = re.compile(r'uset g_currency "(\d+)"')
CHECK_EVERY_S = 30.0


def _log_paths(game, docs=None):
    return [os.path.join(d, GAME_DIRS[game], "game.log.txt") for d in (docs if docs is not None else documents_dirs())]


def read_index(game="ets2", docs=None, paths=None):
    """Oyunun son oturum kaydındaki para birimi seçimi (yoksa None)."""
    for p in paths if paths is not None else _log_paths(game, docs):
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                found = _RE.findall(fh.read())
        except OSError:
            continue
        if found:
            return int(found[-1])
    return None


def resolve(game, index):
    """(kod, simge, 1 € = kur). ATS'nin kurları dolar tabanlıdır; avroya göre çevrilir."""
    table = ATS if game == "ats" else ETS2
    code, sym, rate = table[index] if index is not None and 0 <= index < len(table) else table[0]
    if game == "ats":
        rate = rate / ATS_EUR_PER_USD
    return code, sym, rate


def fmt(v, cur, d=0):
    """Avro tutarını seçili para biriminde biçimler: tek karakterli simge önde (₺1.250), diğerleri sonda (1.250 Kč)."""
    from .i18n import N
    if v is None:
        return "—"
    s = N(v * cur["rate"], d)
    return f"{cur['symbol']}{s}" if len(cur["symbol"]) == 1 else f"{s} {cur['symbol']}"


class CurrencyMonitor:
    """Oyunun seçimini seyrek okur (kayıt dosyası değişince); ayarlarda elle seçim varsa onu kullanır."""

    def __init__(self, docs=None):
        self.docs = docs
        self._cache = {}       # oyun -> (dosya zamanları, indeks)
        self._checked = {}

    def _index(self, game):
        """Kayıt dosyası yalnızca değiştiyse yeniden okunur (oyun açıkken birkaç MB olabilir; her bakışta okunmasın)."""
        now = time.monotonic()
        if now - self._checked.get(game, -1e9) >= CHECK_EVERY_S:
            self._checked[game] = now
            paths = _log_paths(game, self.docs)
            stamp = []
            for p in paths:
                try:
                    st = os.stat(p)
                    stamp.append((p, st.st_mtime_ns, st.st_size))
                except OSError:
                    stamp.append((p, None, None))
            cached = self._cache.get(game)
            if cached is None or cached[0] != stamp:
                self._cache[game] = (stamp, read_index(game, paths=paths))
        cached = self._cache.get(game)
        return cached[1] if cached else None

    def get(self, settings, game="ets2"):
        if settings.get("currency_mode", "auto") == "manual":
            try:
                rate = float(settings.get("currency_rate", 1.0)) or 1.0
            except (TypeError, ValueError):
                rate = 1.0
            sym = str(settings.get("currency") or "€")[:4]
            return {"code": "", "symbol": sym, "rate": rate, "source": "manual", "game": game, "index": None}
        idx = self._index(game)
        code, sym, rate = resolve(game, idx)
        return {"code": code, "symbol": sym, "rate": rate, "source": "auto", "game": game, "index": idx}
