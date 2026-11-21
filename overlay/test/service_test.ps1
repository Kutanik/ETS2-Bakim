# Dört köşe yerleşimini ve oyun içi servis menüsünü (Alt+F8) oyunu açmadan dener.
#  - demo simülatör başlatılır (ilk dakikalarda tır park halinde, motor kapalı)
#  - test_host.exe DLL'i oyun gibi yükler; gerçek oyun ekran görüntüsü arka plan olur
#  - servis menüsünden "yağı MAX'a tamamla" uygulanır ve simülatörün kaydında sonucu doğrulanır
param([int]$Warmup = 8, [string]$Lang = "tr")
$ErrorActionPreference = "Stop"
$env:EBK_PREFS_PATH = Join-Path ([IO.Path]::GetTempPath()) "ebk_test_overlay.ini"   # gerçek katman ayarlarına (konum, dil) dokunulmaz
$ovl = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$root = Split-Path -Parent $ovl
$py = Join-Path $root ".venv\Scripts\python.exe"
$host_exe = Join-Path $ovl "build\test_host.exe"
$dll = Join-Path $ovl "build\ets2bakim_overlay.dll"
$bg = Join-Path $ovl "build\oyun_1080p.bmp"
$cap = Join-Path $ovl "build\captures\servis_$Lang"
New-Item -ItemType Directory -Force $cap | Out-Null
Remove-Item "$cap\*" -ErrorAction SilentlyContinue
$demo = Join-Path $root "data_demo"
Remove-Item -Recurse -Force $demo -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $demo | Out-Null
[IO.File]::WriteAllText((Join-Path $demo "ayarlar.json"), "{`"language`": `"$Lang`"}")
$envs = "EBK_FORCE_CORNER", "EBK_FORCE_MODE", "EBK_FORCE_PAGE", "EBK_CAPTURE", "EBK_CAPTURE_AFTER", "EBK_FORCE_SERVICE",
        "EBK_FORCE_SVC_SEL", "EBK_FORCE_SVC_APPLY"
function Clear-Ebk { foreach ($e in $envs) { Remove-Item "Env:$e" -ErrorAction SilentlyContinue } }
function Shot($name, $frames = 70) {
    $env:EBK_CAPTURE = Join-Path $cap "$name.bmp"
    & $host_exe $dll $frames $bg | Out-Null
    if (Test-Path $env:EBK_CAPTURE) {
        & $py (Join-Path $ovl "tools\bmp2png.py") $env:EBK_CAPTURE ($env:EBK_CAPTURE -replace "\.bmp$", ".png")
        Remove-Item $env:EBK_CAPTURE
        Write-Host "  $name -> goruntu alindi"
    } else { Write-Host "  $name -> GORUNTU YOK" }
}

$sim = Start-Process -FilePath $py -ArgumentList "-m", "ets2bakim", "--demo", "--hiz", "4", "--pencere-yok", "--port", "8799" `
    -WorkingDirectory $root -PassThru -WindowStyle Hidden
Write-Host "Simulator (demo, $Lang) PID $($sim.Id), $Warmup sn bekleniyor..."
Start-Sleep -Seconds $Warmup
try {
    Clear-Ebk
    # servis menüsü açık (sol üst), ardından "yağı MAX'a tamamla" uygulanıp sonucu yakalanır
    $env:EBK_FORCE_CORNER = "0"; $env:EBK_FORCE_SERVICE = "1"
    Shot "menu_sol_ust"
    $env:EBK_FORCE_SVC_SEL = "oil_fill"; $env:EBK_FORCE_SVC_APPLY = "25"; $env:EBK_CAPTURE_AFTER = "200"
    Shot "menu_uygulandi" 260
    Clear-Ebk
    $st = Invoke-RestMethod "http://127.0.0.1:8799/api/state"
    Write-Host "  simulator kaydi: $($st.log[0].text)"
    Write-Host ("  yag seviyesi: %{0}" -f $st.oil.level_pct)
    # dört köşe (kompakt) ve sağ altta servis menüsü
    foreach ($c in 0, 1, 2, 3) {
        $env:EBK_FORCE_CORNER = "$c"; $env:EBK_FORCE_MODE = "1"
        Shot "kose${c}_kompakt"
    }
    $env:EBK_FORCE_CORNER = "2"; $env:EBK_FORCE_MODE = "2"; $env:EBK_FORCE_PAGE = "0"
    Shot "kose2_detayli"
    $env:EBK_FORCE_SERVICE = "1"; $env:EBK_FORCE_SVC_SEL = "batt_replace"
    Shot "menu_sag_alt"
} finally {
    Clear-Ebk
    Stop-Process -Id $sim.Id -Force -ErrorAction SilentlyContinue
}
Write-Host "Bitti. Goruntuler: $cap"
