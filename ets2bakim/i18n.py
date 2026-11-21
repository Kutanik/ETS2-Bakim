"""Çok dil desteği (tr / en / de).

Türkçe şablonlar anahtar (msgid) olarak kullanılır; İngilizce ve Almanca karşılıkları TRANS sözlüğündedir.
  T("Yağ ömrü %{life:.0f}.", life=42)      -> dile göre metin (sayılar yerel biçimde)
  M("...", **args)                          -> {"m": msgid, "a": args}  (sonradan farklı dilde gösterilebilir)
  render(x)                                 -> M sözlüğü ya da düz msgid'i metne çevirir
Parametre adı "_t" ile bitiyorsa değeri de çevrilir; değeri M sözlüğü olan parametreler iç içe çevrilir.
"""
import re
import string

LANGS = ("tr", "en", "de")
LANG = "tr"

DAYS = {
    "tr": ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "de": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
}


def set_lang(lang):
    global LANG
    LANG = lang if lang in LANGS else "tr"


def _localize(s):
    if LANG in ("tr", "de"):
        return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return s


def N(v, d=0, group=True):
    """Dile göre sayı: tr/de 1.234,5 — en 1,234.5"""
    if v is None:
        return "—"
    s = f"{v:,.{d}f}" if group else f"{v:.{d}f}"
    s = _localize(s)
    if s.lstrip("-").strip("0.,") == "":
        s = s.lstrip("-")
    return s


class _Formatter(string.Formatter):
    def format_field(self, value, spec):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return format(value, spec)
        if not spec:
            return str(value)
        return _localize(format(value, spec))


_fmt = _Formatter()


def _resolve(kw):
    out = {}
    for k, v in kw.items():
        if isinstance(v, dict) and "m" in v:
            out[k] = render(v)
        elif k.endswith("_t") and isinstance(v, str):
            out[k] = T(v)
        elif k in ("src", "dst") and isinstance(v, str):
            out[k] = city(v)          # oyunun verdiği şehir adı (oyun dilinde) seçili dilde
        else:
            out[k] = v
    return out


def T(msgid, **kw):
    tmpl = msgid
    if LANG != "tr":
        tr = TRANS.get(msgid)
        if tr:
            tmpl = tr[0 if LANG == "en" else 1]
    if not kw:
        return tmpl if "{" not in tmpl else tmpl.replace("{{", "{").replace("}}", "}")
    try:
        return _fmt.format(tmpl, **_resolve(kw))
    except (KeyError, ValueError, IndexError):
        try:
            return _fmt.format(msgid, **_resolve(kw))
        except Exception:
            return msgid


def M(msgid, **kw):
    return {"m": msgid, "a": kw}


def render(x):
    if isinstance(x, dict) and "m" in x:
        return T(x["m"], **(x.get("a") or {}))
    if isinstance(x, str):
        return T(x)
    return "" if x is None else str(x)


# ---------------------------------------------------------------- eski (düz Türkçe metin) kayıtları
# Çok dil desteğinden önceki olay kayıtları şablon yerine Türkçe metin olarak saklanmıştı; dil değişince Türkçe kalırdı.
# Metin bilinen bir Türkçe şablonla eşleşirse şablon + parametrelere çevrilir (sayılar yeniden yerel biçimlenir).
_PATTERNS = None


def _patterns():
    global _PATTERNS
    if _PATTERNS is None:
        pats = []
        for msgid in TRANS:
            try:
                parts = list(string.Formatter().parse(msgid))
            except ValueError:
                continue
            literal = "".join(p[0] for p in parts)
            fields = [p for p in parts if p[1] is not None]
            if len(literal.strip()) < 8 or any(not f[1].isidentifier() for f in fields):
                continue   # neredeyse yalnızca alandan oluşan şablon (ör. "{msg}") her metne uyar
            rx, names, seen = "", [], set()
            for lit, field, spec, _conv in parts:
                rx += re.escape(lit)
                if field is None:
                    continue
                if field in seen:
                    rx += f"(?P={field})"
                else:
                    rx += f"(?P<{field}>.+?)"
                    seen.add(field)
                    names.append((field, spec or ""))
            pats.append((len(literal), re.compile("^" + rx + "$", re.S), names, msgid))
        pats.sort(key=lambda p: -p[0])   # en çok sabit metni olan şablon önce (daha kesin eşleşme)
        _PATTERNS = pats
    return _PATTERNS


def _number(s, spec):
    """Türkçe biçimli sayı ("71.175", "25,1") -> sayı; sayı biçimli olmayan alan metin kalır."""
    if not spec or spec[-1] not in "fde%g":
        return s
    try:
        v = float(s.strip().replace(".", "").replace(",", "."))
    except ValueError:
        return s
    return int(v) if spec.endswith("d") else v


def match_legacy(text, _depth=0):
    """Düz Türkçe metni bilinen şablona çevirir: {"m": şablon, "a": parametreler} ya da eşleşme yoksa None."""
    if not isinstance(text, str) or not text:
        return None
    if text in TRANS:
        return M(text)
    for _, rx, names, msgid in _patterns():
        m = rx.match(text)
        if not m:
            continue
        args = {}
        for field, spec in names:
            v = m.group(field)
            num = _number(v, spec)
            if num is not v:
                args[field] = num
            elif field.endswith("_t") or _depth >= 1:
                args[field] = v
            else:
                args[field] = match_legacy(v, _depth + 1) or v   # iç ileti (ör. marş başarısızlık nedeni)
        return {"m": msgid, "a": args}
    return None


def upgrade_log_entry(e):
    """Eski düz metin olay kaydını şablonlu biçime çevirir (eşleşmezse olduğu gibi döner)."""
    if not isinstance(e, dict) or "m" in e or not e.get("text"):
        return e
    mm = match_legacy(e["text"])
    if not mm:
        return e
    out = {k: v for k, v in e.items() if k != "text"}
    out.update(m=mm["m"], a=mm["a"])
    return out


def day(i):
    return DAYS[LANG][i % 7]


# Şehir adları (Türkçe adı farklı olanlar): tr -> (en, de)
CITY = {
    "İstanbul": ("Istanbul", "Istanbul"), "Sofya": ("Sofia", "Sofia"), "Burgaz": ("Burgas", "Burgas"),
    "Bükreş": ("Bucharest", "Bukarest"), "Köstence": ("Constanța", "Constanța"), "Kluj": ("Cluj-Napoca", "Klausenburg"),
    "Temeşvar": ("Timișoara", "Temeswar"), "Belgrad": ("Belgrade", "Belgrad"), "Selanik": ("Thessaloniki", "Thessaloniki"),
    "Atina": ("Athens", "Athen"), "Üsküp": ("Skopje", "Skopje"), "Budapeşte": ("Budapest", "Budapest"),
    "Viyana": ("Vienna", "Wien"), "Koşice": ("Košice", "Kaschau"), "Prag": ("Prague", "Prag"),
    "Varşova": ("Warsaw", "Warschau"), "Krakov": ("Kraków", "Krakau"), "Poznan": ("Poznań", "Posen"),
    "Gdansk": ("Gdańsk", "Danzig"), "Wroclaw": ("Wrocław", "Breslau"), "Lodz": ("Łódź", "Lodz"),
    "Münih": ("Munich", "München"), "Köln": ("Cologne", "Köln"), "Nürnberg": ("Nuremberg", "Nürnberg"),
    "Hannover": ("Hanover", "Hannover"), "Brüksel": ("Brussels", "Brüssel"), "Anvers": ("Antwerp", "Antwerpen"),
    "Lüksemburg": ("Luxembourg", "Luxemburg"), "Marsilya": ("Marseille", "Marseille"), "Bordo": ("Bordeaux", "Bordeaux"),
    "Strazburg": ("Strasbourg", "Straßburg"), "Barselona": ("Barcelona", "Barcelona"), "Valensiya": ("Valencia", "Valencia"),
    "Lizbon": ("Lisbon", "Lissabon"), "Milano": ("Milan", "Mailand"), "Torino": ("Turin", "Turin"),
    "Venedik": ("Venice", "Venedig"), "Roma": ("Rome", "Rom"), "Napoli": ("Naples", "Neapel"),
    "Cenevre": ("Geneva", "Genf"), "Zürih": ("Zurich", "Zürich"), "Londra": ("London", "London"),
    "Kopenhag": ("Copenhagen", "Kopenhagen"), "Göteborg": ("Gothenburg", "Göteborg"), "Plovdiv": ("Plovdiv", "Plowdiw"),
}


def city(name):
    if LANG == "tr" or name not in CITY:
        return name
    return CITY[name][0 if LANG == "en" else 1]


