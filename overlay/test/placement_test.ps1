# Katmanın oyun ekranındaki yerleşimini dener: gerçek oyun ekran görüntüsünü (build\oyun_1080p.bmp)
# arka plan yapıp her konum ve sayfa için görüntü alır.
param([int]$Warmup = 40, [string]$Lang = "tr", [string]$Background = "")
$ErrorActionPreference = "Stop"
$env:EBK_PREFS_PATH = Join-Path ([IO.Path]::GetTempPath()) "ebk_test_overlay.ini"   # gerçek katman ayarlarına (konum, dil) dokunulmaz
$ovl = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$root = Split-Path -Parent $ovl
$py = Join-Path $root ".venv\Scripts\python.exe"
$host_exe = Join-Path $ovl "build\test_host.exe"
$dll = Join-Path $ovl "build\ets2bakim_overlay.dll"
if (-not $Background) { $Background = Join-Path $ovl "build\oyun_1080p.bmp" }
$cap = Join-Path $ovl "build\captures\yerlesim_$Lang"
New-Item -ItemType Directory -Force $cap | Out-Null
Remove-Item "$cap\*" -ErrorAction SilentlyContinue
$demo = Join-Path $root "data_demo"
Remove-Item -Recurse -Force $demo -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $demo | Out-Null
[IO.File]::WriteAllText((Join-Path $demo "ayarlar.json"), "{`"language`": `"$Lang`"}")

$sim = Start-Process -FilePath $py -ArgumentList "-m", "ets2bakim", "--demo", "--hiz", "4", "--pencere-yok", "--port", "8799" `
    -WorkingDirectory $root -PassThru -WindowStyle Hidden
Write-Host "Simulator (demo, $Lang) PID $($sim.Id), $Warmup sn isiniyor..."
Start-Sleep -Seconds $Warmup

# konum, mod, sayfa, ad
# varsayılan konumda (0) tüm sayfalar, diğer konumlarda örnekler
$runs = @()
foreach ($c in 0, 1, 2, 3) {
    $runs += , @($c, 1, 0, "k${c}_kompakt")
    $pages = if ($c -eq 0) { 0..9 } else { @(0, 5) }
    foreach ($pg in $pages) { $runs += , @($c, 2, $pg, "k${c}_s$pg") }
}
foreach ($r in $runs) {
    $env:EBK_FORCE_CORNER = "$($r[0])"
    $env:EBK_FORCE_MODE = "$($r[1])"
    $env:EBK_FORCE_PAGE = "$($r[2])"
    $env:EBK_CAPTURE = Join-Path $cap "$($r[3]).bmp"
    & $host_exe $dll 70 $Background | Out-Null
    if (Test-Path $env:EBK_CAPTURE) {
        & $py (Join-Path $ovl "tools\bmp2png.py") $env:EBK_CAPTURE ($env:EBK_CAPTURE -replace "\.bmp$", ".png")
        Remove-Item $env:EBK_CAPTURE
        Write-Host "  $($r[3]) -> goruntu alindi"
    } else { Write-Host "  $($r[3]) -> GORUNTU YOK" }
}
# oyunda HUD gizliyken (F3) katman da gizli olmalı
$env:EBK_FORCE_CORNER = "0"; $env:EBK_FORCE_MODE = "1"; $env:EBK_FORCE_HUDHIDDEN = "1"
$env:EBK_CAPTURE = Join-Path $cap "hud_gizli.bmp"
& $host_exe $dll 70 $Background | Out-Null
if (Test-Path $env:EBK_CAPTURE) {
    & $py (Join-Path $ovl "tools\bmp2png.py") $env:EBK_CAPTURE ($env:EBK_CAPTURE -replace "\.bmp$", ".png")
    Remove-Item $env:EBK_CAPTURE
    Write-Host "  hud_gizli -> goruntu alindi"
}
Remove-Item Env:EBK_FORCE_CORNER, Env:EBK_FORCE_MODE, Env:EBK_FORCE_PAGE, Env:EBK_CAPTURE, Env:EBK_FORCE_HUDHIDDEN -ErrorAction SilentlyContinue
Stop-Process -Id $sim.Id -Force -ErrorAction SilentlyContinue
Write-Host "Bitti. Goruntuler: $cap"
