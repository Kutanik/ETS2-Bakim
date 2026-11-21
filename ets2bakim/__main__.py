import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_dir(demo):
    """Uygulamanın ana veri klasörü (Tek Oyunculu mod): data (demo: data_demo). Çok Oyunculu modun ayarları ve
    kayıtları yanındaki data_mp (data_demo_mp) klasöründedir; dil ve oyun modu seçimi buradan okunur."""
    return os.path.join(ROOT, "data_demo" if demo else "data")


def _early_language(d):
    """Pencere açılmadan çıkan iletiler (ör. uygulama zaten açık) seçili dilde olsun."""
    try:
        import json
        from . import i18n
        with open(os.path.join(d, "ayarlar.json"), encoding="utf-8") as fh:
            i18n.set_lang(json.load(fh).get("language", "tr"))
    except (OSError, ValueError):
        pass


def _log_without_console(demo):
    """pythonw ile (konsolsuz) açıldığında çıktılar ve hatalar data\\ets2bakim.log dosyasına yazılır."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    d = data_dir(demo)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "ets2bakim.log")
    try:
        if os.path.getsize(path) > 1_000_000:
            os.replace(path, path + ".1")
    except OSError:
        pass
    fh = open(path, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = fh


def main():
    p = argparse.ArgumentParser(prog="ets2bakim", description="ETS2 gerçekçi bakım ve motor simülatörü")
    p.add_argument("--demo", action="store_true", help="oyun olmadan sanal kamyonla çalıştır")
    p.add_argument("--hiz", type=float, default=1.0, help="demo modunda zaman hızlandırma çarpanı")
    p.add_argument("--port", type=int, default=8723)
    p.add_argument("--pencere-yok", action="store_true", help="arayüz penceresini açma (yalnızca oyun içi katman)")
    p.add_argument("--tarayici", action="store_true", help="arayüzü uygulama penceresi yerine Edge/Chrome'da aç")
    p.add_argument("--mod", choices=("auto", "tek", "cok"), default=None,
                   help="oyun modunu ayarlar (Ayarlar → Oyun modu ile aynı, kaydedilir): auto: TruckersMP / Konvoy "
                        "algılanınca çok oyunculu · tek: tek oyunculu (tam gerçekçilik) · cok: çok oyunculu (motor zorla "
                        "durdurulmaz)")
    a = p.parse_args()
    _log_without_console(a.demo)
    _early_language(data_dir(a.demo))

    from . import window
    from .app import App, open_app_window
    if not window.single_instance():
        # zaten açık: penceresi öne getirildi; pencere yoksa (tarayıcı modu) arayüzü tarayıcıda yeniden aç
        print("Simülatör zaten çalışıyor.")
        if not window.find_window() and not a.pencere_yok:
            files = [os.path.join(ROOT, d, "port.txt") for d in ("data", "data_demo", "data_mp", "data_demo_mp")]
            files = sorted((f for f in files if os.path.isfile(f)), key=os.path.getmtime, reverse=True)
            try:
                with open(files[0], encoding="utf-8") as fh:
                    open_app_window(f"http://127.0.0.1:{int(fh.read().strip())}/")
            except (IndexError, OSError, ValueError):
                pass
        return
    mode = False if a.pencere_yok else "browser" if a.tarayici else "app"
    App(demo=a.demo, speedup=a.hiz, port=a.port, open_window=mode, game_mode=a.mod, data_dir=data_dir(a.demo)).run()
    # Her şey kaydedildi: pencere motorunun (.NET/WebView2) yavaş kapanışını beklemeden çık.
    from .app import hard_exit
    hard_exit(0)


if __name__ == "__main__":
    main()
