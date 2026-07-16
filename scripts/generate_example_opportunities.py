import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


from _bootstrap import PROJECT_PATHS, PROJECT_ROOT


from app.io import load_system_catalog
from app.models.catalog import SystemCatalog
from app.models.enums import ObservationSide, SensorType
from app.models.imaging import ImagingMode
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request import ObservationRequest
from app.models.request_set import ObservationRequestSet
from app.models.sensor import Sensor
from app.io import load_request_set


CATALOG_PATH = PROJECT_PATHS.scenario("EXAMPLE").catalog

REQUEST_SET_PATH = PROJECT_PATHS.scenario("EXAMPLE").requests

OUTPUT_PATH = PROJECT_PATHS.scenario("EXAMPLE").opportunities

RANDOM_SEED = 20260715
OPPORTUNITIES_PER_REQUEST = 10


def select_mode(
    sensor: Sensor,
    request: ObservationRequest,
) -> ImagingMode:
    """Wybiera najmniej wymagający tryb spełniający rozdzielczość."""

    candidates = [
        mode
        for mode in sensor.imaging_modes
        if (
            mode.is_active
            and mode.nominal_resolution_m
            <= request.max_resolution_m
        )
    ]

    if not candidates:
        raise ValueError(
            f"Brak trybu dla zlecenia {request.request_id} "
            f"i sensora {sensor.sensor_id}"
        )

    return sorted(
        candidates,
        key=lambda mode: (
            -mode.nominal_resolution_m,
            mode.data_rate_mb_s,
            mode.mode_id,
        ),
    )[0]


def calculate_duration_s(
    mode: ImagingMode,
    local_index: int,
) -> float:
    """Wyznacza czas akwizycji wewnątrz limitów trybu."""

    ratio = ((local_index % 5) + 1) / 6.0

    duration = (
        mode.min_acquisition_duration_s
        + (
            mode.max_acquisition_duration_s
            - mode.min_acquisition_duration_s
        )
        * ratio
    )

    return round(duration, 3)


def calculate_time_window(
    request: ObservationRequest,
    duration_s: float,
    local_index: int,
    count: int,
    rng: random.Random,
) -> tuple[datetime, datetime]:
    """Rozmieszcza okazję wewnątrz okna zlecenia."""

    window_duration_s = (
        request.latest_end_utc
        - request.earliest_start_utc
    ).total_seconds()

    fraction = (local_index + 1) / (count + 1)

    center = (
        request.earliest_start_utc
        + timedelta(
            seconds=window_duration_s * fraction
        )
    )

    jitter_limit_s = min(
        300.0,
        window_duration_s / (4.0 * (count + 1)),
    )

    center += timedelta(
        seconds=rng.uniform(
            -jitter_limit_s,
            jitter_limit_s,
        )
    )

    start_utc = center - timedelta(
        seconds=duration_s / 2.0
    )

    latest_possible_start = (
        request.latest_end_utc
        - timedelta(seconds=duration_s)
    )

    if start_utc < request.earliest_start_utc:
        start_utc = request.earliest_start_utc

    if start_utc > latest_possible_start:
        start_utc = latest_possible_start

    end_utc = start_utc + timedelta(
        seconds=duration_s
    )

    return start_utc, end_utc


