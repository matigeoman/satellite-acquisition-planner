from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.models.catalog import SystemCatalog
from app.models.enums import (
    ObservationSide,
    RequestMode,
    SensorType,
)
from app.models.imaging import ImagingMode
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request import ObservationRequest
from app.models.request_set import ObservationRequestSet
from app.models.sensor import Sensor


STRESS_HORIZON_START = datetime(
    2026,
    7,
    16,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)

STRESS_HORIZON_END = (
    STRESS_HORIZON_START
    + timedelta(days=1)
)

STRESS_RANDOM_SEED = 20260716

TRAP_PATTERN = re.compile(
    r"^REQ-STRESS-(SAR|EO)-T([0-9]{2})-([ABC])$"
)

TARGETS = [
    (21.0122, 52.2297),
    (18.6466, 54.3520),
    (19.9450, 50.0647),
    (17.0385, 51.1079),
    (16.9252, 52.4064),
    (14.5528, 53.4285),
    (22.5684, 51.2465),
    (23.1688, 53.1325),
    (19.0238, 50.2649),
    (22.0047, 50.0412),
    (18.5984, 53.0138),
    (19.4560, 51.7592),
    (20.4801, 53.7784),
    (17.9213, 50.6751),
    (20.6286, 50.8661),
    (15.5062, 51.9356),
    (21.1471, 51.4027),
    (18.5305, 54.5189),
    (16.1801, 54.1944),
    (23.8903, 50.4470),
]


def build_stress_catalog(
    base_catalog: SystemCatalog,
) -> SystemCatalog:
    """Buduje katalog z celowo ograniczonymi zasobami."""

    data = base_catalog.model_dump(
        mode="json",
    )

    data["catalog_id"] = "CATALOG-PL-STRESS"
    data["name"] = "Polski system obserwacji Ziemi — stres"
    data["version"] = "1.2.0"
    data["notes"] = (
        "Katalog stresowy z ograniczoną pamięcią, "
        "czasem obrazowania i liczbą akwizycji."
    )

    for satellite in data["satellites"]:
        satellite_id = satellite["satellite_id"]

        if satellite_id.startswith("SAR-"):
            satellite["memory_capacity_mb"] = 20_000.0
            satellite["max_acquisitions_per_day"] = 8
            satellite["max_imaging_time_per_day_s"] = 600.0
        else:
            satellite["memory_capacity_mb"] = 30_000.0
            satellite["max_acquisitions_per_day"] = 12
            satellite["max_imaging_time_per_day_s"] = 360.0

    return SystemCatalog.model_validate(
        data
    )


