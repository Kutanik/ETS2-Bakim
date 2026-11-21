# Yeni gösterge lambaları (1.10) testi: ŞANZIMAN, DİREKSİYON, MARŞ, ABS, EL FRENİ ve FREN lambalarının ve Motor
# sayfasındaki şanzıman / debriyaj satırlarının görüntüsünü alır. Ayrı paylaşılan bellek adları (EBK_STATE_NAME /
# EBK_OVL_NAME) ve geçici ayar dosyası (EBK_PREFS_PATH) kullanır: açık simülatöre ve ayarlara dokunmaz.
# -Onem: gösterilecek en düşük önem derecesi (onemsiz | onemli | uyari | ciddi | kritik)
param([string]$Onem = "onemsiz", [string]$Dil = "tr")
$ErrorActionPreference = "Stop"
$ovl = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$root = Split-Path -Parent $ovl
$py = Join-Path $root ".venv\Scripts\python.exe"
$host_exe = Join-Path $ovl "build\test_host.exe"
$dll = Join-Path $ovl "build\ets2bakim_overlay.dll"
$bg = Join-Path $ovl "build\oyun_1080p.bmp"
$cap = Join-Path $ovl "build\captures\yeni_lamba"
New-Item -ItemType Directory -Force $cap | Out-Null
$stateName = "Local\EBKYeniLambaState"; $ovlName = "Local\EBKYeniLambaOvl"
$feed = Start-Process -FilePath $py -ArgumentList (Join-Path $ovl "test\yeni_lamba_feed.py"), "40", $stateName, $ovlName, $Onem, $Dil `
    -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $cap "lambalar.txt")
Start-Sleep -Seconds 5
$envs = "EBK_STATE_NAME", "EBK_OVL_NAME", "EBK_PREFS_PATH", "EBK_FORCE_CORNER", "EBK_FORCE_MODE", "EBK_FORCE_PAGE",
        "EBK_CAPTURE", "EBK_CAPTURE_AFTER"
$cases = @(
    @{ name = "motor_sayfasi"; mode = 2; page = 1 },
    @{ name = "yalniz_lambalar"; mode = 0; page = 0 }
)
try {
    foreach ($c in $cases) {
        foreach ($e in $envs) { Remove-Item "Env:$e" -ErrorAction SilentlyContinue }
        $env:EBK_STATE_NAME = $stateName; $env:EBK_OVL_NAME = $ovlName
        $env:EBK_PREFS_PATH = Join-Path $cap "test_overlay.ini"
        $env:EBK_FORCE_CORNER = "0"; $env:EBK_FORCE_MODE = "$($c.mode)"; $env:EBK_FORCE_PAGE = "$($c.page)"
        $env:EBK_CAPTURE_AFTER = "60"
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
Get-Content (Join-Path $cap "lambalar.txt")
Write-Host "Bitti: $cap"
