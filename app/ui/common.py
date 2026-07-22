from __future__ import annotations

from datetime import datetime, time, timezone

from app.models.enums import PlanningAlgorithm
from app.planning.profiles import DecisionProfile


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

    if algorithm_value == PlanningAlgorithm.HYBRID.value:
        return "Hybrid Greedy + CP-SAT"

    return algorithm_value.replace("_", "-")


def decision_profile_display_name(profile_value: str) -> str:
    """Zwraca polską nazwę jawnego profilu preferencji."""

    labels = {
        DecisionProfile.CUSTOM.value: "Własne wagi",
        DecisionProfile.BALANCED.value: "Zrównoważony",
        DecisionProfile.EMERGENCY.value: "Reagowanie kryzysowe",
        DecisionProfile.QUALITY_FIRST.value: "Najwyższa jakość",
        DecisionProfile.THROUGHPUT.value: "Maksymalna przepustowość",
        DecisionProfile.SAR_EO_FUSION.value: "Fuzja SAR–EO",
    }
    return labels.get(profile_value, profile_value.replace("_", "-"))
