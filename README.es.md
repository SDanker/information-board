# Information Board

[English](README.md) · **Español**

Cartelera digital autoalojada para oficinas, colegios, hospitales y plantas. Administra pantallas
y playlists desde el navegador, publica anuncios, imágenes, videos, documentos, planillas y
presentaciones, e interrumpe todas las TV con una transmisión de emergencia en tiempo real.

Todo funciona con Docker Compose en un solo servidor dentro de tu red local. La interfaz está
disponible en **inglés y español**, y se pueden configurar el nombre, logo, colores, nombres de
páginas, almacenamiento (disco local, NAS o nube compatible con S3) y el primer administrador.

## Funciones

- **Pantallas**: una URL por TV (`/screen/<slug>`), señal de actividad y estado en línea, apta
  para modo kiosco, sigue mostrando el último contenido conocido si se corta la conexión.
- **Contenido**: anuncios, imágenes, videos (convertidos con ffmpeg), documentos, planillas y
  presentaciones (convertidos con LibreOffice), con duración por página o diapositiva.
- **Playlists y programación**: orden, duración por elemento, vigencia por fecha, día y hora.
- **Emergencias**: geocodificación de direcciones, mapa, fotos y videos, y una transmisión que
  toma todas las pantallas al instante mediante WebSockets.
- **Códigos QR y páginas públicas**: cada pantalla muestra un QR que abre el catálogo de todo lo
  que hay en su playlist, con descargas individuales y en zip; biblioteca pública opcional.
- **Usuarios y auditoría**: roles administrador, editor y operador, registro de auditoría, límite
  de intentos de inicio de sesión y restricción opcional por subred para la administración.
- **Personalización**: ver abajo.

## Qué se puede personalizar

| Dónde | Qué |
| --- | --- |
| **Configuración → Marca** (en la aplicación) | Nombre de la aplicación y de la organización, logo (también ícono del navegador), color principal, idioma por defecto, formato de fecha, zona horaria, titular y mensaje del inicio de sesión, biblioteca pública sí/no |
| **Configuración → Nombres de páginas** | El nombre de cada página del menú (Panel, Pantallas, Publicaciones, Playlists, Biblioteca, Programación, Usuarios, Auditoría, Configuración) |
| **Configuración → Pantallas y TV** | Segundos por defecto por elemento, segundos mínimos por página/diapositiva, segundos por foto o mapa de emergencia, filas por página en planillas, reloj sí/no y 12/24 h, mapa de emergencia sí/no, texto del pie en la TV, código QR sí/no, posición y mensaje |
| **`.env`** (en el servidor) | Usuario y contraseña del primer administrador, pantallas iniciales, dirección pública (automática por defecto, así una IP o red nueva no requiere cambios) y puerto, almacenamiento (carpeta local, NAS por SMB o NFS, nube compatible con S3), límites de tamaño de subida, duración de la sesión, límite de intentos de inicio de sesión, redes permitidas, proveedor y países de geocodificación, id de usuario de los contenedores |

Además, cada visitante puede cambiar entre inglés y español con el selector de idioma.

Referencia completa: [docs/es/configuracion.md](docs/es/configuracion.md) · Almacenamiento: [docs/es/almacenamiento.md](docs/es/almacenamiento.md) · Operación: [docs/es/operacion.md](docs/es/operacion.md)

## Inicio rápido

Requisitos: un servidor Linux (o cualquier equipo con Docker Engine / Docker Desktop y Compose v2)
con IP fija o reserva DHCP, y navegadores modernos en las TV. **No** es necesario instalar Python,
Node.js, PostgreSQL, Redis ni nginx en el servidor: todo corre en contenedores.

```bash
git clone https://github.com/<tu-cuenta>/information-board.git
cd information-board
python3 scripts/setup.py          # asistente bilingüe que crea .env con secretos aleatorios
docker compose up -d --build
```

El asistente pregunta el idioma, nombre, dirección pública, primer administrador, pantallas
iniciales y dónde guardar los archivos. ¿Prefieres editar a mano? Copia `.env.example` como `.env`
y reemplaza cada valor `CHANGE_ME` (en producción el backend no inicia mientras queden valores de
ejemplo).

