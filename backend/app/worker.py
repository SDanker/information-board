"""Background worker: converts uploaded files by polling the processing_jobs table.

Polling the database (instead of a separate message queue) keeps the architecture simple
and makes jobs survive restarts: a job is just a row with a status.
"""

import json
import logging
import tempfile
import time
from pathlib import Path

from redis import Redis
from sqlalchemy import select

from app.config import get_settings
from app.content_paths import derived_prefix
from app.database import SessionLocal
from app.i18n import _
from app.models import Asset, Content, ContentVersion, ProcessingJob, utc_now
from app.processing import (
    DerivedAsset,
    ProcessingError,
    convert_office_document_to_pdf,
    optimize_image,
    parse_spreadsheet,
    render_pdf_pages,
    transcode_video,
)
from app.realtime import publish_event
from app.storage import get_storage

logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","service":"worker","message":%(message)s}')
logger = logging.getLogger("worker")

HEARTBEAT_KEY = "information-board:worker:heartbeat"
IDLE_POLL_SECONDS = 3
BUSY_POLL_SECONDS = 0.3


def _log(message: str, **fields) -> None:
    logger.info(json.dumps({"event": message, **fields}, ensure_ascii=False))


def _run_conversion(job_type: str, source_path: Path, work_dir: Path) -> tuple[list[DerivedAsset], dict]:
    suffix = source_path.suffix.lower()
    if job_type == "OPTIMIZE_IMAGE":
        return optimize_image(source_path, work_dir), {}
    if job_type == "TRANSCODE_VIDEO":
        return transcode_video(source_path, work_dir), {}
    if job_type == "CONVERT_DOCUMENT":
        pdf_path = source_path if suffix == ".pdf" else convert_office_document_to_pdf(source_path, work_dir)
        return render_pdf_pages(pdf_path, work_dir), {}
    if job_type == "CONVERT_PRESENTATION":
        pdf_path = convert_office_document_to_pdf(source_path, work_dir)
        return render_pdf_pages(pdf_path, work_dir), {}
    if job_type == "CONVERT_SPREADSHEET":
        table = parse_spreadsheet(source_path)
        try:
            pdf_path = convert_office_document_to_pdf(source_path, work_dir)
            assets = render_pdf_pages(pdf_path, work_dir)
        except ProcessingError:
            # The table view is what matters; it must not depend on the printable PDF.
            assets = []
        return assets, {"table": table}
    raise ProcessingError(_("Unknown job type: {job_type}", job_type=job_type))


def _claim_next_job(db) -> ProcessingJob | None:
    # A single worker process, so no row-level lock (FOR UPDATE) is needed; it would not
    # be portable to SQLite, which the tests use.
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.status == "QUEUED").order_by(ProcessingJob.created_at).limit(1))
    if job is None:
        return None
    job.status = "RUNNING"
    job.started_at = utc_now()
    job.attempts += 1
    db.commit()
    return job


def process_one_job() -> bool:
    """Process the oldest queued job. Returns False when there was nothing to do."""
    storage = get_storage()
    with SessionLocal() as db:
        job = _claim_next_job(db)
        if job is None:
            return False
        version = db.get(ContentVersion, job.content_version_id)
        content = db.get(Content, version.content_id) if version else None
        if version is None or content is None:
            job.status = "FAILED"
            job.error_message = _("The version or its content no longer exists")
            job.finished_at = utc_now()
            db.commit()
            return True

        source_asset = db.scalar(select(Asset).where(Asset.content_version_id == version.id, Asset.kind == "SOURCE"))
        _log("job_started", job_id=str(job.id), job_type=job.job_type, content_id=str(content.id), attempt=job.attempts)
        try:
            if source_asset is None:
                raise ProcessingError(_("The original file for this version was not found"))
            with tempfile.TemporaryDirectory(prefix="board-job-") as tmp:
                tmp_path = Path(tmp)
                local_source = tmp_path / "source" / Path(source_asset.storage_path).name
                storage.download_to(source_asset.storage_path, local_source)

                derived, payload_updates = _run_conversion(job.job_type, local_source, tmp_path / "derived")

                prefix = derived_prefix(content.id, version.id)
                for item in derived:
                    relative_path = f"{prefix}/{item.path.name}"
                    size = storage.save_local_file(relative_path, item.path)
                    db.add(
                        Asset(
                            content_version_id=version.id,
                            kind=item.kind,
                            page_number=item.page_number,
                            storage_path=relative_path,
                            mime_type=item.mime_type,
                            width=item.width,
                            height=item.height,
                            duration_seconds=int(item.duration_seconds) if item.duration_seconds else None,
                            size_bytes=size,
                        )
                    )

            version.payload = {**version.payload, **payload_updates}
            version.status = "READY"
            version.published_at = utc_now()
            version.error_message = None
            content.published_version_id = version.id
            job.status = "DONE"
            job.finished_at = utc_now()
            db.commit()
            _log("job_done", job_id=str(job.id), content_id=str(content.id))
            publish_event({"target": "all_screens", "type": "content_published", "content_id": str(content.id)})
            publish_event({"target": "admin", "type": "content_changed"})
        except ProcessingError as exc:
            db.rollback()
            _finalize_failure(db, job, version, str(exc))
        except Exception:
            db.rollback()
            logger.exception("Unexpected error processing job %s", job.id)
            _finalize_failure(db, job, version, _("Internal error during processing"))
        return True


def _finalize_failure(db, job: ProcessingJob, version: ContentVersion, message: str) -> None:
    # No automatic retry: a failed job stays FAILED until someone retries it explicitly
    # (POST /content/{id}/versions/{version_id}/retry). `attempts` is informational only.
    job.status = "FAILED"
    job.error_message = message[:2000]
    job.finished_at = utc_now()
    version.status = "FAILED"
    version.error_message = message[:2000]
    db.commit()
    publish_event({"target": "admin", "type": "content_changed"})


def run() -> None:
    redis = Redis.from_url(get_settings().redis_url)
    _log("worker_started")
    while True:
        redis.set(HEARTBEAT_KEY, str(time.time()), ex=30)
        try:
            processed = process_one_job()
        except Exception:
            logger.exception("Unexpected error in the worker loop")
            processed = False
        time.sleep(BUSY_POLL_SECONDS if processed else IDLE_POLL_SECONDS)


if __name__ == "__main__":
    run()
