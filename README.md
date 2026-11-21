# ETS2 Bakım Simülatörü

Euro Truck Simulator 2'ye (ve ATS'ye) **gerçekçi motor yağı, antifriz/soğutma, akü-elektrik, DPF, arıza ve
detaylı motor analizi** ekleyen yardımcı program. Oyunun telemetri verisini okur, fiziksel modellerle
hesaplar ve bilgisayarda ayrı bir pencerede gösterir. Gerektiğinde oyunda motoru durdurur.

**1.3.2:** SPORT sürüş modunda gaz verip bırakırken oyunun takılması düzeltildi (oyun içi katman 1.15.0: gaz düzeltmesi
artık her karede değil, önceki değer oyuna yansıdıktan sonra ve yalnızca anlamlı değişiklikte gönderilir). Yeni
**Ayarlar → Değer güncelleme sıklığı**: uygulama penceresi ve oyun içi katman için ayrı ayrı, gerçek zamanlıdan (0 sn,
saniyede 20 kez) 5 saniyeye kadar. Uygulama daha az işlemci kullanır (telemetri okuma ~16 kat hızlı, pencere canlı akışla
güncellenir, simge durumundayken durur). Grafiklerdeki ve indirme göstergesindeki yüzdeler seçili dilin biçiminde.

**1.3.1:** SPORT sürüş modunda gaz pedalı bırakılınca oyunda çok küçük bir gaz kalıyor, bu da retarderi ve motor frenini devre dışı bırakıyordu; düzeltildi (oyun içi katman 1.14.1). Kullanılmayan kod ve çeviriler temizlendi.

**1.3.0'da yeni:** Motor Analizi'nde **arıza tespiti** (motor bilgileri, 25 parçanın durum yüzdesi, seviyeler; yıpranan parçayı arıza çıkmadan değiştirme), 8 yeni motor parçası arızası (turbo, enjektör, EGR, intercooler, hava ve yakıt filtresi, radyatör sızıntısı, kayış), daha fazla yağ / antifriz / akü seçeneği, katman tuşunu değiştirme, DLSS 5 / OptiScaler çakışmasında panelin kendiliğinden kurulmaması (Ayarlar → *Oyun içi panel*) ve uygulama içi güncelleme.

## Kurulum (bir kez)

