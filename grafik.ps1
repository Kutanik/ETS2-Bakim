# ETS2 grafik ayarlarını hazır düzeylere getirir ya da önceki hâline döndürür.
# TruckersMP ayrı grafik ayarı tutmaz, oyunun config.cfg dosyasını kullanır; bu yüzden tek oyunculuyu da etkiler.
#   grafik.ps1 -Mod youtube   en yüksek kalite (YouTube kaydı): ölçekleme %125, en iyi gölge, yüksek bitki/yansıma
#   grafik.ps1 -Mod dengeli   bir kademe düşük (kalabalık TruckersMP sunucularında akıcı FPS); hiçbir özellik kapanmaz
#   grafik.ps1 -Mod normal    yedekteki (sizin) değerleri geri yükler (yalnızca aşağıdaki ayarlar; diğerlerine dokunulmaz)
# Kendi ayarlarınız ilk hazır düzey uygulanırken config.cfg.grafik-normal olarak yedeklenir; düzeyler arasında geçişte
# bu yedek korunur. Oyun kapanırken ayarlarını config.cfg'ye yazdığı için oyun kapalıyken çalıştırılmalıdır.
param([ValidateSet("youtube", "dengeli", "normal")][string]$Mod = "youtube",
      [string]$Config = "")   # -Config: başka bir dosya (deneme)
$ErrorActionPreference = "Stop"

# Yalnızca anlamı belgelenmiş ayarlar (SCS modding wiki, oyunun ön ayarları). Tutarsız değerleri oyun
# varsayılana döndürür; yine de yedek alınır. Sütunlar: youtube, dengeli, açıklama.
$Table = [ordered]@{
    "r_scale_x"                 = @("1.25", "1",    "Olcekleme (%125 -> %100: en cok FPS kazandiran ayar)")
    "r_scale_y"                 = @("1.25", "1",    "")
    "r_sun_shadow_quality"      = @("4",    "3",    "Golge kalitesi (en yuksek -> yuksek)")
    "r_sun_shadow_texture_size" = @("4096", "2048", "Golge dokusu")
    "r_far_shadow_disable"      = @("0",    "0",    "Uzak golgeler acik")
    "r_ssao"                    = @("2",    "1",    "Ortam golgelemesi (SSAO) orta -> dusuk, acik kalir")
    "g_veg_detail"              = @("2",    "1",    "Bitki ortusu ayrintisi (yuksek -> orta)")
    "g_grass_density"           = @("2",    "1",    "Cim yogunlugu (yuksek -> dusuk, acik kalir)")
    "g_reflection"              = @("3",    "2",    "Yansima ayrintisi")
    "g_rain_reflection"         = @("3",    "2",    "Yagmurda yol yansimasi")
    "g_rain_reflect_traffic"    = @("1",    "1",    "Islak yolda arac yansimalari acik")
    "g_rain_reflect_actor"      = @("1",    "1",    "Islak yolda kendi aracinizin yansimasi acik")
    "r_interior_raindrops"      = @("1",    "1",    "Kabinden camda yagmur damlalari acik")
    "r_color_correction"        = @("1",    "1",    "Renk duzeltme acik")
    "g_pedestrian"              = @("1",    "1",    "Yayalar acik (tek oyunculu)")
}
$Col = @{ youtube = 0; dengeli = 1 }
$Names = @{ youtube = "YouTube (en yuksek)"; dengeli = "Dengeli (bir kademe dusuk)" }

$docs = [Environment]::GetFolderPath("MyDocuments")
$cfg = if ($Config) { $Config } else { Join-Path $docs "Euro Truck Simulator 2\config.cfg" }
$bak = "$cfg.grafik-normal"
if (-not (Test-Path $cfg)) { Write-Host "Bulunamadi: $cfg"; exit 1 }
if (-not $Config -and (Get-Process eurotrucks2 -ErrorAction SilentlyContinue)) {
    Write-Host "Oyun acik. Once ETS2'yi (TruckersMP dahil) kapatin: oyun kapanirken ayarlarini bu dosyanin uzerine yazar."
    exit 1
}

$enc = New-Object System.Text.UTF8Encoding($false)
$text = [IO.File]::ReadAllText($cfg, $enc)

function Get-Val([string]$t, [string]$key) {
    $m = [regex]::Match($t, "(?m)^uset $([regex]::Escape($key)) `"([^`"]*)`"")
    if ($m.Success) { return $m.Groups[1].Value } else { return $null }
}
function Set-Val([string]$t, [string]$key, [string]$val) {
    $pat = "(?m)^uset $([regex]::Escape($key)) `"[^`"]*`""
    if ([regex]::IsMatch($t, $pat)) { return [regex]::Replace($t, $pat, "uset $key `"$val`"") }
    return $t.TrimEnd() + "`r`nuset $key `"$val`"`r`n"
}
function Is-Preset([string]$t, [string]$mode) {
    foreach ($k in $Table.Keys) { if ((Get-Val $t $k) -ne $Table[$k][$Col[$mode]]) { return $false } }
    return $true
}

if ($Mod -ne "normal") {
    if (Is-Preset $text $Mod) { Write-Host "Ayarlar zaten $($Names[$Mod]) duzeyinde."; exit 0 }
    $preset = (Is-Preset $text "youtube") -or (Is-Preset $text "dengeli")
    if (-not $preset) {          # yalnızca sizin kendi ayarlarınız yedeklenir (hazır düzeyler arası geçişte yedek korunur)
        Copy-Item $cfg $bak -Force
        Write-Host "Yedek: $bak"
    }
    Write-Host ""
    Write-Host ("{0,-27} {1,-8} {2,-8} {3}" -f "Ayar", "Once", "Simdi", "")
    foreach ($k in $Table.Keys) {
        $old = Get-Val $text $k
        $new = $Table[$k][$Col[$Mod]]
        $text = Set-Val $text $k $new
        $mark = if ($old -ne $new) { "*" } else { " " }
        Write-Host ("{0,-27} {1,-8} {2,-8} {3} {4}" -f $k, $old, $new, $mark, $Table[$k][2])
    }
    [IO.File]::WriteAllText($cfg, $text, $enc)
    Write-Host ""
    Write-Host "Tamam: $($Names[$Mod]) grafik ayarlari uygulandi. Kendi ayarlariniza donmek icin GRAFIK_NORMAL.bat."
} else {
    if (-not (Test-Path $bak)) { Write-Host "Yedek yok ($bak): once GRAFIK_YOUTUBE.bat ya da GRAFIK_DENGELI.bat calistirilmamis."; exit 1 }
    $old = [IO.File]::ReadAllText($bak, $enc)
    foreach ($k in $Table.Keys) {
        $v = Get-Val $old $k
        if ($null -ne $v) {
            Write-Host ("{0,-27} {1,-8} -> {2}" -f $k, (Get-Val $text $k), $v)
            $text = Set-Val $text $k $v
        }
    }
    [IO.File]::WriteAllText($cfg, $text, $enc)
    Write-Host ""
    Write-Host "Tamam: onceki grafik ayarlari geri yuklendi."
}
