"""Kapak resimleri için oyun içi katmanı büyük boyutta, gerçek oyun görüntüsü üzerinde çizdirir (test_host + katman DLL'i).

Her sahne için katman_besle.py veriyi test adlı paylaşılan belleğe yazar, test_host DLL'i yükleyip oyun ekran görüntüsünün
üzerine katmanı çizer ve bir kare kaydeder. Geçici ayar dosyası kullanılır: oyundaki gerçek katman ayarlarına
(overlay.ini) ve açık simülatöre dokunulmaz. Test penceresi ekran dışında, odak almadan açılır.
Çıktı: tanitim/_parcalar/<sahne>.png  ·  Kullanım: .venv\\Scripts\\python.exe tanitim\\katman_ciz.py [sahne ...]
"""
import os
import subprocess
import sys
import tempfile
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "_parcalar")
HOST = os.path.join(ROOT, "overlay", "build", "test_host.exe")
DLL = os.path.join(ROOT, "overlay", "build", "ets2bakim_overlay.dll")
BG = os.path.join(ROOT, "overlay", "build", "oyun_1080p.bmp")
PY = sys.executable

# ad: (sahne, görünüm 0 yalnız lambalar / 2 detaylı, sayfa, panel boyutu, lamba boyutu, STOP lambası var mı)
SHOTS = {
    "kritik": ("kritik", 2, 0, 1.6, 2.0, True),
    "kis": ("kis", 2, 0, 1.6, 2.0, True),
    "aku": ("aku", 2, 4, 1.6, 2.0, True),
    "cok": ("cok", 2, 0, 1.6, 2.0, False),
    "hepsi": ("hepsi", 0, 0, 1.0, 1.0, True),
}
FRAMES, CAPTURE_AT = 1300, 1150      # kırmızı lambaların ilk 6 sn'lik yanıp sönmesi bitsin (144 Hz'de ~8 sn)


def red_score(img):
    """Lamba şeridindeki parlak kırmızı miktarı: STOP 400 ms yanık / 400 ms sönük; en kırmızı kare seçilir."""
    w, h = img.size
    px = img.crop((0, int(h * 0.62), w, h)).convert("RGB").getdata()
    return sum(1 for r, g, b in px if r > 190 and g < 110 and b < 110)


def shot(name, scene, mode, page, zoom, lamp_zoom, attempts, lang="tr"):
    state, ovl = f"Local\\EBKKapak{name}State", f"Local\\EBKKapak{name}Ovl"
    feed = subprocess.Popen([PY, os.path.join(HERE, "katman_besle.py"), scene, "600", state, ovl, lang],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    tmp = tempfile.mkdtemp()
    ini = os.path.join(tmp, "overlay.ini")
    with open(ini, "w", encoding="utf-16") as fh:   # GetPrivateProfile* UTF-16 dosyayı doğru okur
        fh.write(f"[overlay]\nversion=5\nmode={mode}\npage={page}\ncorner=0\nzoom={zoom}\nlamp_zoom={lamp_zoom}\n")
    best, best_score = None, -1
    try:
        time.sleep(4)
        for i in range(attempts):
            bmp = os.path.join(tmp, f"{name}_{i}.bmp")
            env = dict(os.environ, EBK_STATE_NAME=state, EBK_OVL_NAME=ovl, EBK_PREFS_PATH=ini, EBK_FORCE_CORNER="0",
                       EBK_FORCE_MODE=str(mode), EBK_FORCE_PAGE=str(page), EBK_CAPTURE=bmp,
                       EBK_CAPTURE_AFTER=str(CAPTURE_AT),
                       EBK_TEST_HIDDEN="1")   # ekran dışında, odak almadan
            subprocess.run([HOST, DLL, str(FRAMES), BG], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=120)
            if not os.path.isfile(bmp):
                print(f"  {name}: görüntü alınamadı ({i + 1}. deneme)", flush=True)
                continue
            img = Image.open(bmp).convert("RGB")
            score = red_score(img)
            if score > best_score:
                best, best_score = img, score
        if best is None:
            raise SystemExit(f"{name}: görüntü yok")
        os.makedirs(OUT, exist_ok=True)
        best.save(os.path.join(OUT, name + ("" if lang == "tr" else "_" + lang) + ".png"))
        print(f"  {name}: tamam (kırmızı {best_score})", flush=True)
    finally:
        feed.kill()


def main():
    args = sys.argv[1:]
    langs = [a.split("=")[1] for a in args if a.startswith("--dil=")] or ["tr"]
    names = [a for a in args if not a.startswith("--")] or list(SHOTS)
    for lang in langs:
        for n in names:
            scene, mode, page, zoom, lamp_zoom, has_stop = SHOTS[n]
            shot(n, scene, mode, page, zoom, lamp_zoom, 3 if has_stop else 1, lang)


if __name__ == "__main__":
    main()
