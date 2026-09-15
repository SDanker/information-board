#!/usr/bin/env python3
"""Guided creation of the .env file for Information Board.

Run it from the project folder before the first `docker compose up`:

    python3 scripts/setup.py
    python3 scripts/setup.py --non-interactive --base-url http://192.168.1.50 --language es

Only the Python standard library is needed. Secrets are generated randomly, the file is created
with owner-only permissions, and an existing .env is never replaced unless --force is given
(a timestamped copy of the previous file is kept next to it).
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import secrets
import shutil
import socket
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
# Values made only of these characters are written unquoted; anything else is single-quoted.
UNQUOTED_VALUE = re.compile(r"^[A-Za-z0-9_./:@,+=%-]*$")

TEXT = {
    "en": {
        "intro": "This assistant creates the .env file for Information Board.\nPress Enter to accept the value in [brackets].",
        "exists": ".env already exists. Run again with --force to replace it (a copy is kept).",
        "identity": "Identity",
        "app_name": "Application name",
        "organization": "Organization name (optional)",
        "language": "Default language (en/es)",
        "timezone": "Time zone (IANA name, e.g. America/Santiago)",
        "network": "Network",
        "base_url": "Address used to open the board from other devices",
        "port": "HTTP port",
        "admin": "First administrator",
        "admin_user": "Username",
        "admin_password": "Password (Enter to generate a random one)",
        "admin_repeat": "Repeat the password",
        "screens": "Screens to create, as slug:Name separated by commas (Enter for one default screen)",
        "storage": "File storage",
        "storage_menu": "Where should uploaded files be stored?\n"
        "  1) A folder on this server\n"
        "  2) A NAS already mounted on this server (the host mounts it over SMB or NFS)\n"
        "  3) A NAS share mounted by Docker over SMB/CIFS\n"
        "  4) A NAS export mounted by Docker over NFS\n"
        "  5) S3-compatible storage on the Internet (AWS S3, Cloudflare R2, Backblaze B2, Wasabi, MinIO...)",
        "choice": "Choice",
        "data_path": "Folder for uploaded files",
        "backups_path": "Folder for backups",
        "nas_mount": "Folder where the NAS is mounted on this server",
        "nas_host": "NAS host name or IP address",
        "nas_share": "SMB share name",
        "nas_user": "NAS username",
        "nas_password": "NAS password",
        "nas_export": "NFS export path (e.g. /volume1/information-board)",
        "s3_bucket": "Bucket name",
        "s3_region": "Region (Enter to skip)",
        "s3_endpoint": "Endpoint URL (Enter for AWS S3)",
        "s3_key": "Access key ID",
        "s3_secret": "Secret access key",
        "s3_prefix": "Folder inside the bucket (optional)",
        "s3_path_style": "Use path-style URLs? Usually yes for MinIO, Garage or SeaweedFS",
        "geocoding": "Country codes that restrict emergency addresses (e.g. cl or us,ca; Enter = worldwide)",
        "yes_no": "y/N",
        "required": "This value is required.",
        "invalid_url": "Enter an address that starts with http:// or https://",
        "invalid_port": "Enter a port between 1 and 65535.",
        "invalid_language": "Enter en or es.",
        "invalid_choice": "Enter one of the listed numbers.",
        "invalid_username": "Use 3 to 80 letters, numbers, dots, dashes, underscores or @.",
        "invalid_timezone": "Enter a time zone such as UTC or Europe/Madrid.",
        "invalid_password": "Use at least 8 characters, without single quotes.",
        "invalid_value": "Single quotes (') are not allowed in this value.",
        "invalid_comma": "Commas are not allowed here (Docker mount options are comma-separated).",
        "mismatch": "The passwords do not match.",
        "localhost_warning": "Warning: other devices cannot reach localhost; QR codes will not work from phones.",
        "written": ".env created with owner-only permissions: {path}",
        "backup_kept": "Previous .env kept as {path}",
        "generated_password": "Generated administrator password (shown only once, store it safely): {password}",
        "smb_note": "Before starting: install cifs-utils on this host and create the folders 'data' and 'backups' inside the share.",
        "nfs_note": "Before starting: install nfs-common on this host and create the folders 'data' and 'backups' inside the export.",
        "next": "Next steps:\n  docker compose up -d --build\n  Open {url}/login and sign in as '{user}'.\n  Then open Settings to add your logo, colors and page names.",
    },
    "es": {
        "intro": "Este asistente crea el archivo .env de Information Board.\nPresiona Enter para aceptar el valor entre [corchetes].",
        "exists": ".env ya existe. Vuelve a ejecutar con --force para reemplazarlo (se guarda una copia).",
        "identity": "Identidad",
        "app_name": "Nombre de la aplicación",
        "organization": "Nombre de la organización (opcional)",
        "language": "Idioma por defecto (en/es)",
        "timezone": "Zona horaria (nombre IANA, p. ej. America/Santiago)",
        "network": "Red",
        "base_url": "Dirección para abrir la cartelera desde otros equipos",
        "port": "Puerto HTTP",
        "admin": "Primer administrador",
        "admin_user": "Usuario",
        "admin_password": "Contraseña (Enter para generar una aleatoria)",
        "admin_repeat": "Repite la contraseña",
        "screens": "Pantallas a crear, como slug:Nombre separadas por coma (Enter para una pantalla por defecto)",
        "storage": "Almacenamiento de archivos",
        "storage_menu": "¿Dónde se guardan los archivos subidos?\n"
        "  1) Una carpeta en este servidor\n"
        "  2) Un NAS ya montado en este servidor (el host lo monta por SMB o NFS)\n"
        "  3) Una carpeta compartida de un NAS montada por Docker vía SMB/CIFS\n"
        "  4) Un export de un NAS montado por Docker vía NFS\n"
        "  5) Almacenamiento compatible con S3 en Internet (AWS S3, Cloudflare R2, Backblaze B2, Wasabi, MinIO...)",
        "choice": "Opción",
        "data_path": "Carpeta para los archivos subidos",
        "backups_path": "Carpeta para los respaldos",
        "nas_mount": "Carpeta donde está montado el NAS en este servidor",
        "nas_host": "Nombre o IP del NAS",
        "nas_share": "Nombre de la carpeta compartida SMB",
        "nas_user": "Usuario del NAS",
        "nas_password": "Contraseña del NAS",
        "nas_export": "Ruta del export NFS (p. ej. /volume1/information-board)",
        "s3_bucket": "Nombre del bucket",
        "s3_region": "Región (Enter para omitir)",
        "s3_endpoint": "URL del endpoint (Enter para AWS S3)",
        "s3_key": "Access key ID",
        "s3_secret": "Secret access key",
        "s3_prefix": "Carpeta dentro del bucket (opcional)",
        "s3_path_style": "¿Usar URLs estilo path? Normalmente sí para MinIO, Garage o SeaweedFS",
        "geocoding": "Códigos de país para restringir direcciones de emergencia (p. ej. cl o us,ca; Enter = todo el mundo)",
        "yes_no": "s/N",
        "required": "Este valor es obligatorio.",
        "invalid_url": "Ingresa una dirección que comience con http:// o https://",
        "invalid_port": "Ingresa un puerto entre 1 y 65535.",
        "invalid_language": "Ingresa en o es.",
        "invalid_choice": "Ingresa uno de los números de la lista.",
        "invalid_username": "Usa de 3 a 80 letras, números, puntos, guiones, guiones bajos o @.",
        "invalid_timezone": "Ingresa una zona horaria como UTC o America/Santiago.",
        "invalid_password": "Usa al menos 8 caracteres, sin comillas simples.",
        "invalid_value": "No se permiten comillas simples (') en este valor.",
        "invalid_comma": "No se permiten comas aquí (Docker separa las opciones de montaje con comas).",
        "mismatch": "Las contraseñas no coinciden.",
        "localhost_warning": "Aviso: otros equipos no pueden alcanzar localhost; los códigos QR no funcionarán desde teléfonos.",
        "written": ".env creado con permisos sólo para el dueño: {path}",
        "backup_kept": "El .env anterior se guardó como {path}",
        "generated_password": "Contraseña de administrador generada (se muestra sólo una vez, guárdala en un lugar seguro): {password}",
        "smb_note": "Antes de iniciar: instala cifs-utils en este servidor y crea las carpetas 'data' y 'backups' dentro de la carpeta compartida.",
        "nfs_note": "Antes de iniciar: instala nfs-common en este servidor y crea las carpetas 'data' y 'backups' dentro del export.",
        "next": "Siguientes pasos:\n  docker compose up -d --build\n  Abre {url}/login e inicia sesión como '{user}'.\n  Luego entra a Configuración para agregar tu logo, colores y nombres de páginas.",
    },
}

# Order and headings of the generated .env file.
SECTIONS: list[tuple[str, list[str]]] = [
    ("Identity (initial defaults, editable later in Settings > Branding)", ["APP_NAME", "ORGANIZATION_NAME", "BRAND_PRIMARY_COLOR", "DEFAULT_LANGUAGE", "DATE_LOCALE", "TZ"]),
    ("Network", ["PUBLIC_BASE_URL", "HTTP_PORT", "ALLOWED_NETWORKS", "CORS_EXTRA_ORIGINS"]),
    ("First administrator and screens (only used while the database is empty)", ["INITIAL_ADMIN_USERNAME", "INITIAL_ADMIN_PASSWORD", "INITIAL_SCREENS"]),
    ("Security", ["APP_ENV", "SECRET_KEY", "ACCESS_TOKEN_MINUTES", "LOGIN_MAX_ATTEMPTS", "LOGIN_WINDOW_SECONDS"]),
    ("Database and cache", ["POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "DATABASE_URL", "REDIS_URL"]),
    ("Uploads", ["MAX_DOCUMENT_SIZE_MB", "MAX_IMAGE_SIZE_MB", "MAX_VIDEO_SIZE_MB", "MAX_LOGO_SIZE_MB", "NGINX_MAX_BODY_SIZE"]),
    (
        "File storage (docs/storage.md)",
        [
            "STORAGE_BACKEND", "BOARD_DATA_PATH", "BOARD_BACKUPS_PATH", "APP_UID", "APP_GID", "BACKUP_KEEP",
            "COMPOSE_PATH_SEPARATOR", "COMPOSE_FILE",
            "NAS_HOST", "NAS_SHARE", "NAS_USERNAME", "NAS_PASSWORD", "NAS_SMB_VERSION", "NAS_NFS_EXPORT",
            "S3_BUCKET", "S3_REGION", "S3_ENDPOINT_URL", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "S3_PREFIX",
            "S3_FORCE_PATH_STYLE", "S3_SERVE_MODE", "S3_PRESIGN_SECONDS",
        ],
    ),
    ("Emergency geocoding", ["GEOCODING_ENABLED", "GEOCODE_URL", "GEOCODE_COUNTRY_CODES", "GEOCODE_USER_AGENT"]),
]
# Written only when they have a value: an empty COMPOSE_FILE would confuse Docker Compose.
OMIT_WHEN_EMPTY = {"COMPOSE_PATH_SEPARATOR", "COMPOSE_FILE"}


def detect_ip() -> str:
    """Best-effort LAN address of this machine; no packet is sent by connecting a UDP socket."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 80))
            address = probe.getsockname()[0]
            if not address.startswith("127."):
                return address
    except OSError:
        pass
    return "192.168.1.50"


