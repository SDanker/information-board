"""Tests for the conversions that need neither LibreOffice nor ffmpeg (both only exist in
the Docker image). convert_office_document_to_pdf and transcode_video are exercised on a
real deployment with scripts/deployment_smoke.py.
"""

import csv

import pytest
from PIL import Image

from app.processing import ProcessingError, optimize_image, parse_spreadsheet, render_pdf_pages


def test_optimize_image_produces_page_and_thumbnail(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (3000, 2000), color=(10, 20, 30)).save(source)

    assets = optimize_image(source, tmp_path / "out")

    assert {asset.kind for asset in assets} == {"PAGE", "THUMBNAIL"}
    page = next(a for a in assets if a.kind == "PAGE")
    assert page.width == 1920  # resized to the maximum allowed dimension
    assert page.path.exists()
    thumb = next(a for a in assets if a.kind == "THUMBNAIL")
    assert thumb.width <= 480
    assert thumb.path.exists()


def test_render_pdf_pages_one_webp_per_page(tmp_path):
    import fitz

    pdf_path = tmp_path / "doc.pdf"
    document = fitz.open()
    for _ in range(3):
        page = document.new_page()
        page.insert_text((72, 72), "Test page")
    document.save(pdf_path)
    document.close()

    assets = render_pdf_pages(pdf_path, tmp_path / "out")

    pages = [a for a in assets if a.kind == "PAGE"]
    assert len(pages) == 3
    assert [a.page_number for a in pages] == [1, 2, 3]
    assert all(a.path.exists() for a in pages)
    assert any(a.kind == "THUMBNAIL" for a in assets)


def test_render_pdf_pages_rejects_too_many_pages(tmp_path, monkeypatch):
    import fitz

    import app.processing as processing_module

    monkeypatch.setattr(processing_module, "MAX_PDF_PAGES", 2)
    pdf_path = tmp_path / "doc.pdf"
    document = fitz.open()
    for _ in range(3):
        document.new_page()
    document.save(pdf_path)
    document.close()

    with pytest.raises(ProcessingError, match="maximum allowed is 2"):
        render_pdf_pages(pdf_path, tmp_path / "out")


def test_parse_spreadsheet_csv(tmp_path):
    source = tmp_path / "datos.csv"
    with open(source, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Nombre", "Cargo"])
        writer.writerow(["Ana", "Capitán"])
        writer.writerow(["Luis", "Teniente"])

    result = parse_spreadsheet(source)

    assert result["header"] == ["Nombre", "Cargo"]
    assert result["rows"] == [["Ana", "Capitán"], ["Luis", "Teniente"]]


def test_parse_spreadsheet_xlsx(tmp_path):
    import openpyxl

    source = tmp_path / "datos.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Turnos"
    sheet.append(["Fecha", "Responsable"])
    sheet.append(["2026-09-14", "Ana"])
    workbook.save(source)

    result = parse_spreadsheet(source)

    assert result["sheet_name"] == "Turnos"
    assert result["header"] == ["Fecha", "Responsable"]
    assert result["rows"] == [["2026-09-14", "Ana"]]
