# Configuration

**English** · [Español](es/configuracion.md)

Information Board has two layers of configuration:

1. **Settings in the application** (Settings page, administrators only): branding, page names and
   TV behavior. Stored in the database, applied instantly to every open screen, no restart.
2. **The `.env` file on the server**: infrastructure, security and first-run values. Apply changes
   with `docker compose up -d` (the containers are recreated with the new values).

`python3 scripts/setup.py` creates `.env` interactively in English or Spanish. `.env.example`
documents every variable.

## 1. Settings in the application

### Branding

| Setting | Notes |
| --- | --- |
| Application name | Menu, login page, TVs, browser tab. Initial value: `APP_NAME`. |
| Organization name | Optional subtitle under the name and on public pages. Initial value: `ORGANIZATION_NAME`. |
| Primary color | Buttons, links, active menu entries and accents. Initial value: `BRAND_PRIMARY_COLOR`. |
| Logo | PNG, JPG, WEBP or GIF up to `MAX_LOGO_SIZE_MB`. Converted to PNG, at most 512 px. Used in the menu, login page, TVs, public pages and as the favicon. Without a logo a neutral icon is shown. |
| Default language | `en` or `es`. Used by TVs and by visitors who have not chosen a language. Initial value: `DEFAULT_LANGUAGE`. |
| Date format (locale) | BCP 47 code such as `en-US`, `en-GB`, `es-CL`, `es-MX`. Empty = `en-US` or `es-ES`. Initial value: `DATE_LOCALE`. |
| Time zone | IANA name used by schedules and TV clocks. Initial value: `TZ`. |
| Login headline and message | Texts on the left side of the login page. Empty = default text in each language. |
| Public library | Turns `/library` on or off. Screen catalogs opened from QR codes keep working. |

**Restore defaults** resets every in-app customization to the `.env` values (the logo is kept).

### Page names

Rename any menu page: Dashboard, Screens, Content, Playlists, Library, Schedule, Users, Audit and
Settings. A custom name is shown in every language; leave a field empty to use the translated
default name.

### Screens & TV

| Setting | Default | Notes |
| --- | --- | --- |
| Default seconds per playlist item | 15 | Used when an item has no duration of its own. |
| Minimum seconds per page or slide | 4 | Multi-page documents and presentations stay on screen until every page has been shown. Individual pages can have their own duration. |
| Seconds per emergency photo or map | 7 | Emergency videos always play to the end. |
| Spreadsheet rows per page | 14 | Large tables are split into several pages. |
| Show the clock / 24-hour clock | on / on | |
| Show the map during emergencies | on | |
| TV footer text | empty | Replaces the screen path shown at the bottom left. |
| QR code: show, position, message | on, bottom right | The QR opens `/catalog/<slug>` with every item in the screen's playlist. |

### Language picker

Each person can switch between English and Spanish from the menu, the login page or the public
pages. The choice is remembered in that browser. Order of precedence: the person's choice, then
the installation's default language.

## 2. The `.env` file

### Identity (initial values)

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `Information Board` | Initial application name. |
| `ORGANIZATION_NAME` | empty | Initial organization name. |
| `BRAND_PRIMARY_COLOR` | `#2563eb` | Initial primary color (`#rrggbb`). |
| `DEFAULT_LANGUAGE` | `en` | `en` or `es`. Also the language of the default screen created on the first start and of server messages when the browser sends no preference. |
| `DATE_LOCALE` | empty | Initial date locale. |
| `TZ` | `UTC` | IANA time zone for the application and the containers. |

These are only initial values: once an administrator saves the Branding settings, the saved values
win. Use **Restore defaults** to go back to `.env`.

### Network

