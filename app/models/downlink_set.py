from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.catalog import SystemCatalog
from app.models.downlink import DownlinkOpportunity


class DownlinkOpportunitySet(BaseModel):
    """Zbiór okien transmisji dla jednego horyzontu planowania."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    downlink_set_id: str = Field(pattern=r"^DLOSET-[A-Z0-9-]+$")
    name: str = Field(min_length=1, max_length=150)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    catalog_id: str = Field(pattern=r"^CATALOG-[A-Z0-9-]+$")
    horizon_start_utc: datetime
    horizon_end_utc: datetime
    generated_at_utc: datetime
    opportunities: list[DownlinkOpportunity] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator(
        "horizon_start_utc",
        "horizon_end_utc",
        "generated_at_utc",
    )
    @classmethod
    def validate_utc_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Czas zbioru downlinków musi zawierać strefę czasową")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_set(self) -> "DownlinkOpportunitySet":
        if self.horizon_start_utc >= self.horizon_end_utc:
            raise ValueError(
                "horizon_start_utc musi być wcześniejsze niż horizon_end_utc"
            )
        identifiers = [
            opportunity.downlink_opportunity_id
            for opportunity in self.opportunities
        ]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Zbiór downlinków zawiera powtórzone identyfikatory")
        for opportunity in self.opportunities:
            if (
                opportunity.start_utc < self.horizon_start_utc
                or opportunity.end_utc > self.horizon_end_utc
            ):
                raise ValueError(
                    "Okno downlinku znajduje się poza horyzontem: "
                    f"{opportunity.downlink_opportunity_id}"
                )
        return self

    @property
    def feasible_opportunities(self) -> list[DownlinkOpportunity]:
        return [item for item in self.opportunities if item.is_feasible]

    def validate_against(self, catalog: SystemCatalog) -> None:
        if self.catalog_id != catalog.catalog_id:
            raise ValueError("catalog_id zbioru downlinków jest niezgodne z katalogiem")
        satellite_ids = {item.satellite_id for item in catalog.satellites}
        station_ids = {
            item.ground_station_id for item in catalog.ground_stations
        }
        for opportunity in self.opportunities:
            if opportunity.satellite_id not in satellite_ids:
                raise ValueError(
                    "Nieznany satelita w oknie downlinku: "
                    f"{opportunity.satellite_id}"
                )
            if opportunity.ground_station_id not in station_ids:
                raise ValueError(
                    "Nieznana stacja w oknie downlinku: "
                    f"{opportunity.ground_station_id}"
                )
