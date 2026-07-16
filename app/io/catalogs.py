from pathlib import Path

from app.io.json_files import load_json_model
from app.models.catalog import SystemCatalog


def load_system_catalog(path: str | Path) -> SystemCatalog:
    """Wczytuje i waliduje katalog systemu z pliku JSON."""

    return load_json_model(
        path,
        model_type=SystemCatalog,
        description="katalogu",
    )
