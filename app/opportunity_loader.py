import json
from json import JSONDecodeError
from pathlib import Path

from app.models.catalog import SystemCatalog
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request_set import ObservationRequestSet


def load_opportunity_set(
    path: str | Path,
    *,
    catalog: SystemCatalog | None = None,
    request_set: ObservationRequestSet | None = None,
) -> AcquisitionOpportunitySet:
    """Wczytuje i waliduje zbiór okazji z pliku JSON."""

    opportunity_path = Path(path)

    if not opportunity_path.exists():
        raise FileNotFoundError(
            f"Nie znaleziono pliku okazji: {opportunity_path}"
        )

    if not opportunity_path.is_file():
        raise ValueError(
            f"Ścieżka nie wskazuje pliku: {opportunity_path}"
        )

    try:
        raw_text = opportunity_path.read_text(
            encoding="utf-8",
        )
        raw_data = json.loads(raw_text)
    except JSONDecodeError as error:
        raise ValueError(
            f"Plik {opportunity_path} nie zawiera poprawnego JSON"
        ) from error

    opportunity_set = AcquisitionOpportunitySet.model_validate(
        raw_data
    )

    if catalog is not None and request_set is not None:
        opportunity_set.validate_against(
            catalog,
            request_set,
        )

    return opportunity_set