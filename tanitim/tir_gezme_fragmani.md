# ETS2 Tır Gezme Fragmanı – Çekim Listesi (~60 sn)

## Hazırlık
- Tek oyunculu oyna (TruckersMP'de serbest kamera ve konsol çalışmaz).
- Konsol: Esc'nin altındaki tuş (Türkçe Q klavyede `"` tuşu). Serbest kamera: **0** tuşu (W A S D / ok tuşları + fare).
- Kabin içi kamera **1**, takip kamerası **2**.
- Hareketli çekimde: hız sabitleyiciyi aç (60–70 km/s), düz yolda 0'a geç, kamerayı yol kenarına koy.
- ETS2 Bakım katmanı görüntüye girmesin: kayıttan önce gizle ya da uygulamayı kapat; ilk denemede kontrol et.
- OBS: 1080p60, NVENC, MKV kaydet → sonra Dosya › Remux Recordings ile MP4.
- Her sahneyi 2–3 kez çek; başta ve sonda 2–3 sn fazladan kayıt bırak (kesim payı).

## Konsol komutları (sürüme göre farklı olabilir)
| Komut | Ne yapar |
|---|---|
| `g_set_time 6` / `g_set_time 19` | Gün doğumu / gün batımı |
| `g_set_weather 0` / `g_set_weather 1` | Açık hava / yağmur |
| `g_traffic 0` / `g_traffic 1` | Trafiği kapat / aç (temiz kadraj) |
| `warp 0.5` / `warp 1` | Ağır çekim / normal hız |

## Sahneler
| # | Sahne | Kamera | Süre | Not |
|---|---|---|---|---|
| 1 | Gün doğumu, boş yol; tır uzaktan gelip geçer | 0, yol kenarı, alçak | 5 sn | `g_set_time 6`, `g_traffic 0` |
| 2 | Far ve ızgara yakın plan | 0 | 3 sn | Tır yavaş geçerken |
| 3 | Dönen jant | 0, tekerlek hizası | 3 sn | |
| 4 | Kabin içi: direksiyon, gösterge, camda manzara | 1 | 5 sn | |
| 5 | Arkadan takip, virajlı yol | 2 | 10 sn | Sabit hız |
| 6 | Yüksekten vadi / deniz, tır küçük görünür | 0, yukarıda | 10 sn | İstersen `warp 0.5` |
| 7 | Tünel çıkışı: karanlıktan ışığa | 1 veya 2 | 4 sn | Müzikteki vuruşa denk getir |
| 8 | Gün batımı, güneş karşıdan | 0 veya 2 | 10 sn | `g_set_time 19` |
| 9 | Yağmur / gece, ıslak asfalt, şehir ışıkları | 2 | 6 sn | `g_set_weather 1` |
| 10 | Tır uzaklaşır, siyaha geçiş, logo | 0, sabit | 5 sn | |

## Rota (DLC'ye göre)
- Road to the Black Sea: Transfăgărășan (Romanya) — en iyisi
- Scandinavia: Norveç fjordları (Bergen–Stavanger)
- Vive la France / Italia: Alpler (Lyon–Cenevre, Innsbruck–Brenner)
- Iberia / Greece: sahil yolları
- DLC yoksa: Salzburg–Innsbruck (Avusturya Alpleri)

## Kurgu (DaVinci Resolve)
- Müzik: YouTube Ses Kitaplığı → "Cinematic"; kesimleri vuruşlara denk getir.
- Renk: hafif kontrast + sıcak ton. Geçiş: düz kesim, sonda siyaha geçiş.
- Dışa aktar: 1080p60, H.264.

## Geliştirici modunu açma (bir kez, oyun kapalıyken)
1. `Belgeler\Euro Truck Simulator 2\config.cfg` dosyasını kopyalayıp yedekle (ör. `config_yedek.cfg`).
2. `config.cfg`'yi Not Defteri ile aç, şu iki satırı bul ve "0"ı "1" yap:
   `uset g_developer "1"` ve `uset g_console "1"`
3. Kaydet, oyunu aç. Kapatmak için aynı değerleri "0" yap.
