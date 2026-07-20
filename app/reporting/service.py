from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import asdict
from typing import Any, Mapping

from app.projects.codec import jsonable
from app.reporting.collector import collect_report_snapshot
from app.reporting.docx_renderer import render_docx
from app.reporting.figures import build_report_figures
from app.reporting.html_renderer import render_html
from app.reporting.models import (
    ScientificReportConfig,
    ScientificReportPackage,
    ScientificReportSnapshot,
)
from app.reporting.xlsx_renderer import render_xlsx


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return normalized or "raport-satplan"


def _csv_bytes(rows: tuple[dict[str, Any], ...]) -> bytes:
    buffer = io.StringIO(newline="")
    if not rows:
        buffer.write("Brak danych\n")
        return buffer.getvalue().encode("utf-8-sig")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def _snapshot_json(snapshot: ScientificReportSnapshot) -> bytes:
    payload = {
        **asdict(snapshot),
        "generated_at_utc": snapshot.generated_at_utc.isoformat(),
    }
    return json.dumps(
        jsonable(payload),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")


class ScientificReportService:
    """Buduje spójny pakiet HTML, DOCX, XLSX, CSV i JSON."""

    def build(
        self,
        state: Mapping[str, Any],
        *,
        config: ScientificReportConfig,
    ) -> ScientificReportPackage:
        snapshot = collect_report_snapshot(state, config=config)
        figures = build_report_figures(snapshot)
        html_bytes = render_html(snapshot, figures)
        docx_bytes = render_docx(snapshot, figures)
        xlsx_bytes = render_xlsx(snapshot)
        json_bytes = _snapshot_json(snapshot)

        files: dict[str, bytes] = {
            "report.html": html_bytes,
            "report.docx": docx_bytes,
            "results.xlsx": xlsx_bytes,
            "report.json": json_bytes,
            "README.txt": (
                "Satellite Acquisition Planner — pakiet raportu naukowego\n\n"
                "report.html  — samodzielny raport do przeglądarki i druku\n"
                "report.docx  — edytowalny dokument do pracy dyplomowej\n"
                "results.xlsx — komplet tabel i wyników\n"
                "tables/      — dane CSV w kodowaniu UTF-8 z BOM\n"
                "figures/     — statyczne wykresy PNG\n"
                "report.json  — pełny snapshot raportowy\n"
            ).encode("utf-8"),
        }
        for name, raw in figures.items():
            files[f"figures/{name}"] = raw
        if config.include_raw_tables:
            for name, rows in snapshot.table_map().items():
                files[f"tables/{name}.csv"] = _csv_bytes(rows)
            files["tables/overview_metrics.csv"] = _csv_bytes(
                snapshot.overview_metrics
            )

        archive = io.BytesIO()
        with zipfile.ZipFile(
            archive,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as output:
            for path, raw in sorted(files.items()):
                output.writestr(path, raw)

        filename = f"{_safe_name(snapshot.project_name)}-raport.zip"
        return ScientificReportPackage(
            archive_bytes=archive.getvalue(),
            html_bytes=html_bytes,
            docx_bytes=docx_bytes,
            xlsx_bytes=xlsx_bytes,
            json_bytes=json_bytes,
            suggested_filename=filename,
            included_files=tuple(sorted(files)),
            warnings=snapshot.warnings,
            generated_at_utc=snapshot.generated_at_utc,
        )
