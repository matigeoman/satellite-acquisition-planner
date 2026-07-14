import json
from json import JSONDecodeError
from pathlib import Path

from app.models.catalog import SystemCatalog


def load_system_catalog(
    path: str | Path,
) -> SystemCatalog:
    """Wczytuje i waliduje katalog systemu z pliku JSON."""

    catalog_path = Path(path)

    if not catalog_path.exists():
        raise FileNotFoundError(
            f"Nie znaleziono pliku katalogu: {catalog_path}"
        )

    if not catalog_path.is_file():
        raise ValueError(
            f"Ścieżka katalogu nie wskazuje pliku: "
            f"{catalog_path}"
        )

    try:
        raw_text = catalog_path.read_text(
            encoding="utf-8",
        )
        raw_data = json.loads(raw_text)
    except JSONDecodeError as error:
        raise ValueError(
            f"Plik {catalog_path} nie zawiera poprawnego JSON"
        ) from error

    return SystemCatalog.model_validate(raw_data)