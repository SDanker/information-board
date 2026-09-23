"""Spanish translations of backend messages, keyed by the exact English source text.

``tests/test_i18n.py`` fails when a message wrapped in ``_()`` has no entry here, or when
a translation does not keep the same ``{placeholders}``.
"""

MESSAGES: dict[str, str] = {
    # Storage
    "Invalid storage path: {path}": "Ruta de almacenamiento inválida: {path}",
    "The path is outside the storage directory": "La ruta está fuera del directorio de almacenamiento",
    "S3_BUCKET is required when STORAGE_BACKEND=s3": "S3_BUCKET es obligatorio cuando STORAGE_BACKEND=s3",
    # Branding
    "The application name cannot be empty": "El nombre de la aplicación no puede estar vacío",
    "Enter a color in #RRGGBB format": "Ingrese un color en formato #RRGGBB",
    "Unknown time zone: {timezone}": "Zona horaria desconocida: {timezone}",
    "Unknown page: {page}": "Página desconocida: {page}",
    "Page names can have at most {limit} characters": "Los nombres de página pueden tener como máximo {limit} caracteres",
    "Logo format not allowed. Use PNG, JPG, WEBP or GIF.": "Formato de logo no permitido. Use PNG, JPG, WEBP o GIF.",
    "The logo exceeds the {limit} MB limit": "El logo supera el límite de {limit} MB",
    "No logo has been uploaded": "No se ha subido ningún logo",
    # Authentication and users
    "Your session is invalid or has expired": "Su sesión no es válida o expiró",
    "You do not have permission to perform this action": "No tiene permisos para realizar esta acción",
    "Too many attempts. Wait a few minutes before trying again.": "Demasiados intentos. Espere unos minutos antes de volver a intentar.",
    "Incorrect username or password": "Usuario o contraseña incorrectos",
    "At least one active administrator must remain": "Debe quedar al menos un administrador activo",
    "A user with that name already exists": "Ya existe un usuario con ese nombre",
    "User not found": "Usuario no encontrado",
    "You cannot delete your own account": "No puede eliminar su propia cuenta",
    "The current password is incorrect": "La contraseña actual no es correcta",
    "Invalid role: {role}": "Rol inválido: {role}",
    "Administrative access is not allowed from this network": "Acceso administrativo no permitido desde esta red",
    # Screens
    "Screen not found": "Pantalla no encontrada",
    "Screen not found or inactive": "Pantalla no encontrada o inactiva",
    "A screen with that slug already exists": "Ya existe una pantalla con ese identificador (slug)",
    "The slug may only contain lowercase letters, numbers and hyphens": "El slug sólo admite minúsculas, números y guiones",
    "The resolution must use the WIDTHxHEIGHT format, e.g. 1920x1080": "La resolución debe tener el formato ANCHOxALTO, p. ej. 1920x1080",
    # Content and uploads
    "Content not found": "Contenido no encontrado",
    "Content of type {kind} cannot be created from this endpoint": "El contenido de tipo {kind} no se puede crear desde este endpoint",
    "Announcements require the 'announcement' field": "Los anuncios requieren el campo 'announcement'",
    "Invalid content type: {kind}": "Tipo de contenido inválido: {kind}",
    "Invalid content type for upload: {kind}": "Tipo de contenido inválido para subida: {kind}",
    "Invalid visibility: {visibility}": "Visibilidad inválida: {visibility}",
    "Extension not allowed for {kind}. Allowed formats: {formats}": "Extensión no admitida para {kind}. Formatos permitidos: {formats}",
    "The file is empty": "El archivo está vacío",
    "The file exceeds the {limit} MB limit for {kind}": "El archivo supera el límite de {limit} MB para {kind}",
    "The file is not a valid image": "El archivo no es una imagen válida",
    "Only announcements and calendars accept new versions through this endpoint": "Sólo los anuncios y calendarios admiten nuevas versiones por este endpoint",
    "Version not found": "Versión no encontrada",
    "Only failed versions can be retried": "Sólo se pueden reintentar versiones con error",
    "There is no processing job for this version": "No hay un trabajo de conversión asociado a esta versión",
    "File not found": "Archivo no encontrado",
    "Only pages of a document or presentation accept a custom duration": "Sólo las páginas de un documento o presentación admiten una duración personalizada",
    # Publication periods
    "Archived publications cannot be added to a playlist; restore it first": "Las publicaciones archivadas no se pueden agregar a una playlist; restáuralas primero",
    "The publication must end after it starts": "La publicación debe terminar después de su inicio",
    "Weekdays must be numbers between 0 (Monday) and 6 (Sunday)": "Los días deben ser números entre 0 (lunes) y 6 (domingo)",
    "Invalid date and time: {value}": "Fecha y hora no válidas: {value}",
    # Calendars
    "Calendars require the 'calendar' field": "Los calendarios requieren el campo 'calendar'",
    "Calendar not found": "Calendario no encontrado",
    "Enter the calendar address (ICS), starting with https://": "Ingrese la dirección del calendario (ICS), que comienza con https://",
    "The calendar file is too large": "El archivo del calendario es demasiado grande",
    "The calendar link answered with an error ({status})": "El enlace del calendario respondió con un error ({status})",
    "The calendar link could not be reached": "No fue posible acceder al enlace del calendario",
    "The file is not a valid calendar (ICS)": "El archivo no es un calendario válido (ICS)",
    # Playlists
    "Playlist not found": "Playlist no encontrada",
    "Item not found": "Elemento no encontrado",
    "The list must include exactly the current playlist items": "La lista debe incluir exactamente los elementos actuales de la playlist",
    "days_of_week must contain values between 0 (Monday) and 6 (Sunday)": "days_of_week debe contener valores entre 0 (lunes) y 6 (domingo)",
    # Sharing and library
    "Photo {number}": "Foto {number}",
    "Video": "Video",
    "This content is private; change its visibility to share it": "El contenido es privado; cambie su visibilidad para compartirlo",
    "Invalid or expired link": "Enlace no válido o vencido",
    "Nothing to download yet": "Nada para descargar todavía",
    "The public library is disabled": "La biblioteca pública está desactivada",
    # Emergencies
    "Featured event not found": "Acto destacado no encontrado",
    "The featured event has no published version": "El acto destacado no tiene una versión publicada",
    "Photo extension not allowed: {extension}": "Extensión de foto no admitida: {extension}",
    "Photo is too large: {name}": "Foto demasiado grande: {name}",
    "Video extension not allowed: {extension}": "Extensión de video no admitida: {extension}",
    "The video exceeds the configured size limit": "El video supera el límite de tamaño configurado",
    # Worker and conversions
    "Unknown job type: {job_type}": "Tipo de trabajo desconocido: {job_type}",
    "The version or its content no longer exists": "La versión o el contenido asociado ya no existe",
    "The original file for this version was not found": "No se encontró el archivo original de esta versión",
    "Internal error during processing": "Error interno durante el procesamiento",
    "'{name}' is not installed in this environment. This conversion only works inside the backend/worker container (see backend/Dockerfile).": "'{name}' no está instalado en este entorno. Esta conversión sólo funciona dentro del contenedor backend/worker (ver backend/Dockerfile).",
    "LibreOffice could not convert the document: {details}": "LibreOffice no pudo convertir el documento: {details}",
    "The PDF has no pages": "El PDF no tiene páginas",
    "The document has {pages} pages; the maximum allowed is {maximum}": "El documento tiene {pages} páginas; el máximo admitido es {maximum}",
    "ffmpeg could not transcode the video: {details}": "ffmpeg no pudo transcodificar el video: {details}",
    "The sheet has {rows} rows; the maximum allowed is {maximum}": "La hoja tiene {rows} filas; el máximo admitido es {maximum}",
}
