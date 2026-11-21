@echo off
cd /d "%~dp0"
rem GRAFIK_YOUTUBE.bat oncesindeki grafik ayarlarini geri yukler. Oyun kapali olmali.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0grafik.ps1" -Mod normal
pause
