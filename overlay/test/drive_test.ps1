# Sürüş modları (ECO / COMFORT / SPORT) testi: test_host oyunun gaz zincirini taklit eder (pedal + eklentinin katkısı =
# oyunun gazı), eklenti EBK_TEST_DRIVE ile verilen mod parametreleriyle gazı düzeltir. Her senaryoda son karelerdeki
# etkin gaz beklenen değerle karşılaştırılır. Simülatör ya da oyun gerekmez; gerçek ayarlara dokunulmaz.
$ErrorActionPreference = "Stop"
$ovl = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$host_exe = Join-Path $ovl "build\test_host.exe"
$dll = Join-Path $ovl "build\ets2bakim_overlay.dll"
$out = Join-Path $ovl "build\captures\surus_modu"
New-Item -ItemType Directory -Force $out | Out-Null
$env:EBK_PREFS_PATH = Join-Path $out "test_overlay.ini"
$inv = [Globalization.CultureInfo]::InvariantCulture

# pedalı <len> kareye yayarak bırakma çizelgesi ("kare:değer,..."; ondalık ayırıcı her dilde nokta)
function Release($from, $start, $len) {
    ((0..$len) | ForEach-Object { "{0}:{1}" -f ($start + $_), ($from * (1 - $_ / $len)).ToString("0.####", $inv) }) -join ","
}
# üstel bırakma (oyunun klavye gazı gibi): her karede <k> katına iner, <len> kare sonra sıfır; çok küçük değerlerden geçer
function Decay($from, $start, $len, $k) {
    $s = (0..($len - 1)) | ForEach-Object { "{0}:{1}" -f ($start + $_), ($from * [math]::Pow($k, $_)).ToString("0.########", $inv) }
    ($s + ("{0}:0" -f ($start + $len))) -join ","
}