def detect_timezone() -> str:
    if os.environ.get("TZ"):
        return os.environ["TZ"]
    timezone_file = Path("/etc/timezone")
    if timezone_file.is_file():
        return timezone_file.read_text(encoding="utf-8").strip() or "UTC"
    localtime = Path("/etc/localtime")
    if localtime.is_symlink() and "zoneinfo/" in str(localtime.resolve()):
        return str(localtime.resolve()).split("zoneinfo/", 1)[1]
    return "UTC"


def default_ids() -> tuple[str, str]:
    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    if getuid and getgid and getuid() != 0:
        return str(getuid()), str(getgid())
    return "1000", "1000"


def base_values() -> dict[str, str]:
    uid, gid = default_ids()
    database_password = secrets.token_hex(32)
    return {
        "APP_NAME": "Information Board",
        "ORGANIZATION_NAME": "",
        "BRAND_PRIMARY_COLOR": "#2563eb",
        "DEFAULT_LANGUAGE": "en",
        "DATE_LOCALE": "",
        "TZ": "UTC",
        "PUBLIC_BASE_URL": f"http://{detect_ip()}",
        "HTTP_PORT": "80",
        "ALLOWED_NETWORKS": "",
        "CORS_EXTRA_ORIGINS": "",
        "INITIAL_ADMIN_USERNAME": "admin",
        "INITIAL_ADMIN_PASSWORD": "",
        "INITIAL_SCREENS": "",
        "APP_ENV": "production",
        "SECRET_KEY": secrets.token_hex(48),
        "ACCESS_TOKEN_MINUTES": "480",
        "LOGIN_MAX_ATTEMPTS": "10",
        "LOGIN_WINDOW_SECONDS": "300",
        "POSTGRES_DB": "information_board",
        "POSTGRES_USER": "information_board",
        "POSTGRES_PASSWORD": database_password,
        "DATABASE_URL": f"postgresql+psycopg://information_board:{database_password}@postgres:5432/information_board",
        "REDIS_URL": "redis://redis:6379/0",
        "MAX_DOCUMENT_SIZE_MB": "100",
        "MAX_IMAGE_SIZE_MB": "25",
        "MAX_VIDEO_SIZE_MB": "500",
        "MAX_LOGO_SIZE_MB": "5",
        "NGINX_MAX_BODY_SIZE": "600m",
        "STORAGE_BACKEND": "local",
        "BOARD_DATA_PATH": "./data",
        "BOARD_BACKUPS_PATH": "./backups",
        "APP_UID": uid,
        "APP_GID": gid,
        "BACKUP_KEEP": "0",
        "COMPOSE_PATH_SEPARATOR": "",
        "COMPOSE_FILE": "",
        "NAS_HOST": "",
        "NAS_SHARE": "",
        "NAS_USERNAME": "",
        "NAS_PASSWORD": "",
        "NAS_SMB_VERSION": "3.0",
        "NAS_NFS_EXPORT": "",
        "S3_BUCKET": "",
        "S3_REGION": "",
        "S3_ENDPOINT_URL": "",
        "S3_ACCESS_KEY_ID": "",
        "S3_SECRET_ACCESS_KEY": "",
        "S3_PREFIX": "",
        "S3_FORCE_PATH_STYLE": "false",
        "S3_SERVE_MODE": "proxy",
        "S3_PRESIGN_SECONDS": "3600",
        "GEOCODING_ENABLED": "true",
        "GEOCODE_URL": "https://nominatim.openstreetmap.org/search",
        "GEOCODE_COUNTRY_CODES": "",
        "GEOCODE_USER_AGENT": "",
    }


