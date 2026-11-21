# Renk testi: sınırda (sarı) ve kritik (kırmızı) değerlerle katmanın görüntüsünü alır.
$ErrorActionPreference = "Stop"
$env:EBK_PREFS_PATH = Join-Path ([IO.Path]::GetTempPath()) "ebk_test_overlay.ini"   # gerçek katman ayarlarına (konum, dil) dokunulmaz
$ovl = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$root = Split-Path -Parent $ovl
$py = Join-Path $root ".venv\Scripts\python.exe"
$host_exe = Join-Path $ovl "build\test_host.exe"
$dll = Join-Path $ovl "build\ets2bakim_overlay.dll"
$bg = Join-Path $ovl "build\oyun_1080p.bmp"
$cap = Join-Path $ovl "build\captures\renk"
New-Item -ItemType Directory -Force $cap | Out-Null
Remove-Item "$cap\*" -ErrorAction SilentlyContinue
$feed = Start-Process -FilePath $py -ArgumentList (Join-Path $ovl "test\color_feed.py"), "40" -PassThru -NoNewWindow `
    -RedirectStandardOutput (Join-Path $cap "seviyeler.txt")
Start-Sleep -Seconds 4
$envs = "EBK_FORCE_CORNER", "EBK_FORCE_MODE", "EBK_FORCE_PAGE", "EBK_CAPTURE"
try {
    foreach ($r in @(@(1, 0, "kompakt"), @(2, 0, "genel"), @(2, 2, "yag"), @(2, 4, "aku"))) {
        $env:EBK_FORCE_CORNER = "0"; $env:EBK_FORCE_MODE = "$($r[0])"; $env:EBK_FORCE_PAGE = "$($r[1])"
        $env:EBK_CAPTURE = Join-Path $cap "$($r[2]).bmp"
        & $host_exe $dll 70 $bg | Out-Null
        if (Test-Path $env:EBK_CAPTURE) {
            & $py (Join-Path $ovl "tools\bmp2png.py") $env:EBK_CAPTURE ($env:EBK_CAPTURE -replace "\.bmp$", ".png")
            Remove-Item $env:EBK_CAPTURE
            Write-Host "  $($r[2]) -> goruntu alindi"
        } else { Write-Host "  $($r[2]) -> GORUNTU YOK" }
    }
} finally {
    foreach ($e in $envs) { Remove-Item "Env:$e" -ErrorAction SilentlyContinue }
    Stop-Process -Id $feed.Id -Force -ErrorAction SilentlyContinue
}
Write-Host "Bitti: $cap"