# ad, mod parametreleri (mod,üst,artış/sn,hız sınırı,eğri), pedal çizelgesi, hız, hız sabitleyici, telemetri modeli, beklenen
$cases = @(
    @{ n = "eco_sinir";      d = "1,0.75,0.6,85,1"; t = "0:0,20:1"; v = "0:60"; want = 0.75 },
    @{ n = "eco_hiz";        d = "1,0.75,0.6,85,1"; t = "0:0,20:1"; v = "0:87"; want = 0.0 },
    @{ n = "comfort";        d = "2,1,1.5,0,1";     t = "0:0,20:1"; v = "0:60"; want = 1.0 },
    @{ n = "sport_yarim";    d = "3,1,0,0,1.8";     t = "0:0,20:0.5"; v = "0:60"; want = 0.713 },
    @{ n = "kapali";         d = "0,1,0,0,1";       t = "0:0,20:0.6"; v = "0:60"; want = 0.6 },
    @{ n = "hiz_sabitleyici"; d = "1,0.75,0.6,85,1"; t = "0:0"; v = "0:80"; c = "0:80"; want = 0.6 },
    @{ n = "eco_model2";     d = "1,0.75,0.6,85,1"; t = "0:0,20:0.8"; v = "0:60"; m = 2; want = 0.75; frames = 420 },
    @{ n = "eco_birakma";    d = "1,0.75,0.6,85,1"; t = "0:0,20:1,200:0.3"; v = "0:60"; want = 0.3; frames = 300 },
    # pedal bırakılınca eklentinin katkısı tam sıfıra inmeli: oyunda kalan küçük gaz (ör. 0,0004) retarderi ve motor
    # frenini devreden çıkarır (zero = son karelerde katkı ve etkin gaz sıfır)
    @{ n = "sport_birakma";  d = "3,1,0,0,1.8";     t = "0:0,20:0.5," + (Release 0.5 150 30); v = "0:60"; want = 0.0; zero = $true },
    @{ n = "sport_yavas";    d = "3,1,0,0,1.8";     t = "0:0,20:0.7," + (Release 0.7 120 90); v = "0:60"; want = 0.0; zero = $true; frames = 300 },
    @{ n = "sport_ustel";    d = "3,1,0,0,1.8";     t = "0:0,20:0.5," + (Decay 0.5 150 90 0.85); v = "0:60"; want = 0.0; zero = $true; frames = 300 },
    @{ n = "sport_model2";   d = "3,1,0,0,1.8";     t = "0:0,20:0.5," + (Release 0.5 300 30); v = "0:60"; m = 2; want = 0.0; zero = $true; frames = 420 },
    @{ n = "comfort_birakma"; d = "2,1,1.5,0,1";    t = "0:0,20:0.6," + (Release 0.6 150 30); v = "0:60"; want = 0.0; zero = $true },
    # 1.15: oyun katkıyı geç uygularsa (lag kare) ve pedal gürültülüyse (noise: ±n/10000) gaz kare kare salınmamalı ve
    # eklenti her karede olay göndermemeli (1.14'te SPORT'ta neredeyse her karede olay ve 0,1-0,26 arası salınım vardı:
    # gaz verip bırakırken oyun takılıyordu). maxev: en çok gaz olayı, maxflip: katkının en çok yön değiştirme sayısı
    @{ n = "sport_gecikme1"; d = "3,1,0,0,1.8";     t = "0:0,20:0.5," + (Release 0.5 200 30); v = "0:60"; lag = 1; noise = 40; want = 0.0; zero = $true; frames = 320; maxev = 40; maxflip = 4 },
    @{ n = "sport_gecikme2"; d = "3,1,0,0,1.8";     t = "0:0,20:0.2"; v = "0:60"; lag = 2; noise = 40; want = 0.331; frames = 300; maxev = 30; maxflip = 4 },
    @{ n = "sport_gurultu";  d = "3,1,0,0,1.8";     t = "0:0,20:0.1"; v = "0:60"; noise = 40; want = 0.173; frames = 300; maxev = 30; maxflip = 4 },
    @{ n = "sport_model2_az"; d = "3,1,0,0,1.8";    t = "0:0,20:0.05"; v = "0:60"; m = 2; lag = 1; noise = 40; want = 0.088; frames = 400; maxev = 60; maxflip = 12 },
    @{ n = "sport_tekrar_etkin"; d = "3,1,0,0,1.8"; t = "0:0,20:0.5"; v = "0:60"; react = 140; want = 0.713; frames = 300; maxev = 20; maxflip = 2 },
    @{ n = "comfort_gecikme"; d = "2,1,1.5,0,1";    t = "0:0,20:0.6," + (Release 0.6 150 30); v = "0:60"; lag = 1; noise = 40; want = 0.0; zero = $true; maxev = 40; maxflip = 4 },
    @{ n = "eco_gecikme";    d = "1,0.75,0.6,85,1"; t = "0:0,20:1"; v = "0:60"; lag = 1; noise = 40; want = 0.75; frames = 300; maxev = 60; maxflip = 4 }
)
$envs = "EBK_TEST_DRIVE", "EBK_TEST_THROTTLE", "EBK_TEST_SPEED", "EBK_TEST_CRUISE", "EBK_TEST_THR_MODEL", "EBK_TEST_THR_LAG",
         "EBK_TEST_THR_NOISE", "EBK_TEST_REACTIVATE_AT"