# Validators return the key of an error message, or None when the value is acceptable.
def check_required(value: str) -> str | None:
    return None if value else "required"


def check_url(value: str) -> str | None:
    return None if re.match(r"^https?://[^\s/]+", value) else "invalid_url"


def check_port(value: str) -> str | None:
    return None if value.isdigit() and 1 <= int(value) <= 65535 else "invalid_port"


def check_language(value: str) -> str | None:
    return None if value in ("en", "es") else "invalid_language"


def check_username(value: str) -> str | None:
    return None if re.fullmatch(r"[A-Za-z0-9_.@-]{3,80}", value) else "invalid_username"


def check_timezone(value: str) -> str | None:
    return None if re.fullmatch(r"[A-Za-z_]+(?:/[A-Za-z0-9_+-]+)*", value) else "invalid_timezone"


def check_password(value: str) -> str | None:
    return None if len(value) >= 8 and "'" not in value else "invalid_password"


def check_no_quote(value: str) -> str | None:
    return None if "'" not in value else "invalid_value"


def check_mount_value(value: str) -> str | None:
    if not value:
        return "required"
    return "invalid_comma" if "," in value else check_no_quote(value)


def format_value(value: str) -> str:
    if UNQUOTED_VALUE.fullmatch(value):
        return value
    if "'" in value:
        raise ValueError("Single quotes cannot be written to .env")
    return f"'{value}'"


