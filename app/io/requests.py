from pathlib import Path

from app.io.json_files import load_json_model
from app.models.request_set import ObservationRequestSet


def load_request_set(path: str | Path) -> ObservationRequestSet:
    """Wczytuje i waliduje zbiór zleceń z pliku JSON."""

    return load_json_model(
        path,
        model_type=ObservationRequestSet,
        description="zleceń",
    )
