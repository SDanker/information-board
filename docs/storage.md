# File storage

**English** · [Español](es/almacenamiento.md)

Uploaded originals, converted pages, video renditions, emergency media and the logo can be stored
in four ways. The database always stays in the `postgres_data` Docker volume.

| Option | Best for | Settings |
| --- | --- | --- |
| A. Folder on the server | Single server, simplest setup | `STORAGE_BACKEND=local`, `BOARD_DATA_PATH` |
| B. NAS mounted by the host | You already mount the NAS in `/etc/fstab` | `STORAGE_BACKEND=local`, `BOARD_DATA_PATH=/mnt/nas/...` |
| C. NAS mounted by Docker (SMB or NFS) | NAS without touching the host's mounts | `STORAGE_BACKEND=local`, `NAS_*`, `COMPOSE_FILE` |
| D. S3-compatible object storage | Internet storage or a self-hosted object server | `STORAGE_BACKEND=s3`, `S3_*` |

`python3 scripts/setup.py` can configure any of them. After changing the storage of an installation
that already has content, copy the existing files to the new location first (see
[Moving existing files](#moving-existing-files)).

## Permissions (options A-C)

The backend and worker run as a non-root user whose uid/gid are `APP_UID`/`APP_GID` (default
`1000`). That user must be able to read and write the data and backups folders:

```bash
mkdir -p data backups
sudo chown -R 1000:1000 data backups     # or the values of APP_UID:APP_GID
```

If you change `APP_UID` or `APP_GID`, rebuild the images: `docker compose up -d --build`.

## A. Folder on the server

The default. Files go to `./data` and backups to `./backups` inside the project folder:

```env
STORAGE_BACKEND=local
BOARD_DATA_PATH=./data
BOARD_BACKUPS_PATH=./backups
```

Any absolute path works too, e.g. a second disk: `BOARD_DATA_PATH=/srv/board/data`.

## B. NAS mounted by the host

Mount the share on the host (SMB/CIFS or NFS) so it survives reboots, then point the paths at it.
Example for an SMB share in `/etc/fstab`:

```
//192.168.1.20/signage  /mnt/nas/signage  cifs  credentials=/root/.nas-credentials,uid=1000,gid=1000,vers=3.0,_netdev,nofail  0  0
```

```env
STORAGE_BACKEND=local
BOARD_DATA_PATH=/mnt/nas/signage/data
BOARD_BACKUPS_PATH=/mnt/nas/signage/backups
```

Start the stack after the mount is available (`_netdev` delays it until the network is up).

## C. NAS mounted by Docker

Docker mounts the share itself through a named volume, defined in an override file. Inside the
share create two folders, `data` and `backups`.

### SMB / CIFS (Windows, Synology, QNAP, TrueNAS, UniFi...)

Install the client on the host: `sudo apt install cifs-utils`.

```env
STORAGE_BACKEND=local
NAS_HOST=192.168.1.20
NAS_SHARE=signage
NAS_USERNAME=board
NAS_PASSWORD=a-password-without-commas
NAS_SMB_VERSION=3.0
COMPOSE_PATH_SEPARATOR=:
COMPOSE_FILE=docker-compose.yml:docker-compose.nas-smb.yml
```

### NFS (Synology, QNAP, TrueNAS, Linux)

Install the client on the host: `sudo apt install nfs-common`. Allow the server's IP in the NAS
export, with write access for `APP_UID`/`APP_GID` (or a squash rule mapping to them).

```env
STORAGE_BACKEND=local
NAS_HOST=192.168.1.20
NAS_NFS_EXPORT=/volume1/signage
COMPOSE_PATH_SEPARATOR=:
COMPOSE_FILE=docker-compose.yml:docker-compose.nas-nfs.yml
```

Then `docker compose up -d`. With `COMPOSE_FILE` in `.env`, every `docker compose` command
(including the backup scripts) uses the override automatically.

Notes:

- The Docker volume stores the mount options when it is created. After changing `NAS_*`, remove the
  old volumes so they are recreated: `docker compose down` then
  `docker volume rm information-board_board_data information-board_board_backups`
  (this only removes Docker's mount definition, not the files on the NAS).
- `NAS_PASSWORD` cannot contain commas (mount options are comma-separated).

## D. S3-compatible object storage

Works with AWS S3, Cloudflare R2, Backblaze B2, Wasabi, DigitalOcean Spaces, Scaleway, MinIO,
Garage, SeaweedFS and any other S3-compatible service.

1. Create a **private** bucket (no public access is needed).
2. Create an access key limited to that bucket with permission to list, read, write and delete
   objects (`s3:ListBucket`, `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`).
3. Configure `.env`:

```env
STORAGE_BACKEND=s3
S3_BUCKET=my-signage
S3_REGION=us-east-1
S3_ENDPOINT_URL=                 # empty for AWS; the provider's endpoint otherwise
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_PREFIX=                       # optional folder, e.g. office-1/
S3_FORCE_PATH_STYLE=false        # true for MinIO, Garage, SeaweedFS
S3_SERVE_MODE=proxy
S3_PRESIGN_SECONDS=3600
```

Provider examples for `S3_ENDPOINT_URL`:

| Provider | Endpoint | Region |
| --- | --- | --- |
| AWS S3 | empty | your bucket's region, e.g. `us-east-1` |
| Cloudflare R2 | `https://<account-id>.r2.cloudflarestorage.com` | `auto` |
| Backblaze B2 | `https://s3.<region>.backblazeb2.com` | e.g. `us-west-004` |
| Wasabi | `https://s3.<region>.wasabisys.com` | e.g. `eu-central-1` |
| MinIO (self-hosted) | `http://192.168.1.30:9000` | `us-east-1`, with `S3_FORCE_PATH_STYLE=true` |

### Serve mode

- `proxy` (default): TVs and phones download files through the Information Board server, which
  reads them from the bucket. Works when the TVs have no Internet access and keeps the bucket
  completely private. Video seeking (HTTP Range) is supported.
- `redirect`: the server answers with a signed link valid for `S3_PRESIGN_SECONDS` and the browser
  downloads directly from the bucket. Less load on the server, but every TV and phone needs access
  to the bucket's endpoint, and the bucket may need CORS rules allowing `GET` from the board's address.

The video and document worker downloads originals to a temporary folder, converts them and uploads
the results, so conversions work the same with S3.

### Backups with S3

`scripts/backup.sh` dumps the database but does not copy the bucket. Enable object versioning or
replication at your provider, or copy the bucket with a tool such as `rclone`.

## Moving existing files

The storage layout is the same everywhere, so moving is a plain copy of the folder tree:

```bash
docker compose stop backend worker
# local folder -> NAS or another folder
rsync -a ./data/ /mnt/nas/signage/data/
# local folder -> S3 (with the AWS CLI or rclone), honoring S3_PREFIX if set
aws s3 sync ./data/ s3://my-signage/ --endpoint-url "$S3_ENDPOINT_URL"
# update .env, then
docker compose up -d
```

**Settings → System** shows the storage in use once the application is running.
