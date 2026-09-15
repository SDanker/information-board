"""Validation rules per uploaded content type: accepted extensions, size limit and the
conversion job it triggers. Kept in one place so the upload endpoints never duplicate it."""

from dataclasses import dataclass

from app.config import Settings


@dataclass(frozen=True)
class UploadRule:
    job_type: str
    extensions: frozenset[str]
    max_size_attr: str
    mime_prefix: str | None = None


UPLOAD_RULES: dict[str, UploadRule] = {
    "IMAGE": UploadRule("OPTIMIZE_IMAGE", frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}), "max_image_size_mb", "image/"),
    "VIDEO": UploadRule("TRANSCODE_VIDEO", frozenset({".mp4", ".mov", ".avi", ".mkv", ".webm"}), "max_video_size_mb", "video/"),
    "DOCUMENT": UploadRule("CONVERT_DOCUMENT", frozenset({".pdf", ".doc", ".docx", ".odt", ".txt", ".rtf"}), "max_document_size_mb"),
    "EXCEL": UploadRule("CONVERT_SPREADSHEET", frozenset({".xls", ".xlsx", ".csv"}), "max_document_size_mb"),
    "PPTX": UploadRule("CONVERT_PRESENTATION", frozenset({".ppt", ".pptx", ".odp"}), "max_document_size_mb"),
}


def max_size_bytes(settings: Settings, rule: UploadRule) -> int:
    return int(getattr(settings, rule.max_size_attr)) * 1024 * 1024
