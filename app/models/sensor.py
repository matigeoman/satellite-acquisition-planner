from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    FrequencyBand,
    LookSideCapability,
    SensorSourceType,
    SensorType,
)
from app.models.imaging import ImagingMode


class Sensor(BaseModel):
    """Definicja instrumentu obserwacyjnego satelity."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    sensor_id: str = Field(
        pattern=r"^SENSOR-[A-Z0-9-]+$",
        description="Unikalny identyfikator sensora.",
    )
    name: str = Field(min_length=1, max_length=100)

    sensor_type: SensorType
    imaging_modes: list[ImagingMode] = Field(min_length=1)

    frequency_band: FrequencyBand | None = None

    cloud_sensitive: bool
    daylight_required: bool

    minimum_sun_elevation_deg: float | None = Field(
        default=None,
        ge=-90.0,
        le=90.0,
    )
    default_max_cloud_cover: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    look_side_capability: LookSideCapability

    warmup_time_s: float = Field(ge=0.0)
    cooldown_time_s: float = Field(ge=0.0)
    maximum_continuous_acquisition_s: float = Field(gt=0.0)

    is_active: bool = True

    source_type: SensorSourceType = SensorSourceType.MODEL
    source_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_sensor_configuration(self) -> "Sensor":
        """Sprawdza zależności pomiędzy sensorem i jego trybami."""

        self._validate_mode_identifiers()
        self._validate_active_modes()
        self._validate_mode_types()
        self._validate_mode_durations()
        self._validate_source()

        if self.sensor_type == SensorType.SAR:
            self._validate_sar_sensor()
        else:
            self._validate_optical_sensor()

        return self

    def _validate_mode_identifiers(self) -> None:
        mode_ids = [mode.mode_id for mode in self.imaging_modes]

        if len(mode_ids) != len(set(mode_ids)):
            raise ValueError(
                "Sensor nie może zawierać zduplikowanych mode_id"
            )

    def _validate_active_modes(self) -> None:
        if not any(mode.is_active for mode in self.imaging_modes):
            raise ValueError(
                "Sensor musi posiadać co najmniej jeden aktywny tryb"
            )

    def _validate_mode_types(self) -> None:
        invalid_modes = [
            mode.mode_id
            for mode in self.imaging_modes
            if mode.sensor_type != self.sensor_type
        ]

        if invalid_modes:
            raise ValueError(
                "Typ sensora jest niezgodny z trybami: "
                + ", ".join(invalid_modes)
            )

    def _validate_mode_durations(self) -> None:
        invalid_modes = [
            mode.mode_id
            for mode in self.imaging_modes
            if mode.max_acquisition_duration_s
            > self.maximum_continuous_acquisition_s
        ]

        if invalid_modes:
            raise ValueError(
                "Maksymalny czas trybu przekracza limit sensora: "
                + ", ".join(invalid_modes)
            )

    def _validate_source(self) -> None:
        if (
            self.source_type != SensorSourceType.MODEL
            and not self.source_reference
        ):
            raise ValueError(
                "source_reference jest wymagane dla danych innych niż MODEL"
            )

    def _validate_sar_sensor(self) -> None:
        if self.frequency_band is None:
            raise ValueError(
                "Sensor SAR musi posiadać frequency_band"
            )

        if self.cloud_sensitive:
            raise ValueError(
                "Sensor SAR nie powinien być zależny od zachmurzenia"
            )

        if self.daylight_required:
            raise ValueError(
                "Sensor SAR nie wymaga światła dziennego"
            )

        if self.minimum_sun_elevation_deg is not None:
            raise ValueError(
                "Sensor SAR nie może wymagać minimalnej elewacji Słońca"
            )

        if self.default_max_cloud_cover is not None:
            raise ValueError(
                "Sensor SAR nie może posiadać limitu zachmurzenia"
            )

    def _validate_optical_sensor(self) -> None:
        if self.frequency_band is not None:
            raise ValueError(
                "Sensor optyczny nie może posiadać pasma radarowego"
            )

        if not self.cloud_sensitive:
            raise ValueError(
                "Sensor optyczny musi być zależny od zachmurzenia"
            )

        if not self.daylight_required:
            raise ValueError(
                "Sensor optyczny musi wymagać światła dziennego"
            )

        if self.minimum_sun_elevation_deg is None:
            raise ValueError(
                "Sensor optyczny wymaga minimum_sun_elevation_deg"
            )

        if self.default_max_cloud_cover is None:
            raise ValueError(
                "Sensor optyczny wymaga default_max_cloud_cover"
            )