"""1. kapağın başlıksız hâli (Türkçe, İngilizce, Almanca): panel, KRİTİK uyarı şeridi ve altta ikaz lambaları.

Parçalar o dilde çizilmiş katmandan (katman_ciz.py kritik --dil=en ...) kesilir; konumları katmansız oyun görüntüsüyle
farkından bulunur. Çıktı: tanitim/kapaklar/tek_01_yazisiz[_en|_de].png
Kullanım: .venv\\Scripts\\python.exe tanitim\\kapak_yazisiz.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kapak_olustur as K  # noqa: E402
from PIL import Image, ImageChops  # noqa: E402

TOP = 34          # üst kenar boşluğu (uyarı şeridi)
SIDE = 34
# orta boşluktaki başlık (iki satır)
TITLE = {"tr": ("Gerçekçi Arıza", "İzleme Uygulaması"),
         "en": ("Realistic Breakdown", "Monitoring App"),
         "de": ("App zur realistischen", "Pannenüberwachung")}
# sol üstteki uygulama adı (uygulamanın kendi çevirisi, i18n.py)
NAME = {"tr": "ETS2 BAKIM", "en": "ETS2 MAINTENANCE", "de": "ETS2 WARTUNG"}


def boxes(cap, game):
    """Panel, uyarı şeridi ve lamba şeridinin sınırları (katmanlı ve katmansız görüntünün farkı)."""
    m = ImageChops.difference(cap.convert("RGB"), game).convert("L").point(lambda v: 255 if v > 10 else 0)
    out = {}
    for name, (x0, y0, x1, y1) in {"panel": (0, 0, 620, 860), "banner": (600, 0, 1320, 200),
                                   "strip": (500, 860, 1420, 1080)}.items():
        bb = m.crop((x0, y0, x1, y1)).getbbox()
        out[name] = (bb[0] + x0, bb[1] + y0, bb[2] + x0, bb[3] + y0)
    return out


def fix_stop(strip, game, origin):
    """İlk lamba (STOP) sönük karede çekildiyse yanık hâline getirir."""
    w, h = strip.size
    icon_h = int(h * 0.62)
    cols = [x for x in range(w) if any((lambda p: p[0] > 60 and p[0] > p[1] + 25)(strip.getpixel((x, y)))
                                       for y in range(4, icon_h, 2))]
    if not cols:
        return
    x0 = x1 = cols[0]
    for c in cols:                      # ilk simge: 14 px'ten büyük boşluğa kadar
        if c - x1 > 14:
            break
        x1 = c
    if max(strip.getpixel((x, y))[0] for x in range(x0, x1 + 1) for y in range(4, icon_h, 2)) >= 200:
        return
    K.unblink(strip, (max(0, x0 - 4), 2, min(w, x1 + 5), icon_h), game, origin, 0.22)
    K.unblink(strip, (max(0, x0 - 30), icon_h, min(w, x1 + 31), h - 2), game, origin, 0.65)


def make(lang):
    game = Image.open(K.GAME_BG).convert("RGB")
    cap = Image.open(os.path.join(K.PARTS, "kritik.png" if lang == "tr" else f"kritik_{lang}.png")).convert("RGBA")
    b = boxes(cap, game)
    panel = K.deghost(cap.crop(b["panel"]), game, b["panel"][:2])
    banner = cap.crop(b["banner"])
    strip = cap.crop(b["strip"])
    fix_stop(strip, game, b["strip"][:2])

    base = K.cover(K.clean_bg("cam"), fx=0.6, fy=0.5)
    base = K.grade(base, 0.62, 1.12, 0.9)
    base.alpha_composite(K.gradient(K.W, K.H, [(0, (0, 0, 0, 0)), (0.42, (0, 0, 0, 40)), (1, (0, 0, 0, 160))]))
    base = K.vignette(base, 0.5)

    # sol üst: uygulama adı (Tek / Çok Oyunculu etiketi yok)
    chip = K.pill(NAME[lang], 30, (12, 12, 12, 215), pad=(18, 9))
    icon = K.app_icon("tek", 54)
    box = Image.new("RGBA", (chip.width + 62, max(chip.height, 58)), (0, 0, 0, 0))
    box.alpha_composite(chip, (52, (box.height - chip.height) // 2))
    box.alpha_composite(icon, (0, (box.height - 54) // 2))
    K.paste(base, box, (26, TOP - 8), blur=10, alpha=0.6)
    chip_bottom = K.game_caption(base, 26 + 52 + 18, TOP - 8 + box.height + 3)

    # sol: panel, çipin altından alt kenara kadar sığacak boyutta
    ptop = chip_bottom + 22
    s = min(0.78, (K.H - SIDE - ptop) / panel.height)
    panel = panel.resize((round(panel.width * s), round(panel.height * s)), Image.LANCZOS)
    K.paste(base, panel, (SIDE, ptop))

    # üst: uyarı şeridi, panelin sağındaki alanda ortalanmış
    area_x0, area_x1 = SIDE + panel.width + 30, K.W - SIDE
    bs = min(0.9, (area_x1 - area_x0) / banner.width)
    banner = banner.resize((round(banner.width * bs), round(banner.height * bs)), Image.LANCZOS)
    K.paste(base, banner, (area_x0 + (area_x1 - area_x0 - banner.width) // 2, TOP))
    banner_bottom = TOP + banner.height

    # alt: ikaz lambaları
    ls = min(1.4, (area_x1 - area_x0) / strip.width)
    strip = strip.resize((round(strip.width * ls), round(strip.height * ls)), Image.LANCZOS)
    x = area_x0 + (area_x1 - area_x0 - strip.width) // 2
    strip_top = K.H - SIDE - strip.height
    K.glow(base, strip, (x, strip_top), K.CRIT, radius=40, alpha=0.45)

    # orta: başlık, uyarı şeridiyle lambalar arasında ortalı; iki satır aynı boyutta
    l1, l2 = TITLE[lang]
    max_w = area_x1 - area_x0 - 40
    size = min(K.fit(l1, K.BLACK, max_w, 96, 0.07), K.fit(l2, K.BLACK, max_w, 96, 0.07))
    sw = max(4, round(size * 0.07))
    f = K.font(K.BLACK, size)
    asc = f.getbbox("ÇİĞ", anchor="la")[1]           # büyük harf / şapka üstü ile satır üstü arası
    desc = f.getbbox("gy", anchor="la")[3]
    block = round(size * 1.02) + desc - asc
    y = (banner_bottom + strip_top - block) // 2 - asc
    cx = (area_x0 + area_x1) // 2
    K.text(base, (cx, y), l1, size, K.WHITE, K.BLACK, stroke=sw, anchor="ma")
    K.text(base, (cx, y + round(size * 1.02)), l2, size, K.WHITE, K.BLACK, stroke=sw, anchor="ma")

    out = os.path.join(K.OUT, "tek_01_yazisiz" + ("" if lang == "tr" else "_" + lang) + ".png")
    base.convert("RGB").save(out)
    print(out, flush=True)


if __name__ == "__main__":
    for lg in sys.argv[1:] or ("tr", "en", "de"):
        make(lg)
