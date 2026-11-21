r"""Oyun ekran görüntüsünden özgeçmiş (CV) için proje tanıtım görseli üretir (TR ve EN).
Kullanım: .venv\Scripts\python.exe cv\cv_kart.py [ekran_goruntusu] [cikti_klasoru]
Varsayılan: cv\kaynak_ekran_goruntusu.webp -> cv\ (ets2_bakim_cv_tr/en.png ve küçük .jpg'ler).
PANEL: ekran görüntüsündeki oyun içi katman panelinin konumu (başka görüntüde güncelleyin)."""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "kaynak_ekran_goruntusu.webp")
OUT = sys.argv[2] if len(sys.argv) > 2 else HERE
os.makedirs(OUT, exist_ok=True)
FONTS = r"C:\Windows\Fonts"


def font(names, size):
    for n in names:
        p = os.path.join(FONTS, n)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


REG = ["segoeui.ttf"]
SEMI = ["seguisb.ttf", "segoeuib.ttf"]
BOLD = ["segoeuib.ttf"]

W, H = 2400, 1350
BG = (247, 247, 245)
INK = (17, 17, 17)
INK2 = (82, 81, 78)
MUTED = (137, 135, 129)
ACCENT = (42, 120, 214)
CHIP_BG = (232, 239, 250)

TEXT = {
    "tr": dict(
        title="ETS2 Bakım Simülatörü",
        subtitle="Euro Truck Simulator 2 için gerçekçi araç bakımı simülasyonu ve oyun içi gösterge katmanı",
        shot_label="OYUN İÇİNDEN EKRAN GÖRÜNTÜSÜ",
        inset="OYUN İÇİ KATMAN · YAKIN GÖRÜNÜM",
        bullets=[
            "Motor, yağ, soğutma, akü, lastik ve DPF fiziksel modelleri",
            "DirectX 11 kancasıyla tam ekranda çalışan ImGui katmanı",
            "Telemetri SDK eklentisi, Python ↔ C++ paylaşılan bellek",
            "Tek ve çok oyunculu (TruckersMP) mod, 3 dil desteği",
        ],
        stack="Teknolojiler",
        footer="Kişisel proje · 2026",
    ),
    "en": dict(
        title="ETS2 Maintenance Simulator",
        subtitle="Realistic vehicle maintenance simulation and in-game HUD overlay for Euro Truck Simulator 2",
        shot_label="IN-GAME SCREENSHOT",
        inset="IN-GAME OVERLAY · CLOSE-UP",
        bullets=[
            "Physics models: engine, oil, cooling, battery, tyres, DPF",
            "ImGui overlay via a DirectX 11 hook, works in fullscreen",
            "Telemetry SDK plugin, Python ↔ C++ via shared memory",
            "Single and multiplayer (TruckersMP) modes, 3 languages",
        ],
        stack="Tech stack",
        footer="Personal project · 2026",
    ),
}
CHIPS = ["Python", "C++17", "DirectX 11", "Dear ImGui", "SCS Telemetry SDK", "MinHook", "Shared memory IPC", "WebView UI"]


def rounded(im, r):
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, im.size[0] - 1, im.size[1] - 1), r, fill=255)
    out = Image.new("RGBA", im.size)
    out.paste(im.convert("RGBA"), (0, 0), m)
    return out


