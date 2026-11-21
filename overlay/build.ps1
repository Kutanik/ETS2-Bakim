# Oyun içi katmanı (ets2bakim_overlay.dll) ve test uygulamasını MinGW-w64 (GCC) ile derler.
param([switch]$NoTest)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# Akıllı Uygulama Denetimi açıkken imzasız MinGW derleyicisi çalıştırılamaz (Windows engeller).
$sac = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy" -ErrorAction SilentlyContinue).VerifiedAndReputablePolicyState
if ($sac -eq 1) {
    Write-Host "Akilli Uygulama Denetimi acik: MinGW derleyicisi imzasiz oldugu icin Windows onu engeller."
    Write-Host "Derlemek icin denetimi kapatin (Windows Guvenligi > Uygulama ve tarayici denetimi)."
    Write-Host "Mevcut DLL'i imzalamak icin derleme gerekmez: overlay\imzala.ps1 (README > Akilli Uygulama Denetimi)."
    exit 1
}

function Find-Gpp {
    $project = Join-Path $root "tools\mingw64\bin\g++.exe"
    if (Test-Path $project) { return $project }
    $c = Get-Command g++ -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    $pkgs = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    $hit = Get-ChildItem -Path $pkgs -Recurse -Filter g++.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match "WinLibs" -and $_.FullName -match "mingw64\\bin" } | Select-Object -First 1
    if ($hit) { return $hit.FullName }
    throw "g++ bulunamadi. 'winget install BrechtSanders.WinLibs.POSIX.UCRT' ile MinGW-w64 kurun."
}
$gpp = Find-Gpp
$bin = Split-Path $gpp
$env:PATH = "$bin;$env:PATH"
$gcc = Join-Path $bin "gcc.exe"
Write-Host "Derleyici: $gpp"

$tp = "third_party"
$obj = "build\obj"
New-Item -ItemType Directory -Force $obj | Out-Null
$inc = @("-I$tp/scs_sdk/include", "-I$tp/imgui", "-I$tp/imgui/backends", "-I$tp/minhook/include")
$common = @("-O2", "-DNDEBUG", "-DIMGUI_DISABLE_OBSOLETE_FUNCTIONS", "-D_WIN32_WINNT=0x0A00")

$objs = @()
# MinHook (C)
foreach ($f in @("src/buffer.c", "src/hook.c", "src/trampoline.c", "src/hde/hde64.c", "src/hde/hde32.c")) {
    $o = Join-Path $obj ("mh_" + [IO.Path]::GetFileNameWithoutExtension($f) + ".o")
    & $gcc -c @common @inc "$tp/minhook/$f" -o $o
    if ($LASTEXITCODE) { throw "derleme hatasi: $f" }
    $objs += $o
}
# Dear ImGui + katman (C++)
$cpp = @("$tp/imgui/imgui.cpp", "$tp/imgui/imgui_draw.cpp", "$tp/imgui/imgui_tables.cpp", "$tp/imgui/imgui_widgets.cpp",
         "$tp/imgui/backends/imgui_impl_dx11.cpp", "$tp/imgui/backends/imgui_impl_win32.cpp", "src/ebk_overlay.cpp")
foreach ($f in $cpp) {
    $o = Join-Path $obj ([IO.Path]::GetFileNameWithoutExtension($f) + ".o")
    $src = Get-Item $f
    if (-not (Test-Path $o) -or (Get-Item $o).LastWriteTime -lt $src.LastWriteTime -or $f -like "src/*") {
        Write-Host "  $f"
        & $gpp -c -std=c++17 @common @inc $f -o $o
        if ($LASTEXITCODE) { throw "derleme hatasi: $f" }
    }
    $objs += $o
}
& $gpp -shared -static -static-libgcc -static-libstdc++ -o build/ets2bakim_overlay.dll @objs `
    -ld3d11 -ldxgi -ld3dcompiler -ldwmapi -lgdi32 -luser32 -limm32
if ($LASTEXITCODE) { throw "baglama hatasi (dll)" }
Write-Host "OK -> build\ets2bakim_overlay.dll ($([math]::Round((Get-Item build/ets2bakim_overlay.dll).Length/1KB)) KB)"
# Sertifika tanımlıysa (overlay\imza.json ya da EBK_IMZA_SERTIFIKA) DLL hemen imzalanır
if ((Test-Path (Join-Path $root "imza.json")) -or $env:EBK_IMZA_SERTIFIKA) {
    & (Join-Path $root "imzala.ps1")
    if ($LASTEXITCODE) { throw "imzalama hatasi" }
} else {
    Write-Host "DLL imzasiz (Akilli Uygulama Denetimi acikken oyun yuklemez; bkz. overlay\imzala.ps1)."
}

if (-not $NoTest) {
    & $gpp -std=c++17 -O1 @inc test/test_host.cpp -o build/test_host.exe -static -ld3d11 -ldxgi -luser32
    if ($LASTEXITCODE) { throw "baglama hatasi (test)" }
    Write-Host "OK -> build\test_host.exe"
}
