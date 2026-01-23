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
