import json
from json import JSONDecodeError
from pathlib import Path

from app.models.schedule import Schedule


def load_schedule(
    path: str | Path,
) -> Schedule:
    """Wczytuje i waliduje harmonogram z pliku JSON."""

    schedule_path = Path(path)

    if not schedule_path.exists():
        raise FileNotFoundError(
            f"Nie znaleziono pliku harmonogramu: {schedule_path}"
        )

    if not schedule_path.is_file():
        raise ValueError(
            f"Ścieżka nie wskazuje pliku: {schedule_path}"
        )

    try:
        raw_text = schedule_path.read_text(
            encoding="utf-8",
        )

        raw_data = json.loads(
            raw_text
        )
    except JSONDecodeError as error:
        raise ValueError(
            f"Plik {schedule_path} nie zawiera poprawnego JSON"
        ) from error

    return Schedule.model_validate(
        raw_data
    )


def save_schedule(
    schedule: Schedule,
    path: str | Path,
) -> Path:
    """Zapisuje harmonogram do pliku JSON."""

    schedule_path = Path(path)

    schedule_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_data = schedule.model_dump(
        mode="json",
    )

    schedule_path.write_text(
        json.dumps(
            output_data,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return schedule_path