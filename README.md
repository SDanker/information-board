# Information Board

**English** · [Español](README.es.md)

Self-hosted digital signage for offices, schools, hospitals and factories. Manage screens and
playlists from a browser, publish announcements, images, videos, documents, spreadsheets and
presentations, and interrupt every TV with a featured event broadcast in real time.

Everything runs with Docker Compose on a single server in your local network. The interface is
available in **English and Spanish**, and the name, logo, colors, page names, storage (local
disk, NAS or S3-compatible cloud) and first administrator are all configurable.

## Features

- **Screens**: one URL per TV (`/screen/<slug>`), heartbeat and online status, kiosk friendly,
  keeps playing the last known content if the connection drops.
- **Content**: announcements, images, videos (transcoded with ffmpeg), documents, spreadsheets
  and presentations (converted with LibreOffice), with per-page or per-slide durations.
- **Shared calendars**: paste the ICS address of an Outlook, Google or Nextcloud calendar and
  show it as a month, week or day. The server reads and caches the feed, so the TVs need no
  Internet access and the link is never exposed on screen.
- **Publication periods**: every publication lasts 7 days by default (configurable); set its start
  and end date and time and the weekdays it appears when creating it, independently of playlists.
  When the period ends it is archived: it leaves the playlists, moves to the **Archived** segment of
  Content and of the download pages, where every archived publication can be downloaded (or all at
  once as a zip), and it can be restored with a new period.
- **Playlists and schedule**: ordering, per-item duration, validity by date, weekday and time.
- **Featured events**: address geocoding, map, photos and videos, and a broadcast that takes over
  every screen instantly through WebSockets.
- **QR codes and public pages**: each screen shows a QR that opens the catalog of everything in
  its playlist, with per-item downloads and zip archives; optional public library.
- **Users and audit**: administrator, editor and operator roles, audit log, login rate limiting
  and optional subnet restriction for the admin area.
- **Customization**: see below.

## What you can customize

| Where | What |
| --- | --- |
| **Settings → Branding** (in the app) | Application and organization name, logo (also the browser icon), primary color, default language, date format, time zone, login page headline and message, public library on/off |
| **Settings → Page names** | The name of every menu page (Dashboard, Screens, Content, Playlists, Library, Schedule, Users, Audit, Settings) |
| **Settings → Screens & TV** | Default publication length (7 days), default seconds per item, minimum seconds per page/slide, seconds per featured event photo or map, spreadsheet rows per page, clock on/off and 12/24 h, featured event map on/off, TV footer text, QR code on/off, position and message |
| **`.env`** (on the server) | First administrator username and password, initial screens, public address (automatic by default, so a new IP or network needs no change) and port, storage backend (local folder, NAS over SMB or NFS, S3-compatible cloud), upload size limits, session length, login attempt limits, allowed networks, geocoding provider and countries, container user id |

Every visitor can also switch between English and Spanish with the language picker.

Full reference: [docs/configuration.md](docs/configuration.md) · Storage options: [docs/storage.md](docs/storage.md) · Operations: [docs/operations.md](docs/operations.md)

## Quick start

Requirements: a Linux server (or any machine with Docker Engine / Docker Desktop and Compose v2)
with a fixed IP address or DHCP reservation, and modern browsers on the TVs. Python, Node.js,
PostgreSQL, Redis and nginx are **not** needed on the host: everything runs in containers.

```bash
git clone https://github.com/<your-account>/information-board.git
cd information-board
python3 scripts/setup.py          # bilingual wizard that creates .env with random secrets
docker compose up -d --build
```

The wizard asks for the language, name, public address, first administrator, initial screens and
where to store files. Prefer to edit by hand? Copy `.env.example` to `.env` and replace every
`CHANGE_ME` value (the backend refuses to start in production while placeholders remain).

Then open:

| Page | URL |
| --- | --- |
| Sign in | `http://SERVER-IP/login` |
| Administration | `http://SERVER-IP/admin` |
| A screen (open it on the TV, full screen) | `http://SERVER-IP/screen/<slug>` |
| Screen catalog (what the QR opens) | `http://SERVER-IP/catalog/<slug>` |
| Public library | `http://SERVER-IP/library` |
| Health check | `http://SERVER-IP/api/v1/health` |

Sign in with the administrator from `.env`, go to **Settings** to upload your logo and adjust the
branding, then create content and playlists and assign them to screens.

## Architecture

```
TV browsers / phones / admins
            │
          nginx ─────────────┐
      /        \             │ /ws (real time)
 Next.js 15    FastAPI ──────┘
 (frontend)    (backend) ── PostgreSQL 16
                  │   └──── Redis 7 (events, queue)
               worker (LibreOffice, ffmpeg, PyMuPDF)
                  │
     files: local folder · NAS (SMB/NFS) · S3-compatible bucket
```

| Folder | Content |
| --- | --- |
| `backend/` | FastAPI API, SQLAlchemy models, Alembic migrations, worker, CLI and tests |
| `frontend/` | Next.js App Router interface (admin, TV player, public pages) with EN/ES messages |
| `nginx/templates/` | Reverse proxy configuration |
| `scripts/` | `setup.py` wizard, `backup.sh`, `restore.sh`, `deployment_smoke.py` |
| `e2e/` | Playwright end-to-end tests against a running stack |
| `docs/` | Configuration, storage and operations guides (`docs/es/` in Spanish) |

## Development

```bash
# Backend tests (Python 3.12)
cd backend
pip install -r requirements-dev.txt
python -m pytest -q

# Frontend (Node.js 22 + pnpm)
cd frontend
corepack enable
pnpm install
pnpm build
```

Conventions:

- Code, identifiers and comments are written in English.
- Backend user-facing messages are English strings wrapped in `_()` (`app/i18n.py`), with the
  Spanish translation in `app/locales/es.py`. A test fails if a translation is missing.
- Frontend texts live in `frontend/lib/i18n/messages/*.ts`, where each group defines the English
  and Spanish messages together; TypeScript fails the build if a key is missing in either language.
- Database changes need an Alembic migration in `backend/alembic/versions/`.

GitHub Actions (`.github/workflows/ci.yml`) runs the backend tests, the frontend build and a
validation of the Compose files on every push and pull request.

## Security notes

- Never commit `.env`: it contains the database password, the signing key and the initial
  administrator password. It is already listed in `.gitignore`.
- Change the initial password after the first sign-in (**Settings → My account**) and create one
  account per person.
- nginx is the only published port. PostgreSQL and Redis are only reachable inside Docker.
- Put the server behind HTTPS (for example a reverse proxy with a certificate) if it is reachable
  from outside the local network.

## License

No license file is included yet. Add one (for example MIT or Apache-2.0) before publishing the
repository if you want others to be able to use it.
