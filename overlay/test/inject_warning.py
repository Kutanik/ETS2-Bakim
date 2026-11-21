"""Test: katmana kritik/dikkat uyarıları içeren sahte bir durum yazar (uyarı şeridini görmek için)."""
import struct
import sys
import time
from multiprocessing import shared_memory

STATE = "Local\\ETS2BakimState"
seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0

lines = [
    "v\t1", "cfg\tsound\t0",
    "k\ttruck\tScania S 2016\tn\t-1", "k\ttime\tSal 14:20\tn\t-1", "k\tloc\tİnnsbruck yakını\tn\t-1",
    "k\tamb\t31,5 °C\tn\t-1", "k\todo\t512.904 km\tn\t-1", "k\trun\tÇalışıyor\tg\t-1",
    "k\tcool\t112 °C\tc\t0.85", "k\toilt\t131 °C\tw\t0.83", "k\toilp\t1,2 bar\tw\t0.2",
    "k\tvolt\t27,9 V\tg\t0.88", "k\tsoc\t%81\tg\t0.81", "k\tolife\t%7\tw\t0.07", "k\tfreeze\t−37 °C\tg\t-1",
    "k\tdpf\t%96\tw\t0.74", "k\thealth\t%61,3\tg\t0.61",
    "w\tcrit\tHARARET: 112 °C",
    "w\twarn\tFan kavraması arızası: fan devreye girmiyor; düşük hızda, yokuşta ve sıcak havada hararet.",
    "w\twarn\tYağ ömrü %7 (TBN (asit nötrleme)). Değişim yaklaşıyor.",
]
payload = "\n".join(lines).encode("utf-8")
m = shared_memory.SharedMemory(name=STATE, create=True, size=256 * 1024)
buf = m.buf
buf[0:8] = b"EBKSTAT1"
buf[64:64 + len(payload)] = payload
struct.pack_into("<IIIII", buf, 8, 2, len(payload), 0, 0, 1)
end = time.time() + seconds
beat = 1
while time.time() < end:
    beat += 1
    struct.pack_into("<I", buf, 24, beat)
    time.sleep(0.2)
m.close()
m.unlink()
