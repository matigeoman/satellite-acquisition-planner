from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import DownlinkSourceType


class DownlinkOpportunity(BaseModel):
    """Stałe okno kontaktu satelity ze stacją naziemną."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    downlink_opportunity_id: str = Field(pattern=r"^DLO-[A-Z0-9-]+$")
    satellite_id: str = Field(pattern=r"^(SAR|EO)-[0-9]{2}$")
    ground_station_id: str = Field(pattern=r"^GS-[A-Z0-9-]+$")
    start_utc: datetime
    end_utc: datetime
    data_rate_mbps: float = Field(gt=0.0)
    link_efficiency: float = Field(default=0.8, gt=0.0, le=1.0)
    setup_time_s: float = Field(default=0.0, ge=0.0)
    teardown_time_s: float = Field(default=0.0, ge=0.0)
    is_feasible: bool = True
    source_type: DownlinkSourceType = DownlinkSourceType.SYNTHETIC
    source_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("start_utc", "end_utc")
    @classmethod
    def validate_utc_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Czas downlinku musi zawierać strefę czasową")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_window(self) -> "DownlinkOpportunity":
        if self.start_utc >= self.end_utc:
            raise ValueError("start_utc musi być wcześniejsze niż end_utc")
        if self.effective_duration_s <= 0.0:
            raise ValueError(
                "Czas kontaktu po odjęciu setup/teardown musi być dodatni"
            )
        if self.source_type != DownlinkSourceType.SYNTHETIC and not self.source_reference:
            raise ValueError(
                "source_reference jest wymagane dla danych innych niż SYNTHETIC"
            )
        return self

    @property
    def duration_s(self) -> float:
        return (self.end_utc - self.start_utc).total_seconds()

    @property
    def effective_duration_s(self) -> float:
        return self.duration_s - self.setup_time_s - self.teardown_time_s

    @property
    def capacity_mb(self) -> float:
        """Nominalna objętość danych w MB (Mb/s / 8 * czas * sprawność)."""

        return (
            self.data_rate_mbps
            / 8.0
            * self.effective_duration_s
            * self.link_efficiency
        )
