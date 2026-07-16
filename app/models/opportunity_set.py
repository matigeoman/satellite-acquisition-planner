from collections import Counter
from datetime import datetime, timezone
from math import isclose

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.catalog import SystemCatalog
from app.models.enums import SensorType
from app.models.imaging import ImagingMode
from app.models.opportunity import AcquisitionOpportunity
from app.models.request import ObservationRequest
from app.models.request_set import ObservationRequestSet
from app.models.sensor import Sensor


class AcquisitionOpportunitySet(BaseModel):
    """Zbiór syntetycznych lub zewnętrznych okazji akwizycyjnych."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    opportunity_set_id: str = Field(
        pattern=r"^OPPSET-[A-Z0-9-]+$",
    )

    name: str = Field(
        min_length=1,
        max_length=150,
    )

    version: str = Field(
        pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$",
    )

    catalog_id: str = Field(
        pattern=r"^CATALOG-[A-Z0-9-]+$",
    )

    request_set_id: str = Field(
        pattern=r"^REQSET-[A-Z0-9-]+$",
    )

    horizon_start_utc: datetime
    horizon_end_utc: datetime

    generated_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    random_seed: int = Field(
        ge=0,
    )

    opportunities: list[AcquisitionOpportunity] = Field(
        min_length=1,
    )

    notes: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator(
        "horizon_start_utc",
        "horizon_end_utc",
        "generated_at_utc",
    )
    @classmethod
    def validate_utc_datetime(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "Czas zbioru okazji musi zawierać strefę czasową"
            )

        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_opportunity_set_configuration(
        self,
    ) -> "AcquisitionOpportunitySet":
        self._validate_horizon()
        self._validate_unique_opportunity_ids()
        self._validate_opportunity_windows()

        return self

    def _validate_horizon(self) -> None:
        if self.horizon_start_utc >= self.horizon_end_utc:
            raise ValueError(
                "horizon_start_utc musi być wcześniejsze "
                "niż horizon_end_utc"
            )

    def _validate_unique_opportunity_ids(self) -> None:
        opportunity_ids = [
            opportunity.opportunity_id
            for opportunity in self.opportunities
        ]

        duplicates = sorted(
            opportunity_id
            for opportunity_id, count
            in Counter(opportunity_ids).items()
            if count > 1
        )

        if duplicates:
            raise ValueError(
                "Zbiór zawiera zduplikowane opportunity_id: "
                + ", ".join(duplicates)
            )

    def _validate_opportunity_windows(self) -> None:
        for opportunity in self.opportunities:
            if (
                opportunity.start_utc
                < self.horizon_start_utc
            ):
                raise ValueError(
                    f"Okazja {opportunity.opportunity_id} "
                    "rozpoczyna się przed horyzontem"
                )

            if (
                opportunity.end_utc
                > self.horizon_end_utc
            ):
                raise ValueError(
                    f"Okazja {opportunity.opportunity_id} "
                    "kończy się po horyzoncie"
                )

    def validate_against(
        self,
        catalog: SystemCatalog,
        request_set: ObservationRequestSet,
    ) -> None:
        """Sprawdza powiązania okazji z katalogiem i zleceniami."""

        if self.catalog_id != catalog.catalog_id:
            raise ValueError(
                "catalog_id zbioru okazji jest niezgodne z katalogiem"
            )

        if self.request_set_id != request_set.request_set_id:
            raise ValueError(
                "request_set_id zbioru okazji jest niezgodne "
                "ze zbiorem zleceń"
            )

        request_by_id = {
            request.request_id: request
            for request in request_set.requests
        }

        satellite_by_id = {
            satellite.satellite_id: satellite
            for satellite in catalog.satellites
        }

        sensor_by_id = {
            sensor.sensor_id: sensor
            for sensor in catalog.sensors
        }

        mode_by_id: dict[
            str,
            tuple[Sensor, ImagingMode],
        ] = {
            mode.mode_id: (sensor, mode)
            for sensor in catalog.sensors
            for mode in sensor.imaging_modes
        }

        for opportunity in self.opportunities:
            request = request_by_id.get(
                opportunity.request_id
            )

            if request is None:
                raise ValueError(
                    f"Okazja {opportunity.opportunity_id} "
                    f"odwołuje się do nieistniejącego zlecenia "
                    f"{opportunity.request_id}"
                )

            satellite = satellite_by_id.get(
                opportunity.satellite_id
            )

            if satellite is None:
                raise ValueError(
                    f"Okazja {opportunity.opportunity_id} "
                    f"odwołuje się do nieistniejącego satelity "
                    f"{opportunity.satellite_id}"
                )

            sensor = sensor_by_id.get(
                opportunity.sensor_id
            )

            if sensor is None:
                raise ValueError(
                    f"Okazja {opportunity.opportunity_id} "
                    f"odwołuje się do nieistniejącego sensora "
                    f"{opportunity.sensor_id}"
                )

            mode_record = mode_by_id.get(
                opportunity.mode_id
            )

            if mode_record is None:
                raise ValueError(
                    f"Okazja {opportunity.opportunity_id} "
                    f"odwołuje się do nieistniejącego trybu "
                    f"{opportunity.mode_id}"
                )

            mode_sensor, mode = mode_record

            self._validate_references(
                opportunity=opportunity,
                request=request,
                satellite_sensor_id=satellite.sensor_id,
                sensor=sensor,
                mode_sensor=mode_sensor,
                mode=mode,
            )

            self._validate_time_against_request(
                opportunity,
                request,
            )

            self._validate_duration_and_volume(
                opportunity,
                mode,
            )

            if opportunity.is_feasible:
                self._validate_feasible_opportunity(
                    opportunity=opportunity,
                    request=request,
                    sensor=sensor,
                    mode=mode,
                )

    @staticmethod
    def _validate_references(
        *,
        opportunity: AcquisitionOpportunity,
        request: ObservationRequest,
        satellite_sensor_id: str,
        sensor: Sensor,
        mode_sensor: Sensor,
        mode: ImagingMode,
    ) -> None:
        if satellite_sensor_id != opportunity.sensor_id:
            raise ValueError(
                f"Satelita {opportunity.satellite_id} nie posiada "
                f"sensora {opportunity.sensor_id}"
            )

        if sensor.sensor_type != opportunity.sensor_type:
            raise ValueError(
                f"Sensor {sensor.sensor_id} jest niezgodny "
                f"z sensor_type okazji"
            )

        if mode_sensor.sensor_id != sensor.sensor_id:
            raise ValueError(
                f"Tryb {mode.mode_id} nie należy do sensora "
                f"{sensor.sensor_id}"
            )

        if mode.sensor_type != opportunity.sensor_type:
            raise ValueError(
                f"Tryb {mode.mode_id} jest niezgodny "
                f"z typem okazji"
            )

        if (
            opportunity.sensor_type
            not in request.requested_sensor_types
        ):
            raise ValueError(
                f"Zlecenie {request.request_id} nie dopuszcza "
                f"typu {opportunity.sensor_type.value}"
            )

    @staticmethod
    def _validate_time_against_request(
        opportunity: AcquisitionOpportunity,
        request: ObservationRequest,
    ) -> None:
        if (
            opportunity.start_utc
            < request.earliest_start_utc
        ):
            raise ValueError(
                f"Okazja {opportunity.opportunity_id} rozpoczyna się "
                f"przed oknem zlecenia {request.request_id}"
            )

        if (
            opportunity.end_utc
            > request.latest_end_utc
        ):
            raise ValueError(
                f"Okazja {opportunity.opportunity_id} kończy się "
                f"po oknie zlecenia {request.request_id}"
            )

    @staticmethod
    def _validate_duration_and_volume(
        opportunity: AcquisitionOpportunity,
        mode: ImagingMode,
    ) -> None:
        if (
            opportunity.duration_s
            < mode.min_acquisition_duration_s
            or opportunity.duration_s
            > mode.max_acquisition_duration_s
        ):
            raise ValueError(
                f"Czas okazji {opportunity.opportunity_id} "
                f"jest niezgodny z trybem {mode.mode_id}"
            )

        expected_volume = (
            opportunity.duration_s
            * mode.data_rate_mb_s
        )

        if not isclose(
            opportunity.estimated_data_volume_mb,
            expected_volume,
            rel_tol=1e-6,
            abs_tol=0.01,
        ):
            raise ValueError(
                f"Niepoprawny rozmiar danych okazji "
                f"{opportunity.opportunity_id}"
            )

    @staticmethod
    def _validate_feasible_opportunity(
        *,
        opportunity: AcquisitionOpportunity,
        request: ObservationRequest,
        sensor: Sensor,
        mode: ImagingMode,
    ) -> None:
        if (
            mode.nominal_resolution_m
            > request.resolution_limit_for(mode.sensor_type)
        ):
            raise ValueError(
                f"Wykonalna okazja {opportunity.opportunity_id} "
                "nie spełnia wymagania rozdzielczości"
            )

        if (
            opportunity.coverage_ratio
            < request.minimum_coverage_ratio
        ):
            raise ValueError(
                f"Wykonalna okazja {opportunity.opportunity_id} "
                "nie spełnia wymagania pokrycia"
            )

        if (
            opportunity.off_nadir_angle_deg
            > mode.max_off_nadir_deg
        ):
            raise ValueError(
                f"Wykonalna okazja {opportunity.opportunity_id} "
                "przekracza limit trybu off-nadir"
            )

        if (
            request.max_off_nadir_deg is not None
            and opportunity.off_nadir_angle_deg
            > request.max_off_nadir_deg
        ):
            raise ValueError(
                f"Wykonalna okazja {opportunity.opportunity_id} "
                "przekracza limit zlecenia off-nadir"
            )

        if opportunity.sensor_type == SensorType.SAR:
            incidence_angle = opportunity.incidence_angle_deg

            if incidence_angle is None:
                raise ValueError(
                    "Wykonalna okazja SAR wymaga kąta padania"
                )

            if (
                mode.min_incidence_angle_deg is not None
                and incidence_angle
                < mode.min_incidence_angle_deg
            ):
                raise ValueError(
                    f"Wykonalna okazja {opportunity.opportunity_id} "
                    "ma zbyt mały kąt padania"
                )

            if (
                mode.max_incidence_angle_deg is not None
                and incidence_angle
                > mode.max_incidence_angle_deg
            ):
                raise ValueError(
                    f"Wykonalna okazja {opportunity.opportunity_id} "
                    "ma zbyt duży kąt padania"
                )

            if (
                request.max_incidence_angle_deg is not None
                and incidence_angle
                > request.max_incidence_angle_deg
            ):
                raise ValueError(
                    f"Wykonalna okazja {opportunity.opportunity_id} "
                    "przekracza limit kąta padania zlecenia"
                )

        else:
            cloud_cover = opportunity.cloud_cover
            sun_elevation = opportunity.sun_elevation_deg

            if cloud_cover is None:
                raise ValueError(
                    "Wykonalna okazja optyczna wymaga zachmurzenia"
                )

            if (
                request.max_cloud_cover is not None
                and cloud_cover
                > request.max_cloud_cover
            ):
                raise ValueError(
                    f"Wykonalna okazja {opportunity.opportunity_id} "
                    "przekracza limit zachmurzenia"
                )

            if (
                sensor.minimum_sun_elevation_deg is not None
                and (
                    sun_elevation is None
                    or sun_elevation
                    < sensor.minimum_sun_elevation_deg
                )
            ):
                raise ValueError(
                    f"Wykonalna okazja {opportunity.opportunity_id} "
                    "ma zbyt małą elewację Słońca"
                )

    @property
    def feasible_opportunities(
        self,
    ) -> list[AcquisitionOpportunity]:
        """Zwraca okazje dostępne dla algorytmu planowania."""

        return [
            opportunity
            for opportunity in self.opportunities
            if opportunity.is_feasible
        ]

    @property
    def infeasible_opportunities(
        self,
    ) -> list[AcquisitionOpportunity]:
        """Zwraca okazje odrzucone podczas generowania."""

        return [
            opportunity
            for opportunity in self.opportunities
            if not opportunity.is_feasible
        ]

    @property
    def sensor_type_counts(self) -> dict[str, int]:
        """Liczba okazji według typu sensora."""

        return dict(
            Counter(
                opportunity.sensor_type.value
                for opportunity in self.opportunities
            )
        )

    @property
    def satellite_counts(self) -> dict[str, int]:
        """Liczba okazji przypisanych do każdego satelity."""

        return dict(
            Counter(
                opportunity.satellite_id
                for opportunity in self.opportunities
            )
        )

    @property
    def request_counts(self) -> dict[str, int]:
        """Liczba okazji wygenerowanych dla każdego zlecenia."""

        return dict(
            Counter(
                opportunity.request_id
                for opportunity in self.opportunities
            )
        )

    def get_opportunity(
        self,
        opportunity_id: str,
    ) -> AcquisitionOpportunity:
        """Zwraca okazję na podstawie identyfikatora."""

        for opportunity in self.opportunities:
            if opportunity.opportunity_id == opportunity_id:
                return opportunity

        raise KeyError(
            f"Nie znaleziono okazji: {opportunity_id}"
        )