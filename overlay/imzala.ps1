# Oyun içi katmanı (build\ets2bakim_overlay.dll) kod imzalama sertifikasıyla imzalar.
#
# Akıllı Uygulama Denetimi yalnızca Microsoft Trusted Root Program'daki bir kuruluşun verdiği sertifikayı kabul eder;
# kendi oluşturulmuş (self-signed) sertifika imzasız sayılır. Sertifika Windows sertifika deposunda olmalı
# (ör. Certum SimplySign sanal kartı, USB anahtar ya da içe aktarılmış .pfx). İmzalama derleyici gerektirmez,
# denetim açıkken de çalışır.
#
# Kullanım:  imzala.ps1 [-Thumbprint <parmak izi>] [-Timestamp <url>] [-Dosya <yol>]
#   Parmak izi verilmezse sırayla overlay\imza.json ({"thumbprint": "...", "timestamp": "..."}),
#   EBK_IMZA_SERTIFIKA ortam değişkeni ve depodaki tek geçerli kod imzalama sertifikası denenir.
param([string]$Thumbprint, [string]$Timestamp, [string]$Dosya)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Dosya) { $Dosya = Join-Path $here "build\ets2bakim_overlay.dll" }
if (-not (Test-Path $Dosya)) { Write-Host "Imzalanacak dosya yok: $Dosya"; exit 1 }

$cfgPath = Join-Path $here "imza.json"
if (Test-Path $cfgPath) {
    $cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
    if (-not $Thumbprint) { $Thumbprint = $cfg.thumbprint }
    if (-not $Timestamp) { $Timestamp = $cfg.timestamp }
}
if (-not $Thumbprint) { $Thumbprint = $env:EBK_IMZA_SERTIFIKA }
if (-not $Timestamp) { $Timestamp = "http://timestamp.digicert.com" }  # sertifika süresi bitse de imza geçerli kalır

$certs = @(Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date) })
$cert = $null
if ($Thumbprint) {
    $tp = ($Thumbprint -replace "\s", "").ToUpperInvariant()
    $cert = $certs | Where-Object { $_.Thumbprint -eq $tp } | Select-Object -First 1
} elseif ($certs.Count -eq 1) {
    $cert = $certs[0]
}
if (-not $cert) {
    if ($certs.Count -eq 0) {
        Write-Host "Kod imzalama sertifikasi bulunamadi (Cert:\CurrentUser\My)."
        Write-Host "Guvenilir bir kurulustan sertifika alin ve depoya ekleyin; README > Akilli Uygulama Denetimi."
    } else {
        Write-Host "Birden fazla sertifika var; -Thumbprint ile secin ya da overlay\imza.json olusturun:"
        $certs | ForEach-Object { Write-Host "  $($_.Thumbprint)  $($_.Subject)  (bitis $($_.NotAfter.ToString('yyyy-MM-dd')))" }
    }
    exit 1
}
if ($cert.Subject -eq $cert.Issuer) {
    Write-Host "UYARI: sertifika kendi kendini imzalamis (self-signed). Akilli Uygulama Denetimi bunu imzasiz sayar."
}
Write-Host "Imzalaniyor: $Dosya"
Write-Host "  sertifika: $($cert.Subject)"
$r = Set-AuthenticodeSignature -FilePath $Dosya -Certificate $cert -HashAlgorithm SHA256 -TimestampServer $Timestamp
$v = Get-AuthenticodeSignature -FilePath $Dosya
Write-Host "  sonuc: $($v.Status) $($v.StatusMessage)"
if ($v.Status -ne "Valid") { exit 1 }
Write-Host "Tamam. Oyuna kurmak icin EKLENTI_KUR.bat calistirin."
