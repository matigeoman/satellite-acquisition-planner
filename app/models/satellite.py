from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.enums import SatelliteSourceType, SatelliteStatus


class Satellite(BaseModel):
    """Definicja pojedynczego satelity należącego do konstelacji."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    satellite_id: str = Field(
        pattern=r"^(SAR|EO)-[0-9]{2}$",
        description="Unikalny identyfikator satelity.",
    )
    name: str = Field(min_length=1, max_length=100)

    constellation_id: str = Field(
        pattern=r"^CONST-(SAR|EO)$",
        description="Identyfikator podkonstelacji.",
    )
    orbit_id: str = Field(
        pattern=r"^ORB-[A-Z0-9-]+$",
        description="Identyfikator przypisanej orbity.",
    )
    sensor_id: str = Field(
        pattern=r"^SENSOR-[A-Z0-9-]+$",
        description="Identyfikator przypisanego sensora.",
    )

    phase_angle_deg: float

    memory_capacity_mb: float = Field(gt=0.0)
    initial_memory_usage_mb: float = Field(ge=0.0)

    minimum_transition_time_s: float = Field(ge=0.0)
    max_acquisitions_per_day: int = Field(ge=1)
    max_imaging_time_per_day_s: float = Field(gt=0.0)

    status: SatelliteStatus = SatelliteStatus.ACTIVE

    source_type: SatelliteSourceType = SatelliteSourceType.MODEL
    source_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("phase_angle_deg", mode="before")
    @classmethod
    def normalize_phase_angle(cls, value: Any) -> float:
        """Normalizuje kąt fazowy do zakresu od 0 do mniej niż 360 stopni."""

        return float(value) % 360.0

    @model_validator(mode="after")
    def validate_satellite_configuration(self) -> "Satellite":
        """Sprawdza zależności między polami satelity."""

        self._validate_memory()
        self._validate_constellation_assignment()
        self._validate_orbit_assignment()
        self._validate_sensor_assignment()
        self._validate_source()

        return self

    def _validate_memory(self) -> None:
        if self.initial_memory_usage_mb > self.memory_capacity_mb:
            raise ValueError(
                "initial_memory_usage_mb nie może przekraczać "
                "memory_capacity_mb"
            )

    def _validate_constellation_assignment(self) -> None:
        if self.satellite_id.startswith("SAR-"):
            expected_constellation = "CONST-SAR"
        else:
            expected_constellation = "CONST-EO"

        if self.constellation_id != expected_constellation:
            raise ValueError(
                f"Satelita {self.satellite_id} musi należeć do "
                f"{expected_constellation}"
            )

    def _validate_orbit_assignment(self) -> None:
        if self.satellite_id.startswith("SAR-"):
            expected_prefix = "ORB-SAR-"
        else:
            expected_prefix = "ORB-EO-"

        if not self.orbit_id.startswith(expected_prefix):
            raise ValueError(
                f"Orbita satelity {self.satellite_id} musi rozpoczynać się "
                f"od {expected_prefix}"
            )

    def _validate_sensor_assignment(self) -> None:
        if self.satellite_id.startswith("SAR-"):
            expected_prefix = "SENSOR-SAR-"
        else:
            expected_prefix = "SENSOR-EO-"

        if not self.sensor_id.startswith(expected_prefix):
            raise ValueError(
                f"Sensor satelity {self.satellite_id} musi rozpoczynać się "
                f"od {expected_prefix}"
            )

    def _validate_source(self) -> None:
        if (
            self.source_type != SatelliteSourceType.MODEL
            and not self.source_reference
        ):
            raise ValueError(
                "source_reference jest wymagane dla danych innych niż MODEL"
            )

    @property
    def available_memory_mb(self) -> float:
        """Zwraca wolną pamięć na początku horyzontu planowania."""

        return self.memory_capacity_mb - self.initial_memory_usage_mb

    @property
    def is_available_for_planning(self) -> bool:
        """Informuje, czy satelita może być używany w planowaniu."""

        return self.status == SatelliteStatus.ACTIVE