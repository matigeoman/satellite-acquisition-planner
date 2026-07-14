from datetime import datetime, timezone
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.enums import (
    ObservationSide,
    OpportunitySourceType,
    SensorType,
)


class AcquisitionOpportunity(BaseModel):
    """Kandydat do wykonania akwizycji satelitarnej."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    opportunity_id: str = Field(
        pattern=r"^OPP-[A-Z0-9-]+$",
        description="Unikalny identyfikator okazji akwizycyjnej.",
    )

    request_id: str = Field(
        pattern=r"^REQ-[A-Z0-9-]+$",
        description="Identyfikator zlecenia obserwacyjnego.",
    )

    satellite_id: str = Field(
        pattern=r"^(SAR|EO)-[0-9]{2}$",
        description="Identyfikator satelity.",
    )

    sensor_id: str = Field(
        pattern=r"^SENSOR-[A-Z0-9-]+$",
        description="Identyfikator sensora.",
    )

    mode_id: str = Field(
        pattern=r"^MODE-[A-Z0-9-]+$",
        description="Identyfikator trybu obrazowania.",
    )

    sensor_type: SensorType

    start_utc: datetime
    end_utc: datetime

    observation_side: ObservationSide
    off_nadir_angle_deg: float = Field(
        ge=0.0,
        lt=90.0,
    )

    incidence_angle_deg: float | None = Field(
        default=None,
        ge=0.0,
        lt=90.0,
    )

    cloud_cover: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    sun_elevation_deg: float | None = Field(
        default=None,
        ge=-90.0,
        le=90.0,
    )

    coverage_ratio: float = Field(
        gt=0.0,
        le=1.0,
    )

    quality_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    estimated_data_volume_mb: float = Field(
        gt=0.0,
    )

    is_feasible: bool = True

    infeasibility_reasons: list[str] = Field(
        default_factory=list,
    )

    source_type: OpportunitySourceType = (
        OpportunitySourceType.SYNTHETIC
    )

    source_reference: str | None = Field(
        default=None,
        max_length=500,
    )

    notes: str | None = Field(
        default=None,
        max_length=1000,
    )

    @field_validator(
        "start_utc",
        "end_utc",
    )
    @classmethod
    def validate_utc_datetime(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "Czas okazji musi zawierać strefę czasową"
            )

        return value.astimezone(timezone.utc)

    @field_validator(
        "infeasibility_reasons",
        mode="before",
    )
    @classmethod
    def normalize_infeasibility_reasons(
        cls,
        value: Any,
    ) -> list[str]:
        if value is None:
            return []

        if not isinstance(value, list):
            raise ValueError(
                "infeasibility_reasons musi być listą"
            )

        normalized = [
            str(reason).strip()
            for reason in value
        ]

        if any(not reason for reason in normalized):
            raise ValueError(
                "Powody niewykonalności nie mogą być puste"
            )

        if len(normalized) != len(set(normalized)):
            raise ValueError(
                "Powody niewykonalności nie mogą się powtarzać"
            )

        return normalized

    @model_validator(mode="after")
    def validate_opportunity_configuration(
        self,
    ) -> "AcquisitionOpportunity":
        self._validate_time_window()
        self._validate_platform_assignment()
        self._validate_sensor_specific_fields()
        self._validate_feasibility()
        self._validate_source()

        return self

    def _validate_time_window(self) -> None:
        if self.start_utc >= self.end_utc:
            raise ValueError(
                "start_utc musi być wcześniejsze niż end_utc"
            )

    def _validate_platform_assignment(self) -> None:
        if self.sensor_type == SensorType.SAR:
            expected_satellite_prefix = "SAR-"
            expected_sensor_prefix = "SENSOR-SAR-"
            expected_mode_prefix = "MODE-SAR-"
        else:
            expected_satellite_prefix = "EO-"
            expected_sensor_prefix = "SENSOR-EO-"
            expected_mode_prefix = "MODE-OPT-"

        if not self.satellite_id.startswith(
            expected_satellite_prefix
        ):
            raise ValueError(
                f"Typ {self.sensor_type.value} jest niezgodny "
                f"z satellite_id {self.satellite_id}"
            )

        if not self.sensor_id.startswith(
            expected_sensor_prefix
        ):
            raise ValueError(
                f"Typ {self.sensor_type.value} jest niezgodny "
                f"z sensor_id {self.sensor_id}"
            )

        if not self.mode_id.startswith(
            expected_mode_prefix
        ):
            raise ValueError(
                f"Typ {self.sensor_type.value} jest niezgodny "
                f"z mode_id {self.mode_id}"
            )

    def _validate_sensor_specific_fields(self) -> None:
        if self.sensor_type == SensorType.SAR:
            self._validate_sar_fields()
        else:
            self._validate_optical_fields()

    def _validate_sar_fields(self) -> None:
        if self.incidence_angle_deg is None:
            raise ValueError(
                "Okazja SAR wymaga incidence_angle_deg"
            )

        if self.cloud_cover is not None:
            raise ValueError(
                "Okazja SAR nie może posiadać cloud_cover"
            )

        if self.sun_elevation_deg is not None:
            raise ValueError(
                "Okazja SAR nie może posiadać sun_elevation_deg"
            )

        if self.observation_side == ObservationSide.NADIR:
            raise ValueError(
                "W modelu SAR obserwacja musi być LEFT albo RIGHT"
            )

    def _validate_optical_fields(self) -> None:
        if self.incidence_angle_deg is not None:
            raise ValueError(
                "Okazja optyczna nie może posiadać "
                "incidence_angle_deg"
            )

        if self.cloud_cover is None:
            raise ValueError(
                "Okazja optyczna wymaga cloud_cover"
            )

        if self.sun_elevation_deg is None:
            raise ValueError(
                "Okazja optyczna wymaga sun_elevation_deg"
            )

    def _validate_feasibility(self) -> None:
        if self.is_feasible and self.infeasibility_reasons:
            raise ValueError(
                "Wykonalna okazja nie może posiadać "
                "powodów niewykonalności"
            )

        if (
            not self.is_feasible
            and not self.infeasibility_reasons
        ):
            raise ValueError(
                "Niewykonalna okazja musi posiadać "
                "co najmniej jeden powód"
            )

    def _validate_source(self) -> None:
        if (
            self.source_type
            != OpportunitySourceType.SYNTHETIC
            and not self.source_reference
        ):
            raise ValueError(
                "source_reference jest wymagane dla źródła "
                "innego niż SYNTHETIC"
            )

    @property
    def duration_s(self) -> float:
        """Czas trwania akwizycji w sekundach."""

        return (
            self.end_utc - self.start_utc
        ).total_seconds()

    @property
    def memory_cost_mb(self) -> float:
        """Ilość pamięci potrzebna do zapisania produktu."""

        return self.estimated_data_volume_mb

    @property
    def is_available_for_planning(self) -> bool:
        """Informuje, czy okazja może trafić do optymalizatora."""

        return self.is_feasible