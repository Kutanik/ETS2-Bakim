"""Video açılış görselleri (1920×1080): 1. kapağın düzeni; Türkçe, İngilizce ve Almanca ayrı ayrı.

Parçalar kapak_yazisiz.py ile aynı (o dilde çizilmiş katmandan panel, KRİTİK uyarı şeridi, ikaz lambaları; başlık ve
uygulama adı da oradaki çeviriler); ölçüler 1280×720 kapağın 1,5 katı. Büyütülen parçalar hafifçe keskinleştirilir.
Çıktı: tanitim/kapaklar/acilis_1080p[_en|_de].png ve Videolar\\ETS2_acilis_1080p[_en|_de].png
(CapCut projesi 1015 Türkçesini kullanır). Kullanım: .venv\\Scripts\\python.exe tanitim\\acilis_gorseli.py [tr en de]
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kapak_olustur as K  # noqa: E402
import kapak_yazisiz as KY  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402

W, H = 1920, 1080
S = 1.5                                   # 1280×720 kapağa göre
TOP = SIDE = round(34 * S)
VIDEOS = os.path.join(os.path.expanduser("~"), "Videos")
SHARP = ImageFilter.UnsharpMask(radius=1.2, percent=70, threshold=2)


def scaled(img, k):
    out = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
    return out.filter(SHARP) if k > 1.0 else out


def make(lang):
    game = Image.open(K.GAME_BG).convert("RGB")
    cap = Image.open(os.path.join(K.PARTS, "kritik.png" if lang == "tr" else f"kritik_{lang}.png")).convert("RGBA")
    b = KY.boxes(cap, game)
    panel = K.deghost(cap.crop(b["panel"]), game, b["panel"][:2])
    banner = cap.crop(b["banner"])
    strip = cap.crop(b["strip"])
    KY.fix_stop(strip, game, b["strip"][:2])

    base = K.cover(K.clean_bg("cam"), W, H, fx=0.6, fy=0.5)
    base = K.grade(base, 0.62, 1.12, 0.9)
    base.alpha_composite(K.gradient(W, H, [(0, (0, 0, 0, 0)), (0.42, (0, 0, 0, 40)), (1, (0, 0, 0, 160))]))
    base = K.vignette(base, 0.5)

    # sol üst: uygulama adı ve simgesi
    chip = K.pill(KY.NAME[lang], round(30 * S), (12, 12, 12, 215), pad=(round(18 * S), round(9 * S)))
    isz = round(54 * S)
    icon = K.app_icon("tek", isz)
    box = Image.new("RGBA", (chip.width + round(62 * S), max(chip.height, round(58 * S))), (0, 0, 0, 0))
    box.alpha_composite(chip, (round(52 * S), (box.height - chip.height) // 2))
    box.alpha_composite(icon, (0, (box.height - isz) // 2))
    K.paste(base, box, (round(26 * S), TOP - round(8 * S)), blur=15, alpha=0.6)
    chip_bottom = K.game_caption(base, round((26 + 52 + 18) * S), TOP - round(8 * S) + box.height + round(3 * S),
                                 round(20 * S))

    # sol: panel, çipin altından alt kenara kadar
    ptop = chip_bottom + round(22 * S)
    panel = scaled(panel, min(0.78 * S, (H - SIDE - ptop) / panel.height))
    K.paste(base, panel, (SIDE, ptop), blur=24)

    # üst: uyarı şeridi, panelin sağındaki alanda ortalı
    area_x0, area_x1 = SIDE + panel.width + round(30 * S), W - SIDE
    banner = scaled(banner, min(0.9 * S, (area_x1 - area_x0) / banner.width))
    K.paste(base, banner, (area_x0 + (area_x1 - area_x0 - banner.width) // 2, TOP), blur=24)
    banner_bottom = TOP + banner.height

    # alt: ikaz lambaları
    strip = scaled(strip, min(1.4 * S, (area_x1 - area_x0) / strip.width))
    strip_top = H - SIDE - strip.height
    K.glow(base, strip, (area_x0 + (area_x1 - area_x0 - strip.width) // 2, strip_top), K.CRIT, radius=60, alpha=0.45)

    # orta: başlık iki satır, aynı boyutta, şeritle lambalar arasında ortalı
    cx, max_w = (area_x0 + area_x1) // 2, area_x1 - area_x0 - round(40 * S)
    title = KY.TITLE[lang]
    size = min(K.fit(t, K.BLACK, max_w, round(96 * S), 0.07) for t in title)
    f = K.font(K.BLACK, size)
    asc, desc = f.getbbox("ÇİĞ", anchor="la")[1], f.getbbox("gy", anchor="la")[3]
    step = round(size * 1.02)
    y = (banner_bottom + strip_top - (step + desc - asc)) // 2 - asc
    for i, t in enumerate(title):
        K.text(base, (cx, y + i * step), t, size, K.WHITE, K.BLACK, stroke=max(4, round(size * 0.07)), anchor="ma",
               sh_blur=18)

    suffix = "" if lang == "tr" else "_" + lang
    out = os.path.join(K.OUT, f"acilis_1080p{suffix}.png")
    base.convert("RGB").save(out)
    dst = os.path.join(VIDEOS, f"ETS2_acilis_1080p{suffix}.png")
    try:
        shutil.copyfile(out, dst)
    except OSError:                      # CapCut açıkken dosyayı tutuyor olabilir
        dst = dst[:-4] + "_yeni.png"
        shutil.copyfile(out, dst)
    print(out, "|", dst, flush=True)
    return base


if __name__ == "__main__":
    langs = sys.argv[1:] or ["tr", "en", "de"]
    imgs = [make(lg) for lg in langs]
    sheet = Image.new("RGB", (960, 540 * len(imgs) + 10 * (len(imgs) - 1)), (20, 20, 20))
    for i, im in enumerate(imgs):
        sheet.paste(im.convert("RGB").resize((960, 540), Image.LANCZOS), (0, i * 550))
    sheet.save(os.path.join(K.OUT, "acilis_onizleme.jpg"), quality=85)
