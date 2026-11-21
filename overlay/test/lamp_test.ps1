# Gösterge lambaları ve menüde gizleme testi: sahte arızalı tır durumuyla katmanın görüntülerini alır.
#   kompakt     : kompakt panel + alt ortada lambalar
#   kapali      : katman kapalı (F8) — yalnızca lambalar
#   menu        : oyun duraklatılmış (ana menü) — hiçbir şey görünmemeli
#   duraklatma  : sürüşte Esc ile duraklatma (20. kare) — hiçbir şey görünmemeli
#   devam       : duraklatma (20.) ve devam (40.) — kompakt panel ve lambalar geri gelmeli
$ErrorActionPreference = "Stop"
$env:EBK_PREFS_PATH = Join-Path ([IO.Path]::GetTempPath()) "ebk_test_overlay.ini"   # gerçek katman ayarlarına (konum, dil) dokunulmaz
$ovl = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$root = Split-Path -Parent $ovl
$py = Join-Path $root ".venv\Scripts\python.exe"
$host_exe = Join-Path $ovl "build\test_host.exe"
$dll = Join-Path $ovl "build\ets2bakim_overlay.dll"
$bg = Join-Path $ovl "build\oyun_1080p.bmp"
$cap = Join-Path $ovl "build\captures\lamba"
New-Item -ItemType Directory -Force $cap | Out-Null
Remove-Item "$cap\*" -ErrorAction SilentlyContinue
$feed = Start-Process -FilePath $py -ArgumentList (Join-Path $ovl "test\color_feed.py"), "60" -PassThru -NoNewWindow `
    -RedirectStandardOutput (Join-Path $cap "seviyeler.txt")
Start-Sleep -Seconds 4
$envs = "EBK_FORCE_CORNER", "EBK_FORCE_MODE", "EBK_FORCE_PAGE", "EBK_CAPTURE", "EBK_CAPTURE_AFTER",
        "EBK_TEST_PAUSED", "EBK_TEST_PAUSE_AT", "EBK_TEST_RESUME_AT"
$cases = @(
    @{ name = "kompakt"; mode = 1 },
    @{ name = "kompakt_b"; mode = 1; after = 70 },
    @{ name = "kapali"; mode = 0 },
    @{ name = "menu"; mode = 1; paused = 1 },
    @{ name = "duraklatma"; mode = 1; pause = 20 },
    @{ name = "devam"; mode = 1; pause = 20; resume = 40; after = 60 }
)
try {
    foreach ($c in $cases) {
        foreach ($e in $envs) { Remove-Item "Env:$e" -ErrorAction SilentlyContinue }
        $env:EBK_FORCE_CORNER = "3"; $env:EBK_FORCE_MODE = "$($c.mode)"; $env:EBK_FORCE_PAGE = "0"
        if ($c.after) { $env:EBK_CAPTURE_AFTER = "$($c.after)" }
        if ($c.paused) { $env:EBK_TEST_PAUSED = "1" }
        if ($c.pause) { $env:EBK_TEST_PAUSE_AT = "$($c.pause)" }
        if ($c.resume) { $env:EBK_TEST_RESUME_AT = "$($c.resume)" }
        $env:EBK_CAPTURE = Join-Path $cap "$($c.name).bmp"
        & $host_exe $dll 90 $bg | Out-Null
        if (Test-Path $env:EBK_CAPTURE) {
            & $py (Join-Path $ovl "tools\bmp2png.py") $env:EBK_CAPTURE ($env:EBK_CAPTURE -replace "\.bmp$", ".png")
            Remove-Item $env:EBK_CAPTURE
            Write-Host "  $($c.name) -> goruntu alindi"
        } else { Write-Host "  $($c.name) -> GORUNTU YOK" }
    }
} finally {
    foreach ($e in $envs) { Remove-Item "Env:$e" -ErrorAction SilentlyContinue }
    Stop-Process -Id $feed.Id -Force -ErrorAction SilentlyContinue
}
Write-Host "Bitti: $cap"