1. **Python 3.10+** kurulu olmalı (python.org).
2. `EKLENTI_KUR.bat` dosyasını çalıştırın. Telemetri eklentisini
   ([RenCloud/scs-sdk-plugin V.1.12.1](https://github.com/RenCloud/scs-sdk-plugin/releases/tag/V.1.12.1))
   indirir ve `Euro Truck Simulator 2\bin\win_x64\plugins\scs-telemetry.dll` olarak kurar (zaten kuruluysa yeniden
   indirmez). Yanına oyun içi katmanı (`ets2bakim_overlay.dll`) da kopyalar; Akıllı Uygulama Denetimi açıksa ve katman
   imzasızsa kopyalamaz (aşağıya bakın).
3. Oyunu açınca çıkan **"Advanced SDK features"** uyarısını **OK** ile geçin.

Başkalarına dağıtmak için Python gerektirmeyen, kendi kurulum ve kaldırma programı olan zip paketleri vardır: aşağıda
[Dağıtım paketi](#dağıtım-paketi-indirilebilir-zip-kurulum-ve-kaldırma).

## Kullanım: tek uygulama, iki mod

Masaüstünde (ve klasörde) tek kısayol vardır: **ETS2 Bakım**. Tek / Çok Oyunculu mod uygulamanın içinde seçilir
(Ayarlar → **Oyun modu**; 1.1'e kadar bunlar iki ayrı uygulamaydı):

| Oyun modu | Ne yapar |
|---|---|
| **Otomatik** (varsayılan) | TruckersMP ya da oyunun Konvoy modu algılanınca Çok Oyunculu, yoksa Tek Oyunculu |
| **Tek Oyunculu** | Normal oyun, tam gerçekçilik: arızada motor her zaman durdurulur (tam izleme) |
| **Çok Oyunculu** | TruckersMP / Konvoy: motor zorla durdurulmaz, isterseniz Ayarlar → *İzleme modu* |

- **Her modun kendi ayarları ve tır kayıtları vardır**: Tek Oyunculu `data\`, Çok Oyunculu `data_mp\` klasöründe; tek
  oyunculu ve çok oyunculu tır kayıtları birbirine karışmaz. Ayarlar sayfası o anki modun ayarlarını gösterir (ör. Tek
  Oyunculu'da azalma hızları 5×, Çok Oyunculu'da 1× olabilir). **Dil ve oyun modu ortaktır.** Çok Oyunculu modda
  sürüş modları (gaz eğrisi) varsayılan olarak kapalıdır.
- **Otomatik geçiş:** oyun bağlanınca TruckersMP hemen denetlenir ve tır o modun kaydından yüklenir. Oyun sürerken
  TruckersMP algılaması bir an kaçarsa (denetim 15 sn'de bir) hemen dönülmez: 45 sn algılanmazsa Tek Oyunculu'ya
  geçilir; oyun kapalıyken son mod korunur. Mod değişince durum kaydedilir, öbür modun ayarları ve kayıtları yüklenir.
- **Çok oyunculu izleme modu** (yalnızca Çok Oyunculu modda, Ayarlar → Gerçekçilik):
  - *Sadece gösterme* (varsayılan): değerler ve uyarılar var, motora hiç dokunulmaz.
  - *Tam izleme*: arızada motor da durdurulur. Trafikte tehlike yaratmamak için bu ancak tır 10 km/h altına inince
    yapılır; o zamana kadar "güvenli yerde durun" uyarısı çıkar. Kontak ve ışıklar açık kalır.
- Arızalar, bakım, uyarılar, analiz ve oyun içi servis menüsü her iki modda aynen çalışır.
- **Güvenlik:** mod Tek Oyunculu'ya sabitlenmişken TruckersMP ya da Konvoy oturumu algılanırsa uyarı çıkar ve motor
  durdurulmaz. Üst çubuktaki rozet o anki modu ve algılanan oturumu gösterir.
- Komut satırında `--mod auto|tek|cok` oyun modunu ayarlar (Ayarlar'daki seçimle aynı, kaydedilir).
- **Dil:** sağ üstteki dil seçicide (TR, EN, DE) seçilen dil iki moda da uygulanır. Uygulama
  penceresi (başlığı ve onay pencereleri dahil), oyun içi katman, uyarılar, servis menüsü, olay kaydı ve gösterge
  lambaları seçilen dilde görünür. Çok dil desteğinden önce yazılmış eski olay kayıtları da açılışta seçili dile
  çevrilir. Oyun içi katman son dili hatırlar: simülatör kapalıyken de o dilde yazar. Oyunun verdiği şehir ve yük
  adları oyunun dilinde gelir; bilinen şehirler (ör. Münih → Munich / München) seçili dile çevrilir.
- Uygulama **kendi penceresinde** açılır: tarayıcı, adres çubuğu ya da siyah konsol penceresi yoktur
  (Windows'un yerleşik WebView2 bileşeni kullanılır). İkinci monitöre koyabilirsiniz. Oyunu tam ekran yerine
  **pencereli tam ekran** oynarsanız Alt+Tab daha rahat olur.
- Kapatmak için pencereyi kapatın; durum kaydedilir (ayrıca her 15 saniyede bir) ve uygulama hemen kapanır.
  Uygulama zaten açıksa kısayol ikinci bir kopya açmaz, açık pencereyi öne getirir.
- **Güncelleme sıklığı:** simülasyon ve oyun içi katman saniyede 10 kez, uygulama penceresindeki canlı değerler
  saniyede 4 kez, grafikler her saniye yenilenir.
- `DEMO.bat` → oyun olmadan sanal kamyonla deneme (Berlin–Münih arası, 4 kat hızlı).
- Kısayol silinirse `kisayol_olustur.ps1` yeniden oluşturur (1.1'in iki eski kısayolunu da kaldırır). Hata kayıtları:
  `data\ets2bakim.log`.
- Her kamyon (model + plaka) için ayrı kayıt tutulur: `data\trucks\*.json` (Çok Oyunculu modda `data_mp\trucks\`).
- **Başka tır (hızlı iş):** oyunun hızlı işte verdiği geçici tır kullanılıyorsa, teslimat bitince (ya da iş iptal edilince)
  o tırın bakım değerleri sıfırlanır; kendi tırlarınızın kayıtlarına dokunulmaz. Ayarlar → *Hızlı iş tırları* ile
  kapatılabilir. Servis sekmesindeki **Bu tırın değerlerini sıfırla** düğmesi aynı işi elle yapar (tır dururken).
- Motor değerleri **otomatik seçilir** (aşağıya bakın); isterseniz Ayarlar sekmesinden değiştirebilirsiniz.
- **Değer renkleri:** her ölçüm durumuna göre renklenir — **sarı** = sınırda, **kırmızı** = kritik (normal değerler
  olduğu gibi kalır). Eşikler tek yerde (`ets2bakim\levels.py`) tanımlıdır; uygulama penceresi ve oyun içi katman aynı
  kuralları kullanır (ör. soğutma suyu 104 °C'den sarı, 110 °C'den kırmızı; yağda demir 60 / 100 ppm; akü şarjı %75 / %50).
- **Dil:** Türkçe, English, Deutsch — sağ üstteki seçiciden. Oyun içi katman da aynı dili kullanır.
- **Uyarı düzeyi** (Ayarlar): *Az* = yalnızca kritik, *Normal* = kritik + dikkat (ekran şeridi ve ses yalnızca kritikte),
  *Hepsi* = sürüş ipuçları gibi bilgi mesajları dahil.
- **Yolculuk & Sürüş** sekmesi: iş başına mesafe, tüketim, yakıt maliyeti (yakıt fiyatı Ayarlar'da), CO₂, rölanti,
  hıza göre tüketim, vites kullanımı, fren enerjisi dağılımı (servis freni / retarder / motor freni), fren sıcaklığı
  ve hava basıncı.
- **Bakım planı** (Servis sekmesi): sıradaki yağ, filtre, antifriz, DPF kül temizliği, akü ve motor revizyonu için
  kalan tahmini km / gün ve 1000 km başına bakım gideri.

## Akıllı Uygulama Denetimi (Smart App Control)

Denetim açıkken Windows yalnızca Microsoft'un tanıdığı ya da **güvenilir bir sertifika kuruluşunca imzalanmış**
dosyaları çalıştırır. Kendi oluşturulmuş (self-signed) imza imzasız sayılır ve tek bir dosyaya istisna tanınamaz.
Durumunu *Windows Güvenliği → Uygulama ve tarayıcı denetimi* bölümünden görebilir ya da
`.venv\Scripts\python.exe -m ets2bakim.appcontrol` ile rapor alabilirsiniz. Denetim açıkken (Ekim 2026'da denendi):

| Bileşen | Durum |
|---|---|
| Simülatör, uygulama penceresi (Python, WebView2) | **Çalışır** (Python imzalı, pencere bileşenleri Microsoft'ça tanınıyor) |
| Telemetri eklentisi `scs-telemetry.dll` | **Çalışır** (imzasız ama Microsoft'ça tanınan yaygın bir dosya) |
| Uyarılar, analiz, servis sekmesi, gösterge renkleri | **Çalışır** |
| Motoru durdurma | **Çalışır**, yedek yöntemle: oyuna tuş gönderilir (oyun penceresi öndeyken) |
| Oyun içi katman `ets2bakim_overlay.dll` (panel, lambalar, Alt+F8 servis) | **Engellenir** — imzasız ve her derlemede yeni bir dosya |
| Katmanı derleme (MinGW) | **Engellenir** — derleyici imzasız |

Uygulama bunu kendisi algılar: denetim açıksa `EKLENTI_KUR.bat` imzasız katmanı oyuna kurmaz (kuruluysa kaldırır;
yoksa her oyun açılışında engellenip bildirim çıkarır), Ayarlar → *Oyun içi katman* bölümünde de durumu yazar.

**Katmanı denetim açıkken de kullanmak için** DLL'in güvenilir bir kod imzalama sertifikasıyla imzalanması gerekir.
Sertifika sizin adınıza düzenlenir, kimlik doğrulaması ister ve ücretlidir:

- **Certum Open Source Code Signing** (yaklaşık 50 $/yıl): proje açık kaynak olarak yayımlanırsa bireysel geliştiriciye
  verilir; bulut imzalama (SimplySign) ile kullanılır.
- **Standart (OV) kod imzalama sertifikası** (Certum, Sectigo, SSL.com vb.; yaklaşık 100–200 €/yıl).
- **SignPath Foundation** (ücretsiz): açık kaynak projeleri kendi sertifikasıyla imzalar; projenin GitHub'da herkese açık
  olması ve DLL'in GitHub Actions'ta derlenmesi gerekir.
- Microsoft'un *Artifact Signing* hizmeti şimdilik bireysel geliştiricilere yalnızca ABD ve Kanada'da açık.

Sertifika Windows sertifika deposuna eklendikten sonra:

1. `powershell -ExecutionPolicy Bypass -File overlay\imzala.ps1` — mevcut DLL'i imzalar (derleme gerekmez,
   denetim açıkken de çalışır). Birden fazla sertifika varsa `-Thumbprint <parmak izi>` ile seçin ya da
   `overlay\imza.json` dosyasına `{"thumbprint": "...", "timestamp": "..."}` yazın.
2. `EKLENTI_KUR.bat` — imzalı katmanı oyuna kurar.

`overlay\imza.json` varsa `overlay\build.ps1` her derlemeden sonra DLL'i kendiliğinden imzalar. Derlemek için ise
denetimin kapalı olması gerekir (MinGW derleyicisi imzasız).

**Denetim kapalıysa** her şey imzasız da çalışır: `powershell -ExecutionPolicy Bypass -File overlay\build.ps1` ve
ardından `EKLENTI_KUR.bat`. Oyundaki sürüm: **1.10.3** (şanzıman, direksiyon, marş, fren, el freni ve ABS lambaları, önem derecesine göre lamba süzgeci, Motor sayfasında şanzıman yağı ve debriyaj, ikaz sesi
simülatörden, sürüş modları ECO/COMFORT/SPORT, fareyle taşıma/boyutlandırma, lastik patlaması etkisi,
lastik/yakıt/AdBlue, gösterge lambaları, menüde gizlenme, dört köşe konumu,
Alt+F8 servis menüsü, F3 ile gizlenme, 3 dil, 10 sayfa).
Oyun açılırken "Advanced SDK features" uyarısı **çıkmıyorsa** eklentiler yüklenmemiş demektir.

## Oyun içi katman (tam ekranda da görünür)

`overlay\build\ets2bakim_overlay.dll`, oyunun kendi eklenti sistemiyle (SCS SDK) yüklenen bir eklentidir.
`EKLENTI_KUR.bat` onu telemetri eklentisiyle birlikte `bin\win_x64\plugins` klasörüne kurar.

- Oyunun DirectX 11 görüntüsüne doğrudan çizer (Steam/Discord katmanları gibi); **tam ekranda da görünür**.
- Veriler simülatörden paylaşılan bellekle gelir, yani uygulama (**ETS2 Bakım**) açık olmalı.
- **Konum:** ekranın dört köşesinden biri; varsayılan **sol üst**. `Ctrl+F8` sırayla: sol üst → sağ üst → sağ alt →
  sol alt. Sayfa sığmazsa kendiliğinden küçülür.
- **Fareyle taşıma ve boyutlandırma (`Ctrl+Alt+F8`):** düzenleme modunda ekranda katmanın kendi imleci çıkar; paneli
  ve gösterge lambası şeridini **sürükleyerek** istediğiniz yere taşıyın (kenarlara ve ortaya yapışır), **fare
  tekerleğiyle** ya da köşedeki **mavi tutamacı** çekerek büyütüp küçültün (%70–%200). **Orta tık** üzerindeki öğeyi
  varsayılan yer ve boyuta döndürür. **Sağ tık**, `Esc` ya da yeniden `Ctrl+Alt+F8` düzenlemeyi bitirir; ayarlar
  kaydedilir ve sonraki açılışlarda korunur. Düzenleme sırasında fare oyuna gitmez (kamera ve fareyle direksiyon
  dönmez, tıklamalar oyunda bir şeye basmaz); bu yüzden tır dururken yapın. Oyun penceresi önde değilse, menü açılırsa
  ya da 2 dakika dokunulmazsa fare kendiliğinden oyuna döner. Panel ekranın alt yarısına taşınırsa yukarı doğru,
  sağ yarısına taşınırsa sola doğru uzar; sayfa değişse de ekrandan taşmaz. `Ctrl+F8` serbest konumdan hazır köşeye,
  `Ctrl+Shift+F8` hazır boyutlara döner.
- **HUD ile birlikte gizlenir:** oyunda haritayı/rota ekranını gizleyen tuşa (varsayılan **F3**, `showhud`) basınca
  katman da gizlenir, tekrar basınca geri gelir. Tuşu oyunda değiştirdiyseniz simülatör yeni atamayı profilinizin
  `controls.sii` dosyasından okur. Gizliyken yalnızca yeni kritik uyarı kısa süre görünür. Eşleşme bozulursa
  (ör. oyun HUD'u gizli başlarsa) `F8` katmanı geri getirir. Ayarlar sekmesinden kapatılabilir.
- **Kompakt mod:** soğutma suyu, yağ sıcaklığı/basıncı, akü, yağ ömrü, antifriz, DPF, motor sağlığı, yakıt, AdBlue,
  lastikler, molaya kalan süre ve son uyarılar.
- **Detaylı mod:** 11 sayfa — Genel, Motor, Yağ, Soğutma, Akü, Lastik & yakıt, Sürüş & fren, Yolculuk, Bakım planı,
  Analiz, Arıza & kayıt.
- **Uyarı şeridi:** ekranın üst ortasında; varsayılan olarak yalnızca kritik uyarılar yanıp söner (ikaz sesini
  simülatör çalar, aşağıya bakın).
- **Menüde gizlenir:** oyun duraklatılınca (ana menü, Esc menüsü, harita, yükleme ekranı) katmanın tamamı geçici olarak
  gizlenir, sürüşe dönünce aynı düzende geri gelir; bu sırada F8 tuşları yok sayılır. TruckersMP'de oyun Esc menüsünde
  durmadığı için katman açık kalır; orada `F3` ya da `F8` ile gizleyebilirsiniz.
- **Gösterge lambaları:** ekranın alt ortasında, gerçek kamyon göstergesindeki gibi ikaz lambaları (aşağıya bakın).

| Kısayol (oyunda) | İşlev |
|---|---|
| `F8` | Kapalı → kompakt → detaylı |
| `Shift+F8` | Sonraki sayfa |
| `Ctrl+F8` | Köşe değiştir (sol üst → sağ üst → sağ alt → sol alt) |
| `Ctrl+Shift+F8` | Boyut değiştir (hazır boyutlar: panel ve lambalar) |
| `Ctrl+Alt+F8` | Fareyle taşıma ve boyutlandırma (panel ve gösterge lambaları) |
| `Alt+F8` | Servis menüsünü aç / kapat |
| `F3` (oyunun HUD tuşu) | Katmanı oyunun haritasıyla birlikte gizle / göster |
| `F10` (değiştirilebilir) | Sürüş modu: ECO → COMFORT → SPORT (aşağıya bakın) |
| Çekim modu tuşu (atanırsa) | Ayarlar → *Çekim modu*'nda seçili arızayı hemen tetikler (yalnızca tek oyunculu; aşağıya bakın) |

### Oyun içi servis menüsü (`Alt+F8`)

Yağ ekleme/değiştirme, antifriz, akü, DPF ve onarım işlemleri oyundan çıkmadan yapılabilir. Menü açıkken F8 tuşları
menüyü yönetir:

| Tuş | İşlev |
|---|---|
| `F8` / `Shift+F8` | Aşağı / yukarı |
| `Ctrl+F8` | Seçili işlemi uygula (pahalı ya da geri dönüşsüz işlemlerde onay için **ikinci kez** basın) |
| `Alt+F8` | Menüyü kapat |

Menüde: 1 L yağ ekle, yağı MAX'a tamamla, yağ + filtre değişimi (3 yağ tipi), yalnız filtre, yağ numunesi;
antifriz tamamlama (50/50), soğutma sıvısı değişimi, refraktometre ölçümü; şarj cihazı, takviye kablosu, akü testi,
akü yenileme; şanzıman yağı değişimi ve debriyaj yenileme; DPF servis rejenerasyonu ve kül temizliği; aktif
arızaların onarımı ve motor revizyonu. Her maddede
fiyat yazar. Uygulamadaki **Servis** işlemleriyle aynı kurallar geçerlidir: çoğu işlem için tır durmalı ve motor
kapalı olmalı (yapılamayan maddeler soluk görünür, seçince nedeni yazar). Sonuç menünün altında görünür.

F8 oyunda boş bir tuştur. Ayarlar `%LOCALAPPDATA%\ETS2Bakim\overlay.ini` dosyasında saklanır.
F8 başka bir işe atanmışsa Ayarlar → Oyun içi katman → *Katman tuşu* ile başka bir klavye tuşu seçilebilir (1.11+);
bütün kombinasyonlar (Shift, Ctrl, Alt) o tuşla çalışır, katmandaki kısayol yazıları da onu gösterir.

**Oyun içi panel ayarı (1.11+, Ayarlar → Oyun içi katman):** *Otomatik*te oyun klasöründe OptiScaler ya da DLSS 5
eklentisi varsa veya oyun bir önceki açılışta donup düzgün kapanmadıysa panel o açılışta kurulmaz (bu eklentilerle
oyunun donduğu bildirildi). *Açık* her zaman kurar, *Kapalı* hiç kurmaz; değişiklik oyun yeniden açılınca uygulanır.
Panel kurulmasa da sürüş modları, motor durdurma ve lastik patlaması (oyunun giriş cihazı) çalışır.

### Gösterge lambaları

Oyunun kendi gösterge panelindeki ikaz lambaları (devir saati yanındaki yağ, akü, hararet lambaları) oyunun **kendi iç
değerlerine** bağlıdır. SCS SDK kamyon değerlerini yalnızca okumaya izin verir; bu lambalar dışarıdan yakılamaz. Bu
yüzden simülatörün bulduğu sorunlar katmanın alt ortasında, gerçek göstergedeki simgelerle lamba olarak yanar.
**Sarı** = dikkat / bakım, **kırmızı** = hemen müdahale. Yeni yanan kırmızı lamba ilk 6 saniye, STOP ise sürekli
yanıp söner.

**Önem dereceleri ve gösterme ayarı:** her lamba durumunun beş önem derecesinden biri vardır. Ayarlar →
*Gösterilecek lambalar* ile hangi dereceden itibaren yanacaklarını seçersiniz (varsayılan: hepsi). Renk dereceden
gelir: ciddi ve kritik kırmızı, diğerleri sarı.

| Derece | Renk | Örnekler |
|---|---|---|
| **Önemsiz** | sarı | Bilgi: ön ısıtma sürüyor, DPF rejenerasyonu bekliyor / yapıyor |
| **Önemli** | sarı | Bakım zamanı: yağ / şanzıman yağı değişimi, debriyaj balatası %85, lastik dişi azaldı, akü sağlığı, motor sağlığı, DPF külü, oyunun şanzıman hasarı |
| **Uyarı** | sarı | Sarı arızalar ve sınır değerler: ABS sensörü, marş motoru, direksiyon kaçağı, şanzıman soğutucusu, park freni çekilmedi, sıcaklık yüksek, seviye MIN altında, lastik basıncı ayarsız, yakıt / AdBlue az |
| **Ciddi** | kırmızı | Şarj yok, akü marşa yetmiyor, fren aşırı sıcak, fren havası düşük, park freni çekiliyken hareket, direksiyon desteği yok, şanzıman / debriyaj aşırı sıcak, balata bitti, lastik patladı, yağ / su seviyesi kritik, DPF tıkalı, AdBlue bitti, donma |
| **Kritik** | kırmızı | Motoru hemen durdurun: STOP, yağ basıncı düşük, hararet ve kaynama, motor kilitlendi, patlak lastikle ya da acil fren havasıyla hareket |

| Lamba | Kırmızı | Sarı |
|---|---|---|
| **STOP** (Durun) | Motor gerçekte durdu (kilitlendi, akü bitti…), yağ basıncı düşük, hararet, kaynama, patlak lastikle ya da acil fren havasıyla sürüş | — |
| **Akü** | Şarj yok (alternatör arızası), voltaj kritik, akü dondu ya da marşa yetmiyor | Şarj %50 altı, akü sağlığı %60 altı, donma riski |
| **Yağ** | Yağ basıncı düşük ya da seviye %70 altı | Seviye MIN altında ya da MAX üstünde |
| **Soğutma** | 110 °C üstü, kaynama ya da seviye %70 altı | 104 °C üstü ya da seviye %85 altı |
| **Fren** | Fren sıcaklığı 450 °C üstü ya da fren devresinde hava basıncı düşük | 320 °C üstü |
| **El freni** (P) | Park freni çekiliyken hareket | Motor kapalı, kontak açık, tır duruyor ve park freni çekilmemiş (3 sn sonra) |
| **ABS** | — | ABS tekerlek hızı sensörü arızası (ABS ve ESC devre dışı) |
| **Şanzıman** | Şanzıman yağı 130 °C üstü, debriyaj 320 °C üstü ya da balata bitti | Yağ 115 °C / debriyaj 250 °C üstü, balata %85 aşındı, şanzıman yağı değişim zamanı, yağ soğutucusu ya da debriyaj aktüatörü arızası, oyunun şanzıman hasarı %30 üstü |
| **Direksiyon** | Hidrolik destek yok: motor çalışmıyorken tır gidiyor ya da hidrolik yağı %60 altı | Direksiyon hidrolik kaçağı (yağ eksiliyor) |
| **Marş** | — | Marş motoru arızası (zaman zaman çevirmez) |
| **Lastik** (basınç izleme) | Lastik patladı, basınç %75 altı, diş 1,6 mm altı ya da 115 °C üstü | Yavaş patlak, basınç ayarsız, diş azaldı ya da 95 °C üstü |
| **AdBlue** | AdBlue bitti | %10 altı |
| **Yakıt** | — | Oyunun düşük yakıt sınırının (genelde %15) altında |
| **Motor** | Motor çalışmaz durumda (kilitlenme, blok çatlağı, conta yanması) | Termostat açık kaldı, fan kavraması arızası, motor sağlığı %40 altı, egzoz aşırı sıcak |
| **DPF** | Filtre %120 dolu (tıkalı) | Rejenerasyon bekliyor / yapıyor, %100 dolu, kül ya da karşı basınç kritik |
| **Isıtma** (ön ısıtma) | Ön ısıtma arızası (soğukta yanıp söner) | Kontak açıldı, ön ısıtma sürüyor: sönünce marşa basın |
| **Donma** | Hava antifrizin donma noktasının altında ya da sistemde buz var | Antifriz bölgede beklenen en düşük sıcaklığa yetmiyor |
| **Bakım** | Yağ ömrü bitti | Yağ ömrü %10 altı, değişim km'si doldu, filtre tıkalı, antifriz inhibitörü ya da ömrü bitti |

- Lambalar gerçek araçtaki gibi **sensörün göreceği şeye** göre yanar. Örneğin sızdıran su pompası seviye düşene kadar
  lamba yakmaz, alternatör arızası ise şarj lambasını hemen yakar. Kontak kapalıyken gösterge karanlıktır.
- Katman `F8` ile kapalıyken de lambalar yanar; `F3` (HUD) ile ve menüde gizlenir. Ayarlar → *Gösterge lambaları*
  ile tamamen kapatılabilir.
- Katmanda yalnızca sarı ve kırmızı ikaz lambaları vardır; yeşil, mavi ve beyaz bilgi lambaları (sinyal, far, hız
  sabitleyici…) oyunun kendi göstergesinde görünür. Oyunun kendi lambaları oyunun değerlerine göre çalışmaya devam eder.
- Önem süzgeci yalnızca katmandaki lambalar içindir; uyarı şeridi, uygulamadaki uyarılar ve ikaz sesi Ayarlar →
  *Uyarı düzeyi* (Az / Normal / Hepsi) ayarına göre çalışır.
- Her lamba ayrıca tek tek kapatılabilir: Ayarlar → *Uyarılar ve ikaz lambaları* (aşağıda).

### Uyarılar ve ikaz lambalarını tek tek açma / kapama

Ayarlar → **Uyarılar ve ikaz lambaları** kartında simülatörün bütün uyarıları (90: motor, yağ, soğutma, akü, fren,
direksiyon, şanzıman, DPF, yakıt / AdBlue, lastikler, 18 parça arızası, tek / çok oyunculu bildirimleri)
gruplar hâlinde ve katmandaki 18 ikaz lambası tek tek listelenir; her biri bir kutuyla açılıp kapatılır. Grup kutusu
grubun tamamını, *Hepsini aç / Hepsini kapat* hepsini değiştirir (kapatma onay ister). Kapatılan uyarı ne uygulamanın
listesinde ne oyun içi katmanda (şerit dahil) görünür, ikaz sesi de çıkarmaz; kapatılan lamba katmanda yanmaz.
Yalnızca gösterim değişir: aşınma, arızalar ve motor durdurma aynen sürer. *Uyarı düzeyi* ve *Gösterilecek lambalar*
süzgeci bunlara ek olarak uygulanır. Ayar her uygulamanın kendi ayar dosyasındadır (`warnings_off`, `lamps_off`);
uyarıların kalıcı anahtarları ve grupları `ets2bakim/alerts.py`'dedir.

**Motor durdurma:** Eklenti, oyunun resmi Input SDK'sıyla "ETS2 Bakim" adlı bir *semantik* giriş cihazı kaydeder.
Akü bitince, motor kilitlenince vb. **yalnızca motoru durdurur**; kontak, ekranlar ve ışıklar açık kalır. Komut
2,5 saniyede etkisiz kalırsa yedek olarak `E` tuşunu gönderir. Tuş ataması gerekmez, oyun arka plandayken de çalışır.

**Notlar**
- Oyun DirectX 11 ile çalışmalı (varsayılan). OpenGL/Vulkan modunda katman görünmez; simülatör ve motor durdurma yine çalışır.
- TruckersMP'nin kendi katmanıyla çakışırsa katmanı kaldırmak için DLL'i silmeniz yeterli; simülatör ve uygulama
  penceresi katmansız da çalışır.
- Bazı antivirüs programları DirectX'e kanca atan DLL'leri şüpheli bulabilir. Kaynak kodu `overlay\src` klasöründedir.
- Yeniden derlemek için: `powershell -ExecutionPolicy Bypass -File overlay\build.ps1` (MinGW-w64 gerekir; Akıllı
  Uygulama Denetimi kapalı olmalı).

## Otomatik motor seçimi

Telemetri motor gücünü vermez, yalnızca kamyonun marka/modelini verir. Bu yüzden iki aşamalı çalışır:

1. **Model veritabanı:** Kamyon ilk görüldüğünde marka/modelden (Volvo FH, Scania R/S/Streamline, Mercedes Actros
   MP3/MP4/MP5, MAN TGX, DAF XF/XG/XD, Renault T/Magnum/Premium, Iveco Stralis/Hi-Way/S-Way ve ATS kamyonları) o modelin
   gerçek motor seçenekleri yüklenir. Yaygın motor; gücü, torku, hacmi, yağ ve su kapasitesi, DPF olup olmadığı ile seçilir.
2. **Sürüşten algılama:** Tam gazda, sabit viteste ve 1000–1450 rpm aralığında birkaç saniye sürdüğünüzde (dolu yükle yokuş
   çıkmak idealdir), vites oranı × diferansiyel, tekerlek yarıçapı, ivme, yol eğimi, yük kütlesi, yuvarlanma ve hava direncinden
   motorun tepe torku hesaplanır. Ölçüm tutarlıysa modelin motorları içinden en yakını otomatik seçilir ve kayda yazılır.

Ayarlar sekmesinde motoru listeden seçebilir veya değerleri elle girebilirsiniz; bu durumda otomatik algılama kapanır
("Yeniden algıla" ile tekrar açılır). Tanınmayan modellerde değerleri elle girin. Değer sınırları araç sınıfına göredir
(TruckersMP otomobilinde ör. motor hacmi 0,9–4 L, yağ 3–10 L, akü 40–120 Ah; otomobilin torku yalnızca gösterilir).

## Neler simüle ediliyor?

| Sistem | Ayrıntı |
|---|---|
| **Konum ve iklim** | Oyun koordinatları gerçek enlem/boylama çevrilir (ETS2'nin Lambert konik projeksiyonu). Dış sıcaklık enlem, boylam (karasallık), gerçek takvimdeki mevsim, oyun saati (gece/gündüz), rakım ve günden güne hava sapmasından hesaplanır. Silecek açıksa yağmur kabul edilir. |
| **Motor** | Tork eğrisi, yük (gaz + hız sabitleyici), güç, yakıt debisi (oyunun gerçek tüketiminden ölçülür), sürtünme, motor freni, hidrolik retarder ısısı, egzoz sıcaklığı. |
| **Isıl model** | Soğutma suyu + blok ve yağ ayrı düğümler. Termostat (83/95 °C), viskoz fan, araç hızıyla radyatör hava akışı, kabin kaloriferi, basınç kapağı (0,75 bar), kaynama ve buhar kaybı. |
| **Motor yağı** | 12 yağ tipi: 15W-40 E7, 15W-40 E9 Low-SAPS, 15W-40 CK-4 yarı sentetik, 10W-30 E9, 10W-40 E4/E7, 10W-40 E6, 10W-40 E11/CK-4, 5W-40 E7/E9, 5W-30 E6, 5W-30 E4 uzun ömürlü, 0W-30 E6 (çok soğuk iklim), 20W-50 mineral (eski motorlar; soğukta marş zor). Düşük küllü (Low-SAPS) yağlar DPF'yi geç doldurur. Sıcaklığa göre viskozite (Walther), TBN tükenmesi, is, oksidasyon, VII kesme, yakıt seyrelmesi (rölanti/soğuk/rejen), yoğuşma suyu, glikol, aşınma metalleri (Fe, Cr, Pb, Cu, Al, Si, K), filtre doluluğu/bypass, yağ yakma, devir/viskoziteye bağlı yağ basıncı. Gerçek laboratuvar raporu gibi **yağ analizi**. |
| **Antifriz** | 8 tip: OAT, IAT, HOAT (G11/G05), Si-OAT (G12++/G13), Si-OAT G12evo (ömür boyu dolum), P-OAT (fosfatlı; musluk suyunda çok kireç), NOAT (nitritli; ıslak gömlekli ağır dizel), nitritsiz HOAT (Volvo VCS / Renault Type D). Glikol oranına göre donma ve kaynama noktası, tipe göre ömür ve inhibitör tükenmesi, pH, kireç birikimi (musluk suyu), seviye ve kaçaklar. Saf su eklemek korumayı düşürür. Antifrizsiz suyla donma **bloğu/radyatörü çatlatır**. |
| **Akü ve elektrik** | 2 x 12 V seri akü grubu; 140–240 Ah (12 boy), 5 tip: standart (SHD), EFB (2 kat döngü ömrü, daha az sülfatlaşma), AGM (3 kat döngü ömrü, düşük iç direnç ve kendi kendine boşalma), jel (4 kat döngü ömrü, derin deşarja dayanıklı), ağır hizmet AGM (park klimalı tırlar için 4,5 kat döngü ömrü). Şarj durumu, sağlık, sülfatlaşma, iç direnç, Peukert etkisi, sıcaklık, şarj kabulü. Işıklar, silecek ve kontaktan gelen yükler. Silecek kademeye göre çeker: aralıklı ~1,2 A, yavaş ~3,5 A, hızlı ~5,5 A (0 °C altında kar/buz yüzünden %25 fazla). Oyun telemetrisi yalnızca "silecek açık/kapalı" bildirdiği için kademe, oyundaki silecek tuşundan (`controls.sii` atamaları: klavye, kumanda/direksiyon düğmesi ya da yön tuşu) yalnızca oyun penceresi öndeyken izlenir; silecek kapanınca sayaç sıfırlanır. Alternatör çıkışı devire bağlı. Marş akımı yağ viskozitesine bağlı: soğukta zayıf akü veya kalın yağla **marş başarısız**. Boş akü donabilir. Uykuda park ısıtıcısı/kliması aküden çeker. |
| **DPF** | Yüke bağlı is üretimi, pasif ve aktif rejenerasyon (40 km/h üstü), yağdan gelen kül (düşük SAPS yağ farkı), servis rejenerasyonu ve kül temizliği. |
| **Lastikler** | Dingil başına (ön, çekiş, taşıyıcı; düzen oyunun tekerlek verisinden): diş derinliği (yeni 16/20 mm, yasal sınır 1,6 mm), soğuk ayar basıncı (ön 9,0 / arka 8,5 bar) ve sıcaklığa göre şu anki basınç, lastik sıcaklığı. Aşınma yük, hız, basınç, sıcaklık, sert fren, viraj (ön), çekiş (tahrikli) ve yol yüzeyine (toprak/çakıl 2 kat) bağlı; kaldırılmış dingil aşınmaz. Basınç ayda ~0,15 bar kendiliğinden düşer; rastgele yavaş patlak (ortalama 90 bin km'de bir, çakılda 3 kat sık). Düşük basınçla ısınan ya da dişi bitmiş lastik patlayabilir. Servis: basınç ayarı, patlak tamiri, dingil başına lastik değişimi; 4 sınıf: premium, orta sınıf (%12 hızlı aşınır), ekonomik (%35 hızlı aşınır, ısınmaya daha az dayanıklı), kaplama (yalnız arka dingiller; ucuz ama ısınınca daha kolay patlar). Oyunda serviste tekerlek hasarı onarılınca lastikler de yenilenir. **Patlamada oyunda fiziksel etki** (yalnızca tek oyunculu, Ayarlar'dan kapatılabilir): katman eklentisi oyunun fren ve direksiyon girdisine ölçülü değer ekler (sizin kontrolünüz korunur): ilk ~1,5 sn sert sürüklenme ve patlayan tarafa çekme (arka dingilde kuyruk sallanması), sonra tır durana kadar jant sürtmesi ve titreşim. Uygulama kapanırsa etki 0,5 sn içinde kalkar. Oyunun kendi lastik modeli değişmez; tır görsel olarak patlak görünmez. |
| **Yakıt ve AdBlue** | Yakıt seviyesi, kamyonun ölçülen uzun dönem tüketimiyle menzil, düşük yakıt uyarıları. ETS2 AdBlue harcamadığı için tüketim simülatörde: katalizör ısınınca yakıtın ~%3–7'si (yükle artar). Oyunda yakıt alınca AdBlue da pompadan tamamlanır (Ayarlar). Bittiğinde gerçek araçtaki güç düşürme ve 20 km/h sınırı uyarısı verilir; AdBlue −11 °C'de donar. |
| **Ön ısıtma** | Dizelde buji yoktur; soğukta kontak açılınca kızdırma bujisi / ızgara ısıtıcı ön ısıtma yapar (5 °C altında; 0 °C'de ~12 sn, -20 °C'de ~30 sn, gerçek zaman), aküden ~150 A çeker. Lamba sönmeden marş: zor ateşleme ve ek aşınma; -15 °C altında yarıdan az ısıtılmış motor hiç ateşlemez. Arızalı ön ısıtma soğukta ısıtmaz (-5 °C altında motor çalışmaz). |
| **Şanzıman ve debriyaj** | Şanzıman yağı sıcaklığı oyun saatiyle: dişli kayıpları (doğrudan viteste iletilen gücün ~%1,5'i, ara viteslerde ~%2,5'i) ve çalkalama ısıtır; retarderli tırlarda yağ-su eşanjörü motor soğutma suyuna bağlar, retardersizde gövde ve hava akışı soğutur; intarder frenleme gücünün küçük bir kısmını yağda bırakır. Otoyolda ~65–75 °C, sıcak havada uzun tam yük yokuşta ~105–115 °C, uzun retarderli inişte ~120 °C (sarı 115, kırmızı 130 °C). Yağ 100 °C üstünde hızlı yaşlanır; değişim aralığı 450.000 km (otomobil DSG 60.000 km). Debriyaj gerçek saniyeyle: motor devri ile şanzıman giriş mili devri (tekerlek hızı × vites oranı × diferansiyel) arasındaki fark ve kavrama oranından kayma gücü; yalnızca debriyaj gerçekten yarım kavrarken (kalkış, manevra, yarım debriyajla sürünme). Dolu kalkış ~10 °C ısıtır, 2 dk yarım debriyajla sürünme 320 °C'yi aşar. Balata kayma enerjisiyle aşınır (200 °C üstünde çok hızlı); kalan ömür tırın kendi aşınma hızından tahmin edilir. Servis: şanzıman yağı değişimi, debriyaj yenileme. |
| **Direksiyon** | Hidrolik direksiyon pompası motordan döner: motor dururken giden tırda destek kalmaz (kırmızı lamba, kritik uyarı). Hidrolik kaçağında yağ eksilir; %60 altında destek azalır. Otomobilde elektrikli direksiyon (EPS). |
| **Arızalar** | Kilometreye bağlı Weibull dağılımıyla alternatör, termostat (açık/kapalı takılma), fan kavraması, su pompası, karter contası, ön ısıtma, şanzıman yağ soğutucusu (yağ aşırı ısınır), debriyaj aktüatörü (debriyaj yükte kayar, ısınır), direksiyon hidrolik kaçağı, ABS tekerlek hızı sensörü, marş motoru (marş denemelerinin ~%40'ı başarısız), turbo (yağ yakar: tüketim 4 kat, DPF iki kat hızlı dolar), enjektör (DPF ve motor aşınması artar), EGR valfi, intercooler kaçağı, hava filtresi (DPF ve aşınma artar), yakıt filtresi, radyatör sızıntısı (soğutma suyu sürüşte hızla eksilir) ve kayış (alternatör şarj etmez, su pompası ve fan dönmez: hararet) arızaları. Sarı arızalar (şanzıman, direksiyon, ABS, marş) kritik değildir: lamba yakar, servis gerektirir. Kötü kullanımdan doğan hasarlar: silindir kapak contası (hararet), motor kilitlenmesi (yağsız kalma / aşırı ısı), donma çatlakları, akü donması. Yağ pompası arızası (basınç uyarı eşiğinin altında kalır) yalnızca *Çekim modu* ile tetiklenir. |
| **Arıza tespiti** | Motor Analizi sekmesinin başında, Grand Truck Simulator 2'deki *Diagnosis* ekranı gibi: motor bilgileri (motor, yakıt, hacim, güç, tork, devir, yağ, antifriz, akü), parça durumu ve seviyeler (yağ, soğutma suyu, AdBlue, direksiyon yağı, yakıt). Ana bileşenlerin yüzdesi kendi modelinden (motor sağlığı, yağ ömrü, antifriz ömrü, akü sağlığı, DPF külü, debriyaj balatası); diğer 19 parçanınki yaşına göre arıza yapmadan çalışma olasılığıdır (Weibull; yeni %100, ortalama ömründe ~%43, arızalı %0). Yıpranan parça arıza çıkmadan *Değiştir* ile yenilenir (Servis'teki onarımla aynı ücret, tır durmuş ve motor kapalıyken). |
| **Motor analizi** | Devir x yük haritası, eko bant, rölanti, hız sabitleyici, yakıtsız yuvarlanma, retarder, lugging, aşırı devir, soğuk motora yüklenme, sert fren, marş istatistikleri, sürüş puanı. Her 250 km'de motor sağlığı, yağ metalleri, akü sağlığı trendi. |

### Azalma hızları (Ayarlar → *Azalma hızları*)

Değerlerin ne kadar hızlı azalacağını ayarlayabilirsiniz: bir **genel** çarpan ve sistem başına çarpanlar
(etkin hız = genel × sistem, kaydırıcıyla 0–5×). 1× gerçekçidir; 0,5× yarı hızda (iki kat uzun dayanır),
2× iki kat hızlı, 0× o değer hiç azalmaz. Hazır düğmeler: *Gerçekçi (hepsi 1×)*, *Kolay (0,5×)*, *Çok kolay (0,25×)*, *Zor (2×)*, *Çok zor (5×)*.

| Çarpan | Etkilediği |
|---|---|
| Motor yağı | TBN, is, oksidasyon, viskozite, yakıt seyrelmesi, aşınma metalleri, değişim aralığı (km ve takvim), yağ eksilmesi, filtre dolması |
| Antifriz | İnhibitör tükenmesi, değişim aralığı (gün ve km), kireçlenme, buharlaşma |
| Akü sağlığı | Yaşlanma, sülfatlaşma, kendi kendine boşalma |
| Akü boşalması | Elektrik yüklerinin aküyü boşaltma hızı (şarj olma hızı değişmez) |
| Lastikler | Diş aşınması, doğal basınç kaybı |
| DPF · AdBlue | İs ve kül dolması · AdBlue tüketimi |
| Motor aşınması | Motor sağlığının normal kullanımda azalması |
| Şanzıman ve debriyaj | Debriyaj balatası aşınması, şanzıman yağının yaşlanması (değişim aralığı) |
| Arıza sıklığı | Rastgele parça arızaları ve yavaş patlaklar |

Kullanım hatasının verdiği hasar (hararet, yağsız sürüş, donma, ön ısıtmasız marş), arızadan kaynaklanan kaçaklar ve
akünün şarj olması çarpandan etkilenmez. Değişim aralıkları ve bakım planı seçilen hıza göre gerçek km/gün olarak uzar
ya da kısalır (ör. 0,5× yağda *Bu yağla gidilen 20.000 / 100.000 km*: kalan 40.000 km'lik aralık 80.000 km sürer).
Hız yolda değiştirilirse o ana kadarki kullanım korunur, yalnızca kalan kısım yeni hızla işler. 1× dışındaki
sistemlerin kart başlığında *azalma hızı 0,5×* etiketi görünür.

### TruckersMP araçları: otomobil ve otobüs

TruckersMP'nin kendi araçları da tanınır ve kendi özellikleriyle simüle edilir (araç tanımları TruckersMP'nin oyun
dosyalarından okundu):

| Araç | Sınıf | Motorlar | Simülasyondaki farklar |
|---|---|---|---|
| **Škoda Superb** | Otomobil | 1.8 TSI benzinli 160 hp / 250 Nm · 2.0 TDI dizel 170 hp / 320 Nm (varsayılan) | 12 V tek akü (72 Ah AGM, 140 A alternatör, otomobil marş akımı), otomobil yağları (VW 504/507 5W-30, 508/509 0W-20, 502/505 5W-40; 4,3–4,6 L), G13 antifriz, 4 tekil lastik (235/45 R18, ön 2,5 / arka 2,4 bar, 8 mm), oto servisi fiyatları; benzinlide DPF, AdBlue ve ön ısıtma yok |
| **Scout Extra_D Estate** | Otomobil | aynı iki motor | Superb ile aynı |
| **HVT Tourvego 16 SHD** | Otobüs | OM 470 FE 456 hp (335 kW, 2200 Nm, 10,7 L) | 24 V, DPF ve AdBlue, 2 x 225 Ah; yolcu kliması/ısıtması için elektrik yükü %25 fazla |

- TruckersMP otomobilinde iki motorun oyundaki torku aynıdır; motor sürüşten algılanamaz. Benzinli ya da dizel motoru
  Ayarlar → *Bu kamyonun motoru* listesinden seçin.
- Otomobilde ECO sürüş modunun 85 km/h hız sınırı yoktur. Kaplama (sırtı yenilenmiş) lastik otomobile takılmaz.
- Uygulama otomobil ve otobüs için de aynı sekmeleri gösterir. Akü sekmesinde sistem (12 V / 24 V), panel başlığında
  araç sınıfı görünür.

### Tek oyunculu otomobil ve otobüs modları: Ayarlar → *Araç tipi*

Tek oyunculu otomobil ve otobüs modlarını (Togg, Passat, Fiat, otobüs modları…) oyun telemetride tır olarak bildirir ve
model veritabanı bunları tanımaz; bu yüzden 24 V akü ve tır yağıyla simüle edilirler. Ayarlar → *Bu kamyonun motoru* →
**Araç tipi** ile sınıf elle seçilir (seçim o araca kaydedilir; diğer tırlarınız etkilenmez):

| Seçim | Ne olur |
|---|---|
| **Otomatik** (varsayılan) | Sınıf motor veritabanındaki modelden gelir (bilinmeyen araç = tır) |
| **Tır** | Tır varsayılanları; model tır değilse bilinmeyen motor (500 hp) varsayılır, değerler Ayarlar'dan girilir |
| **Otobüs** | 24 V, yolcu kliması/ısıtması için %25 fazla elektrik yükü; model otobüs değilse genel otobüs motor listesi (OM 470, MAN D2676, Scania DC13, Volvo D13K) |
| **Otomobil** | 12 V tek akü (72 Ah AGM), otomobil yağı (VW 504/507 5W-30), G13 antifriz, 4 tekil lastik (2,5 / 2,4 bar), otomobil sınırları ve oto servisi fiyatları; model otomobil değilse genel otomobil motor listesi: 1.0 / 1.5 / 2.0 turbo benzinli, 1.6 / 2.0 dizel (150 ya da 190 hp) |

- Sınıf değişince (uygulama önce onay sorar) aracın motoru, aküsü, yağı, antifrizi, lastikleri ve şanzımanı yeni
  sınıfın varsayılanlarına göre yeniden kurulur; yağ ve su seviyeleri oran olarak korunur. Seçim için oyunda o araçla
  bağlı olun. *Bu tırın değerlerini sıfırla* seçimi korur.
- Benzinli ya da dizel motoru aynı bölümdeki *Motor* listesinden seçin (otomobilde motor sürüşten algılanmaz).
- Oyun içi devir sınırı 3000 rpm'den yüksek (ör. gerçek otomobil devriyle 6000–7000 rpm) çalışan modlarda motor
  modeline devir orantılı küçültülerek verilir: güç, ısı ve *Aşırı devir* uyarısı otomobil devrine göre çalışır,
  gösterilen devir oyununkidir.
- Elektrikli araçlar (ör. gerçek Togg T10X) simüle edilmez: simülatör içten yanmalı motorlar içindir.

### Sürüş modları: ECO / COMFORT / SPORT

Gerçek kamyonlardaki sürüş modu seçicisi gibi. Oyun içi katman (1.8+), oyunun gaz girdisine değer ekleyip çıkararak gaz
pedalınızın haritasını moda göre değiştirir. Bu, oyunun kendi kontrol sistemi üzerinden yapılır (`controls.sii`:
`semantical.aforward`). Tır gerçekten ona göre hızlanır, yakıt tüketimi de buna göre değişir.

| Mod | Etkisi |
|---|---|
| **ECO** | En fazla %75 güç, gaz yavaş artar (0,6/sn), 85 km/h hız sınırlayıcı (elle sürüşte) |
| **COMFORT** (varsayılan) | Güç sınırı yok, gaz yumuşak artar (1,5/sn): sarsıntısız kalkış ve geçişler |
| **SPORT** | Keskin pedal: gaz = 1 − (1 − pedal)^1,8, yarım pedalda ~%71 gaz, anında tepki |

- **Mod değiştirme:**
  - Oyunda mod tuşu (varsayılan **F10**) modları sırayla değiştirir.
  - Uygulamada Ayarlar → *Sürüş modu* kartındaki düğmelerle ya da üst çubuktaki mod etiketine tıklayarak da değiştirebilirsiniz.
  - Mod değişince katmanda kısa bir bildirim çıkar; panelin başlığında mod etiketi görünür.
- **Tuş seçme:**
  - Ayarlar → *Sürüş modu* → **Tuş ata**'ya basın, sonra istediğiniz klavye tuşuna ya da direksiyon / kumanda düğmesine
    (yön tuşu dahil) basın. 10 saniye beklenir; `Esc` iptal eder.
  - Tuş yalnızca oyun penceresi öndeyken sayılır; menüdeyken modu değiştirmez. `F8` (katmanın tuşu) atanamaz.
  - Seçtiğiniz tuşun oyunda başka bir işe atanmamış olmasına dikkat edin.
- **Gaza karışılmayan durumlar:**
  - Hız sabitleyici açıkken modlar gaza karışmaz.
  - Ayarlardaki *Sürüş modları* kutusu kapatılırsa gaz pedalına hiç dokunulmaz.
  - Simülatör kapanırsa eklenti 1,5 saniye içinde gaza karışmayı bırakır.
- **Çok oyunculu:** Tek ve çok oyunculuda (TruckersMP) çalışır; yalnızca kendi gaz pedalınızı etkiler. Çok Oyunculu
  modda varsayılan olarak kapalıdır (TruckersMP'nin gaza müdahale konusundaki tutumu doğrulanmadı); Ayarlar'dan açılabilir.
- **Bilinen sınırlama:** Eklenti oyuncunun gazını oyunun telemetrisinden (`truck.input.throttle`) okur. Gönderdiği
  düzeltme oyuna bir iki kare gecikmeyle yansıyabildiği için (1.15.0'dan beri) yeni değeri ancak önceki değer oturunca
  (en az 3 kare ve 35 ms) hesaplar; %1'den küçük değişiklikleri (pedal titremesi) göndermez. Bu yüzden düzeltme pedala
  ~35–50 ms geriden gelir; pedal bırakılınca eklenen gaz beklemeden kalkar. 1.14'te düzeltme her karede gönderiliyordu:
  gürültülü pedalda neredeyse her karede bir olay oluyor, gecikmede gaz kare kare salınıyordu (SPORT'ta gaz verip
  bırakırken oyun takılıyordu). Gaz yine de ileri geri salınırsa eklenti modu 10 saniye devre dışı bırakır ve oyun
  günlüğüne (`game.log.txt`, `[ets2bakim] surus modu: gaz salinimi algilandi`) yazar.

### Değer güncelleme sıklığı (Ayarlar → *Değer güncelleme sıklığı*)

Değerlerin ne sıklıkla yenileneceği uygulama penceresi ve oyun içi katman için ayrı ayrı seçilir:

| Seçenek | Ne olur |
|---|---|
| **Gerçek zamanlı (0 sn)** | Simülasyon saniyede 20 adım çalışır, her adım hemen gösterilir (en çok işlemci) |
| **0,1 sn** | Saniyede 10 kez (oyun içi katmanın varsayılanı) |
| **0,25 sn** | Saniyede 4 kez (uygulama penceresinin varsayılanı) |
| **0,5 / 1 / 2 / 5 sn** | Daha seyrek: bilgisayar daha az çalışır |

- Uyarılar, ikaz lambaları ve uyarı sesleri seçilen aralığı beklemez: yeni bir uyarı ya da lamba hemen gelir.
- Pencere değerleri sunucudan canlı akışla (`/api/stream`, Server-Sent Events) alır; akış çalışmazsa aynı aralıkta yoklar.
  Pencere simge durumundayken güncelleme durur, açılınca hemen sürer.
- Katman aralığı uzunken de eklenti simülatörü canlı görür (her adımda canlılık sayacı yazılır), servis menüsü komutları
  her adımda okunur.
- Ayar Tek ve Çok Oyunculu modda ortaktır (dil ve oyun modu gibi).

### Çekim modu: arızayı istediğiniz anda tetikleme (yalnızca tek oyunculu)

Video çekimi için (korku videosu, ikaz lambası anlatımı…): Ayarlar → **Çekim modu**.

1. **Çekim modu** kutusunu işaretleyin (kapalıyken kısayol tuşu ve tetikleme düğmesi çalışmaz).
2. **Tetiklenecek arıza** listesinden seçin. Altında arızanın etkisi ve hangi ikaz lambasının hemen, hangisinin belirti
   çıkınca yandığı yazar. Liste: yağ pompası (YAĞ BASINCI DÜŞÜK), karter sızıntısı, conta, motor kilitlenmesi, termostat
   (kapalı / açık takılı), fan kavraması (hararet), su pompası, alternatör (ŞARJ YOK), marş motoru, ön ısıtma, ABS
   sensörü, şanzıman soğutucusu, debriyaj aktüatörü, direksiyon kaçağı, ön / arka lastik patlaması ve yavaş patlak.
3. **Şimdi tetikle**'ye basın ya da **Kısayol tuşu** atayıp oyunda o tuşa basın (*Tuş ata* → klavye tuşu ya da
   direksiyon / kumanda düğmesi, 10 sn, `Esc` iptal). Tuş yalnızca oyun penceresi öndeyken ve oyun duraklatılmamışken
   sayılır. Varsayılan tuş yoktur: oyunun F tuşlarının çoğu dolu, `F10` sürüş modunda; aynı tuş iki işe atanamaz.
4. Çekim tekrarı için **Hepsini onar**: tüm arızaları ve lastik hasarını ücretsiz giderir. Sıvı seviyeleri, akü şarjı ve
   sıcaklıklar değişmez (gerekirse servis menüsünden tamamlayın).

- Tetiklenen arıza kendiliğinden çıkmış gibi işler: aynı uyarı, ikaz lambası, ses ve sonuçlar (hararet, akü boşalması,
  ECU kapanması, motor kilitlenince motorun durdurulması). Uygulamadan ve oyun içi servis menüsünden (`Alt+F8`) aynı
  ücretle onarılır. Olay kaydında **elle** etiketiyle görünür.
- Yeniden tetiklenen arıza da hemen öter (60 sn yeniden kurulma beklenmez). Sarı (dikkat) arızalar (ABS, marş,
  şanzıman) her uyarı gibi yalnızca uyarı düzeyi *Hepsi* iken öter.
- Lastik patlamasında, oyun içi katman kuruluysa ve *Lastik patlaması* ayarı açıksa araç patlayan tarafa çeker, jant
  sürterek yavaşlar (otomobilde ön lastik de direksiyonu çeker).
- Yağ pompası arızasında basınç her devirde uyarı eşiğinin altında kalır (kırmızı YAĞ ve DURUN lambası); bu halde
  sürmek motor sağlığını düşürür.
- Çok Oyunculu modda ve TruckersMP / Konvoy oturumu algılanınca çekim modu kapalıdır.

### Uyarı sesleri (markaya göre, her uyarıda bir kez)

Yeni bir uyarı çıkınca tırın markasına göre kısa bir ikaz sesi çalar:
- **Sesler:** Scania sıcak "bong", Volvo iki notalı zil, Mercedes-Benz tiz "pling", MAN kısa elektronik bip, DAF iki
  tonlu ses, Renault üç notalı zil, Iveco tek bip; Škoda/Scout otomobilde gong, otobüste "ding-dong". Her markanın
  *dikkat* ve *kritik* sesi ayrıdır.
- **Neden benzetme:** Üreticilerin özgün ikaz kayıtları yayımlanmaz (telif hakkı üreticidedir), oyunun kendi sesleri de
  paketli ses bankalarındadır. Bu yüzden sesler her markanın tanınan ikaz karakterine benzetilerek üretilir.
- **Her uyarı yalnızca bir kez öter.** Uyarının içindeki değer değişse de (ör. "akü 25,1 V" → "24,9 V") yeniden ötmez.
  Kaybolup 60 saniye içinde geri gelen uyarı da ötmez. Farklı arızalar ve farklı dingillerin lastik uyarıları ayrı
  uyarıdır; her biri kendi çıktığında bir kez öter.
- **Ses kesilmez:** sesler sırayla ve sonuna kadar çalar. Bir ses çalarken çıkan aynı ya da daha düşük seviyeli uyarı
  o sese katılır, kritik uyarı dikkat sesinin bitmesini bekler (eski sürümde arka arkaya çıkan uyarılar sesi baştan
  başlatıp kesik kesik öttürüyordu). Ses dosyalarının başında kısa bir sessizlik vardır: bazı dizüstü ses kartları
  boştayken sesin ilk ~100 ms'sini yutar. Sesler 44,1 kHz üretilir (`sesler\v2`).
- **Marka seçimi:** Ayarlar → *İkaz sesi*: *Otomatik* tırın markasına göre çalar; isterseniz başka bir markanın sesini
  seçebilirsiniz. Oyun kapalıyken *dinle* düğmeleri son kullanılan aracın sesini çalar.
- **Hangi uyarılar öter:** Kritik uyarılar her zaman. Dikkat (sarı) uyarıları yalnızca uyarı düzeyi *Hepsi* iken.
- **Tek kaynak:** Ses yalnızca uygulamadan çalar; oyun içi katman ve uygulama penceresi ayrıca bip yapmaz.
- **Deneme:** Ayarlar → *İkaz sesi* → **Kritik sesi dinle / Dikkat sesi dinle**. *Sesli uyarı* kutusu kapalıyken
  oyunda hiç ötmez (dinle düğmesi yine çalar ve bunu hatırlatır).
- **Kendi sesleriniz:** `sesler\ozel` klasörüne `<marka>_<seviye>.wav` koyun; varsa o çalar.
  - Marka adları: scania, volvo, mercedes, man, daf, renault, iveco, skoda, otobus, genel.
  - Seviye adları: dikkat, kritik. Örnek: `scania_kritik.wav`.

## Gerçekçi müdahale (motoru durdurma)

Motorun gerçekte çalışmaması gereken durumlarda program motoru durdurur:

- marş başarısız olduğunda (akü yetersiz, yağ çok koyu, motor kilitli, blok çatlak, ön ısıtma beklenmedi ya da arızalı,
  marş motoru arızalı),
- çalışırken akü voltajı ECU sınırının altına düşerse (ör. alternatör arızası),
- yağsız kalma veya aşırı ısı yüzünden motor kilitlenirse.

Yalnızca motor durdurulur; kontak, gösterge ekranları ve ışıklar açık kalır. Oyun içi eklenti kuruluysa oyunun resmi
giriş SDK'sıyla motor durdurma komutu gönderilir; eklenti yoksa ya da komut etkisiz kalırsa yedek olarak **motor
çalıştır/durdur tuşu** (varsayılan `E`) gönderilir. Tuş yalnızca oyun penceresi öndeyken gönderilir. Tek oyunculuda
bu her zaman açıktır; Çok Oyunculu modda Ayarlar → *İzleme modu* ile seçilir (yukarıya bakın).

## Bilmeniz gerekenler

- Süreçler **oyun zamanına** göre ilerler (ETS2'de 1 gerçek saniye ≈ 19 oyun saniyesi). Kilometre ve yakıt
  ekonomisi de böyle ölçeklendiği için bakım aralıkları gerçek dünyadaki km'lerle aynıdır.
  Örneğin hararet, gerçek zamanda çok hızlı gelişebilir; sarı uyarıyı (103 °C) görünce hemen önlem alın.
- **Zaman atlamaları** (uyku, feribot, tren) motor kapalı geçen süre sayılır: motor ve şanzıman soğur, akü park
  yükleriyle boşalır, lastikler hava kaybeder, yağ / antifriz kaçakları sürer. Feribot ve tren yolculuğu yükleme
  ekranında (oyun duraklatılmışken) geçtiği için duraklatmadan dönüşte de aranır; o sırada başka bir kayıt
  yüklendiyse (kilometre değiştiyse) sayılmaz.
- Bakım masrafları programın kendi hesabında tutulur, oyundaki paranızdan **düşülmez** (SCS SDK oyunun parasını değiştiremez).
  Fiyatlar 2026 Batı Avrupa bağımsız ağır vasıta servisi seviyesindedir (parça + işçilik, saat ücreti ~110 €, KDV hariç)
  ve tek bir tablodan ayarlanır: `ets2bakim\prices.py`. Örnekler: yağ + filtre (10W-40, 42 L) ~520 €, alternatör 880 €,
  su pompası 950 €, silindir kapak contası 5.200 €, motor revizyonu 19.500 €, aküler (2 x 225 Ah) 720 €, ön lastik 600 €
  (takma dahil), DPF kül temizliği 950 €.
- **Para birimi oyunla eşleşir:** oyunda seçtiğiniz para birimi (ör. ₺) oyunun kaydından (`game.log.txt`:
  `uset g_currency`) okunur, oyun ETS2 mi ATS mi telemetriden anlaşılır. Avro tabanlı fiyatlar oyunun kendi kurlarıyla
  çevrilir (ETS2 1.57: 1 € = 48,73 ₺, 0,87 £, 4,24 zł…; ATS tabanı dolar), yani yalnız simge değil tutar da değişir:
  ör. silindir kapak contası ₺253.391. Oyunda para birimini değiştirirseniz en geç bir sonraki oyun açılışında güncellenir.
  Ayarlar → *Para birimi* → *Elle* ile kendi simgenizi ve kurunuzu (1 € = ?) girebilirsiniz.
- Servis işlemleri için kamyon durmuş ve motor kapalı olmalı. Sıcak motorda radyatör kapağı açılamaz.
- **Oyundaki servis noktasında parça tamiri:** oyunda servise girip tamir yaptırdığınızda (oyunun motor, şanzıman,
  kabin, şasi ya da tekerlek hasarı düşünce) simülasyondaki **arızalı parçalar da onarılır** — alternatör, termostat,
  fan kavraması, su pompası, contalar, çatlaklar; donmuş aküler yenilenir. Her onarımın gideri kayda yazılır.
  Ayarlar → *Oyundaki serviste parça tamiri* ile kapatılabilir. Oyun yalnızca hasar varken tamire izin verdiği için
  oyun hasarı %0 ise parçaları `Alt+F8` servis menüsünden onarın.
- Oyunda tamir yaptırmak yağ/antifriz **bakımı** yerine geçmez; isterseniz Ayarlar → *Oyunda tamirde otomatik bakım*
  ile yağ + filtre + antifriz tamamlama da eklenir.
- Kamyon ilk kez görüldüğünde kilometresine göre "kullanılmış araç" durumu varsayılır. Bir yağ analizi
  yaptırıp gerekirse yağ değiştirin.

## Grafik ön ayarları (`GRAFIK_YOUTUBE.bat` / `GRAFIK_DENGELI.bat` / `GRAFIK_NORMAL.bat`)

TruckersMP'nin ayrı bir grafik ayarı yoktur; oyunun `Belgeler\Euro Truck Simulator 2\config.cfg` dosyasını kullanır
(tek oyunculuyu da etkiler). `GRAFIK_YOUTUBE.bat` (oyun kapalıyken) önce mevcut değerleri `config.cfg.grafik-normal`
olarak yedekler, sonra yalnızca anlamı belgelenmiş ayarları yükseltir: ölçekleme %125, gölge kalitesi en yüksek ve
4096 doku, uzak gölgeler, SSAO orta, bitki örtüsü ve çim yüksek, yansıma ve ıslak yol yansımaları yüksek, camda yağmur
damlaları, renk düzeltme, yayalar. `GRAFIK_NORMAL.bat` bu ayarları yedekteki değerlere döndürür (diğer ayarlarınıza
dokunmaz).

`GRAFIK_DENGELI.bat` bir kademe düşük ayar verir; kalabalık TruckersMP sunucularında FPS düşüyorsa kullanın.
Hiçbir özellik kapanmaz, yalnızca kalitesi bir kademe iner:
- ölçekleme %100,
- gölge yüksek ve 2048 doku (uzak gölgeler açık),
- SSAO düşük,
- bitki örtüsü orta, çim düşük,
- yansımalar bir kademe düşük;
- yağmur yansımaları, cam damlaları, renk düzeltme ve yayalar açık kalır.

Hazır düzeyler arasında geçerken kendi ayarlarınızın yedeği korunur; `GRAFIK_NORMAL.bat` her zaman sizin
ayarlarınıza döner.

Kayıt FPS'i yine düşerse oyunda *Ayarlar → Grafik → Ölçekleme*'yi %100'e indirmek en çok kazandıran ayardır;
anizotropik filtreyi oyunda 16x yapmak yol dokularını belirgin keskinleştirir ve neredeyse hiç FPS yemez.

## Dağıtım paketi (indirilebilir zip), kurulum ve kaldırma

`.venv\Scripts\python.exe paketle.py` indirilebilir paketi oluşturur: `dagitim\ETS2-Maintenance-Simulator-<sürüm>.zip` (Tek / Çok
Oyunculu mod aynı uygulamada seçildiği için tek paket; 1.1'de iki paket vardı).

Zip kendi başına çalışır, kullanıcının Python kurmasına gerek yoktur: içinde bu bilgisayardaki Python 3.13'ün
imzalı çalışma dosyaları, derlenmiş standart kütüphane (`python313.zip`), uygulamanın paketleri (pywebview, pythonnet,
truck-telemetry…), uygulama, web arayüzü, önceden üretilmiş ikaz sesleri, oyun eklentileri (RenCloud telemetri eklentisi
V.1.12.1 ve oyun içi katman) ve `LISANSLAR` klasörü vardır. Telemetri eklentisi kurulu oyundaki kopyadan alınır
(`--telemetri <yol>` ile değiştirilebilir); oyun içi katman `overlay\build`'dendir. Betik, paketin kendi Python'uyla
bütün modüllerin yüklendiğini dener ve zip'in SHA-256 özetini yazar (indirme sayfasına koymak için). README.txt'de
TR / EN / DE kısa bir sorumluluk notu vardır (SCS Software ve TruckersMP ile bağlantı yok, marka adları yalnızca
tanımlayıcı, TruckersMP'de kullanım kendi sorumluluğunda).

**Kullanıcı için:** zip'i ayıklayıp `INSTALL.bat`'a çift tıklar (yönetici izni gerekmez). Kurulum (`ets2bakim/kurulum.py`):
- programı `%LOCALAPPDATA%\Programs\ETS2-Bakim` klasörüne kopyalar (içerik olarak: zip'ten gelen "internetten
  indirildi" işareti kurulan dosyalara geçmez); güncellemede `data*` ve `sesler\ozel` korunur,
- Steam kütüphanelerindeki ETS2 / ATS'ye telemetri eklentisini ve katmanı kurar: önceden **aynı** telemetri eklentisi
  varsa (başka bir araç da kullanıyor olabilir) ona dokunmaz, **farklı** bir sürüm varsa yedekler
  (`scs-telemetry.dll.ets2bakim-yedek`); Akıllı Uygulama Denetimi açıksa imzasız katmanı kurmaz,
- masaüstüne ve Başlat menüsüne (Windows dilinde: *ETS2 Bakım / ETS2 Maintenance / ETS2 Wartung*) uygulama,
  *Eklentileri kur*, *Demo* ve *Kaldır* kısayollarını koyar (görev çubuğu kimliğiyle); aynı adlı ama başka bir kopyayı
  açan kısayola dokunmaz,
- Windows Ayarlar → Uygulamalar listesine kaydeder (HKCU), uygulamanın ilk dilini Windows'un dili yapar, uygulamayı açar.

1.1'in üzerine kurulunca iki eski kısayol (Tek / Çok Oyunculu) kaldırılır, `data\` ve `data_mp\` korunur. Yapılan her
şey `kurulum.json`'a yazılır.
**Kaldırma** (Ayarlar → Uygulamalar → Kaldır, Başlat menüsü ya da `KALDIR.bat`) onay ister, açık uygulamayı kaydedip
kapatır, oyun açıksa kapatılmasını bekler; eklentileri siler ve yedeklenen telemetri eklentisini geri koyar,
kısayolları, kaydı, katman ayarlarını (`%LOCALAPPDATA%\ETS2Bakim`) ve program klasörünü (bakım kayıtları dahil) siler.
`kurulum kaldir --sessiz` soru sormaz. Kurulu programda bekleme ekranı ve Ayarlar, `EKLENTI_KUR.bat` / `DEMO.bat`
yerine Başlat menüsündeki kısayolları gösterir.

Bilinmesi gerekenler: zip'teki `INSTALL.bat`, Akıllı Uygulama Denetimi açık bilgisayarlarda "internetten indirildi"
işareti yüzünden engellenebilir (Microsoft'un listesindeki `.bat`); kullanıcı zip'e sağ tık → Özellikler →
*Engellemeyi kaldır* yapıp yeniden ayıklar (README.txt'de yazıyor). Kurulan program bu işareti taşımaz. Paketi
yayımlamadan önce VirusTotal'da taratmak iyi olur: DirectX'e kanca atan imzasız katman DLL'i bazı antivirüslerde
yanlış alarm verebilir.

### Uygulama içi güncelleme (1.3.0 ve sonrası)

Kurulu uygulama açılışta (Ayarlar → Genel → *Açılışta yeni sürümü denetle*, varsayılan açık) ya da *Şimdi denetle* ile
Drive'daki `surum.json`'a bakar. Yeni sürüm varsa bildirim çıkar; *İndir ve kur* zip'i `%TEMP%\ETS2Bakim-guncelleme`
klasörüne indirir, SHA-256 özetini `surum.json`'dakiyle karşılaştırır, açar ve içindeki kurulumu sessiz çalıştırır
(`kur --sessiz --hedef <kurulu klasör>`; çıktı aynı klasörde `kurulum.log`). Kurulum uygulamayı kaydedip kapatır,
programı günceller (`data*` korunur) ve uygulamayı yeniden açar. İndirilen zip ve açılmış paket, yeni sürümün
açılışından 2 dakika sonra silinir (`kurulum.log` kalır). Oyun açıkken güncelleme başlamaz; geliştirme
kopyasında (`paket.json` yok) kapalıdır. 1.2.1 ve öncesinde bu özellik yoktur: 1.3.0'a geçiş zip'ten yapılır.

**Yayımlama:** `paketle.py` zip'in yanına `dagitim\surum.json`'u da yazar (sürüm, zip'in Drive indirme adresi, SHA-256,
boyut, `RELEASE_NOTES`). Drive'da önce zip'i, sonra `surum.json`'u *Sürümleri yönet → Yeni sürüm yükle* ile değiştirin;
iki bağlantı da aynı kalır (dosya kimlikleri `ets2bakim/guncelleme.py`'de: `ZIP_ID`, `INFO_ID`). `surum.json`
"Bağlantıya sahip olan herkes: Görüntüleyen" olarak paylaşılmalıdır; kapalıysa uygulama "Sürüm bilgisi okunamadı" yazar.

## Sorun giderme

| Durum | Çözüm |
|---|---|
| "Oyun çalışmıyor ya da telemetri eklentisi kurulu değil" | `EKLENTI_KUR.bat` çalıştırın, oyunu yeniden başlatın. |
| "Telemetri eklentisi uyumsuz" | Eklentinin V.1.12.x olması gerekir. Eski bir `scs-telemetry.dll` varsa silip yeniden kurun. |
| Motor durdurma çalışmıyor | Ayarlar sekmesindeki "Oyun içi katman" kartına bakın. Eklenti yoksa: oyun penceresi önde mi, yedek motor tuşu oyundaki atamayla aynı mı? |
| Oyunda katman görünmüyor | Eklenti kurulu mu (`plugins\ets2bakim_overlay.dll`)? Oyun DirectX 11 ile mi çalışıyor? `F8` ile mod değiştirin. Oyun günlüğünde (`Belgeler\Euro Truck Simulator 2\game.log.txt`) `[ets2bakim]` satırlarına bakın; “oyun ici panel kurulmadi” satırının nedeni Ayarlar → Oyun içi katman → Durum'da da yazar. |
| Oyun açılışta donuyor (DLSS 5, OptiScaler gibi görüntü eklentileriyle) | Ayarlar → Oyun içi katman → *Oyun içi panel*: *Otomatik* bu eklentileri ve bir önceki donmayı tanır; yine donuyorsa *Kapalı* seçin. Sürüş modları, motor durdurma ve lastik patlaması panelsiz de çalışır. |
| Ses gelmiyor | Pencereye bir kez tıklayın (tarayıcılar otomatik sesi engeller). |

Testler: `.venv\Scripts\python.exe -m unittest tests.test_models`
