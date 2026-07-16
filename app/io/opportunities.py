from pathlib import Path

from app.io.json_files import load_json_model
from app.models.catalog import SystemCatalog
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request_set import ObservationRequestSet


def load_opportunity_set(
    path: str | Path,
    *,
    catalog: SystemCatalog | None = None,
    request_set: ObservationRequestSet | None = None,
) -> AcquisitionOpportunitySet:
    """Wczytuje okazje i opcjonalnie waliduje ich referencje."""

    opportunity_set = load_json_model(
        path,
        model_type=AcquisitionOpportunitySet,
        description="okazji",
    )

    if catalog is not None and request_set is not None:
        opportunity_set.validate_against(catalog, request_set)

    return opportunity_set
