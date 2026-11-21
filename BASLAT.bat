@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ETS2 Bakim Simulatoru
if not exist ".venv\Scripts\python.exe" (
  echo Ilk kurulum yapiliyor, lutfen bekleyin...
  py -3 -m venv .venv 2>nul
  if not exist ".venv\Scripts\python.exe" python -m venv .venv
  if not exist ".venv\Scripts\python.exe" (
    echo Python bulunamadi. https://www.python.org adresinden Python 3.10 veya ustunu kurun.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -c "import truck_telemetry, webview" 2>nul || (
  echo Gerekli paketler kuruluyor, lutfen bekleyin...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
)
if not exist "ETS2 Bak*m.lnk" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0kisayol_olustur.ps1" -SadeceKlasor >nul 2>&1
rem Uygulama kendi penceresinde, konsolsuz acilir. Hata olursa: data\ets2bakim.log
start "" ".venv\Scripts\pythonw.exe" -m ets2bakim %*
