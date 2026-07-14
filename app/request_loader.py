import json
from json import JSONDecodeError
from pathlib import Path

from app.models.request_set import ObservationRequestSet


def load_request_set(
    path: str | Path,
) -> ObservationRequestSet:
    """Wczytuje i waliduje zbiór zleceń z pliku JSON."""

    request_path = Path(path)

    if not request_path.exists():
        raise FileNotFoundError(
            f"Nie znaleziono pliku zleceń: {request_path}"
        )

    if not request_path.is_file():
        raise ValueError(
            f"Ścieżka nie wskazuje pliku: {request_path}"
        )

    try:
        raw_text = request_path.read_text(
            encoding="utf-8",
        )
        raw_data = json.loads(raw_text)
    except JSONDecodeError as error:
        raise ValueError(
            f"Plik {request_path} nie zawiera poprawnego JSON"
        ) from error

    return ObservationRequestSet.model_validate(raw_data)