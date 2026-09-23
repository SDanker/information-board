# Configuración

[English](../configuration.md) · **Español**

Information Board tiene dos niveles de configuración:

1. **Configuración dentro de la aplicación** (página Configuración, sólo administradores): marca,
   nombres de páginas y comportamiento de las TV. Se guarda en la base de datos y se aplica al
   instante en todas las pantallas abiertas, sin reiniciar.
2. **El archivo `.env` del servidor**: infraestructura, seguridad y valores del primer arranque.
   Los cambios se aplican con `docker compose up -d` (los contenedores se recrean con los valores
   nuevos).

`python3 scripts/setup.py` crea `.env` de forma interactiva en inglés o español. `.env.example`
documenta todas las variables.

## 1. Configuración dentro de la aplicación

### Marca

| Opción | Notas |
| --- | --- |
| Nombre de la aplicación | Menú, inicio de sesión, TV, pestaña del navegador. Valor inicial: `APP_NAME`. |
| Nombre de la organización | Subtítulo opcional bajo el nombre y en páginas públicas. Valor inicial: `ORGANIZATION_NAME`. |
| Color principal | Botones, enlaces, menú activo y acentos. Valor inicial: `BRAND_PRIMARY_COLOR`. |
| Logo | PNG, JPG, WEBP o GIF de hasta `MAX_LOGO_SIZE_MB`. Se convierte a PNG de máximo 512 px. Se usa en el menú, inicio de sesión, TV, páginas públicas y como favicon. Sin logo se muestra un ícono neutro. |
| Idioma por defecto | `en` o `es`. Lo usan las TV y los visitantes que no han elegido idioma. Valor inicial: `DEFAULT_LANGUAGE`. |
| Formato de fecha (locale) | Código BCP 47 como `es-CL`, `es-MX`, `en-US`, `en-GB`. Vacío = `en-US` o `es-ES`. Valor inicial: `DATE_LOCALE`. |
| Zona horaria | Nombre IANA que usan la vigencia de las playlists y los relojes. Valor inicial: `TZ`. |
| Titular y mensaje del inicio de sesión | Textos del lado izquierdo del inicio de sesión. Vacío = texto por defecto en cada idioma. |
| Biblioteca pública | Activa o desactiva `/library`. Los catálogos que abren los QR siguen funcionando. |

**Restaurar valores** vuelve toda la personalización a los valores de `.env` (el logo se conserva).

### Nombres de páginas

Renombra cualquier página del menú: Panel, Pantallas, Publicaciones, Playlists, Biblioteca,
Programación, Usuarios, Auditoría y Configuración. Un nombre personalizado se muestra en todos los
idiomas; deja el campo vacío para usar el nombre por defecto traducido.

### Pantallas y TV

| Opción | Por defecto | Notas |
| --- | --- | --- |
| Segundos por defecto de cada elemento | 15 | Se usa cuando un elemento no tiene duración propia. |
| Segundos mínimos por página o diapositiva | 4 | Los documentos y presentaciones de varias páginas siguen en pantalla hasta mostrar todas. Cada página puede tener su propia duración. |
| Segundos por foto o mapa de acto destacado | 7 | Los videos de los actos destacados siempre se reproducen completos. |
| Filas por página en planillas | 14 | Las tablas grandes se dividen en varias páginas. |
| Dirección por defecto del calendario (ICS) | vacío | Se rellena al crear una publicación de tipo Calendario, para que cada instalación use su propio calendario. Valor inicial: `DEFAULT_CALENDAR_ICS_URL`. |
| Duración por defecto de una publicación (días) | 7 | Las publicaciones nuevas comienzan al crearlas y terminan después de esta cantidad de días. 0 = sin término. Valor inicial: `DEFAULT_PUBLICATION_DAYS`. |
| Mostrar el reloj / reloj de 24 horas | sí / sí | |
| Mostrar el mapa en actos destacados | sí | |
| Texto del pie en la TV | vacío | Reemplaza la ruta de la pantalla abajo a la izquierda. |
| Código QR: mostrar, posición, mensaje | sí, abajo a la derecha | El QR abre `/catalog/<slug>` con todos los elementos de la playlist de la pantalla. |

### Calendarios compartidos

Una publicación de tipo **Calendario** muestra en las pantallas un calendario compartido, por
mes, semana o día:

1. Publica el calendario en tu proveedor y copia la dirección que termina en `.ics`:
   - **Outlook / Microsoft 365**: Calendario → Configuración → Calendarios compartidos →
     Publicar un calendario. Elige "Puede ver todos los detalles" para mostrar los títulos de
     los eventos y copia el enlace **ICS** (el enlace HTML es la página web de Outlook y la
     cartelera no puede dibujarlo).
   - **Google Calendar**: Configuración → el calendario → "Dirección secreta en formato iCal".
   - **Nextcloud**: Calendario → Compartir → publicar, y luego el enlace de suscripción (ICS).
