from collections import Counter

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import SensorType
from app.models.ground_station import GroundStation
from app.models.imaging import ImagingMode
from app.models.orbit import OrbitDefinition
from app.models.satellite import Satellite
from app.models.sensor import Sensor


class SystemCatalog(BaseModel):
    """Kompletny katalog modelowanego systemu satelitarnego."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    catalog_id: str = Field(
        pattern=r"^CATALOG-[A-Z0-9-]+$",
    )

    name: str = Field(
        min_length=1,
        max_length=150,
    )

    version: str = Field(
        pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$",
    )

    orbits: list[OrbitDefinition] = Field(
        min_length=1,
    )

    sensors: list[Sensor] = Field(
        min_length=1,
    )

    satellites: list[Satellite] = Field(
        min_length=1,
    )

    ground_stations: list[GroundStation] = Field(
        default_factory=list,
    )

    notes: str | None = Field(
        default=None,
        max_length=2000,
    )

    @model_validator(mode="after")
    def validate_catalog_configuration(
        self,
    ) -> "SystemCatalog":
        self._validate_unique_identifiers()
        self._validate_sensor_identifiers()
        self._validate_ground_station_identifiers()
        self._validate_satellite_references()
        self._validate_unique_phases()

        return self

    def _validate_unique_identifiers(self) -> None:
        self._ensure_unique(
            [orbit.orbit_id for orbit in self.orbits],
            "orbit_id",
        )

        self._ensure_unique(
            [sensor.sensor_id for sensor in self.sensors],
            "sensor_id",
        )

        self._ensure_unique(
            [
                satellite.satellite_id
                for satellite in self.satellites
            ],
            "satellite_id",
        )

        self._ensure_unique(
            [
                mode.mode_id
                for mode in self.imaging_modes
            ],
            "mode_id",
        )

        self._ensure_unique(
            [station.ground_station_id for station in self.ground_stations],
            "ground_station_id",
        )

    @staticmethod
    def _ensure_unique(
        values: list[str],
        field_name: str,
    ) -> None:
        duplicates = sorted(
            value
            for value, count in Counter(values).items()
            if count > 1
        )

        if duplicates:
            duplicate_text = ", ".join(duplicates)

            raise ValueError(
                f"Katalog zawiera zduplikowane {field_name}: "
                f"{duplicate_text}"
            )

    def _validate_ground_station_identifiers(self) -> None:
        for station in self.ground_stations:
            if not station.ground_station_id.startswith("GS-"):
                raise ValueError(
                    "Identyfikator stacji naziemnej musi rozpoczynać się od GS-"
                )

    def _validate_sensor_identifiers(self) -> None:
        for sensor in self.sensors:
            if sensor.sensor_type == SensorType.SAR:
                expected_sensor_prefix = "SENSOR-SAR-"
                expected_mode_prefix = "MODE-SAR-"
            else:
                expected_sensor_prefix = "SENSOR-EO-"
                expected_mode_prefix = "MODE-OPT-"

            if not sensor.sensor_id.startswith(
                expected_sensor_prefix
            ):
                raise ValueError(
                    f"Sensor {sensor.sensor_id} typu "
                    f"{sensor.sensor_type.value} musi rozpoczynać się "
                    f"od {expected_sensor_prefix}"
                )

            for mode in sensor.imaging_modes:
                if not mode.mode_id.startswith(
                    expected_mode_prefix
                ):
                    raise ValueError(
                        f"Tryb {mode.mode_id} sensora "
                        f"{sensor.sensor_id} musi rozpoczynać się "
                        f"od {expected_mode_prefix}"
                    )

    def _validate_satellite_references(self) -> None:
        orbit_by_id = {
            orbit.orbit_id: orbit
            for orbit in self.orbits
        }

        sensor_by_id = {
            sensor.sensor_id: sensor
            for sensor in self.sensors
        }

        for satellite in self.satellites:
            if satellite.orbit_id not in orbit_by_id:
                raise ValueError(
                    f"Satelita {satellite.satellite_id} odwołuje się "
                    f"do nieistniejącej orbity {satellite.orbit_id}"
                )

            if satellite.sensor_id not in sensor_by_id:
                raise ValueError(
                    f"Satelita {satellite.satellite_id} odwołuje się "
                    f"do nieistniejącego sensora "
                    f"{satellite.sensor_id}"
                )

            referenced_sensor = sensor_by_id[
                satellite.sensor_id
            ]

            expected_sensor_type = (
                SensorType.SAR
                if satellite.satellite_id.startswith("SAR-")
                else SensorType.OPTICAL
            )

            if (
                referenced_sensor.sensor_type
                != expected_sensor_type
            ):
                raise ValueError(
                    f"Satelita {satellite.satellite_id} jest "
                    f"niezgodny z typem sensora "
                    f"{referenced_sensor.sensor_id}"
                )

    def _validate_unique_phases(self) -> None:
        phases_by_constellation: dict[
            str,
            set[float],
        ] = {}

        for satellite in self.satellites:
            constellation_phases = (
                phases_by_constellation.setdefault(
                    satellite.constellation_id,
                    set(),
                )
            )

            normalized_phase = round(
                satellite.phase_angle_deg,
                9,
            )

            if normalized_phase in constellation_phases:
                raise ValueError(
                    f"Podkonstelacja "
                    f"{satellite.constellation_id} zawiera "
                    f"zduplikowany kąt fazowy "
                    f"{satellite.phase_angle_deg}"
                )

            constellation_phases.add(normalized_phase)

    @property
    def imaging_modes(self) -> list[ImagingMode]:
        """Zwraca wszystkie tryby obrazowania ze wszystkich sensorów."""

        return [
            mode
            for sensor in self.sensors
            for mode in sensor.imaging_modes
        ]

    @property
    def active_satellites(self) -> list[Satellite]:
        """Zwraca satelity dostępne do planowania."""

        return [
            satellite
            for satellite in self.satellites
            if satellite.is_available_for_planning
        ]

    @property
    def constellation_counts(self) -> dict[str, int]:
        """Zwraca liczbę satelitów w każdej podkonstelacji."""

        return dict(
            Counter(
                satellite.constellation_id
                for satellite in self.satellites
            )
        )

    def get_orbit(
        self,
        orbit_id: str,
    ) -> OrbitDefinition:
        """Zwraca orbitę na podstawie identyfikatora."""

        for orbit in self.orbits:
            if orbit.orbit_id == orbit_id:
                return orbit

        raise KeyError(
            f"Nie znaleziono orbity: {orbit_id}"
        )

    def get_sensor(
        self,
        sensor_id: str,
    ) -> Sensor:
        """Zwraca sensor na podstawie identyfikatora."""

        for sensor in self.sensors:
            if sensor.sensor_id == sensor_id:
                return sensor

        raise KeyError(
            f"Nie znaleziono sensora: {sensor_id}"
        )

    def get_satellite(
        self,
        satellite_id: str,
    ) -> Satellite:
        """Zwraca satelitę na podstawie identyfikatora."""

        for satellite in self.satellites:
            if satellite.satellite_id == satellite_id:
                return satellite

        raise KeyError(
            f"Nie znaleziono satelity: {satellite_id}"
        )
    def get_ground_station(
        self,
        ground_station_id: str,
    ) -> GroundStation:
        """Zwraca stację naziemną na podstawie identyfikatora."""

        for station in self.ground_stations:
            if station.ground_station_id == ground_station_id:
                return station

        raise KeyError(
            f"Nie znaleziono stacji naziemnej: {ground_station_id}"
        )
