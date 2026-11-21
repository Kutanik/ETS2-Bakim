# ETS2 / ATS telemetri eklentisini (RenCloud scs-sdk-plugin V.1.12.1) ve oyun ici katmani oyun klasorune kurar.
# Kaynak: https://github.com/RenCloud/scs-sdk-plugin/releases/tag/V.1.12.1
# Telemetri eklentisi zaten kuruluysa yeniden indirilmez (-Yenile ile indirilir).
# Akilli Uygulama Denetimi aciksa imzasiz katman kurulmaz (oyun onu yukleyemez), kuruluysa kaldirilir.
param([switch]$Yenile)
$ErrorActionPreference = "Stop"
$ReleaseUrl = "https://github.com/RenCloud/scs-sdk-plugin/releases/download/V.1.12.1/release_v_1_12_1.zip"

function Get-SteamLibraries {
    $libs = @()
    $steam = $null
    try { $steam = (Get-ItemProperty -Path "HKCU:\Software\Valve\Steam" -ErrorAction Stop).SteamPath } catch { }
    if (-not $steam) { $steam = "C:\Program Files (x86)\Steam" }
    $steam = $steam -replace "/", "\"
    $libs += $steam
    $vdf = Join-Path $steam "steamapps\libraryfolders.vdf"
    if (Test-Path $vdf) {
        foreach ($line in Get-Content $vdf) {
            if ($line -match '"path"\s+"(.+)"') { $libs += ($Matches[1] -replace "\\\\", "\") }
        }
    }
    $seen = @{}
    return $libs | Where-Object { $k = $_.TrimEnd("\").ToLowerInvariant(); if ($seen.ContainsKey($k)) { $false } else { $seen[$k] = 1; $true } }
}

$games = @()
foreach ($lib in Get-SteamLibraries) {
    foreach ($g in @("Euro Truck Simulator 2", "American Truck Simulator")) {
        $bin = Join-Path $lib "steamapps\common\$g\bin\win_x64"
        if (Test-Path $bin) { $games += $bin }
    }
}
if ($games.Count -eq 0) {
    Write-Host "Oyun klasoru bulunamadi. Elle kurulum: zip icindeki 64 bit scs-telemetry.dll dosyasini"
    Write-Host "  <oyun klasoru>\bin\win_x64\plugins\  klasorune kopyalayin."
    exit 1
}

$needTelemetry = $Yenile -or @($games | Where-Object { -not (Test-Path (Join-Path $_ "plugins\scs-telemetry.dll")) }).Count -gt 0
$dll = $null
if ($needTelemetry) {
    $tmp = Join-Path $env:TEMP "ets2bakim_eklenti"
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    New-Item -ItemType Directory -Force $tmp | Out-Null
    $zip = Join-Path $tmp "release.zip"
    Write-Host "Indiriliyor: $ReleaseUrl"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $ReleaseUrl -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath (Join-Path $tmp "x") -Force

    $dlls = Get-ChildItem -Path (Join-Path $tmp "x") -Recurse -Filter "scs-telemetry.dll"
    $dll = $dlls | Where-Object { $_.FullName -match "64" } | Select-Object -First 1
    if (-not $dll) { $dll = $dlls | Select-Object -First 1 }
    if (-not $dll) { Write-Host "Zip icinde scs-telemetry.dll bulunamadi."; exit 1 }
    Write-Host "Bulunan eklenti: $($dll.FullName)"
} else {
    Write-Host "Telemetri eklentisi zaten kurulu (yeniden indirmek icin: eklenti_kur.ps1 -Yenile)."
}

# Akilli Uygulama Denetimi: acikken (1) yalnizca guvenilir sertifikayla imzali DLL yuklenebilir
$sac = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy" -ErrorAction SilentlyContinue).VerifiedAndReputablePolicyState
$overlay = Join-Path $PSScriptRoot "overlay\build\ets2bakim_overlay.dll"
$overlayOk = Test-Path $overlay
$overlayBlocked = $false
if ($overlayOk -and $sac -eq 1) {
    $sig = Get-AuthenticodeSignature -FilePath $overlay
    $overlayBlocked = $sig.Status -ne "Valid"
}
foreach ($bin in $games) {
    $plugins = Join-Path $bin "plugins"
    try {
        New-Item -ItemType Directory -Force $plugins | Out-Null
        if ($dll) {
            Copy-Item -Path $dll.FullName -Destination (Join-Path $plugins "scs-telemetry.dll") -Force
            Write-Host "KURULDU -> $plugins\scs-telemetry.dll"
        }
        $target = Join-Path $plugins "ets2bakim_overlay.dll"
        if (-not $overlayOk) {
            Write-Host "Oyun ici katman bulunamadi (overlay\build). Once overlay\build.ps1 ile derleyin."
        } elseif ($overlayBlocked) {
            Write-Host "ATLANDI -> oyun ici katman: Akilli Uygulama Denetimi acik ve DLL imzasiz; oyun onu yukleyemez."
            if ((Test-Path $target) -and (Get-AuthenticodeSignature -FilePath $target).Status -ne "Valid") {
                Remove-Item -Path $target -Force
                Write-Host "KALDIRILDI -> $target (her oyun acilisinda engellenip bildirim cikariyordu)"
            }
            Write-Host "  Simulator, uygulama penceresi ve motor durdurma (tus yontemi) katmansiz calisir."
            Write-Host "  Katman icin DLL'i guvenilir bir sertifikayla imzalayin (overlay\imzala.ps1) ya da denetimi kapatin."
        } else {
            Copy-Item -Path $overlay -Destination $target -Force
            Write-Host "KURULDU -> $target (oyun ici katman)"
        }
    } catch {
        Write-Host "Kopyalanamadi: $plugins"
        Write-Host "Oyun aciksa kapatin. Hala olmuyorsa bu dosyayi yonetici olarak calistirin."
    }
}
Write-Host ""
Write-Host "Tamam. Oyunu acinca cikan 'Advanced SDK features' uyarisini OK ile onaylayin."
Write-Host "Durum raporu: .venv\Scripts\python.exe -m ets2bakim.appcontrol"
Write-Host "Kaldirmak icin plugins klasorundeki scs-telemetry.dll ve ets2bakim_overlay.dll dosyalarini silmeniz yeterli."
