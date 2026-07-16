from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def reference_schedule_path(
    *,
    scenario_id: str,
    algorithm_value: str,
) -> Path:
    """Wyznacza ścieżkę zapisanego harmonogramu referencyjnego."""

    normalized_scenario = scenario_id.strip().upper()
    normalized_algorithm = algorithm_value.strip().upper()

    scenario_prefixes = {
        "EXAMPLE": "example_schedule",
        "STRESS": "stress_schedule",
    }

    try:
        scenario_prefix = scenario_prefixes[normalized_scenario]
    except KeyError as error:
        raise ValueError(
            f"Nieobsługiwany scenariusz: {scenario_id}"
        ) from error

    if normalized_algorithm not in {"GREEDY", "CP_SAT"}:
        raise ValueError(
            f"Nieobsługiwany algorytm: {algorithm_value}"
        )

    return (
        PROJECT_ROOT
        / "data"
        / f"{scenario_prefix}_{normalized_algorithm.lower()}.json"
    )