$fail = 0
try {
    foreach ($c in $cases) {
        foreach ($e in $envs) { Remove-Item "Env:$e" -ErrorAction SilentlyContinue }
        $env:EBK_TEST_DRIVE = $c.d; $env:EBK_TEST_THROTTLE = $c.t; $env:EBK_TEST_SPEED = $c.v
        if ($c.c) { $env:EBK_TEST_CRUISE = $c.c }
        if ($c.m) { $env:EBK_TEST_THR_MODEL = "$($c.m)" }
        if ($c.lag) { $env:EBK_TEST_THR_LAG = "$($c.lag)" }
        if ($c.noise) { $env:EBK_TEST_THR_NOISE = "$($c.noise)" }
        if ($c.react) { $env:EBK_TEST_REACTIVATE_AT = "$($c.react)" }
        $frames = if ($c.frames) { $c.frames } else { 260 }
        $log = Join-Path $out "$($c.n).txt"
        & $host_exe $dll $frames | Out-File -Encoding utf8 $log
        $rows = Select-String -Path $log -Pattern "^\[thr\] (\d+) ham=([\d.]+) girdi=([\d.]+) etkin=([\d.]+) katki=(-?[\d.]+) olay=(\d+) toplam=(\d+)" |
            ForEach-Object { $g = $_.Matches[0].Groups; [pscustomobject]@{ f = [int]$g[1].Value; ham = [double]$g[2].Value;
                etkin = [double]$g[4].Value; katki = [double]$g[5].Value; olay = [int]$g[6].Value; toplam = [int]$g[7].Value } }
        if (-not $rows) { Write-Host "HATA $($c.n): test_host cikti vermedi ($log)"; $fail++; continue }
        $last = $rows | Select-Object -Last 10
        $avg = ($last | Measure-Object etkin -Average).Average
        $ok = [math]::Abs($avg - $c.want) -lt 0.03
        # ECO ve COMFORT gazı yavaş artırır: pedala basıştan kısa süre sonra gaz hâlâ hedefin altında olmalı
        $ramp = ""
        if ($c.n -in "eco_sinir", "comfort") {
            $early = ($rows | Where-Object { $_.f -eq 30 }).etkin
            $rampOk = $early -lt 0.5
            $ramp = " | 10 kare sonra etkin=$early (yumusak: $rampOk)"
            $ok = $ok -and $rampOk
        }
        if ($c.zero) {
            # eklentinin katkısı tam sıfır olmalı; etkin gazda yalnızca bırakılmış pedalın gürültüsü kalabilir
            $restK = ($last | ForEach-Object { [math]::Abs($_.katki) } | Measure-Object -Maximum).Maximum
            $restE = ($last | Measure-Object etkin -Maximum).Maximum
            $noiseMax = if ($c.noise) { $c.noise / 20000.0 } else { 0.0 }
            $zeroOk = ($restK -le 0.000001) -and ($restE -le $noiseMax + 0.000001)
            $ramp = " | birakinca kalan katki=" + $restK.ToString("0.######", $inv) + " gaz=" + $restE.ToString("0.######", $inv) + " (sifir: $zeroOk)"
            $ok = $ok -and $zeroOk
        }
        # gaz olayı sayısı ve katkının yön değiştirmesi (salınım): katkı her karede gönderilmemeli, ileri geri gitmemeli
        $total = ($rows | Select-Object -Last 1).toplam
        $flips = 0; $prevD = 0.0
        for ($k = 1; $k -lt $rows.Count; $k++) {
            $dv = $rows[$k].katki - $rows[$k - 1].katki
            if ([math]::Abs($dv) -lt 0.015) { continue }
            if ($prevD -ne 0 -and (($dv -gt 0) -ne ($prevD -gt 0))) { $flips++ }
            $prevD = $dv
        }
        $evInfo = " | olay=$total yon_degisimi=$flips"
        if ($c.maxev) {
            $evOk = ($total -le $c.maxev) -and ($flips -le $c.maxflip)
            $evInfo += " (sinir $($c.maxev)/$($c.maxflip): $evOk)"
            $ok = $ok -and $evOk
        }
        $ramp += $evInfo
        if (Select-String -Path $log -Pattern "HATA: kare" -Quiet) { $ok = $false; $ramp += " | SONSUZ OLAY" }
        $learn = (Select-String -Path $log -Pattern "surus modu: " | ForEach-Object { " | " + ($_.Line -replace '.*surus modu: ', '') }) -join ""
        Write-Host ("{0} {1,-16} son etkin gaz={2:N3} (beklenen {3}){4}{5}" -f ($(if ($ok) { "OK  " } else { "HATA" })), $c.n, $avg, $c.want, $ramp, $learn)
        if (-not $ok) { $fail++ }
    }
} finally {
    foreach ($e in $envs + "EBK_PREFS_PATH") { Remove-Item "Env:$e" -ErrorAction SilentlyContinue }
}
if ($fail) { Write-Host "BASARISIZ: $fail"; exit 1 }
Write-Host "Tum surus modu senaryolari gecti. Kayitlar: $out"
