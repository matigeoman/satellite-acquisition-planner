from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ScientificReportConfig:
    """Konfiguracja pakietu raportowego generowanego z bieżącej sesji."""

    title: str = "Raport z planowania akwizycji satelitarnych"
    author: str = ""
    institution: str = "Wojskowa Akademia Techniczna"
    description: str = ""
    include_raw_tables: bool = True
    include_methodology: bool = True
    include_limitations: bool = True
    include_stk_validation: bool = True
    include_benchmarks: bool = True

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title nie może być pusty")
        if len(self.title) > 250:
            raise ValueError("title nie może przekraczać 250 znaków")
        if len(self.author) > 200:
            raise ValueError("author nie może przekraczać 200 znaków")
        if len(self.institution) > 250:
            raise ValueError("institution nie może przekraczać 250 znaków")
        if len(self.description) > 4000:
            raise ValueError("description nie może przekraczać 4000 znaków")


@dataclass(frozen=True)
class ScientificReportSnapshot:
    """Znormalizowane dane wykorzystywane przez wszystkie renderery."""

    generated_at_utc: datetime
    title: str
    author: str
    institution: str
    description: str
    include_methodology: bool
    include_limitations: bool
    include_stk_validation: bool
    include_benchmarks: bool
    project_name: str
    project_id: str
    application_version: str
    overview_metrics: tuple[dict[str, Any], ...]
    satellite_rows: tuple[dict[str, Any], ...]
    request_rows: tuple[dict[str, Any], ...]
    access_rows: tuple[dict[str, Any], ...]
    opportunity_rows: tuple[dict[str, Any], ...]
    schedule_rows: tuple[dict[str, Any], ...]
    request_diagnostic_rows: tuple[dict[str, Any], ...]
    satellite_kpi_rows: tuple[dict[str, Any], ...]
    benchmark_rows: tuple[dict[str, Any], ...]
    benchmark_summary_rows: tuple[dict[str, Any], ...]
    schedule_history_rows: tuple[dict[str, Any], ...]
    stk_access_rows: tuple[dict[str, Any], ...]
    stk_aer_rows: tuple[dict[str, Any], ...]
    narrative: dict[str, str]
    limitations: tuple[str, ...]
    warnings: tuple[str, ...]

    def table_map(self) -> dict[str, tuple[dict[str, Any], ...]]:
        return {
            "satellites": self.satellite_rows,
            "requests": self.request_rows,
            "access_windows": self.access_rows,
            "opportunities": self.opportunity_rows,
            "schedule_entries": self.schedule_rows,
            "request_diagnostics": self.request_diagnostic_rows,
            "satellite_kpis": self.satellite_kpi_rows,
            "benchmark_runs": self.benchmark_rows,
            "benchmark_summary": self.benchmark_summary_rows,
            "schedule_history": self.schedule_history_rows,
            "stk_access_matches": self.stk_access_rows,
            "stk_aer_matches": self.stk_aer_rows,
        }


@dataclass(frozen=True)
class ScientificReportPackage:
    """Gotowy pakiet ZIP wraz z najważniejszymi artefaktami osobno."""

    archive_bytes: bytes
    html_bytes: bytes
    docx_bytes: bytes
    xlsx_bytes: bytes
    json_bytes: bytes
    suggested_filename: str
    included_files: tuple[str, ...]
    warnings: tuple[str, ...]
    generated_at_utc: datetime

    @property
    def size_bytes(self) -> int:
        return len(self.archive_bytes)
