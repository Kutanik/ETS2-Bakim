# Büyük bir dosyayı paralel aralık istekleriyle indirir ve SHA-256 ile doğrular.
param(
    [string]$Url = "https://github.com/brechtsanders/winlibs_mingw/releases/download/16.2.0posix-14.0.0-ucrt-r1/winlibs-x86_64-posix-seh-gcc-16.2.0-mingw-w64ucrt-14.0.0-r1.zip",
    [long]$Size = 274029684,
    [string]$Sha256 = "C1F52294597C0B73786B2A78EB5D176D89226D2F21875EAB75E783A8B1CEFCC4",
    [string]$Out = "$env:LOCALAPPDATA\ETS2Bakim\tools\winlibs-x86_64-gcc16.2.zip",
    [int]$Parts = 24
)
$ErrorActionPreference = "Stop"
$dir = "$Out.parts"
New-Item -ItemType Directory -Force $dir | Out-Null
$chunk = [math]::Ceiling($Size / $Parts)
$ranges = 0..($Parts - 1) | ForEach-Object {
    $s = [long]$_ * $chunk
    $e = [math]::Min($Size - 1, $s + $chunk - 1)
    [pscustomobject]@{ i = $_; s = $s; e = $e; f = Join-Path $dir "part$_" }
}

function Get-Have($r) { if (Test-Path $r.f) { (Get-Item $r.f).Length } else { 0 } }

for ($round = 1; $round -le 6; $round++) {
    $todo = $ranges | Where-Object { (Get-Have $_) -lt ($_.e - $_.s + 1) }
    if (-not $todo) { break }
    Write-Host "Tur $round : $($todo.Count) parca indiriliyor..."
    $procs = foreach ($r in $todo) {
        $have = Get-Have $r
        $from = $r.s + $have
        $tmp = "$($r.f).tmp"
        $args = "-L -s --retry 10 --retry-delay 2 --retry-all-errors --speed-limit 1000 --speed-time 60 -r $from-$($r.e) -o `"$tmp`" `"$Url`""
        $p = Start-Process -FilePath curl.exe -ArgumentList $args -NoNewWindow -PassThru
        [pscustomobject]@{ r = $r; p = $p; tmp = $tmp }
    }
    foreach ($x in $procs) {
        $x.p.WaitForExit()
        if (Test-Path $x.tmp) {
            $bytes = [IO.File]::ReadAllBytes($x.tmp)
            $fs = [IO.File]::Open($x.r.f, [IO.FileMode]::Append)
            $fs.Write($bytes, 0, $bytes.Length)
            $fs.Close()
            Remove-Item $x.tmp
        }
    }
    $got = ($ranges | ForEach-Object { Get-Have $_ } | Measure-Object -Sum).Sum
    Write-Host ("  indirilen: {0:N1} / {1:N1} MB" -f ($got / 1MB), ($Size / 1MB))
}

$stream = [IO.File]::Create($Out)
foreach ($r in $ranges) {
    $bytes = [IO.File]::ReadAllBytes($r.f)
    $stream.Write($bytes, 0, $bytes.Length)
}
$stream.Close()
$h = (Get-FileHash $Out -Algorithm SHA256).Hash
if ($h -ne $Sha256) { Write-Host "HASH UYUSMUYOR: $h"; exit 1 }
Remove-Item -Recurse -Force $dir
Write-Host "DOGRULANDI: $Out"