| Variable | Default | Description |
| --- | --- | --- |
| `PUBLIC_BASE_URL` | empty (automatic) | Address used in QR codes and share links. **Empty = automatic**: links use the address each TV, phone or computer used to open the board (including the port), so a new IP address or network needs no change. Set a fixed value only to force one address, e.g. `https://board.example.org` behind a reverse proxy. See [when the network changes](operations.md#when-the-network-changes). |
| `HTTP_PORT` | `80` | Port published by nginx on the host. |
| `ALLOWED_NETWORKS` | empty | Networks allowed to use the admin API, comma-separated. `private` allows every private network (10.x, 172.16-31.x, 192.168.x, private IPv6, localhost) and keeps working if the LAN changes; specific subnets such as `192.168.1.0/24` also work. Screens (`/api/v1/public/*`), the health check and WebSockets are always reachable. Empty = no restriction. |
| `CORS_EXTRA_ORIGINS` | empty | Extra browser origins allowed to call the API, for custom integrations. |

### First administrator and screens

| Variable | Default | Description |
| --- | --- | --- |
| `INITIAL_ADMIN_USERNAME` | `admin` | Created on the first start only, while there are no users. |
| `INITIAL_ADMIN_PASSWORD` | placeholder | At least 8 characters. Required in production. |
| `INITIAL_SCREENS` | empty | `slug:Name` pairs separated by commas, e.g. `lobby:Lobby,cafeteria:Cafeteria`. Created only while there are no screens. Empty = one screen `main` (`principal` in Spanish). |

Changing these values later does **not** modify existing accounts or screens. To change a password
or recover access use the CLI (see [operations](operations.md#command-line-tools)):

```bash
docker compose exec backend python -m app.cli reset-password --username admin
```

### Security

| Variable | Default | Description |
| --- | --- | --- |
| `APP_ENV` | `production` in `.env.example` | In `production` the backend refuses to start while `SECRET_KEY`, `INITIAL_ADMIN_PASSWORD` or `DATABASE_URL` hold placeholder or weak values. |
| `SECRET_KEY` | placeholder | At least 32 random characters. Signs session tokens: changing it signs everyone out. |
| `ACCESS_TOKEN_MINUTES` | `480` | Length of an admin session. |
| `LOGIN_MAX_ATTEMPTS` | `10` | Failed sign-ins allowed per IP address within the window. |
| `LOGIN_WINDOW_SECONDS` | `300` | Length of that window. |

### Database and cache

| Variable | Default | Description |
| --- | --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | `information_board`, `information_board`, placeholder | PostgreSQL database created on the first start. |
| `DATABASE_URL` | built from the above | Must contain the same user and password. |
| `REDIS_URL` | `redis://redis:6379/0` | Real-time events and the processing queue. |

The PostgreSQL password is fixed when the database volume is first created; changing it later in
`.env` requires changing it inside PostgreSQL too (`ALTER USER ... PASSWORD ...`).

### Uploads

| Variable | Default | Description |
| --- | --- | --- |
| `MAX_DOCUMENT_SIZE_MB` | `100` | Documents, spreadsheets and presentations. |
| `MAX_IMAGE_SIZE_MB` | `25` | Images, including emergency photos. |
| `MAX_VIDEO_SIZE_MB` | `500` | Videos. |
| `MAX_LOGO_SIZE_MB` | `5` | Logo in Settings. |
| `NGINX_MAX_BODY_SIZE` | `600m` | Largest request nginx accepts; keep it above the largest limit. |

### File storage

`STORAGE_BACKEND` (`local` or `s3`), `BOARD_DATA_PATH`, `BOARD_BACKUPS_PATH`, `APP_UID`, `APP_GID`,
`BACKUP_KEEP`, the `NAS_*` variables and the `S3_*` variables are explained in
[storage.md](storage.md).

### Emergency geocoding

| Variable | Default | Description |
| --- | --- | --- |
| `GEOCODING_ENABLED` | `true` | Turns address search for emergencies on or off. Without it, emergencies still work but show no map. |
| `GEOCODE_URL` | OpenStreetMap Nominatim | Any Nominatim-compatible `/search` endpoint, e.g. a self-hosted instance for networks without Internet access. |
| `GEOCODE_COUNTRY_CODES` | empty | ISO country codes that restrict results, e.g. `cl` or `us,ca`. Empty = worldwide. |
| `GEOCODE_USER_AGENT` | empty | Identifies your installation (OpenStreetMap's usage policy asks for it), e.g. `information-board (it@example.org)`. |

## Applying changes

```bash
docker compose up -d            # recreate containers whose configuration changed
docker compose up -d --build    # also needed after changing APP_UID/APP_GID or updating the code
```
