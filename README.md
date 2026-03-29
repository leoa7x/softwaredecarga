# Sistema de Cargas

Aplicación de escritorio (Python + Tkinter + SQLite) para registrar cargas de camiones, administrar catálogos y generar reportes.

## Ejecutar

```bash
python3 camiones_gui.py
```

## Login

Usuarios por defecto:

- admin / admin123 (administrador)
- operador / operador123 (operador)

Los usuarios ahora incluyen: nombre y cédula.

## Dependencias opcionales

- Calendarios: `pip install tkcalendar`
- Exportar PDF: `pip install reportlab`
- Exportar Excel: `pip install openpyxl`
- QR en PDF: `pip install qrcode[pil]`

## Archivos

- `camiones_gui.py`: app principal
- `camiones.db`: base de datos local (no se sube a GitHub)
- `camion-de-carga.png`: logo opcional

## Pruebas

```bash
pytest -q
```

## E2E (GUI)

Mac (pyautogui):

```bash
pip install pyautogui
python3 e2e/run_login_flow.py
```

## Ejecutar en Windows (sin .exe)

1) Instala Python desde https://www.python.org/downloads/ (marca "Add Python to PATH").
2) Descomprime el proyecto.
3) Ejecuta `run_windows.bat`.

## Empaquetar a .exe en Windows

1) Abre `CMD` o `PowerShell` en esta carpeta.
2) Ejecuta `build_windows_exe.bat`.
3) El ejecutable quedará en `dist/SistemaDeCargas.exe`.

Notas:

- El `.exe` se construye con PyInstaller.
- Se incluye `camion-de-carga.png` dentro del paquete.
- La base de datos `camiones.db` no se embebe.
- En el `.exe` para Windows, la base se crea por defecto en `C:\SistemaDeCargas\camiones.db`.
- Los backups se guardan en `C:\SistemaDeCargas\backups`.
- Esto permite que varias sesiones de Terminal Server usen la misma base local del servidor.
- Si necesitas otra ubicacion, puedes definir `CAMIONES_DB_PATH` o `CAMIONES_DATA_DIR`.