def build_observation_parameters(
    *,
    sensor_type: SensorType,
    request: ObservationRequest,
    mode: ImagingMode,
    local_index: int,
    rng: random.Random,
) -> dict[str, Any]:
    """Generuje kąty, pogodę i pokrycie."""

    deliberately_feasible = local_index % 5 == 0
    deliberately_infeasible = local_index % 5 == 4

    if deliberately_feasible:
        coverage_ratio = max(
            request.minimum_coverage_ratio,
            0.95,
        )

        if sensor_type == SensorType.SAR:
            return {
                "observation_side": ObservationSide.RIGHT,
                "off_nadir_angle_deg": 25.0,
                "incidence_angle_deg": 30.0,
                "cloud_cover": None,
                "sun_elevation_deg": None,
                "coverage_ratio": coverage_ratio,
            }

        return {
            "observation_side": ObservationSide.NADIR,
            "off_nadir_angle_deg": 0.0,
            "incidence_angle_deg": None,
            "cloud_cover": 0.1,
            "sun_elevation_deg": 35.0,
            "coverage_ratio": coverage_ratio,
        }

    if deliberately_infeasible:
        coverage_ratio = max(
            0.1,
            request.minimum_coverage_ratio - 0.15,
        )

        if sensor_type == SensorType.SAR:
            return {
                "observation_side": ObservationSide.LEFT,
                "off_nadir_angle_deg": 50.0,
                "incidence_angle_deg": 55.0,
                "cloud_cover": None,
                "sun_elevation_deg": None,
                "coverage_ratio": coverage_ratio,
            }

        cloud_limit = (
            request.max_cloud_cover
            if request.max_cloud_cover is not None
            else 0.3
        )

        return {
            "observation_side": ObservationSide.RIGHT,
            "off_nadir_angle_deg": 50.0,
            "incidence_angle_deg": None,
            "cloud_cover": min(
                1.0,
                cloud_limit + 0.2,
            ),
            "sun_elevation_deg": 5.0,
            "coverage_ratio": coverage_ratio,
        }

    coverage_ratio = round(
        rng.uniform(0.78, 1.0),
        4,
    )

    if sensor_type == SensorType.SAR:
        off_nadir_angle_deg = round(
            rng.uniform(12.0, 52.0),
            3,
        )

        incidence_angle_deg = round(
            min(
                75.0,
                off_nadir_angle_deg
                + rng.uniform(3.0, 9.0),
            ),
            3,
        )

        observation_side = (
            ObservationSide.LEFT
            if local_index % 2 == 0
            else ObservationSide.RIGHT
        )

        return {
            "observation_side": observation_side,
            "off_nadir_angle_deg": off_nadir_angle_deg,
            "incidence_angle_deg": incidence_angle_deg,
            "cloud_cover": None,
            "sun_elevation_deg": None,
            "coverage_ratio": coverage_ratio,
        }

    side_sequence = [
        ObservationSide.NADIR,
        ObservationSide.LEFT,
        ObservationSide.RIGHT,
    ]

    observation_side = side_sequence[
        local_index % len(side_sequence)
    ]

    if observation_side == ObservationSide.NADIR:
        off_nadir_angle_deg = 0.0
    else:
        off_nadir_angle_deg = round(
            rng.uniform(5.0, 50.0),
            3,
        )

    return {
        "observation_side": observation_side,
        "off_nadir_angle_deg": off_nadir_angle_deg,
        "incidence_angle_deg": None,
        "cloud_cover": round(
            rng.uniform(0.05, 0.55),
            4,
        ),
        "sun_elevation_deg": round(
            rng.uniform(5.0, 50.0),
            3,
        ),
        "coverage_ratio": coverage_ratio,
    }