def render_env(values: dict[str, str]) -> str:
    lines = [
        "# Information Board configuration generated by scripts/setup.py.",
        "# Reference: docs/configuration.md · docs/es/configuracion.md",
    ]
    for heading, keys in SECTIONS:
        lines += ["", f"# --- {heading} ---"]
        for key in keys:
            if key in OMIT_WHEN_EMPTY and not values.get(key):
                continue
            lines.append(f"{key}={format_value(values.get(key, ''))}")
    return "\n".join(lines) + "\n"


def write_env(values: dict[str, str], text: dict[str, str]) -> None:
    if ENV_PATH.exists():
        backup = ENV_PATH.with_name(f".env.backup-{datetime.now():%Y%m%d%H%M%S}")
        shutil.copy2(ENV_PATH, backup)
        ENV_PATH.unlink()
        print(text["backup_kept"].format(path=backup))
    descriptor = os.open(ENV_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_env(values))
    print(text["written"].format(path=ENV_PATH))


class Prompter:
    def __init__(self, language: str) -> None:
        self.text = TEXT[language]

    def heading(self, key: str) -> None:
        print(f"\n== {self.text[key]} ==")

    def ask(self, key: str, default: str = "", check=None) -> str:
        while True:
            suffix = f" [{default}]" if default else ""
            answer = input(f"{self.text[key]}{suffix}: ").strip() or default
            error = check(answer) if check else None
            if error is None:
                return answer
            print(f"  ! {self.text[error]}")

    def ask_secret(self, key: str, check=None, allow_empty: bool = False) -> str:
        while True:
            answer = getpass.getpass(f"{self.text[key]}: ")
            if not answer and allow_empty:
                return ""
            error = check(answer) if check else None
            if error is None:
                return answer
            print(f"  ! {self.text[error]}")

    def ask_yes_no(self, key: str) -> bool:
        answer = input(f"{self.text[key]} ({self.text['yes_no']}): ").strip().lower()
        return answer in ("y", "yes", "s", "si", "sí")


