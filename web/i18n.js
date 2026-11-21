/* Arayüz çevirileri: Türkçe metin -> [English, Deutsch]. Sayfadaki sabit metinler otomatik çevrilir,
   koddaki metinler tt("...") ile çevrilir. */
const I18N = {
  // üst çubuk ve genel
  "ETS2 Bakım Simülatörü": ["ETS2 Maintenance Simulator", "ETS2 Wartungssimulator"],
  "Kilometre": ["Odometer", "Kilometerstand"], "Oyun saati": ["Game time", "Spielzeit"], "Konum": ["Location", "Standort"],
  "Dış hava": ["Outside air", "Außentemperatur"], "Bakım gideri": ["Service cost", "Wartungskosten"],
  "Bağlanıyor…": ["Connecting…", "Verbinde…"], "Oyun bekleniyor": ["Waiting for the game", "Warte auf das Spiel"],
  "Tema": ["Theme", "Design"],
  "EKLENTI_KUR.bat dosyasını bir kez çalıştırın (telemetri eklentisini ETS2 klasörüne kurar).": [
    "Run EKLENTI_KUR.bat once (it installs the telemetry plugin into the ETS2 folder).",
    "EKLENTI_KUR.bat einmal ausführen (installiert das Telemetrie-Plugin in den ETS2-Ordner)."],
  "Euro Truck Simulator 2'yi başlatın ve açılıştaki “Advanced SDK features” uyarısını OK ile onaylayın.": [
    "Start Euro Truck Simulator 2 and confirm the “Advanced SDK features” prompt with OK.",
    "Euro Truck Simulator 2 starten und den Hinweis „Advanced SDK features“ mit OK bestätigen."],
  "Profilinizi yükleyip kamyona binin; bu pencere otomatik olarak bağlanır.": [
    "Load your profile and get into the truck; this window connects automatically.",
    "Profil laden und in den Lkw steigen; dieses Fenster verbindet sich automatisch."],
  "Oyun olmadan denemek için DEMO.bat dosyasını çalıştırın.": ["To try it without the game, run DEMO.bat.", "Zum Testen ohne Spiel DEMO.bat ausführen."],
  "Oyun olmadan denemek için DEMO.bat dosyasını çalıştırın. Ayarlar sekmesi oyun beklenirken de kullanılabilir.": [
    "To try it without the game, run DEMO.bat. The Settings tab can be used while waiting for the game too.",
    "Zum Testen ohne Spiel DEMO.bat ausführen. Der Einstellungen-Tab ist auch beim Warten auf das Spiel nutzbar."],
  // sekmeler
  "Gösterge": ["Dashboard", "Übersicht"], "Yağ": ["Oil", "Öl"], "Soğutma": ["Cooling", "Kühlung"],
  "Akü & Elektrik": ["Battery & electrics", "Batterie & Elektrik"], "Motor Analizi": ["Engine analysis", "Motoranalyse"],
  "Yolculuk & Sürüş": ["Trip & driving", "Tour & Fahrt"], "Servis & Arızalar": ["Service & faults", "Service & Defekte"],
  "Ayarlar": ["Settings", "Einstellungen"],
  // gösterge
  "Devir": ["RPM", "Drehzahl"], "rpm": ["rpm", "U/min"], "Yük": ["Load", "Last"], "Vites": ["Gear", "Gang"], "Motor gücü / tork": ["Engine power / torque", "Motorleistung / Drehmoment"],
  "Anlık tüketim": ["Current consumption", "Momentanverbrauch"], "Soğutma suyu": ["Coolant", "Kühlmittel"], "termostat": ["thermostat", "Thermostat"],
  "Yağ sıcaklığı": ["Oil temperature", "Öltemperatur"], "Yağ basıncı": ["Oil pressure", "Öldruck"], "alt sınır": ["min.", "min."],
  "Akü voltajı": ["Battery voltage", "Batteriespannung"], "Fren sıcaklığı": ["Brake temperature", "Bremstemperatur"], "hava": ["air", "Luft"],
  "Bakım durumu": ["Maintenance status", "Wartungszustand"], "Yağ ömrü": ["Oil life", "Öllebensdauer"], "Yağ seviyesi": ["Oil level", "Ölstand"],
  "Antifriz koruması": ["Antifreeze protection", "Frostschutz"], "beklenen en düşük": ["expected low", "erwartetes Minimum"],
  "Soğutma suyu seviyesi": ["Coolant level", "Kühlmittelstand"], "Akü şarjı / sağlığı": ["Battery charge / health", "Batterieladung / -zustand"],
  "marş": ["cranking", "Anlassen"], "DPF doluluğu": ["DPF load", "DPF-Beladung"], "kül": ["ash", "Asche"], "Motor sağlığı": ["Engine health", "Motorzustand"],
  "aşınma hızı": ["wear rate", "Verschleißrate"],
  "Son 30 dakika": ["Last 30 minutes", "Letzte 30 Minuten"],
  // yağ
  "Motor yağı": ["Engine oil", "Motoröl"], "Kalan ömür": ["Remaining life", "Restlebensdauer"], "Sınırlayan": ["Limited by", "Begrenzt durch"],
  "Bu yağla gidilen": ["Distance on this oil", "Strecke mit diesem Öl"], "Motor saati (bu yağla)": ["Engine hours (this oil)", "Motorstunden (dieses Öl)"],
  "Seviye": ["Level", "Stand"], "Basınç (şu an)": ["Pressure (now)", "Druck (aktuell)"], "Viskozite şu an / 100 °C": ["Viscosity now / 100 °C", "Viskosität aktuell / 100 °C"],
  "Yağ filtresi doluluğu": ["Oil filter load", "Ölfilterbeladung"], "Bu yağla tüketim": ["Consumption on this oil", "Verbrauch mit diesem Öl"],
  "Ömrü belirleyen ölçütler": ["Oil life criteria", "Lebensdauer-Kriterien"],
  "Yağ, en kötü ölçütü sıfıra indiğinde ömrünü doldurur. Rölanti, kısa mesafe, soğuk motora yüklenme ve yüksek sıcaklık ömrü kısaltır.": [
    "The oil is worn out when its worst criterion reaches zero. Idling, short trips, loading a cold engine and high temperatures shorten its life.",
    "Das Öl ist verbraucht, wenn sein schlechtestes Kriterium null erreicht. Leerlauf, Kurzstrecken, Kaltlast und hohe Temperaturen verkürzen die Lebensdauer."],
  "Servis işlemleri": ["Service actions", "Wartungsarbeiten"], "kamyon durmuş ve motor kapalı olmalı": ["truck stopped, engine off", "Lkw steht, Motor aus"],
  "Yağ değişimi": ["Oil change", "Ölwechsel"], "Filtre de değişsin": ["Change filter too", "Filter mitwechseln"], "Yağı değiştir": ["Change oil", "Öl wechseln"],
  "Yağ ekle": ["Top up oil", "Öl nachfüllen"], "Ekle": ["Add", "Nachfüllen"], "Sadece filtre değiştir": ["Change filter only", "Nur Filter wechseln"],
  "Yağ numunesi al (analiz)": ["Take oil sample (analysis)", "Ölprobe nehmen (Analyse)"], "Yağ analizi raporu": ["Oil analysis report", "Ölanalyse-Bericht"],
  "Henüz analiz yok. “Yağ numunesi al” ile laboratuvar raporu alın.": ["No analysis yet. Use “Take oil sample” to get a lab report.", "Noch keine Analyse. Mit „Ölprobe nehmen“ einen Laborbericht erstellen."],
  // soğutma
  "Termostat": ["Thermostat", "Thermostat"], "83 °C açar, 95 °C tam açık": ["opens at 83 °C, fully open at 95 °C", "öffnet bei 83 °C, voll offen bei 95 °C"],
  "Fan": ["Fan", "Lüfter"], "95 °C'de ve retarderde devreye girer": ["engages at 95 °C and with the retarder", "schaltet bei 95 °C und mit Retarder zu"],
  "Sistem basıncı": ["System pressure", "Systemdruck"], "kaynama noktası": ["boiling point", "Siedepunkt"], "Donma noktası": ["Freezing point", "Gefrierpunkt"],
  "Buzlanma": ["Icing", "Vereisung"], "blok · radyatör": ["block · radiator", "Block · Kühler"], "Soğutma sıvısı": ["Coolant", "Kühlmittel"],
  "Antifriz oranı (glikol)": ["Antifreeze ratio (glycol)", "Frostschutzanteil (Glykol)"], "Korozyon inhibitörü": ["Corrosion inhibitor", "Korrosionsschutz"],
  "Kireç / korozyon birikimi": ["Scale / corrosion deposits", "Kalk- / Korrosionsablagerung"], "Yaşı": ["Age", "Alter"],
  "Bölgede beklenen en düşük sıcaklık": ["Expected low in this region", "Erwartete Tiefsttemperatur in der Region"],
  "%50 antifriz −37 °C'ye kadar korur. Saf su eklemek oranı düşürür, musluk suyu kireç yapar. Antifrizsiz su donunca blok ve radyatör çatlar.": [
    "50% antifreeze protects down to −37 °C. Adding water lowers the ratio, tap water causes scale. Plain water cracks the block and radiator when it freezes.",
    "50 % Frostschutz schützt bis −37 °C. Wasser nachfüllen senkt den Anteil, Leitungswasser verkalkt. Reines Wasser sprengt beim Gefrieren Block und Kühler."],
  "Sıvı değişimi": ["Coolant change", "Kühlmittelwechsel"], "Değiştir": ["Change", "Wechseln"], "Tamamla": ["Top up", "Nachfüllen"],
  "Refraktometre ile ölç": ["Measure with refractometer", "Mit Refraktometer messen"],
  // akü
  "Voltaj": ["Voltage", "Spannung"], "Akü akımı": ["Battery current", "Batteriestrom"], "+ şarj · − deşarj": ["+ charge · − discharge", "+ Laden · − Entladen"],
  "Elektrik yükü": ["Electrical load", "Elektrische Last"], "alternatör": ["alternator", "Lichtmaschine"], "Şarj durumu": ["State of charge", "Ladezustand"],
  "Akü sağlığı": ["Battery health", "Batteriezustand"], "sülfat": ["sulphation", "Sulfatierung"], "Tahmini marş voltajı": ["Estimated cranking voltage", "Geschätzte Anlassspannung"],
  "gereken en az şarj": ["min. charge needed", "nötige Mindestladung"], "Akü grubu": ["Battery pack", "Batteriesatz"],
  "2 x 12 V seri, 24 V sistem": ["2 x 12 V in series, 24 V system", "2 x 12 V in Reihe, 24-V-System"],
  "Kapasite / kullanılabilir": ["Capacity / usable", "Kapazität / nutzbar"], "Akü sıcaklığı": ["Battery temperature", "Batterietemperatur"],
  "Elektrolit donma noktası": ["Electrolyte freezing point", "Gefrierpunkt des Elektrolyts"], "Eşdeğer tam döngü": ["Equivalent full cycles", "Äquivalente Vollzyklen"],
  "%50'ye kalan süre (bu yükle)": ["Time to 50% (at this load)", "Zeit bis 50 % (bei dieser Last)"], "Şarj cihazı / takviye": ["Charger / jump start", "Ladegerät / Starthilfe"],
  "Kontak açıkken ~9 A, kısa farlar +6 A, tavan lambaları +5 A çekilir. Uykuda park ısıtıcısı/kliması da aküden beslenir. Soğukta yağ koyulaşır, marş akımı artar ve akü iç direnci yükselir.": [
    "Ignition on draws ~9 A, low beams +6 A, roof lights +5 A. While sleeping the parking heater/AC also runs off the battery. In the cold the oil thickens, cranking current rises and the battery's internal resistance increases.",
    "Zündung an zieht ~9 A, Abblendlicht +6 A, Dachleuchten +5 A. Im Schlaf läuft auch die Standheizung/-klima über die Batterie. Bei Kälte wird das Öl zäh, der Anlassstrom steigt und der Innenwiderstand der Batterie nimmt zu."],
  "Akü testi yap": ["Test battery", "Batterie testen"], "Şarj cihazı bağla": ["Connect charger", "Ladegerät anschließen"], "Şarj cihazını sök": ["Remove charger", "Ladegerät entfernen"],
  "Takviye kablosu bağla": ["Connect jumper cables", "Starthilfekabel anschließen"], "Akü değişimi": ["Battery replacement", "Batterietausch"],
  "Aküleri değiştir": ["Replace batteries", "Batterien tauschen"], "Aküyü değiştir": ["Replace battery", "Batterie tauschen"],
"Bağlı": ["Connected", "Angeschlossen"], "Yok": ["No", "Nein"],
  // motor analizi
  "Sürüş puanı": ["Driving score", "Fahrbewertung"], "Bu oturum": ["This session", "Diese Sitzung"], "Toplam": ["Total", "Gesamt"],
  "Eko bant (1000–1500 rpm), rölanti oranı, sert fren, lugging, aşırı devir, soğuk motora yüklenme ve hararetten hesaplanır.": [
    "Calculated from the eco band (1000–1500 rpm), idle share, harsh braking, lugging, over-revving, cold-engine load and overheating.",
    "Berechnet aus Eco-Bereich (1000–1500 U/min), Leerlaufanteil, starkem Bremsen, Untertourigkeit, Überdrehzahl, Kaltlast und Überhitzung."],
  "Devir x yük haritası": ["RPM x load map", "Drehzahl x Last"], "motorun hangi bölgede çalıştığı (dakika)": ["where the engine operates (minutes)", "Betriebsbereiche des Motors (Minuten)"],
  "DPF (partikül filtresi)": ["DPF (particulate filter)", "DPF (Partikelfilter)"], "İs doluluğu": ["Soot load", "Rußbeladung"], "Kül doluluğu": ["Ash load", "Aschebeladung"],
  "Rejenerasyon": ["Regeneration", "Regeneration"], "Rejenerasyon sayısı / son rejenden beri": ["Regenerations / since last", "Regenerationen / seit letzter"],
  "Egzoz karşı basıncı": ["Exhaust back pressure", "Abgasgegendruck"], "Servis rejenerasyonu": ["Workshop regeneration", "Werkstatt-Regeneration"],
  "DPF kül temizliği": ["DPF ash cleaning", "DPF-Ascheabreinigung"], "Simülasyon motor sağlığı": ["Simulated engine health", "Simulierter Motorzustand"],
  "Son dönem aşınma hızı": ["Recent wear rate", "Aktuelle Verschleißrate"], "Conta zorlanması / kilitlenme riski": ["Head gasket stress / seizure risk", "Kopfdichtungsbelastung / Festfressrisiko"],
  "Oyun hasarı: motor / şanzıman": ["Game damage: engine / transmission", "Spielschaden: Motor / Getriebe"],
  "Oyun hasarı: kabin / şasi / tekerlek": ["Game damage: cabin / chassis / wheels", "Spielschaden: Kabine / Fahrgestell / Räder"],
  "Motor tanımı": ["Engine definition", "Motordaten"], "Model / seçim": ["Model / selection", "Modell / Auswahl"], "Güç": ["Power", "Leistung"],
  "Tepe tork": ["Peak torque", "Max. Drehmoment"], "Hacim": ["Displacement", "Hubraum"], "Yağ / soğutma suyu kapasitesi": ["Oil / coolant capacity", "Öl- / Kühlmittelmenge"],
  "Toplam kütle (tahmini)": ["Gross weight (estimated)", "Gesamtgewicht (geschätzt)"],
  "Motor otomatik seçilir; Ayarlar sekmesinden değiştirebilirsiniz.": ["The engine is selected automatically; you can change it in Settings.", "Der Motor wird automatisch gewählt; Änderung in den Einstellungen."],
  "Uzun dönem trend": ["Long-term trend", "Langzeittrend"], "otomatik": ["automatic", "automatisch"], "elle": ["manual", "manuell"],
  // yolculuk
  "Bu yolculuk": ["This trip", "Diese Tour"], "Mesafe": ["Distance", "Strecke"], "Ortalama tüketim": ["Avg. consumption", "Ø Verbrauch"],
  "Yolculuğu sıfırla": ["Reset trip", "Tour zurücksetzen"], "Yeni bir iş aldığınızda yolculuk kendiliğinden sıfırlanır.": ["The trip resets automatically when you take a new job.", "Die Tour wird bei einem neuen Auftrag automatisch zurückgesetzt."],
  "Frenler": ["Brakes", "Bremsen"], "Hava basıncı": ["Air pressure", "Luftdruck"], "Fren enerjisi dağılımı (yolculuk)": ["Braking energy split (trip)", "Bremsenergie-Verteilung (Tour)"],
  "Servis freni": ["Service brake", "Betriebsbremse"], "Retarder": ["Retarder", "Retarder"], "Motor freni": ["Engine brake", "Motorbremse"],
  "Süre": ["Duration", "Dauer"], "Ortalama hız": ["Average speed", "Durchschnittstempo"], "Yakıt": ["Fuel", "Kraftstoff"],
  "Yakıt maliyeti": ["Fuel cost", "Kraftstoffkosten"], "CO₂ emisyonu": ["CO₂ emissions", "CO₂-Ausstoß"], "Rölanti (süre / yakıt)": ["Idling (time / fuel)", "Leerlauf (Zeit / Kraftstoff)"],
  "Hız sabitleyici": ["Cruise control", "Tempomat"], "Yakıtsız yuvarlanma": ["Coasting (fuel cut)", "Schubbetrieb"], "Retarder kullanımı": ["Retarder use", "Retardernutzung"],
  "Sert fren": ["Harsh braking", "Starkes Bremsen"], "Vites değişimi / 100 km": ["Gear shifts / 100 km", "Schaltvorgänge / 100 km"],
  "Ortalama yük / devir": ["Avg. load / rpm", "Ø Last / Drehzahl"], "En yüksek fren sıcaklığı": ["Peak brake temperature", "Max. Bremstemperatur"],
  "Hıza göre tüketim": ["Consumption by speed", "Verbrauch nach Tempo"], "Vites kullanımı": ["Gear usage", "Gangnutzung"],
  // servis
  "Bakım planı (tahmini)": ["Service plan (estimated)", "Wartungsplan (geschätzt)"], "Bakım gideri / 1000 km": ["Service cost / 1000 km", "Wartungskosten / 1000 km"],
  "Aktif arızalar": ["Active faults", "Aktive Defekte"], "Arıza yok.": ["No faults.", "Keine Defekte."], "Motor revizyonu": ["Engine overhaul", "Motorüberholung"],
  "Gömlek, piston, segman ve yataklar yenilenir; motor sağlığı %100 olur.": ["Liners, pistons, rings and bearings are renewed; engine health returns to 100%.", "Laufbuchsen, Kolben, Ringe und Lager werden erneuert; Motorzustand wieder 100 %."],
  "Servis ve olay kaydı": ["Service and event log", "Service- und Ereignisprotokoll"], "toplam bakım gideri": ["total service cost", "Wartungskosten gesamt"],
  "Km": ["Km", "Km"], "Olay": ["Event", "Ereignis"], "Tutar": ["Amount", "Betrag"], "Bakım": ["Service", "Wartung"], "Kalan": ["Remaining", "Verbleibend"],
  // ayarlar
  "Oyun içi katman": ["In-game overlay", "Spiel-Overlay"], "Durum": ["Status", "Status"], "Motoru durdurma yolu": ["Engine stop method", "Motor-Stopp-Methode"],
  "Kısayollar (oyunda)": ["Hotkeys (in game)", "Tastenkürzel (im Spiel)"], "Genel": ["General", "Allgemein"],
  "Uyarı düzeyi": ["Alert level", "Warnstufe"], "Az — yalnızca kritik": ["Low — critical only", "Gering — nur kritisch"],
  "Normal — kritik + dikkat": ["Normal — critical + warnings", "Normal — kritisch + Warnungen"], "Hepsi — bilgi mesajları dahil": ["All — including info messages", "Alle — inkl. Hinweise"],
  "Normal düzeyde ekran şeridi ve sesli ikaz yalnızca kritik durumlarda çıkar.": ["At normal level the on-screen banner and beep appear only for critical alerts.", "Auf Stufe Normal erscheinen Banner und Ton nur bei kritischen Warnungen."],
  "Sesli uyarı": ["Sound alert", "Warnton"],
  "Para birimi": ["Currency", "Währung"],
  "Gerçekçilik": ["Realism", "Realismus"],
  "Yedek motor tuşu": ["Fallback engine key", "Ersatz-Motortaste"], "Rastgele parça arızaları": ["Random component faults", "Zufällige Bauteildefekte"],
  "Alternatör, termostat, fan, pompa, conta, şanzıman soğutucusu, debriyaj aktüatörü, direksiyon pompası, ABS sensörü, marş motoru (km'ye bağlı)": [
    "Alternator, thermostat, fan, pump, gasket, gearbox cooler, clutch actuator, steering pump, ABS sensor, starter (by mileage)",
    "Lichtmaschine, Thermostat, Lüfter, Pumpe, Dichtung, Getriebeölkühler, Kupplungssteller, Lenkpumpe, ABS-Sensor, Anlasser (nach Laufleistung)"],
  "Uykuda park ısıtıcı/kliması": ["Parking heater/AC while sleeping", "Standheizung/-klima im Schlaf"],
  "Soğukta ısıtıcı, sıcakta klima aküden çeker": ["Heater in the cold, AC in the heat drain the battery", "Heizung bei Kälte, Klima bei Hitze belasten die Batterie"],
  "Oyunda tamirde otomatik bakım":["Auto service on in-game repair", "Auto-Wartung bei Reparatur im Spiel"],
  "Oyunda serviste tamir olunca yağ + filtre + antifriz tamamlansın": ["When repaired at an in-game service, also do oil + filter + coolant", "Bei Reparatur in der Spielwerkstatt auch Öl + Filter + Kühlmittel"],
  "İklim": ["Climate", "Klima"], "Mevsim kaynağı": ["Season source", "Jahreszeit-Quelle"], "Gerçek takvim (bugünün tarihi)": ["Real calendar (today's date)", "Echter Kalender (heutiges Datum)"],
  "Seçilen ay": ["Selected month", "Gewählter Monat"], "Sabit sıcaklık": ["Fixed temperature", "Feste Temperatur"], "Ay": ["Month", "Monat"],
  "Sabit sıcaklık (°C)": ["Fixed temperature (°C)", "Feste Temperatur (°C)"], "Hava değişkenliği": ["Weather variability", "Wetterschwankung"],
  "Günden güne ±3 °C sapma": ["±3 °C day-to-day variation", "±3 °C Schwankung von Tag zu Tag"],
  "Sıcaklık kamyonun gerçek enlem/boylamından (oyun koordinatlarından), oyun saatinden ve mevsimden hesaplanır.": [
    "The temperature is calculated from the truck's real latitude/longitude (game coordinates), the game clock and the season.",
    "Die Temperatur wird aus der echten Breite/Länge des Lkw (Spielkoordinaten), der Spieluhr und der Jahreszeit berechnet."],
  "Bu kamyonun motoru": ["This truck's engine", "Motor dieses Lkw"], "Algılanan model": ["Detected model", "Erkanntes Modell"], "Motor seçimi": ["Engine selection", "Motorwahl"],
  "Otomatik (modelden + sürüşten algıla)": ["Automatic (from model + driving)", "Automatisch (aus Modell + Fahrt)"], "Elle": ["Manual", "Manuell"], "Motor": ["Engine", "Motor"],
  "Listeden seçmek otomatik algılamayı kapatır.": ["Choosing from the list turns automatic detection off.", "Auswahl aus der Liste schaltet die automatische Erkennung aus."],
  "Sürüşten algılama": ["Detection from driving", "Erkennung aus der Fahrt"], "Yeniden algıla": ["Detect again", "Neu erkennen"], "Elle ayar": ["Manual values", "Manuelle Werte"],
  "kaydetmek motor seçimini “Elle” yapar": ["saving sets engine selection to “Manual”", "Speichern setzt die Motorwahl auf „Manuell“"],
  "Motor adı": ["Engine name", "Motorname"], "Güç (hp)": ["Power (hp)", "Leistung (PS)"], "Tepe tork (Nm)": ["Peak torque (Nm)", "Max. Drehmoment (Nm)"],
  "Nominal güç devri (rpm)": ["Rated speed (rpm)", "Nenndrehzahl (U/min)"], "Motor hacmi (L)": ["Displacement (L)", "Hubraum (L)"],
  "Yağ kapasitesi (L)": ["Oil capacity (L)", "Ölmenge (L)"], "Soğutma suyu kapasitesi (L)": ["Coolant capacity (L)", "Kühlmittelmenge (L)"],
  "Akü kapasitesi (Ah)": ["Battery capacity (Ah)", "Batteriekapazität (Ah)"], "DPF": ["DPF", "DPF"], "Euro VI (partikül filtresi var)": ["Euro VI (has particulate filter)", "Euro VI (mit Partikelfilter)"],
  "Elle değerleri kaydet": ["Save manual values", "Manuelle Werte speichern"],
  "Telemetri motor gücünü vermez. Otomatik modda önce kamyon modelinin yaygın motoru seçilir; ardından tam gazda, sabit viteste ve 1000–1450 rpm arasında birkaç saniye (ör. dolu yükle yokuş çıkarken) sürdüğünüzde vites oranları, tekerlek yarıçapı, ivme, yol eğimi ve yük kütlesinden motor torku ölçülür ve modelin motorları içinden en yakını seçilir.": [
    "Telemetry does not report engine power. In automatic mode the model's common engine is chosen first; then, after a few seconds at full throttle in a fixed gear between 1000–1450 rpm (e.g. climbing loaded), engine torque is measured from gear ratios, wheel radius, acceleration, road grade and mass, and the closest engine of the model is selected.",
    "Die Telemetrie liefert keine Motorleistung. Im Automatikmodus wird zuerst der übliche Motor des Modells gewählt; nach einigen Sekunden Vollgas in festem Gang zwischen 1000–1450 U/min (z. B. beladen bergauf) wird das Drehmoment aus Übersetzungen, Radradius, Beschleunigung, Steigung und Masse gemessen und der passendste Motor des Modells gewählt."],
  // durum etiketleri
  "Soğuk": ["Cold", "Kalt"], "Normal": ["Normal", "Normal"], "Yüksek": ["High", "Hoch"], "Kaynıyor": ["Boiling", "Kocht"], "Hararet": ["Overheating", "Überhitzt"],
  "Aşırı": ["Excessive", "Zu hoch"], "Motor kapalı": ["Engine off", "Motor aus"], "Düşük": ["Low", "Niedrig"], "Sınırda": ["Borderline", "Grenzwertig"],
  "Şarj ediyor": ["Charging", "Lädt"], "Zayıf şarj": ["Weak charging", "Schwache Ladung"], "Şarj yok": ["Not charging", "Keine Ladung"], "Dolu": ["Full", "Voll"],
  "Yarı dolu": ["Half", "Halb"], "Boş": ["Empty", "Leer"], "İyi": ["Good", "Gut"], "Değişim yakın": ["Change soon", "Wechsel bald"], "Değiştirin": ["Replace", "Ersetzen"],
  "Fazla": ["Overfilled", "Zu viel"], "MIN altı": ["Below MIN", "Unter MIN"], "Kritik": ["Critical", "Kritisch"], "Donuyor": ["Freezing", "Gefriert"],
  "Yetersiz": ["Insufficient", "Unzureichend"], "Yeterli": ["Sufficient", "Ausreichend"], "Azalıyor": ["Depleting", "Nimmt ab"], "Tükendi": ["Depleted", "Verbraucht"],
  "Çok düşük": ["Very low", "Sehr niedrig"], "Yıpranmış": ["Worn", "Verschlissen"], "DPF yok": ["No DPF", "Kein DPF"], "Rejenerasyon ": ["Regenerating", "Regeneriert"],
  "Tıkalı": ["Blocked", "Verstopft"], "Temizlik yakın": ["Cleaning soon", "Reinigung bald"], "Temizlik gerekli": ["Cleaning needed", "Reinigung nötig"],
  "Revizyon": ["Overhaul", "Überholung"], "Sıcak": ["Hot", "Heiß"],
  "Dikkat": ["Warning", "Achtung"], "Bilgi": ["Info", "Hinweis"], "normal": ["normal", "normal"], "dikkat": ["caution", "Achtung"], "kritik": ["critical", "kritisch"],
  // uygulama içi
  "Veri toplanıyor…": ["Collecting data…", "Sammle Daten…"], "Henüz motor çalışma verisi yok.": ["No engine data yet.", "Noch keine Motordaten."],
  "şu an": ["now", "aktuell"], "şimdi": ["now", "jetzt"], "dk": ["min", "min"], "sa": ["h", "h"], "gün": ["days", "Tage"],
  "Sıcaklıklar": ["Temperatures", "Temperaturen"], "Dış hava ": ["Outside air", "Außenluft"], "Yağ ": ["Oil", "Öl"], "Devir ": ["RPM", "Drehzahl"],
  "Motor devri": ["Engine speed", "Motordrehzahl"], "Akım": ["Current", "Strom"], "Şarj": ["Charge", "Ladung"], "Sağlık": ["Health", "Zustand"],
  "Akü akımı (+ şarj / − deşarj)": ["Battery current (+ charge / − discharge)", "Batteriestrom (+ Laden / − Entladen)"],
  "Yağda demir (Fe)": ["Iron in oil (Fe)", "Eisen im Öl (Fe)"], "Akü sağlığı ": ["Battery health", "Batteriezustand"],
  "Motor çalışma süresi": ["Engine running time", "Motorlaufzeit"], "Sürüş süresi": ["Driving time", "Fahrzeit"], "Eko bant (1000–1500 rpm)": ["Eco band (1000–1500 rpm)", "Eco-Bereich (1000–1500 U/min)"],
  "Rölanti oranı": ["Idle share", "Leerlaufanteil"], "Lugging (düşük devir tam yük)": ["Lugging (full load at low rpm)", "Untertourig (Volllast)"],
  "Aşırı devir olayı": ["Over-rev events", "Überdrehzahl-Ereignisse"], "Soğuk motora yüklenme": ["Cold engine load", "Kaltlast"], "Hararet süresi (>103 °C)": ["Overheating time (>103 °C)", "Überhitzungszeit (>103 °C)"],
  "Marş / soğuk / başarısız": ["Starts / cold / failed", "Starts / kalt / fehlgeschlagen"], "En yüksek su / yağ sıcaklığı": ["Peak coolant / oil temp.", "Max. Kühlmittel- / Öltemp."],
  "Rejenerasyon sürüyor": ["Regeneration running", "Regeneration läuft"], "Rejenerasyon bekliyor (40 km/h üstü sürüş)": ["Regeneration pending (drive above 40 km/h)", "Regeneration ausstehend (über 40 km/h fahren)"],
  "Parametre": ["Parameter", "Parameter"], "Sonuç": ["Result", "Ergebnis"], "Değerlendirme": ["Assessment", "Bewertung"], "Laboratuvar yorumu": ["Lab comments", "Laborkommentar"],
  "uyarı daha": ["more alerts", "weitere Warnungen"], "Daha az göster": ["Show less", "Weniger anzeigen"], "gizli": ["hidden", "ausgeblendet"],
  "Oyundaki serviste parça tamiri": ["Part repair at in-game service", "Teilereparatur in der Spielwerkstatt"],
  "Oyunda servis noktasında tamir yaptırınca arızalı parçalar (alternatör, termostat, conta…) da onarılsın": [
    "When you repair at an in-game service point, broken parts (alternator, thermostat, gasket…) are repaired too",
    "Bei einer Reparatur in der Spielwerkstatt werden defekte Teile (Lichtmaschine, Thermostat, Dichtung…) mit repariert"],
  "Oyun yalnızca hasar varken tamire izin verir; oyun hasarı %0 ise Alt+F8 servis menüsünü kullanın.": [
    "The game only allows repairs when there is damage; if game damage is 0%, use the Alt+F8 service menu.",
    "Das Spiel erlaubt Reparaturen nur bei Schaden; bei 0 % Spielschaden das Servicemenü mit Alt+F8 nutzen."],
  "Tek oyunculu": ["Singleplayer", "Einzelspieler"], "Çok oyunculu": ["Multiplayer", "Mehrspieler"],
  "Konvoy": ["Convoy", "Konvoi"], "TruckersMP": ["TruckersMP", "TruckersMP"],
  "Sunucu kapalı": ["Server offline", "Server offline"], "DEMO": ["DEMO", "DEMO"], "Oyun duraklatıldı": ["Game paused", "Spiel pausiert"], "Oyuna bağlı": ["Connected to game", "Mit Spiel verbunden"],
  "MOTOR DURDU": ["ENGINE STOPPED", "MOTOR AUS"], "yakını": ["near", "bei"], "Kamyon": ["Truck", "Lkw"],
  "Aküleri değiştirin": ["Replace batteries", "Batterien tauschen"], "Onar": ["Repair", "Reparieren"],
  "Motor revizyonu yaklaşık {cost} tutar. Devam edilsin mi?": ["An engine overhaul costs about {cost}. Continue?", "Eine Motorüberholung kostet etwa {cost}. Fortfahren?"],
  "onarımı": ["repair costs", "Reparatur kostet"], "Devam?": ["Continue?", "Fortfahren?"], "Özel (elle girilen değerler)": ["Custom (manual values)", "Benutzerdefiniert (manuell)"],
  "Model tanınmadığı için motor listesi yok.": ["No engine list because the model was not recognised.", "Keine Motorliste, da das Modell nicht erkannt wurde."],
  "Örnek toplanıyor": ["Collecting samples", "Sammle Messwerte"], "Tam gazda, sabit viteste, 1000–1450 rpm aralığında sürün (dolu yükle yokuş idealdir).": [
    "Drive at full throttle in a fixed gear between 1000–1450 rpm (a loaded climb is ideal).", "Mit Vollgas in festem Gang zwischen 1000–1450 U/min fahren (beladen bergauf ist ideal)."],
  "Ölçülen tepe tork": ["Measured peak torque", "Gemessenes max. Drehmoment"], "örnek": ["samples", "Messwerte"], "en yakın": ["closest", "am nächsten"],
  "güvenilir": ["reliable", "zuverlässig"], "henüz kesin değil, ölçüm sürüyor": ["not certain yet, measuring", "noch unsicher, Messung läuft"],
  "(elle modda uygulanmaz)": ["(not applied in manual mode)", "(im manuellen Modus nicht angewendet)"],
  "Oyunda çalışıyor": ["Running in game", "Läuft im Spiel"], "Oyunda yüklü değil ya da oyun kapalı (EKLENTI_KUR.bat ile kurun; oyun DirectX 11 ile çalışmalı).": [
    "Not loaded in the game or the game is closed (install with EKLENTI_KUR.bat; the game must run with DirectX 11).",
    "Nicht im Spiel geladen oder Spiel geschlossen (mit EKLENTI_KUR.bat installieren; das Spiel muss mit DirectX 11 laufen)."],
  "Oyunun resmi giriş cihazı (kontağı kapat)": ["Game's official input device (ignition off)", "Offizielles Eingabegerät des Spiels (Zündung aus)"],
  "aktif": ["active", "aktiv"], "oyun odakta değil": ["game not focused", "Spiel nicht im Fokus"],
  "Yedek yöntem: oyuna tuş gönderilir (yalnızca oyun penceresi öndeyken).": ["Fallback: a key is sent to the game (only while the game window is in front).", "Ersatz: eine Taste wird ans Spiel gesendet (nur wenn das Spielfenster vorne ist)."],
  "kapalı → kompakt → detaylı": ["off → compact → detailed", "aus → kompakt → detailliert"], "sonraki sayfa": ["next page", "nächste Seite"],
  "köşe değiştir (sol üst → sağ üst → sağ alt → sol alt)": ["change corner (top left → top right → bottom right → bottom left)", "Ecke wechseln (oben links → oben rechts → unten rechts → unten links)"],
  "servis menüsü (yağ, antifriz, akü, DPF, onarım)": ["service menu (oil, antifreeze, battery, DPF, repair)", "Servicemenü (Öl, Frostschutz, Batterie, DPF, Reparatur)"],
  "boyut": ["size", "Größe"],
  "Son ölçüm": ["Last reading", "Letzte Messung"], "antifriz": ["antifreeze", "Frostschutz"], "donma": ["freezes at", "Gefrierpunkt"], "inhibitör": ["inhibitor", "Inhibitor"],
  "kireç": ["scale", "Kalk"], "Son test": ["Last test", "Letzter Test"], "boşta": ["at rest", "Ruhespannung"], "şarj": ["charge", "Ladung"], "sağlık": ["health", "Zustand"],
  "iç direnç": ["internal resistance", "Innenwiderstand"], "marş tahmini": ["cranking estimate", "Anlass-Schätzung"], "döngü": ["cycles", "Zyklen"],
  "Devrede": ["Engaged", "Ein"], "Kapalı": ["Off", "Aus"],
  "Bu tırın değerlerini sıfırla": ["Reset this truck's values", "Werte dieses Lkw zurücksetzen"],
  "Başka bir tıra geçtiyseniz ya da baştan başlamak istiyorsanız; bu tırın tüm bakım kaydı silinir.": [
    "If you switched to another truck or want to start over; this truck's whole maintenance record is deleted.",
    "Wenn Sie den Lkw gewechselt haben oder neu beginnen möchten; die gesamte Wartungshistorie dieses Lkw wird gelöscht."],
  "Bu tırın tüm bakım değerleri ve kaydı silinip baştan başlanacak. Devam edilsin mi?": [
    "All maintenance values and the log of this truck will be deleted and start fresh. Continue?",
    "Alle Wartungswerte und das Protokoll dieses Lkw werden gelöscht und neu begonnen. Fortfahren?"],
  "Hızlı iş tırları": ["Quick job trucks", "Lkw aus Schnellaufträgen"],
  "Oyunda HUD gizlenince (F3) katman da gizlensin": ["Hide the overlay when the game HUD is hidden (F3)", "Overlay ausblenden, wenn das Spiel-HUD ausgeblendet wird (F3)"],
  "Oyunun verdiği geçici tırın değerleri teslimatta sıfırlansın": ["Reset the values of the game's temporary truck on delivery", "Werte des Leih-Lkw des Spiels bei Lieferung zurücksetzen"],
  "geçici tır (hızlı iş)": ["temporary truck (quick job)", "Leih-Lkw (Schnellauftrag)"],
  "Akıllı Uygulama Denetimi açık: imzasız katman DLL'i oyunda engelleniyor. Simülatör, bu pencere ve motor durdurma (tuş yöntemi) çalışır. Katman için DLL'in güvenilir bir sertifikayla imzalanması ya da denetimin kapatılması gerekir (README).": [
    "Smart App Control is on: the unsigned overlay DLL is blocked in the game. The simulator, this window and engine stop (key method) still work. The overlay needs the DLL signed with a trusted certificate, or Smart App Control turned off (README).",
    "Intelligente App-Steuerung ist aktiv: Die unsignierte Overlay-DLL wird im Spiel blockiert. Simulator, dieses Fenster und Motorstopp (Tastenmethode) funktionieren weiter. Für das Overlay muss die DLL mit einem vertrauenswürdigen Zertifikat signiert oder die App-Steuerung ausgeschaltet werden (README)."],
  "Akıllı Uygulama Denetimi açık: imzasız katman oyuna kurulmadı (engellenirdi). Simülatör, bu pencere ve motor durdurma (tuş yöntemi) çalışır.": [
    "Smart App Control is on: the unsigned overlay was not installed in the game (it would be blocked). The simulator, this window and engine stop (key method) still work.",
    "Intelligente App-Steuerung ist aktiv: Das unsignierte Overlay wurde nicht im Spiel installiert (es würde blockiert). Simulator, dieses Fenster und Motorstopp (Tastenmethode) funktionieren weiter."],
  "Ön ısıtma (kızdırma)": ["Preheating (glow)", "Vorglühen"],
  "Akü tipi": ["Battery type", "Batterietyp"],
  "Kaplama ön dingile takılmaz": ["Retreads not allowed on the front axle", "Runderneuerte nicht an der Vorderachse"],
  "Oyundan okunan": ["Read from the game", "Aus dem Spiel gelesen"],
  "Oyunda para birimini değiştirirseniz en geç bir sonraki oyun açılışında burası da güncellenir.": [
    "If you change the currency in the game, this updates by the next game start at the latest.",
    "Wenn Sie die Währung im Spiel ändern, wird dies spätestens beim nächsten Spielstart übernommen."],
  "Otomatik — oyunda seçili para birimi ve oyunun kuru": ["Automatic — currency selected in the game, at the game's rate", "Automatisch — im Spiel gewählte Währung zum Spielkurs"],
  "Simge": ["Symbol", "Symbol"], "Kur (1 € =)": ["Rate (1 € =)", "Kurs (1 € =)"],
  "Yakıt fiyatı (€ / litre)": ["Fuel price (€ / litre)", "Kraftstoffpreis (€ / Liter)"],
  "Lastik patlaması": ["Tyre blowout", "Reifenplatzer"],
  "Oyunda ani sürüklenme, kayma ve jant sürtmesi (fren ve direksiyona etki)": [
    "Sudden drag, skid and rim scraping in the game (acts on brake and steering)",
    "Plötzliches Abbremsen, Schlingern und Felgenschleifen im Spiel (wirkt auf Bremse und Lenkung)"],
  "Yalnızca tek oyunculuda ve oyun içi katman kuruluyken çalışır; çok oyunculuda hiç uygulanmaz.": [
    "Only in singleplayer and with the in-game overlay installed; never applied in multiplayer.",
    "Nur im Einzelspieler und mit installiertem Overlay; im Mehrspieler nie angewendet."],
  // lastikler, yakıt, AdBlue
  "Lastik & Yakıt": ["Tyres & fuel", "Reifen & Kraftstoff"], "Lastikler": ["Tyres", "Reifen"], "AdBlue": ["AdBlue", "AdBlue"],
  "menzil": ["range", "Reichweite"], "en düşük basınç": ["lowest pressure", "niedrigster Druck"],
  "diş derinliği · ayar / şu anki basınç · sıcaklık": ["tread depth · set / current pressure · temperature", "Profiltiefe · Soll-/Istdruck · Temperatur"],
  "Dingil": ["Axle", "Achse"], "Diş": ["Tread", "Profil"], "Basınç (ayar / şu an)": ["Pressure (set / now)", "Druck (Soll / Ist)"],
  "Sıcaklık": ["Temperature", "Temperatur"], "Bu lastiklerle": ["On these tyres", "Mit diesen Reifen"],
  "Oyundaki tekerlek hasarı": ["In-game wheel damage", "Radschaden im Spiel"],
  "Yasal en az diş derinliği 1,6 mm; ön lastikler 4 mm'de, arka lastikler 3 mm'de değiştirilmeli. Basınç soğuk lastikte ayarlanır (ön 9,0 bar, arka 8,5 bar); sıcak lastikte ~%10 yükselir. Düşük basınç lastiği ısıtır, omuzlarından aşındırır ve patlama riskini artırır. Toprak/çakıl yolda aşınma 2 kat, patlak 3 kat artar. Oyunda serviste tekerlek hasarı onarılınca lastikler de yenilenir.": [
    "Legal minimum tread depth is 1.6 mm; replace front tyres at 4 mm and rear tyres at 3 mm. Pressure is set on cold tyres (front 9.0 bar, rear 8.5 bar); hot tyres read ~10% higher. Low pressure heats the tyre, wears the shoulders and raises the risk of a blowout. On dirt/gravel wear doubles and punctures triple. When the in-game service repairs wheel damage, the tyres are renewed too.",
    "Gesetzliche Mindestprofiltiefe 1,6 mm; Vorderreifen bei 4 mm, Hinterreifen bei 3 mm wechseln. Der Druck wird am kalten Reifen eingestellt (vorn 9,0 bar, hinten 8,5 bar); warm liegt er ~10 % höher. Zu niedriger Druck erhitzt den Reifen, verschleißt die Schultern und erhöht das Platzrisiko. Auf Schotter/Erde doppelter Verschleiß, dreimal mehr Pannen. Repariert der Spiel-Service den Radschaden, werden auch die Reifen erneuert."],
  "Basınçları ayarla": ["Set pressures", "Druck einstellen"], "Patlağı tamir et": ["Repair puncture", "Panne reparieren"],
  "Lastik değişimi": ["Tyre replacement", "Reifenwechsel"], "Lastikleri değiştir": ["Replace tyres", "Reifen wechseln"],
  "Depo": ["Tank", "Tank"], "Menzil (ölçülen tüketimle)": ["Range (measured consumption)", "Reichweite (gemessener Verbrauch)"],
  "Uzun dönem ortalama": ["Long-term average", "Langzeitdurchschnitt"], "Menzil": ["Range", "Reichweite"],
  "SCR katalizörü için %32,5 üre": ["32.5% urea for the SCR catalyst", "32,5 % Harnstoff für den SCR-Katalysator"],
  "Püskürtme (yakıta oranla)": ["Dosing (relative to fuel)", "Dosierung (bezogen auf Kraftstoff)"],
  "Toplam kullanılan": ["Total used", "Gesamt verbraucht"], "AdBlue tamamla": ["Top up AdBlue", "AdBlue auffüllen"],
  "Oyun AdBlue'yu harcamaz; tüketimi simülatör hesaplar (yakıtın ~%3–7'si, yük arttıkça daha çok). Oyunda yakıt alınca AdBlue da tamamlanır (Ayarlar). Depo boşalınca gerçek araçta motor gücü düşer ve yeniden çalıştırmada hız 20 km/h ile sınırlanır. AdBlue −11 °C'de donar.": [
    "The game does not consume AdBlue; the simulator calculates it (~3–7% of fuel, more under load). It is topped up when you refuel in the game (Settings). When the tank runs dry a real truck cuts engine power and limits speed to 20 km/h after a restart. AdBlue freezes at −11 °C.",
    "Das Spiel verbraucht kein AdBlue; der Simulator berechnet es (~3–7 % des Kraftstoffs, unter Last mehr). Beim Tanken im Spiel wird es aufgefüllt (Einstellungen). Bei leerem Tank reduziert ein echter Lkw die Leistung und begrenzt nach dem Neustart auf 20 km/h. AdBlue gefriert bei −11 °C."],
  "Oyunda yakıt alınca AdBlue da tamamlansın": ["Top up AdBlue when refuelling in the game", "Beim Tanken im Spiel auch AdBlue auffüllen"],
  "Bitmek üzere": ["Almost empty", "Fast leer"], "Az": ["Low", "Niedrig"], "SCR yok": ["No SCR", "Kein SCR"], "Bitti": ["Empty", "Leer"],
  "Patladı": ["Blown", "Geplatzt"], "Yavaş patlak": ["Slow puncture", "Schleichende Panne"], "Kaldırılmış": ["Lifted", "Angehoben"],
  "Diş yasal sınırın altında": ["Tread below legal limit", "Profil unter gesetzlicher Grenze"],
  "Basınç çok düşük": ["Pressure very low", "Druck sehr niedrig"], "Aşırı sıcak": ["Overheated", "Überhitzt"],
  "Diş azaldı": ["Tread low", "Profil knapp"], "Basınç ayarsız": ["Pressure off", "Druck falsch"],
  "Tüm lastikler": ["All tyres", "Alle Reifen"], "adet": ["pcs", "Stk."],
  "İzleme modu": ["Watch mode", "Überwachungsmodus"],
  "Sadece gösterme — değerler ve uyarılar, motora dokunulmaz": ["Display only — values and warnings, the engine is never touched", "Nur Anzeige — Werte und Warnungen, der Motor bleibt unberührt"],
  "Tam izleme — uyarılar + arızada motor durdurulur": ["Full monitoring — warnings + engine stopped on failure", "Volle Überwachung — Warnungen + Motorstopp bei Defekt"],
  "Tam izlemede motor, trafikte tehlike yaratmamak için tır 10 km/h altına inince durdurulur; o zamana kadar uyarı verilir. Kontak ve ışıklar açık kalır.": [
    "In full monitoring the engine is stopped only once the truck is below 10 km/h, so it does not endanger traffic; until then a warning is shown. Ignition and lights stay on.",
    "Bei voller Überwachung wird der Motor erst unter 10 km/h abgestellt, um den Verkehr nicht zu gefährden; bis dahin erscheint eine Warnung. Zündung und Licht bleiben an."],
  "Motor durdurma": ["Engine stop", "Motorstopp"],
  "Akü bitince, motor kilitlenince vb. yalnızca motor durdurulur; kontak ve ekranlar açık kalır.": [
    "When the battery is flat, the engine seizes etc., only the engine is stopped; ignition and screens stay on.",
    "Bei leerer Batterie, festgefressenem Motor usw. wird nur der Motor abgestellt; Zündung und Bildschirme bleiben an."],
  "Çok oyunculu oturum (TruckersMP, Konvoy) algılanırsa motor güvenlik için durdurulmaz, yalnızca uyarı verilir; oyun modu Otomatik iken uygulama Çok Oyunculu moda kendisi geçer.": [
    "If a multiplayer session (TruckersMP, Convoy) is detected, the engine is not stopped for safety, only warnings are shown; with game mode Automatic the app switches to Multiplayer mode by itself.",
    "Wird eine Mehrspieler-Sitzung (TruckersMP, Konvoi) erkannt, wird der Motor aus Sicherheitsgründen nicht abgestellt, nur gewarnt; im Spielmodus Automatisch wechselt die App selbst in den Mehrspielermodus."],
  "Oyun modu": ["Game mode", "Spielmodus"], "tek ve çok oyunculu aynı uygulamada": ["single and multiplayer in one app", "Einzel- und Mehrspieler in einer App"],
  "Mod seçimi": ["Mode", "Modus"], "Şu anki mod": ["Current mode", "Aktueller Modus"],
  "Otomatik — TruckersMP / Konvoy algılanınca Çok Oyunculu": ["Automatic — Multiplayer when TruckersMP / Convoy is detected", "Automatisch — Mehrspieler, sobald TruckersMP / Konvoi erkannt wird"],
  "Tek Oyunculu — tam gerçekçilik, gerekirse motor durdurulur": ["Singleplayer — full realism, the engine is stopped when needed", "Einzelspieler — volle Realistik, Motor wird bei Bedarf abgestellt"],
  "Çok Oyunculu — motor zorla durdurulmaz": ["Multiplayer — the engine is never force-stopped", "Mehrspieler — der Motor wird nie zwangsweise abgestellt"],
  "Tek ve Çok Oyunculu modun ayarları ve tır bakım kayıtları ayrı tutulur: bu sayfada şu anki modun ayarlarını değiştirirsiniz. Dil ve oyun modu iki modda ortaktır. Çok Oyunculu modda sürüş modları varsayılan olarak kapalıdır.": [
    "Singleplayer and Multiplayer mode keep their own settings and truck maintenance records: this page changes the settings of the current mode. Language and game mode are shared by both. In Multiplayer mode the drive modes are off by default.",
    "Einzel- und Mehrspielermodus haben eigene Einstellungen und Wartungsdaten der Lkw: Diese Seite ändert die Einstellungen des aktuellen Modus. Sprache und Spielmodus gelten für beide. Im Mehrspielermodus sind die Fahrmodi standardmäßig aus."],
  "Tek Oyunculu": ["Singleplayer", "Einzelspieler"], "Çok Oyunculu": ["Multiplayer", "Mehrspieler"],
  "otomatik seçildi": ["chosen automatically", "automatisch gewählt"], "algılandı": ["detected", "erkannt"],
  "Tam izleme: arızada motor durdurulur": ["Full monitoring: engine stopped on failure", "Volle Überwachung: Motorstopp bei Defekt"],
  "Sadece gösterme: motor durdurulmaz (yalnızca uyarı)": ["Display only: engine not stopped (warnings only)", "Nur Anzeige: kein Motorstopp (nur Warnungen)"],
  "Gösterge lambaları": ["Warning lamps", "Warnleuchten"],
  "Sorunlar katmanın alt ortasında ikaz lambası olarak yansın": ["Show problems as warning lamps at the bottom centre of the overlay", "Probleme als Warnleuchten unten in der Mitte des Overlays anzeigen"],
  "Oyunun kendi gösterge panelindeki lambalar oyunun iç değerlerine bağlıdır ve dışarıdan yakılamaz; bu yüzden simülatörün ikazları katmanda gerçek gösterge gibi lamba olarak gösterilir. Sarı: dikkat/bakım, kırmızı: hemen müdahale.": [
    "The lamps on the game's own instrument cluster follow the game's internal values and cannot be switched on from outside, so the simulator's warnings are shown as lamps in the overlay. Amber: attention/service, red: act now.",
    "Die Leuchten im Kombiinstrument des Spiels hängen von spielinternen Werten ab und lassen sich nicht von außen einschalten; daher zeigt das Overlay die Warnungen des Simulators als Leuchten. Gelb: Achtung/Wartung, Rot: sofort handeln."],
  // azalma hızları
  "Azalma hızları": ["Wear rates", "Verschleißraten"],
  "1× gerçekçi · 0,5× yarı hızda (iki kat uzun dayanır) · 5× beş kat hızlı · 0× hiç azalmaz": [
    "1× realistic · 0.5× half speed (lasts twice as long) · 5× five times as fast · 0× never decreases",
    "1× realistisch · 0,5× halbe Geschwindigkeit (hält doppelt so lange) · 5× fünfmal so schnell · 0× nimmt nie ab"],
  "Gerçekçi (hepsi 1×)": ["Realistic (all 1×)", "Realistisch (alle 1×)"],
  "Kolay (genel 0,5×)": ["Easy (overall 0.5×)", "Leicht (gesamt 0,5×)"],
  "Çok kolay (genel 0,25×)": ["Very easy (overall 0.25×)", "Sehr leicht (gesamt 0,25×)"],
  "Zor (genel 2×)": ["Hard (overall 2×)", "Schwer (gesamt 2×)"],
  "Çok zor (genel 5×)": ["Very hard (overall 5×)", "Sehr schwer (gesamt 5×)"],
  "Kritik sesi dinle": ["Play critical sound", "Kritischen Ton abspielen"], "Dikkat sesi dinle": ["Play warning sound", "Warnton abspielen"],
  // sürüş modu
  "Sürüş modu": ["Drive mode", "Fahrmodus"],
  "oyun içi katman gaz pedalını seçilen moda göre ayarlar": ["the in-game overlay adjusts the throttle to the selected mode",
    "das Overlay passt das Gaspedal an den gewählten Modus an"],
  "Sürüş modları": ["Drive modes", "Fahrmodi"],
  "Açık (kapalıyken gaz pedalına hiç karışılmaz)": ["On (when off, the throttle is never touched)",
    "An (ausgeschaltet wird das Gaspedal nie verändert)"],
  "Mod değiştirme tuşu": ["Mode switch key", "Taste für Moduswechsel"],
  "Tuş ata": ["Assign key", "Taste zuweisen"], "Kaldır": ["Remove", "Entfernen"], "İptal": ["Cancel", "Abbrechen"],
  "tuşa basın…": ["press a key…", "Taste drücken…"], "tıklayın: sonraki mod": ["click: next mode", "klicken: nächster Modus"],
  "Katman tuşu": ["Overlay key", "Overlay-Taste"], "Varsayılan (F8)": ["Default (F8)", "Standard (F8)"],
  "“Tuş ata”ya basıp klavyede bir tuşa basın (10 sn, Esc iptal). Katmanın bütün kısayolları bu tuşla çalışır: tek başına görünüm, Shift ile sayfa, Ctrl ile köşe, Alt ile servis menüsü. Sürüş modu ve çekim modu tuşlarıyla aynı olamaz.": [
    "Press “Assign key”, then a key on the keyboard (10 s, Esc cancels). All overlay shortcuts use this key: alone for the view, with Shift for the page, Ctrl for the corner, Alt for the service menu. It cannot be the drive mode or filming mode key.",
    "„Taste zuweisen“ drücken, dann eine Taste auf der Tastatur (10 s, Esc bricht ab). Alle Overlay-Kürzel nutzen diese Taste: allein für die Ansicht, mit Shift für die Seite, Strg für die Ecke, Alt für das Servicemenü. Sie darf nicht die Fahrmodus- oder Aufnahmemodus-Taste sein."],
  "Oyun içi panel": ["In-game panel", "Panel im Spiel"],
  // değer güncelleme sıklığı (1.3.2)
  "Değer güncelleme sıklığı": ["Value update rate", "Aktualisierungsrate der Werte"],
  "değerlerin ne sıklıkla yenileneceği": ["how often the values are refreshed", "wie oft die Werte aktualisiert werden"],
  "Uygulama penceresi": ["App window", "App-Fenster"],
  "Gerçek zamanlı (0 sn) — saniyede 20 kez": ["Real time (0 s) — 20 times per second", "Echtzeit (0 s) — 20-mal pro Sekunde"],
  "0,1 sn — saniyede 10 kez": ["0.1 s — 10 times per second", "0,1 s — 10-mal pro Sekunde"],
  "0,1 sn — saniyede 10 kez (varsayılan)": ["0.1 s — 10 times per second (default)", "0,1 s — 10-mal pro Sekunde (Standard)"],
  "0,25 sn — saniyede 4 kez": ["0.25 s — 4 times per second", "0,25 s — 4-mal pro Sekunde"],
  "0,25 sn — saniyede 4 kez (varsayılan)": ["0.25 s — 4 times per second (default)", "0,25 s — 4-mal pro Sekunde (Standard)"],
  "0,5 sn": ["0.5 s", "0,5 s"], "1 sn": ["1 s", "1 s"], "2 sn": ["2 s", "2 s"], "5 sn": ["5 s", "5 s"],
  "Gerçek zamanlıda simülasyon saniyede 20 adım çalışır ve her adım hemen gösterilir; aralık uzadıkça bilgisayar daha az çalışır. Uyarılar, ikaz lambaları ve uyarı sesleri seçilen aralığı beklemez, hemen gelir. Pencere simge durumuna küçültülünce değerler yenilenmez (bilgisayar boşuna çalışmaz); pencere açılınca hemen güncellenir. Bu ayar Tek ve Çok Oyunculu modda ortaktır.": [
    "In real time the simulation runs 20 steps per second and every step is shown at once; longer intervals put less load on the computer. Warnings, warning lamps and warning sounds never wait for the interval, they appear immediately. While the window is minimised the values are not refreshed (no wasted work); they update as soon as the window is restored. This setting is shared by Singleplayer and Multiplayer mode.",
    "In Echtzeit rechnet die Simulation 20 Schritte pro Sekunde und zeigt jeden Schritt sofort an; längere Abstände entlasten den Computer. Warnungen, Warnleuchten und Warntöne warten nie auf den Abstand, sie erscheinen sofort. Solange das Fenster minimiert ist, werden die Werte nicht aktualisiert (keine unnötige Arbeit); nach dem Wiederherstellen sofort. Diese Einstellung gilt für Einzel- und Mehrspielermodus gemeinsam."],
  "Arıza tespiti": ["Diagnosis", "Diagnose"], "Motor bilgileri": ["Engine data", "Motordaten"], "Parça durumu": ["Part condition", "Teilezustand"],
  "Seviyeler": ["Levels", "Füllstände"],
  "{part} değiştirilecek: {cost}. Devam edilsin mi?": ["{part} will be replaced: {cost}. Continue?", "{part} wird ersetzt: {cost}. Fortfahren?"],
  "Parça yüzdesi, parçanın yaşına göre arıza yapmadan çalışma olasılığıdır: yeni parça %100, ortalama ömründe yaklaşık %40; arızalı parça %0. Yüzdesi düşen parçayı arıza çıkmadan “Değiştir” ile yenileyebilirsiniz (ücret, Servis sekmesindeki onarımla aynı). Yağ, soğutma suyu, akü, DPF ve debriyaj kendi sekmelerinden yenilenir.": [
    "A part's percentage is the chance that it keeps working without failure at its age: a new part is 100%, about 40% at its average life; a failed part is 0%. You can renew a part with a falling percentage before it fails with “Replace” (same price as the repair on the Service tab). Oil, coolant, battery, DPF and clutch are renewed on their own tabs.",
    "Der Prozentwert eines Teils ist die Wahrscheinlichkeit, dass es bei seinem Alter ohne Ausfall weiterläuft: neues Teil 100 %, bei durchschnittlicher Lebensdauer etwa 40 %; ein defektes Teil 0 %. Ein Teil mit sinkendem Wert kann vor dem Ausfall mit „Ersetzen“ erneuert werden (gleicher Preis wie die Reparatur im Service-Tab). Öl, Kühlmittel, Batterie, DPF und Kupplung werden in ihren eigenen Tabs erneuert."],
  "Güncelleme": ["Updates", "Updates"], "Açılışta yeni sürümü denetle": ["Check for a new version at startup", "Beim Start nach neuer Version suchen"],
  "Şimdi denetle": ["Check now", "Jetzt prüfen"], "İndir ve kur": ["Download and install", "Herunterladen und installieren"],
  "Sürüm": ["Version", "Version"], "Sürümünüz güncel.": ["You have the latest version.", "Sie haben die neueste Version."],
  "Güncelleme yalnızca kurulu uygulamada çalışır.": ["Updates work only in the installed app.", "Updates funktionieren nur in der installierten App."],
  "Yeni sürüm denetleniyor…": ["Checking for a new version…", "Suche nach neuer Version…"],
  "Yeni sürüm hazır": ["New version available", "Neue Version verfügbar"], "İndiriliyor": ["Downloading", "Wird heruntergeladen"],
  "Kuruluyor; uygulama kapanıp yeniden açılacak.": ["Installing; the app will close and reopen.", "Wird installiert; die App schließt sich und öffnet sich neu."],
  "Güncelleme başarısız": ["Update failed", "Update fehlgeschlagen"],
  "Sürüm bilgisi okunamadı.": ["Could not read the version info.", "Versionsinfo konnte nicht gelesen werden."],
  "İndirilen dosya doğrulanamadı; güncelleme yapılmadı.": ["The downloaded file failed verification; nothing was updated.", "Die heruntergeladene Datei ist ungültig; es wurde nichts aktualisiert."],
  "İndirilen paket beklenen dosyaları içermiyor.": ["The downloaded package lacks the expected files.", "Das heruntergeladene Paket enthält nicht die erwarteten Dateien."],
  "İnternete bağlanılamadı.": ["Could not connect to the internet.", "Keine Internetverbindung."], "Beklenmeyen hata.": ["Unexpected error.", "Unerwarteter Fehler."],
  "Ayarlar → Genel → İndir ve kur": ["Settings → General → Download and install", "Einstellungen → Allgemein → Herunterladen und installieren"],
  "Yeni sürüm indirilip kurulacak; uygulama kapanıp yeniden açılacak. Bakım kayıtları ve ayarlar korunur. Devam edilsin mi?": [
    "The new version will be downloaded and installed; the app will close and reopen. Maintenance records and settings are kept. Continue?",
    "Die neue Version wird heruntergeladen und installiert; die App schließt sich und öffnet sich neu. Wartungsdaten und Einstellungen bleiben erhalten. Fortfahren?"],
  "Otomatik — çakışma görülürse kurulmaz": ["Automatic — skipped if a conflict is seen", "Automatisch — bei Konflikt nicht geladen"],
  "Açık — her zaman kur": ["On — always load", "An — immer laden"],
  "Otomatik: oyun klasöründe OptiScaler ya da DLSS 5 eklentisi varsa veya oyun bir önceki açılışta donup düzgün kapanmadıysa panel çizilmez; sürüş modları, motor durdurma ve lastik patlaması çalışmaya devam eder. Değişiklik oyun yeniden açılınca uygulanır.": [
    "Automatic: if the game folder contains OptiScaler or a DLSS 5 mod, or the game froze and did not close properly last time, the panel is not drawn; drive modes, engine stop and tyre blowouts keep working. Changes apply when the game is restarted.",
    "Automatisch: Liegt OptiScaler oder eine DLSS-5-Mod im Spielordner oder ist das Spiel beim letzten Start eingefroren und nicht sauber beendet worden, wird das Panel nicht gezeichnet; Fahrmodi, Motorstopp und Reifenplatzer funktionieren weiter. Änderungen gelten nach einem Neustart des Spiels."],
  "Oyun içi panel Ayarlar'dan kapatıldı. Sürüş modları, motor durdurma ve lastik patlaması çalışır.": [
    "The in-game panel is switched off in Settings. Drive modes, engine stop and tyre blowouts work.",
    "Das Panel im Spiel ist in den Einstellungen ausgeschaltet. Fahrmodi, Motorstopp und Reifenplatzer funktionieren."],
  "Oyun klasöründe şu eklenti bulundu": ["Found in the game folder", "Im Spielordner gefunden"],
  "Oyun içi panel çakışmayı önlemek için kapalı; sürüş modları, motor durdurma ve lastik patlaması çalışır. Denemek isterseniz “Oyun içi panel”i “Açık” yapıp oyunu yeniden açın.": [
    "The in-game panel is off to avoid a conflict; drive modes, engine stop and tyre blowouts work. To try it anyway, set “In-game panel” to “On” and restart the game.",
    "Das Panel im Spiel ist aus, um einen Konflikt zu vermeiden; Fahrmodi, Motorstopp und Reifenplatzer funktionieren. Zum Ausprobieren „Panel im Spiel“ auf „An“ stellen und das Spiel neu starten."],
  "Oyun bir önceki açılışta düzgün kapanmadı (donma ya da çökme); oyun içi panel bu yüzden kapalı başladı. Sürüş modları, motor durdurma ve lastik patlaması çalışır. Panel sorun değilse “Oyun içi panel”i “Açık” yapıp oyunu yeniden açın.": [
    "The game did not close properly last time (freeze or crash), so the in-game panel started switched off. Drive modes, engine stop and tyre blowouts work. If the panel was not the cause, set “In-game panel” to “On” and restart the game.",
    "Das Spiel wurde beim letzten Start nicht sauber beendet (Einfrieren oder Absturz), daher startete das Panel im Spiel ausgeschaltet. Fahrmodi, Motorstopp und Reifenplatzer funktionieren. Lag es nicht am Panel, „Panel im Spiel“ auf „An“ stellen und das Spiel neu starten."],
  "Bu tuş sürüş modu ya da çekim modu tuşu olarak kullanılıyor.": ["This key is already the drive mode or filming mode key.", "Diese Taste ist bereits die Fahrmodus- oder Aufnahmemodus-Taste."],
  "“Tuş ata”ya basıp istediğiniz klavye tuşuna ya da direksiyon / kumanda düğmesine basın (10 sn, Esc iptal). Oyunda bu tuş modu sırayla değiştirir: ECO → COMFORT → SPORT. Tuş yalnızca oyun penceresi öndeyken sayılır.": [
    "Click “Assign key”, then press the keyboard key or wheel / controller button you want (10 s, Esc cancels). In the game this key cycles the modes: ECO → COMFORT → SPORT. It only counts while the game window is in front.",
    "„Taste zuweisen“ klicken und die gewünschte Taste oder Lenkrad-/Controllertaste drücken (10 s, Esc bricht ab). Im Spiel wechselt diese Taste die Modi: ECO → COMFORT → SPORT. Sie zählt nur, wenn das Spielfenster im Vordergrund ist."],
  "ECO: en fazla %75 güç, gaz yavaş artar, 85 km/h hız sınırı. COMFORT: yumuşak gaz tepkisi, güç sınırı yok. SPORT: keskin pedal, yarım pedalda ~%71 gaz. Oyun içi katman (1.8+) gaz pedalınıza değer ekleyip çıkararak çalışır; hız sabitleyici açıkken gaza karışmaz. Tek ve çok oyunculuda çalışır; Çok Oyunculu modda varsayılan olarak kapalıdır.": [
    "ECO: at most 75% power, throttle rises slowly, 85 km/h speed limit. COMFORT: smooth throttle response, no power limit. SPORT: sharp pedal, ~71% throttle at half pedal. The in-game overlay (1.8+) works by adding to or subtracting from your throttle; it does not interfere while cruise control is on. Works in single and multiplayer; off by default in Multiplayer mode.",
    "ECO: höchstens 75 % Leistung, Gas steigt langsam, 85 km/h Begrenzung. COMFORT: sanfte Gasannahme, keine Leistungsgrenze. SPORT: scharfes Pedal, ~71 % Gas bei halbem Pedal. Das Overlay (1.8+) addiert oder subtrahiert Werte zu Ihrem Gaspedal; bei Tempomat greift es nicht ein. Funktioniert im Einzel- und Mehrspieler; im Mehrspielermodus standardmäßig aus."],
  "fareyle taşı ve boyutlandır (panel ve lambalar)": ["move and resize with the mouse (panel and lamps)",
    "mit der Maus verschieben und skalieren (Panel und Leuchten)"],
  "Genel (tümü)": ["Overall (all)", "Gesamt (alle)"],
  "Tüm sistemlerin çarpanı; aşağıdaki her çarpanla çarpılır.": [
    "Multiplier for all systems; multiplied with each multiplier below.",
    "Multiplikator für alle Systeme; wird mit jedem Multiplikator unten multipliziert."],
  "Yağ ömrü (TBN, is, oksidasyon, viskozite), değişim aralığı, yağ eksilmesi, filtre dolması": [
    "Oil life (TBN, soot, oxidation, viscosity), change interval, oil consumption, filter loading",
    "Ölstandzeit (TBN, Ruß, Oxidation, Viskosität), Wechselintervall, Ölverbrauch, Filterbeladung"],
  "Antifriz": ["Coolant", "Kühlmittel"],
  "İnhibitör tükenmesi, değişim aralığı (gün ve km), kireçlenme, buharlaşma": [
    "Inhibitor depletion, change interval (days and km), scaling, evaporation",
    "Inhibitorabbau, Wechselintervall (Tage und km), Verkalkung, Verdunstung"],
  "Yaşlanma, sülfatlaşma, kendi kendine boşalma": ["Ageing, sulphation, self-discharge", "Alterung, Sulfatierung, Selbstentladung"],
  "Akü boşalması": ["Battery drain", "Batterieentladung"],
  "Elektrik yüklerinin (ışık, ısıtıcı, silecek…) aküyü boşaltma hızı; şarj olma hızı değişmez": [
    "How fast electrical loads (lights, heater, wipers…) drain the battery; charging speed is unchanged",
    "Wie schnell Verbraucher (Licht, Heizung, Wischer…) die Batterie entladen; die Ladegeschwindigkeit bleibt gleich"],
  "Diş aşınması ve doğal basınç kaybı": ["Tread wear and natural pressure loss", "Profilverschleiß und natürlicher Druckverlust"],
  "İs ve kül dolması": ["Soot and ash loading", "Ruß- und Aschebeladung"],
  "AdBlue tüketimi": ["AdBlue consumption", "AdBlue-Verbrauch"],
  "Motor aşınması": ["Engine wear", "Motorverschleiß"],
  "Motor sağlığının normal kullanımda azalması": ["Decline of engine health in normal use", "Abnahme der Motorgesundheit im Normalbetrieb"],
  "Arıza sıklığı": ["Failure frequency", "Ausfallhäufigkeit"],
  "Rastgele parça arızaları ve yavaş patlaklar": ["Random part failures and slow punctures", "Zufällige Bauteilausfälle und schleichende Reifenpannen"],
  "Etkin hız = genel × sistem çarpanı. Yalnızca kendiliğinden azalan değerler etkilenir; hararet, yağsız sürüş, donma, ön ısıtmasız marş gibi kullanım hatalarının verdiği hasar, arızadan kaynaklanan kaçaklar ve akünün şarj olması değişmez. Değişim aralıkları ve bakım planı seçilen hıza göre uzar ya da kısalır.": [
    "Effective rate = overall × system multiplier. Only values that decrease by themselves are affected; damage from misuse (overheating, oil starvation, freezing, starting without preheat), leaks caused by failures and battery charging are unchanged. Change intervals and the service plan lengthen or shorten with the chosen rate.",
    "Effektive Rate = Gesamt × System-Multiplikator. Nur Werte, die von selbst abnehmen, sind betroffen; Schäden durch Fehlbedienung (Überhitzung, Ölmangel, Frost, Start ohne Vorglühen), Lecks durch Defekte und das Laden der Batterie bleiben gleich. Wechselintervalle und Wartungsplan verlängern oder verkürzen sich mit der gewählten Rate."],
  "hiç azalmaz": ["never decreases", "nimmt nie ab"], "gerçekçi": ["realistic", "realistisch"],
  "{n} kat uzun dayanır": ["lasts {n}× longer", "hält {n}× länger"], "{n} kat hızlı": ["{n}× faster", "{n}× schneller"],
  "azalma hızı": ["wear rate", "Verschleißrate"], "boşalma": ["drain", "Entladung"],
  // uyarı sesi
  "Yeni uyarıda ikaz sesi (her uyarıda bir kez)": ["Warning chime on a new warning (once per warning)", "Warnton bei neuer Warnung (einmal pro Warnung)"],
  "İkaz sesi": ["Chime", "Warnton"], "Otomatik — tırın markasına göre": ["Automatic — by truck brand", "Automatisch — nach Lkw-Marke"],
  "Otomobil (gong)": ["Car (gong)", "Pkw (Gong)"], "Otobüs": ["Bus", "Bus"],
  "Otomatikte ses tırın markasına göre değişir (Scania, Volvo, Mercedes-Benz, MAN, DAF, Renault, Iveco, otomobil, otobüs); isterseniz başka bir marka sesi seçebilirsiniz. Her uyarı bir kez öter; çalan ses yeni bir uyarıyla kesilmez. Dikkat uyarıları yalnızca uyarı düzeyi “Hepsi” iken öter. Kendi ses dosyanız için: sesler\\ozel klasörü (README).": [
    "In automatic mode the chime follows the truck brand (Scania, Volvo, Mercedes-Benz, MAN, DAF, Renault, Iveco, car, bus); you can also pick another brand's chime. Each warning chimes once; a playing chime is never cut off by a new warning. Caution warnings only chime when the alert level is “All”. For your own sound files: the sesler\\ozel folder (README).",
    "Automatisch richtet sich der Ton nach der Lkw-Marke (Scania, Volvo, Mercedes-Benz, MAN, DAF, Renault, Iveco, Pkw, Bus); Sie können auch den Ton einer anderen Marke wählen. Jede Warnung ertönt einmal; ein laufender Ton wird von einer neuen Warnung nicht abgeschnitten. Hinweise ertönen nur bei Warnstufe „Alle“. Eigene Tondateien: Ordner sesler\\ozel (README)."],
  // şanzıman ve debriyaj
  "Debriyaj / şanzıman": ["Clutch / gearbox", "Kupplung / Getriebe"], "aşınmış": ["worn", "verschlissen"],
  "şanzıman yağı": ["gearbox oil", "Getriebeöl"], "Şanzıman ve debriyaj": ["Gearbox and clutch", "Getriebe und Kupplung"],
  "Şanzıman yağı sıcaklığı": ["Gearbox oil temperature", "Getriebeöltemperatur"], "Yağ soğutma": ["Oil cooling", "Ölkühlung"],
  "yağ-su eşanjörü (retarderli)": ["oil-to-water heat exchanger (with retarder)", "Öl-Wasser-Wärmetauscher (mit Retarder)"],
  "gövde ve hava akışı (retarder yok)": ["housing and airflow (no retarder)", "Gehäuse und Fahrtwind (kein Retarder)"],
  "Şanzıman yağı (gidilen / aralık)": ["Gearbox oil (driven / interval)", "Getriebeöl (gefahren / Intervall)"],
  "Debriyaj sıcaklığı / anlık kayma": ["Clutch temperature / current slip", "Kupplungstemperatur / aktueller Schlupf"],
  "Debriyaj balatası aşınması": ["Clutch lining wear", "Kupplungsbelagverschleiß"],
  "Tahmini kalan debriyaj ömrü": ["Estimated remaining clutch life", "Geschätzte Restlebensdauer der Kupplung"],
  "Oyun hasarı: şanzıman": ["Game damage: gearbox", "Spielschaden: Getriebe"],
  "Şanzıman yağını değiştir": ["Change gearbox oil", "Getriebeöl wechseln"], "Debriyajı yenile": ["Replace clutch", "Kupplung erneuern"],
  "Şanzıman yağı yokuşta tam yükte ve uzun retarder kullanımında ısınır (sarı 115 °C, kırmızı 130 °C). Debriyaj kalkışta, manevrada ve yarım debriyajla sürünürken ısınır (sarı 250 °C, kırmızı 320 °C); sıcak balata çok hızlı aşınır.": [
    "Gearbox oil heats up at full load on climbs and with long retarder use (amber 115 °C, red 130 °C). The clutch heats up when pulling away, manoeuvring and creeping on a slipping clutch (amber 250 °C, red 320 °C); a hot lining wears very quickly.",
    "Getriebeöl erwärmt sich bei Volllast an Steigungen und langem Retarder-Einsatz (gelb 115 °C, rot 130 °C). Die Kupplung erwärmt sich beim Anfahren, Rangieren und Kriechen mit schleifender Kupplung (gelb 250 °C, rot 320 °C); ein heißer Belag verschleißt sehr schnell."],
  "Şanzıman yağı ve filtresi değişecek ({l} L): {cost}. Devam edilsin mi?": ["The gearbox oil and filter will be changed ({l} L): {cost}. Continue?",
    "Getriebeöl und Filter werden gewechselt ({l} L): {cost}. Fortfahren?"],
  "Debriyaj yenilenecek (şanzıman sökülür): {cost}. Devam edilsin mi?": ["The clutch will be replaced (gearbox removed): {cost}. Continue?",
    "Die Kupplung wird erneuert (Getriebe wird ausgebaut): {cost}. Fortfahren?"],
  "Yağ aşırı sıcak": ["Oil overheating", "Öl überhitzt"], "Debriyaj aşırı sıcak": ["Clutch overheating", "Kupplung überhitzt"],
  "Debriyaj bitti": ["Clutch worn out", "Kupplung verschlissen"], "Yağ sıcak": ["Oil hot", "Öl heiß"],
  "Debriyaj ısınıyor": ["Clutch getting hot", "Kupplung wird heiß"], "Debriyaj değişimi yakın": ["Clutch replacement due soon", "Kupplungswechsel bald fällig"],
  "Yağ değişimi ": ["Oil change due", "Ölwechsel fällig"], "Isınıyor": ["Getting hot", "Wird heiß"], "Aşırı ısındı": ["Overheated", "Überhitzt"],
  "Debriyaj balatası aşınması ve şanzıman yağının yaşlanması (değişim aralığı)": ["Clutch lining wear and gearbox oil ageing (change interval)",
    "Kupplungsbelagverschleiß und Alterung des Getriebeöls (Wechselintervall)"],
  // direksiyon, ABS, park freni
  "Direksiyon, fren ve park freni": ["Steering, brakes and parking brake", "Lenkung, Bremsen und Feststellbremse"],
  "Direksiyon desteği": ["Steering assist", "Lenkunterstützung"], "Direksiyon hidrolik yağı": ["Power steering fluid", "Servolenköl"],
  "Park freni": ["Parking brake", "Feststellbremse"], "Fren havası": ["Brake air", "Bremsluft"],
  "Oyun içi katmanın alt ortasındaki ikaz lambaları yalnızca sarı ve kırmızıdır; ŞANZIMAN, DİREKSİYON, FREN, EL FRENİ, ABS ve MARŞ lambaları da bunlara dahildir. Hangi önem derecesinden itibaren yanacaklarını Ayarlar → Gösterilecek lambalar'dan seçebilirsiniz. Yeşil, mavi ve beyaz bilgi lambaları oyunun kendi göstergesinde görünür.": [
    "The warning lamps at the bottom centre of the in-game overlay are only amber and red, including the GEARBOX, STEERING, BRAKES, PARK BRAKE, ABS and STARTER lamps. Choose from which importance level they light up in Settings → Lamps shown. Green, blue and white information lamps appear on the game's own dashboard.",
    "Die Warnleuchten unten in der Mitte des Overlays sind nur gelb und rot, einschließlich GETRIEBE, LENKUNG, BREMSE, PARKBREMSE, ABS und ANLASSER. Ab welcher Wichtigkeit sie leuchten, wählen Sie unter Einstellungen → Angezeigte Leuchten. Grüne, blaue und weiße Kontrollleuchten zeigt das Spiel im eigenen Cockpit."],
  "Elektrikli direksiyon (EPS)": ["Electric power steering (EPS)", "Elektrische Servolenkung (EPS)"],
  "Destek yok (motor çalışmıyor)": ["No assist (engine not running)", "Keine Unterstützung (Motor läuft nicht)"],
  "Hidrolik yağı çok az": ["Fluid very low", "Öl sehr niedrig"], "Hidrolik kaçağı": ["Hydraulic leak", "Hydraulikleck"],
  "Arızalı (sensör)": ["Faulty (sensor)", "Defekt (Sensor)"], "Çekili, tır hareket ediyor!": ["Applied while moving!", "Angezogen während der Fahrt!"],
  "Çekilmedi!": ["Not applied!", "Nicht angezogen!"], "Çekili": ["Applied", "Angezogen"], "Çekili değil": ["Released", "Gelöst"],
  "Acil fren": ["Emergency braking", "Notbremsung"],
  // dağıtım paketinden kurulu program: eklenti ve demo Başlat menüsünde
  "Oyun eklentileri kurulumda yüklendi; oyun o sırada bulunamadıysa ya da sonradan kurulduysa: Başlat menüsü → ETS2 Bakım → “Eklentileri kur”.": [
    "The game plugins were installed during setup; if the game was not found then or was installed later: Start menu → ETS2 Maintenance → “Install plugins”.",
    "Die Spiel-Plugins wurden bei der Installation eingerichtet; wurde das Spiel dabei nicht gefunden oder später installiert: Startmenü → ETS2 Wartung → „Plugins installieren“."],
  "Oyun olmadan denemek için: Başlat menüsü → ETS2 Bakım → “Demo (oyunsuz deneme)”. Ayarlar sekmesi oyun beklenirken de kullanılabilir.": [
    "To try it without the game: Start menu → ETS2 Maintenance → “Demo (try without the game)”. The Settings tab can be used while waiting for the game too.",
    "Zum Testen ohne Spiel: Startmenü → ETS2 Wartung → „Demo (ohne Spiel testen)“. Der Einstellungen-Tab ist auch beim Warten auf das Spiel nutzbar."],
  "Oyunda yüklü değil ya da oyun kapalı (Başlat menüsü → ETS2 Bakım → “Eklentileri kur”; oyun DirectX 11 ile çalışmalı).": [
    "Not loaded in the game or the game is closed (Start menu → ETS2 Maintenance → “Install plugins”; the game must run with DirectX 11).",
    "Nicht im Spiel geladen oder Spiel geschlossen (Startmenü → ETS2 Wartung → „Plugins installieren“; das Spiel muss mit DirectX 11 laufen)."],
  // uyarılar ve ikaz lambaları (tek tek açma / kapama)
  "Uyarılar ve ikaz lambaları": ["Warnings and warning lamps", "Warnungen und Warnleuchten"],
  "her birini tek tek açıp kapatın; kapalı uyarı ne listede ne oyun içi katmanda görünür, ses de çıkarmaz": [
    "switch each one on or off; a disabled warning appears neither in the list nor in the in-game overlay and makes no sound",
    "jede einzeln ein- oder ausschalten; eine ausgeschaltete Warnung erscheint weder in der Liste noch im Spiel-Overlay und gibt keinen Ton aus"],
  "Hepsini aç": ["Turn all on", "Alle einschalten"], "Hepsini kapat": ["Turn all off", "Alle ausschalten"],
  "Uyarılar": ["Warnings", "Warnungen"], "İkaz lambaları (oyun içi katman)": ["Warning lamps (in-game overlay)", "Warnleuchten (Spiel-Overlay)"],
  "Tüm lambalar": ["All lamps", "Alle Leuchten"], "uyarı açık": ["warnings on", "Warnungen an"], "lamba açık": ["lamps on", "Leuchten an"],
  "Kapatılan uyarılar ve lambalar yalnızca gösterilmez: simülasyon (aşınma, arızalar, motor durdurma) aynen sürer. Uyarı düzeyi ve “Gösterilecek lambalar” süzgeci de ayrıca uygulanır; “Gösterge lambaları” kapalıysa hiçbir lamba yanmaz.": [
    "Disabled warnings and lamps are only hidden: the simulation (wear, faults, engine stop) carries on unchanged. The alert level and the “Lamps shown” filter still apply as well; if “Warning lamps” is off, no lamp lights up.",
    "Ausgeschaltete Warnungen und Leuchten werden nur ausgeblendet: Die Simulation (Verschleiß, Defekte, Motorstopp) läuft unverändert weiter. Warnstufe und der Filter „Angezeigte Leuchten“ gelten zusätzlich; ist „Warnleuchten“ aus, leuchtet keine Leuchte."],
  "Tüm uyarılar ve ikaz lambaları kapatılacak (kritik olanlar dahil). Devam edilsin mi?": [
    "All warnings and warning lamps will be turned off (critical ones included). Continue?",
    "Alle Warnungen und Warnleuchten werden ausgeschaltet (auch kritische). Fortfahren?"],
  // onay penceresi
  "Vazgeç": ["Cancel", "Abbrechen"], "Devam": ["Continue", "Weiter"],
  "hp @": ["hp @", "PS @"],
  // gösterge lambalarının önem dereceleri
  "Gösterilecek lambalar": ["Lamps shown", "Angezeigte Leuchten"],
  "Hepsi — önemsiz ve üstü": ["All — minor and above", "Alle — geringfügig und höher"],
  "Önemli ve üstü": ["Important and above", "Wichtig und höher"], "Uyarı ve üstü": ["Warning and above", "Warnung und höher"],
  "Ciddi ve üstü — yalnızca kırmızı lambalar": ["Serious and above — red lamps only", "Ernst und höher — nur rote Leuchten"],
  "Yalnızca kritik — motoru hemen durdurun": ["Critical only — stop the engine now", "Nur kritisch — Motor sofort abstellen"],
  "Her lamba durumunun bir önem derecesi vardır; seçilen derece ve üstü yanar. Önemsiz: bilgi (ön ısıtma sürüyor, DPF rejenerasyonu). Önemli: bakım zamanı (yağ ve şanzıman yağı değişimi, debriyaj balatası, lastik dişi, akü ve motor sağlığı). Uyarı: sarı arızalar ve sınır değerler (ABS, marş, park freni çekilmedi, sıcaklık yüksek, seviye düşük, yakıt az). Ciddi: kırmızı lambalar (şarj yok, fren aşırı sıcak, hava basıncı düşük, park freni çekiliyken hareket, direksiyon desteği yok, şanzıman ya da debriyaj aşırı sıcak, lastik patladı). Kritik: STOP, yağ basıncı, hararet.": [
    "Every lamp condition has an importance level; the chosen level and above light up. Minor: information (preheating, DPF regeneration). Important: service due (oil and gearbox oil change, clutch lining, tyre tread, battery and engine health). Warning: amber faults and limit values (ABS, starter, parking brake not applied, high temperature, low level, low fuel). Serious: red lamps (no charging, brakes overheated, low air pressure, driving with the parking brake on, no steering assist, gearbox or clutch overheated, tyre blown). Critical: STOP, oil pressure, overheating.",
    "Jeder Leuchtenzustand hat eine Wichtigkeit; die gewählte Stufe und höher leuchten. Geringfügig: Information (Vorglühen, DPF-Regeneration). Wichtig: Wartung fällig (Öl- und Getriebeölwechsel, Kupplungsbelag, Reifenprofil, Batterie- und Motorzustand). Warnung: gelbe Defekte und Grenzwerte (ABS, Anlasser, Feststellbremse nicht angezogen, hohe Temperatur, niedriger Stand, wenig Kraftstoff). Ernst: rote Leuchten (keine Ladung, Bremsen überhitzt, niedriger Luftdruck, Fahrt mit Feststellbremse, keine Lenkunterstützung, Getriebe oder Kupplung überhitzt, Reifen geplatzt). Kritisch: STOP, Öldruck, Überhitzung."],
  // çekim modu (yalnızca tek oyunculu)
  "Çekim modu": ["Filming mode", "Aufnahmemodus"],
  "video çekimi için seçtiğiniz arızayı istediğiniz anda tetikleyin (yalnızca tek oyunculu)": [
    "trigger the fault you choose at exactly the right moment of your video (single player only)",
    "den gewählten Defekt im richtigen Moment Ihres Videos auslösen (nur Einzelspieler)"],
  "Açık (kısayol tuşu ve “Şimdi tetikle” çalışır)": ["On (the shortcut key and “Trigger now” work)",
    "An (Tastenkürzel und „Jetzt auslösen“ funktionieren)"],
  "Tetiklenecek arıza": ["Fault to trigger", "Auszulösender Defekt"], "Kısayol tuşu": ["Shortcut key", "Tastenkürzel"],
  "Oyunda bu tuşa basınca seçili arıza hemen tetiklenir (çekim modu açıkken, yalnızca oyun penceresi öndeyken). Oyunun F tuşlarının çoğu dolu (F10 sürüş modunda): direksiyondaki boş bir düğmeyi ya da oyunda kullanılmayan bir tuşu seçin.": [
    "Pressing this key in the game triggers the selected fault immediately (while filming mode is on and the game window is in front). Most of the game's F keys are taken (F10 is the drive mode key): pick a free wheel button or a key the game does not use.",
    "Ein Druck auf diese Taste im Spiel löst den gewählten Defekt sofort aus (bei eingeschaltetem Aufnahmemodus und nur, wenn das Spielfenster im Vordergrund ist). Die meisten F-Tasten sind im Spiel belegt (F10 ist die Fahrmodus-Taste): eine freie Lenkradtaste oder eine im Spiel ungenutzte Taste wählen."],
  "Şimdi tetikle": ["Trigger now", "Jetzt auslösen"], "Hepsini onar": ["Repair all", "Alles reparieren"],
  "Tetiklenen arıza kendiliğinden çıkmış gibi işler: aynı uyarı, ikaz lambası, ses ve sonuçlar (hararet, akü boşalması, motorun durması…); Servis sekmesinden ya da oyun içi servis menüsünden (Alt+F8) aynı ücretle onarılır. Olay kaydında “elle” diye işaretlenir. “Hepsini onar” tüm arızaları ve lastik hasarını ücretsiz giderir; sıvı seviyeleri, akü şarjı ve sıcaklıklar değişmez. Sarı (dikkat) arızalar yalnızca uyarı düzeyi “Hepsi” iken öter.": [
    "A triggered fault behaves exactly like one that occurred by itself: same warning, warning lamp, sound and consequences (overheating, battery drain, engine shutdown…); it is repaired at the usual price on the Service & faults tab or in the in-game service menu (Alt+F8). The event log marks it “manual”. “Repair all” fixes every fault and tyre damage for free; fluid levels, battery charge and temperatures stay as they are. Amber (warning) faults only sound when the alert level is “All”.",
    "Ein ausgelöster Defekt verhält sich genau wie ein von selbst aufgetretener: gleiche Warnung, Warnleuchte, gleicher Ton und gleiche Folgen (Überhitzung, Batterieentladung, Abstellen des Motors…); er wird zum üblichen Preis im Tab Service & Defekte oder im Service-Menü im Spiel (Alt+F8) repariert. Das Ereignisprotokoll markiert ihn als „manuell“. „Alles reparieren“ behebt alle Defekte und Reifenschäden kostenlos; Füllstände, Batterieladung und Temperaturen bleiben unverändert. Gelbe (Hinweis-)Defekte ertönen nur bei Warnstufe „Alle“."],
  "Hemen yanan lamba": ["Lamp right away", "Leuchte sofort"], "Belirti çıkınca": ["Once symptoms appear", "Sobald Symptome auftreten"],
  "Bu araçta yok": ["Not on this vehicle", "Bei diesem Fahrzeug nicht vorhanden"],
  "Çok oyunculu oturumda çekim modu kullanılamaz.": ["Filming mode is not available in a multiplayer session.",
    "Der Aufnahmemodus ist in einer Mehrspieler-Sitzung nicht verfügbar."],
  "Çekim modu kapalı: kutuyu işaretleyin.": ["Filming mode is off: tick the box.", "Aufnahmemodus ist aus: Kästchen ankreuzen."],
  "Oyuna bağlanınca kullanılabilir.": ["Available once connected to the game.", "Verfügbar, sobald das Spiel verbunden ist."],
  "Hazır": ["Ready", "Bereit"], "oyunda kısayol": ["in-game shortcut", "Tastenkürzel im Spiel"],
  "kısayol tuşu atanmadı": ["no shortcut key assigned", "kein Tastenkürzel zugewiesen"],
  // araç tipi
  "Araç tipi": ["Vehicle type", "Fahrzeugtyp"], "Otomatik": ["Automatic", "Automatisch"], "Tır": ["Truck", "Lkw"],
  "Otomobil": ["Car", "Pkw"], "Algılanan": ["Detected", "Erkannt"],
  "Otomobilde motor sürüşten algılanmaz: benzinli ya da dizel motoru listeden seçin.": [
    "Car engines are not detected from driving: pick the petrol or diesel engine from the list.",
    "Bei Pkw wird der Motor nicht aus der Fahrt erkannt: Benzin- oder Dieselmotor aus der Liste wählen."],
  "Tek oyunculu otomobil ve otobüs modlarını (Togg, Passat…) oyun tır olarak bildirir: burada Otomobil ya da Otobüs seçin (12 V akü, otomobil yağı ve antifrizi, otomobil motorları).": [
    "The game reports single-player car and bus mods (Togg, Passat…) as trucks: choose Car or Bus here (12 V battery, car oil and coolant, car engines).",
    "Das Spiel meldet Pkw- und Bus-Mods im Einzelspieler (Togg, Passat…) als Lkw: hier Pkw oder Bus wählen (12-V-Batterie, Pkw-Öl und -Kühlmittel, Pkw-Motoren)."],
  "Araç tipi değişince bu aracın motoru, aküsü (12 / 24 V), yağı, antifrizi, lastikleri ve şanzımanı yeni tipin varsayılanlarına göre yeniden kurulur. Devam edilsin mi?": [
    "When the vehicle type changes, this vehicle's engine, battery (12 / 24 V), oil, coolant, tyres and gearbox are set up again with the new type's defaults. Continue?",
    "Beim Wechsel des Fahrzeugtyps werden Motor, Batterie (12 / 24 V), Öl, Kühlmittel, Reifen und Getriebe dieses Fahrzeugs mit den Standardwerten des neuen Typs neu eingerichtet. Fortfahren?"],
};
const MONTHS = {
  tr: ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"],
  en: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
  de: ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
};
const LOCALES = { tr: "tr-TR", en: "en-GB", de: "de-DE" };
const UNITS = { sa: ["h", "h"], "gün": ["days", "Tage"], dk: ["min", "min"], rpm: ["rpm", "U/min"], hp: ["hp", "PS"] };
let LANG = "tr";

function tt(s) {
  if (LANG === "tr" || s == null) return s;
  const e = I18N[s] || I18N[s.trim()];
  return e ? e[LANG === "en" ? 0 : 1] : s;
}
function tu(u) {
  if (LANG === "tr" || !UNITS[u]) return u;
  return UNITS[u][LANG === "en" ? 0 : 1];
}
function pct(text) {
  return LANG === "tr" ? "%" + text : LANG === "en" ? text + "%" : text + " %";
}
// Sayfadaki sabit metinleri seçili dile çevirir (değer bağlı öğeler hariç)
function translateDom(root) {
  const walker = document.createTreeWalker(root || document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    const p = n.parentElement;
    if (!p || p.closest("[data-v],[data-s],script,style,#alerts,.no-i18n,#log-body,#lab-body,#fault-list")) continue;
    if (n._src === undefined) n._src = n.nodeValue;
    const key = n._src.trim();
    if (!key) continue;
    const tr = tt(key);
    n.nodeValue = tr === key ? n._src : n._src.replace(key, tr);
  }
  document.documentElement.lang = LANG;
  document.title = tt("ETS2 Bakım Simülatörü");
}
