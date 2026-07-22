from pathlib import Path

from app.io.json_files import load_json_model, save_json_model
from app.models.catalog import SystemCatalog
from app.models.downlink_set import DownlinkOpportunitySet


def load_downlink_opportunity_set(
    path: str | Path,
    *,
    catalog: SystemCatalog | None = None,
) -> DownlinkOpportunitySet:
    result = load_json_model(
        path,
        model_type=DownlinkOpportunitySet,
        description="okien downlinku",
    )
    if catalog is not None:
        result.validate_against(catalog)
    return result


def save_downlink_opportunity_set(
    downlink_set: DownlinkOpportunitySet,
    path: str | Path,
) -> Path:
    return save_json_model(downlink_set, path)


__all__ = [
    "load_downlink_opportunity_set",
    "save_downlink_opportunity_set",
]
