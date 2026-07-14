from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import ModeCategory, ProductType, SensorType


class ImagingMode(BaseModel):
    """Definicja pojedynczego trybu obrazowania sensora."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    mode_id: str = Field(
        pattern=r"^MODE-[A-Z0-9-]+$",
        description="Unikalny identyfikator trybu obrazowania.",
    )
    name: str = Field(min_length=1, max_length=100)

    sensor_type: SensorType
    mode_category: ModeCategory
    product_type: ProductType

    nominal_resolution_m: float = Field(gt=0.0)
    nominal_scene_width_km: float = Field(gt=0.0)
    nominal_scene_length_km: float = Field(gt=0.0)

    min_acquisition_duration_s: float = Field(gt=0.0)
    max_acquisition_duration_s: float = Field(gt=0.0)

    data_rate_mb_s: float = Field(ge=0.0)
    max_off_nadir_deg: float = Field(ge=0.0, lt=90.0)

    min_incidence_angle_deg: float | None = Field(
        default=None,
        ge=0.0,
        lt=90.0,
    )
    max_incidence_angle_deg: float | None = Field(
        default=None,
        ge=0.0,
        lt=90.0,
    )

    polarizations: list[str] | None = None
    spectral_bands: list[str] | None = None

    quality_factor: float = Field(ge=0.0, le=1.0)
    is_active: bool = True
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("polarizations", "spectral_bands", mode="before")
    @classmethod
    def normalize_string_list(cls, value: Any) -> list[str] | None:
        """Normalizuje elementy listy do wielkich liter."""

        if value is None:
            return None

        if not isinstance(value, list):
            raise ValueError("Wartość musi być listą albo null")

        normalized = [str(item).strip().upper() for item in value]

        if any(not item for item in normalized):
            raise ValueError("Lista nie może zawierać pustych wartości")

        if len(normalized) != len(set(normalized)):
            raise ValueError("Lista nie może zawierać duplikatów")

        return normalized

    @model_validator(mode="after")
    def validate_mode_configuration(self) -> "ImagingMode":
        """Sprawdza zależności między parametrami trybu."""

        if self.min_acquisition_duration_s > self.max_acquisition_duration_s:
            raise ValueError(
                "min_acquisition_duration_s nie może przekraczać "
                "max_acquisition_duration_s"
            )

        if self.sensor_type == SensorType.SAR:
            self._validate_sar_mode()
        else:
            self._validate_optical_mode()

        return self

    def _validate_sar_mode(self) -> None:
        allowed_categories = {
            ModeCategory.SPOTLIGHT,
            ModeCategory.STRIPMAP,
            ModeCategory.SCANSAR,
        }

        if self.mode_category not in allowed_categories:
            raise ValueError(
                "Tryb SAR musi używać kategorii SPOTLIGHT, STRIPMAP "
                "albo SCANSAR"
            )

        if self.product_type != ProductType.SAR_IMAGE:
            raise ValueError(
                "Tryb SAR musi mieć product_type równy SAR_IMAGE"
            )

        if (
            self.min_incidence_angle_deg is None
            or self.max_incidence_angle_deg is None
        ):
            raise ValueError(
                "Tryb SAR wymaga minimalnego i maksymalnego kąta padania"
            )

        if self.min_incidence_angle_deg > self.max_incidence_angle_deg:
            raise ValueError(
                "Minimalny kąt padania nie może przekraczać maksymalnego"
            )

        if not self.polarizations:
            raise ValueError(
                "Tryb SAR musi posiadać co najmniej jedną polaryzację"
            )

        allowed_polarizations = {"HH", "HV", "VH", "VV"}

        if not set(self.polarizations).issubset(allowed_polarizations):
            raise ValueError(
                "Dozwolone polaryzacje SAR to HH, HV, VH oraz VV"
            )

        if self.spectral_bands is not None:
            raise ValueError(
                "Tryb SAR nie może posiadać pasm spektralnych"
            )

    def _validate_optical_mode(self) -> None:
        allowed_categories = {
            ModeCategory.PUSHBROOM,
            ModeCategory.FRAME,
        }
        allowed_products = {
            ProductType.PANCHROMATIC,
            ProductType.MULTISPECTRAL,
            ProductType.PANSHARPENED,
        }

        if self.mode_category not in allowed_categories:
            raise ValueError(
                "Tryb optyczny musi używać kategorii PUSHBROOM albo FRAME"
            )

        if self.product_type not in allowed_products:
            raise ValueError(
                "Niepoprawny typ produktu dla sensora optycznego"
            )

        if (
            self.min_incidence_angle_deg is not None
            or self.max_incidence_angle_deg is not None
        ):
            raise ValueError(
                "Tryb optyczny nie może posiadać kątów padania SAR"
            )

        if self.polarizations is not None:
            raise ValueError(
                "Tryb optyczny nie może posiadać polaryzacji SAR"
            )

        if not self.spectral_bands:
            raise ValueError(
                "Tryb optyczny musi posiadać co najmniej jedno pasmo"
            )