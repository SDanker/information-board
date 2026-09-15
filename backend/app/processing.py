"""Conversion of uploaded files into what the screens actually display.

Every function is a pure operation on files (receives paths, returns paths plus metadata)
so it can be tested without a database or a queue. The module is split by the tool each
conversion needs:

- Images (Pillow) and PDF to WebP (PyMuPDF) are pure Python packages and work anywhere.
- DOCX/PPTX/XLSX to PDF needs the ``soffice`` binary (headless LibreOffice).
- Video needs the ``ffmpeg`` binary.

Both binaries are only installed in the backend/worker Docker image (see Dockerfile);
when they are missing, ProcessingError explains it instead of a confusing subprocess trace.
"""

from __future__ import annotations

import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from app.i18n import _

MAX_PAGE_DIMENSION = 1920
THUMBNAIL_DIMENSION = 480
WEBP_QUALITY = 82
PDF_RENDER_DPI = 150
MAX_PDF_PAGES = 60  # sensible limit for a screen; avoids gigantic documents


class ProcessingError(Exception):
    pass


@dataclass
class DerivedAsset:
    kind: str
    page_number: int | None
    path: Path
    mime_type: str
    width: int | None
    height: int | None
    duration_seconds: float | None = None


def _require_binary(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise ProcessingError(
            _("'{name}' is not installed in this environment. This conversion only works inside the backend/worker container (see backend/Dockerfile).", name=name)
        )
    return path


def optimize_image(source: Path, dest_dir: Path) -> list[DerivedAsset]:
    """Shrink an image to a reasonably sized WebP plus a thumbnail."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as raw:
        image = ImageOps.exif_transpose(raw.convert("RGB"))
    assets: list[DerivedAsset] = []

    full = image.copy()
    full.thumbnail((MAX_PAGE_DIMENSION, MAX_PAGE_DIMENSION), Image.LANCZOS)
    full_path = dest_dir / f"page-1-{uuid.uuid4().hex[:8]}.webp"
    full.save(full_path, "WEBP", quality=WEBP_QUALITY)
    assets.append(DerivedAsset("PAGE", 1, full_path, "image/webp", full.width, full.height))

    thumb = image.copy()
    thumb.thumbnail((THUMBNAIL_DIMENSION, THUMBNAIL_DIMENSION), Image.LANCZOS)
    thumb_path = dest_dir / f"thumb-{uuid.uuid4().hex[:8]}.webp"
    thumb.save(thumb_path, "WEBP", quality=WEBP_QUALITY)
    assets.append(DerivedAsset("THUMBNAIL", None, thumb_path, "image/webp", thumb.width, thumb.height))
    return assets


def convert_office_document_to_pdf(source: Path, dest_dir: Path) -> Path:
    """DOC/DOCX/TXT/ODT/XLSX/PPTX to PDF with headless LibreOffice."""
    soffice = _require_binary("soffice")
    dest_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [soffice, "--headless", "--norestore", "--convert-to", "pdf", "--outdir", str(dest_dir), str(source)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    produced = dest_dir / f"{source.stem}.pdf"
    if result.returncode != 0 or not produced.exists():
        details = result.stderr[-800:] or result.stdout[-800:]
        raise ProcessingError(_("LibreOffice could not convert the document: {details}", details=details))
    return produced


def render_pdf_pages(pdf_path: Path, dest_dir: Path) -> list[DerivedAsset]:
    """PDF to one WebP image per page, plus a thumbnail of the first page."""
    import fitz  # PyMuPDF; imported lazily so importing this module stays cheap

    dest_dir.mkdir(parents=True, exist_ok=True)
    assets: list[DerivedAsset] = []
    zoom = PDF_RENDER_DPI / 72
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(pdf_path) as document:
        if document.page_count == 0:
            raise ProcessingError(_("The PDF has no pages"))
        if document.page_count > MAX_PDF_PAGES:
            raise ProcessingError(
                _("The document has {pages} pages; the maximum allowed is {maximum}", pages=document.page_count, maximum=MAX_PDF_PAGES)
            )
        for index in range(document.page_count):
            pixmap = document[index].get_pixmap(matrix=matrix)
            page_path = dest_dir / f"page-{index + 1}-{uuid.uuid4().hex[:8]}.webp"
            pixmap.pil_save(page_path, "WEBP", quality=WEBP_QUALITY)
            assets.append(DerivedAsset("PAGE", index + 1, page_path, "image/webp", pixmap.width, pixmap.height))
            if index == 0:
                thumb_pixmap = document[index].get_pixmap(matrix=fitz.Matrix(zoom * 0.3, zoom * 0.3))
                thumb_path = dest_dir / f"thumb-{uuid.uuid4().hex[:8]}.webp"
                thumb_pixmap.pil_save(thumb_path, "WEBP", quality=WEBP_QUALITY)
                assets.append(DerivedAsset("THUMBNAIL", None, thumb_path, "image/webp", thumb_pixmap.width, thumb_pixmap.height))
    return assets


def transcode_video(source: Path, dest_dir: Path) -> list[DerivedAsset]:
    """Video to H.264/AAC MP4 suitable for silent autoplay on TVs, plus a thumbnail."""
    ffmpeg = _require_binary("ffmpeg")
    dest_dir.mkdir(parents=True, exist_ok=True)
    video_path = dest_dir / f"video-{uuid.uuid4().hex[:8]}.mp4"
    result = subprocess.run(
        [
            ffmpeg, "-y", "-i", str(source),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-vf", "scale='min(1920,iw)':-2",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        timeout=900,
    )
    if result.returncode != 0 or not video_path.exists():
        raise ProcessingError(_("ffmpeg could not transcode the video: {details}", details=result.stderr[-800:]))

    probe = subprocess.run([ffmpeg, "-i", str(video_path)], capture_output=True, text=True, timeout=30)
    duration = _parse_ffmpeg_duration(probe.stderr)

    thumb_path = dest_dir / f"thumb-{uuid.uuid4().hex[:8]}.webp"
    subprocess.run(
        [ffmpeg, "-y", "-i", str(video_path), "-ss", "00:00:01", "-frames:v", "1", str(thumb_path)],
        capture_output=True,
        timeout=30,
    )
    assets = [DerivedAsset("VIDEO", None, video_path, "video/mp4", None, None, duration_seconds=duration)]
    if thumb_path.exists():
        assets.append(DerivedAsset("THUMBNAIL", None, thumb_path, "image/webp", None, None))
    return assets


def _parse_ffmpeg_duration(stderr: str) -> float | None:
    for line in stderr.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            timestamp = line.split(",")[0].removeprefix("Duration:").strip()
            try:
                hours, minutes, seconds = timestamp.split(":")
                return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            except ValueError:
                return None
    return None


def parse_spreadsheet(source: Path, max_rows: int = 2000) -> dict:
    """XLS/XLSX/CSV to plain JSON rows for the paginated table view."""
    import csv

    if source.suffix.lower() == ".csv":
        with open(source, newline="", encoding="utf-8-sig", errors="replace") as handle:
            rows = [row for row in csv.reader(handle)]
        sheet_name = source.stem
    else:
        import openpyxl

        workbook = openpyxl.load_workbook(source, data_only=True, read_only=True)
        sheet = workbook.active
        sheet_name = sheet.title
        rows = [[("" if cell is None else str(cell)) for cell in row] for row in sheet.iter_rows(values_only=True)]
        workbook.close()

    if len(rows) > max_rows:
        raise ProcessingError(_("The sheet has {rows} rows; the maximum allowed is {maximum}", rows=len(rows), maximum=max_rows))
    header, *body = rows if rows else ([], [])
    return {"sheet_name": sheet_name, "header": header, "rows": body}
