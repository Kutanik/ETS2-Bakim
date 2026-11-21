"""24 bit BMP'yi PNG'ye çevirir (yalnızca standart kütüphane). Test ekran görüntüleri için."""
import struct
import sys
import zlib


def bmp_to_png(src, dst):
    data = open(src, "rb").read()
    off = struct.unpack_from("<I", data, 10)[0]
    w, h = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0]
    assert bpp == 24, "yalnızca 24 bit"
    row = (w * 3 + 3) & ~3
    raw = bytearray()
    for y in range(abs(h)):
        sy = abs(h) - 1 - y if h > 0 else y
        line = data[off + sy * row: off + sy * row + w * 3]
        raw.append(0)
        for x in range(0, w * 3, 3):
            raw += bytes((line[x + 2], line[x + 1], line[x]))

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, abs(h), 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b"")
    open(dst, "wb").write(png)


if __name__ == "__main__":
    bmp_to_png(sys.argv[1], sys.argv[2])
