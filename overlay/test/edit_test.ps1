# Fareyle düzenleme (Ctrl+Alt+F8) testi: sahte tır durumuyla katmanı açar, test betiğiyle (EBK_TEST_EDIT) fare girdisi
# verir, ekran görüntüsü alır ve kaydedilen ayarları denetler. Gerçek fare kancası kurulmaz, gerçek overlay.ini'ye
# dokunulmaz (EBK_PREFS_PATH geçici dosyaya yönlendirilir).
$ErrorActionPreference = "Stop"
$ovl = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$root = Split-Path -Parent $ovl
$py = Join-Path $root ".venv\Scripts\python.exe"
$host_exe = Join-Path $ovl "build\test_host.exe"
$dll = Join-Path $ovl "build\ets2bakim_overlay.dll"
$bg = Join-Path $ovl "build\oyun_1080p.bmp"
$cap = Join-Path $ovl "build\captures\duzenleme"
New-Item -ItemType Directory -Force $cap | Out-Null
Remove-Item "$cap\*" -ErrorAction SilentlyContinue
$ini = Join-Path $cap "test_overlay.ini"
$feed = Start-Process -FilePath $py -ArgumentList (Join-Path $ovl "test\color_feed.py"), "150" -PassThru -NoNewWindow `
    -RedirectStandardOutput (Join-Path $cap "besleme.txt")
Start-Sleep -Seconds 4

function Ini($key) {
    $m = Select-String -Path $ini -Pattern "^$key=(.*)$" -ErrorAction SilentlyContinue
    if ($m) { return $m.Matches[0].Groups[1].Value } else { return "" }
}
$fail = 0
function Check($name, $ok) {
    if ($ok) { Write-Host "  OK   $name" } else { Write-Host "  HATA $name"; $script:fail++ }
}

# ad, betik, yakalama karesi (betik adımları kare sayar; "n:K" K kare bekler)
$cases = @(
    @{ name = "1_duzenleme"; script = "n:25;on;n:3;cp;n:60;r"; after = 45 },
    @{ name = "2_tasima"; script = "n:25;on;n:3;cp;n:2;d;n:1;m:700,350;n:2;m:500,150;n:3;u;n:60;r"; after = 55 },
    @{ name = "3_tekerlek"; script = "n:25;on;n:3;cp;n:2;w:4;n:60;r"; after = 45 },
    @{ name = "4_tutamac"; script = "n:25;on;n:3;gp;n:2;d;n:1;m:90,90;n:3;u;n:60;r"; after = 50 },
    @{ name = "5_lambalar"; script = "n:25;on;n:3;cl;n:2;d;n:1;m:-650,-420;n:3;u;n:3;gl;n:2;d;n:1;m:70,-50;n:3;u;n:60;r"; after = 62 },
    @{ name = "6_kalici"; script = ""; after = 45 },
    @{ name = "7_sifirla"; script = "n:25;on;n:3;cp;n:2;mid;n:3;cl;n:2;mid;n:60;r"; after = 50 }
)
$envs = "EBK_FORCE_CORNER", "EBK_FORCE_MODE", "EBK_FORCE_PAGE", "EBK_CAPTURE", "EBK_CAPTURE_AFTER", "EBK_TEST_EDIT", "EBK_PREFS_PATH"
try {
    foreach ($c in $cases) {
        foreach ($e in $envs) { Remove-Item "Env:$e" -ErrorAction SilentlyContinue }
        $env:EBK_PREFS_PATH = $ini
        $env:EBK_FORCE_MODE = "1"
        if ($c.script) { $env:EBK_TEST_EDIT = $c.script }
        $env:EBK_CAPTURE_AFTER = "$($c.after)"
        $env:EBK_CAPTURE = Join-Path $cap "$($c.name).bmp"
        & $host_exe $dll 120 $bg | Out-Null
        if (Test-Path $env:EBK_CAPTURE) {
            & $py (Join-Path $ovl "tools\bmp2png.py") $env:EBK_CAPTURE ($env:EBK_CAPTURE -replace "\.bmp$", ".png")
            Remove-Item $env:EBK_CAPTURE
        } else { Write-Host "  $($c.name): GORUNTU YOK"; $fail++ }
        $vals = "free=$(Ini free) fx=$(Ini fx) fy=$(Ini fy) fpx=$(Ini fpx) fpy=$(Ini fpy) zoom=$(Ini zoom) lamp_free=$(Ini lamp_free) lx=$(Ini lx) ly=$(Ini ly) lamp_zoom=$(Ini lamp_zoom)"
        Write-Host "$($c.name): $vals"
        switch ($c.name) {
            "2_tasima" {
                Check "panel serbest konumda" ((Ini free) -eq "1")
                Check "panel sag alt yariya tutturuldu" ((Ini fpx) -eq "1" -and (Ini fpy) -eq "1")
                Check "panel ekranin sag alt bolgesinde" ([double](Ini fx) -gt 0.6 -and [double](Ini fy) -gt 0.6)
            }
            "3_tekerlek" { Check "tekerlekle panel %120" ([math]::Abs([double](Ini zoom) - 1.2) -lt 0.001) }
            "4_tutamac" { Check "tutamacla panel kuculdu" ([double](Ini zoom) -lt 1.2 -and [double](Ini zoom) -ge 0.7) }
            "5_lambalar" {
                Check "lambalar serbest konumda" ((Ini lamp_free) -eq "1")
                Check "lambalar sola ve yukari tasindi" ([double](Ini lx) -lt 0.3 -and [double](Ini ly) -lt 0.75)
                Check "tutamacla lambalar buyudu" ([double](Ini lamp_zoom) -gt 1.0)
            }
            "7_sifirla" {
                Check "panel varsayilana dondu" ((Ini free) -eq "0" -and [double](Ini zoom) -eq 1.0)
                Check "lambalar varsayilana dondu" ((Ini lamp_free) -eq "0" -and [double](Ini lamp_zoom) -eq 1.0)
            }
        }
    }
} finally {
    foreach ($e in $envs) { Remove-Item "Env:$e" -ErrorAction SilentlyContinue }
    Stop-Process -Id $feed.Id -Force -ErrorAction SilentlyContinue
}
if ($fail) { Write-Host "BASARISIZ: $fail"; exit 1 }
Write-Host "Tum kontroller gecti. Goruntuler: $cap"
