"""ETS2 Bakım tanıtım kapakları (YouTube küçük resmi, 1280×720): 5 Tek Oyunculu + 5 Çok Oyunculu.

Gerçek oyun görüntüleri ve oyun içi katmanın gerçek çizimleri (katman_ciz.py → _parcalar/, overlay/build/captures)
kullanılır; uyarı şeridi ve sürüş modu bildirimi katmanın kendi yazı tipleri, renkleri ve ölçüleriyle yeniden dizilir.
Çıktı: tanitim/kapaklar/*.png ve tanitim/kapaklar/onizleme.jpg
Kullanım: .venv\\Scripts\\python.exe tanitim\\kapak_olustur.py
"""
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "kapaklar")
PARTS = os.path.join(HERE, "_parcalar")
CAPS = os.path.join(ROOT, "overlay", "build", "captures")
GAME_BG = os.path.join(ROOT, "overlay", "build", "oyun_1080p.bmp")
SHOTS = r"C:\Users\fevzi\OneDrive\Belgeler\Euro Truck Simulator 2\screenshot"
W, H = 1280, 720
FONTS = r"C:\Windows\Fonts"
BLACK, BOLD, REG = "seguibl.ttf", "segoeuib.ttf", "segoeui.ttf"

# renkler (katmanla aynı)
CRIT, CRIT_TXT, WARN, GOOD, ACCENT, ORANGE = (229, 57, 53), (255, 77, 77), (255, 198, 26), (47, 191, 47), (57, 135, 229), (232, 105, 47)
YELLOW, WHITE = (255, 210, 31), (255, 255, 255)
MODES = {"tek": dict(label="TEK OYUNCULU", col=(42, 120, 214), icon="app.ico"),
         "cok": dict(label="ÇOK OYUNCULU · TruckersMP", col=(18, 150, 72), icon="app_mp.ico")}

_fonts = {}


def font(name, size):
    key = (name, int(size))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(os.path.join(FONTS, name), int(size))
    return _fonts[key]


# ---------------------------------------------------------------- görüntü yardımcıları
def cover(img, w=W, h=H, fx=0.5, fy=0.5, zoom=1.0):
    """Görüntüyü w×h'yi tamamen kaplayacak şekilde ölçekler; (fx, fy) odak noktası, zoom ek yakınlaştırma."""
    img = img.convert("RGB")
    s = max(w / img.width, h / img.height) * zoom
    r = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x = min(max(0, round(r.width * fx - w / 2)), r.width - w)
    y = min(max(0, round(r.height * fy - h / 2)), r.height - h)
    return r.crop((x, y, x + w, y + h)).convert("RGBA")


def grade(img, bright=1.0, contrast=1.0, sat=1.0, tint=None, tint_a=0.0):
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Brightness(rgb).enhance(bright)
    rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
    rgb = ImageEnhance.Color(rgb).enhance(sat)
    if tint:
        rgb = Image.blend(rgb, Image.new("RGB", rgb.size, tint), tint_a)
    return rgb.convert("RGBA")


def gradient(w, h, stops, horizontal=True):
    """Saydamlık geçişi: stops = [(konum 0..1, (r, g, b, a)), ...]"""
    g = Image.new("RGBA", (w, h))
    px = g.load()
    n = w if horizontal else h
    cols = []
    for i in range(n):
        t = i / max(1, n - 1)
        for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
            if p0 <= t <= p1:
                k = (t - p0) / max(1e-6, p1 - p0)
                cols.append(tuple(round(c0[j] + (c1[j] - c0[j]) * k) for j in range(4)))
                break
        else:
            cols.append(stops[-1][1])
    for i, c in enumerate(cols):
        if horizontal:
            for y in range(h):
                px[i, y] = c
        else:
            for x in range(w):
                px[x, i] = c
    return g


def vignette(img, strength=0.55):
    w, h = img.size
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).ellipse((-w * 0.15, -h * 0.25, w * 1.15, h * 1.25), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(min(w, h) * 0.18))
    dark = Image.new("RGBA", (w, h), (0, 0, 0, round(255 * strength)))
    dark.putalpha(ImageChops.invert(m).point(lambda v: round(v * strength)))
    out = img.copy()
    out.alpha_composite(dark)
    return out


def shadow_of(layer, blur=14, offset=(0, 8), alpha=0.65):
    a = layer.getchannel("A").point(lambda v: round(v * alpha))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(sh, offset)
    return out


def paste(base, img, xy, shadow=True, blur=16, alpha=0.7):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer.alpha_composite(img.convert("RGBA"), (round(xy[0]), round(xy[1])))
    if shadow:
        base.alpha_composite(shadow_of(layer, blur=blur, alpha=alpha))
    base.alpha_composite(layer)


