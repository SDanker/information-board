FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# libreoffice-* converts DOCX/PPTX/XLSX to PDF, ffmpeg transcodes video, and the fonts avoid
# blank text when documents contain accents or symbols. The backend and the worker share this
# image: the backend does not use these tools, but a single image keeps builds simple.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libreoffice-writer libreoffice-calc libreoffice-impress \
    ffmpeg \
    fonts-dejavu fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# The process runs as a non-root user whose uid/gid should match the owner of the data and
# backups folders on the host or NAS (APP_UID/APP_GID in .env, default 1000). HOME must be
# writable: headless LibreOffice creates its profile in $HOME/.config on the first conversion.
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --gid "${APP_GID}" appuser \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
ENV HOME=/home/appuser
USER appuser

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
