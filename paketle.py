"""Dağıtım paketini oluşturur (indirilebilir zip; kullanıcının Python kurmasına gerek yok):

    dagitim\\ETS2-Maintenance-Simulator-<sürüm>.zip

Tek / Çok Oyunculu mod aynı uygulamanın içinde seçilir (Ayarlar → Oyun modu), bu yüzden tek paket vardır.
Zip: INSTALL.bat (kurulum), README.txt (EN / TR / DE) ve program\\ klasörü — bu bilgisayardaki Python 3.13'ün imzalı çalışma dosyaları,
derlenmiş standart kütüphane (python313.zip), uygulamanın kullandığı paketler (pywebview, pythonnet, truck-telemetry…),
uygulama, web arayüzü, ikaz sesleri, oyun eklentileri (RenCloud telemetri eklentisi + oyun içi katman) ve lisanslar.
Kurulum ve kaldırma ets2bakim/kurulum.py'dedir. Kullanım (proje klasöründe):

    .venv\\Scripts\\python.exe paketle.py [--telemetri <scs-telemetry.dll>]
"""
import argparse
import hashlib
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ets2bakim import __version__, appcontrol, guncelleme, sounds  # noqa: E402

OUT = os.path.join(HERE, "dagitim")
STAGE = os.path.join(OUT, "_hazirlik")
PY_TAG = f"python{sys.version_info.major}{sys.version_info.minor}"            # python313
RUNTIME_FILES = ("python.exe", "pythonw.exe", "python3.dll", f"{PY_TAG}.dll", "vcruntime140.dll", "vcruntime140_1.dll")
DLL_SKIP = {"_tkinter.pyd", "tcl86t.dll", "tk86t.dll", "_sqlite3.pyd", "sqlite3.dll", "_ctypes_test.pyd"}
LIB_SKIP_DIRS = {"test", "idlelib", "tkinter", "turtledemo", "ensurepip", "site-packages", "__pycache__", "sqlite3",
                 "venv", "pydoc_data", "lib2to3"}
LIB_SKIP_FILES = {"turtle.py"}
# uygulamanın çalışma zamanı paketleri (pip dağıtım adları); dosyaları RECORD listesinden kopyalanır
DISTS = ("pywebview", "proxy_tools", "bottle", "typing_extensions", "pythonnet", "clr_loader", "cffi", "pycparser",
         "truck_telemetry")
TELEMETRY_SHA256 = "1d03dbc7a975e72203c60a7b9998021ceb8800b836bf28a131279979ad386cd4"  # RenCloud scs-sdk-plugin V.1.12.1, 64 bit