# msgid (Türkçe) -> (English, Deutsch)
TRANS = {
    # ---------------------------------------------------------------- olaylar / kamyon
    "Yeni kamyon: tüm sıvılar ve akü yeni.": ("New truck: all fluids and batteries are new.", "Neuer Lkw: alle Flüssigkeiten und Batterien sind neu."),
    "Kamyon ilk kez görüldü ({odo:,.0f} km). Bakım geçmişi bilinmiyor: yağ analizi ve genel kontrol önerilir.": (
        "Truck seen for the first time ({odo:,.0f} km). Service history unknown: an oil analysis and general check are recommended.",
        "Lkw zum ersten Mal erkannt ({odo:,.0f} km). Wartungshistorie unbekannt: Ölanalyse und Durchsicht empfohlen."),
    "Elektrikli kamyon algılandı: bu simülatör dizel motorlar içindir, değerler anlamsız olabilir.": (
        "Electric truck detected: this simulator is built for diesel engines, values may be meaningless.",
        "Elektro-Lkw erkannt: dieser Simulator ist für Dieselmotoren gedacht, Werte können sinnlos sein."),
    "Model algılandı: {model}. Varsayılan motor {engine} seçildi; tam gazda sürüşten gerçek motor algılanacak.": (
        "Model detected: {model}. Default engine {engine} selected; the real engine will be detected from full-throttle driving.",
        "Modell erkannt: {model}. Standardmotor {engine} gewählt; der echte Motor wird bei Vollgasfahrt erkannt."),
    "Kamyon modeli tanınmadı ({truck}). Ayarlar'dan motoru girin.": (
        "Truck model not recognised ({truck}). Enter the engine in Settings.",
        "Lkw-Modell nicht erkannt ({truck}). Motor in den Einstellungen eintragen."),
    "Motor sürüşten algılandı: {engine} ({hp} hp, ölçülen tork ≈{nm:,.0f} Nm). Önceki seçim: {old}.": (
        "Engine detected from driving: {engine} ({hp} hp, measured torque ≈{nm:,.0f} Nm). Previous choice: {old}.",
        "Motor aus der Fahrt erkannt: {engine} ({hp} PS, gemessenes Drehmoment ≈{nm:,.0f} Nm). Bisher: {old}."),
    "Marş başarısız: {reason}.": ("Start failed: {reason}.", "Start fehlgeschlagen: {reason}."),
    "Takviye ile marş": ("Jump start", "Starthilfe-Start"),
    "Takviye ile marş — yağ çok koyu, motor yine de dönmedi": ("Jump start — oil too thick, engine still would not turn", "Starthilfe — Öl zu zäh, Motor dreht trotzdem nicht"),
    "Akü donmuş/hasarlı — marş yok": ("Battery frozen/damaged — no crank", "Batterie gefroren/beschädigt — kein Start"),
    "Yağ çok koyu ({visc:,.0f} cSt): marş motoru motoru çeviremiyor": ("Oil too thick ({visc:,.0f} cSt): the starter cannot turn the engine", "Öl zu zäh ({visc:,.0f} cSt): der Anlasser kann den Motor nicht drehen"),
    "Akü yetersiz: marşta voltaj {v:.1f} V'a düştü": ("Battery too weak: voltage dropped to {v:.1f} V while cranking", "Batterie zu schwach: Spannung fiel beim Anlassen auf {v:.1f} V"),
    "Zorlu marş ({v:.1f} V) — akü zayıf": ("Hard start ({v:.1f} V) — battery weak", "Schwerer Start ({v:.1f} V) — Batterie schwach"),
    "Soğuk marş ({t:.0f} °C yağ, {visc:,.0f} cSt): ilk dakikalarda yüklenmeyin.": (
        "Cold start ({t:.0f} °C oil, {visc:,.0f} cSt): avoid high load for the first minutes.",
        "Kaltstart ({t:.0f} °C Öl, {visc:,.0f} cSt): in den ersten Minuten nicht stark belasten."),
    "Akü şarj cihazı söküldü (motor çalıştırıldı / hareket edildi).": ("Battery charger removed (engine started / truck moved).", "Ladegerät entfernt (Motor gestartet / Lkw bewegt)."),
    "Akü dondu ve hasar gördü (akü {t:.0f} °C, şarj %{soc:.0f}).": ("Battery froze and was damaged (battery {t:.0f} °C, charge {soc:.0f}%).", "Batterie ist eingefroren und beschädigt (Batterie {t:.0f} °C, Ladung {soc:.0f} %)."),
    "Akü voltajı {v:.1f} V'a düştü: ECU kapandı, motor stop etti.": ("Battery voltage dropped to {v:.1f} V: ECU shut down, engine stalled.", "Batteriespannung auf {v:.1f} V gefallen: Steuergerät aus, Motor abgewürgt."),
    "Yağ basıncı yok: krank yatakları sardı, MOTOR KİLİTLENDİ.": ("No oil pressure: crank bearings seized, ENGINE SEIZED.", "Kein Öldruck: Kurbelwellenlager gefressen, MOTOR FESTGEGANGEN."),
    "Aşırı hararet: silindir kapak contası yandı.": ("Severe overheating: cylinder head gasket blown.", "Starke Überhitzung: Zylinderkopfdichtung durchgebrannt."),
    "Aşırı hararet: pistonlar sardı, MOTOR KİLİTLENDİ.": ("Severe overheating: pistons seized, ENGINE SEIZED.", "Starke Überhitzung: Kolben gefressen, MOTOR FESTGEGANGEN."),
    "Motor bloğundaki su dondu ve bloğu çatlattı!": ("Water in the engine block froze and cracked the block!", "Wasser im Motorblock ist gefroren und hat den Block gesprengt!"),
    "Radyatördeki su dondu ve radyatörü çatlattı!": ("Water in the radiator froze and cracked the radiator!", "Wasser im Kühler ist gefroren und hat den Kühler gesprengt!"),
    "ARIZA: {name_t} — {desc_t}": ("FAULT: {name_t} — {desc_t}", "DEFEKT: {name_t} — {desc_t}"),
    "Gece akü dondu ve hasar gördü (şarj %{soc:.0f}).": ("The battery froze overnight and was damaged (charge {soc:.0f}%).", "Die Batterie ist über Nacht eingefroren und beschädigt (Ladung {soc:.0f} %)."),
    "Gece motor bloğundaki su dondu ve bloğu çatlattı!": ("Overnight the water in the engine block froze and cracked it!", "Über Nacht ist das Wasser im Motorblock gefroren und hat ihn gesprengt!"),
    "Gece radyatördeki su dondu ve radyatörü çatlattı!": ("Overnight the water in the radiator froze and cracked it!", "Über Nacht ist das Wasser im Kühler gefroren und hat ihn gesprengt!"),
    "Otomatik bakım: yağ + filtre değişti, {l:.1f} L antifriz eklendi.": ("Automatic service: oil + filter changed, {l:.1f} L coolant added.", "Automatische Wartung: Öl + Filter gewechselt, {l:.1f} L Kühlmittel nachgefüllt."),
    "Bu işlem için kamyon durmuş ve motor kapalı olmalı.": ("The truck must be stopped with the engine off for this.", "Dafür muss der Lkw stehen und der Motor aus sein."),
    "Ölçüm için kamyonu durdurun.": ("Stop the truck to measure.", "Zum Messen den Lkw anhalten."),
    "Bilinmeyen yağ tipi.": ("Unknown oil type.", "Unbekannte Ölsorte."),
    "Yağ değişti: {grade_t}, {l:.0f} L": ("Oil changed: {grade_t}, {l:.0f} L", "Öl gewechselt: {grade_t}, {l:.0f} L"),
    "Yağ değişti: {grade_t}, {l:.0f} L + yağ filtresi": ("Oil changed: {grade_t}, {l:.0f} L + oil filter", "Öl gewechselt: {grade_t}, {l:.0f} L + Ölfilter"),
    "Yağ değiştirildi.": ("Oil changed.", "Öl gewechselt."),
    "{l:.1f} L {grade_t} eklendi (seviye %{lvl:.0f}).": ("{l:.1f} L {grade_t} added (level {lvl:.0f}%).", "{l:.1f} L {grade_t} nachgefüllt (Stand {lvl:.0f} %)."),
    "{l:.1f} L {grade_t} eklendi (seviye %{lvl:.0f}). Dikkat: yağ fazla! Köpüklenme ve yağ yakma riski.": (
        "{l:.1f} L {grade_t} added (level {lvl:.0f}%). Warning: overfilled! Risk of foaming and oil burning.",
        "{l:.1f} L {grade_t} nachgefüllt (Stand {lvl:.0f} %). Achtung: überfüllt! Gefahr von Schaumbildung und Ölverbrennung."),
    "Yağ filtresi değişti.": ("Oil filter changed.", "Ölfilter gewechselt."),
    "Filtre değişti.": ("Filter changed.", "Filter gewechselt."),
    "Yağ numunesi alındı, laboratuvar raporu hazır.": ("Oil sample taken, lab report ready.", "Ölprobe entnommen, Laborbericht liegt vor."),
    "Yağ analizi raporu hazır.": ("Oil analysis report ready.", "Ölanalyse-Bericht liegt vor."),
    "Soğutma sıvısı değişti: {type_t}, %{c:.0f} antifriz (donma {f:.0f} °C)": ("Coolant changed: {type_t}, {c:.0f}% antifreeze (freezes at {f:.0f} °C)", "Kühlmittel gewechselt: {type_t}, {c:.0f} % Frostschutz (gefriert bei {f:.0f} °C)"),
    "Soğutma sıvısı değişti.": ("Coolant changed.", "Kühlmittel gewechselt."),
    "Bilinmeyen sıvı.": ("Unknown fluid.", "Unbekannte Flüssigkeit."),
    "Motor sıcakken radyatör kapağını açmayın! (sıvı > 60 °C, basınç altında)": ("Do not open the radiator cap while the engine is hot! (coolant > 60 °C, under pressure)", "Kühlerdeckel nicht bei heißem Motor öffnen! (Kühlmittel > 60 °C, unter Druck)"),
    "{l:.1f} L {fluid_t} eklendi. Antifriz %{g:.0f}, donma noktası {f:.0f} °C.": ("{l:.1f} L {fluid_t} added. Antifreeze {g:.0f}%, freezing point {f:.0f} °C.", "{l:.1f} L {fluid_t} nachgefüllt. Frostschutz {g:.0f} %, Gefrierpunkt {f:.0f} °C."),
    "Antifriz ölçümü: %{g:.0f}, donma {f:.0f} °C, pH {ph:.1f}.": ("Coolant test: {g:.0f}%, freezes at {f:.0f} °C, pH {ph:.1f}.", "Kühlmitteltest: {g:.0f} %, Gefrierpunkt {f:.0f} °C, pH {ph:.1f}."),
    "Refraktometre ölçümü yapıldı.": ("Refractometer reading taken.", "Refraktometer-Messung durchgeführt."),
    "Aküler değişti.": ("Batteries replaced.", "Batterien getauscht."),
    "Şarj cihazı için motor kapalı ve kamyon duruyor olmalı.": ("Engine must be off and the truck stopped to connect a charger.", "Für das Ladegerät muss der Motor aus sein und der Lkw stehen."),
    "Akü şarj cihazı söküldü.": ("Battery charger removed.", "Ladegerät entfernt."),
    "Tamam.": ("Done.", "Erledigt."),
    "Motor zaten çalışıyor.": ("The engine is already running.", "Der Motor läuft bereits."),
    "Takviye kablosu bağlandı: bir sonraki marş dış aküden yapılacak.": ("Jumper cables connected: the next start will use the external battery.", "Starthilfekabel angeschlossen: der nächste Start erfolgt mit Fremdbatterie."),
    "Takviye bağlandı — şimdi oyunda motoru çalıştırın.": ("Jump start connected — now start the engine in the game.", "Starthilfe angeschlossen — jetzt im Spiel den Motor starten."),
    "Akü testi: şarj %{soc:.0f}, sağlık %{soh:.0f}, CCA {cca:.0f} A.": ("Battery test: charge {soc:.0f}%, health {soh:.0f}%, CCA {cca:.0f} A.", "Batterietest: Ladung {soc:.0f} %, Zustand {soh:.0f} %, Kaltstartstrom {cca:.0f} A."),
    "Akü testi yapıldı.": ("Battery test done.", "Batterietest durchgeführt."),
    "Serviste zorunlu DPF rejenerasyonu yapıldı.": ("Forced DPF regeneration performed at the workshop.", "Erzwungene DPF-Regeneration in der Werkstatt durchgeführt."),
    "DPF rejenerasyonu tamam.": ("DPF regeneration complete.", "DPF-Regeneration abgeschlossen."),
    "DPF söküldü, kül temizliği yapıldı.": ("DPF removed and cleaned of ash.", "DPF ausgebaut und von Asche gereinigt."),
    "DPF temizlendi.": ("DPF cleaned.", "DPF gereinigt."),
    "Bu arıza aktif değil.": ("This fault is not active.", "Dieser Defekt ist nicht aktiv."),
    "Donmuş akü onarılamaz: aküleri değiştirin.": ("A frozen battery cannot be repaired: replace the batteries.", "Eine gefrorene Batterie ist nicht reparierbar: Batterien tauschen."),
    "Onarıldı: {name_t}.": ("Repaired: {name_t}.", "Repariert: {name_t}."),
    "Onarım tamamlandı.": ("Repair complete.", "Reparatur abgeschlossen."),
    "Motor revizyonu yapıldı (gömlek, piston, segman, yataklar).": ("Engine overhauled (liners, pistons, rings, bearings).", "Motor überholt (Laufbuchsen, Kolben, Ringe, Lager)."),
    "Revizyon tamamlandı.": ("Overhaul complete.", "Überholung abgeschlossen."),
    "Bilinmeyen işlem.": ("Unknown action.", "Unbekannte Aktion."),
    "Yeni sürüm denetleniyor…": ("Checking for a new version…", "Suche nach neuer Version…"),
    "Güncelleme sürüyor.": ("An update is already in progress.", "Ein Update läuft bereits."),
    "Güncelleme yalnızca kurulu uygulamada çalışır.": ("Updates work only in the installed app.",
                                                       "Updates funktionieren nur in der installierten App."),
    "Yeni sürüm indiriliyor; kurulunca uygulama kapanıp yeniden açılacak.": (
        "Downloading the new version; the app will close and reopen after installing.",
        "Neue Version wird heruntergeladen; nach der Installation schließt sich die App und öffnet sich neu."),
    "Oyun açıkken güncellenemez; oyunu kapatıp tekrar deneyin.": (
        "Cannot update while the game is running; close the game and try again.",
        "Kein Update, solange das Spiel läuft; Spiel schließen und erneut versuchen."),
    "Kurulacak yeni sürüm yok.": ("There is no new version to install.", "Keine neue Version zum Installieren."),
    # arıza tespiti (Motor Analizi) ve yeni motor parçaları
    "Turbo arızası (yağ yakıyor)": ("Turbo failure (burning oil)", "Turbo-Defekt (verbrennt Öl)"),
    "Şaft keçeleri aşındı: turbo yağ yakar (mavi-siyah duman); yağ hızla eksilir, DPF çabuk dolar.": (
        "Shaft seals worn: the turbo burns oil (blue-black smoke); oil drops fast and the DPF fills quickly.",
        "Wellendichtungen verschlissen: Der Turbo verbrennt Öl (blauschwarzer Rauch); Öl nimmt schnell ab, der DPF füllt sich rasch."),
    "Enjektör arızası": ("Injector failure", "Injektor-Defekt"),
    "Bir enjektör damlatıyor: motor tekler, siyah duman atar; DPF hızla dolar, motor aşınması artar.": (
        "An injector is dribbling: the engine misfires and smokes black; the DPF fills fast and engine wear rises.",
        "Ein Injektor tropft nach: Der Motor ruckelt und raucht schwarz; der DPF füllt sich schnell, der Motorverschleiß steigt."),
    "EGR valfi takıldı": ("EGR valve stuck", "AGR-Ventil hängt"),
    "Valf kurumla tıkandı: yanma kirlenir, DPF daha çabuk dolar.": (
        "The valve is clogged with soot: combustion gets dirtier and the DPF fills faster.",
        "Das Ventil ist verrußt: Die Verbrennung wird schmutziger, der DPF füllt sich schneller."),
    "Intercooler kaçağı": ("Intercooler leak", "Ladeluftkühler undicht"),
    "Şarj havası kaçıyor: güç düşer, egzoz sıcaklığı ve DPF kurumu artar.": (
        "Charge air is leaking: power drops, exhaust temperature and DPF soot rise.",
        "Ladeluft entweicht: Leistung sinkt, Abgastemperatur und DPF-Ruß steigen."),
    "Hava filtresi tıkandı": ("Air filter clogged", "Luftfilter verstopft"),
    "Motor yeterli hava alamıyor: güç düşer, DPF kurumu ve motor aşınması artar.": (
        "The engine cannot get enough air: power drops, DPF soot and engine wear rise.",
        "Der Motor bekommt zu wenig Luft: Leistung sinkt, DPF-Ruß und Motorverschleiß steigen."),
    "Yakıt filtresi tıkandı": ("Fuel filter clogged", "Kraftstofffilter verstopft"),
    "Yakıt akışı kısıldı: yüksek yükte motor tekler ve güç düşer.": (
        "Fuel flow is restricted: under high load the engine stumbles and loses power.",
        "Kraftstofffluss gedrosselt: Unter hoher Last ruckelt der Motor und verliert Leistung."),
    "Radyatör sızıntısı": ("Radiator leak", "Kühler undicht"),
    "Radyatör peteği çürüdü: soğutma suyu sürüşte hızla eksilir.": (
        "The radiator core has corroded: coolant drops quickly while driving.",
        "Der Kühlerblock ist korrodiert: Kühlmittel nimmt beim Fahren schnell ab."),
    "Kayış koptu (alternatör ve su pompası)": ("Belt snapped (alternator and water pump)",
                                               "Riemen gerissen (Lichtmaschine und Wasserpumpe)"),
    "Poly-V kayışı koptu: alternatör şarj etmez, su pompası ve fan dönmez; motor kısa sürede hararet yapar.": (
        "The poly-V belt snapped: the alternator stops charging, the water pump and fan stop; the engine overheats quickly.",
        "Der Keilrippenriemen ist gerissen: Die Lichtmaschine lädt nicht, Wasserpumpe und Lüfter stehen; der Motor überhitzt schnell."),
    "Ana bileşenler": ("Main components", "Hauptkomponenten"), "Motor": ("Engine", "Motor"), "Soğutma": ("Cooling", "Kühlung"),
    "Elektrik": ("Electrical", "Elektrik"), "Aktarma ve direksiyon": ("Drivetrain and steering", "Antrieb und Lenkung"),
    "Turbo": ("Turbo", "Turbo"), "Enjektörler": ("Injectors", "Injektoren"), "EGR valfi": ("EGR valve", "AGR-Ventil"),
    "Intercooler": ("Intercooler", "Ladeluftkühler"), "Hava filtresi": ("Air filter", "Luftfilter"),
    "Yakıt filtresi": ("Fuel filter", "Kraftstofffilter"), "Ön ısıtma": ("Preheating", "Vorglühen"),
    "Karter contası": ("Oil pan gasket", "Ölwannendichtung"), "Radyatör": ("Radiator", "Kühler"),
    "Su pompası": ("Water pump", "Wasserpumpe"), "Termostat": ("Thermostat", "Thermostat"),
    "Fan kavraması": ("Fan clutch", "Lüfterkupplung"), "Kayış": ("Belt", "Riemen"), "Alternatör": ("Alternator", "Lichtmaschine"),
    "Marş motoru": ("Starter motor", "Anlasser"), "ABS sensörü": ("ABS sensor", "ABS-Sensor"),
    "Debriyaj aktüatörü": ("Clutch actuator", "Kupplungssteller"), "Şanzıman yağ soğutucusu": ("Gearbox oil cooler", "Getriebeölkühler"),
    "Direksiyon pompası": ("Steering pump", "Lenkhilfepumpe"), "Yağ": ("Oil", "Öl"), "Soğutma suyu": ("Coolant", "Kühlmittel"),
    "Akü": ("Battery", "Batterie"), "DPF (kül)": ("DPF (ash)", "DPF (Asche)"), "Debriyaj balatası": ("Clutch lining", "Kupplungsbelag"),
    "Yakıt türü": ("Fuel type", "Kraftstoff"), "Benzinli": ("Petrol", "Benzin"), "Dizel": ("Diesel", "Diesel"),
    "Silindir hacmi": ("Displacement", "Hubraum"), "Güç": ("Power", "Leistung"), "Tork": ("Torque", "Drehmoment"),
    "Devir": ("Rated speed", "Nenndrehzahl"), "Antifriz": ("Antifreeze", "Frostschutz"), "Motor yağı": ("Engine oil", "Motoröl"),
    "AdBlue": ("AdBlue", "AdBlue"), "Direksiyon yağı": ("Steering fluid", "Lenkhydrauliköl"), "Yakıt": ("Fuel", "Kraftstoff"),
    "Parça değiştirildi: {part_t}.": ("Part replaced: {part_t}.", "Teil ersetzt: {part_t}."),
    "Bilinmeyen parça.": ("Unknown part.", "Unbekanntes Teil."),
    # yeni yağ, antifriz ve akü seçenekleri
    "0W-30 Tam Sentetik Low-SAPS (ACEA E6, çok soğuk iklim)": ("0W-30 Fully Synthetic Low-SAPS (ACEA E6, very cold climates)",
                                                              "0W-30 Vollsynthetisch Low-SAPS (ACEA E6, sehr kaltes Klima)"),
    "5W-40 Sentetik (ACEA E7/E9)": ("5W-40 Synthetic (ACEA E7/E9)", "5W-40 Synthetisch (ACEA E7/E9)"),
    "10W-40 Low-SAPS (ACEA E11 / API CK-4)": ("10W-40 Low-SAPS (ACEA E11 / API CK-4)", "10W-40 Low-SAPS (ACEA E11 / API CK-4)"),
    "15W-40 Yarı Sentetik (API CK-4)": ("15W-40 Semi-Synthetic (API CK-4)", "15W-40 Teilsynthetisch (API CK-4)"),
    "NOAT nitritli organik asit (ıslak gömlekli ağır dizel)": ("NOAT nitrited organic acid (heavy-duty wet-liner diesels)",
                                                               "NOAT nitrithaltige organische Säure (Diesel mit nassen Laufbuchsen)"),
    "HOAT nitritsiz (Volvo VCS / Renault Type D)": ("HOAT nitrite-free (Volvo VCS / Renault Type D)",
                                                    "HOAT nitritfrei (Volvo VCS / Renault Type D)"),
    "Si-OAT G12evo (yeni nesil, ömür boyu dolum)": ("Si-OAT G12evo (new generation, lifetime fill)",
                                                    "Si-OAT G12evo (neue Generation, Lebensdauerfüllung)"),
    "Jel (derin deşarja dayanıklı)": ("Gel (deep-discharge resistant)", "Gel (tiefentladefest)"),
    "AGM ağır hizmet (park klimalı tırlar, yüksek çevrim)": ("Heavy-duty AGM (trucks with parking cooler, high cycling)",
                                                            "AGM Schwerlast (Lkw mit Standklima, hohe Zyklenfestigkeit)"),
    "Yolculuk sıfırlandı.": ("Trip reset.", "Fahrt zurückgesetzt."),
    "Yeni yolculuk: {src} → {dst}.": ("New trip: {src} → {dst}.", "Neue Fahrt: {src} → {dst}."),
    "Teslimat tamamlandı: geçici tırın (hızlı iş) bakım değerleri sıfırlandı.": (
        "Delivery complete: the temporary (quick job) truck's maintenance values were reset.",
        "Lieferung abgeschlossen: die Wartungswerte des Leih-Lkw (Schnellauftrag) wurden zurückgesetzt."),
    "İş iptal edildi: geçici tırın (hızlı iş) bakım değerleri sıfırlandı.": (
        "Job cancelled: the temporary (quick job) truck's maintenance values were reset.",
        "Auftrag abgebrochen: die Wartungswerte des Leih-Lkw (Schnellauftrag) wurden zurückgesetzt."),
    "Bu tırın bakım değerleri elle sıfırlandı.": ("This truck's maintenance values were reset manually.", "Die Wartungswerte dieses Lkw wurden manuell zurückgesetzt."),
    "Bilinmeyen motor (500 hp varsayıldı)": ("Unknown engine (500 hp assumed)", "Unbekannter Motor (500 PS angenommen)"),

    # ---------------------------------------------------------------- arızalar
    "Alternatör arızası": ("Alternator failure", "Lichtmaschinendefekt"),
    "Şarj yok: akü sürüş sırasında boşalır, voltaj düşünce motor stop eder.": ("No charging: the battery drains while driving, the engine stalls when voltage drops.", "Keine Ladung: die Batterie entlädt sich während der Fahrt, bei zu niedriger Spannung geht der Motor aus."),
    "Termostat kapalı takıldı": ("Thermostat stuck closed", "Thermostat klemmt geschlossen"),
    "Radyatöre su gitmiyor; motor yük altında hızla hararet yapar.": ("No coolant reaches the radiator; the engine overheats quickly under load.", "Kein Kühlmittel erreicht den Kühler; der Motor überhitzt unter Last schnell."),
    "Termostat açık takıldı": ("Thermostat stuck open", "Thermostat klemmt offen"),
    "Motor çalışma sıcaklığına ulaşamaz; yakıt seyrelmesi ve aşınma artar.": ("The engine never reaches operating temperature; fuel dilution and wear increase.", "Der Motor erreicht nie Betriebstemperatur; Kraftstoffverdünnung und Verschleiß steigen."),
    "Fan kavraması arızası": ("Fan clutch failure", "Lüfterkupplung defekt"),
    "Fan devreye girmiyor; düşük hızda, yokuşta ve sıcak havada hararet.": ("The fan does not engage; overheating at low speed, on climbs and in hot weather.", "Der Lüfter schaltet nicht zu; Überhitzung bei niedriger Geschwindigkeit, bergauf und bei Hitze."),
    "Su pompası sızdırıyor": ("Water pump leaking", "Wasserpumpe undicht"),
    "Soğutma suyu yavaş yavaş eksilir.": ("Coolant is slowly lost.", "Kühlmittel geht langsam verloren."),
    "Karter contası sızıntısı": ("Oil pan gasket leak", "Ölwannendichtung undicht"),
    "Yağ yavaş yavaş eksilir (park halinde bile damlar).": ("Oil is slowly lost (drips even when parked).", "Öl geht langsam verloren (tropft auch im Stand)."),
    "Silindir kapak contası yandı": ("Cylinder head gasket blown", "Zylinderkopfdichtung defekt"),
    "Hararet sonucu: yağa soğutma suyu karışıyor, su eksiliyor, sistem basınçlanıyor.": ("Caused by overheating: coolant mixes into the oil, coolant is lost, the system pressurises.", "Folge von Überhitzung: Kühlmittel gelangt ins Öl, Kühlmittelverlust, das System baut Druck auf."),
    "Motor kilitlendi (yatak sardı)": ("Engine seized (bearing failure)", "Motor festgegangen (Lagerschaden)"),
    "Yağsız çalışma veya aşırı hararet sonucu. Motor çalışmaz, revizyon gerekli.": ("Caused by oil starvation or severe overheating. The engine will not run, an overhaul is required.", "Folge von Ölmangel oder starker Überhitzung. Der Motor läuft nicht, Überholung nötig."),
    "Motor bloğu donarak çatladı": ("Engine block cracked by frost", "Motorblock durch Frost gerissen"),
    "Antifrizsiz suyla donma sonucu. Büyük kaçak, motor değişimi gerekli.": ("Caused by freezing with plain water. Major leak, engine replacement required.", "Folge von Frost mit reinem Wasser. Großes Leck, Motortausch nötig."),
    "Radyatör donarak çatladı": ("Radiator cracked by frost", "Kühler durch Frost gerissen"),
    "Antifrizsiz suyla donma sonucu. Soğutma suyu hızla kaçar.": ("Caused by freezing with plain water. Coolant leaks out quickly.", "Folge von Frost mit reinem Wasser. Kühlmittel läuft schnell aus."),
    "Akü dondu": ("Battery frozen", "Batterie eingefroren"),
    "Boş akünün elektroliti dondu, plakalar hasar gördü. Aküler değiştirilmeli.": ("The electrolyte of the flat battery froze and damaged the plates. The batteries must be replaced.", "Der Elektrolyt der leeren Batterie ist gefroren und hat die Platten beschädigt. Batterien müssen getauscht werden."),

    # ---------------------------------------------------------------- yağ / antifriz adları
    "15W-40 Mineral (ACEA E7)": ("15W-40 Mineral (ACEA E7)", "15W-40 Mineralisch (ACEA E7)"),
    "10W-40 Sentetik (ACEA E4/E7)": ("10W-40 Synthetic (ACEA E4/E7)", "10W-40 Synthetisch (ACEA E4/E7)"),
    "5W-30 Sentetik Low-SAPS (ACEA E6)": ("5W-30 Synthetic Low-SAPS (ACEA E6)", "5W-30 Synthetisch Low-SAPS (ACEA E6)"),
    "OAT uzun ömürlü (organik asit)": ("OAT long-life (organic acid)", "OAT Langzeit (organische Säure)"),
    "IAT konvansiyonel (silikatlı)": ("IAT conventional (silicate)", "IAT konventionell (Silikat)"),
    # ek yağ, antifriz, akü ve lastik seçenekleri
    "15W-40 Low-SAPS (ACEA E9)": ("15W-40 Low-SAPS (ACEA E9)", "15W-40 Low-SAPS (ACEA E9)"),
    "10W-30 Low-SAPS (ACEA E9 / API CK-4)": ("10W-30 Low-SAPS (ACEA E9 / API CK-4)", "10W-30 Low-SAPS (ACEA E9 / API CK-4)"),
    "10W-40 Sentetik Low-SAPS (ACEA E6)": ("10W-40 Synthetic Low-SAPS (ACEA E6)", "10W-40 Synthetisch Low-SAPS (ACEA E6)"),
    "5W-30 Tam Sentetik Uzun Ömürlü (ACEA E4)": ("5W-30 Fully Synthetic Long-Drain (ACEA E4)", "5W-30 Vollsynthetisch Longlife (ACEA E4)"),
    "20W-50 Mineral (API CF, eski motorlar)": ("20W-50 Mineral (API CF, older engines)", "20W-50 Mineralisch (API CF, ältere Motoren)"),
    "HOAT hibrit (silikat + organik asit, G11/G05)": ("HOAT hybrid (silicate + organic acid, G11/G05)", "HOAT Hybrid (Silikat + organische Säure, G11/G05)"),
    "Si-OAT uzun ömürlü (G12++/G13)": ("Si-OAT long-life (G12++/G13)", "Si-OAT Langzeit (G12++/G13)"),
    "P-OAT fosfatlı organik asit": ("P-OAT phosphated organic acid", "P-OAT phosphatierte organische Säure"),
    "Standart ağır hizmet (SHD)": ("Standard heavy duty (SHD)", "Standard Heavy Duty (SHD)"),
    "EFB (güçlendirilmiş sulu)": ("EFB (enhanced flooded)", "EFB (verbesserte Nassbatterie)"),
    "AGM (cam elyaf, bakımsız)": ("AGM (glass mat, maintenance-free)", "AGM (Glasvlies, wartungsfrei)"),
    "Premium (Michelin, Continental, Bridgestone…)": ("Premium (Michelin, Continental, Bridgestone…)", "Premium (Michelin, Continental, Bridgestone…)"),
    "Orta sınıf": ("Mid-range", "Mittelklasse"), "Ekonomik": ("Budget", "Budget"),
    "Kaplama (yalnız arka dingiller)": ("Retread (rear axles only)", "Runderneuert (nur Hinterachsen)"),
    "Bilinmeyen akü tipi.": ("Unknown battery type.", "Unbekannter Batterietyp."),
    "Aküler değişti (2 x 12 V {ah:.0f} Ah, {kind_t}).": ("Batteries replaced (2 x 12 V {ah:.0f} Ah, {kind_t}).", "Batterien gewechselt (2 x 12 V {ah:.0f} Ah, {kind_t})."),
    "Aküleri yenile: 2 x {ah} Ah, {kind_t}": ("Replace batteries: 2 x {ah} Ah, {kind_t}", "Batterien erneuern: 2 x {ah} Ah, {kind_t}"),
    "Soğutma sıvısını değiştir: %50 {type_t}": ("Change coolant: 50% {type_t}", "Kühlmittel wechseln: 50 % {type_t}"),
    "Bilinmeyen lastik sınıfı.": ("Unknown tyre class.", "Unbekannte Reifenklasse."),
    "Kaplama lastik ön (yönlendirilen) dingile takılmaz.": ("Retreads may not be fitted to the front (steer) axle.", "Runderneuerte Reifen nicht an der Vorderachse (Lenkachse)."),
    "Tüm lastikler yenilendi ({tier_t}).": ("All tyres replaced ({tier_t}).", "Alle Reifen erneuert ({tier_t})."),
    "Lastikler yenilendi: {grp_t}, {tier_t}.": ("Tyres replaced: {grp_t}, {tier_t}.", "Reifen erneuert: {grp_t}, {tier_t}."),
    "Lastik: {grp_t} ({n} adet, {mm} mm) → {tier_t}": ("Tyres: {grp_t} ({n} pcs, {mm} mm) → {tier_t}", "Reifen: {grp_t} ({n} Stk., {mm} mm) → {tier_t}"),
    "50/50 hazır karışım": ("50/50 premix", "50/50 Fertiggemisch"),
    "Konsantre antifriz": ("Antifreeze concentrate", "Frostschutz-Konzentrat"),
    "Saf (demineralize) su": ("Distilled water", "Destilliertes Wasser"),
    "Musluk suyu": ("Tap water", "Leitungswasser"),
    "TBN (asit nötrleme)": ("TBN (acid neutralisation)", "TBN (Säureneutralisation)"),
    "İs (soot)": ("Soot", "Ruß"),
    "Oksidasyon": ("Oxidation", "Oxidation"),
    "Yakıt seyrelmesi": ("Fuel dilution", "Kraftstoffverdünnung"),
    "Viskozite": ("Viscosity", "Viskosität"),
    "Su": ("Water", "Wasser"),
    "Değişim aralığı (km)": ("Drain interval (km)", "Wechselintervall (km)"),
    "Değişim aralığı (takvim)": ("Drain interval (time)", "Wechselintervall (Zeit)"),
    "Glikol kirliliği": ("Glycol contamination", "Glykolverunreinigung"),
    "Viskozite @100°C": ("Viscosity @100°C", "Viskosität @100°C"),
    "TBN": ("TBN", "TBN"),
    "Glikol": ("Glycol", "Glykol"),
    "Pozitif": ("Positive", "Positiv"),
    "Negatif": ("Negative", "Negativ"),
    "Demir (Fe)": ("Iron (Fe)", "Eisen (Fe)"),
    "Krom (Cr)": ("Chromium (Cr)", "Chrom (Cr)"),
    "Kurşun (Pb)": ("Lead (Pb)", "Blei (Pb)"),
    "Bakır (Cu)": ("Copper (Cu)", "Kupfer (Cu)"),
    "Alüminyum (Al)": ("Aluminium (Al)", "Aluminium (Al)"),
    "Silisyum (Si)": ("Silicon (Si)", "Silizium (Si)"),
    "Potasyum (K)": ("Potassium (K)", "Kalium (K)"),
    "normal": ("normal", "normal"),
    "dikkat": ("caution", "Achtung"),
    "kritik": ("critical", "kritisch"),
    "Yağda soğutma sıvısı (glikol + potasyum) var: silindir kapak contası / yağ soğutucusu kaçağı. Motoru çalıştırmayın, acil servis.": (
        "Coolant in the oil (glycol + potassium): head gasket / oil cooler leak. Do not run the engine, urgent service.",
        "Kühlmittel im Öl (Glykol + Kalium): Zylinderkopfdichtung / Ölkühler undicht. Motor nicht betreiben, sofort in die Werkstatt."),
    "İs yüksek: uzun rölanti ve düşük devirde yüksek yük (lugging) azaltılmalı; enjektör/EGR kontrolü önerilir.": (
        "High soot: reduce long idling and high load at low rpm (lugging); injector/EGR check recommended.",
        "Hoher Rußanteil: langes Leerlaufen und Volllast bei niedriger Drehzahl vermeiden; Injektoren/AGR prüfen."),
    "Yakıt seyrelmesi: kısa mesafe, soğuk çalışma ve uzun rölanti yağa yakıt karıştırır. Motoru tam ısıtacak sürüşler yapın.": (
        "Fuel dilution: short trips, cold running and long idling mix fuel into the oil. Drive long enough to fully warm up the engine.",
        "Kraftstoffverdünnung: Kurzstrecken, Kaltbetrieb und langes Leerlaufen bringen Kraftstoff ins Öl. Fahrten so lang machen, dass der Motor warm wird."),
    "TBN düşüyor: yağın asit nötrleme rezervi azaldı, korozif aşınma riski artıyor. Yağ değişimi planlayın.": (
        "TBN falling: the oil's acid reserve is depleting, risk of corrosive wear rises. Plan an oil change.",
        "TBN sinkt: die Säurereserve des Öls nimmt ab, Korrosionsverschleiß droht. Ölwechsel planen."),
    "Demir yüksek: gömlek/segman/eksantrik aşınması. Soğuk motora yüklenme ve yağ kalitesi kontrol edilmeli.": (
        "High iron: liner/ring/camshaft wear. Check cold-engine loading and oil quality.",
        "Hoher Eisenanteil: Verschleiß an Laufbuchse/Ringen/Nockenwelle. Kaltbelastung und Ölqualität prüfen."),
    "Kurşun/bakır yüksek: yatak aşınması işareti (düşük yağ basıncı, lugging, yakıt seyrelmesi).": (
        "High lead/copper: sign of bearing wear (low oil pressure, lugging, fuel dilution).",
        "Hoher Blei-/Kupferanteil: Hinweis auf Lagerverschleiß (niedriger Öldruck, Untertourig, Kraftstoffverdünnung)."),
    "Alüminyum yüksek: piston aşınması, motor aşırı ısınmış olabilir.": ("High aluminium: piston wear, the engine may have overheated.", "Hoher Aluminiumanteil: Kolbenverschleiß, Motor war evtl. überhitzt."),
    "Silisyum yüksek: toz girişi; hava filtresi ve yağ filtresi (bypass) kontrol edilmeli.": ("High silicon: dust ingress; check air filter and oil filter (bypass).", "Hoher Siliziumanteil: Staubeintrag; Luftfilter und Ölfilter (Bypass) prüfen."),
    "Su yüksek: yoğuşma (kısa sürüşler) veya sızıntı. Uzun ve sıcak bir sürüş suyu buharlaştırır.": ("High water: condensation (short trips) or a leak. A long, hot drive evaporates it.", "Hoher Wasseranteil: Kondensat (Kurzstrecken) oder Leck. Eine lange, heiße Fahrt verdampft es."),
    "Yağ ve motor durumu normal. Mevcut bakım aralığına devam edilebilir.": ("Oil and engine condition normal. The current service interval can be kept.", "Öl- und Motorzustand normal. Das aktuelle Wartungsintervall kann beibehalten werden."),

    # ---------------------------------------------------------------- uyarılar
    "Elektrikli kamyon: bu simülatör dizel motorlar için tasarlandı.": ("Electric truck: this simulator is designed for diesel engines.", "Elektro-Lkw: dieser Simulator ist für Dieselmotoren ausgelegt."),
    "MOTOR GERÇEKTE ÇALIŞMIYOR: {reason} Oyunda motoru kapatın.": ("THE ENGINE IS NOT REALLY RUNNING: {reason} Switch the engine off in the game.", "DER MOTOR LÄUFT IN WIRKLICHKEIT NICHT: {reason} Motor im Spiel ausschalten."),
    "{name_t}: {desc_t}": ("{name_t}: {desc_t}", "{name_t}: {desc_t}"),
    "YAĞ BASINCI DÜŞÜK ({p:.1f} bar) — motoru hemen durdurun!": ("LOW OIL PRESSURE ({p:.1f} bar) — stop the engine now!", "ÖLDRUCK NIEDRIG ({p:.1f} bar) — Motor sofort abstellen!"),
    "Yağ seviyesi kritik (%{lvl:.0f}) — yağ pompası hava emiyor.": ("Oil level critical ({lvl:.0f}%) — the oil pump is drawing air.", "Ölstand kritisch ({lvl:.0f} %) — die Ölpumpe saugt Luft."),
    "Yağ seviyesi MIN altında (%{lvl:.0f}, {v:.1f} L). Yağ ekleyin.": ("Oil level below MIN ({lvl:.0f}%, {v:.1f} L). Top up oil.", "Ölstand unter MIN ({lvl:.0f} %, {v:.1f} L). Öl nachfüllen."),
    "Yağ seviyesi MAX üstünde: köpüklenme ve yağ yakma riski.": ("Oil level above MAX: risk of foaming and oil burning.", "Ölstand über MAX: Gefahr von Schaumbildung und Ölverbrennung."),
    "Yağ ömrü bitti ({lim_t}). Yağ ve filtreyi değiştirin.": ("Oil life expired ({lim_t}). Change oil and filter.", "Öllebensdauer erreicht ({lim_t}). Öl und Filter wechseln."),
    "Yağ ömrü %{life:.0f} ({lim_t}). Değişim yaklaşıyor.": ("Oil life {life:.0f}% ({lim_t}). Change due soon.", "Öllebensdauer {life:.0f} % ({lim_t}). Wechsel bald fällig."),
    "Yağ filtresi tıkalı: bypass valfi açık, yağ filtrelenmiyor.": ("Oil filter clogged: bypass valve open, oil is not filtered.", "Ölfilter verstopft: Bypassventil offen, Öl wird nicht gefiltert."),
    "Yağda soğutma suyu var (glikol)! Yataklar zarar görür.": ("Coolant in the oil (glycol)! Bearings will be damaged.", "Kühlmittel im Öl (Glykol)! Die Lager werden beschädigt."),
    "SOĞUTMA SUYU KAYNIYOR ({t:.0f} °C) — durun, motoru rölantide soğutun!": ("COOLANT BOILING ({t:.0f} °C) — stop and let the engine cool at idle!", "KÜHLMITTEL KOCHT ({t:.0f} °C) — anhalten, Motor im Leerlauf abkühlen lassen!"),
    "HARARET: {t:.0f} °C": ("OVERHEATING: {t:.0f} °C", "ÜBERHITZUNG: {t:.0f} °C"),
    "Motor sıcaklığı yüksek: {t:.0f} °C": ("Engine temperature high: {t:.0f} °C", "Motortemperatur hoch: {t:.0f} °C"),
    "Retarder hararet yapıyor: gerçek araçta retarder gücü bu sıcaklıkta düşürülür. Vites küçültüp motor freni kullanın.": (
        "Retarder overheating: a real truck would reduce retarder power at this temperature. Shift down and use the engine brake.",
        "Retarder überhitzt: im echten Lkw würde die Retarderleistung bei dieser Temperatur reduziert. Herunterschalten und Motorbremse nutzen."),
    "Soğutma suyu çok az (%{lvl:.0f}) — pompa kavitasyon yapıyor.": ("Coolant very low ({lvl:.0f}%) — the pump is cavitating.", "Kühlmittel sehr niedrig ({lvl:.0f} %) — die Pumpe kavitiert."),
    "Soğutma suyu seviyesi düşük (%{lvl:.0f}). Motor soğukken tamamlayın.": ("Coolant level low ({lvl:.0f}%). Top up when the engine is cold.", "Kühlmittelstand niedrig ({lvl:.0f} %). Bei kaltem Motor nachfüllen."),
    "DONMA: hava {amb:.0f} °C, antifriz donma noktası {fp:.0f} °C!": ("FREEZING: air {amb:.0f} °C, coolant freezing point {fp:.0f} °C!", "FROST: Luft {amb:.0f} °C, Gefrierpunkt des Kühlmittels {fp:.0f} °C!"),
    "Antifriz yetersiz: donma noktası {fp:.0f} °C, bölgede beklenen en düşük {mn:.0f} °C.": ("Antifreeze insufficient: freezing point {fp:.0f} °C, expected low in this region {mn:.0f} °C.", "Frostschutz unzureichend: Gefrierpunkt {fp:.0f} °C, erwartetes Minimum in der Region {mn:.0f} °C."),
    "Soğutma sisteminde buzlanma (blok %{b:.0f}, radyatör %{r:.0f}).": ("Ice in the cooling system (block {b:.0f}%, radiator {r:.0f}%).", "Eis im Kühlsystem (Block {b:.0f} %, Kühler {r:.0f} %)."),
    "Antifriz inhibitörü tükendi (%{i:.0f}): korozyon ve kireçlenme başladı.": ("Coolant inhibitor depleted ({i:.0f}%): corrosion and scaling have started.", "Korrosionsschutz im Kühlmittel verbraucht ({i:.0f} %): Korrosion und Kalk beginnen."),
    "Radyatör/blok kireçlenmiş (%{s:.0f}): soğutma verimi düştü.": ("Radiator/block scaled ({s:.0f}%): cooling efficiency reduced.", "Kühler/Block verkalkt ({s:.0f} %): Kühlleistung gesunken."),
    "Alternatör yükü karşılayamıyor (rölantide yüksek elektrik yükü).": ("The alternator cannot keep up (high electrical load at idle).", "Die Lichtmaschine kommt nicht nach (hohe elektrische Last im Leerlauf)."),
    "ŞARJ YOK: akü {v:.1f} V, %{soc:.0f}.": ("NO CHARGING: battery {v:.1f} V, {soc:.0f}%.", "KEINE LADUNG: Batterie {v:.1f} V, {soc:.0f} %."),
    "Yağ bu soğukta çok koyu ({visc:,.0f} cSt): motor marşla dönmez. Daha ince yağ veya ısıtma gerekir.": (
        "Oil too thick in this cold ({visc:,.0f} cSt): the engine won't crank. Thinner oil or a heater is needed.",
        "Öl bei dieser Kälte zu zäh ({visc:,.0f} cSt): der Motor dreht nicht durch. Dünneres Öl oder Vorwärmung nötig."),
    "Akü bu koşulda motoru çeviremez (marşta ~{v:.1f} V). Şarj edin veya takviye yapın.": ("The battery cannot crank the engine now (~{v:.1f} V while cranking). Charge it or jump start.", "Die Batterie kann den Motor jetzt nicht durchdrehen (~{v:.1f} V beim Anlassen). Laden oder Starthilfe geben."),
    "Zayıf marş bekleniyor (~{v:.1f} V).": ("Weak start expected (~{v:.1f} V).", "Schwacher Start zu erwarten (~{v:.1f} V)."),
    "Kontak açık, {a:.0f} A çekiliyor: akü {h:.1f} saatte %50'ye iner.": ("Ignition on, {a:.0f} A drawn: battery reaches 50% in {h:.1f} h.", "Zündung an, {a:.0f} A Verbrauch: Batterie erreicht 50 % in {h:.1f} h."),
    "Akü şarjı düşük (%{soc:.0f}). Sülfatlaşma riski.": ("Battery charge low ({soc:.0f}%). Risk of sulphation.", "Batterieladung niedrig ({soc:.0f} %). Sulfatierungsgefahr."),
    "Akü sağlığı zayıf (%{soh:.0f}). Değişim önerilir.": ("Battery health poor ({soh:.0f}%). Replacement recommended.", "Batteriezustand schlecht ({soh:.0f} %). Austausch empfohlen."),
    "Akü donma riski: bu şarjda elektrolit {fp:.0f} °C'de donar.": ("Battery freeze risk: at this charge the electrolyte freezes at {fp:.0f} °C.", "Frostgefahr für die Batterie: bei dieser Ladung gefriert der Elektrolyt bei {fp:.0f} °C."),
    "DPF tıkalı (%{s:.0f}): gerçek araçta motor güç düşürür. Servis rejenerasyonu gerekli.": ("DPF blocked ({s:.0f}%): a real truck would derate. Workshop regeneration required.", "DPF verstopft ({s:.0f} %): im echten Lkw Leistungsreduzierung. Werkstatt-Regeneration nötig."),
    "DPF dolu (%{s:.0f}). 40 km/h üstünde uzun sürüş yapın ya da servis rejenerasyonu yaptırın.": ("DPF full ({s:.0f}%). Drive for a while above 40 km/h or have a workshop regeneration.", "DPF voll ({s:.0f} %). Länger über 40 km/h fahren oder Werkstatt-Regeneration machen lassen."),
    "DPF aktif rejenerasyon yapıyor — motoru kapatmayın, sürüşe devam edin.": ("DPF active regeneration running — do not switch off, keep driving.", "Aktive DPF-Regeneration läuft — Motor nicht abstellen, weiterfahren."),
    "DPF rejenerasyon bekliyor: 40 km/h üstünde sürüş gerekli.": ("DPF regeneration pending: driving above 40 km/h required.", "DPF-Regeneration ausstehend: Fahrt über 40 km/h nötig."),
    "DPF kül doluluğu %{a:.0f}: filtre temizliği gerekli.": ("DPF ash load {a:.0f}%: filter cleaning required.", "DPF-Aschebeladung {a:.0f} %: Filterreinigung nötig."),
    "Soğuk motora yüklenme (yağ {t:.0f} °C): aşınma 3 kat.": ("Loading a cold engine (oil {t:.0f} °C): 3× wear.", "Belastung bei kaltem Motor (Öl {t:.0f} °C): 3-facher Verschleiß."),
    "Düşük devirde tam yük (lugging): vites küçültün.": ("Full load at low rpm (lugging): shift down.", "Volllast bei niedriger Drehzahl: herunterschalten."),
    "Aşırı devir!": ("Over-revving!", "Überdrehzahl!"),
    "{m:.0f} dk'dır rölantide: yakıt, is ve yakıt seyrelmesi.": ("Idling for {m:.0f} min: fuel, soot and fuel dilution.", "Seit {m:.0f} min im Leerlauf: Kraftstoff, Ruß und Kraftstoffverdünnung."),
    "Motor sağlığı %{h:.0f}: revizyon yaklaşıyor (yağ yakma, düşük basınç).": ("Engine health {h:.0f}%: overhaul approaching (oil burning, low pressure).", "Motorzustand {h:.0f} %: Überholung naht (Ölverbrauch, niedriger Druck)."),
    "Fren sıcaklığı yüksek ({t:.0f} °C): fren zayıflaması (fading) riski. Retarder ve motor frenini kullanın.": ("Brake temperature high ({t:.0f} °C): risk of brake fade. Use the retarder and engine brake.", "Bremstemperatur hoch ({t:.0f} °C): Fading-Gefahr. Retarder und Motorbremse nutzen."),
    "FRENLER AŞIRI ISINDI ({t:.0f} °C) — fren gücü azaldı!": ("BRAKES OVERHEATED ({t:.0f} °C) — braking power reduced!", "BREMSEN ÜBERHITZT ({t:.0f} °C) — Bremsleistung reduziert!"),
    "Hava basıncı düşük ({p:.1f} bar): frenler kilitlenebilir.": ("Air pressure low ({p:.1f} bar): the brakes may lock.", "Luftdruck niedrig ({p:.1f} bar): die Bremsen können blockieren."),

    # ---------------------------------------------------------------- uygulama / durum
    "Yakıt alındı: {l:.0f} L.": ("Refuelled: {l:.0f} L.", "Getankt: {l:.0f} L."),
    "Zaman atlaması {h:.1f} saat (uyku/feribot): motor {t:.0f} °C'ye soğudu, akü %{soc:.0f}.": ("Time skip {h:.1f} h (sleep/ferry): engine cooled to {t:.0f} °C, battery {soc:.0f}%.", "Zeitsprung {h:.1f} h (Schlaf/Fähre): Motor auf {t:.0f} °C abgekühlt, Batterie {soc:.0f} %."),
    "Motor durduruluyor (oyun içi eklenti); kontak ve ekranlar açık kalır.": (
        "Stopping the engine (in-game plugin); ignition and screens stay on.",
        "Motor wird abgestellt (Spiel-Plugin); Zündung und Bildschirme bleiben an."),
    "Motor çalışmaz durumda: güvenli bir yere çekip yavaşlayın; tır {v} km/h altına inince motor durdurulacak (kontak ve ışıklar açık kalır).": (
        "The engine is not working: pull over somewhere safe and slow down; the engine will be stopped below {v} km/h (ignition and lights stay on).",
        "Der Motor ist nicht betriebsbereit: an sicherer Stelle anhalten und langsamer werden; unter {v} km/h wird der Motor abgestellt (Zündung und Licht bleiben an)."),
    "Motor durduruldu: {msg}": ("Engine stopped: {msg}", "Motor gestoppt: {msg}"),
    "'{key}' tuşu gönderildi": ("'{key}' key sent", "Taste '{key}' gesendet"),
    "Oyun penceresi ön planda değil — motoru kendiniz durdurun": ("The game window is not in front — stop the engine yourself", "Das Spielfenster ist nicht im Vordergrund — Motor selbst abstellen"),
    "Yalnızca Windows'ta çalışır": ("Works on Windows only", "Funktioniert nur unter Windows"),
    "Oyun içi katmana veri gönderilemedi: {err}": ("Could not send data to the in-game overlay: {err}", "Daten konnten nicht an das Spiel-Overlay gesendet werden: {err}"),
    "Simülasyon hatası: {err}": ("Simulation error: {err}", "Simulationsfehler: {err}"),
    "Henüz kamyon verisi yok.": ("No truck data yet.", "Noch keine Lkw-Daten."),
    "Başlatılıyor…": ("Starting…", "Startet…"),
    "Durum hatası: {err}": ("State error: {err}", "Statusfehler: {err}"),
    "Ayarlar kaydedildi.": ("Settings saved.", "Einstellungen gespeichert."),
    # uyarı sesi
    "Uyarı sesi: {brand_t} ({lvl_t}).": ("Warning sound: {brand_t} ({lvl_t}).", "Warnton: {brand_t} ({lvl_t})."),
    "Uyarı sesi: {brand_t} ({lvl_t}). Sesli uyarı kapalı: oyunda ötmesi için “Sesli uyarı” kutusunu işaretleyin.": (
        "Warning sound: {brand_t} ({lvl_t}). Audible warnings are off: tick “Audible warning” to hear them in the game.",
        "Warnton: {brand_t} ({lvl_t}). Akustische Warnung ist aus: „Akustische Warnung“ ankreuzen, damit sie im Spiel ertönt."),
    "Ses çalınamadı (demo modunda ses kapalı).": ("Could not play the sound (sound is off in demo mode).",
                                                   "Ton konnte nicht abgespielt werden (im Demo-Modus aus)."),
    "Otomobil (gong)": ("Car (gong)", "Pkw (Gong)"), "Genel": ("Generic", "Allgemein"),
    # TruckersMP araçları (otomobil, otobüs)
    "Tır": ("Truck", "Lkw"), "Otobüs": ("Bus", "Bus"), "Otomobil": ("Car", "Pkw"),
    "Araç algılandı: {model} ({veh_t}). Varsayılan motor {engine}; benzinli / dizel motoru Ayarlar'dan seçebilirsiniz.": (
        "Vehicle detected: {model} ({veh_t}). Default engine {engine}; choose petrol / diesel in Settings.",
        "Fahrzeug erkannt: {model} ({veh_t}). Standardmotor {engine}; Benzin / Diesel in den Einstellungen wählen."),
    "Akü şarj cihazı bağlandı ({a:.0f} A).": ("Battery charger connected ({a:.0f} A).", "Batterieladegerät angeschlossen ({a:.0f} A)."),
    "Şarj cihazı bağla ({a} A)": ("Connect charger ({a} A)", "Ladegerät anschließen ({a} A)"),
    "Aküyü yenile: 12 V {ah} Ah, {kind_t}": ("Replace battery: 12 V {ah} Ah, {kind_t}", "Batterie erneuern: 12 V {ah} Ah, {kind_t}"),
    "2 x 12 V seri, 24 V sistem": ("2 x 12 V in series, 24 V system", "2 x 12 V in Reihe, 24-V-System"),
    "12 V, tek akü": ("12 V, single battery", "12 V, eine Batterie"),
    "ön lastikler": ("front tyres", "Vorderreifen"), "arka lastikler": ("rear tyres", "Hinterreifen"),
    # sürüş modları
    "Güç %75 ile sınırlı, yumuşak gaz, 85 km/h hız sınırı": ("Power limited to 75%, soft throttle, 85 km/h speed limit",
                                                            "Leistung auf 75 % begrenzt, sanftes Gas, 85 km/h Begrenzung"),
    "Yumuşak gaz tepkisi, güç sınırı yok": ("Smooth throttle response, no power limit", "Sanfte Gasannahme, keine Leistungsgrenze"),
    "Keskin pedal: yarım pedalda daha çok güç, anında tepki": ("Sharp pedal: more power at half pedal, instant response",
                                                             "Scharfes Pedal: mehr Leistung bei halbem Pedal, sofortige Reaktion"),
    "Sürüş modu: {name} — {desc_t}": ("Drive mode: {name} — {desc_t}", "Fahrmodus: {name} — {desc_t}"),
    "Sürüş modu tuşu atandı: {key}": ("Drive mode key assigned: {key}", "Fahrmodus-Taste zugewiesen: {key}"),
    "Tuş atama iptal edildi ya da süre doldu.": ("Key assignment cancelled or timed out.", "Tastenzuweisung abgebrochen oder abgelaufen."),
    "Tuş atama iptal edildi.": ("Key assignment cancelled.", "Tastenzuweisung abgebrochen."),
    "Atamak istediğiniz klavye tuşuna ya da direksiyon / kumanda düğmesine basın (10 sn, Esc iptal).": (
        "Press the keyboard key or wheel / controller button to assign (10 s, Esc cancels).",
        "Gewünschte Taste oder Lenkrad-/Controllertaste drücken (10 s, Esc bricht ab)."),
    "Tuş yok": ("No key", "Keine Taste"),
    "Kumanda düğmesi {n}": ("Controller button {n}", "Controller-Taste {n}"),
    "Kumanda yön tuşu: {d_t}": ("Controller D-pad: {d_t}", "Controller-Steuerkreuz: {d_t}"),
    "yukarı": ("up", "oben"), "aşağı": ("down", "unten"), "sol": ("left", "links"), "sağ": ("right", "rechts"),
    "Henüz kamyon yok.": ("No truck yet.", "Noch kein Lkw."),
    "Otomatik algılama yeniden başlatıldı.": ("Automatic detection restarted.", "Automatische Erkennung neu gestartet."),
    "Motor seçim modu: otomatik": ("Engine selection: automatic", "Motorwahl: automatisch"),
    "Motor seçim modu: elle": ("Engine selection: manual", "Motorwahl: manuell"),
    "Bu modelde böyle bir motor yok.": ("This model has no such engine.", "Dieses Modell hat keinen solchen Motor."),
    "Motor seçildi: {engine} (otomatik algılama kapatıldı).": ("Engine selected: {engine} (automatic detection off).", "Motor gewählt: {engine} (automatische Erkennung aus)."),
    "Geçersiz değer.": ("Invalid value.", "Ungültiger Wert."),
    "Kamyon özellikleri kaydedildi.": ("Truck specifications saved.", "Lkw-Daten gespeichert."),
    "Bağlanıyor…": ("Connecting…", "Verbinde…"),
    "Oyuna bağlı": ("Connected to game", "Mit Spiel verbunden"),
    "Eksik truck-telemetry paketi kuruluyor…": ("Installing the missing truck-telemetry package…", "Fehlendes Paket truck-telemetry wird installiert…"),
    "truck-telemetry paketi kurulamadı (internet bağlantısını kontrol edin)": (
        "Could not install the truck-telemetry package (check your internet connection)",
        "Paket truck-telemetry konnte nicht installiert werden (Internetverbindung prüfen)"),
    "Oyun çalışmıyor ya da telemetri eklentisi (scs-telemetry.dll) kurulu değil": ("The game is not running or the telemetry plugin (scs-telemetry.dll) is not installed", "Das Spiel läuft nicht oder das Telemetrie-Plugin (scs-telemetry.dll) ist nicht installiert"),
    "Telemetri eklentisi uyumsuz: {err} (V.1.12.x gerekli)": ("Telemetry plugin incompatible: {err} (V.1.12.x required)", "Telemetrie-Plugin inkompatibel: {err} (V.1.12.x nötig)"),
    "Telemetri okunamadı: {err}": ("Telemetry could not be read: {err}", "Telemetrie konnte nicht gelesen werden: {err}"),
    "Oyun menüde / telemetri beklemede": ("Game in menu / telemetry waiting", "Spiel im Menü / Telemetrie wartet"),
    "DEMO modu (sanal kamyon)": ("DEMO mode (virtual truck)", "DEMO-Modus (virtueller Lkw)"),

    # ---------------------------------------------------------------- oyun içi katman metinleri
    "{city} yakını": ("near {city}", "bei {city}"),
    "DEMO": ("DEMO", "DEMO"),
    "Duraklatıldı": ("Paused", "Pausiert"),
    "Bağlı": ("Connected", "Verbunden"),
    "Bağlı değil": ("Not connected", "Nicht verbunden"),
    "DURDU": ("STALLED", "AUS"),
    "Çalışıyor": ("Running", "Läuft"),
    "Kapalı": ("Off", "Aus"),
    "Devrede": ("Engaged", "Ein"),
    "Aktif": ("Active", "Aktiv"),
    "Bekliyor": ("Pending", "Ausstehend"),
    "Yok": ("None", "Keine"),
    "vites {g}": ("gear {g}", "Gang {g}"),
    "vites —": ("gear —", "Gang —"),
    "motor freni {kw} kW": ("engine brake {kw} kW", "Motorbremse {kw} kW"),
    "marş imkânsız": ("cannot start", "Start unmöglich"),
    "{a} A · alternatör {b} A": ("{a} A · alternator {b} A", "{a} A · Lichtmaschine {b} A"),
    "{t} °C · donma {f} °C": ("{t} °C · freezes at {f} °C", "{t} °C · Gefrierpunkt {f} °C"),
    "{v} cSt · 100 °C'de {w}": ("{v} cSt · at 100 °C {w}", "{v} cSt · bei 100 °C {w}"),
    "{p} bar · kaynama {b} °C": ("{p} bar · boils at {b} °C", "{p} bar · Siedepunkt {b} °C"),
    "blok %{b} · radyatör %{r}": ("block {b}% · radiator {r}%", "Block {b} % · Kühler {r} %"),
    "Model tanınmadı": ("Model not recognised", "Modell nicht erkannt"),
    "otomatik": ("automatic", "automatisch"),
    "elle": ("manual", "manuell"),
    "ölçülen ≈{nm} Nm → {e}": ("measured ≈{nm} Nm → {e}", "gemessen ≈{nm} Nm → {e}"),
    "örnek {n}/{k}": ("samples {n}/{k}", "Messwerte {n}/{k}"),
    "{h} sa · {d} km": ("{h} h · {d} km", "{h} h · {d} km"),
    "{n} dk": ("{n} min", "{n} min"),
    "{n} sa": ("{n} h", "{n} h"),
    "{n} gün": ("{n} days", "{n} Tage"),
    "şimdi": ("now", "jetzt"),
    # ---------------------------------------------------------------- oyundaki servis noktasında tamir
    "Oyundaki serviste tamir yapıldı (oyun hasarı %{d:.0f} azaldı).": (
        "Repaired at an in-game service (game damage reduced by {d:.0f}%).",
        "In der Spielwerkstatt repariert (Spielschaden um {d:.0f} % verringert)."),
    "Oyundaki serviste onarıldı: {name_t}.": ("Repaired at the in-game service: {name_t}.", "In der Spielwerkstatt repariert: {name_t}."),
    "Oyundaki serviste donmuş aküler yenilendi (2 x 12 V {ah:.0f} Ah).": (
        "Frozen batteries replaced at the in-game service (2 x 12 V {ah:.0f} Ah).",
        "Gefrorene Batterien in der Spielwerkstatt ersetzt (2 x 12 V {ah:.0f} Ah)."),
    "Oyundaki serviste donmuş akü yenilendi (12 V {ah:.0f} Ah).": (
        "Frozen battery replaced at the in-game service (12 V {ah:.0f} Ah).",
        "Gefrorene Batterie in der Spielwerkstatt ersetzt (12 V {ah:.0f} Ah)."),
    "Akü değişti (12 V {ah:.0f} Ah, {kind_t}).": ("Battery replaced (12 V {ah:.0f} Ah, {kind_t}).",
                                                  "Batterie gewechselt (12 V {ah:.0f} Ah, {kind_t})."),
    "Akü değişti.": ("Battery replaced.", "Batterie getauscht."),
    "Kaplama lastik otomobile takılmaz.": ("Retreads may not be fitted to a car.",
                                           "Runderneuerte Reifen sind für Pkw nicht zulässig."),
    "Kayıt yazılamadı: {err}": ("Could not save: {err}", "Speichern fehlgeschlagen: {err}"),
    # ---------------------------------------------------------------- tek / çok oyunculu mod
    # ön ısıtma (kızdırma)
    "ISITMA": ("PREHEAT", "VORGLÜHEN"),
    "Ön ısıtma (kızdırma bujisi / ızgara ısıtıcı) arızası": ("Preheater (glow plug / grid heater) fault", "Vorglühanlage (Glühkerze / Heizflansch) defekt"),
    "Soğukta motor zor çalışır ya da hiç ateşlemez, beyaz duman atar; ön ısıtma lambası yanıp söner.": (
        "In the cold the engine starts badly or not at all and smokes white; the preheat lamp flashes.",
        "Bei Kälte springt der Motor schlecht oder gar nicht an und qualmt weiß; die Vorglühleuchte blinkt."),
    "ön ısıtma arızalı, motor {t:.0f} °C'de ateşlemedi": ("preheater faulty, the engine did not fire at {t:.0f} °C",
                                                         "Vorglühanlage defekt, der Motor zündete bei {t:.0f} °C nicht"),
    "ön ısıtma lambası sönmeden marşa basıldı, motor {t:.0f} °C'de ateşlemedi; kontak açıkken lamba sönene kadar bekleyip tekrar deneyin": (
        "cranked before the preheat lamp went out, the engine did not fire at {t:.0f} °C; with the ignition on, wait until the lamp goes out and try again",
        "vor dem Erlöschen der Vorglühleuchte gestartet, der Motor zündete bei {t:.0f} °C nicht; Zündung an, warten bis die Leuchte erlischt, dann erneut versuchen"),
    "Ön ısıtma tamamlanmadan marş ({t:.0f} °C): zor ateşleme, beyaz duman, ek aşınma.": (
        "Started before preheating finished ({t:.0f} °C): hard start, white smoke, extra wear.",
        "Vor Ende des Vorglühens gestartet ({t:.0f} °C): schwerer Start, weißer Rauch, zusätzlicher Verschleiß."),
    "Ön ısıtma yapılıyor: lamba sönünce marşa basın (~{s:.0f} sn).": (
        "Preheating: crank once the lamp goes out (~{s:.0f} s).", "Vorglühen: starten, sobald die Leuchte erlischt (~{s:.0f} s)."),
    "ARIZALI: soğukta ısıtmıyor": ("FAULTY: no preheating in the cold", "DEFEKT: kein Vorglühen bei Kälte"),
    "Kontak kapalı": ("Ignition off", "Zündung aus"),
    "Gerekmiyor (motor {t} °C)": ("Not needed (engine {t} °C)", "Nicht nötig (Motor {t} °C)"),
    "Isıtıyor, {s} sn kaldı": ("Preheating, {s} s left", "Glüht vor, noch {s} s"),
    "Hazır: marşa basabilirsiniz": ("Ready: you can crank", "Bereit: Motor starten"),
    # lastikler, yakıt, AdBlue
    "ön dingil": ("front axle", "Vorderachse"), "çekiş dingili": ("drive axle", "Antriebsachse"),
    "taşıyıcı dingil": ("tag axle", "Nachlaufachse"),
    "LASTİK": ("TYRES", "REIFEN"), "YAKIT": ("FUEL", "KRAFTSTOFF"),
    "LASTİK PATLADI ({grp_t})! Hemen güvenli bir yerde durun.": (
        "TYRE BLOWOUT ({grp_t})! Stop somewhere safe immediately.", "REIFEN GEPLATZT ({grp_t})! Sofort sicher anhalten."),
    "Yavaş patlak: {grp_t} lastiği hava kaçırıyor.": (
        "Slow puncture: {grp_t} tyre is losing air.", "Schleichender Plattfuß: Reifen an der {grp_t} verliert Luft."),
    "Yavaş patlak: {grp_t} lastiği hava kaçırıyor ({p:.1f} bar).": (
        "Slow puncture: {grp_t} tyre is losing air ({p:.1f} bar).",
        "Schleichender Plattfuß: Reifen an der {grp_t} verliert Luft ({p:.1f} bar)."),
    "Lastik basıncı çok düşük: {grp_t} {p:.1f} bar (olması gereken {n:.1f}). Isınıp patlayabilir.": (
        "Tyre pressure very low: {grp_t} {p:.1f} bar (should be {n:.1f}). It may overheat and burst.",
        "Reifendruck sehr niedrig: {grp_t} {p:.1f} bar (soll {n:.1f}). Er kann überhitzen und platzen."),
    "Lastik basıncı düşük: {grp_t} {p:.1f} bar (olması gereken {n:.1f}).": (
        "Tyre pressure low: {grp_t} {p:.1f} bar (should be {n:.1f}).", "Reifendruck niedrig: {grp_t} {p:.1f} bar (soll {n:.1f})."),
    "Lastik dişi yasal sınırın altında: {grp_t} {mm:.1f} mm. Lastikleri değiştirin.": (
        "Tread below the legal limit: {grp_t} {mm:.1f} mm. Replace the tyres.",
        "Profil unter der gesetzlichen Grenze: {grp_t} {mm:.1f} mm. Reifen erneuern."),
    "Lastik dişi azaldı: {grp_t} {mm:.1f} mm. Değişim yaklaşıyor.": (
        "Tread getting low: {grp_t} {mm:.1f} mm. Replacement due soon.", "Profil wird knapp: {grp_t} {mm:.1f} mm. Wechsel bald fällig."),
    "Lastikler aşırı ısındı ({grp_t} {t:.0f} °C): yavaşlayın, basıncı kontrol edin.": (
        "Tyres overheating ({grp_t} {t:.0f} °C): slow down and check the pressure.",
        "Reifen überhitzt ({grp_t} {t:.0f} °C): langsamer fahren, Druck prüfen."),
    "Lastikler ısınıyor ({grp_t} {t:.0f} °C).": ("Tyres heating up ({grp_t} {t:.0f} °C).", "Reifen werden heiß ({grp_t} {t:.0f} °C)."),
    "Yakıt bitmek üzere (%{p:.0f}, {l:.0f} L). Hemen yakıt alın.": (
        "Almost out of fuel ({p:.0f}%, {l:.0f} L). Refuel now.", "Kraftstoff fast leer ({p:.0f} %, {l:.0f} L). Sofort tanken."),
    "Yakıt azaldı (%{p:.0f}, {l:.0f} L).": ("Fuel low ({p:.0f}%, {l:.0f} L).", "Kraftstoff knapp ({p:.0f} %, {l:.0f} L)."),
    "Yakıt bitti: dizel sistemine hava girdi (gerçek araçta yakıt alındıktan sonra el pompasıyla havası alınmadan motor çalışmaz).": (
        "Out of fuel: air entered the diesel system (on a real truck the engine will not start until it is bled with the hand pump after refuelling).",
        "Kraftstoff leer: Luft im Dieselsystem (beim echten Lkw startet der Motor erst nach dem Entlüften mit der Handpumpe)."),
    "AdBlue bitti: gerçek araçta motor gücü düşürülür, yeniden çalıştırmada hız 20 km/h ile sınırlanır.": (
        "AdBlue empty: a real truck cuts engine power and limits speed to 20 km/h after a restart.",
        "AdBlue leer: Ein echter Lkw reduziert die Leistung und begrenzt nach dem Neustart auf 20 km/h."),
    "AdBlue bitmek üzere (%{p:.0f}). Yakıtla birlikte AdBlue alın.": (
        "AdBlue almost empty ({p:.0f}%). Fill AdBlue when refuelling.", "AdBlue fast leer ({p:.0f} %). Beim Tanken AdBlue auffüllen."),
    "AdBlue azaldı (%{p:.0f}).": ("AdBlue low ({p:.0f}%).", "AdBlue knapp ({p:.0f} %)."),
    "AdBlue {t:.0f} °C'de donar: motor çalışınca depo ısıtıcısı çözer, ilk dakikalarda püskürtme gecikir.": (
        "AdBlue freezes at {t:.0f} °C: the tank heater thaws it once the engine runs, dosing is delayed at first.",
        "AdBlue gefriert bei {t:.0f} °C: Die Tankheizung taut es bei laufendem Motor auf, die Dosierung beginnt verzögert."),
    "Oyundaki serviste lastikler yenilendi.": ("Tyres replaced at the in-game service.", "Reifen im Spiel-Service erneuert."),
    "Lastik basıncı için kamyonu durdurun.": ("Stop the truck to set the tyre pressure.", "Zum Einstellen des Reifendrucks anhalten."),
    "Lastik basınçları ayarlandı ({n} dingil).": ("Tyre pressures set ({n} axles).", "Reifendruck eingestellt ({n} Achsen)."),
    "Lastik basınçları ayarlandı ({n} dingil). Lastikler sıcakken ayarlandı: soğuyunca basınç düşük kalabilir.": (
        "Tyre pressures set ({n} axles). Set while the tyres were hot: pressure may be low once they cool down.",
        "Reifendruck eingestellt ({n} Achsen). Bei warmen Reifen eingestellt: kalt kann der Druck zu niedrig sein."),
    "Patlak lastik yok.": ("No punctured tyre.", "Kein Reifen mit Panne."),
    "Yavaş patlak tamir edildi, basınç ayarlandı.": ("Slow puncture repaired, pressure set.", "Reifenpanne repariert, Druck eingestellt."),
    "Patlak tamir edildi.": ("Puncture repaired.", "Panne repariert."),
    "Bu dingil yok.": ("This axle does not exist.", "Diese Achse gibt es nicht."),
    "Bu kamyonda AdBlue (SCR) yok.": ("This truck has no AdBlue (SCR).", "Dieser Lkw hat kein AdBlue (SCR)."),
    "{l:.1f} L AdBlue eklendi (depo %{lvl:.0f}).": ("{l:.1f} L AdBlue added (tank {lvl:.0f}%).", "{l:.1f} L AdBlue nachgefüllt (Tank {lvl:.0f} %)."),
    "Yakıtla birlikte {l:.1f} L AdBlue alındı.": ("{l:.1f} L AdBlue filled together with fuel.", "{l:.1f} L AdBlue zusammen mit Kraftstoff getankt."),
    "yakıtın %{p}'i": ("{p}% of fuel", "{p} % des Kraftstoffs"),
    "yok (SCR'siz motor)": ("none (engine without SCR)", "keins (Motor ohne SCR)"),
    "{mm} mm · basınç {p}": ("{mm} mm · pressure {p}", "{mm} mm · Druck {p}"),
    "{c} bar (şu an {h}) · {t} °C": ("{c} bar (now {h}) · {t} °C", "{c} bar (aktuell {h}) · {t} °C"),
    "PATLADI": ("BLOWN", "GEPLATZT"), "kaldırılmış": ("lifted", "angehoben"), "patlak": ("puncture", "Panne"),
    "LASTİK · en az diş {mm} mm · en düşük basınç %{p}": (
        "TYRES · min. tread {mm} mm · lowest pressure {p}%", "REIFEN · min. Profil {mm} mm · niedrigster Druck {p} %"),
    "Lastik basınçlarını ayarla": ("Set tyre pressures", "Reifendruck einstellen"),
    "ücretsiz": ("free", "kostenlos"),
    "Yavaş patlağı tamir et": ("Repair slow puncture", "Reifenpanne reparieren"),
    "ADBLUE · %{p} · {l} / {c} L": ("ADBLUE · {p}% · {l} / {c} L", "ADBLUE · {p} % · {l} / {c} L"),
    "AdBlue tamamla (+{l} L)": ("Top up AdBlue (+{l} L)", "AdBlue auffüllen (+{l} L)"),
    # silecek kademesi
    "silecek {s_t} · {a:.1f} A": ("wipers {s_t} · {a:.1f} A", "Wischer {s_t} · {a:.1f} A"),
    "silecek {s_t}": ("wipers {s_t}", "Wischer {s_t}"),
    "kapalı": ("off", "aus"), "aralıklı": ("intermittent", "Intervall"), "yavaş": ("slow", "langsam"),
    "hızlı": ("fast", "schnell"),
    # gösterge lambaları (katman)
    "AKÜ": ("BATTERY", "BATTERIE"), "YAĞ": ("OIL", "ÖL"), "SOĞUTMA": ("COOLANT", "KÜHLUNG"),
    "FREN": ("BRAKES", "BREMSE"), "MOTOR": ("ENGINE", "MOTOR"), "DONMA": ("FROST", "FROST"),
    "BAKIM": ("SERVICE", "WARTUNG"), "DURUN": ("PULL OVER", "ANHALTEN"),
    "Tek Oyunculu": ("Singleplayer", "Einzelspieler"),
    "Çok Oyunculu": ("Multiplayer", "Mehrspieler"),
    "Konvoy": ("Convoy", "Konvoi"),
    "TruckersMP": ("TruckersMP", "TruckersMP"),
    "ETS2 Bakım": ("ETS2 Maintenance", "ETS2 Wartung"),
    "ETS2 Bakım Simülatörü": ("ETS2 Maintenance Simulator", "ETS2 Wartungssimulator"),
    "{n} hp": ("{n} hp", "{n} PS"),
    "{mp_t} oturumu algılandı: güvenlik için motor zorla durdurulmuyor. Ayarlar → Oyun modu: Otomatik ya da "
    "Çok Oyunculu seçin.": (
        "{mp_t} session detected: for safety the engine is not force-stopped. Settings → Game mode: choose Automatic "
        "or Multiplayer.",
        "{mp_t}-Sitzung erkannt: aus Sicherheitsgründen wird der Motor nicht zwangsweise abgestellt. Einstellungen → "
        "Spielmodus: Automatisch oder Mehrspieler wählen."),
    "Tek oyunculu oturum: tam gerçekçilik (motor durdurma) için Ayarlar → Oyun modu: Otomatik ya da Tek "
    "Oyunculu seçin.": (
        "Singleplayer session: for full realism (engine stop) choose Settings → Game mode: Automatic or Singleplayer.",
        "Einzelspieler-Sitzung: für volle Realistik (Motorstopp) Einstellungen → Spielmodus: Automatisch oder "
        "Einzelspieler wählen."),
    "Oyun modu: {mode_t} — bu modun kendi ayarları ve bakım kayıtları yüklendi.": (
        "Game mode: {mode_t} — this mode's own settings and maintenance records are loaded.",
        "Spielmodus: {mode_t} — die eigenen Einstellungen und Wartungsdaten dieses Modus sind geladen."),
    # ---------------------------------------------------------------- oyun içi servis menüsü (Alt+F8)
    "Tır durmalı ve motor kapalı olmalı": ("Truck must be stopped with the engine off", "Lkw muss stehen, Motor aus"),
    "Önce tırı durdurun": ("Stop the truck first", "Zuerst den Lkw anhalten"),
    "YAĞ · {v} / {c} L · ömür %{life}": ("OIL · {v} / {c} L · life {life}%", "ÖL · {v} / {c} L · Lebensdauer {life} %"),
    "1 L yağ ekle ({grade})": ("Add 1 L of oil ({grade})", "1 L Öl nachfüllen ({grade})"),
    "Yağı MAX'a tamamla (+{l} L)": ("Top up oil to MAX (+{l} L)", "Öl bis MAX auffüllen (+{l} L)"),
    "Yağ + filtre değiştir: {grade}": ("Change oil + filter: {grade}", "Öl + Filter wechseln: {grade}"),
    "Yalnız yağ filtresini değiştir": ("Change oil filter only", "Nur Ölfilter wechseln"),
    "Yağ numunesi al (analiz)": ("Take an oil sample (analysis)", "Ölprobe nehmen (Analyse)"),
    "SOĞUTMA · seviye %{lvl} · donma {f} °C": ("COOLING · level {lvl}% · freezes at {f} °C", "KÜHLUNG · Stand {lvl} % · gefriert bei {f} °C"),
    "Motor sıcak: radyatör kapağını açmayın": ("Engine hot: do not open the radiator cap", "Motor heiß: Kühlerdeckel nicht öffnen"),
    "Antifriz tamamla, 50/50 (+{l} L)": ("Top up antifreeze, 50/50 (+{l} L)", "Frostschutz auffüllen, 50/50 (+{l} L)"),
    "Antifriz ölçümü (refraktometre)": ("Measure antifreeze (refractometer)", "Frostschutz messen (Refraktometer)"),
    "AKÜ · şarj %{soc} · sağlık %{soh}": ("BATTERY · charge {soc}% · health {soh}%", "BATTERIE · Ladung {soc} % · Zustand {soh} %"),
    "Şarj cihazını sök": ("Disconnect the charger", "Ladegerät abklemmen"),
    "Takviye kablosu bağla": ("Connect jumper cables", "Starthilfekabel anschließen"),
    "Motor zaten çalışıyor": ("Engine is already running", "Motor läuft bereits"),
    "Akü testi": ("Battery test", "Batterietest"),
    "DPF · is %{s} · kül %{a}": ("DPF · soot {s}% · ash {a}%", "DPF · Ruß {s} % · Asche {a} %"),
    "Servis rejenerasyonu": ("Service regeneration", "Service-Regeneration"),
    "DPF kül temizliği": ("DPF ash cleaning", "DPF-Aschereinigung"),
    "ONARIM · motor sağlığı %{h}": ("REPAIR · engine health {h}%", "REPARATUR · Motorzustand {h} %"),
    "Onar: {name_t}": ("Repair: {name_t}", "Reparieren: {name_t}"),
    "Motor revizyonu": ("Engine overhaul", "Motorüberholung"),
    "Tır duruyor, motor kapalı: servis yapılabilir.": ("Truck stopped, engine off: service is possible.",
                                                       "Lkw steht, Motor aus: Service möglich."),
    # ---------------------------------------------------------------- şanzıman, debriyaj, direksiyon, ABS, park freni, marş
    "Şanzıman yağ soğutucusu arızası": ("Gearbox oil cooler fault", "Getriebeölkühler defekt"),
    "Yağ-su eşanjörü tıkandı: yokuşta ve retarder kullanımında şanzıman yağı aşırı ısınır.": (
        "Oil-to-water heat exchanger blocked: the gearbox oil overheats on climbs and when using the retarder.",
        "Öl-Wasser-Wärmetauscher verstopft: das Getriebeöl überhitzt an Steigungen und beim Retarder-Einsatz."),
    "Debriyaj aktüatörü arızası": ("Clutch actuator fault", "Kupplungssteller defekt"),
    "Aktüatör hava kaçırıyor: debriyaj tam kavramıyor, yükte kayar; debriyaj ısınır ve hızla aşınır.": (
        "The actuator leaks air: the clutch does not fully engage and slips under load; it overheats and wears quickly.",
        "Der Steller verliert Luft: die Kupplung greift nicht voll und rutscht unter Last; sie überhitzt und verschleißt schnell."),
    "Direksiyon hidrolik kaçağı": ("Power steering leak", "Leck in der Servolenkung"),
    "Direksiyon pompası / hortumu sızdırıyor: hidrolik yağı eksilir; azalınca direksiyon ağırlaşır, pompa zarar görür.": (
        "Steering pump / hose is leaking: hydraulic fluid is lost; when it is low the steering gets heavy and the pump is damaged.",
        "Lenkpumpe / Schlauch undicht: Hydrauliköl geht verloren; bei niedrigem Stand wird die Lenkung schwer und die Pumpe beschädigt."),
    "ABS tekerlek hızı sensörü arızası": ("ABS wheel speed sensor fault", "ABS-Raddrehzahlsensor defekt"),
    "Sensör sinyali yok: ABS ve ESC devre dışı, sert frenlemede tekerlekler kilitlenebilir.": (
        "No sensor signal: ABS and ESC are disabled, the wheels may lock under hard braking.",
        "Kein Sensorsignal: ABS und ESC sind aus, bei starkem Bremsen können die Räder blockieren."),
    "Park freni çekiliyken hareket ediliyor: frenler ısınır, balatalar yanar!": (
        "Driving with the parking brake applied: the brakes overheat and the linings burn!",
        "Fahrt mit angezogener Feststellbremse: die Bremsen überhitzen, die Beläge verbrennen!"),
    "Park freni çekilmedi: motor kapalıyken tırı park frenine alın.": (
        "Parking brake not applied: apply the parking brake while the engine is off.",
        "Feststellbremse nicht angezogen: bei abgestelltem Motor die Feststellbremse anziehen."),
    "Marş motoru arızası": ("Starter motor fault", "Anlasser defekt"),
    "Selenoid / kömürler aşınmış: marş motoru zaman zaman çevirmiyor, birkaç denemede çalışabilir.": (
        "Worn solenoid / brushes: the starter sometimes does not crank; it may work after a few attempts.",
        "Magnetschalter / Kohlen verschlissen: der Anlasser dreht manchmal nicht; nach einigen Versuchen kann es klappen."),
    "marş motoru çevirmedi (selenoid / kömürler); motoru kapatıp tekrar deneyin": (
        "the starter did not crank (solenoid / brushes); switch off and try again",
        "der Anlasser hat nicht gedreht (Magnetschalter / Kohlen); ausschalten und erneut versuchen"),
    "Direksiyon hidrolik desteği yok (motor çalışmıyor): direksiyon çok ağır, yavaşlayıp güvenli bir yerde durun.": (
        "No power steering assist (engine not running): the steering is very heavy, slow down and stop somewhere safe.",
        "Keine Lenkunterstützung (Motor läuft nicht): die Lenkung ist sehr schwer, langsamer werden und sicher anhalten."),
    "Direksiyon hidrolik yağı çok az (%{p:.0f}): destek azaldı, pompa zarar görüyor. Kaçağı onarın.": (
        "Power steering fluid very low ({p:.0f}%): assist reduced, the pump is being damaged. Repair the leak.",
        "Servolenköl sehr niedrig ({p:.0f} %): Unterstützung vermindert, die Pumpe wird beschädigt. Leck reparieren."),
    "ŞANZIMAN YAĞI AŞIRI SICAK ({t:.0f} °C): yükü azaltın, gerekirse durup motoru rölantide çalıştırarak soğutun!": (
        "GEARBOX OIL OVERHEATING ({t:.0f} °C): reduce the load; if needed stop and let it cool with the engine idling!",
        "GETRIEBEÖL ÜBERHITZT ({t:.0f} °C): Last verringern, notfalls anhalten und im Leerlauf abkühlen lassen!"),
    "Şanzıman yağı sıcak ({t:.0f} °C): yükü ve retarder kullanımını azaltın.": (
        "Gearbox oil hot ({t:.0f} °C): reduce the load and retarder use.",
        "Getriebeöl heiß ({t:.0f} °C): Last und Retarder-Einsatz verringern."),
    "DEBRİYAJ AŞIRI ISINDI ({t:.0f} °C): yarım debriyajla sürünmeyin; durun, motor rölantide debriyaj soğusun!": (
        "CLUTCH OVERHEATED ({t:.0f} °C): do not creep on a slipping clutch; stop and let it cool with the engine idling!",
        "KUPPLUNG ÜBERHITZT ({t:.0f} °C): nicht mit schleifender Kupplung kriechen; anhalten und im Leerlauf abkühlen lassen!"),
    "Debriyaj ısınıyor ({t:.0f} °C): kalkış ve manevraları azaltın, yarım debriyajla beklemeyin.": (
        "Clutch getting hot ({t:.0f} °C): fewer starts and manoeuvres, do not hold the truck on a slipping clutch.",
        "Kupplung wird heiß ({t:.0f} °C): weniger anfahren und rangieren, nicht mit schleifender Kupplung halten."),
    "Debriyaj balatası bitti: yükte kayıyor. Debriyajı yenileyin.": (
        "Clutch lining worn out: it slips under load. Replace the clutch.",
        "Kupplungsbelag verschlissen: sie rutscht unter Last. Kupplung erneuern."),
    "Debriyaj balatası %{w:.0f} aşındı: değişim yaklaşıyor.": (
        "Clutch lining {w:.0f}% worn: replacement due soon.", "Kupplungsbelag {w:.0f} % verschlissen: Wechsel bald fällig."),
    "Şanzıman yağının değişim zamanı geldi ({km:,.0f} km).": (
        "Gearbox oil change due ({km:,.0f} km).", "Getriebeölwechsel fällig ({km:,.0f} km)."),
    "Şanzıman yağı ve filtresi değişti ({l:.0f} L).": ("Gearbox oil and filter changed ({l:.0f} L).",
                                                       "Getriebeöl und Filter gewechselt ({l:.0f} L)."),
    "Şanzıman yağı değiştirildi.": ("Gearbox oil changed.", "Getriebeöl gewechselt."),
    "Debriyaj yenilendi (balata, baskı plakası, debriyaj rulmanı).": (
        "Clutch replaced (disc, pressure plate, release bearing).", "Kupplung erneuert (Scheibe, Druckplatte, Ausrücklager)."),
    "Debriyaj yenilendi.": ("Clutch replaced.", "Kupplung erneuert."),
    "%{w} aşınmış · {t} °C": ("{w}% worn · {t} °C", "{w} % verschlissen · {t} °C"),
    "ŞANZIMAN · yağ {t} °C · debriyaj %{w} aşınmış": ("GEARBOX · oil {t} °C · clutch {w}% worn",
                                                     "GETRIEBE · Öl {t} °C · Kupplung {w} % verschlissen"),
    "Şanzıman yağını değiştir ({l} L + filtre)": ("Change gearbox oil ({l} L + filter)", "Getriebeöl wechseln ({l} L + Filter)"),
    "Debriyajı yenile (balata, baskı plakası, rulman)": ("Replace clutch (disc, pressure plate, bearing)",
                                                         "Kupplung erneuern (Scheibe, Druckplatte, Lager)"),
    "MARŞ": ("STARTER", "ANLASSER"), "EL FRENİ": ("PARK BRAKE", "PARKBREMSE"), "DİREKSİYON": ("STEERING", "LENKUNG"),
    "ŞANZIMAN": ("GEARBOX", "GETRIEBE"),
    # gösterge lambalarının önem dereceleri
    "Önemsiz": ("Minor", "Geringfügig"), "Önemli": ("Important", "Wichtig"), "Uyarı": ("Warning", "Warnung"),
    "Ciddi": ("Serious", "Ernst"), "Kritik": ("Critical", "Kritisch"),
    # ---------------------------------------------------------------- Ayarlar → uyarılar ve ikaz lambaları (alerts.py)
    "Motor ve sürüş": ("Engine and driving", "Motor und Fahrweise"),
    "Soğutma ve donma": ("Cooling and freezing", "Kühlung und Frost"),
    "Akü ve elektrik": ("Battery and electrics", "Batterie und Elektrik"),
    "Frenler, hava ve park freni": ("Brakes, air and parking brake", "Bremsen, Druckluft und Feststellbremse"),
    "Direksiyon": ("Steering", "Lenkung"), "Şanzıman ve debriyaj": ("Gearbox and clutch", "Getriebe und Kupplung"),
    "DPF (partikül filtresi)": ("DPF (particulate filter)", "DPF (Partikelfilter)"),
    "Yakıt ve AdBlue": ("Fuel and AdBlue", "Kraftstoff und AdBlue"), "Lastikler": ("Tyres", "Reifen"),
    "Parça arızaları": ("Component faults", "Bauteildefekte"),
    "Tek / çok oyunculu bildirimleri": ("Singleplayer / multiplayer notices", "Einzel-/Mehrspieler-Hinweise"),
    "Motor gerçekte çalışmıyor": ("Engine not actually running", "Motor läuft in Wirklichkeit nicht"),
    "Motor sağlığı düşük (revizyon yaklaşıyor)": ("Low engine health (overhaul due soon)",
                                                  "Niedriger Motorzustand (Überholung bald fällig)"),
    "Aşırı devir": ("Over-revving", "Überdrehzahl"),
    "Düşük devirde tam yük (lugging)": ("Full load at low rpm (lugging)", "Volllast bei niedriger Drehzahl (untertourig)"),
    "Soğuk motora yüklenme": ("Loading a cold engine", "Kaltlast"), "Uzun süre rölanti": ("Long idling", "Langer Leerlauf"),
    "Ön ısıtma yapılıyor": ("Preheating in progress", "Vorglühen läuft"),
    "Elektrikli kamyon bilgisi": ("Electric truck notice", "Hinweis Elektro-Lkw"),
    "Yağ basıncı düşük": ("Low oil pressure", "Öldruck zu niedrig"), "Yağ seviyesi kritik": ("Oil level critical", "Ölstand kritisch"),
    "Yağ seviyesi MIN altında": ("Oil level below MIN", "Ölstand unter MIN"),
    "Yağ seviyesi MAX üstünde": ("Oil level above MAX", "Ölstand über MAX"),
    "Yağ ömrü bitti": ("Oil life expired", "Öllebensdauer erreicht"),
    "Yağ değişimi yaklaşıyor": ("Oil change due soon", "Ölwechsel bald fällig"),
    "Yağ filtresi tıkalı": ("Oil filter clogged", "Ölfilter verstopft"),
    "Yağda soğutma suyu (glikol)": ("Coolant in the oil (glycol)", "Kühlmittel im Öl (Glykol)"),
    "Soğutma suyu kaynıyor": ("Coolant boiling", "Kühlmittel kocht"), "Hararet": ("Overheating", "Überhitzung"),
    "Motor sıcaklığı yüksek": ("Engine temperature high", "Motortemperatur hoch"),
    "Retarder hararet yapıyor": ("Retarder overheating the engine", "Retarder überhitzt den Motor"),
    "Soğutma suyu çok az": ("Coolant very low", "Kühlmittel sehr niedrig"),
    "Soğutma suyu seviyesi düşük": ("Coolant level low", "Kühlmittelstand niedrig"),
    "Antifriz donuyor": ("Coolant freezing", "Kühlmittel gefriert"),
    "Antifriz yetersiz (beklenen soğuğa göre)": ("Antifreeze insufficient (for the expected cold)",
                                                 "Frostschutz unzureichend (für die erwartete Kälte)"),
    "Soğutma sisteminde buzlanma": ("Ice in the cooling system", "Eis im Kühlsystem"),
    "Antifriz inhibitörü tükendi": ("Coolant inhibitor depleted", "Korrosionsschutz des Kühlmittels verbraucht"),
    "Radyatör / blok kireçlenmiş": ("Radiator / block scaled", "Kühler / Block verkalkt"),
    "Şarj yok": ("Not charging", "Keine Ladung"),
    "Alternatör yükü karşılayamıyor": ("Alternator cannot cover the load", "Lichtmaschine deckt die Last nicht"),
    "Akü motoru çeviremez": ("Battery cannot crank the engine", "Batterie kann den Motor nicht durchdrehen"),
    "Yağ marş için çok koyu": ("Oil too thick to crank", "Öl zu zäh zum Anlassen"),
    "Zayıf marş bekleniyor": ("Weak cranking expected", "Schwacher Start erwartet"),
    "Kontak açık, akü boşalıyor": ("Ignition on, battery draining", "Zündung an, Batterie entlädt sich"),
    "Akü şarjı düşük": ("Battery charge low", "Batterieladung niedrig"),
    "Akü sağlığı zayıf": ("Battery health poor", "Batteriezustand schlecht"),
    "Akü donma riski": ("Battery freezing risk", "Batterie-Frostgefahr"),
    "Frenler aşırı ısındı": ("Brakes overheated", "Bremsen überhitzt"),
    "Fren sıcaklığı yüksek": ("Brake temperature high", "Bremstemperatur hoch"),
    "Hava basıncı düşük": ("Air pressure low", "Luftdruck niedrig"),
    "Park freni çekiliyken hareket": ("Moving with the parking brake on", "Fahrt mit angezogener Feststellbremse"),
    "Park freni çekilmedi": ("Parking brake not applied", "Feststellbremse nicht angezogen"),
    "Direksiyon desteği yok (motor çalışmıyor)": ("No steering assist (engine not running)",
                                                  "Keine Lenkunterstützung (Motor läuft nicht)"),
    "Direksiyon hidrolik yağı çok az": ("Power steering fluid very low", "Servolenköl sehr niedrig"),
    "Şanzıman yağı aşırı sıcak": ("Gearbox oil overheated", "Getriebeöl überhitzt"),
    "Şanzıman yağı sıcak": ("Gearbox oil hot", "Getriebeöl heiß"),
    "Debriyaj aşırı ısındı": ("Clutch overheated", "Kupplung überhitzt"),
    "Debriyaj ısınıyor": ("Clutch getting hot", "Kupplung wird heiß"),
    "Debriyaj balatası bitti": ("Clutch lining worn out", "Kupplungsbelag verschlissen"),
    "Debriyaj balatası aşınıyor": ("Clutch lining wearing", "Kupplungsbelag nutzt sich ab"),
    "Şanzıman yağı değişim zamanı": ("Gearbox oil change due", "Getriebeölwechsel fällig"),
    "DPF tıkalı": ("DPF blocked", "DPF verstopft"), "DPF dolu": ("DPF full", "DPF voll"),
    "DPF kül temizliği gerekli": ("DPF ash cleaning needed", "DPF-Ascheabreinigung nötig"),
    "DPF rejenerasyon yapıyor": ("DPF regenerating", "DPF regeneriert"),
    "DPF rejenerasyon bekliyor": ("DPF regeneration pending", "DPF-Regeneration ausstehend"),
    "Yakıt bitmek üzere": ("Fuel almost empty", "Kraftstoff fast leer"), "Yakıt azaldı": ("Fuel low", "Kraftstoff knapp"),
    "AdBlue bitti": ("AdBlue empty", "AdBlue leer"), "AdBlue bitmek üzere": ("AdBlue almost empty", "AdBlue fast leer"),
    "AdBlue azaldı": ("AdBlue low", "AdBlue knapp"), "AdBlue donma bilgisi": ("AdBlue freezing notice", "Hinweis AdBlue-Frost"),
    "Lastik patladı": ("Tyre blown", "Reifen geplatzt"),
    "Lastik basıncı çok düşük": ("Tyre pressure very low", "Reifendruck sehr niedrig"),
    "Lastik basıncı düşük": ("Tyre pressure low", "Reifendruck niedrig"),
    "Yavaş patlak": ("Slow puncture", "Schleichender Plattfuß"),
    "Lastik dişi yasal sınırın altında": ("Tread below the legal limit", "Profil unter der gesetzlichen Grenze"),
    "Lastik dişi azaldı": ("Tread low", "Profil knapp"), "Lastikler aşırı ısındı": ("Tyres overheated", "Reifen überhitzt"),
    "Lastikler ısınıyor": ("Tyres getting hot", "Reifen werden heiß"),
    "Tek Oyunculu modda çok oyunculu oturum algılandı": ("Multiplayer session detected in Singleplayer mode",
                                                         "Mehrspieler-Sitzung im Einzelspielermodus erkannt"),
    "Çok Oyunculu modda tek oyunculu oturum": ("Singleplayer session in Multiplayer mode",
                                               "Einzelspieler-Sitzung im Mehrspielermodus"),
    "Motor yavaşlayınca durdurulacak (çok oyunculu tam izleme)": (
        "Engine will be stopped once you slow down (multiplayer full monitoring)",
        "Motor wird beim Langsamwerden abgestellt (Mehrspieler, volle Überwachung)"),
    "Motoru hemen durdurun: yağ basıncı yok, hararet / kaynama, motor kilitlendi, patlak lastikle ya da fren havası "
    "bitmişken hareket": (
        "Stop the engine now: no oil pressure, overheating / boiling, engine seized, moving on a blown tyre or with the "
        "brake air running out",
        "Motor sofort abstellen: kein Öldruck, Überhitzung / Kochen, Motor festgefressen, Fahrt mit geplatztem Reifen "
        "oder ausgehender Bremsluft"),
    "Şarj yok; akü boş, zayıf ya da donma riskinde; marş için şarj yetersiz": (
        "Not charging; battery flat, weak or at risk of freezing; not enough charge to crank",
        "Keine Ladung; Batterie leer, schwach oder frostgefährdet; zu wenig Ladung zum Anlassen"),
    "Ön ısıtma sürüyor (bilgi) ya da ön ısıtma arızası": ("Preheating in progress (info) or preheater fault",
                                                          "Vorglühen läuft (Hinweis) oder Vorglühdefekt"),
    "Yağ basıncı düşük ya da yağ seviyesi az": ("Low oil pressure or low oil level", "Öldruck oder Ölstand zu niedrig"),
    "Motor sıcaklığı yüksek ya da soğutma suyu az": ("Engine temperature high or coolant low",
                                                    "Motortemperatur hoch oder Kühlmittel niedrig"),
    "Frenler çok sıcak ya da fren havası düşük": ("Brakes very hot or brake air pressure low",
                                                  "Bremsen sehr heiß oder Bremsluftdruck niedrig"),
    "Park freni çekiliyken hareket ya da motor kapalıyken çekilmemiş": (
        "Moving with the parking brake on, or not applied with the engine off",
        "Fahrt mit angezogener Feststellbremse oder bei Motor aus nicht angezogen"),
    "ABS sensörü arızası": ("ABS sensor fault", "ABS-Sensordefekt"),
    "Direksiyon hidrolik desteği yok, yağı az ya da kaçak var": ("No power steering assist, fluid low or leaking",
                                                                 "Keine Lenkunterstützung, Öl niedrig oder undicht"),
    "Şanzıman yağı ya da debriyaj sıcaklığı, balata aşınması, arıza, yağ değişimi": (
        "Gearbox oil or clutch temperature, lining wear, fault, oil change",
        "Getriebeöl- oder Kupplungstemperatur, Belagverschleiß, Defekt, Ölwechsel"),
    "Lastik basıncı, sıcaklığı, dişi ya da patlak": ("Tyre pressure, temperature, tread or puncture",
                                                     "Reifendruck, -temperatur, Profil oder Panne"),
    "Motor arıza lambası: arıza kodu, conta, termostat, düşük motor sağlığı": (
        "Engine warning lamp: fault code, gasket, thermostat, low engine health",
        "Motorkontrollleuchte: Fehlercode, Dichtung, Thermostat, niedriger Motorzustand"),
    "DPF dolu ya da tıkalı, kül, rejenerasyon": ("DPF full or blocked, ash, regeneration", "DPF voll oder verstopft, Asche, Regeneration"),
    "AdBlue az ya da bitti": ("AdBlue low or empty", "AdBlue knapp oder leer"), "Yakıt az": ("Fuel low", "Kraftstoff knapp"),
    "Antifriz yetersiz ya da soğutma sisteminde buz": ("Antifreeze insufficient or ice in the cooling system",
                                                       "Frostschutz unzureichend oder Eis im Kühlsystem"),
    "Bakım zamanı: yağ ömrü, yağ filtresi, antifriz": ("Service due: oil life, oil filter, antifreeze",
                                                       "Wartung fällig: Öllebensdauer, Ölfilter, Frostschutz"),
    # ---------------------------------------------------------------- çekim modu (filming.py)
    "Yağ pompası arızası": ("Oil pump failure", "Ölpumpendefekt"),
    "Pompa yeterli basınç üretmiyor (aşınmış dişliler, açık kalan tahliye valfi): yağ basıncı düşer, kırmızı yağ lambası "
    "yanar. Motoru durdurun; bu halde sürmek yatakları aşındırır.": (
        "The pump does not build enough pressure (worn gears, relief valve stuck open): oil pressure drops and the red "
        "oil lamp comes on. Stop the engine; driving on like this wears the bearings.",
        "Die Pumpe baut nicht genug Druck auf (verschlissene Zahnräder, offen hängendes Überdruckventil): der Öldruck "
        "fällt, die rote Öldruckleuchte geht an. Motor abstellen; Weiterfahren verschleißt die Lager."),
    "Motor ve yağlama": ("Engine and lubrication", "Motor und Schmierung"),
    "Elektrik, marş ve ön ısıtma": ("Electrics, starter and preheating", "Elektrik, Anlasser und Vorglühen"),
    "Şanzıman, ABS ve direksiyon": ("Gearbox, ABS and steering", "Getriebe, ABS und Lenkung"),
    "Lastik patlaması — ön dingil": ("Tyre blowout — front axle", "Reifenplatzer — Vorderachse"),
    "Lastik patlaması — arka dingil": ("Tyre blowout — rear axle", "Reifenplatzer — Hinterachse"),
    "Yavaş patlak — ön dingil": ("Slow puncture — front axle", "Schleichender Plattfuß — Vorderachse"),
    "Yavaş patlak — arka dingil": ("Slow puncture — rear axle", "Schleichender Plattfuß — Hinterachse"),
    "Lastik aniden patlar: araç patlayan tarafa çeker, jant sürterek yavaşlar (oyun içi katman kurulu ve Ayarlar'da "
    "“Lastik patlaması” açıksa). Lastik değişimiyle giderilir.": (
        "The tyre bursts suddenly: the vehicle pulls towards the burst side and slows down with the rim scraping (if the "
        "in-game overlay is installed and “Tyre blowout” is on in Settings). Fixed by replacing the tyre.",
        "Der Reifen platzt plötzlich: das Fahrzeug zieht zur geplatzten Seite und bremst mit schleifender Felge ab (wenn "
        "das Spiel-Overlay installiert und „Reifenplatzer“ in den Einstellungen an ist). Behebung durch Reifenwechsel."),
    "Lastik yavaş yavaş hava kaçırır: basınç düştükçe lastik ısınır, sonunda patlayabilir. Yavaş patlak tamiriyle "
    "giderilir.": (
        "The tyre slowly loses air: as the pressure drops it heats up and may eventually burst. Fixed by a puncture repair.",
        "Der Reifen verliert langsam Luft: mit sinkendem Druck wird er heiß und kann schließlich platzen. Behebung durch "
        "Pannenreparatur."),
    "Bilinmeyen arıza.": ("Unknown fault.", "Unbekannter Defekt."),
    "Otomobilde hidrolik direksiyon yok (elektrikli direksiyon).": (
        "Cars have no hydraulic power steering (electric steering).", "Pkw haben keine hydraulische Lenkung (elektrische Lenkung)."),
    "Benzinli motorda ön ısıtma yok.": ("Petrol engines have no preheating.", "Benzinmotoren haben keine Vorglühanlage."),
    "Bu arıza zaten var: {name_t}.": ("This fault is already active: {name_t}.", "Dieser Defekt ist bereits aktiv: {name_t}."),
    "ARIZA (elle tetiklendi): {name_t} — {desc_t}": ("FAULT (triggered manually): {name_t} — {desc_t}",
                                                     "DEFEKT (manuell ausgelöst): {name_t} — {desc_t}"),
    "Krank yatakları sardı, MOTOR KİLİTLENDİ.": ("Crank bearings seized, ENGINE SEIZED.",
                                                 "Kurbelwellenlager gefressen, MOTOR FESTGEGANGEN."),
    "Tetiklendi: {name_t}.": ("Triggered: {name_t}.", "Ausgelöst: {name_t}."),
    "Bu lastik zaten patlak: {grp_t}.": ("This tyre is already blown: {grp_t}.", "Dieser Reifen ist bereits geplatzt: {grp_t}."),
    "LASTİK PATLADI ({grp_t}) — elle tetiklendi.": ("TYRE BLOWOUT ({grp_t}) — triggered manually.",
                                                    "REIFEN GEPLATZT ({grp_t}) — manuell ausgelöst."),
    "Bu lastikte zaten yavaş patlak var: {grp_t}.": ("This tyre already has a slow puncture: {grp_t}.",
                                                     "Dieser Reifen hat bereits einen schleichenden Plattfuß: {grp_t}."),
    "Yavaş patlak: {grp_t} lastiği hava kaçırıyor (elle tetiklendi).": (
        "Slow puncture: {grp_t} tyre is losing air (triggered manually).",
        "Schleichender Plattfuß: Reifen an der {grp_t} verliert Luft (manuell ausgelöst)."),
    "Onarılacak arıza ya da lastik sorunu yok.": ("No fault or tyre problem to repair.",
                                                  "Kein Defekt und kein Reifenproblem zu beheben."),
    "Çekim modu: {n} arıza / lastik sorunu ücretsiz onarıldı.": (
        "Filming mode: {n} fault(s) / tyre problem(s) repaired for free.",
        "Aufnahmemodus: {n} Defekt(e) / Reifenproblem(e) kostenlos behoben."),
    "Bu tuş çekim modu tuşu olarak atanmış; başka bir tuş seçin.": (
        "This key is already the filming mode key; choose another one.",
        "Diese Taste ist bereits die Aufnahmemodus-Taste; bitte eine andere wählen."),
    "Bu tuş sürüş modu tuşu olarak atanmış; başka bir tuş seçin.": (
        "This key is already the drive mode key; choose another one.",
        "Diese Taste ist bereits die Fahrmodus-Taste; bitte eine andere wählen."),
    "Çekim modu tuşu atandı: {key}": ("Filming mode key assigned: {key}", "Aufnahmemodus-Taste zugewiesen: {key}"),
    "Çekim modu yalnızca tek oyunculu oturumda kullanılabilir.": (
        "Filming mode is only available in single-player sessions.",
        "Der Aufnahmemodus ist nur in Einzelspieler-Sitzungen verfügbar."),
    "Çekim modu kapalı: Ayarlar → Çekim modu kutusunu işaretleyin.": (
        "Filming mode is off: tick Settings → Filming mode.", "Aufnahmemodus ist aus: Einstellungen → Aufnahmemodus ankreuzen."),
    # ---------------------------------------------------------------- araç tipi (Ayarlar → Araç tipi)
    "Araç tipini değiştirmek için oyunda bu araçla bağlı olun.": (
        "To change the vehicle type, be in the game with this vehicle.",
        "Zum Ändern des Fahrzeugtyps im Spiel mit diesem Fahrzeug verbunden sein."),
    "Bilinmeyen araç tipi.": ("Unknown vehicle type.", "Unbekannter Fahrzeugtyp."),
    "Araç tipi: {veh_t}.": ("Vehicle type: {veh_t}.", "Fahrzeugtyp: {veh_t}."),
    "Araç tipi: otomatik algılama ({veh_t}). Motor: {engine}.": (
        "Vehicle type: automatic detection ({veh_t}). Engine: {engine}.",
        "Fahrzeugtyp: automatische Erkennung ({veh_t}). Motor: {engine}."),
    "Araç tipi elle seçildi: {veh_t}. Motor: {engine}; Ayarlar'dan değiştirebilirsiniz.": (
        "Vehicle type set manually: {veh_t}. Engine: {engine}; you can change it in Settings.",
        "Fahrzeugtyp manuell gewählt: {veh_t}. Motor: {engine}; in den Einstellungen änderbar."),
    "Otomobil — genel motor listesi": ("Car — generic engine list", "Pkw — allgemeine Motorliste"),
    "Otobüs — genel motor listesi": ("Bus — generic engine list", "Bus — allgemeine Motorliste"),
    "1.0 turbo benzinli 110 hp": ("1.0 turbo petrol 110 hp", "1.0 Turbobenziner 110 PS"),
    "1.5 turbo benzinli 150 hp": ("1.5 turbo petrol 150 hp", "1.5 Turbobenziner 150 PS"),
    "2.0 turbo benzinli 190 hp": ("2.0 turbo petrol 190 hp", "2.0 Turbobenziner 190 PS"),
    "1.6 dizel 115 hp": ("1.6 diesel 115 hp", "1.6 Diesel 115 PS"),
    "2.0 dizel 150 hp": ("2.0 diesel 150 hp", "2.0 Diesel 150 PS"),
    "2.0 dizel 190 hp": ("2.0 diesel 190 hp", "2.0 Diesel 190 PS"),
}
