# Operación

[English](../operations.md) · **Español**

## Comandos habituales

```bash
docker compose ps                  # todos los servicios deben estar "healthy"
docker compose logs -f backend     # también: worker, frontend, nginx, postgres
docker compose restart backend
docker compose down                # detener (los datos se conservan)
docker compose up -d               # iniciar
```

Los datos sobreviven a `docker compose down` y a la recreación de contenedores. **Nunca** ejecutes
`docker compose down -v` salvo que realmente quieras borrar los volúmenes de PostgreSQL y Redis.

## Actualizar

```bash
git pull
docker compose up -d --build
```

Las migraciones de base de datos se ejecutan solas (`alembic upgrade head`) cuando inicia el
backend. Sólo el backend las ejecuta; el worker espera a que el backend esté saludable. Haz un
respaldo antes.

Ver la migración aplicada:

```bash
docker compose exec backend alembic current
```

## Herramientas de línea de comandos

Se ejecutan dentro del contenedor backend. Si omites `--password`, la contraseña se pide sin
mostrarla, lo que además la mantiene fuera del historial de la terminal.

```bash
docker compose exec backend python -m app.cli list-users
docker compose exec backend python -m app.cli create-admin --username maria
docker compose exec backend python -m app.cli reset-password --username admin
docker compose exec backend python -m app.cli reset-password --username admin --activate   # además reactiva la cuenta
```

Usa `reset-password` si olvidas la contraseña del administrador o si cambiaste
`INITIAL_ADMIN_PASSWORD` después del primer arranque (esa variable sólo importa mientras no existan
usuarios).

## Pantallas y modo kiosco

1. En **Pantallas**, crea una pantalla y asígnale una playlist. Su URL es `/screen/<slug>`.
2. Abre esa URL en el navegador de la TV y activa la pantalla completa.
3. Configura el equipo para abrirla automáticamente al encender:
   - **Chromium / Chrome en Linux, Windows o mini PC**:
     `chromium --kiosk --noerrdialogs --disable-infobars --autoplay-policy=no-user-gesture-required http://IP-DEL-SERVIDOR/screen/principal`
   - **Raspberry Pi OS**: agrega el mismo comando al inicio automático del escritorio.
   - **Smart TV / Android TV**: usa un navegador kiosco con inicio automático (p. ej. Fully Kiosk
     Browser) y permite la reproducción automática.
4. Desactiva el ahorro de energía y el protector de pantalla de la TV.

Cada pantalla envía una señal de actividad cada 15 segundos; **Pantallas** muestra cuáles están en
línea. Si se corta la red, la TV sigue mostrando el último contenido que tenía y se reconecta sola.
Los cambios en playlists, marca, opciones de pantalla y actos destacados llegan en tiempo real.

## Respaldos

Desde la carpeta del proyecto en el servidor Docker (Linux, macOS o WSL):

```bash
bash scripts/backup.sh
```

El script detiene `backend` y `worker` por unos segundos (para que nada escriba mientras copia),
crea `backups/information-board-<fecha>/` con `database.dump`, `data.tar.gz` (se omite con
almacenamiento S3), `manifest.sha256` e `info.txt`, y vuelve a iniciar los servicios. Define
`BACKUP_KEEP` en `.env` para conservar sólo los N respaldos más recientes.

**`.env` no se incluye** porque contiene secretos: guarda una copia protegida por separado.

Prográmalo con cron, por ejemplo todas las noches a las 03:00:

```cron
0 3 * * * cd /opt/information-board && bash scripts/backup.sh >> backups/backup.log 2>&1
```

## Restaurar

```bash
bash scripts/restore.sh information-board-20260101T030000Z
```

El script verifica los checksums, pide escribir `yes`, detiene `backend` y `worker`, reemplaza la
base de datos, extrae los archivos y vuelve a iniciar los servicios. Prueba la restauración
periódicamente en otro equipo, no sólo durante un incidente real.

## Verificar una instalación

```bash
docker compose config --quiet                 # la configuración es válida
curl http://localhost/api/v1/health           # {"status":"ok","database":"ok","redis":"ok"}
docker compose exec -T backend python - < scripts/deployment_smoke.py
```

La prueba de humo inicia sesión con el administrador inicial (agrega `-e SMOKE_PASSWORD=...` si esa
contraseña cambió), revisa las rutas principales, crea una publicación y una playlist temporales,
verifica la reproducción en la primera pantalla y borra todo lo que creó.

Pruebas unitarias del backend dentro del contenedor:

```bash
docker compose run --rm --no-deps -v "$(pwd)/backend/tests:/app/tests:ro" backend sh -c "pip install -q moto[s3]==5.0.18 && python -m pytest -q"
```

Pruebas de navegador de extremo a extremo: ver [e2e/README.md](../../e2e/README.md).

## Cuando cambia la red

