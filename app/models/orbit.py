from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import OrbitSourceType, OrbitType, ReferenceFrame


class OrbitDefinition(BaseModel):
    """Wspólna definicja orbity dla jednej podkonstelacji."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    orbit_id: str = Field(
        pattern=r"^ORB-[A-Z0-9-]+$",
        description="Unikalny identyfikator orbity.",
    )
    name: str = Field(min_length=1, max_length=100)

    orbit_type: OrbitType

    altitude_km: float = Field(ge=160.0, le=2000.0)
    inclination_deg: float = Field(ge=0.0, le=180.0)
    eccentricity: float = Field(ge=0.0, lt=1.0)

    raan_deg: float
    argument_of_perigee_deg: float

    epoch_utc: datetime

    reference_frame: ReferenceFrame = ReferenceFrame.J2000
    is_sun_synchronous: bool = False

    source_type: OrbitSourceType = OrbitSourceType.MODEL
    source_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("raan_deg", "argument_of_perigee_deg", mode="before")
    @classmethod
    def normalize_angle(cls, value: float) -> float:
        """Normalizuje kąt do zakresu od 0 do mniej niż 360 stopni."""

        angle = float(value) % 360.0
        return angle

    @field_validator("epoch_utc")
    @classmethod
    def validate_epoch_utc(cls, value: datetime) -> datetime:
        """Wymaga daty ze strefą czasową i zapisuje ją w UTC."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("epoch_utc musi zawierać strefę czasową")

        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_orbit_configuration(self) -> "OrbitDefinition":
        """Sprawdza zależności między polami modelu."""

        if self.orbit_type in {
            OrbitType.CIRCULAR_LEO,
            OrbitType.CIRCULAR_SSO,
        }:
            if self.eccentricity > 0.001:
                raise ValueError(
                    "Dla orbity kołowej eccentricity nie może przekraczać 0.001"
                )

        if self.is_sun_synchronous:
            if self.orbit_type != OrbitType.CIRCULAR_SSO:
                raise ValueError(
                    "Orbita heliosynchroniczna musi mieć typ CIRCULAR_SSO"
                )

        if self.source_type != OrbitSourceType.MODEL:
            if not self.source_reference:
                raise ValueError(
                    "source_reference jest wymagane dla danych innych niż MODEL"
                )

        return self