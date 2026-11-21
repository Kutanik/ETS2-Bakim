@echo off
cd /d "%~dp0"
rem ETS2 grafiklerini YouTube kaydi icin yukseltir (TruckersMP ayni ayarlari kullanir). Oyun kapali olmali.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0grafik.ps1" -Mod youtube
pause
