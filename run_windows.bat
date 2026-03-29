@echo off
setlocal

where python >nul 2>nul
if errorlevel 1 (
  echo Python no esta instalado. Descargalo desde https://www.python.org/downloads/
  pause
  exit /b 1
)

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python camiones_gui.py

endlocal