Con `PUBLIC_BASE_URL` vacío (el valor por defecto), los QR y enlaces compartidos se construyen con la
dirección con que cada equipo abrió la cartelera, incluido el puerto. Si el servidor recibe otra IP o
se cambia a otra red, **no hay que modificar `.env`**: una TV abierta en
`http://10.0.0.8/screen/principal` muestra un QR hacia `http://10.0.0.8/catalog/principal`.
**Configuración → Sistema** muestra la dirección en uso.

Las TV igual necesitan una dirección para abrir la cartelera. De más a menos estable:

1. **Un nombre en vez de una IP.** Crea un registro DNS en el router o en tu DNS local (por ejemplo
   `cartelera.lan`), o usa mDNS: en un servidor Linux ejecuta `sudo apt install avahi-daemon` y abre
   `http://<nombre-del-servidor>.local`. mDNS funciona en Windows 10+, macOS, iOS, la mayoría de los
   Linux de escritorio y Android reciente; algunas smart TV y Android antiguos no resuelven `.local`.
2. **Una reserva DHCP** en el router, para que el servidor reciba siempre la misma IP.
3. Si no, actualiza la URL de kiosco en cada TV cuando cambie la dirección.

Para restringir la administración sin atarla a una subred, usa `ALLOWED_NETWORKS=private`.

Define `PUBLIC_BASE_URL` con un valor fijo sólo cuando los enlaces deban usar siempre una dirección,
por ejemplo si las TV abren la cartelera con `localhost` en el mismo servidor, o detrás de un proxy
inverso que no reenvía el nombre original.

### Cambiar el puerto

```env
HTTP_PORT=8080
```

Luego `docker compose up -d`. La cartelera queda en `http://SERVIDOR:8080` y los QR incluyen el
puerto automáticamente. Actualiza las URL de kiosco en las TV.

## HTTPS

La plataforma sirve HTTP dentro de la red local. Para exponerla hacia afuera, ponla detrás de un
proxy inverso con certificado (Caddy, Traefik, nginx Proxy Manager, Cloudflare Tunnel...). Los
enlaces pasan a `https://` automáticamente si el proxy reenvía los encabezados `Host` y
`X-Forwarded-Proto` (la mayoría lo hace por defecto); si no, define
`PUBLIC_BASE_URL=https://cartelera.ejemplo.cl`. Considera `ALLOWED_NETWORKS=private` para mantener la
administración limitada a tus redes internas.

## Solución de problemas

| Síntoma | Qué revisar |
| --- | --- |
| El sitio no abre | `docker compose ps`, el firewall del servidor y que `HTTP_PORT` no esté ocupado por otro programa. |
| El backend se detiene al iniciar | `docker compose logs backend`. "Refusing to start" lista las variables que siguen con valores de ejemplo. La otra causa habitual es una contraseña distinta entre `POSTGRES_PASSWORD` y `DATABASE_URL`. |
| `Permission denied` al escribir en `/data` | La carpeta de datos debe pertenecer a `APP_UID:APP_GID` (ver [almacenamiento](almacenamiento.md#permisos-opciones-a-c)). |
| El volumen del NAS no monta | Instala `cifs-utils` / `nfs-common` en el servidor, revisa el nombre de la carpeta, credenciales y permisos del export, y recrea los volúmenes después de cambiar `NAS_*`. |
| Errores de S3 en los logs | Revisa bucket, región, endpoint, permisos de la clave y `S3_FORCE_PATH_STYLE`. **Configuración → Sistema** muestra el bucket configurado. |
| Las subidas fallan con "413" | Aumenta `NGINX_MAX_BODY_SIZE` y el `MAX_*_SIZE_MB` correspondiente. |
| Un documento queda "Procesando" | `docker compose logs worker`; el worker debe estar saludable. Las presentaciones muy grandes pueden tardar unos minutos. |
| Una pantalla aparece desconectada | Mantén la URL abierta en la TV y verifica que todavía alcance el servidor (ver [cuando cambia la red](#cuando-cambia-la-red)). |
| No acepta el inicio de sesión | Los valores `INITIAL_ADMIN_*` sólo aplican al primer arranque. Usa `python -m app.cli reset-password`. Demasiados intentos bloquean esa IP durante `LOGIN_WINDOW_SECONDS`. |
| Los QR no abren en los teléfonos | Los QR usan la dirección con que se abrió la TV: abre la pantalla con la dirección o el nombre del servidor en la red, no `localhost` (o define un `PUBLIC_BASE_URL` fijo). El teléfono debe estar en una red que llegue al servidor. **Configuración → Sistema** avisa cuando la dirección es `localhost`. |
| Hora incorrecta en TV o programación | Define la zona horaria en **Configuración → Marca** (y `TZ` en `.env` para los contenedores). |
| No encuentra la dirección de un acto destacado | Revisa `GEOCODING_ENABLED`, el acceso a Internet del servidor (o tu propio `GEOCODE_URL`) y `GEOCODE_COUNTRY_CODES`. |