def determine_infeasibility_reasons(
    *,
    request: ObservationRequest,
    sensor: Sensor,
    mode: ImagingMode,
    parameters: dict[str, Any],
) -> list[str]:
    """Sprawdza podstawowe ograniczenia wykonalności."""

    reasons: list[str] = []

    coverage_ratio = parameters["coverage_ratio"]
    off_nadir_angle_deg = parameters[
        "off_nadir_angle_deg"
    ]

    if (
        mode.nominal_resolution_m
        > request.max_resolution_m
    ):
        reasons.append(
            "Niewystarczająca rozdzielczość trybu"
        )

    if (
        coverage_ratio
        < request.minimum_coverage_ratio
    ):
        reasons.append(
            "Niewystarczające pokrycie celu"
        )

    if (
        off_nadir_angle_deg
        > mode.max_off_nadir_deg
    ):
        reasons.append(
            "Przekroczony limit off-nadir trybu"
        )

    if (
        request.max_off_nadir_deg is not None
        and off_nadir_angle_deg
        > request.max_off_nadir_deg
    ):
        reasons.append(
            "Przekroczony limit off-nadir zlecenia"
        )

    if sensor.sensor_type == SensorType.SAR:
        incidence_angle_deg = parameters[
            "incidence_angle_deg"
        ]

        if (
            mode.min_incidence_angle_deg is not None
            and incidence_angle_deg
            < mode.min_incidence_angle_deg
        ):
            reasons.append(
                "Kąt padania poniżej minimum trybu"
            )

        if (
            mode.max_incidence_angle_deg is not None
            and incidence_angle_deg
            > mode.max_incidence_angle_deg
        ):
            reasons.append(
                "Kąt padania powyżej maksimum trybu"
            )

        if (
            request.max_incidence_angle_deg is not None
            and incidence_angle_deg
            > request.max_incidence_angle_deg
        ):
            reasons.append(
                "Przekroczony limit kąta padania zlecenia"
            )

    else:
        cloud_cover = parameters["cloud_cover"]
        sun_elevation_deg = parameters[
            "sun_elevation_deg"
        ]

        if (
            request.max_cloud_cover is not None
            and cloud_cover
            > request.max_cloud_cover
        ):
            reasons.append(
                "Przekroczony limit zachmurzenia"
            )

        if (
            sensor.minimum_sun_elevation_deg is not None
            and sun_elevation_deg
            < sensor.minimum_sun_elevation_deg
        ):
            reasons.append(
                "Elewacja Słońca poniżej minimum"
            )

    return reasons


def calculate_quality_score(
    *,
    mode: ImagingMode,
    parameters: dict[str, Any],
) -> float:
    """Wyznacza uproszczoną ocenę jakości od 0 do 1."""

    off_nadir_angle_deg = parameters[
        "off_nadir_angle_deg"
    ]
    coverage_ratio = parameters["coverage_ratio"]

    angle_factor = max(
        0.2,
        1.0 - off_nadir_angle_deg / 90.0,
    )

    weather_factor = 1.0

    cloud_cover = parameters["cloud_cover"]
    sun_elevation_deg = parameters[
        "sun_elevation_deg"
    ]

    if cloud_cover is not None:
        weather_factor *= max(
            0.1,
            1.0 - cloud_cover,
        )

    if sun_elevation_deg is not None:
        weather_factor *= max(
            0.2,
            min(
                1.0,
                sun_elevation_deg / 30.0,
            ),
        )

    score = (
        mode.quality_factor
        * coverage_ratio
        * angle_factor
        * weather_factor
    )

    return round(
        max(0.0, min(1.0, score)),
        6,
    )