SCS_SDK_PLUGIN_LICENSE = """scs-telemetry.dll — RenCloud/scs-sdk-plugin V.1.12.1 (https://github.com/RenCloud/scs-sdk-plugin)

The MIT License (MIT)

Copyright (c) 2014 Hans

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

PROXY_TOOLS_LICENSE = """proxy_tools 0.1.0 — Jonathan Tushman (http://github.com/jtushman/proxy_tools)

Paket kendi lisans metnini taşımıyor; paket bilgisinde (METADATA) "License: MIT" yazıyor. Tek modülünün başlığına
göre kod Werkzeug'dan alınmış (BSD). İki bildirim de aşağıda; telif satırları bu başlıktan alındı.
The package ships no license text of its own; its metadata (METADATA) declares "License: MIT". According to the header
of its only module, the code was extracted from Werkzeug (BSD). Both notices follow; the copyright lines are taken from
that header.

proxy_tools/__init__.py:
    Proxy. Extracted from Werkzeug

    :copyright: (c) 2013 by Armin Ronacher (adapted by Jonathan Tushman 2014).
    :license: BSD, see LICENSE for more details.


The MIT License (MIT)

Copyright (c) 2014 Jonathan Tushman

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


Werkzeug (https://github.com/pallets/werkzeug) — BSD 3-Clause License

Copyright (c) 2013 by Armin Ronacher

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of the copyright holder nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
# kendi lisans dosyasını taşımayan paketlerin bildirimleri (LISANSLAR\<ad>-LICENSE.txt olarak yazılır)
DIST_LICENSES = {"proxy_tools": PROXY_TOOLS_LICENSE}

BAT_INSTALL = """@echo off
chcp 65001 >nul
title ETS2 Maintenance Simulator - Setup / Kurulum
cd /d "%~dp0"
if not exist "program\\python\\python.exe" (
  echo Zip dosyasini once tamamen cikarin: sag tik - Tumunu ayikla. Sonra bu dosyayi yeniden calistirin.
  echo Extract the whole zip first: right-click - Extract All. Then run this file again.
  pause
  exit /b 1
)
"program\\python\\python.exe" -X utf8 -m ets2bakim.kurulum kur
"""
BAT_UNINSTALL = """@echo off
chcp 65001 >nul
"%~dp0python\\python.exe" -X utf8 -m ets2bakim.kurulum kaldir %*
"""
BAT_PLUGINS = """@echo off
chcp 65001 >nul
"%~dp0python\\python.exe" -X utf8 -m ets2bakim.kurulum eklenti %*
"""
BAT_DEMO = """@echo off
rem Oyun olmadan sanal kamyonla dener (zaman 4 kat hizli). Demo verisi data_demo klasorune yazilir.
start "" "%~dp0python\\pythonw.exe" -m ets2bakim --demo --hiz 4
"""
CUSTOM_SOUNDS = """Kendi ikaz sesleriniz / Your own warning sounds / Eigene Warntöne

Bu klasöre <marka>_<seviye>.wav koyun; varsa uygulamanın sesi yerine o çalınır.
Put <brand>_<level>.wav files here; they replace the app's sound.
Legen Sie hier <marke>_<stufe>.wav ab; sie ersetzen den Ton der App.

marka / brand / Marke: scania, volvo, mercedes, man, daf, renault, iveco, skoda, otobus, genel
seviye / level / Stufe: kritik, dikkat        (örnek / example / Beispiel: scania_kritik.wav)
"""

README_TEXT = """ETS2 Maintenance Simulator {v}
{line}
English · Türkçe · Deutsch

ENGLISH
-------
A realistic maintenance and fault simulator for Euro Truck Simulator 2 / American Truck Simulator: engine oil, coolant
and antifreeze, battery, tyres, DPF, AdBlue, gearbox and clutch; an in-game overlay, warning lamps and brand-style
warning sounds.

SINGLEPLAYER AND MULTIPLAYER
One app, two modes (Settings → Game mode):
- Automatic (default): switches to Multiplayer when TruckersMP or the game's Convoy mode is detected, and back to
  Singleplayer otherwise.
- Singleplayer: full realism. If the engine can no longer run (oil starvation, overheating, flat battery, freezing…) it
  is stopped in the game; ignition and screens stay on.
- Multiplayer (TruckersMP / Convoy): to keep traffic safe the engine is never force-stopped; values and warnings are
  shown. Optional: Settings → Watch mode → Full monitoring stops the engine only below 10 km/h. Drive modes
  (ECO / COMFORT / SPORT throttle curve) are off by default in this mode.
Each mode keeps its own settings and truck records; language and game mode are shared.

REQUIREMENTS
- Windows 10 / 11 (64-bit). No need to install Python: everything is in the package.
- Euro Truck Simulator 2 or American Truck Simulator on Steam (DirectX 11 for the in-game overlay).

INSTALLATION
1. Right-click the zip → "Extract All".
2. In the extracted folder, double-click INSTALL.bat and follow the prompts. No administrator rights needed.
   - If "Windows protected your PC" appears: "More info" → "Run anyway".
   - If Smart App Control blocks INSTALL.bat: right-click the zip → Properties → tick "Unblock" at the bottom → OK;
     extract the zip again and run INSTALL.bat.
3. Setup installs the program, puts the game plugins (telemetry + in-game overlay) into the game folder, adds desktop
   and Start menu shortcuts and finally opens the app.
4. When the game starts, confirm the "Advanced SDK features" message with OK. The app connects to the game by itself.
Installing over an older version (1.1 or later) keeps settings and records; the two old shortcuts become one.

USAGE
- In the game: F8 overlay (off → compact → detailed), Shift+F8 next page, Ctrl+F8 corner, Alt+F8 service menu (oil,
  antifreeze, battery, DPF, repairs), Ctrl+Alt+F8 move / resize the overlay with the mouse.
- Settings in the app window: game mode (Automatic / Singleplayer / Multiplayer), language (Türkçe / English /
  Deutsch), drive modes (ECO / COMFORT / SPORT), warnings and warning lamps (each can be switched on or off), wear
  rates, climate, currency…
- Settings → Value update rate: how often values refresh, separately for the app window and the in-game overlay, from
  real time (0 s, 20 times per second) to 5 s. Warnings, warning lamps and sounds never wait for the interval.
- Try it without the game: Start menu → ETS2 Maintenance → Demo.
- Installed the game later: Start menu → ETS2 Maintenance → Install plugins.
  (Start menu names follow the Windows language.)

UNINSTALL
Windows Settings → Apps → "ETS2 Maintenance Simulator" → Uninstall (or Start menu → ETS2 Maintenance → "Uninstall ETS2
Maintenance"). The program, game plugins, shortcuts, settings and maintenance records are removed; a telemetry plugin
that was in the game before the installation is put back.

KNOWN LIMITS
- With Smart App Control on, Windows blocks the unsigned in-game overlay in the game (setup then does not install it).
  The simulator, app window, warnings and sounds work without the overlay.
- The in-game overlay works with DirectX 11 only.

DISCLAIMER
This is an independent project, not affiliated with, endorsed or supported by SCS Software or TruckersMP. Euro Truck
Simulator 2, American Truck Simulator, TruckersMP and vehicle brand names are used only to describe compatibility and
what is simulated; they belong to their owners. Using it on TruckersMP is at your own risk: TruckersMP's official
position on in-game overlays and on drive modes that adjust the throttle could not be verified. Check their rules
yourself; if unsure, keep the overlay and the drive modes off.

Licenses: program\\LISANSLAR folder.


TÜRKÇE
------
ETS2 Bakım Simülatörü: Euro Truck Simulator 2 / American Truck Simulator için gerçekçi bakım ve arıza simülatörü: motor
yağı, soğutma suyu ve antifriz, akü, lastikler, DPF, AdBlue, şanzıman ve debriyaj; oyun içi gösterge (katman), ikaz
lambaları ve markaya göre ikaz sesleri.

TEK VE ÇOK OYUNCULU
Tek uygulama, iki mod (Ayarlar → Oyun modu):
- Otomatik (varsayılan): TruckersMP ya da oyunun Konvoy modu algılanınca Çok Oyunculu moda, tek oyunculuda yine Tek
  Oyunculu moda geçer.
- Tek Oyunculu: tam gerçekçilik. Motor çalışamaz hâle gelirse (yağsız kalma, hararet, akü bitmesi, donma…) oyunda
  motor durdurulur; kontak ve ekranlar açık kalır.
- Çok Oyunculu (TruckersMP / Konvoy): trafiği tehlikeye atmamak için motor zorla durdurulmaz; değerler ve uyarılar
  gösterilir. İsterseniz Ayarlar → İzleme modu → Tam izleme: motor yalnızca tır 10 km/h altına inince durdurulur.
  Sürüş modları (ECO / COMFORT / SPORT gaz eğrisi) bu modda varsayılan olarak kapalıdır.
İki modun ayarları ve tır bakım kayıtları ayrı tutulur; dil ve oyun modu ikisinde ortaktır.

GEREKSİNİMLER
- Windows 10 / 11 (64 bit). Python kurmanıza gerek yok: her şey pakette.
- Steam'de Euro Truck Simulator 2 ya da American Truck Simulator (oyun içi katman için DirectX 11).

KURULUM
1. Zip dosyasına sağ tıklayın → "Tümünü ayıkla".
2. Çıkan klasörde INSTALL.bat'a çift tıklayın ve yönergeleri izleyin. Yönetici izni gerekmez.
   - "Windows bilgisayarınızı korudu" çıkarsa: "Ek bilgi" → "Yine de çalıştır".
   - Akıllı Uygulama Denetimi INSTALL.bat'ı engellerse: zip dosyasına sağ tık → Özellikler → en alttaki
     "Engellemeyi kaldır" kutusunu işaretleyin → Tamam; zip'i yeniden ayıklayıp INSTALL.bat'ı çalıştırın.
3. Kurulum; programı kurar, oyun eklentilerini (telemetri + oyun içi katman) oyun klasörüne koyar, masaüstüne ve
   Başlat menüsüne kısayol ekler, sonunda uygulamayı açar.
4. Oyunu açınca çıkan "Advanced SDK features" uyarısını OK ile onaylayın. Uygulama oyuna kendiliğinden bağlanır.
Eski bir sürümün (1.1 ve sonrası) üzerine kurulursa ayarlar ve kayıtlar korunur, iki eski kısayolun yerine tek kısayol
gelir.

KULLANIM
- Oyunda: F8 katman (kapalı → kompakt → detaylı), Shift+F8 sonraki sayfa, Ctrl+F8 köşe, Alt+F8 servis menüsü
  (yağ, antifriz, akü, DPF, onarım), Ctrl+Alt+F8 katmanı fareyle taşı / boyutlandır.
- Uygulama penceresinde Ayarlar: oyun modu (Otomatik / Tek / Çok Oyunculu), dil (Türkçe / English / Deutsch), sürüş
  modları (ECO / COMFORT / SPORT), uyarılar ve ikaz lambaları (her biri ayrı ayrı açılıp kapatılır), azalma hızları,
  iklim, para birimi…
- Ayarlar → Değer güncelleme sıklığı: değerlerin ne sıklıkla yenileneceği, uygulama penceresi ve oyun içi katman için
  ayrı ayrı, gerçek zamanlıdan (0 sn, saniyede 20 kez) 5 saniyeye kadar. Uyarılar, ikaz lambaları ve sesler beklemez.
- Oyunsuz deneme: Başlat menüsü → ETS2 Bakım → Demo.
- Oyunu sonradan kurduysanız: Başlat menüsü → ETS2 Bakım → Eklentileri kur.
  (Başlat menüsündeki adlar Windows'un diline göre değişir.)

KALDIRMA
Windows Ayarlar → Uygulamalar → "ETS2 Bakım Simülatörü" → Kaldır (ya da Başlat menüsü → ETS2 Bakım → "ETS2 Bakım'ı
kaldır"). Program, oyun eklentileri, kısayollar, ayarlar ve bakım kayıtları otomatik silinir; kurulumdan önce oyunda
başka bir telemetri eklentisi varsa geri konur.

BİLİNEN SINIRLAR
- Akıllı Uygulama Denetimi açıksa Windows imzasız oyun içi katmanı oyunda engeller (kurulum bu durumda katmanı
  kurmaz). Simülatör, uygulama penceresi, uyarılar ve sesler katmansız çalışır.
- Oyun içi katman yalnızca DirectX 11 ile çalışır.

SORUMLULUK
Bu program bağımsız bir projedir; SCS Software ve TruckersMP ile bağlantılı değildir, onlar tarafından onaylanmamış ya
da desteklenmemiştir. Euro Truck Simulator 2, American Truck Simulator, TruckersMP ve araç markalarının adları yalnızca
uyumluluğu ve neyin simüle edildiğini tanımlamak için geçer; hakları sahiplerine aittir. TruckersMP'de kullanmak kendi
sorumluluğunuzdadır: TruckersMP'nin oyun içi katmanlar ve gaz pedalına müdahale eden sürüş modları hakkındaki resmi
tutumu doğrulanamadı. Kurallarını kendiniz kontrol edin; emin değilseniz katmanı ve sürüş modlarını kapalı tutun.

Lisanslar: program\\LISANSLAR klasörü.


DEUTSCH
-------
ETS2 Wartungssimulator: realistischer Wartungs- und Pannensimulator für Euro Truck Simulator 2 / American Truck
Simulator: Motoröl, Kühlmittel und Frostschutz, Batterie, Reifen, DPF, AdBlue, Getriebe und Kupplung; Spiel-Overlay,
Warnleuchten und markentypische Warntöne.

EINZEL- UND MEHRSPIELER
Eine App, zwei Modi (Einstellungen → Spielmodus):
- Automatisch (Standard): wechselt in den Mehrspielermodus, sobald TruckersMP oder der Konvoi-Modus des Spiels erkannt
  wird, sonst zurück in den Einzelspielermodus.
- Einzelspieler: volle Realistik. Kann der Motor nicht mehr laufen (Ölmangel, Überhitzung, leere Batterie, Frost…),
  wird er im Spiel abgestellt; Zündung und Anzeigen bleiben an.
- Mehrspieler (TruckersMP / Konvoi): zur Sicherheit im Verkehr wird der Motor nie zwangsweise gestoppt; Werte und
  Warnungen werden angezeigt. Optional: Einstellungen → Überwachungsmodus → Volle Überwachung stoppt ihn erst unter
  10 km/h. Die Fahrmodi (ECO / COMFORT / SPORT Gaskennlinie) sind in diesem Modus standardmäßig aus.
Jeder Modus hat eigene Einstellungen und Lkw-Daten; Sprache und Spielmodus sind gemeinsam.

VORAUSSETZUNGEN
- Windows 10 / 11 (64 Bit). Python muss nicht installiert werden: alles ist im Paket.
- Euro Truck Simulator 2 oder American Truck Simulator auf Steam (DirectX 11 für das Spiel-Overlay).

INSTALLATION
1. Rechtsklick auf das Zip → "Alle extrahieren".
2. Im entpackten Ordner INSTALL.bat doppelklicken und den Hinweisen folgen. Keine Administratorrechte nötig.
   - Erscheint "Der Computer wurde durch Windows geschützt": "Weitere Informationen" → "Trotzdem ausführen".
   - Blockiert die intelligente App-Steuerung INSTALL.bat: Rechtsklick auf das Zip → Eigenschaften → unten "Zulassen"
     ankreuzen → OK; das Zip erneut entpacken und INSTALL.bat starten.
3. Die Installation kopiert das Programm, legt die Spiel-Plugins (Telemetrie + Spiel-Overlay) in den Spielordner,
   erstellt Verknüpfungen auf dem Desktop und im Startmenü und öffnet am Ende die App.
4. Beim Spielstart die Meldung "Advanced SDK features" mit OK bestätigen. Die App verbindet sich selbst mit dem Spiel.
Bei Installation über eine ältere Version (ab 1.1) bleiben Einstellungen und Daten erhalten; aus den zwei alten
Verknüpfungen wird eine.

BEDIENUNG
- Im Spiel: F8 Overlay (aus → kompakt → ausführlich), Shift+F8 nächste Seite, Ctrl+F8 Ecke, Alt+F8 Servicemenü (Öl,
  Frostschutz, Batterie, DPF, Reparaturen), Ctrl+Alt+F8 Overlay mit der Maus verschieben / Größe ändern.
- Einstellungen im App-Fenster: Spielmodus (Automatisch / Einzelspieler / Mehrspieler), Sprache (Türkçe / English /
  Deutsch), Fahrmodi (ECO / COMFORT / SPORT), Warnungen und Warnleuchten (jede einzeln ein- und ausschaltbar),
  Verschleißraten, Klima, Währung…
- Einstellungen → Aktualisierungsrate der Werte: wie oft die Werte aktualisiert werden, getrennt für App-Fenster und
  Spiel-Overlay, von Echtzeit (0 s, 20-mal pro Sekunde) bis 5 s. Warnungen, Warnleuchten und Töne warten nie.
- Ohne Spiel testen: Startmenü → ETS2 Wartung → Demo.
- Spiel später installiert: Startmenü → ETS2 Wartung → Plugins installieren.
  (Die Namen im Startmenü folgen der Windows-Sprache.)

DEINSTALLATION
Windows-Einstellungen → Apps → "ETS2 Wartungssimulator" → Deinstallieren (oder Startmenü → ETS2 Wartung → "ETS2 Wartung
deinstallieren"). Programm, Spiel-Plugins, Verknüpfungen, Einstellungen und Wartungsdaten werden entfernt; ein vor der
Installation im Spiel vorhandenes Telemetrie-Plugin wird zurückgelegt.

BEKANNTE GRENZEN
- Bei eingeschalteter intelligenter App-Steuerung blockiert Windows das unsignierte Spiel-Overlay im Spiel (die
  Installation legt es dann nicht an). Simulator, App-Fenster, Warnungen und Töne funktionieren ohne Overlay.
- Das Spiel-Overlay funktioniert nur mit DirectX 11.

HAFTUNGSHINWEIS
Ein unabhängiges Projekt, nicht mit SCS Software oder TruckersMP verbunden und nicht von ihnen genehmigt oder
unterstützt. Euro Truck Simulator 2, American Truck Simulator, TruckersMP und Fahrzeugmarken werden nur genannt, um
Kompatibilität und das Simulierte zu beschreiben; die Rechte liegen bei ihren Inhabern. Die Nutzung auf TruckersMP
erfolgt auf eigenes Risiko: Die offizielle Haltung von TruckersMP zu Spiel-Overlays und zu Fahrmodi, die das Gaspedal
beeinflussen, konnte nicht geprüft werden. Prüfen Sie die Regeln selbst; im Zweifel Overlay und Fahrmodi ausgeschaltet
lassen.

Lizenzen: Ordner program\\LISANSLAR.
"""


def log(msg):
    print(msg, flush=True)


def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)


def build_runtime(prog):
    base = sys.base_prefix
    py = os.path.join(prog, "python")
    for f in RUNTIME_FILES:
        copy(os.path.join(base, f), os.path.join(py, f))
    n = 0
    for f in sorted(os.listdir(os.path.join(base, "DLLs"))):
        if f.endswith((".pyd", ".dll")) and f not in DLL_SKIP and not f.startswith("_test"):
            copy(os.path.join(base, "DLLs", f), os.path.join(py, "DLLs", f))
            n += 1
    # standart kütüphane: derlenmiş .pyc dosyaları tek zip'te (Python'un gömülebilir dağıtımı gibi)
    lib = os.path.join(base, "Lib")
    count, tmp = 0, tempfile.mkdtemp()
    with zipfile.ZipFile(os.path.join(py, f"{PY_TAG}.zip"), "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, dirs, files in os.walk(lib):
            rel_root = os.path.relpath(root, lib)
            dirs[:] = sorted(d for d in dirs if d not in LIB_SKIP_DIRS and not (rel_root == "." and d == "site-packages"))
            for f in sorted(files):
                if not f.endswith(".py") or f in LIB_SKIP_FILES:
                    continue
                rel = os.path.normpath(os.path.join(rel_root, f)).replace("\\", "/")
                cfile = os.path.join(tmp, "m.pyc")
                py_compile.compile(os.path.join(root, f), cfile=cfile, dfile=rel, doraise=True,
                                   invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
                z.write(cfile, rel[:-3] + ".pyc")
                count += 1
    shutil.rmtree(tmp, ignore_errors=True)
    with open(os.path.join(py, f"{PY_TAG}._pth"), "w", encoding="utf-8") as fh:
        fh.write(f"{PY_TAG}.zip\nDLLs\nLib\\site-packages\n..\n")
    copy(os.path.join(base, "LICENSE.txt"), os.path.join(prog, "LISANSLAR", "Python.txt"))
    log(f"  Python {sys.version.split()[0]}: {n} DLL/pyd, standart kütüphane {count} modül")


def _dist_info(site, name):
    norm = name.lower().replace("-", "_")
    for d in os.listdir(site):
        if d.endswith(".dist-info") and d.lower().split("-")[0].replace("-", "_") == norm:
            return d
    raise SystemExit(f"Paket bulunamadı: {name} (.venv'e kurulu olmalı)")


def build_site_packages(prog):
    import csv
    site = os.path.join(HERE, ".venv", "Lib", "site-packages")
    dst = os.path.join(prog, "python", "Lib", "site-packages")
    lic = os.path.join(prog, "LISANSLAR")
    total = 0
    for name in DISTS:
        info = _dist_info(site, name)
        with open(os.path.join(site, info, "RECORD"), encoding="utf-8", newline="") as fh:
            rows = [r[0] for r in csv.reader(fh) if r]
        has_license = False
        for rel in rows:
            if "__pycache__" in rel or rel.endswith((".pyc", ".pdb")) or rel.startswith(".."):
                continue
            src = os.path.join(site, rel)
            if os.path.isfile(src):
                copy(src, os.path.join(dst, rel))
                total += 1
            if rel.startswith(info + "/") and ("LICENSE" in rel.upper() or "AUTHORS" in rel.upper()):
                copy(src, os.path.join(lic, info.split("-")[0] + "-" + os.path.basename(rel) + ".txt"))
                has_license = has_license or "LICENSE" in rel.upper()
        if not has_license:                                             # lisans dosyası yoksa bildirim buradan yazılır
            if name not in DIST_LICENSES:
                raise SystemExit(f"{info}: lisans dosyası yok; bildirimini paketle.py'de DIST_LICENSES'e ekleyin")
            with open(os.path.join(lic, info.split("-")[0] + "-LICENSE.txt"), "w", encoding="utf-8") as fh:
                fh.write(DIST_LICENSES[name])
    log(f"  Paketler: {', '.join(DISTS)} ({total} dosya)")


def build_app(prog, telemetry):
    for sub, exts in (("ets2bakim", (".py", ".ico")), ("web", None)):
        src = os.path.join(HERE, sub)
        for f in sorted(os.listdir(src)):
            p = os.path.join(src, f)
            if os.path.isfile(p) and ".bak-" not in f and (exts is None or f.endswith(exts)):   # düzenleme yedekleri girmesin
                copy(p, os.path.join(prog, sub, f))
    # ikaz sesleri önceden üretilir (ilk uyarıda gecikme olmasın) + kendi sesleriniz için klasör
    for brand in sounds.BRANDS:
        for level, name in sounds.LEVEL_NAMES.items():
            p = os.path.join(prog, "sesler", f"v{sounds.VERSION}", f"{brand}_{name}.wav")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(sounds.synth(brand, level))
    os.makedirs(os.path.join(prog, "sesler", "ozel"), exist_ok=True)
    with open(os.path.join(prog, "sesler", "ozel", "README.txt"), "w", encoding="utf-8") as fh:
        fh.write(CUSTOM_SOUNDS)
    # oyun eklentileri
    ovl = os.path.join(HERE, "overlay", "build", appcontrol.DLL_NAME)
    if not os.path.isfile(ovl):
        raise SystemExit(f"Oyun içi katman derlenmemiş: {ovl} (overlay\\build.ps1)")
    copy(ovl, os.path.join(prog, "eklenti", appcontrol.DLL_NAME))
    if not telemetry or not os.path.isfile(telemetry):
        raise SystemExit("scs-telemetry.dll bulunamadı: --telemetri ile yolunu verin (RenCloud scs-sdk-plugin V.1.12.1, 64 bit)")
    if sha256(telemetry) != TELEMETRY_SHA256:
        log(f"  UYARI: {telemetry} beklenen V.1.12.1 dosyası değil (özet farklı); yine de pakete konuyor")
    copy(telemetry, os.path.join(prog, "eklenti", "scs-telemetry.dll"))
    with open(os.path.join(prog, "LISANSLAR", "scs-sdk-plugin.txt"), "w", encoding="utf-8") as fh:
        fh.write(SCS_SDK_PLUGIN_LICENSE)
    with open(os.path.join(prog, "LISANSLAR", "README.txt"), "w", encoding="utf-8") as fh:
        fh.write("Pakette kullanılan bileşenler ve lisansları / Third-party components and licenses\n\n"
                 "- Python (Python Software Foundation): Python.txt (PSF lisansı; içindeki OpenSSL, libffi, bzip2, xz,\n"
                 "  mpdecimal vb. bildirimleri dahil)\n"
                 "- pywebview (BSD-3-Clause), pythonnet (MIT), clr_loader (MIT), cffi (MIT-0), pycparser (BSD-3-Clause),\n"
                 "  bottle (MIT), proxy_tools (MIT; içindeki Werkzeug kodu BSD-3-Clause), typing_extensions (PSF-2.0),\n"
                 "  truck-telemetry (MIT): *-LICENSE*.txt\n"
                 "- Microsoft Edge WebView2 SDK (Microsoft Corporation; Microsoft.Web.WebView2.*.dll, pywebview ile\n"
                 "  birlikte dağıtılır): https://www.nuget.org/packages/Microsoft.Web.WebView2\n"
                 "- scs-telemetry.dll (RenCloud/scs-sdk-plugin, MIT): scs-sdk-plugin.txt\n")
    for name, text in (("KALDIR.bat", BAT_UNINSTALL), ("EKLENTI_KUR.bat", BAT_PLUGINS), ("DEMO.bat", BAT_DEMO)):
        with open(os.path.join(prog, name), "w", encoding="ascii", newline="\r\n") as fh:
            fh.write(text)
    with open(os.path.join(prog, "paket.json"), "w", encoding="utf-8") as fh:
        json.dump({"version": __version__, "built": time.strftime("%Y-%m-%d")}, fh, indent=1)


def readme():
    head = f"ETS2 Maintenance Simulator {__version__}"
    return README_TEXT.format(v=__version__, line="=" * len(head))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def smoke_test(prog):
    """Paketin kendi Python'u uygulamanın tüm modüllerini yükleyebiliyor mu (pencere açmadan)."""
    code = ("import sys, ets2bakim.app, ets2bakim.kurulum, webview, truck_telemetry, clr_loader, pythonnet, ssl, winsound;"
            "from webview.platforms import winforms; print(sys.version.split()[0], sys.prefix)")
    r = subprocess.run([os.path.join(prog, "python", "python.exe"), "-c", code], capture_output=True, text=True,
                       cwd=tempfile.gettempdir(), timeout=120)
    if r.returncode != 0:
        raise SystemExit("Paket denemesi başarısız:\n" + r.stdout + r.stderr)
    log(f"  Deneme: paketin Python'u modülleri yükledi ({r.stdout.strip()})")


# uygulama içi güncellemede "Yeni sürüm hazır" satırında gösterilir (surum.json → notlar)
RELEASE_NOTES = {
    "tr": "SPORT modunda gaz verip bırakırken oyunun takılması düzeltildi; değer güncelleme sıklığı ayarı (0 sn gerçek "
          "zamanlı dahil) ve daha az işlemci kullanan uygulama",
    "en": "Fixed the game stuttering when pressing and releasing the throttle in SPORT; new value update rate setting "
          "(including 0 s real time) and a lighter app",
    "de": "Behoben: Ruckeln des Spiels beim Gasgeben und Loslassen im SPORT-Modus; neue Einstellung der "
          "Aktualisierungsrate (inkl. 0 s Echtzeit) und eine sparsamere App",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--telemetri", help="scs-telemetry.dll (varsayılan: kurulu oyundaki kopya)")
    a = ap.parse_args()
    telemetry = a.telemetri
    if not telemetry:
        for b in appcontrol.steam_game_dirs():
            p = os.path.join(b, "plugins", "scs-telemetry.dll")
            if os.path.isfile(p) and sha256(p) == TELEMETRY_SHA256:
                telemetry = p
                break
    log(f"ETS2 Bakım {__version__} paketleniyor…")
    shutil.rmtree(STAGE, ignore_errors=True)
    prog = os.path.join(STAGE, "program")
    os.makedirs(prog)
    build_runtime(prog)
    build_site_packages(prog)
    build_app(prog, telemetry)
    smoke_test(prog)
    for d, _, files in os.walk(prog):                                   # deneme sırasında oluşan önbellekler pakete girmesin
        if os.path.basename(d) == "__pycache__":
            shutil.rmtree(d, ignore_errors=True)
    name = f"ETS2-Maintenance-Simulator-{__version__}"
    zpath = os.path.join(OUT, name + ".zip")
    text = "\ufeff" + readme().replace("\n", "\r\n")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr(f"{name}/INSTALL.bat", BAT_INSTALL.replace("\n", "\r\n"))
        z.writestr(f"{name}/README.txt", text)
        z.writestr(f"{name}/program/README.txt", text)
        for root, dirs, files in os.walk(prog):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for f in sorted(files):
                full = os.path.join(root, f)
                z.write(full, f"{name}/program/" + os.path.relpath(full, prog).replace("\\", "/"))
    digest = sha256(zpath)
    log(f"  {os.path.relpath(zpath, HERE)}: {os.path.getsize(zpath) / 1e6:.1f} MB · SHA-256 {digest}")
    # uygulama içi güncelleme: Drive'da önce zip, sonra bu dosya "Sürümleri yönet"le değiştirilir (bağlantılar aynı kalır)
    info = {"surum": __version__, "zip": guncelleme.DRIVE_DOWNLOAD.format(id=guncelleme.ZIP_ID), "sha256": digest,
            "boyut": os.path.getsize(zpath), "notlar": RELEASE_NOTES}
    with open(os.path.join(OUT, "surum.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, ensure_ascii=False, indent=1)
    log(f"  {os.path.relpath(os.path.join(OUT, 'surum.json'), HERE)}: Drive'daki surum.json'un yeni sürümü")
    shutil.rmtree(STAGE, ignore_errors=True)                           # yalnızca zip kalsın
    log("Tamam.")


if __name__ == "__main__":
    main()
