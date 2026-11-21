@echo off
cd /d "%~dp0"
rem ETS2 grafiklerini bir kademe dusurur (kalabalik TruckersMP sunuculari icin); hicbir ozellik kapanmaz. Oyun kapali olmali.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0grafik.ps1" -Mod dengeli
pause
