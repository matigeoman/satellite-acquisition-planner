from pathlib import Path

from app.io.json_files import load_json_model, save_json_model
from app.models.schedule import Schedule


def load_schedule(path: str | Path) -> Schedule:
    """Wczytuje i waliduje harmonogram z pliku JSON."""

    return load_json_model(
        path,
        model_type=Schedule,
        description="harmonogramu",
    )


def save_schedule(schedule: Schedule, path: str | Path) -> Path:
    """Zapisuje harmonogram do pliku JSON."""

    return save_json_model(schedule, path)
