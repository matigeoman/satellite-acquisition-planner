from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from app.reporting.models import ScientificReportSnapshot


_ACQUISITION_PATTERN = re.compile(r"\b(\d+) akwizycji\b")
_LEGACY_CONSTRAINTS_TEXT = (
    "z uwzględnieniem zasobów, downlinku i przeorientowań."
)


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


def _join_polish(items: list[str]) -> str:
    if not items:
        return "skonfigurowanych ograniczeń planistycznych"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" oraz {items[-1]}"


def _planning_constraints_text(planning: Any | None) -> str:
    options = getattr(planning, "options", None)
    if options is None:
        return "z uwzględnieniem skonfigurowanych ograniczeń planistycznych."

    constraints = ["ograniczeń pamięci"]
    if getattr(options, "enable_downlink_planning", False):
        constraints.append("planowania downlinku")
        if getattr(options, "require_full_downlink", False):
            constraints.append(
                "pełnego opróżnienia pamięci do końca horyzontu"
            )
    if getattr(options, "use_dynamic_transition_model", False):
        constraints.append("dynamicznego modelu przeorientowań")

    return f"z uwzględnieniem {_join_polish(constraints)}."


def _normalize_text(value: str, *, planning: Any | None) -> str:
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
        _LEGACY_CONSTRAINTS_TEXT,
        _planning_constraints_text(planning),
    )


def normalize_report_snapshot(
    snapshot: ScientificReportSnapshot,
    *,
    planning: Any | None = None,
) -> ScientificReportSnapshot:
    """Normalizuje teksty wspólne dla JSON, HTML, DOCX i XLSX."""

    narrative = {
        key: _normalize_text(value, planning=planning)
        for key, value in snapshot.narrative.items()
    }
    return replace(snapshot, narrative=narrative)


__all__ = ["normalize_report_snapshot", "polish_count"]
