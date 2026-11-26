# Hotel Backend DIRCETUR

API de gestión hotelera con FastAPI, SQLAlchemy asíncrono, PostgreSQL y Alembic. Gestiona establecimientos, habitaciones, reservas, huéspedes, cobros y caja. Genera el reporte mensual DIRCETUR y el registro mensual de huéspedes en Excel.

## Inicio rápido

Se requiere Python 3.12 o superior y una instancia de PostgreSQL disponible. Ejecuta estos comandos de PowerShell desde la raíz del proyecto.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Crea en PostgreSQL la base que indique `DATABASE_URL`. La configuración de ejemplo usa `fastapi_starter`.

```sql
CREATE DATABASE fastapi_starter;
```

Edita `.env` y conserva el archivo fuera del control de versiones.

| Variable | Uso |
| --- | --- |
| `DATABASE_URL` | Conexión con el formato `postgresql+asyncpg://usuario:contraseña@localhost:5432/base`. |
| `JWT_SECRET_KEY` | Clave generada en el paso anterior, de al menos 32 caracteres. |
| `CORS_ORIGINS` | Lista JSON de los orígenes del frontend, por ejemplo `["http://localhost:5173"]`. |
| `DEBUG` | Usa `false` para este flujo. |
| `SMTP_*` | Configuración opcional para enviar códigos de recuperación de contraseña. |
| `CULQI_SECRET_KEY` | Llave privada del backend. Usa una llave `sk_test_…` para pruebas. |
| `CULQI_ALLOW_LIVE` | `false` por defecto. Junto con una llave `sk_live_…`, habilita cobros reales. |
| `RENIEC_API_URL` y `TOKEN_RENIEC` | URL HTTPS de Scrall y clave privada para consultar DNI desde el backend. |

```powershell
python -m alembic upgrade head
python -m scripts.create_superadmin
python -m uvicorn app.main:app --reload
```

