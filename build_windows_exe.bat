@echo off
setlocal

where python >nul 2>nul
if errorlevel 1 (
  echo Python no esta instalado o no esta en PATH.
  pause
  exit /b 1
)

pushd %~dp0

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller pillow

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

python -m PyInstaller --noconfirm softwaredecarga.spec

if errorlevel 1 (
  echo Error generando el .exe.
  popd
  pause
  exit /b 1
)

echo.
echo EXE generado en:
echo %~dp0dist\SistemaDeCargas.exe
echo.
echo Copia junto al .exe cualquier archivo de respaldo que quieras distribuir.

popd
endlocal
