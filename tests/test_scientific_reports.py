from __future__ import annotations

import io
import json
import zipfile

from app.reporting import ScientificReportConfig, ScientificReportService


def test_report_package_contains_all_primary_formats() -> None:
    service = ScientificReportService()
    result = service.build(
        {},
        config=ScientificReportConfig(
            title="Raport testowy SatPlan",
            author="Autor testowy",
        ),
    )

    assert result.archive_bytes.startswith(b"PK")
    assert result.docx_bytes.startswith(b"PK")
    assert result.xlsx_bytes.startswith(b"PK")
    assert b"Raport testowy SatPlan" in result.html_bytes
    assert result.suggested_filename.endswith("-raport.zip")
    assert result.warnings

    with zipfile.ZipFile(io.BytesIO(result.archive_bytes)) as archive:
        names = set(archive.namelist())
        assert {
            "report.html",
            "report.docx",
            "results.xlsx",
            "report.json",
            "README.txt",
            "tables/overview_metrics.csv",
        }.issubset(names)
        payload = json.loads(archive.read("report.json").decode("utf-8"))
        assert payload["title"] == "Raport testowy SatPlan"
        assert payload["author"] == "Autor testowy"


def test_office_documents_are_valid_ooxml_archives() -> None:
    result = ScientificReportService().build(
        {},
        config=ScientificReportConfig(title="Walidacja OOXML"),
    )

    with zipfile.ZipFile(io.BytesIO(result.docx_bytes)) as document:
        assert "word/document.xml" in document.namelist()
        assert "[Content_Types].xml" in document.namelist()

    with zipfile.ZipFile(io.BytesIO(result.xlsx_bytes)) as workbook:
        assert "xl/workbook.xml" in workbook.namelist()
        assert "[Content_Types].xml" in workbook.namelist()


def test_raw_tables_can_be_disabled() -> None:
    result = ScientificReportService().build(
        {},
        config=ScientificReportConfig(
            title="Raport bez CSV",
            include_raw_tables=False,
        ),
    )

    assert not any(path.startswith("tables/") for path in result.included_files)
    assert "report.html" in result.included_files
    assert "results.xlsx" in result.included_files
