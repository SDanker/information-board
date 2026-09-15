# Operations

**English** · [Español](es/operacion.md)

## Everyday commands

```bash
docker compose ps                  # every service should be "healthy"
docker compose logs -f backend     # also: worker, frontend, nginx, postgres
docker compose restart backend
docker compose down                # stop (data is kept)
docker compose up -d               # start
```

Data survives `docker compose down` and container re-creation. **Never** run
`docker compose down -v` unless you really want to delete the PostgreSQL and Redis volumes.

## Updating

```bash
git pull
docker compose up -d --build
```

Database migrations run automatically (`alembic upgrade head`) when the backend starts. Only the
backend runs them; the worker waits until the backend is healthy. Make a backup first.

Check the applied migration:

```bash
docker compose exec backend alembic current
```

## Command-line tools

Run inside the backend container. When `--password` is omitted the password is asked without echo,
which also keeps it out of the shell history.

```bash
docker compose exec backend python -m app.cli list-users
docker compose exec backend python -m app.cli create-admin --username maria
docker compose exec backend python -m app.cli reset-password --username admin
docker compose exec backend python -m app.cli reset-password --username admin --activate   # also re-enable the account
```

Use `reset-password` if you forget the administrator password or if you changed
`INITIAL_ADMIN_PASSWORD` after the first start (that variable only matters while there are no users).

## Screens and kiosk mode

1. In **Screens**, create a screen and assign a playlist. Its URL is `/screen/<slug>`.
2. Open that URL in the TV's browser and enable full screen.
3. Configure the device to open it automatically on startup:
   - **Chromium / Chrome on Linux, Windows or mini PCs**:
     `chromium --kiosk --noerrdialogs --disable-infobars --autoplay-policy=no-user-gesture-required http://SERVER-IP/screen/lobby`
   - **Raspberry Pi OS**: add the same command to the desktop autostart.
   - **Smart TVs / Android TV**: use a kiosk browser app with auto-start (e.g. Fully Kiosk Browser)
     and allow autoplay.
4. Disable the TV's energy saving and screen saver.

Each screen sends a heartbeat every 15 seconds; **Screens** shows which ones are online. If the
network drops, the TV keeps showing the last content it had and reconnects on its own. Changes to
playlists, branding, display settings and emergencies reach open screens in real time.

## Backups

From the project folder on the Docker host (Linux, macOS or WSL):

```bash
bash scripts/backup.sh
```

The script stops `backend` and `worker` for a few seconds (so nothing writes while copying),
creates `backups/information-board-<timestamp>/` with `database.dump`, `data.tar.gz` (skipped with
S3 storage), `manifest.sha256` and `info.txt`, and starts the services again. Set `BACKUP_KEEP` in
`.env` to keep only the most recent N backups.

**`.env` is not included** because it holds secrets: keep a protected copy separately.

Schedule it with cron, for example every night at 03:00:

```cron
0 3 * * * cd /opt/information-board && bash scripts/backup.sh >> backups/backup.log 2>&1
```

## Restore

```bash
bash scripts/restore.sh information-board-20260101T030000Z
```

The script verifies the checksums, asks you to type `yes`, stops `backend` and `worker`, replaces
the database, extracts the files and starts the services again. Test restores periodically on a
separate machine, not only during a real incident.

## Verifying an installation

```bash
docker compose config --quiet                 # the configuration is valid
curl http://localhost/api/v1/health           # {"status":"ok","database":"ok","redis":"ok"}
docker compose exec -T backend python - < scripts/deployment_smoke.py
```

The smoke test signs in with the initial administrator (pass `-e SMOKE_PASSWORD=...` if that
password was changed), checks the main routes, creates a temporary publication and playlist, checks
playback on the first screen and removes everything it created.

Backend unit tests inside the container:

```bash
docker compose run --rm --no-deps -v "$(pwd)/backend/tests:/app/tests:ro" backend sh -c "pip install -q moto[s3]==5.0.18 && python -m pytest -q"
```