2. En **Publicaciones → Nueva publicación → Calendario**, pega la dirección, elige la vista y
   usa **Probar enlace** para confirmar que se puede leer. Para tenerla siempre lista,
   guárdala en `DEFAULT_CALENDAR_ICS_URL` o en **Configuración → Pantallas y TV → Publicaciones**.
3. Agrega la publicación a una playlist, como cualquier otra.

Un calendario nunca muestra el código QR de la pantalla y no aparece en el catálogo ni en la
biblioteca pública: se lee en vivo desde su origen, así que no hay nada que descargar y el código
sólo taparía parte de la grilla. Cualquier otra publicación puede ocultar el código por su cuenta
con **Mostrar el código QR mientras se ve esta publicación** en su formulario.

El servidor descarga el calendario, expande los eventos que se repiten y convierte cada hora a
la zona horaria de la instalación, así que las TV no necesitan internet y la dirección nunca
aparece en pantalla. El resultado se guarda en caché por 10 minutos, y se conserva hasta una
semana: si el proveedor no responde, las pantallas siguen mostrando los últimos eventos
conocidos. Cualquiera con el enlace ICS puede ver el calendario, así que trátalo como una
contraseña y usa **Probar enlace** en vez de abrirlo en público.

### Período de publicación

Cada publicación, incluidos los actos destacados, tiene un período que se define al crearla y se
puede cambiar después con **Editar**:

- **Inicio / Término**: fecha y hora en la zona horaria de la instalación. Inicio vacío = de
  inmediato; término vacío = sin fecha de término. Las publicaciones nuevas vienen con
  *ahora* → *ahora + duración por defecto*, y hay botones rápidos de 1, 7, 14 o 30 días.
- **Días**: opcionalmente, mostrarla sólo algunos días de la semana dentro del período (sin
  selección = todos los días).

Fuera de su período la publicación no se muestra en ninguna pantalla, esté en las playlists que
esté, y desaparece de los catálogos de pantalla, la biblioteca pública y los enlaces compartidos.
Los elementos de una playlist pueden sumar sus propias fechas, días y horas. **Programación**
lista todas las publicaciones con su período y estado (publicada, programada, hoy no). Las
publicaciones creadas antes de esta opción no tienen límites, así que nada de lo que ya estaba en
pantalla desaparece.

Un acto destacado que se está transmitiendo permanece en todas las pantallas hasta que detengas la
transmisión, sin importar su período.

### Publicaciones archivadas

Cuando una publicación llega a su fecha y hora de término se **archiva** en menos de un minuto:

- Sale de todas las playlists y deja de aparecer en las pantallas y en los catálogos de pantalla.
- Pasa al segmento **Archivadas** de **Publicaciones**, con un contador en la pestaña.
- Aparece en el segmento **Archivadas** de las páginas de descarga (`/library` y la página que abre
  el QR de una pantalla). Cada elemento se puede seguir descargando, y **Descargar todo (.zip)**
  reúne todas las publicaciones archivadas, una carpeta por cada una. Sólo se listan las que son
  *públicas en la red local*, y el segmento sigue el interruptor de la biblioteca pública.
- Los enlaces y códigos QR que ya existían siguen entregando el archivo.

**Restaurar** (en el segmento Archivadas) la publica de nuevo desde ahora con el período por
defecto, conservando los días de la semana que tenía. Restaurar no la devuelve a las playlists,
porque al archivarla se sacó de ellas: agrégala otra vez desde **Playlists** y ajusta el período con
**Editar**. Archivar a mano desde la API (`is_archived`) funciona igual. Los calendarios también se
archivan, pero no tienen nada que descargar.

### Selector de idioma

Cada persona puede cambiar entre inglés y español desde el menú, el inicio de sesión o las páginas
públicas. La elección se recuerda en ese navegador. Prioridad: la elección de la persona y luego el
idioma por defecto de la instalación.

## 2. El archivo `.env`

### Identidad (valores iniciales)

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `APP_NAME` | `Information Board` | Nombre inicial de la aplicación. |
| `ORGANIZATION_NAME` | vacío | Nombre inicial de la organización. |
| `BRAND_PRIMARY_COLOR` | `#2563eb` | Color principal inicial (`#rrggbb`). |
| `DEFAULT_LANGUAGE` | `en` | `en` o `es`. También define el idioma de la pantalla creada en el primer arranque y de los mensajes del servidor cuando el navegador no indica preferencia. |
| `DATE_LOCALE` | vacío | Locale inicial de fechas. |
| `TZ` | `UTC` | Zona horaria IANA de la aplicación y de los contenedores. Para Chile: `America/Santiago`. |

Son sólo valores iniciales: cuando un administrador guarda la Marca, mandan los valores guardados.
Usa **Restaurar valores** para volver a `.env`.

