# End-to-end tests (Playwright)

**English** · [Español](#pruebas-de-extremo-a-extremo-playwright)

These tests exercise real business flows against a running stack (`docker compose up -d`),
because they depend on the real worker (LibreOffice and ffmpeg) to convert documents and
spreadsheets. They force the English interface, so they work whatever the installation's
default language is, and they create and delete their own screens, playlists and content.

## Requirements

- Node.js 20 or later.
- A running installation (default `http://localhost`, configurable with `PLAYWRIGHT_BASE_URL`).
- An administrator account, passed through environment variables (never stored in the repository):

```bash
export E2E_ADMIN_USERNAME=admin
export E2E_ADMIN_PASSWORD='the-real-password'
export PLAYWRIGHT_BASE_URL=http://192.168.1.50   # optional
```

## Install and run

```bash
cd e2e
npm install
npx playwright install --with-deps chromium
npm test
```

## What each file covers

- `document-flow.spec.ts`: uploads a `.txt` document, waits for the conversion, adds it to a
  playlist, assigns the playlist to a new screen and checks that the TV shows the page.
- `spreadsheet-flow.spec.ts`: uploads a `.csv` and checks that the TV renders it as a table.
- `emergency-flow.spec.ts`: creates a featured event, broadcasts it, checks that it interrupts a
  TV in real time, stops it and checks that the TV goes back to normal.

---

# Pruebas de extremo a extremo (Playwright)

Estas pruebas recorren flujos reales contra una instalación en funcionamiento
(`docker compose up -d`), porque dependen del worker real (LibreOffice y ffmpeg) para convertir
documentos y planillas. Fuerzan la interfaz en inglés, así funcionan sea cual sea el idioma por
defecto de la instalación, y crean y borran sus propias pantallas, playlists y publicaciones.

## Requisitos

- Node.js 20 o superior.
- Una instalación funcionando (por defecto `http://localhost`, configurable con `PLAYWRIGHT_BASE_URL`).
- Una cuenta de administrador, entregada por variables de entorno (nunca guardada en el repositorio):

```bash
export E2E_ADMIN_USERNAME=admin
export E2E_ADMIN_PASSWORD='la-contraseña-real'
export PLAYWRIGHT_BASE_URL=http://192.168.1.50   # opcional
```

## Instalar y ejecutar

```bash
cd e2e
npm install
npx playwright install --with-deps chromium
npm test
```

## Qué cubre cada archivo

- `document-flow.spec.ts`: sube un documento `.txt`, espera la conversión, lo agrega a una
  playlist, la asigna a una pantalla nueva y verifica que la TV muestre la página.
- `spreadsheet-flow.spec.ts`: sube un `.csv` y verifica que la TV lo muestre como tabla.
- `emergency-flow.spec.ts`: crea un acto destacado, lo transmite, verifica que interrumpa una TV
  en tiempo real, la detiene y verifica que la TV vuelva a la normalidad.