End-to-end browser tests: see [e2e/README.md](../e2e/README.md).

## When the network changes

With `PUBLIC_BASE_URL` empty (the default), QR codes and share links are built from the address each
device used to open the board, port included. If the server gets a new IP address or moves to
another network, **nothing has to change in `.env`**: a TV opened at `http://10.0.0.8/screen/lobby`
shows a QR code for `http://10.0.0.8/catalog/lobby`. **Settings → System** shows the address in use.

The TVs still need an address to open. From most to least stable:

1. **A name instead of an IP address.** Create a DNS record in your router or local DNS (for example
   `board.lan`), or use mDNS: on a Linux server run `sudo apt install avahi-daemon` and open
   `http://<server-hostname>.local`. mDNS works on Windows 10+, macOS, iOS, most Linux desktops and
   recent Android; some smart TVs and older Android devices cannot resolve `.local` names.
2. **A DHCP reservation** in the router, so the server always receives the same IP address.
3. Otherwise, update the kiosk URL on each TV after the address changes.

To restrict administration without tying it to one subnet, use `ALLOWED_NETWORKS=private`.

Set `PUBLIC_BASE_URL` to a fixed value only when links must always use one address, for example
when TVs open the board through `localhost` on the server itself, or behind a reverse proxy that
does not forward the original host name.

### Changing the port

```env
HTTP_PORT=8080
```

Then `docker compose up -d`. The board is reachable at `http://SERVER:8080` and QR codes include the
port automatically. Update the kiosk URLs on the TVs.

## HTTPS

The stack serves plain HTTP inside the local network. To expose it outside, place it behind a
reverse proxy with a certificate (Caddy, Traefik, nginx Proxy Manager, Cloudflare Tunnel...). Links
switch to `https://` automatically when the proxy forwards the `Host` and `X-Forwarded-Proto`
headers (most do by default); otherwise set `PUBLIC_BASE_URL=https://board.example.org`. Consider
`ALLOWED_NETWORKS=private` to keep administration limited to your internal networks.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| The site does not open | `docker compose ps`, the host firewall, and that `HTTP_PORT` is not used by another program. |
| The backend exits right after starting | `docker compose logs backend`. "Refusing to start" lists the settings that still hold placeholder values. A password mismatch between `POSTGRES_PASSWORD` and `DATABASE_URL` is the other usual cause. |
| `Permission denied` writing to `/data` | The data folder must belong to `APP_UID:APP_GID` (see [storage](storage.md#permissions-options-a-c)). |
| NAS volume fails to mount | Install `cifs-utils` / `nfs-common` on the host, check the share name, credentials and export permissions, and recreate the volumes after changing `NAS_*`. |
| S3 errors in the logs | Check bucket name, region, endpoint, key permissions and `S3_FORCE_PATH_STYLE`. **Settings → System** shows the configured bucket. |
| Uploads fail with "413" | Raise `NGINX_MAX_BODY_SIZE` and the matching `MAX_*_SIZE_MB`. |
| A document stays "Processing" | `docker compose logs worker`; the worker needs to be healthy. Very large presentations can take a few minutes. |
| A screen shows as offline | Keep the URL open on the TV and check that it can still reach the server (see [when the network changes](#when-the-network-changes)). |
| Sign-in is rejected | The `INITIAL_ADMIN_*` values only apply to the first start. Use `python -m app.cli reset-password`. Too many attempts block that IP for `LOGIN_WINDOW_SECONDS`. |
| QR codes do not open on phones | QR codes use the address the TV opened: open the screen with the server's network address or name, not `localhost` (or set a fixed `PUBLIC_BASE_URL`). The phone must be on a network that reaches the server. **Settings → System** warns when the address is `localhost`. |
| Wrong time on TVs or schedules | Set the time zone in **Settings → Branding** (and `TZ` in `.env` for the containers). |
| Emergency address not found | Check `GEOCODING_ENABLED`, Internet access from the server (or your own `GEOCODE_URL`) and `GEOCODE_COUNTRY_CODES`. |
