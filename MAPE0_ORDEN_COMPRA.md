# Mapeo Orden de Compra

## Archivo base revisado

- Plantilla: `ORDEN DE COMPRA.xlsx`

## Conclusion

La plantilla del cliente no corresponde al documento actual de cargas. Hoy el sistema genera un recibo/orden operativa de carga. La plantilla Excel es una orden de compra administrativa con proveedor, condiciones y detalle economico por items.

La recomendacion tecnica es mantener dos documentos distintos:

- `Recibo de carga`: el documento operativo actual.
- `Orden de compra`: un nuevo documento administrativo basado en la plantilla del cliente.

Intentar forzar la orden de compra sobre la tabla `cargas` va a mezclar dos procesos de negocio distintos.

## Mapeo campo por campo

| Plantilla Excel | Existe hoy | Fuente actual | Observacion |
|---|---|---|---|
| FECHA | Parcial | `fecha_carga` o fecha de impresion | Falta definir cual usa el cliente |
| ORDEN DE COMPRA No. | Parcial | `orden` | Hoy el consecutivo es de carga, no de compra |
| SOLICITADO POR | No | Ninguna | Requiere nuevo campo o relacion con usuarios |
| CONDICIONES DE ENTREGA | No | Ninguna | Requiere nuevo campo |
| DATOS DE PROVEEDOR / Nombre | No | Ninguna | Requiere catalogo de proveedores |
| DATOS DE PROVEEDOR / Nit | Parcial | `config.nit` existe pero es de la empresa propia | No sirve para proveedor |
| DATOS DE PROVEEDOR / Telefono | Parcial | `config.telefono` existe pero es de la empresa propia | No sirve para proveedor |
| DATOS DE PROVEEDOR / Contacto | No | Ninguna | Requiere campo de proveedor |
| CONDICIONES COMERCIALES | No | Ninguna | Requiere nuevo campo |
| CANT | No | Ninguna | Requiere items |
| DESCRIPCION | Parcial | `tipo de carga`, origen/destino, peso | No alcanza para detalle de compra |
| VALOR UNITARIO | No | Ninguna | Requiere items/precios |
| VALOR TOTAL por item | No | Ninguna | Requiere calculo por item |
| SUBTOTAL | No | Ninguna | Requiere calculo |
| TOTAL | No | Ninguna | Requiere calculo |
| REVISADO Y APROBADO POR | No | Ninguna | Requiere nuevo campo |

## Datos que hoy si tiene el sistema

Desde `cargas`, `conductores`, `vehiculos`, `tipos_carga`, `ciudades`, `bodegas`, `config`:

- `orden`
- `fecha_carga`
- `fecha_descarga`
- `placa`
- `conductor`
- `cedula del conductor`
- `tipo de carga`
- `peso`
- `origen`
- `destino`
- `bodega origen`
- `bodega destino`
- datos propios de empresa: `nit`, `direccion`, `telefono`, `logo`, `nota_pie`

Estos datos sirven para el recibo actual, pero no para replicar exactamente la orden del Excel.

## Propuesta minima de modelo

### 1. Nueva tabla `proveedores`

Campos sugeridos:

- `id`
- `nombre`
- `nit`
- `telefono`
- `contacto`
- `direccion`
- `activo`

### 2. Nueva tabla `ordenes_compra`

Campos sugeridos:

- `id`
- `numero`
- `fecha`
- `solicitado_por`
- `proveedor_id`
- `condiciones_entrega`
- `condiciones_comerciales`
- `revisado_aprobado_por`
- `observaciones`
- `created_by`
- `created_at`
- `updated_at`

### 3. Nueva tabla `orden_compra_items`

Campos sugeridos:

- `id`
- `orden_compra_id`
- `cantidad`
- `descripcion`
- `valor_unitario`
- `valor_total`

`valor_total` puede guardarse o calcularse como `cantidad * valor_unitario`.

## Propuesta de interfaz

- Nueva pestana: `Orden de compra`
- Formulario superior:
  `fecha`, `numero`, `solicitado_por`, `proveedor`, `condiciones_entrega`, `condiciones_comerciales`, `revisado_aprobado_por`
- Subtabla de items:
  `cantidad`, `descripcion`, `valor_unitario`, `total`
- Botones:
  `Crear`, `Editar`, `Imprimir`, `PDF`

## Propuesta de impresion/PDF

- No reutilizar el diseno actual de recibo.
- Crear un generador PDF nuevo que replique la plantilla Excel:
  encabezado, bloques superiores, grilla de items, subtotal/total y firma.

## Decision recomendada

Implementar `orden de compra` como modulo separado de `cargas`.

Razon:

- `cargas` describe operacion logistica.
- `orden de compra` describe adquisicion/contratacion.
- Mezclarlas en la misma tabla va a complicar UI, reportes y mantenimiento.

## Si se quisiera reutilizar parte de cargas

Solo se podria reaprovechar de forma limitada:

- usar `orden` como base de consecutivo
- usar `users.nombre` para `solicitado_por` o `revisado_aprobado_por`
- usar `config` para datos de la empresa emisora

Pero aun asi siguen faltando proveedor e items, que son el nucleo de la plantilla.
