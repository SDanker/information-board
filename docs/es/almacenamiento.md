# Almacenamiento de archivos

[English](../storage.md) · **Español**

Los originales subidos, las páginas convertidas, los videos procesados, el material de emergencias
y el logo se pueden guardar de cuatro formas. La base de datos siempre queda en el volumen Docker
`postgres_data`.

| Opción | Ideal para | Variables |
| --- | --- | --- |
| A. Carpeta en el servidor | Un servidor, lo más simple | `STORAGE_BACKEND=local`, `BOARD_DATA_PATH` |
| B. NAS montado por el servidor | Ya montas el NAS en `/etc/fstab` | `STORAGE_BACKEND=local`, `BOARD_DATA_PATH=/mnt/nas/...` |
| C. NAS montado por Docker (SMB o NFS) | NAS sin tocar los montajes del servidor | `STORAGE_BACKEND=local`, `NAS_*`, `COMPOSE_FILE` |
| D. Almacenamiento de objetos compatible con S3 | Almacenamiento en Internet o un servidor de objetos propio | `STORAGE_BACKEND=s3`, `S3_*` |

`python3 scripts/setup.py` puede configurar cualquiera de ellas. Si cambias el almacenamiento de
una instalación que ya tiene contenido, primero copia los archivos existentes a la nueva ubicación
(ver [Mover archivos existentes](#mover-archivos-existentes)).

## Permisos (opciones A-C)

El backend y el worker corren con un usuario sin privilegios cuyo uid/gid son `APP_UID`/`APP_GID`
(por defecto `1000`). Ese usuario debe poder leer y escribir las carpetas de datos y respaldos:

```bash
mkdir -p data backups
sudo chown -R 1000:1000 data backups     # o los valores de APP_UID:APP_GID
```

Si cambias `APP_UID` o `APP_GID`, reconstruye las imágenes: `docker compose up -d --build`.

## A. Carpeta en el servidor

La opción por defecto. Los archivos van a `./data` y los respaldos a `./backups` dentro del proyecto:

```env
STORAGE_BACKEND=local
BOARD_DATA_PATH=./data
BOARD_BACKUPS_PATH=./backups
```

También sirve cualquier ruta absoluta, p. ej. un segundo disco: `BOARD_DATA_PATH=/srv/board/data`.

## B. NAS montado por el servidor

Monta la carpeta compartida en el servidor (SMB/CIFS o NFS) para que sobreviva a los reinicios y
apunta las rutas a ella. Ejemplo para SMB en `/etc/fstab`:

```
//192.168.1.20/cartelera  /mnt/nas/cartelera  cifs  credentials=/root/.nas-credentials,uid=1000,gid=1000,vers=3.0,_netdev,nofail  0  0
```

```env
STORAGE_BACKEND=local
BOARD_DATA_PATH=/mnt/nas/cartelera/data
BOARD_BACKUPS_PATH=/mnt/nas/cartelera/backups
```

Inicia la plataforma cuando el montaje esté disponible (`_netdev` lo retrasa hasta que haya red).

## C. NAS montado por Docker

Docker monta la carpeta compartida mediante un volumen con nombre definido en un archivo override.
Dentro de la carpeta compartida crea dos carpetas: `data` y `backups`.

### SMB / CIFS (Windows, Synology, QNAP, TrueNAS, UniFi...)

Instala el cliente en el servidor: `sudo apt install cifs-utils`.

```env
STORAGE_BACKEND=local
NAS_HOST=192.168.1.20
NAS_SHARE=cartelera
NAS_USERNAME=board
NAS_PASSWORD=una-contraseña-sin-comas
NAS_SMB_VERSION=3.0
COMPOSE_PATH_SEPARATOR=:
COMPOSE_FILE=docker-compose.yml:docker-compose.nas-smb.yml
```

### NFS (Synology, QNAP, TrueNAS, Linux)

Instala el cliente en el servidor: `sudo apt install nfs-common`. Autoriza la IP del servidor en el
export del NAS, con escritura para `APP_UID`/`APP_GID` (o una regla de squash que los mapee).

```env
STORAGE_BACKEND=local
NAS_HOST=192.168.1.20
NAS_NFS_EXPORT=/volume1/cartelera
COMPOSE_PATH_SEPARATOR=:
COMPOSE_FILE=docker-compose.yml:docker-compose.nas-nfs.yml
```

Luego `docker compose up -d`. Con `COMPOSE_FILE` en `.env`, todos los comandos `docker compose`
(incluidos los scripts de respaldo) usan el override automáticamente.

Notas:

- El volumen de Docker guarda las opciones de montaje al crearse. Después de cambiar `NAS_*`, borra
  los volúmenes antiguos para que se recreen: `docker compose down` y luego
  `docker volume rm information-board_board_data information-board_board_backups`
  (sólo elimina la definición del montaje en Docker, no los archivos del NAS).
- `NAS_PASSWORD` no puede contener comas (las opciones de montaje se separan con comas).

## D. Almacenamiento compatible con S3

Funciona con AWS S3, Cloudflare R2, Backblaze B2, Wasabi, DigitalOcean Spaces, Scaleway, MinIO,
Garage, SeaweedFS y cualquier otro servicio compatible con S3.

1. Crea un bucket **privado** (no necesita acceso público).
2. Crea una clave de acceso limitada a ese bucket con permiso para listar, leer, escribir y borrar
   objetos (`s3:ListBucket`, `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`).
3. Configura `.env`:

```env
STORAGE_BACKEND=s3
S3_BUCKET=mi-cartelera
S3_REGION=us-east-1
S3_ENDPOINT_URL=                 # vacío para AWS; el endpoint del proveedor en otros casos
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_PREFIX=                       # carpeta opcional, p. ej. oficina-1/
S3_FORCE_PATH_STYLE=false        # true para MinIO, Garage, SeaweedFS
S3_SERVE_MODE=proxy
S3_PRESIGN_SECONDS=3600
```

Ejemplos de `S3_ENDPOINT_URL` por proveedor:

| Proveedor | Endpoint | Región |
| --- | --- | --- |
| AWS S3 | vacío | la región del bucket, p. ej. `sa-east-1` |
| Cloudflare R2 | `https://<account-id>.r2.cloudflarestorage.com` | `auto` |
| Backblaze B2 | `https://s3.<region>.backblazeb2.com` | p. ej. `us-west-004` |
| Wasabi | `https://s3.<region>.wasabisys.com` | p. ej. `eu-central-1` |
| MinIO (propio) | `http://192.168.1.30:9000` | `us-east-1`, con `S3_FORCE_PATH_STYLE=true` |

### Modo de entrega

- `proxy` (por defecto): las TV y teléfonos descargan los archivos a través del servidor de
  Information Board, que los lee del bucket. Funciona aunque las TV no tengan Internet y mantiene el
  bucket totalmente privado. Admite adelantar videos (HTTP Range).
- `redirect`: el servidor responde con un enlace firmado válido por `S3_PRESIGN_SECONDS` y el
  navegador descarga directo desde el bucket. Menos carga para el servidor, pero cada TV y teléfono
  necesita acceso al endpoint del bucket, y el bucket puede requerir reglas CORS que permitan `GET`
  desde la dirección de la cartelera.

El worker de videos y documentos descarga los originales a una carpeta temporal, los convierte y
sube los resultados, así que las conversiones funcionan igual con S3.

### Respaldos con S3

`scripts/backup.sh` respalda la base de datos pero no copia el bucket. Activa el versionado o la
replicación de objetos en tu proveedor, o copia el bucket con una herramienta como `rclone`.

## Mover archivos existentes

La estructura de carpetas es la misma en todas las opciones, así que mover es copiar el árbol:

```bash
docker compose stop backend worker
# carpeta local -> NAS u otra carpeta
rsync -a ./data/ /mnt/nas/cartelera/data/
# carpeta local -> S3 (con AWS CLI o rclone), respetando S3_PREFIX si lo usas
aws s3 sync ./data/ s3://mi-cartelera/ --endpoint-url "$S3_ENDPOINT_URL"
# actualiza .env y luego
docker compose up -d
```

**Configuración → Sistema** muestra el almacenamiento en uso cuando la aplicación está funcionando.
