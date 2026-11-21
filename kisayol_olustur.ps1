# Uygulama icin tek kisayol olusturur (proje klasorune ve istenirse masaustune): "ETS2 Bakim"
# Tek / Cok Oyunculu mod uygulamanin icinden secilir (Ayarlar -> Oyun modu); her modun ayri veri klasoru vardir
# (data, data_mp). 1.1'in iki ayri kisayolu ("ETS2 Bakim - Tek Oyunculu" / "ETS2 Bakim - Cok Oyunculu") ve daha eski
# "ETS2 Bakim" (ASCII) kisayolu, bu klasoru aciyorlarsa kaldirilir. Kisayol uygulamayi konsolsuz, kendi penceresinde acar.
param([switch]$SadeceKlasor)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyw = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pyw)) { Write-Host "Python ortami (.venv) bulunamadi; once kurulum yapilmali."; exit 1 }

# Turkce harfler: dosya ANSI okunsa da bozulmasin diye karakter kodlariyla
$i = [char]0x0131; $C = [char]0x00C7
$name = "ETS2 Bak${i}m"
$old = @("ETS2 Bakim", "ETS2 Bak${i}m - Tek Oyunculu", "ETS2 Bak${i}m - ${C}ok Oyunculu")
$dirs = @($root)
if (-not $SadeceKlasor) { $dirs += [Environment]::GetFolderPath("Desktop") }

$sh = New-Object -ComObject WScript.Shell
function Opens-Here($path) {
    # kisayol bu klasordeki uygulamayi mi aciyor (kurulu paketin ayni adli kisayoluna dokunulmaz)
    $t = $sh.CreateShortcut($path).TargetPath
    return [bool]($t -and $t.StartsWith($root, [StringComparison]::OrdinalIgnoreCase))
}
foreach ($d in $dirs) {
    foreach ($o in $old) {
        $p = Join-Path $d ($o + ".lnk")
        if ((Test-Path -LiteralPath $p) -and (Opens-Here $p)) {
            Remove-Item -LiteralPath $p -Force
            Write-Host "Eski kisayol kaldirildi: $p"
        }
    }
    $t = Join-Path $d ($name + ".lnk")
    if ((Test-Path -LiteralPath $t) -and -not (Opens-Here $t)) {
        Write-Host "Dokunulmadi (ayni adli kisayol baska bir kopyayi aciyor): $t"
        continue
    }
    $lnk = $sh.CreateShortcut($t)
    $lnk.TargetPath = $pyw
    $lnk.Arguments = "-m ets2bakim"
    $lnk.WorkingDirectory = $root
    $lnk.IconLocation = (Join-Path $root "ets2bakim\app.ico") + ",0"
    $lnk.Description = "ETS2 Bakim Simulatoru - tek ve cok oyunculu (Ayarlar -> Oyun modu)"
    $lnk.Save()
    Write-Host "Kisayol: $t"
}
