@echo off
rem Oyun olmadan sanal kamyonla dener (zaman 4 kat hizli). Demo verisi data_demo klasorune yazilir.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" -m ets2bakim --demo --hiz 4
