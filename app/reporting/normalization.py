from __future__ import annotations

import re
from dataclasses import replace

from app.reporting.models import ScientificReportSnapshot


_ACQUISITION_PATTERN = re.compile(r"\b(\d+) akwizycji\b")


def polish_count(
    value: int,
    *,
    singular: str,
    paucal: str,
    plural: str,
) -> str:
    """Zwraca polską formę rzeczownika odpowiednią dla liczebnika."""

    absolute = abs(int(value))
    last_two = absolute % 100
    last = absolute % 10
    if absolute == 1:
        form = singular
    elif 12 <= last_two <= 14:
        form = plural
    elif 2 <= last <= 4:
        form = paucal
    else:
        form = plural
    return f"{value} {form}"


def _normalize_text(value: str) -> str:
    def replace_acquisition(match: re.Match[str]) -> str:
        count = int(match.group(1))
        return polish_count(
            count,
            singular="akwizycję",
            paucal="akwizycje",
            plural="akwizycji",
        )

    normalized = _ACQUISITION_PATTERN.sub(replace_acquisition, value)
    return normalized.replace(
        "z uwzględnieniem zasobów, downlinku i przeorientowań.",
        "z uwzględnieniem skonfigurowanych ograniczeń planistycznych.",
    )


def normalize_report_snapshot(
    snapshot: ScientificReportSnapshot,
) -> ScientificReportSnapshot:
    """Normalizuje teksty wspólne dla JSON, HTML, DOCX i XLSX."""

    narrative = {
        key: _normalize_text(value)
        for key, value in snapshot.narrative.items()
    }
    return replace(snapshot, narrative=narrative)


__all__ = ["normalize_report_snapshot", "polish_count"]