def glow(base, img, xy, color, radius=26, alpha=0.9):
    """Lamba gibi parlayan öğeler için renkli hale."""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer.alpha_composite(img.convert("RGBA"), (round(xy[0]), round(xy[1])))
    halo = Image.new("RGBA", base.size, color + (0,))
    halo.putalpha(layer.getchannel("A").point(lambda v: round(v * alpha)))
    base.alpha_composite(halo.filter(ImageFilter.GaussianBlur(radius)))
    base.alpha_composite(layer)


def text(base, xy, s, size, fill=WHITE, fnt=BLACK, stroke=0, stroke_fill=(0, 0, 0), anchor="la", shadow=True,
         sh_blur=12, sh_alpha=0.75):
    f = font(fnt, size)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(xy, s, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill, anchor=anchor)
    if shadow:
        base.alpha_composite(shadow_of(layer, blur=sh_blur, offset=(0, round(size * 0.06)), alpha=sh_alpha))
    base.alpha_composite(layer)
    return ImageDraw.Draw(layer).textbbox(xy, s, font=f, stroke_width=stroke, anchor=anchor)


def fit(s, fnt, max_w, size, stroke_k=0.0):
    while size > 10:
        f = font(fnt, size)
        if f.getlength(s) + 2 * stroke_k * size <= max_w:
            return size
        size -= 2
    return size


def headline(base, lines, x, y, max_w, anchor="l"):
    """Büyük başlık: [(metin, boyut, renk)], kalın siyah kontur ve gölgeyle; satırlar sığacak kadar küçülür."""
    for s, size, col in lines:
        size = fit(s, BLACK, max_w, size, 0.07)
        sw = max(4, round(size * 0.07))
        a = {"l": "la", "m": "ma", "r": "ra"}[anchor]
        text(base, (x, y), s, size, col, BLACK, stroke=sw, anchor=a)
        y += round(size * 1.02)
    return y


def pill(s, size, bg, fg=WHITE, fnt=BLACK, pad=(18, 8), radius=None, border=None):
    f = font(fnt, size)
    bb = f.getbbox(s)
    w, h = round(bb[2] - bb[0] + 2 * pad[0]), round(size * 1.15 + 2 * pad[1])
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius if radius is not None else h // 2, fill=bg,
                        outline=border, width=3 if border else 0)
    d.text((w / 2, h / 2), s, font=f, fill=fg, anchor="mm")
    return img


def app_icon(mode, size):
    ico = Image.open(os.path.join(ROOT, "ets2bakim", MODES[mode]["icon"]))
    ico.size = (256, 256)
    return ico.convert("RGBA").resize((size, size), Image.LANCZOS)


GAME_NAME = "Euro Truck Simulator 2"


def game_caption(base, x, y, size=20):
    """Uygulama adının altında küçük oyun adı (logo değil, düz yazı: SCS'nin resmî ürünü gibi görünmesin); alt kenarı."""
    return text(base, (x, y), GAME_NAME, size, WHITE, BOLD, sh_blur=8, sh_alpha=0.85)[3]