### Red

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `PUBLIC_BASE_URL` | vacío (automática) | Dirección que usan los QR y los enlaces compartidos. **Vacío = automática**: los enlaces usan la dirección con que cada TV, teléfono o computador abrió la cartelera (incluido el puerto), así que una IP o red nueva no requiere cambios. Define un valor fijo sólo para forzar una dirección, p. ej. `https://cartelera.ejemplo.cl` detrás de un proxy inverso. Ver [cuando cambia la red](operacion.md#cuando-cambia-la-red). |
| `HTTP_PORT` | `80` | Puerto que nginx publica en el servidor. |
| `ALLOWED_NETWORKS` | vacío | Redes que pueden usar la API de administración, separadas por coma. `private` permite todas las redes privadas (10.x, 172.16-31.x, 192.168.x, IPv6 privadas, localhost) y sigue funcionando si cambia la LAN; también sirven subredes específicas como `192.168.1.0/24`. Las pantallas (`/api/v1/public/*`), el estado y los WebSockets siempre son accesibles. Vacío = sin restricción. |
| `CORS_EXTRA_ORIGINS` | vacío | Orígenes adicionales de navegador que pueden llamar a la API, para integraciones propias. |

### Primer administrador y pantallas

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `INITIAL_ADMIN_USERNAME` | `admin` | Se crea sólo en el primer arranque, mientras no existan usuarios. |
| `INITIAL_ADMIN_PASSWORD` | valor de ejemplo | Al menos 8 caracteres. Obligatoria en producción. |
| `INITIAL_SCREENS` | vacío | Pares `slug:Nombre` separados por coma, p. ej. `principal:Pantalla Principal,pasillo:Pasillo`. Se crean sólo mientras no existan pantallas. Vacío = una pantalla `main` (`principal` en español). |

Cambiar estos valores después **no** modifica cuentas ni pantallas existentes. Para cambiar una
contraseña o recuperar el acceso usa la CLI (ver [operación](operacion.md#herramientas-de-línea-de-comandos)):

```bash
docker compose exec backend python -m app.cli reset-password --username admin
```

### Seguridad

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `APP_ENV` | `production` en `.env.example` | En `production` el backend no inicia mientras `SECRET_KEY`, `INITIAL_ADMIN_PASSWORD` o `DATABASE_URL` tengan valores de ejemplo o débiles. |
| `SECRET_KEY` | valor de ejemplo | Al menos 32 caracteres aleatorios. Firma las sesiones: cambiarla cierra la sesión de todos. |
| `ACCESS_TOKEN_MINUTES` | `480` | Duración de una sesión de administración. |
| `LOGIN_MAX_ATTEMPTS` | `10` | Intentos fallidos permitidos por dirección IP dentro de la ventana. |
| `LOGIN_WINDOW_SECONDS` | `300` | Duración de esa ventana. |

### Base de datos y caché

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | `information_board`, `information_board`, valor de ejemplo | Base PostgreSQL creada en el primer arranque. |
| `DATABASE_URL` | construida con lo anterior | Debe contener el mismo usuario y contraseña. |
| `REDIS_URL` | `redis://redis:6379/0` | Eventos en tiempo real y cola de procesamiento. |

La contraseña de PostgreSQL queda fija al crear el volumen de la base; cambiarla después en `.env`
requiere cambiarla también dentro de PostgreSQL (`ALTER USER ... PASSWORD ...`).

### Subidas

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `MAX_DOCUMENT_SIZE_MB` | `100` | Documentos, planillas y presentaciones. |
| `MAX_IMAGE_SIZE_MB` | `25` | Imágenes, incluidas las fotos de actos destacados. |
| `MAX_VIDEO_SIZE_MB` | `500` | Videos. |
| `MAX_LOGO_SIZE_MB` | `5` | Logo en Configuración. |
| `NGINX_MAX_BODY_SIZE` | `600m` | Tamaño máximo de petición que acepta nginx; mantenlo sobre el límite más grande. |

### Almacenamiento de archivos

`STORAGE_BACKEND` (`local` o `s3`), `BOARD_DATA_PATH`, `BOARD_BACKUPS_PATH`, `APP_UID`, `APP_GID`,
`BACKUP_KEEP` y las variables `NAS_*` y `S3_*` se explican en [almacenamiento.md](almacenamiento.md).

### Geocodificación de actos destacados

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `GEOCODING_ENABLED` | `true` | Activa o desactiva la búsqueda de direcciones. Sin ella los actos destacados funcionan igual, pero sin mapa. |
| `GEOCODE_URL` | Nominatim de OpenStreetMap | Cualquier endpoint `/search` compatible con Nominatim, p. ej. una instancia propia para redes sin Internet. |
| `GEOCODE_COUNTRY_CODES` | vacío | Códigos ISO de país que restringen resultados, p. ej. `cl` o `us,ca`. Vacío = todo el mundo. |
| `GEOCODE_USER_AGENT` | vacío | Identifica tu instalación (lo pide la política de uso de OpenStreetMap), p. ej. `information-board (ti@ejemplo.cl)`. |

## Aplicar cambios

```bash
docker compose up -d            # recrea los contenedores cuya configuración cambió
docker compose up -d --build    # también necesario al cambiar APP_UID/APP_GID o actualizar el código
```