def shadow(canvas, box, r, blur=26, alpha=70, offset=(0, 14)):
    x0, y0, x1, y1 = box
    pad = blur * 3
    sh = Image.new("RGBA", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad, pad + x1 - x0, pad + y1 - y0), r, fill=(0, 0, 0, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    canvas.alpha_composite(sh, (x0 - pad + offset[0], y0 - pad + offset[1]))


def wrap(draw, text, f, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


src = Image.open(SRC).convert("RGB")
sw, sh_ = src.size
PANEL = (14, 16, 336, 436)   # oyun içi katman paneli (ekran görüntüsünde)

for lang, t in TEXT.items():
    cv = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(cv)
    M = 90
    # başlık
    d.rectangle((M, 62, M + 10, 128), fill=ACCENT)
    d.text((M + 34, 44), t["title"], font=font(BOLD, 66), fill=INK)
    d.text((M + 36, 134), t["subtitle"], font=font(REG, 32), fill=INK2)

    # ana görüntü + yakın görünüm aynı yükseklikte, birlikte tam genişlik
    gap = 50
    ratio = (sh_ / sw) * ((PANEL[2] - PANEL[0]) / (PANEL[3] - PANEL[1]))
    mw = round((W - 2 * M - gap) / (1 + ratio))
    scale = mw / sw
    mh = round(sh_ * scale)
    iw = W - 2 * M - gap - mw
    mx, my = M, 246
    rx = mx + mw + gap
    f_lab = font(BOLD, 21)
    d.text((mx + 2, my - 36), t["shot_label"], font=f_lab, fill=MUTED)
    d.text((rx + 2, my - 36), t["inset"], font=f_lab, fill=MUTED)
    shot = src.resize((mw, mh), Image.LANCZOS)
    shadow(cv, (mx, my, mx + mw, my + mh), 22)
    cv.alpha_composite(rounded(shot, 22), (mx, my))
    inset = src.crop(PANEL).resize((iw, mh), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.4, percent=70, threshold=2))
    shadow(cv, (rx, my, rx + iw, my + mh), 22)
    cv.alpha_composite(rounded(inset, 22), (rx, my))
    d = ImageDraw.Draw(cv)
    # ekrandaki panel ve yakın görünüm aynı mavi çerçeveyle eşleşir
    px0, py0 = mx + round(PANEL[0] * scale), my + round(PANEL[1] * scale)
    px1, py1 = mx + round(PANEL[2] * scale), my + round(PANEL[3] * scale)
    d.rounded_rectangle((px0 - 4, py0 - 4, px1 + 4, py1 + 4), 10, outline=ACCENT, width=4)
    d.rounded_rectangle((rx - 3, my - 3, rx + iw + 3, my + mh + 3), 24, outline=ACCENT, width=4)

    # özellikler: iki sütun, sığmazsa yazı küçülür
    colw = (W - 2 * M) // 2
    size = 28
    while size > 20 and any(d.textlength(b, font=font(REG, size)) > colw - 60 for b in t["bullets"]):
        size -= 1
    f_b = font(REG, size)
    by0 = my + mh + 34
    for i, b in enumerate(t["bullets"]):
        x = M + (i % 2) * colw
        y = by0 + (i // 2) * (size + 18)
        d.ellipse((x + 2, y + size * 0.42, x + 14, y + size * 0.42 + 12), fill=ACCENT)
        d.text((x + 30, y), b, font=f_b, fill=INK)

    # teknoloji etiketleri ve alt bilgi
    f_chip = font(SEMI, 25)
    ty = by0 + 2 * (size + 18) + 22
    f_st = font(BOLD, 21)
    d.text((M, ty + 11), t["stack"].upper(), font=f_st, fill=MUTED)
    cx = M + d.textlength(t["stack"].upper(), font=f_st) + 26
    for c in CHIPS:
        tw = d.textlength(c, font=f_chip)
        d.rounded_rectangle((cx, ty, cx + tw + 36, ty + 46), 23, fill=CHIP_BG)
        d.text((cx + 18, ty + 7), c, font=f_chip, fill=ACCENT)
        cx += tw + 48
    f_f = font(REG, 23)
    fw = d.textlength(t["footer"], font=f_f)
    fy = ty + 11 if cx + 40 < W - M - fw else ty + 62
    d.text((W - M - fw, fy), t["footer"], font=f_f, fill=MUTED)
    assert fy + 30 < H, "alt bilgi tuvale sığmadı"

    out = os.path.join(OUT, f"ets2_bakim_cv_{lang}.png")
    cv.convert("RGB").save(out, optimize=True)
    small = cv.convert("RGB").resize((1200, 675), Image.LANCZOS)
    small.save(os.path.join(OUT, f"ets2_bakim_cv_{lang}_kucuk.jpg"), quality=92)
    print(out, cv.size, "madde yazısı", size, "px, alt", ty + 46)
