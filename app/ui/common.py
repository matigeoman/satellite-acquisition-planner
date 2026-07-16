from __future__ import annotations

from datetime import datetime, time, timezone

from app.models.enums import PlanningAlgorithm


def combine_utc(selected_date, selected_time: time) -> datetime:
    """Łączy datę i czas formularza w jednoznaczny znacznik UTC."""

    return datetime.combine(
        selected_date,
        selected_time.replace(tzinfo=None),
    ).replace(tzinfo=timezone.utc)


def algorithm_display_name(algorithm_value: str) -> str:
    """Zwraca czytelną nazwę algorytmu używaną w interfejsie."""

    if algorithm_value == PlanningAlgorithm.GREEDY.value:
        return "Greedy"

    if algorithm_value == PlanningAlgorithm.CP_SAT.value:
        return "CP-SAT"

    return algorithm_value.replace("_", "-")