def chrome(base, mode):
    """Sol üstte ETS2 BAKIM ve altında küçük oyun adı, sağ üstte Tek / Çok Oyunculu etiketi."""
    m = MODES[mode]
    chip = pill("ETS2 BAKIM", 30, (12, 12, 12, 215), pad=(18, 9))
    icon = app_icon(mode, 54)
    box = Image.new("RGBA", (chip.width + 62, max(chip.height, 58)), (0, 0, 0, 0))
    box.alpha_composite(chip, (52, (box.height - chip.height) // 2))
    box.alpha_composite(icon, (0, (box.height - 54) // 2))
    paste(base, box, (26, 22), blur=10, alpha=0.6)
    game_caption(base, 26 + 52 + 18, 22 + box.height + 3)
    tag = pill(m["label"], 27, m["col"] + (245,), pad=(20, 9))
    paste(base, tag, (W - 26 - tag.width, 26), blur=10, alpha=0.6)


# ---------------------------------------------------------------- katman parçaları
def overlay_strip_bg(x, y, game):
    """Lamba şeridinin pencere rengi (katmanda %91 opak #191918) altındaki oyun pikseliyle karışımı."""
    g = game.getpixel((x, y))
    return tuple(0.91 * c + 0.09 * gc for c, gc in zip((25, 25, 24), g))


def unblink(img, box, game, origin, a):
    """Yanıp sönen lambanın sönük karesini (saydamlık a) yanık hâline çevirir: renk = arka + (piksel − arka) / a."""
    px = img.load()
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        for x in range(x0, x1):
            bg = overlay_strip_bg(x + origin[0], y + origin[1], game)
            p = px[x, y]
            px[x, y] = tuple(max(0, min(255, round(bg[i] + (p[i] - bg[i]) / a))) for i in range(3)) + (p[3],)


def deghost(img, game, origin, alpha=0.91, behind=(30, 30, 29)):
    """Panel %91 opak: arkadaki oyun görüntüsünün (içinde eski bir panel de var) %9'u silik iz olarak görünür. Arka planın
    katkısı düz koyu bir zeminle değiştirilir: piksel + (1 − a) · (koyu − arka)."""
    img = img.convert("RGBA")
    px = img.load()
    k = 1.0 - alpha
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            gb = game.getpixel((x + origin[0], y + origin[1]))
            px[x, y] = (max(0, min(255, round(r + k * (behind[0] - gb[0])))),
                        max(0, min(255, round(g + k * (behind[1] - gb[1])))),
                        max(0, min(255, round(b + k * (behind[2] - gb[2])))), a)
    return img


def parts():
    """Katman çizimlerinden kesilen parçalar (kritik.png: 1,6× panel, 2× lambalar)."""
    game = Image.open(GAME_BG).convert("RGB")
    k = Image.open(os.path.join(PARTS, "kritik.png")).convert("RGBA")
    strip = k.crop((727, 930, 1193, 1064))
    # STOP simgesi (400 ms yanık / 400 ms sönük) sönük karede çekildiyse yanık hâline getir
    sx0, sy0 = 727, 930
    stop_icon, stop_label = (12, 4, 122, 82), (12, 86, 122, 128)
    if max(strip.getpixel((x, y))[0] for x in range(30, 100, 3) for y in range(20, 70, 3)) < 200:
        unblink(strip, stop_icon, game, (sx0, sy0), 0.22)
        unblink(strip, stop_label, game, (sx0, sy0), 0.65)
    lamps = {}
    for name, (x0, x1) in {"stop": (12, 120), "yag": (122, 218), "sogutma": (222, 352), "motor": (352, 455)}.items():
        lamps[name] = strip.crop((x0, 0, x1, strip.height))
    big = Image.open(os.path.join(CAPS, "yeni_lamba", "serit_buyuk.png")).convert("RGBA")
    for name, (x0, x1) in {"mars": (310, 470), "direksiyon": (470, 680), "sanziman": (680, 880)}.items():
        lamps[name] = big.crop((x0, 30, x1, 210))
    return dict(
        strip=strip,
        panel=deghost(k.crop((16, 16, 582, 792)), game, (16, 16)),
        lamps=lamps,
        banner=k.crop((649, 11, 1271, 117)),
        cockpit=k,
        game=game,
    )


def lamp_strip(icons, scale=1.0):
    """Katmandaki gibi koyu, yuvarlak köşeli şerit içinde lambalar (gerçek çizimlerden)."""
    icons = [im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS) for im in icons]
    pad, gap = round(14 * scale), round(4 * scale)
    w = sum(i.width for i in icons) + gap * (len(icons) - 1) + 2 * pad
    h = max(i.height for i in icons) + 2 * pad
    box = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(box).rounded_rectangle((0, 0, w - 1, h - 1), radius=round(16 * scale), fill=(25, 25, 24, 235),
                                          outline=(255, 255, 255, 30), width=max(1, round(2 * scale)))
    x = pad
    for im in icons:
        # parçaların kendi (koyu) zemini şerit rengine yakın; kenar izi kalmasın diye koyu pikseller saydamlaşır
        box.alpha_composite(knock_dark(im), (x, (h - im.height) // 2))
        x += im.width + gap
    return box


def knock_dark(im, lo=34, hi=70):
    """Koyu zemini saydam yapar (yalnızca simge ve yazı kalır)."""
    im = im.convert("RGBA")
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            v = max(r, g, b)
            t = 0 if v <= lo else 255 if v >= hi else round((v - lo) / (hi - lo) * 255)
            px[x, y] = (r, g, b, min(a, t))
    return im


def banner(lines, s=2.0, width=620):
    """Katmanın uyarı şeridi (üst orta): koyu zemin, kırmızı / sarı çerçeve, KRİTİK / DİKKAT etiketi."""
    w = round(width * s)
    pad_x, pad_y = round(12 * s), round(10 * s)
    f_lab = font(BOLD, 12 * s)
    rows = []
    for lvl, msg in lines:
        lab = "KRİTİK" if lvl == "crit" else "DİKKAT"
        f_txt = font(BOLD if lvl == "crit" else REG, 14.5 * s)
        lw = f_lab.getlength(lab) + 8 * s
        avail = w - 2 * pad_x - lw
        words, cur, out = msg.split(), "", []
        for wd in words:
            t = (cur + " " + wd).strip()
            if f_txt.getlength(t) <= avail:
                cur = t
            else:
                out.append(cur)
                cur = wd
        out.append(cur)
        rows.append((lvl, lab, lw, f_txt, out))
    lh = round(14.5 * s * 1.25)
    h = pad_y * 2 + sum(len(r[4]) * lh for r in rows) + round(4 * s) * (len(rows) - 1)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    crit = rows[0][0] == "crit"
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=round(8 * s), fill=(25, 25, 24, 235),
                        outline=CRIT if crit else WARN, width=round(2 * s))
    y = pad_y
    for lvl, lab, lw, f_txt, out in rows:
        d.text((pad_x, y + round(2 * s)), lab, font=f_lab, fill=CRIT_TXT if lvl == "crit" else WARN)
        for ln in out:
            d.text((pad_x + lw, y), ln, font=f_txt, fill=WHITE)
            y += lh
        y += round(4 * s)
    return img


DRIVE = {"eco": ("ECO", GOOD, "Güç %75 · yumuşak gaz · 85 km/h sınır"),
         "comfort": ("COMFORT", ACCENT, "Yumuşak gaz tepkisi · güç sınırı yok"),
         "sport": ("SPORT", ORANGE, "Keskin pedal · anında tepki")}


def toast(mode, s=3.0):
    """Sürüş modu değişince katmanda çıkan bildirim (SÜRÜŞ MODU · ad · açıklama)."""
    name, col, desc = DRIVE[mode]
    f1, f2, f3 = font(BOLD, 13 * s), font(BOLD, 34 * s), font(REG, 14 * s)
    t1 = "SÜRÜŞ MODU"
    w = max(f1.getlength(t1), f2.getlength(name), f3.getlength(desc)) + 48 * s
    h1, h2, h3 = f1.getbbox(t1)[3], f2.getbbox(name)[3], f3.getbbox(desc)[3]
    h = h1 + h2 + h3 + 34 * s
    img = Image.new("RGBA", (round(w), round(h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius=round(10 * s), fill=(11, 11, 11, 225),
                        outline=col + (242,), width=round(2.5 * s))
    y = 10 * s
    d.text((img.width / 2, y), t1, font=f1, fill=(201, 198, 189), anchor="ma")
    y += h1 + 4 * s
    d.text((img.width / 2, y), name, font=f2, fill=col, anchor="ma")
    y += h2 + 4 * s
    d.text((img.width / 2, y), desc, font=f3, fill=(228, 226, 218), anchor="ma")
    return img


def frost(base, strength=1.0, seed=3):
    """Kenarlarda buz / kırağı: bulanık açık mavi gürültü."""
    rnd = random.Random(seed)
    w, h = base.size
    n = Image.new("L", (w // 10, h // 10))
    px = n.load()
    for y in range(n.height):
        for x in range(n.width):
            px[x, y] = rnd.randint(40, 255)
    n = n.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(6))
    edge = Image.new("L", (w, h), 0)
    ImageDraw.Draw(edge).rectangle((0, 0, w, h), fill=255)
    hole = Image.new("L", (w, h), 0)
    ImageDraw.Draw(hole).ellipse((w * 0.12, h * 0.05, w * 0.88, h * 1.05), fill=255)
    hole = hole.filter(ImageFilter.GaussianBlur(120))
    mask = ImageChops.subtract(edge, hole)
    mask = ImageChops.multiply(mask, n.point(lambda v: min(255, round(v * 1.4))))
    mask = mask.point(lambda v: round(v * strength))
    ice = Image.new("RGBA", (w, h), (215, 238, 255, 0))
    ice.putalpha(mask)
    base.alpha_composite(ice)
    for _ in range(260):                       # kar taneleri
        x, y, r = rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(1.2, 3.4)
        flake = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        ImageDraw.Draw(flake).ellipse((8 - r, 8 - r, 8 + r, 8 + r), fill=(255, 255, 255, rnd.randint(110, 220)))
        base.alpha_composite(flake.filter(ImageFilter.GaussianBlur(0.6)), (round(x), round(y)))


def battery_icon(w, level, col):
    """Basit akü çizimi (çerçeve, kutup başları, seviye)."""
    h = round(w * 0.6)
    img = Image.new("RGBA", (w + 4, h + round(w * 0.12) + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    t = round(w * 0.12)
    lw = max(4, round(w * 0.055))
    d.rounded_rectangle((round(w * 0.18), 0, round(w * 0.34), t + lw), radius=round(lw / 2), fill=col)
    d.rounded_rectangle((round(w * 0.66), 0, round(w * 0.82), t + lw), radius=round(lw / 2), fill=col)
    d.rounded_rectangle((2, t, w, t + h), radius=round(w * 0.07), outline=col, width=lw)
    inner = (2 + lw * 2, t + lw * 2, w - lw * 2, t + h - lw * 2)
    fill_w = round((inner[2] - inner[0]) * level)
    if fill_w > 0:
        d.rounded_rectangle((inner[0], inner[1], inner[0] + fill_w, inner[3]), radius=round(lw * 0.6), fill=col)
    return img


# ---------------------------------------------------------------- kapaklar
def load_shot(name):
    return Image.open(os.path.join(SHOTS, name)).convert("RGB")


def clean_bg(which):
    """Oyun görüntülerinin katman ve oyun arayüzü (hız göstergesi, iş bilgisi, harita, aynalar) içermeyen kesitleri."""
    if which == "cam":          # Volvo kabini: ön cam ve liman
        return Image.open(GAME_BG).convert("RGB").crop((560, 60, 1550, 617))
    if which == "direksiyon":   # Volvo kabini: direksiyon ve gösterge paneli
        return Image.open(GAME_BG).convert("RGB").crop((560, 420, 1550, 977))
    if which == "rafineri":     # rafineride kabin içi
        return load_shot("ets2_20261001_221435_00.png").crop((330, 300, 1555, 989))
    if which == "gece":         # gece otoparkı, tır yukarıdan
        return load_shot("ets2_20261010_202805_00.png").crop((300, 0, 1555, 706))
    raise KeyError(which)


def check_pill(s, size, bg, fg=WHITE):
    """Başında çizilmiş onay işareti olan etiket (yazı tipinde ✓ yok)."""
    f = font(BLACK, size)
    tw = f.getlength(s)
    hgt = round(size * 1.15 + 20)
    icon = round(size * 0.95)
    w = round(tw + icon + 18 + 2 * 20)
    img = Image.new("RGBA", (w, hgt), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, hgt - 1), radius=hgt // 2, fill=bg)
    cx, cy = 20 + icon / 2, hgt / 2
    lw = max(4, round(size * 0.16))
    d.line([(cx - icon * 0.36, cy + icon * 0.02), (cx - icon * 0.08, cy + icon * 0.3), (cx + icon * 0.4, cy - icon * 0.32)],
           fill=fg, width=lw, joint="curve")
    d.text((20 + icon + 18, hgt / 2), s, font=f, fill=fg, anchor="lm")
    return img


def k_tek_01(P):
    """Ana tanıtım: gerçek arıza + güç modu + canlı izleme."""
    base = cover(clean_bg("cam"), fx=0.6, fy=0.5)
    base = grade(base, 0.62, 1.12, 0.9)
    base.alpha_composite(gradient(W, H, [(0, (0, 0, 0, 0)), (0.42, (0, 0, 0, 40)), (1, (0, 0, 0, 215))]))
    base = vignette(base, 0.5)
    panel = P["panel"].resize((round(566 * 0.76), round(776 * 0.76)), Image.LANCZOS)
    paste(base, panel, (34, 118))        # sol üstteki oyun adının altından başlar
    paste(base, P["banner"].resize((round(622 * 0.88), round(106 * 0.88)), Image.LANCZOS), (346, 22))
    y = headline(base, [("GERÇEK", 120, WHITE), ("ARIZA!", 160, CRIT_TXT)], 520, 140, 720)
    text(base, (528, y + 6), "+ GÜÇ MODU  + CANLI İZLEME", 40, YELLOW, BLACK, stroke=4)
    strip = lamp_strip([P["lamps"][n] for n in ("stop", "yag", "sogutma", "motor")], 1.0)
    glow(base, strip, (560, 520), CRIT, radius=30, alpha=0.35)
    chrome(base, "tek")
    return base


def k_tek_02(P):
    """−25 °C: yanlış yağla motor çalışmadı."""
    base = cover(clean_bg("rafineri"), fx=0.5, fy=0.5)
    base = grade(base, 0.6, 1.1, 0.25, tint=(70, 130, 200), tint_a=0.32)
    frost(base, 0.95)
    base = vignette(base, 0.55)
    text(base, (48, 108), "−25 °C", 150, (210, 236, 255), BLACK, stroke=8, stroke_fill=(8, 30, 60))
    y = headline(base, [("MOTOR", 112, WHITE), ("ÇALIŞMADI!", 132, CRIT_TXT)], 48, 300, 700)
    bn = banner([("crit", "MOTOR GERÇEKTE ÇALIŞMIYOR: Marş başarısız: Yağ çok koyu (21.400 cSt): marş motoru motoru "
                          "çeviremiyor. Oyunda motoru kapatın.")], s=1.25, width=430)
    paste(base, bn, (W - bn.width - 34, 128))
    strip = lamp_strip([P["lamps"]["stop"], P["lamps"]["mars"].resize((128, 144), Image.LANCZOS)], 1.15)
    glow(base, strip, (W - strip.width - 70, 430), CRIT, radius=34, alpha=0.4)
    chrome(base, "tek")
    return base


def k_tek_03(P):
    """Yağ değiştirmeden kaç km gider?"""
    base = cover(clean_bg("direksiyon"), fx=0.5, fy=0.5)
    base = grade(base, 0.55, 1.15, 0.8, tint=(120, 70, 20), tint_a=0.22)
    base.alpha_composite(gradient(W, H, [(0, (0, 0, 0, 200)), (0.55, (0, 0, 0, 90)), (1, (0, 0, 0, 30))]))
    base = vignette(base, 0.45)
    lamp = P["lamps"]["yag"]
    lamp = knock_dark(lamp.resize((lamp.width * 3, lamp.height * 3), Image.LANCZOS))
    glow(base, lamp, (W - lamp.width - 110, 180), CRIT, radius=40, alpha=0.75)
    y = headline(base, [("YAĞ DEĞİŞTİRMEDEN", 82, WHITE), ("KAÇ KM", 190, YELLOW), ("GİDER?", 120, YELLOW)], 48, 120, 760)
    card = stat_card("Yağ ömrü", "%0", 0.0, CRIT_TXT, "değişim zamanı geçti")
    paste(base, card, (W - card.width - 70, 470))
    chrome(base, "tek")
    return base


def stat_card(label, value, frac, col, sub):
    """Katmanın değer kutusu biçiminde küçük kart (etiket, büyük değer, çubuk)."""
    w, h = 360, 168
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=14, fill=(25, 25, 24, 235), outline=(255, 255, 255, 30), width=2)
    d.text((24, 18), label, font=font(REG, 26), fill=(228, 226, 218))
    d.text((24, 50), value, font=font(BOLD, 58), fill=col)
    d.text((24, 118), sub, font=font(REG, 20), fill=(201, 198, 189))
    d.rounded_rectangle((24, 150, w - 24, 158), radius=4, fill=(60, 60, 57))
    if frac > 0:
        d.rounded_rectangle((24, 150, 24 + round((w - 48) * frac), 158), radius=4, fill=col)
    return img


def k_tek_04(P):
    """Akü bitti: farlar açık kaldı, marş yok."""
    base = cover(clean_bg("gece"), fx=0.5, fy=0.5)
    base = grade(base, 0.8, 1.2, 0.8, tint=(10, 20, 60), tint_a=0.25)
    base.alpha_composite(gradient(W, H, [(0, (0, 0, 0, 215)), (0.5, (0, 0, 0, 120)), (1, (0, 0, 0, 30))]))
    base = vignette(base, 0.5)
    bat = battery_icon(250, 0.09, CRIT_TXT)
    glow(base, bat, (W - bat.width - 120, 150), CRIT, radius=36, alpha=0.6)
    text(base, (W - 120 - bat.width / 2, 340), "%9", 74, CRIT_TXT, BLACK, stroke=5, anchor="ma")
    y = headline(base, [("AKÜ", 170, CRIT_TXT), ("BİTTİ!", 170, WHITE)], 48, 110, 640)
    text(base, (56, y + 8), "Farlar açık kaldı… marş yok", 40, YELLOW, BLACK, stroke=4)
    bn = banner([("crit", "Marş başarısız: Akü yetersiz: marşta voltaj 15,2 V'a düştü.")], s=1.3, width=420)
    paste(base, bn, (W - bn.width - 40, 470))
    chrome(base, "tek")
    return base


def k_tek_05(P):
    """Tırı öldüren 5 sürücü hatası."""
    base = cover(clean_bg("direksiyon"), fx=0.5, fy=0.5)
    base = grade(base, 0.48, 1.2, 0.45, tint=(90, 10, 10), tint_a=0.25)
    base = vignette(base, 0.6)
    text(base, (60, 70), "5", 420, CRIT_TXT, BLACK, stroke=12)
    headline(base, [("TIRI ÖLDÜREN", 96, WHITE), ("SÜRÜCÜ HATASI", 96, YELLOW)], 330, 150, 900)
    icons = [P["lamps"][n] for n in ("mars", "sanziman", "sogutma", "motor", "stop")]
    icons = [ic if ic.height == P["lamps"]["stop"].height else ic.resize((round(ic.width * 134 / 180), 134), Image.LANCZOS)
             for ic in icons]
    strip = lamp_strip(icons, 1.05)
    glow(base, strip, ((W - strip.width) / 2, 470), CRIT, radius=30, alpha=0.35)
    chrome(base, "tek")
    return base


def k_cok_01(P):
    """TruckersMP'de gerçek bakım: uyarır, motoru zorla durdurmaz."""
    base = cover(clean_bg("rafineri"), fx=0.5, fy=0.5)
    base = grade(base, 0.55, 1.12, 0.75, tint=(10, 60, 30), tint_a=0.18)
    base.alpha_composite(gradient(W, H, [(0, (0, 0, 0, 225)), (0.55, (0, 0, 0, 120)), (1, (0, 0, 0, 40))]))
    base = vignette(base, 0.45)
    panel = P["panel"].resize((round(566 * 0.74), round(776 * 0.74)), Image.LANCZOS)
    paste(base, panel, (W - panel.width - 34, 104))
    y = headline(base, [("TRUCKERSMP'DE", 92, WHITE), ("GERÇEK", 140, (60, 220, 110)), ("BAKIM", 140, WHITE)],
                 48, 120, 760)
    tag = check_pill("Motor trafikte asla zorla durdurulmaz", 30, (18, 150, 72, 240))
    paste(base, tag, (48, y + 18))
    chrome(base, "cok")
    return base


def k_cok_02(P):
    """Konvoyda kim önce bozulacak? (VS)"""
    left = cover(clean_bg("rafineri"), W // 2, H, fx=0.55, fy=0.5)
    left = grade(left, 0.6, 1.1, 0.7, tint=(20, 120, 60), tint_a=0.25)
    right = cover(clean_bg("direksiyon"), W // 2, H, fx=0.5, fy=0.5)
    right = grade(right, 0.5, 1.15, 0.7, tint=(130, 20, 20), tint_a=0.3)
    base = Image.new("RGBA", (W, H))
    base.alpha_composite(left, (0, 0))
    base.alpha_composite(right, (W // 2, 0))
    d = ImageDraw.Draw(base)
    d.polygon([(W // 2 - 10, 0), (W // 2 + 10, 0), (W // 2 + 10, H), (W // 2 - 10, H)], fill=(255, 255, 255, 230))
    base = vignette(base, 0.45)
    headline(base, [("KONVOYDA KİM", 84, WHITE), ("ÖNCE BOZULACAK?", 96, YELLOW)], W // 2, 110, 1180, anchor="m")
    ok_strip = lamp_strip([P["lamps"]["mars"].resize((128, 144), Image.LANCZOS)], 1.0)
    bad_strip = lamp_strip([P["lamps"][n] for n in ("stop", "yag", "sogutma")], 1.0)
    paste(base, ok_strip, (W // 4 - ok_strip.width // 2, 420))
    glow(base, bad_strip, (3 * W // 4 - bad_strip.width // 2, 420), CRIT, radius=30, alpha=0.45)
    vs = pill("VS", 64, (229, 57, 53, 255), pad=(22, 6))
    paste(base, vs, (W // 2 - vs.width // 2, 440))
    text(base, (W // 4, 600), "SEN", 54, (90, 230, 130), BLACK, stroke=5, anchor="ma")
    text(base, (3 * W // 4, 600), "KONVOY ARKADAŞIN", 46, CRIT_TXT, BLACK, stroke=5, anchor="ma")
    chrome(base, "cok")
    return base


def k_cok_03(P):
    """ECO mu SPORT mu? (TruckersMP'de de çalışır)"""
    base = cover(clean_bg("cam"), fx=0.5, fy=0.5)
    base = grade(base, 0.42, 1.1, 0.6)
    base = base.filter(ImageFilter.GaussianBlur(3))
    base = vignette(base, 0.5)
    a, b = toast("eco", 1.85), toast("sport", 1.85)
    hh = max(a.height, b.height)
    glow(base, a, (44, 300 + (hh - a.height) // 2), GOOD, radius=40, alpha=0.5)
    glow(base, b, (W - b.width - 44, 300 + (hh - b.height) // 2), ORANGE, radius=40, alpha=0.5)
    vs = pill("VS", 60, (255, 255, 255, 255), fg=(15, 15, 15), pad=(20, 4))
    paste(base, vs, ((44 + a.width + W - b.width - 44) // 2 - vs.width // 2, 300 + hh // 2 - vs.height // 2))
    headline(base, [("HANGİSİ DAHA İYİ?", 104, WHITE)], W // 2, 118, 1180, anchor="m")
    text(base, (W // 2, 600), "Güç modları TruckersMP'de de çalışır", 40, YELLOW, BLACK, stroke=4, anchor="ma")
    chrome(base, "cok")
    return base


def k_cok_04(P):
    """Frenler yanıyor! (TruckersMP'de uzun yokuş)"""
    base = cover(clean_bg("rafineri"), fx=0.5, fy=0.5)
    base = grade(base, 0.5, 1.2, 0.6, tint=(160, 50, 0), tint_a=0.35)
    heat = gradient(W, H, [(0, (255, 90, 0, 0)), (0.6, (255, 70, 0, 40)), (1, (255, 40, 0, 120))], horizontal=False)
    base.alpha_composite(heat)
    base = vignette(base, 0.55)
    y = headline(base, [("FRENLER", 140, WHITE), ("YANIYOR!", 150, (255, 120, 40))], 48, 110, 700)
    text(base, (W - 70, 120), "471 °C", 150, (255, 170, 60), BLACK, stroke=8, anchor="ra")
    bn = banner([("crit", "FRENLER AŞIRI ISINDI (471 °C) — fren gücü azaldı!"),
                 ("crit", "Hava basıncı düşük (5,2 bar): frenler kilitlenebilir.")], s=1.35, width=440)
    paste(base, bn, (W - bn.width - 40, 470))
    text(base, (56, y + 10), "Retarder kullanmazsan…", 44, YELLOW, BLACK, stroke=4)
    chrome(base, "cok")
    return base


def k_cok_05(P):
    """Çok Oyunculu sürüm çıktı: indir ve kur."""
    app = Image.open(os.path.join(PARTS, "uygulama_cok.png")).convert("RGB")
    hd = ImageDraw.Draw(app)
    bgc = app.getpixel((1180, 40))
    hd.rectangle((226, 14, 318, 54), fill=bgc)          # "(Demo)"
    hd.rectangle((2066, 20, 2182, 70), fill=bgc)        # DEMO etiketi
    base = Image.new("RGBA", (W, H), (14, 16, 18, 255))
    base.alpha_composite(gradient(W, H, [(0, (18, 150, 72, 90)), (0.55, (14, 16, 18, 0)), (1, (14, 16, 18, 0))]))
    shot = app.crop((0, 0, 2400, 1350)).resize((860, 484), Image.LANCZOS).convert("RGBA")
    frame = Image.new("RGBA", (shot.width + 16, shot.height + 16), (60, 62, 60, 255))
    frame.alpha_composite(shot, (8, 8))
    frame = frame.rotate(-4, resample=Image.BICUBIC, expand=True)
    paste(base, frame, (W - frame.width + 110, 200), blur=24, alpha=0.8)
    y = headline(base, [("ÇOK OYUNCULU", 96, WHITE), ("SÜRÜM", 120, (60, 220, 110)), ("ÇIKTI!", 120, WHITE)], 48, 110, 560)
    tag = pill("TruckersMP · Konvoy · kolay kurulum", 30, (255, 255, 255, 240), fg=(15, 15, 15), pad=(18, 9))
    paste(base, tag, (48, y + 16))
    chrome(base, "cok")
    return base


THUMBS = [
    ("tek_01_gercek_ariza", k_tek_01), ("tek_02_eksi25_motor_calismadi", k_tek_02), ("tek_03_yag_kac_km", k_tek_03),
    ("tek_04_aku_bitti", k_tek_04), ("tek_05_5_surucu_hatasi", k_tek_05),
    ("cok_01_truckersmp_gercek_bakim", k_cok_01), ("cok_02_konvoy_kim_bozulacak", k_cok_02),
    ("cok_03_eco_mu_sport_mu", k_cok_03), ("cok_04_frenler_yaniyor", k_cok_04), ("cok_05_cok_oyunculu_surum", k_cok_05),
]


def main(only=None):
    os.makedirs(OUT, exist_ok=True)
    P = parts()
    done = []
    for name, fn in THUMBS:
        if only and not any(o in name for o in only):
            continue
        img = fn(P).convert("RGB")
        img.save(os.path.join(OUT, name + ".png"))
        done.append((name, img))
        print("  ", name, flush=True)
    if len(done) == len(THUMBS):       # önizleme: 2 sütun (Tek | Çok), 5 satır
        sheet = Image.new("RGB", (2 * 640 + 30, 5 * 360 + 60), (20, 20, 20))
        for i, (name, img) in enumerate(done):
            col, row = (0, i) if i < 5 else (1, i - 5)
            sheet.paste(img.resize((640, 360), Image.LANCZOS), (10 + col * 650, 10 + row * 370))
        sheet.save(os.path.join(OUT, "onizleme.jpg"), quality=88)


if __name__ == "__main__":
    import sys
    main(sys.argv[1:] or None)