def build_opportunity_set(
    catalog: SystemCatalog,
    request_set: ObservationRequestSet,
) -> AcquisitionOpportunitySet:
    """Buduje deterministyczny zbiór 200 okazji."""

    rng = random.Random(RANDOM_SEED)

    satellites_by_type = {
        SensorType.SAR: sorted(
            [
                satellite
                for satellite in catalog.active_satellites
                if catalog.get_sensor(
                    satellite.sensor_id
                ).sensor_type == SensorType.SAR
            ],
            key=lambda satellite: satellite.satellite_id,
        ),
        SensorType.OPTICAL: sorted(
            [
                satellite
                for satellite in catalog.active_satellites
                if catalog.get_sensor(
                    satellite.sensor_id
                ).sensor_type
                == SensorType.OPTICAL
            ],
            key=lambda satellite: satellite.satellite_id,
        ),
    }

    opportunities: list[dict[str, Any]] = []
    global_counter = 1

    for request_index, request in enumerate(
        request_set.active_requests
    ):
        if len(request.requested_sensor_types) == 1:
            generation_plan = [
                (
                    request.requested_sensor_types[0],
                    OPPORTUNITIES_PER_REQUEST,
                )
            ]
        else:
            generation_plan = [
                (SensorType.SAR, 5),
                (SensorType.OPTICAL, 5),
            ]

        for sensor_type, count in generation_plan:
            satellites = satellites_by_type[sensor_type]

            for local_index in range(count):
                satellite = satellites[
                    (request_index + local_index)
                    % len(satellites)
                ]

                sensor = catalog.get_sensor(
                    satellite.sensor_id
                )

                mode = select_mode(
                    sensor,
                    request,
                )

                duration_s = calculate_duration_s(
                    mode,
                    local_index,
                )

                start_utc, end_utc = calculate_time_window(
                    request=request,
                    duration_s=duration_s,
                    local_index=local_index,
                    count=count,
                    rng=rng,
                )

                parameters = build_observation_parameters(
                    sensor_type=sensor_type,
                    request=request,
                    mode=mode,
                    local_index=local_index,
                    rng=rng,
                )

                reasons = determine_infeasibility_reasons(
                    request=request,
                    sensor=sensor,
                    mode=mode,
                    parameters=parameters,
                )

                is_feasible = not reasons

                quality_score = calculate_quality_score(
                    mode=mode,
                    parameters=parameters,
                )

                estimated_data_volume_mb = round(
                    mode.data_rate_mb_s
                    * duration_s,
                    6,
                )

                sensor_label = (
                    "SAR"
                    if sensor_type == SensorType.SAR
                    else "EO"
                )

                opportunity_id = (
                    f"OPP-{sensor_label}-{global_counter:04d}"
                )

                opportunities.append(
                    {
                        "opportunity_id": opportunity_id,
                        "request_id": request.request_id,
                        "satellite_id": satellite.satellite_id,
                        "sensor_id": sensor.sensor_id,
                        "mode_id": mode.mode_id,
                        "sensor_type": sensor_type.value,
                        "start_utc": start_utc,
                        "end_utc": end_utc,
                        "observation_side": parameters[
                            "observation_side"
                        ].value,
                        "off_nadir_angle_deg": parameters[
                            "off_nadir_angle_deg"
                        ],
                        "incidence_angle_deg": parameters[
                            "incidence_angle_deg"
                        ],
                        "cloud_cover": parameters[
                            "cloud_cover"
                        ],
                        "sun_elevation_deg": parameters[
                            "sun_elevation_deg"
                        ],
                        "coverage_ratio": parameters[
                            "coverage_ratio"
                        ],
                        "quality_score": quality_score,
                        "estimated_data_volume_mb": (
                            estimated_data_volume_mb
                        ),
                        "is_feasible": is_feasible,
                        "infeasibility_reasons": reasons,
                        "source_type": "SYNTHETIC",
                        "source_reference": None,
                        "notes": None,
                    }
                )

                global_counter += 1

    opportunity_set = AcquisitionOpportunitySet(
        opportunity_set_id="OPPSET-PL-DEMO",
        name="Syntetyczne dobowe okazje akwizycyjne",
        version="1.0.0",
        catalog_id=catalog.catalog_id,
        request_set_id=request_set.request_set_id,
        horizon_start_utc=request_set.horizon_start_utc,
        horizon_end_utc=request_set.horizon_end_utc,
        generated_at_utc=datetime(
            2026,
            7,
            14,
            21,
            0,
            0,
            tzinfo=timezone.utc,
        ),
        random_seed=RANDOM_SEED,
        opportunities=opportunities,
        notes=(
            "Okazje syntetyczne przeznaczone do testowania "
            "algorytmów harmonogramowania."
        ),
    )

    opportunity_set.validate_against(
        catalog,
        request_set,
    )

    return opportunity_set


def main() -> None:
    catalog = load_system_catalog(
        CATALOG_PATH
    )

    request_set = load_request_set(
        REQUEST_SET_PATH
    )

    opportunity_set = build_opportunity_set(
        catalog,
        request_set,
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_data = opportunity_set.model_dump(
        mode="json",
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            output_data,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Zapisano {len(opportunity_set.opportunities)} "
        "okazji do:"
    )
    print(OUTPUT_PATH)
    print(
        "Wykonalne: "
        f"{len(opportunity_set.feasible_opportunities)}"
    )
    print(
        "Niewykonalne: "
        f"{len(opportunity_set.infeasible_opportunities)}"
    )
    print(
        f"Typy sensorów: {opportunity_set.sensor_type_counts}"
    )


if __name__ == "__main__":
    main()