Crea el superadministrador una sola vez. Su contraseña debe tener al menos 12 caracteres. Abre [Swagger](http://127.0.0.1:8000/docs) y usa **Authorize** para iniciar sesión. Los endpoints tienen títulos en español y el [esquema OpenAPI](http://127.0.0.1:8000/openapi.json) describe los cuerpos, filtros y respuestas.

Alembic carga los países y ubigeos de Perú, los tipos y categorías de habitación, los cinco pisos, los métodos de pago y los conceptos de caja. También sincroniza los permisos que declaran los routers. Después de actualizar el código, reinstala las dependencias y ejecuta `python -m alembic upgrade head` antes de arrancar la API. En un proyecto en uso, conserva tu `.env` y las migraciones existentes.

## Módulos y rutas

Las rutas de la tabla llevan el prefijo `/api/v1`. Los listados paginados admiten `page` y `page_size`. Los filtros disponibles por recurso aparecen en Swagger.

| Módulo | Rutas principales | Función |
| --- | --- | --- |
| Autenticación y usuarios | `/auth`, `/users`, `/users/me` | Registro, inicio y cierre de sesión, renovación de tokens, recuperación de contraseña y gestión de usuarios. |
| Perfiles y permisos | `/profiles`, `/permissions` | Catálogo y asignación de permisos a perfiles. |
| Ubigeo | `/ubigeo`, `/ubigeo/countries?search=pe` | Jerarquía de Perú y búsqueda de países por código o nombre. |
| Empresas | `/companies`, `/companies/{company_id}/branches` | Datos del establecimiento y sus sucursales. El distrito determina provincia y departamento. |
| Personas y clientes | `/persons`, `/persons/choices`, `/customers` | Personal y consulta de clientes. La confirmación de una reserva registra al cliente y aumenta su contador una sola vez. |
| Habitaciones | `/rooms`, `/rooms/types`, `/rooms/categories`, `/rooms/floors`, `/rooms/rates` | Inventario, tarifas, capacidad y fotos. Las fotos se convierten a WebP al subirse. |
| Reservas | `/reservations`, `/reservations/quotes`, `/reservations/{id}/payments` | Reservas, cotizaciones, acompañantes y resumen por método de pago. |
| Métodos de pago y Culqi | `/payment-methods`, `/culqi/charges` | Catálogo de métodos y cobros de Culqi por token. |
| Caja | `/tills`, `/tills/{till_id}/shifts`, `/tills/transfers` | Turnos, movimientos, arqueo, transferencias de efectivo y anulaciones. |
| Reportes | `/reports/months`, `/reports/dircetur`, `/reports/guest-register` | Descarga de los dos reportes mensuales en Excel. |
| Sitio web | `/website/choices`, `/website/media`, `/website/galleries`, `/website/descriptions`, `/website/complaints`, `/website/contacts` | Contenido público, galería y formularios. Los videos y PDF se publican con base64. Las bandejas de formularios requieren permisos. |
| Integraciones | `/integrations/email`, `/integrations/reniec` | Envío de correo con adjunto y consulta básica de DNI mediante Scrall. |

## Integraciones

- `POST /api/v1/integrations/email` requiere `integrations.send_email`. Envía `email`, `asunto` y `mensaje`. `archivo` es opcional y admite base64, con hasta 10 MiB una vez decodificado. El servidor usa la configuración `SMTP_*`.
- `POST /api/v1/integrations/reniec` requiere `integrations.lookup_dni`. Envía `{"dni": "12345678"}` como JSON. Los ocho dígitos deben viajar como texto para conservar ceros iniciales. La respuesta exitosa tiene solo `success` y `data`. Configura `TOKEN_RENIEC` en el `.env` del backend. [Consulta RENIEC básica de Scrall](https://www.scrall.net/apis/reniec_basico)

## Autenticación y permisos

- `POST /api/v1/auth/login` recibe `username` y `password` como datos de formulario. Usa el token de acceso como `Authorization: Bearer <token>`. El login y `GET /api/v1/users/me` devuelven `is_admin` y los códigos de permiso del perfil.
- El frontend puede usar códigos como `reservations.read` o `tills.transfer` para mostrar opciones. La autorización se verifica en la API. Los permisos nuevos se crean en el catálogo y se asignan explícitamente a los perfiles. El superadministrador tiene acceso completo.
- Para recuperar una contraseña, usa `POST /api/v1/auth/forgot-password` y `POST /api/v1/auth/reset-password`. El cambio autenticado usa `POST /api/v1/auth/change-password`. Las contraseñas nuevas requieren al menos 12 caracteres. Para el envío de códigos, configura `SMTP_HOST`, `SMTP_FROM_EMAIL` y las credenciales de tu proveedor. Los puertos 587 y 465 suelen requerir STARTTLS y TLS directo, respectivamente.

## Reservas, cobros y caja

Una reserva guarda la habitación, la tarifa, los datos del huésped y sus acompañantes. Envía fechas ISO 8601 con zona horaria cuando esté disponible. Las fechas y horas sin zona se interpretan como hora de Perú. Los teléfonos aceptan números locales peruanos o internacionales con prefijo y se guardan en formato E.164.

- Una reserva ordinaria empieza en `RESERVADO`. Un abono cambia el estado a `RESERVA CON PAGOS PARCIALES` y el pago total la deja en `CONFIRMADO`. Las reservas de cortesía usan `RESERVA SIN PAGOS`.
- Las reservas ordinarias impagas caducan a las 24 horas de su creación. El worker usa PostgreSQL `LISTEN/NOTIFY` para esperar hasta el próximo vencimiento. Si la API estuvo apagada, procesa los vencimientos pendientes al arrancar.
- `PATCH /api/v1/reservations/{id}/payment` recibe el **monto acumulado pagado**. `GET /api/v1/reservations/{id}/payments` agrupa los abonos por método e informa el monto histórico sin método identificado.
- Las aperturas, los cierres, los movimientos, las transferencias y las anulaciones de caja requieren `Idempotency-Key`. Envía montos positivos y distingue `INGRESO` de `EGRESO` con `direction`. El arqueo compara el efectivo esperado con el contado. Una transferencia registra ambos movimientos en una transacción y exige un turno abierto en cada caja.

### Códigos de descuento

`POST /api/v1/reservations/discount-codes` requiere `reservations.discount_codes_create`. Envía `room_type_id`, `start_date`, `end_date` y `discount_percentage` entre 0 y 100, con un valor mayor que cero. `is_active` es opcional y vale `true` por defecto. La respuesta incluye el UUID y un código único como `HT04258317`, disponible en `data.code` para mostrarlo en el popup.

Para aplicar el código a una reserva existente, usa `PATCH /api/v1/reservations/{id}/discount-code` con el permiso `reservations.discount_codes_apply` y el cuerpo `{"code": "HT04258317"}`. También puedes enviar `discount_code` al crear una reserva con detalle financiero o al convertir una cotización. La API comprueba el tipo de habitación, la vigencia inclusiva en hora de Perú y que la reserva esté pendiente, sin pagos ni descuentos previos. Aplica el porcentaje al total y actualiza el saldo. Un descuento que cubra todo el total deja la reserva en `RESERVA SIN PAGOS`.

El popup puede consultar `GET /api/v1/reservations/discount-codes` sin autenticarse. Devuelve los códigos activos y vigentes en `data.items`. Puedes filtrar por `room_type_id` y usar `page` y `page_size`.

### Cotizaciones de reserva

La API calcula `quoted_total` en soles multiplicando el precio de la tarifa vigente por las noches entre las fechas locales de entrada y salida. La tarifa debe estar activa y asignada a la habitación. El total queda guardado con la cotización. Para generar un precio antes de reservar, envía `room_id`, `rate_id`, `check_in`, `check_out` y `valid_until` como fecha y hora de vencimiento futura. La cotización por sí sola no bloquea la habitación.

| Ruta | Permiso | Uso |
| --- | --- | --- |
| `POST /api/v1/reservations/quotes` | `reservations.quotes_create` | Crear una cotización de al menos una noche. |
| `GET /api/v1/reservations/quotes` | `reservations.quotes_read` | Listar con `page` y `page_size`. |
| `GET /api/v1/reservations/quotes/{quote_id}` | `reservations.quotes_read` | Consultar importe, vigencia y reserva vinculada. |
| `POST /api/v1/reservations/quotes/{quote_id}/reservation` | `reservations.create` y `reservations.quotes_link` | Crear y vincular una reserva utilizando los datos del titular y sus acompañantes. |
| `PATCH /api/v1/reservations/quotes/{quote_id}/reservation` | `reservations.quotes_link` | Enviar `{"reservation_id": "<uuid>"}` para vincular una reserva existente a una cotización vigente. Deben coincidir habitación, tarifa y fechas. |

Para el botón **Crear reserva**, usa el `POST` con el ID de la cotización en la URL. Envía nombre, tipo y número de documento si corresponde, fecha de nacimiento, teléfono, correo, país, ciudad, región, distrito, dirección, motivo de viaje, restricciones alimentarias y género del titular. Si hay acompañantes, inclúyelos en `companions`. El backend toma la habitación, tarifa, fechas y total de la cotización, crea el detalle con saldo pendiente y vincula ambos registros en una transacción. Si se repite el `POST`, devuelve la reserva vinculada. El `PATCH` sirve cuando la reserva ya existe.

### Personal y asignaciones

`POST /api/v1/persons` y `PATCH /api/v1/persons/{person_id}` aceptan `employment_start_date`, `employment_end_date` y `branch_id`. Si omites la fecha de ingreso en un alta nueva, se usa la fecha actual de Perú. Deja la fecha de baja vacía mientras la persona siga trabajando.

Los cambios de sucursal, área, categoría o condición de permanente se registran con `assignment_effective_from`. Si omites esa fecha al editar, se usa la fecha actual de Perú o la fecha de ingreso si es posterior. Consulta el historial con `GET /api/v1/persons/{person_id}/assignments`. Para conservar a la persona en reportes anteriores, registra la baja con `employment_end_date`.

## Integración con Culqi

Las cuatro rutas requieren el token de acceso de la API en `Authorization: Bearer <token>` y el permiso indicado. Usa Culqi Checkout en el frontend para obtener el token de pago. La llave privada `CULQI_SECRET_KEY` se configura en el backend. El número de tarjeta y el CVV se ingresan en Checkout. [Documentación de cargos de Culqi](https://docs.culqi.com/es/documentacion/pagos-online/cargo-unico/cargos)

### Crear un cargo

`POST /api/v1/culqi/charges` requiere `culqi.charge` y el encabezado `Idempotency-Key`. Genera una clave nueva para cada intento de cobro y reutilízala con el mismo cuerpo si se pierde la respuesta o necesitas reintentar. Si la clave se reutiliza con datos distintos, la API devuelve `409`.

```json
{
  "reservation_id": "b9c2388e-ca64-4649-8d60-2d05419e1a07",
  "token": "tkn_test_ejemplo",
  "amount": "420.00",
  "device_id": "8019959c-fab1-49eb-bbbe-b846d308d8df"
}
```

| Campo | Qué envía el frontend |
| --- | --- |
| `reservation_id` | UUID de la reserva que se va a cobrar. |
| `token` | Token de Checkout, por ejemplo `tkn_test_…` para tarjeta o `ype_test_…` para Yape. Usa el mismo entorno que la llave privada. |
| `amount` | Importe de este abono en soles, positivo, con hasta dos decimales y dentro del saldo pendiente. Enviar `"420.00"` cobra S/ 420.00. El backend convierte el valor a céntimos para Culqi. |
| `device_id` | UUID opcional en el esquema del backend. Para el flujo de tarjeta con 3DS, genera este valor con `Culqi3DS.generateDevice()` y envíalo desde el primer intento. |

El backend obtiene el correo de la reserva y usa PEN como moneda. Lee `data.status` para saber el resultado. El HTTP `201` indica que la API respondió con un intento registrado.

| `data.status` | Qué significa |
| --- | --- |
| `SUCCEEDED` | Culqi confirmó el cargo capturado. La API actualizó el saldo de la reserva y guardó el ID de Culqi en `transaction_number`. |
| `REQUIRES_3DS` | El titular debe completar la autenticación con Culqi3DS. Luego se llama a `/authenticate`. |
| `DECLINED` | Culqi devolvió un rechazo que el backend pudo identificar. Se puede iniciar otro intento con un token y una clave nuevos. |
| `PROCESSING` | El cargo está en curso o su resultado es incierto. Consulta su estado y concilia el cargo si aparece en CulqiPanel. |

Guarda `data.id`, el UUID interno que se usa como `{charge_id}` en las siguientes rutas. `data.provider_charge_id` es el identificador de Culqi, con formato `chr_test_…` o `chr_live_…`, y puede estar vacío mientras el resultado no esté confirmado.

### Consultar el estado

`GET /api/v1/culqi/charges/{charge_id}` requiere `culqi.read`. Envía el UUID interno en la URL. Devuelve el último estado registrado por el backend, el importe y el ID de Culqi si ya se confirmó.

### Completar la autenticación 3DS

`POST /api/v1/culqi/charges/{charge_id}/authenticate` requiere `culqi.charge`. Para un cargo en `REQUIRES_3DS`, completa el desafío con Culqi3DS y envía el mismo `token` del primer intento. Copia el objeto `parameters3DS` que devuelve la librería dentro de `authentication`. El backend reutiliza el importe y el dispositivo originales. [Uso de Culqi3DS](https://docs.culqi.com/es/documentacion/culqi-3ds/v1/uso-libreria/)

| Campo dentro de `authentication` | Qué representa |
| --- | --- |
| `eci` | Indicador de comercio electrónico devuelto por el flujo de autenticación. |
| `xid` | Identificador de la transacción de autenticación. |
| `cavv` | Valor criptográfico generado durante la autenticación del titular. |
| `protocolVersion` | Versión de 3DS informada por Culqi, por ejemplo `2.1.0`. |
| `directoryServerTransactionId` | UUID de la transacción asignado por el servidor de directorio de 3DS. El backend lo requiere. |

```json
{
  "token": "tkn_test_ejemplo",
  "authentication": {
    "eci": "05",
    "xid": "<xid devuelto por Culqi3DS>",
    "cavv": "<cavv devuelto por Culqi3DS>",
    "protocolVersion": "2.1.0",
    "directoryServerTransactionId": "755f8c81-a4db-4c84-8b8c-23f6b0196cfd"
  }
}
```

### Conciliar un cargo de resultado incierto

`POST /api/v1/culqi/charges/{charge_id}/reconcile` requiere `culqi.reconcile`. Usa el UUID interno en la URL y envía el ID del cargo que encontraste en CulqiPanel.

```json
{
  "provider_charge_id": "chr_test_ejemplo"
}
```

La API consulta ese cargo directamente en Culqi. Solo registra el abono si verifica la captura, el importe, la moneda y la referencia al intento original. Repetir una conciliación exitosa con el mismo ID devuelve el resultado registrado.

## Reportes Excel

Selecciona el mes con `GET /api/v1/reports/months`. Las dos descargas requieren `month` y `year`.

| Reporte | Ejemplo |
| --- | --- |
| DIRCETUR de seis capítulos | `GET /api/v1/reports/dircetur?month=11&year=2026` |
| Registro mensual de huéspedes | `GET /api/v1/reports/guest-register?month=11&year=2026` |

El permiso `reports.export` habilita las opciones de mes y la descarga DIRCETUR. El registro de huéspedes requiere además `reports.guests_export` porque contiene datos personales.

El reporte DIRCETUR usa el establecimiento y el inventario actual. Para exportarlo, completa el baño y las plazas-cama de cada tipo de habitación ofertado. Las cifras de ocupación se estiman con reservas elegibles cuya fecha de entrada ya pasó. El sistema todavía no registra el ingreso efectivo. El registro mensual incluye a los acompañantes en filas separadas y cuenta las noches de habitación una vez por habitación y fecha.

Los archivos de [plantilla](app/modules/reports/templates/) forman parte del backend. La API los abre para generar una copia nueva por descarga. Los archivos generados en `reportes/` son ejemplos locales.

## Desarrollo y pruebas

Los módulos de `app/modules/` se registran por sus archivos `models.py` y `router.py`. En rutas protegidas, declara el permiso con `require_permissions(...)`. El catálogo recoge esos códigos durante `alembic upgrade head`.

```powershell
python -m alembic revision --autogenerate -m "describe el cambio"
python -m alembic upgrade head
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Antes de hacer commit, ejecuta las dos comprobaciones de Ruff que usa GitHub Actions. Para corregir imports y formato, ejecuta `python -m ruff check --fix .` y luego `python -m ruff format .`.

Revisa la migración autogenerada antes de aplicarla. Las pruebas usan SQLite en memoria por defecto. Para ejecutarlas con PostgreSQL, define `TEST_DATABASE_URL` en el entorno con una base exclusiva cuyo nombre termine en `_test`. GitHub Actions comprueba las migraciones y ejecuta la suite con PostgreSQL.
