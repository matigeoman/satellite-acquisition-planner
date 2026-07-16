from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.imaging import ImagingMode
from app.models.orbit import OrbitDefinition
from app.models.sensor import Sensor


class ParameterOrigin(StrEnum):
    """Pochodzenie parametru użytego w profilu publicznym."""

    PUBLIC_DATA = "PUBLIC_DATA"
    MODEL_DERIVED = "MODEL_DERIVED"
    TLE_PENDING = "TLE_PENDING"


class ParameterSource(BaseModel):
    """Opis źródła pojedynczej grupy parametrów profilu."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    parameter_group: str = Field(min_length=1, max_length=120)
    origin: ParameterOrigin
    reference: str = Field(min_length=1, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class ProductSizeRange(BaseModel):
    """Publiczny lub oszacowany zakres rozmiaru produktu obrazowego."""

    model_config = ConfigDict(extra="forbid")

    minimum_mb: float = Field(ge=0.0)
    maximum_mb: float = Field(ge=0.0)
    product_name: str = Field(min_length=1, max_length=80)
    origin: ParameterOrigin

    @model_validator(mode="after")
    def validate_range(self) -> "ProductSizeRange":
        if self.minimum_mb > self.maximum_mb:
            raise ValueError("minimum_mb nie może przekraczać maximum_mb")
        return self

    @property
    def midpoint_mb(self) -> float:
        return (self.minimum_mb + self.maximum_mb) / 2.0


class PublicMissionProfile(BaseModel):
    """Profil misji z parametrami publicznymi i jawnymi założeniami."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        arbitrary_types_allowed=True,
    )

    profile_id: str = Field(pattern=r"^PROFILE-[A-Z0-9-]+$")
    name: str = Field(min_length=1, max_length=150)
    operator: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1500)
    satellite_slots: int = Field(ge=1, le=100)
    satellite_labels: list[str] = Field(min_length=1)
    orbit_template: OrbitDefinition
    sensor: Sensor
    product_sizes_by_mode: dict[str, ProductSizeRange]
    parameter_sources: list[ParameterSource] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_profile(self) -> "PublicMissionProfile":
        if len(self.satellite_labels) != self.satellite_slots:
            raise ValueError(
                "Liczba satellite_labels musi być równa satellite_slots"
            )

        mode_ids = {mode.mode_id for mode in self.sensor.imaging_modes}
        unknown = sorted(set(self.product_sizes_by_mode) - mode_ids)
        if unknown:
            raise ValueError(
                "Rozmiary produktów odnoszą się do nieznanych trybów: "
                + ", ".join(unknown)
            )
        return self

    @property
    def imaging_modes(self) -> list[ImagingMode]:
        return list(self.sensor.imaging_modes)

    def get_mode(self, mode_id: str) -> ImagingMode:
        for mode in self.sensor.imaging_modes:
            if mode.mode_id == mode_id:
                return mode
        raise KeyError(f"Nie znaleziono trybu: {mode_id}")

    def mode_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for mode in self.sensor.imaging_modes:
            size = self.product_sizes_by_mode.get(mode.mode_id)
            rows.append(
                {
                    "Tryb": mode.name,
                    "Kategoria": mode.mode_category.value,
                    "Rozdzielczość [m]": mode.nominal_resolution_m,
                    "Scena [km]": (
                        f"{mode.nominal_scene_width_km:g} × "
                        f"{mode.nominal_scene_length_km:g}"
                    ),
                    "Czas [s]": (
                        f"{mode.min_acquisition_duration_s:g}–"
                        f"{mode.max_acquisition_duration_s:g}"
                    ),
                    "Kąt padania [°]": (
                        "—"
                        if mode.min_incidence_angle_deg is None
                        else (
                            f"{mode.min_incidence_angle_deg:g}–"
                            f"{mode.max_incidence_angle_deg:g}"
                        )
                    ),
                    "Produkt [MB]": (
                        "model"
                        if size is None
                        else f"{size.minimum_mb:g}–{size.maximum_mb:g}"
                    ),
                }
            )
        return rows