def compose_files(extra: str) -> dict[str, str]:
    return {"COMPOSE_PATH_SEPARATOR": ":", "COMPOSE_FILE": f"docker-compose.yml:{extra}"}


def interactive(values: dict[str, str]) -> tuple[dict[str, str], str | None, list[str]]:
    language = ""
    while language not in ("en", "es"):
        language = (input("Language / Idioma (en/es) [en]: ").strip().lower() or "en")[:2]
    ask = Prompter(language)
    text = ask.text
    notes: list[str] = []
    print(f"\n{text['intro']}")

    ask.heading("identity")
    values["DEFAULT_LANGUAGE"] = ask.ask("language", language, check_language)
    values["APP_NAME"] = ask.ask("app_name", values["APP_NAME"], lambda v: check_required(v) or check_no_quote(v))
    values["ORGANIZATION_NAME"] = ask.ask("organization", "", check_no_quote)
    values["TZ"] = ask.ask("timezone", detect_timezone(), check_timezone)

    ask.heading("network")
    values["HTTP_PORT"] = ask.ask("port", values["HTTP_PORT"], check_port)
    suggested_url = values["PUBLIC_BASE_URL"] + ("" if values["HTTP_PORT"] == "80" else f":{values['HTTP_PORT']}")
    values["PUBLIC_BASE_URL"] = ask.ask("base_url", suggested_url, check_url).rstrip("/")
    if "localhost" in values["PUBLIC_BASE_URL"] or "127.0.0.1" in values["PUBLIC_BASE_URL"]:
        print(f"  ! {text['localhost_warning']}")

    ask.heading("admin")
    values["INITIAL_ADMIN_USERNAME"] = ask.ask("admin_user", "admin", check_username)
    generated_password = None
    while True:
        password = ask.ask_secret("admin_password", check_password, allow_empty=True)
        if not password:
            generated_password = secrets.token_urlsafe(18)
            values["INITIAL_ADMIN_PASSWORD"] = generated_password
            break
        if ask.ask_secret("admin_repeat") == password:
            values["INITIAL_ADMIN_PASSWORD"] = password
            break
        print(f"  ! {text['mismatch']}")
    values["INITIAL_SCREENS"] = ask.ask("screens", "", check_no_quote)

    ask.heading("storage")
    print(text["storage_menu"])
    choice = ask.ask("choice", "1", lambda v: None if v in {"1", "2", "3", "4", "5"} else "invalid_choice")
    if choice == "1":
        values["BOARD_DATA_PATH"] = ask.ask("data_path", "./data", check_no_quote)
        values["BOARD_BACKUPS_PATH"] = ask.ask("backups_path", "./backups", check_no_quote)
    elif choice == "2":
        mount = ask.ask("nas_mount", "/mnt/nas/information-board", lambda v: check_required(v) or check_no_quote(v)).rstrip("/")
        values["BOARD_DATA_PATH"] = f"{mount}/data"
        values["BOARD_BACKUPS_PATH"] = f"{mount}/backups"
    elif choice == "3":
        values["NAS_HOST"] = ask.ask("nas_host", "", check_mount_value)
        values["NAS_SHARE"] = ask.ask("nas_share", "", check_mount_value)
        values["NAS_USERNAME"] = ask.ask("nas_user", "", check_mount_value)
        values["NAS_PASSWORD"] = ask.ask_secret("nas_password", check_mount_value)
        values.update(compose_files("docker-compose.nas-smb.yml"))
        notes.append(text["smb_note"])
    elif choice == "4":
        values["NAS_HOST"] = ask.ask("nas_host", "", check_mount_value)
        values["NAS_NFS_EXPORT"] = ask.ask("nas_export", "", check_mount_value).rstrip("/")
        values.update(compose_files("docker-compose.nas-nfs.yml"))
        notes.append(text["nfs_note"])
    else:
        values["STORAGE_BACKEND"] = "s3"
        values["S3_BUCKET"] = ask.ask("s3_bucket", "", lambda v: check_required(v) or check_no_quote(v))
        values["S3_REGION"] = ask.ask("s3_region", "", check_no_quote)
        values["S3_ENDPOINT_URL"] = ask.ask("s3_endpoint", "", lambda v: None if not v else check_url(v))
        values["S3_ACCESS_KEY_ID"] = ask.ask("s3_key", "", lambda v: check_required(v) or check_no_quote(v))
        values["S3_SECRET_ACCESS_KEY"] = ask.ask_secret("s3_secret", lambda v: check_required(v) or check_no_quote(v))
        values["S3_PREFIX"] = ask.ask("s3_prefix", "", check_no_quote)
        values["S3_FORCE_PATH_STYLE"] = "true" if ask.ask_yes_no("s3_path_style") else "false"

    values["GEOCODE_COUNTRY_CODES"] = ask.ask("geocoding", "", lambda v: None if re.fullmatch(r"[a-zA-Z,\s]*", v) else "invalid_value").replace(" ", "")
    return values, generated_password, notes


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the .env file for Information Board.")
    parser.add_argument("--force", action="store_true", help="replace an existing .env (a copy is kept)")
    parser.add_argument("--non-interactive", action="store_true", help="use defaults and the options below without asking")
    parser.add_argument("--language", choices=("en", "es"), default="en")
    parser.add_argument("--base-url", help="address used to reach the server, e.g. http://192.168.1.50")
    parser.add_argument("--port", default="80")
    parser.add_argument("--app-name")
    parser.add_argument("--organization")
    parser.add_argument("--timezone")
    parser.add_argument("--admin-username", default="admin")
    parser.add_argument("--admin-password", help="omit to generate a random password")
    parser.add_argument("--data-path", default="./data")
    parser.add_argument("--backups-path", default="./backups")
    args = parser.parse_args()

    if ENV_PATH.exists() and not args.force:
        print(TEXT[args.language]["exists"], file=sys.stderr)
        return 1

    values = base_values()
    notes: list[str] = []
    if args.non_interactive:
        text = TEXT[args.language]
        errors = [
            check_port(args.port),
            check_url(args.base_url) if args.base_url else None,
            check_username(args.admin_username),
            check_password(args.admin_password) if args.admin_password else None,
        ]
        if any(errors):
            print("\n".join(text[error] for error in errors if error), file=sys.stderr)
            return 2
        generated_password = None if args.admin_password else secrets.token_urlsafe(18)
        values.update(
            {
                "DEFAULT_LANGUAGE": args.language,
                "HTTP_PORT": args.port,
                "PUBLIC_BASE_URL": (args.base_url or values["PUBLIC_BASE_URL"] + ("" if args.port == "80" else f":{args.port}")).rstrip("/"),
                "APP_NAME": args.app_name or values["APP_NAME"],
                "ORGANIZATION_NAME": args.organization or "",
                "TZ": args.timezone or detect_timezone(),
                "INITIAL_ADMIN_USERNAME": args.admin_username,
                "INITIAL_ADMIN_PASSWORD": args.admin_password or generated_password,
                "BOARD_DATA_PATH": args.data_path,
                "BOARD_BACKUPS_PATH": args.backups_path,
            }
        )
    else:
        try:
            values, generated_password, notes = interactive(values)
        except (KeyboardInterrupt, EOFError):
            print()
            return 130
        text = TEXT[values["DEFAULT_LANGUAGE"]]

    write_env(values, text)
    if generated_password:
        print("\n" + text["generated_password"].format(password=generated_password))
    for note in notes:
        print("\n" + note)
    print("\n" + text["next"].format(url=values["PUBLIC_BASE_URL"], user=values["INITIAL_ADMIN_USERNAME"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
