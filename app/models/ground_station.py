from pydantic import BaseModel, ConfigDict, Field, model_validator


class GroundStation(BaseModel):
    """Model stacji naziemnej dostępnej do odbioru danych."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    ground_station_id: str = Field(pattern=r"^GS-[A-Z0-9-]+$")
    name: str = Field(min_length=1, max_length=120)
    latitude_deg: float = Field(ge=-90.0, le=90.0)
    longitude_deg: float = Field(ge=-180.0, le=180.0)
    altitude_m: float = Field(default=0.0, ge=-500.0, le=10000.0)
    minimum_elevation_deg: float = Field(default=10.0, ge=0.0, lt=90.0)
    max_simultaneous_contacts: int = Field(default=1, ge=1)
    is_active: bool = True
    source_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_coordinates(self) -> "GroundStation":
        if self.latitude_deg in {-90.0, 90.0} and self.longitude_deg != 0.0:
            raise ValueError(
                "Dla bieguna longitude_deg powinno wynosić 0 stopni"
            )
        return self
