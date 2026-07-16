from datetime import datetime, timezone

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.enums import (
    RequestMode,
    RequestStatus,
    SensorType,
)
from app.models.geometry import TargetGeometry


class ObservationRequest(BaseModel):
    """Zlecenie wykonania obserwacji satelitarnej."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    request_id: str = Field(
        pattern=r"^REQ-[A-Z0-9-]+$",
        description="Unikalny identyfikator zlecenia.",
    )
    name: str = Field(
        min_length=1,
        max_length=150,
    )

    geometry: TargetGeometry

    priority: int = Field(
        ge=1,
        le=10,
        description="Priorytet zlecenia od 1 do 10.",
    )

    earliest_start_utc: datetime
    latest_end_utc: datetime

    request_mode: RequestMode
    requested_sensor_types: list[SensorType] = Field(
        min_length=1,
        max_length=2,
    )

    max_resolution_m: float = Field(
        gt=0.0,
        description=("Wspólny lub zapasowy maksymalny rozmiar piksela/GSD w metrach."),
    )
    max_sar_resolution_m: float | None = Field(
        default=None,
        gt=0.0,
        description=("Opcjonalny limit rozdzielczości przeznaczony wyłącznie dla SAR."),
    )
    max_optical_resolution_m: float | None = Field(
        default=None,
        gt=0.0,
        description=("Opcjonalny limit rozdzielczości przeznaczony wyłącznie dla EO."),
    )
    minimum_coverage_ratio: float = Field(
        gt=0.0,
        le=1.0,
    )

    max_cloud_cover: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    max_incidence_angle_deg: float | None = Field(
        default=None,
        ge=0.0,
        lt=90.0,
    )
    max_off_nadir_deg: float | None = Field(
        default=None,
        ge=0.0,
        lt=90.0,
    )

    status: RequestStatus = RequestStatus.ACTIVE
    is_mandatory: bool = False

    external_reference: str | None = Field(
        default=None,
        max_length=200,
    )
    notes: str | None = Field(
        default=None,
        max_length=1000,
    )

    @field_validator(
        "earliest_start_utc",
        "latest_end_utc",
    )
    @classmethod
    def validate_utc_datetime(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Czas musi zawierać strefę czasową")

        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_request_configuration(
        self,
    ) -> "ObservationRequest":
        self._validate_time_window()
        self._validate_sensor_types()
        self._validate_cloud_constraint()
        self._validate_incidence_constraint()
        self._validate_sensor_specific_resolution_constraints()

        return self

    def _validate_time_window(self) -> None:
        if self.earliest_start_utc >= self.latest_end_utc:
            raise ValueError(
                "earliest_start_utc musi być wcześniejsze niż latest_end_utc"
            )

    def _validate_sensor_types(self) -> None:
        sensor_types = self.requested_sensor_types
        sensor_set = set(sensor_types)

        if len(sensor_types) != len(sensor_set):
            raise ValueError("requested_sensor_types nie może zawierać duplikatów")

        if self.request_mode == RequestMode.SINGLE:
            if len(sensor_set) != 1:
                raise ValueError("Tryb SINGLE wymaga dokładnie jednego typu sensora")

            return

        required_dual_types = {
            SensorType.SAR,
            SensorType.OPTICAL,
        }

        if sensor_set != required_dual_types:
            raise ValueError("Tryb DUAL wymaga typów SAR i OPTICAL")

    def _validate_cloud_constraint(self) -> None:
        sensor_set = set(self.requested_sensor_types)

        if SensorType.OPTICAL in sensor_set:
            if self.max_cloud_cover is None:
                raise ValueError("Zlecenie optyczne wymaga max_cloud_cover")
        elif self.max_cloud_cover is not None:
            raise ValueError("Zlecenie wyłącznie SAR nie może posiadać max_cloud_cover")

    def _validate_incidence_constraint(self) -> None:
        sensor_set = set(self.requested_sensor_types)

        if (
            SensorType.SAR not in sensor_set
            and self.max_incidence_angle_deg is not None
        ):
            raise ValueError(
                "Zlecenie bez SAR nie może posiadać max_incidence_angle_deg"
            )

    def _validate_sensor_specific_resolution_constraints(self) -> None:
        sensor_set = set(self.requested_sensor_types)

        if SensorType.SAR not in sensor_set and self.max_sar_resolution_m is not None:
            raise ValueError("Zlecenie bez SAR nie może posiadać max_sar_resolution_m")

        if (
            SensorType.OPTICAL not in sensor_set
            and self.max_optical_resolution_m is not None
        ):
            raise ValueError(
                "Zlecenie bez EO nie może posiadać max_optical_resolution_m"
            )

    def resolution_limit_for(self, sensor_type: SensorType) -> float:
        """Zwraca limit rozdzielczości właściwy dla danego typu sensora."""

        if sensor_type == SensorType.SAR and self.max_sar_resolution_m is not None:
            return self.max_sar_resolution_m

        if (
            sensor_type == SensorType.OPTICAL
            and self.max_optical_resolution_m is not None
        ):
            return self.max_optical_resolution_m

        return self.max_resolution_m

    @property
    def requires_sar(self) -> bool:
        """Informuje, czy zlecenie dopuszcza lub wymaga SAR."""

        return SensorType.SAR in self.requested_sensor_types

    @property
    def requires_optical(self) -> bool:
        """Informuje, czy zlecenie dopuszcza lub wymaga sensora EO."""

        return SensorType.OPTICAL in self.requested_sensor_types

    @property
    def minimum_required_acquisitions(self) -> int:
        """Minimalna liczba akwizycji potrzebna do realizacji."""

        if self.request_mode == RequestMode.DUAL_REQUIRED:
            return 2

        return 1

    @property
    def maximum_allowed_acquisitions(self) -> int:
        """Maksymalna liczba akwizycji dla zlecenia."""

        if self.request_mode == RequestMode.SINGLE:
            return 1

        return 2
