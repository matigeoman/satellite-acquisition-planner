from __future__ import annotations

import json
from json import JSONDecodeError
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)


def load_json_model(
    path: str | Path,
    *,
    model_type: type[ModelT],
    description: str,
) -> ModelT:
    """Wczytuje plik JSON i waliduje go wskazanym modelem Pydantic."""

    resolved_path = Path(path)

    if not resolved_path.exists():
        raise FileNotFoundError(
            f"Nie znaleziono pliku {description}: {resolved_path}"
        )

    if not resolved_path.is_file():
        raise ValueError(
            f"Ścieżka {description} nie wskazuje pliku: {resolved_path}"
        )

    try:
        raw_data = json.loads(
            resolved_path.read_text(encoding="utf-8")
        )
    except JSONDecodeError as error:
        raise ValueError(
            f"Plik {resolved_path} nie zawiera poprawnego JSON"
        ) from error

    return model_type.model_validate(raw_data)


def save_json_model(
    model: BaseModel,
    path: str | Path,
) -> Path:
    """Zapisuje model Pydantic do czytelnego pliku JSON UTF-8."""

    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = model.model_dump(mode="json")

    resolved_path.write_text(
        json.dumps(
            serialized,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return resolved_path