def build_stress_request_set() -> ObservationRequestSet:
    """Buduje 80 zleceń stresowych."""

    requests: list[ObservationRequest] = []
    geometry_index = 0

    for global_group_index in range(12):
        if global_group_index < 6:
            sensor_type = SensorType.SAR
            sensor_label = "SAR"
            local_group_index = global_group_index + 1
        else:
            sensor_type = SensorType.OPTICAL
            sensor_label = "EO"
            local_group_index = global_group_index - 5

        base_time = (
            STRESS_HORIZON_START
            + timedelta(hours=1)
            + timedelta(
                minutes=90 * global_group_index
            )
        )

        for role in ("A", "B", "C"):
            if role == "A":
                priority = 10
                earliest_start = (
                    base_time
                    - timedelta(minutes=2)
                )
                latest_end = (
                    base_time
                    + timedelta(minutes=30)
                )
                mandatory = global_group_index < 4
                role_name = "kotwica"
            else:
                priority = 9
                earliest_start = (
                    base_time
                    - timedelta(minutes=2)
                )
                latest_end = (
                    base_time
                    + timedelta(minutes=12)
                )
                mandatory = False
                role_name = "zlecenie zależne"

            requests.append(
                _create_request(
                    request_id=(
                        f"REQ-STRESS-{sensor_label}-"
                        f"T{local_group_index:02d}-{role}"
                    ),
                    name=(
                        f"Pułapka {sensor_label} "
                        f"{local_group_index:02d} — {role_name} {role}"
                    ),
                    geometry_index=geometry_index,
                    priority=priority,
                    earliest_start_utc=earliest_start,
                    latest_end_utc=latest_end,
                    request_mode=RequestMode.SINGLE,
                    sensor_types=[sensor_type],
                    max_resolution_m=(
                        1.0
                        if sensor_type == SensorType.SAR
                        else 0.3
                    ),
                    is_mandatory=mandatory,
                    notes=(
                        f"TRAP|{sensor_label}|"
                        f"{local_group_index:02d}|{role}"
                    ),
                )
            )

            geometry_index += 1

    for index in range(14):
        start = (
            STRESS_HORIZON_START
            + timedelta(minutes=60)
            + timedelta(
                minutes=120 * (index % 7)
            )
            + timedelta(
                minutes=15 * (index // 7)
            )
        )

        requests.append(
            _create_request(
                request_id=(
                    f"REQ-STRESS-SAR-{index + 1:03d}"
                ),
                name=(
                    f"Stresowe zlecenie SAR {index + 1:03d}"
                ),
                geometry_index=geometry_index,
                priority=8 - (index % 6),
                earliest_start_utc=start,
                latest_end_utc=(
                    start + timedelta(minutes=100)
                ),
                request_mode=RequestMode.SINGLE,
                sensor_types=[SensorType.SAR],
                max_resolution_m=(
                    [0.5, 1.0, 3.0][index % 3]
                ),
                is_mandatory=False,
                notes="STRESS|SINGLE|SAR",
            )
        )

        geometry_index += 1

    for index in range(14):
        start = (
            STRESS_HORIZON_START
            + timedelta(minutes=90)
            + timedelta(
                minutes=120 * (index % 7)
            )
            + timedelta(
                minutes=15 * (index // 7)
            )
        )

        requests.append(
            _create_request(
                request_id=(
                    f"REQ-STRESS-EO-{index + 1:03d}"
                ),
                name=(
                    f"Stresowe zlecenie optyczne "
                    f"{index + 1:03d}"
                ),
                geometry_index=geometry_index,
                priority=8 - (index % 6),
                earliest_start_utc=start,
                latest_end_utc=(
                    start + timedelta(minutes=100)
                ),
                request_mode=RequestMode.SINGLE,
                sensor_types=[SensorType.OPTICAL],
                max_resolution_m=(
                    0.3
                    if index % 2 == 0
                    else 1.2
                ),
                is_mandatory=False,
                notes="STRESS|SINGLE|OPTICAL",
            )
        )

        geometry_index += 1

    for index in range(8):
        start = (
            STRESS_HORIZON_START
            + timedelta(hours=2)
            + timedelta(
                minutes=120 * index
            )
        )

        requests.append(
            _create_request(
                request_id=(
                    f"REQ-STRESS-DOPT-{index + 1:03d}"
                ),
                name=(
                    "Stresowe zlecenie DUAL_OPTIONAL "
                    f"{index + 1:03d}"
                ),
                geometry_index=geometry_index,
                priority=7 - (index % 4),
                earliest_start_utc=start,
                latest_end_utc=(
                    start + timedelta(hours=3)
                ),
                request_mode=RequestMode.DUAL_OPTIONAL,
                sensor_types=[
                    SensorType.SAR,
                    SensorType.OPTICAL,
                ],
                max_resolution_m=1.2,
                is_mandatory=False,
                notes="STRESS|DUAL_OPTIONAL",
            )
        )

        geometry_index += 1

    for index in range(8):
        start = (
            STRESS_HORIZON_START
            + timedelta(hours=3)
            + timedelta(
                minutes=120 * index
            )
        )

        requests.append(
            _create_request(
                request_id=(
                    f"REQ-STRESS-DREQ-{index + 1:03d}"
                ),
                name=(
                    "Stresowe zlecenie DUAL_REQUIRED "
                    f"{index + 1:03d}"
                ),
                geometry_index=geometry_index,
                priority=6 - (index % 4),
                earliest_start_utc=start,
                latest_end_utc=(
                    start + timedelta(hours=4)
                ),
                request_mode=RequestMode.DUAL_REQUIRED,
                sensor_types=[
                    SensorType.SAR,
                    SensorType.OPTICAL,
                ],
                max_resolution_m=1.2,
                is_mandatory=False,
                notes="STRESS|DUAL_REQUIRED",
            )
        )

        geometry_index += 1

    return ObservationRequestSet(
        request_set_id="REQSET-PL-STRESS",
        name="Dobowy scenariusz stresowy",
        version="1.0.0",
        horizon_start_utc=STRESS_HORIZON_START,
        horizon_end_utc=STRESS_HORIZON_END,
        generated_at_utc=datetime(
            2026,
            7,
            15,
            20,
            0,
            0,
            tzinfo=timezone.utc,
        ),
        requests=requests,
        notes=(
            "Scenariusz zawiera 80 zleceń, w tym "
            "celowo skonstruowane lokalne pułapki dla Greedy."
        ),
    )


def build_stress_opportunity_set(
    catalog: SystemCatalog,
    request_set: ObservationRequestSet,
) -> AcquisitionOpportunitySet:
    """Buduje 800 wykonalnych okazji akwizycyjnych."""

    opportunities: list[dict[str, Any]] = []
    global_counter = 1

    for request_index, request in enumerate(
        request_set.active_requests
    ):
        trap_match = TRAP_PATTERN.match(
            request.request_id
        )

        if trap_match:
            generated, global_counter = (
                _generate_trap_opportunities(
                    catalog=catalog,
                    request=request,
                    match=trap_match,
                    global_counter=global_counter,
                )
            )

            opportunities.extend(
                generated
            )
            continue

        generated, global_counter = (
            _generate_generic_opportunities(
                catalog=catalog,
                request=request,
                request_index=request_index,
                global_counter=global_counter,
            )
        )

        opportunities.extend(
            generated
        )

    opportunity_set = AcquisitionOpportunitySet(
        opportunity_set_id="OPPSET-PL-STRESS",
        name="Stresowe okazje akwizycyjne",
        version="1.0.0",
        catalog_id=catalog.catalog_id,
        request_set_id=request_set.request_set_id,
        horizon_start_utc=request_set.horizon_start_utc,
        horizon_end_utc=request_set.horizon_end_utc,
        generated_at_utc=datetime(
            2026,
            7,
            15,
            21,
            0,
            0,
            tzinfo=timezone.utc,
        ),
        random_seed=STRESS_RANDOM_SEED,
        opportunities=opportunities,
        notes=(
            "800 wykonalnych okazji: 400 SAR i 400 optycznych."
        ),
    )

    opportunity_set.validate_against(
        catalog,
        request_set,
    )

    return opportunity_set


def build_stress_scenario(
    base_catalog: SystemCatalog,
) -> tuple[
    SystemCatalog,
    ObservationRequestSet,
    AcquisitionOpportunitySet,
]:
    """Buduje kompletny scenariusz stresowy."""

    catalog = build_stress_catalog(
        base_catalog
    )

    request_set = build_stress_request_set()

    opportunity_set = build_stress_opportunity_set(
        catalog,
        request_set,
    )

    return (
        catalog,
        request_set,
        opportunity_set,
    )


def save_stress_scenario(
    *,
    catalog: SystemCatalog,
    request_set: ObservationRequestSet,
    opportunity_set: AcquisitionOpportunitySet,
    output_directory: str | Path,
) -> dict[str, Path]:
    """Zapisuje trzy pliki JSON scenariusza stresowego."""

    directory = Path(
        output_directory
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    paths = {
        "catalog": directory / "system.json",
        "requests": directory / "requests.json",
        "opportunities": (
            directory
            / "opportunities.json"
        ),
    }

    _write_json(
        paths["catalog"],
        catalog.model_dump(mode="json"),
    )

    _write_json(
        paths["requests"],
        request_set.model_dump(mode="json"),
    )

    _write_json(
        paths["opportunities"],
        opportunity_set.model_dump(mode="json"),
    )

    return paths


def _create_request(
    *,
    request_id: str,
    name: str,
    geometry_index: int,
    priority: int,
    earliest_start_utc: datetime,
    latest_end_utc: datetime,
    request_mode: RequestMode,
    sensor_types: list[SensorType],
    max_resolution_m: float,
    is_mandatory: bool,
    notes: str,
) -> ObservationRequest:
    geometry = _geometry_for_index(
        geometry_index
    )

    has_optical = (
        SensorType.OPTICAL
        in sensor_types
    )

    has_sar = (
        SensorType.SAR
        in sensor_types
    )

    return ObservationRequest(
        request_id=request_id,
        name=name,
        geometry=geometry,
        priority=priority,
        earliest_start_utc=earliest_start_utc,
        latest_end_utc=latest_end_utc,
        request_mode=request_mode,
        requested_sensor_types=sensor_types,
        max_resolution_m=max_resolution_m,
        minimum_coverage_ratio=0.9,
        max_cloud_cover=(
            0.35
            if has_optical
            else None
        ),
        max_incidence_angle_deg=(
            45.0
            if has_sar
            else None
        ),
        max_off_nadir_deg=45.0,
        status="ACTIVE",
        is_mandatory=is_mandatory,
        external_reference=(
            f"STRESS-{request_id}"
        ),
        notes=notes,
    )


def _geometry_for_index(
    index: int,
) -> dict[str, Any]:
    longitude, latitude = TARGETS[
        index % len(TARGETS)
    ]

    if index % 2 == 0:
        return {
            "type": "Point",
            "coordinates": [
                longitude,
                latitude,
            ],
        }

    offset = 0.08

    return {
        "type": "Polygon",
        "coordinates": [
            [
                [
                    longitude - offset,
                    latitude - offset,
                ],
                [
                    longitude + offset,
                    latitude - offset,
                ],
                [
                    longitude + offset,
                    latitude + offset,
                ],
                [
                    longitude - offset,
                    latitude + offset,
                ],
                [
                    longitude - offset,
                    latitude - offset,
                ],
            ]
        ],
    }


def _generate_trap_opportunities(
    *,
    catalog: SystemCatalog,
    request: ObservationRequest,
    match: re.Match[str],
    global_counter: int,
) -> tuple[list[dict[str, Any]], int]:
    sensor_label = match.group(1)
    local_group_index = int(
        match.group(2)
    )
    role = match.group(3)

    sensor_type = (
        SensorType.SAR
        if sensor_label == "SAR"
        else SensorType.OPTICAL
    )

    satellites = _satellites_for_type(
        catalog,
        sensor_type,
    )

    trap_satellite = satellites[
        (local_group_index - 1)
        % len(satellites)
    ]

    safe_satellite = satellites[
        local_group_index
        % len(satellites)
    ]

    trap_sensor = catalog.get_sensor(
        trap_satellite.sensor_id
    )

    mode = _select_mode(
        trap_sensor,
        request,
    )

    duration_s = _duration_for_mode(
        mode,
        0,
    )

    transition_s = max(
        trap_satellite.minimum_transition_time_s,
        trap_sensor.warmup_time_s
        + trap_sensor.cooldown_time_s,
    )

    global_group_index = (
        local_group_index - 1
        if sensor_type == SensorType.SAR
        else local_group_index + 5
    )

    base_time = (
        STRESS_HORIZON_START
        + timedelta(hours=1)
        + timedelta(
            minutes=90 * global_group_index
        )
    )

    first_dependent_start = base_time

    second_dependent_start = (
        first_dependent_start
        + timedelta(seconds=duration_s)
        + timedelta(seconds=transition_s)
        + timedelta(seconds=10)
    )

    trap_start = (
        first_dependent_start
        + timedelta(seconds=duration_s)
        + timedelta(
            seconds=transition_s / 2.0
        )
    )

    safe_start = (
        second_dependent_start
        + timedelta(seconds=duration_s)
        + timedelta(seconds=transition_s)
        + timedelta(minutes=3)
    )

    opportunities: list[
        dict[str, Any]
    ] = []

    for variant in range(10):
        if role == "A":
            if variant == 0:
                satellite = trap_satellite
                start_utc = trap_start
                quality_score = 0.99
                coverage_ratio = 1.0
                note = "TRAP-HIGH-QUALITY"
            else:
                satellite = safe_satellite
                start_utc = (
                    safe_start
                    + timedelta(
                        seconds=45 * (variant - 1)
                    )
                )
                quality_score = round(
                    0.76 - 0.004 * variant,
                    6,
                )
                coverage_ratio = 0.95
                note = "TRAP-SAFE-ALTERNATIVE"

        elif role == "B":
            satellite = trap_satellite
            start_utc = (
                first_dependent_start
                + timedelta(seconds=variant)
            )
            quality_score = round(
                0.94 - 0.002 * variant,
                6,
            )
            coverage_ratio = 0.98
            note = "TRAP-DEPENDENT-B"

        else:
            satellite = trap_satellite
            start_utc = (
                second_dependent_start
                + timedelta(seconds=variant)
            )
            quality_score = round(
                0.93 - 0.002 * variant,
                6,
            )
            coverage_ratio = 0.98
            note = "TRAP-DEPENDENT-C"

        sensor = catalog.get_sensor(
            satellite.sensor_id
        )

        satellite_mode = _select_mode(
            sensor,
            request,
        )

        opportunity = _create_opportunity(
            global_counter=global_counter,
            request=request,
            satellite_id=satellite.satellite_id,
            sensor=sensor,
            mode=satellite_mode,
            start_utc=start_utc,
            duration_s=_duration_for_mode(
                satellite_mode,
                0,
            ),
            quality_score=quality_score,
            coverage_ratio=coverage_ratio,
            variant=variant,
            notes=note,
        )

        opportunities.append(
            opportunity
        )

        global_counter += 1

    return opportunities, global_counter


def _generate_generic_opportunities(
    *,
    catalog: SystemCatalog,
    request: ObservationRequest,
    request_index: int,
    global_counter: int,
) -> tuple[list[dict[str, Any]], int]:
    opportunities: list[
        dict[str, Any]
    ] = []

    if len(request.requested_sensor_types) == 1:
        generation_plan = [
            (
                request.requested_sensor_types[0],
                10,
            )
        ]
    else:
        generation_plan = [
            (SensorType.SAR, 5),
            (SensorType.OPTICAL, 5),
        ]

    for sensor_type, count in generation_plan:
        satellites = _satellites_for_type(
            catalog,
            sensor_type,
        )

        for variant in range(count):
            satellite = satellites[
                (
                    request_index
                    + variant
                )
                % len(satellites)
            ]

            sensor = catalog.get_sensor(
                satellite.sensor_id
            )

            mode = _select_mode(
                sensor,
                request,
            )

            duration_s = _duration_for_mode(
                mode,
                variant,
            )

            latest_start = (
                request.latest_end_utc
                - timedelta(seconds=duration_s)
            )

            available_seconds = max(
                0.0,
                (
                    latest_start
                    - request.earliest_start_utc
                ).total_seconds(),
            )

            cluster_fraction = (
                0.12
                + 0.065 * variant
            )

            cluster_fraction = min(
                cluster_fraction,
                0.88,
            )

            start_utc = (
                request.earliest_start_utc
                + timedelta(
                    seconds=(
                        available_seconds
                        * cluster_fraction
                    )
                )
            )

            quality_score = round(
                min(
                    0.96,
                    0.66
                    + 0.025
                    * (
                        (
                            request_index
                            + variant
                        )
                        % 11
                    ),
                ),
                6,
            )

            coverage_ratio = round(
                0.92
                + 0.01
                * (
                    (
                        request_index
                        + variant
                    )
                    % 7
                ),
                6,
            )

            opportunities.append(
                _create_opportunity(
                    global_counter=global_counter,
                    request=request,
                    satellite_id=(
                        satellite.satellite_id
                    ),
                    sensor=sensor,
                    mode=mode,
                    start_utc=start_utc,
                    duration_s=duration_s,
                    quality_score=quality_score,
                    coverage_ratio=coverage_ratio,
                    variant=variant,
                    notes="STRESS-GENERIC",
                )
            )

            global_counter += 1

    return opportunities, global_counter


def _create_opportunity(
    *,
    global_counter: int,
    request: ObservationRequest,
    satellite_id: str,
    sensor: Sensor,
    mode: ImagingMode,
    start_utc: datetime,
    duration_s: float,
    quality_score: float,
    coverage_ratio: float,
    variant: int,
    notes: str,
) -> dict[str, Any]:
    end_utc = (
        start_utc
        + timedelta(seconds=duration_s)
    )

    if sensor.sensor_type == SensorType.SAR:
        sensor_label = "SAR"
        observation_side = (
            ObservationSide.RIGHT
            if variant % 2 == 0
            else ObservationSide.LEFT
        )
        off_nadir_angle_deg = 25.0
        incidence_angle_deg = 30.0
        cloud_cover = None
        sun_elevation_deg = None
    else:
        sensor_label = "EO"
        observation_side = ObservationSide.NADIR
        off_nadir_angle_deg = 0.0
        incidence_angle_deg = None
        cloud_cover = round(
            0.08 + 0.01 * (variant % 8),
            4,
        )
        sun_elevation_deg = 42.0

    estimated_data_volume_mb = round(
        mode.data_rate_mb_s
        * duration_s,
        6,
    )

    return {
        "opportunity_id": (
            f"OPP-{sensor_label}-{global_counter:04d}"
        ),
        "request_id": request.request_id,
        "satellite_id": satellite_id,
        "sensor_id": sensor.sensor_id,
        "mode_id": mode.mode_id,
        "sensor_type": sensor.sensor_type.value,
        "start_utc": start_utc,
        "end_utc": end_utc,
        "observation_side": observation_side.value,
        "off_nadir_angle_deg": off_nadir_angle_deg,
        "incidence_angle_deg": incidence_angle_deg,
        "cloud_cover": cloud_cover,
        "sun_elevation_deg": sun_elevation_deg,
        "coverage_ratio": coverage_ratio,
        "quality_score": quality_score,
        "estimated_data_volume_mb": (
            estimated_data_volume_mb
        ),
        "is_feasible": True,
        "infeasibility_reasons": [],
        "source_type": "SYNTHETIC",
        "source_reference": None,
        "notes": notes,
    }


def _satellites_for_type(
    catalog: SystemCatalog,
    sensor_type: SensorType,
):
    return sorted(
        [
            satellite
            for satellite in catalog.active_satellites
            if (
                catalog.get_sensor(
                    satellite.sensor_id
                ).sensor_type
                == sensor_type
            )
        ],
        key=lambda satellite: satellite.satellite_id,
    )


def _select_mode(
    sensor: Sensor,
    request: ObservationRequest,
) -> ImagingMode:
    candidates = [
        mode
        for mode in sensor.imaging_modes
        if (
            mode.is_active
            and mode.nominal_resolution_m
            <= request.resolution_limit_for(mode.sensor_type)
        )
    ]

    if not candidates:
        raise ValueError(
            f"Brak trybu dla zlecenia "
            f"{request.request_id} "
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


def _duration_for_mode(
    mode: ImagingMode,
    variant: int,
) -> float:
    ratio = (
        0.25
        + 0.05 * (variant % 4)
    )

    duration_s = (
        mode.min_acquisition_duration_s
        + (
            mode.max_acquisition_duration_s
            - mode.min_acquisition_duration_s
        )
        * ratio
    )

    return round(
        duration_s,
        3,
    )


def _write_json(
    path: Path,
    data: dict[str, Any],
) -> None:
    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )