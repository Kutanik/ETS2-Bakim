# Katmanı oyunu açmadan uçtan uca dener:
#  1) simülatörü demo modunda başlatır (paylaşılan belleğe veri yazar)
#  2) test_host.exe ile DLL'i oyun gibi yükler, her mod/sayfanın ekran görüntüsünü alır
#  3) semantik giriş cihazına "kontağı kapat" komutu gönderip olayın oyuna ulaştığını doğrular
param([int]$Warmup = 45)
$ErrorActionPreference = "Stop"
$env:EBK_PREFS_PATH = Join-Path ([IO.Path]::GetTempPath()) "ebk_test_overlay.ini"   # gerçek katman ayarlarına (konum, dil) dokunulmaz
$ovl = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$root = Split-Path -Parent $ovl
$py = Join-Path $root ".venv\Scripts\python.exe"
$host_exe = Join-Path $ovl "build\test_host.exe"
$dll = Join-Path $ovl "build\ets2bakim_overlay.dll"
$cap = Join-Path $ovl "build\captures"
New-Item -ItemType Directory -Force $cap | Out-Null
Remove-Item "$cap\*" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $root "data_demo") -ErrorAction SilentlyContinue

$sim = Start-Process -FilePath $py -ArgumentList "-m", "ets2bakim", "--demo", "--hiz", "4", "--pencere-yok", "--port", "8799" `
    -WorkingDirectory $root -PassThru -WindowStyle Hidden
Write-Host "Simulator (demo) PID $($sim.Id), $Warmup sn isiniyor..."
Start-Sleep -Seconds $Warmup

$runs = @(@(1, 0, "kompakt"), @(2, 0, "genel"), @(2, 1, "motor"), @(2, 2, "yag"), @(2, 3, "sogutma"), @(2, 4, "aku"), @(2, 5, "analiz"), @(2, 6, "kayit"))
foreach ($r in $runs) {
    $env:EBK_FORCE_MODE = "$($r[0])"
    $env:EBK_FORCE_PAGE = "$($r[1])"
    $env:EBK_CAPTURE = Join-Path $cap "$($r[2]).bmp"
    $out = & $host_exe $dll 70 2>&1
    $ok = Test-Path $env:EBK_CAPTURE
    Write-Host ("  {0,-8} -> {1}" -f $r[2], $(if ($ok) { "goruntu alindi" } else { "GORUNTU YOK" }))
    if (-not $ok) { $out | Select-Object -Last 15 | ForEach-Object { Write-Host "     $_" } }
    if ($ok) { & $py (Join-Path $ovl "tools\bmp2png.py") $env:EBK_CAPTURE ($env:EBK_CAPTURE -replace "\.bmp$", ".png"); Remove-Item $env:EBK_CAPTURE }
}
Remove-Item Env:EBK_CAPTURE, Env:EBK_FORCE_PAGE -ErrorAction SilentlyContinue
$env:EBK_FORCE_MODE = "1"

# giriş cihazı testi: test_host çalışırken komut gönder
$log = Join-Path $cap "input_test.txt"
$p = Start-Process -FilePath $host_exe -ArgumentList "`"$dll`"", "240" -PassThru -NoNewWindow -RedirectStandardOutput $log
Start-Sleep -Seconds 2
& $py -c @"
import struct
from multiprocessing import shared_memory
m = shared_memory.SharedMemory(name='Local\\ETS2BakimState', create=False)
seq = struct.unpack_from('<I', m.buf, 16)[0]
struct.pack_into('<II', m.buf, 16, seq + 1, 1)
print('komut gonderildi: kontagi kapat, seq', seq + 1)
m.close()
"@
$p.WaitForExit()
Get-Content $log | Select-String -Pattern "giris|disa|init|ets2bakim|katman|kanca|DXGI" | ForEach-Object { Write-Host "  $_" }

Stop-Process -Id $sim.Id -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# uyarı şeridi (sahte kritik uyarılarla) ve simülatör kapalıyken görünüm
$inj = Start-Process -FilePath $py -ArgumentList (Join-Path $ovl "test\inject_warning.py"), "7" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 1
foreach ($r in @(, @("1", "uyari"))) {
    $env:EBK_FORCE_MODE = $r[0]
    $env:EBK_CAPTURE = Join-Path $cap "$($r[1]).bmp"
    & $host_exe $dll 70 | Out-Null
    if (Test-Path $env:EBK_CAPTURE) { & $py (Join-Path $ovl "tools\bmp2png.py") $env:EBK_CAPTURE ($env:EBK_CAPTURE -replace "\.bmp$", ".png"); Remove-Item $env:EBK_CAPTURE; Write-Host "  $($r[1]) -> goruntu alindi" }
}
$inj.WaitForExit()
$env:EBK_FORCE_MODE = "1"
$env:EBK_CAPTURE = Join-Path $cap "kapali.bmp"
& $host_exe $dll 70 | Out-Null
if (Test-Path $env:EBK_CAPTURE) { & $py (Join-Path $ovl "tools\bmp2png.py") $env:EBK_CAPTURE ($env:EBK_CAPTURE -replace "\.bmp$", ".png"); Remove-Item $env:EBK_CAPTURE; Write-Host "  kapali -> goruntu alindi" }
Remove-Item Env:EBK_FORCE_MODE, Env:EBK_CAPTURE -ErrorAction SilentlyContinue
Write-Host "Bitti. Goruntuler: $cap"
