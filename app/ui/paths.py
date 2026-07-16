from pathlib import Path

from app.config.paths import DEFAULT_PATHS, PROJECT_ROOT


def reference_schedule_path(
    *,
    scenario_id: str,
    algorithm_value: str,
) -> Path:
    """Wyznacza ścieżkę zapisanego harmonogramu referencyjnego."""

    return DEFAULT_PATHS.reference_schedule(
        scenario_id=scenario_id,
        algorithm_value=algorithm_value,
    )


__all__ = [
    "PROJECT_ROOT",
    "reference_schedule_path",
]