Luego abre:

| Página | URL |
| --- | --- |
| Inicio de sesión | `http://IP-DEL-SERVIDOR/login` |
| Administración | `http://IP-DEL-SERVIDOR/admin` |
| Una pantalla (ábrela en la TV, a pantalla completa) | `http://IP-DEL-SERVIDOR/screen/<slug>` |
| Catálogo de la pantalla (lo que abre el QR) | `http://IP-DEL-SERVIDOR/catalog/<slug>` |
| Biblioteca pública | `http://IP-DEL-SERVIDOR/library` |
| Estado del servidor | `http://IP-DEL-SERVIDOR/api/v1/health` |

Inicia sesión con el administrador de `.env`, entra a **Configuración** para subir tu logo y
ajustar la marca, y luego crea publicaciones y playlists y asígnalas a las pantallas.

Si pones `DEFAULT_LANGUAGE=es` (o eliges español en el asistente), las TV, la primera pantalla
creada y los visitantes nuevos verán la interfaz en español.

## Arquitectura

```
Navegadores de TV / teléfonos / administradores
            │
          nginx ─────────────┐
      /        \             │ /ws (tiempo real)
 Next.js 15    FastAPI ──────┘
 (frontend)    (backend) ── PostgreSQL 16
                  │   └──── Redis 7 (eventos, cola)
               worker (LibreOffice, ffmpeg, PyMuPDF)
                  │
  archivos: carpeta local · NAS (SMB/NFS) · bucket compatible con S3
```

| Carpeta | Contenido |
| --- | --- |
| `backend/` | API FastAPI, modelos SQLAlchemy, migraciones Alembic, worker, CLI y pruebas |
| `frontend/` | Interfaz Next.js App Router (administración, reproductor de TV, páginas públicas) con mensajes EN/ES |
| `nginx/templates/` | Configuración del proxy inverso |
| `scripts/` | Asistente `setup.py`, `backup.sh`, `restore.sh`, `deployment_smoke.py` |
| `e2e/` | Pruebas de extremo a extremo con Playwright contra una instalación en funcionamiento |
| `docs/` | Guías de configuración, almacenamiento y operación (`docs/es/` en español) |

## Desarrollo

```bash
# Pruebas del backend (Python 3.12)
cd backend
pip install -r requirements-dev.txt
python -m pytest -q

# Frontend (Node.js 22 + pnpm)
cd frontend
corepack enable
pnpm install
pnpm build
```

Convenciones:

- El código, los identificadores y los comentarios se escriben en inglés.
- Los mensajes del backend visibles para usuarios son textos en inglés envueltos en `_()`
  (`app/i18n.py`), con la traducción al español en `app/locales/es.py`. Una prueba falla si falta
  una traducción.
- Los textos del frontend están en `frontend/lib/i18n/messages/*.ts`, donde cada grupo define
  juntos los mensajes en inglés y español; TypeScript no compila si falta una clave en un idioma.
- Los cambios de base de datos requieren una migración Alembic en `backend/alembic/versions/`.

GitHub Actions (`.github/workflows/ci.yml`) ejecuta las pruebas del backend, la compilación del
frontend y una validación de los archivos de Compose en cada push y pull request.

## Notas de seguridad

- Nunca subas `.env` al repositorio: contiene la contraseña de la base de datos, la clave de firma
  y la contraseña inicial del administrador. Ya está incluido en `.gitignore`.
- Cambia la contraseña inicial después del primer inicio de sesión (**Configuración → Mi cuenta**)
  y crea una cuenta por persona.
- nginx es el único puerto publicado. PostgreSQL y Redis sólo son accesibles dentro de Docker.
- Usa HTTPS (por ejemplo, un proxy inverso con certificado) si el servidor es accesible desde
  fuera de la red local.

## Licencia

Todavía no se incluye un archivo de licencia. Agrega uno (por ejemplo MIT o Apache-2.0) antes de
publicar el repositorio si quieres que otras personas puedan usarlo.
