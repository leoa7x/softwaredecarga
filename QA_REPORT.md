# QA Report — Sistema de Cargas

## Alcance
Pruebas manuales funcionales y pruebas automatizadas de lógica/DB.

## Resumen
- Flujos principales cubiertos: login, catálogos, cargas, órdenes, PDF, usuarios.
- Automatizado: validación de base de datos, usuarios y órdenes.

## Entorno
- Python 3.x
- SQLite local
- Dependencias opcionales: tkcalendar, reportlab, openpyxl, qrcode

## Checklist manual (funcional)
- Login y roles (admin/operador)
- Catálogos (CRUD)
- Registro de carga con orden automática
- Estadísticas y alertas
- Órdenes y filtros
- PDF con QR, logo y firma
- Configuración (logo, nota de pie)
- Usuarios (crear, actualizar, desactivar, reactivar)

## Resultados esperados
- No se permite editar/borrar con rol operador
- PDF en media carta horizontal con QR y firmas
- Orden se genera automáticamente
- Fechas inválidas muestran error

## Pruebas automatizadas (pytest)
- Inicialización de DB y usuarios por defecto
- Autenticación
- CRUD de usuarios
- Inserción de carga con generación de orden
- Filtrado de cargas

## Ejecución de pruebas
```bash
pytest -q
```

## Observaciones
- Pruebas GUI E2E no incluidas (pendiente si se requiere).
