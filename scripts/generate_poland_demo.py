from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from _bootstrap import PROJECT_ROOT

from app.integrations.access import AccessCalculationResult
from app.integrations.orbits import (
    CelestrakQueryResult,
    PublicOrbitRecord,
    SatelliteFamily,
    TrackedSatellite,
)
from app.integrations.orbits.client import CelestrakClient
from app.models.catalog import SystemCatalog
from app.models.enums import (
    ObservationSide,
    OpportunitySourceType,
    RequestMode,
    SensorType,
)
from app.models.geometry import PointGeometry, PolygonGeometry
from app.models.opportunity import AcquisitionOpportunity
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request import ObservationRequest
from app.models.request_set import ObservationRequestSet
from app.projects.codec import encode_access_result, encode_orbit_snapshot
from app.services.access_service import PublicAccessService
from app.services.contracts import PlanningOptions
from app.services.orbit_service import PublicConstellationSnapshot, PublicOrbitService
from app.services.planning_service import PlanningService
from app.services.scenario_service import LoadedScenario, ScenarioDefinition


START_UTC = datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)
END_UTC = START_UTC + timedelta(hours=48)
RANDOM_SEED = 20260720
SCENARIO_DIRECTORY = PROJECT_ROOT / "data" / "scenarios" / "poland_demo"
EXAMPLE_DIRECTORY = PROJECT_ROOT / "examples" / "poland_demo"


TARGETS: tuple[tuple[str, float, float, bool], ...] = (
    ("Warszawa", 21.0122, 52.2297, False),
    ("Gdańsk", 18.6466, 54.3520, False),
    ("Kraków", 19.9450, 50.0647, False),
    ("Wrocław", 17.0385, 51.1079, False),
    ("Poznań", 16.9252, 52.4064, False),
    ("Lublin", 22.5684, 51.2465, False),
    ("Białystok", 23.1688, 53.1325, False),
    ("Szczecin", 14.5528, 53.4285, False),
    ("Rzeszów", 22.0047, 50.0412, False),
    ("Łódź", 19.4560, 51.7592, False),
    ("Bydgoszcz", 18.0084, 53.1235, False),
    ("Toruń", 18.5984, 53.0138, False),
    ("Olsztyn", 20.4801, 53.7784, False),
    ("Kielce", 20.6286, 50.8661, False),
    ("Opole", 17.9213, 50.6751, False),
    ("Zielona Góra", 15.5062, 51.9356, False),
    ("Suwałki", 22.9308, 54.1115, True),
    ("Wybrzeże Bałtyku", 18.6000, 54.6000, True),
    ("Żuławy Wiślane", 19.2000, 54.1500, True),
    ("Mazury", 21.5000, 53.8000, True),
    ("Górny Śląsk", 19.0500, 50.3000, True),
    ("Zagłębie Miedziowe", 16.1000, 51.4500, True),
    ("Bieszczady", 22.5000, 49.3500, True),
    ("Dolina Odry", 16.8500, 51.5000, True),
    ("Wschodnia granica", 23.5000, 52.0000, True),
)

WINDOW_DURATIONS_H = (48.0, 2.0, 3.0, 5.0, 6.0, 8.0, 12.0, 16.0, 20.0, 30.0)
WINDOW_LABELS = (
    "pełne 48 h",
    "pilne 2 h",
    "pilne 3 h",
    "krótkie 5 h",
    "krótkie 6 h",
    "krótkie 8 h",
    "średnie 12 h",
    "średnie 16 h",
    "średnie 20 h",
    "długie 30 h",
)


def _geometry(target: tuple[str, float, float, bool], index: int):
    _, longitude, latitude, polygon = target
    if not polygon:
        return PointGeometry(coordinates=(longitude, latitude))
    half_width = 0.22 + (index % 3) * 0.08
    half_height = 0.16 + (index % 2) * 0.06
    return PolygonGeometry(
        coordinates=(
            (
                (longitude - half_width, latitude - half_height),
                (longitude + half_width, latitude - half_height),
                (longitude + half_width, latitude + half_height),
                (longitude - half_width, latitude + half_height),
                (longitude - half_width, latitude - half_height),
            ),
        )
    )


def _window(index: int) -> tuple[datetime, datetime, str]:
    duration_h = WINDOW_DURATIONS_H[index % len(WINDOW_DURATIONS_H)]
    if duration_h >= 48.0:
        return START_UTC, END_UTC, WINDOW_LABELS[index % len(WINDOW_LABELS)]
    max_offset_h = 48.0 - duration_h
    offset_h = ((index * 5.75) % max_offset_h) if max_offset_h else 0.0
    offset_h = round(offset_h * 2.0) / 2.0
    start = START_UTC + timedelta(hours=offset_h)
    return start, start + timedelta(hours=duration_h), WINDOW_LABELS[index % len(WINDOW_LABELS)]


def _request_specs() -> list[tuple[str, SensorType | None, RequestMode]]:
    specs: list[tuple[str, SensorType | None, RequestMode]] = []
    specs.extend((f"REQ-DEMO-SAR-{index:03d}", SensorType.SAR, RequestMode.SINGLE) for index in range(1, 21))
    specs.extend((f"REQ-DEMO-EO-{index:03d}", SensorType.OPTICAL, RequestMode.SINGLE) for index in range(1, 21))
    specs.extend((f"REQ-DEMO-DUAL-OPT-{index:03d}", None, RequestMode.DUAL_OPTIONAL) for index in range(1, 6))
    specs.extend((f"REQ-DEMO-DUAL-REQ-{index:03d}", None, RequestMode.DUAL_REQUIRED) for index in range(1, 6))
    return specs


def build_request_set() -> ObservationRequestSet:
    requests: list[ObservationRequest] = []
    for index, (request_id, sensor_type, request_mode) in enumerate(_request_specs()):
        target = TARGETS[index % len(TARGETS)]
        start, end, window_label = _window(index)
        target_name = target[0]
        priority = 10 - (index % 8)
        mandatory = priority >= 9 and index % 3 == 0

        if request_mode == RequestMode.SINGLE and sensor_type == SensorType.SAR:
            sensor_types = [SensorType.SAR]
            resolution = 3.0 if index == 0 else (0.25, 1.0, 3.0)[index % 3]
            request = ObservationRequest(
                request_id=request_id,
                name=f"SAR — {target_name} — {window_label}",
                geometry=_geometry(target, index),
                priority=priority,
                earliest_start_utc=start,
                latest_end_utc=end,
                request_mode=request_mode,
                requested_sensor_types=sensor_types,
                max_resolution_m=resolution,
                minimum_coverage_ratio=(0.2 if index == 0 else 0.75 + (index % 3) * 0.1),
                max_incidence_angle_deg=(70.0 if index == 0 else 45.0 + (index % 2) * 5.0),
                max_off_nadir_deg=(70.0 if index == 0 else 45.0 + (index % 3) * 5.0),
                is_mandatory=mandatory,
                external_reference=f"POL-DEMO-{index + 1:03d}",
                notes=f"Zróżnicowane okno demonstracyjne: {window_label}.",
            )
        elif request_mode == RequestMode.SINGLE:
            resolution = 0.3 if index % 2 == 0 else 1.2
            request = ObservationRequest(
                request_id=request_id,
                name=f"EO — {target_name} — {window_label}",
                geometry=_geometry(target, index),
                priority=priority,
                earliest_start_utc=start,
                latest_end_utc=end,
                request_mode=request_mode,
                requested_sensor_types=[SensorType.OPTICAL],
                max_resolution_m=resolution,
                minimum_coverage_ratio=0.75 + (index % 3) * 0.1,
                max_cloud_cover=(0.15, 0.25, 0.35, 0.45)[index % 4],
                max_off_nadir_deg=35.0 + (index % 3) * 5.0,
                is_mandatory=mandatory,
                external_reference=f"POL-DEMO-{index + 1:03d}",
                notes=f"Zróżnicowane okno demonstracyjne: {window_label}.",
            )
        else:
            request = ObservationRequest(
                request_id=request_id,
                name=f"SAR+EO — {target_name} — {window_label}",
                geometry=_geometry(target, index),
                priority=priority,
                earliest_start_utc=start,
                latest_end_utc=end,
                request_mode=request_mode,
                requested_sensor_types=[SensorType.SAR, SensorType.OPTICAL],
                max_resolution_m=3.0,
                max_sar_resolution_m=1.0 if index % 2 else 3.0,
                max_optical_resolution_m=1.2,
                minimum_coverage_ratio=0.75,
                max_cloud_cover=0.35,
                max_incidence_angle_deg=50.0,
                max_off_nadir_deg=50.0,
                max_dual_separation_s=float((2 + index % 5 * 2) * 3600),
                is_mandatory=mandatory,
                external_reference=f"POL-DEMO-{index + 1:03d}",
                notes=(
                    "Zlecenie podwójne do demonstracji parowania SAR–EO; "
                    f"okno: {window_label}."
                ),
            )
        requests.append(request)

    return ObservationRequestSet(
        request_set_id="REQSET-POLAND-DEMO",
        name="Polska — 50 zróżnicowanych zleceń demonstracyjnych",
        version="1.0.0",
        horizon_start_utc=START_UTC,
        horizon_end_utc=END_UTC,
        generated_at_utc=START_UTC,
        requests=requests,
        notes=(
            "20 zleceń SAR, 20 EO, 5 DUAL_OPTIONAL i 5 DUAL_REQUIRED. "
            "Okna mają długości od 2 do 48 godzin."
        ),
    )


def _select_mode(catalog: SystemCatalog, request: ObservationRequest, sensor_type: SensorType):
    sensor = next(sensor for sensor in catalog.sensors if sensor.sensor_type == sensor_type)
    candidates = [
        mode
        for mode in sensor.imaging_modes
        if mode.nominal_resolution_m <= request.resolution_limit_for(sensor_type)
    ]
    return sensor, sorted(candidates, key=lambda mode: (-mode.nominal_resolution_m, mode.mode_id))[0]


def _interval(request: ObservationRequest, local_index: int, duration_s: float) -> tuple[datetime, datetime]:
    window_s = (request.latest_end_utc - request.earliest_start_utc).total_seconds()
    if request.request_mode == RequestMode.SINGLE:
        fraction = (local_index + 1) / 11.0
        center = request.earliest_start_utc + timedelta(seconds=window_s * fraction)
    else:
        pair_index = local_index // 2
        fraction = (pair_index + 1) / 6.0
        center = request.earliest_start_utc + timedelta(seconds=window_s * fraction)
        center += timedelta(minutes=-4 if local_index % 2 == 0 else 4)
    start = center - timedelta(seconds=duration_s / 2.0)
    latest_start = request.latest_end_utc - timedelta(seconds=duration_s)
    start = min(max(start, request.earliest_start_utc), latest_start)
    return start, start + timedelta(seconds=duration_s)


def build_opportunity_set(catalog: SystemCatalog, request_set: ObservationRequestSet) -> AcquisitionOpportunitySet:
    rng = random.Random(RANDOM_SEED)
    opportunities: list[AcquisitionOpportunity] = []
    global_index = 0

    for request_index, request in enumerate(request_set.requests):
        for local_index in range(10):
            if request.request_mode == RequestMode.SINGLE:
                sensor_type = request.requested_sensor_types[0]
            else:
                sensor_type = SensorType.SAR if local_index % 2 == 0 else SensorType.OPTICAL

            sensor, mode = _select_mode(catalog, request, sensor_type)
            satellite_count = 4 if sensor_type == SensorType.SAR else 2
            satellite_id = (
                f"SAR-{(request_index + local_index) % satellite_count + 1:02d}"
                if sensor_type == SensorType.SAR
                else f"EO-{(request_index + local_index) % satellite_count + 1:02d}"
            )
            duration_s = mode.min_acquisition_duration_s + (
                (local_index % 4) / 4.0
            ) * (mode.max_acquisition_duration_s - mode.min_acquisition_duration_s)
            duration_s = round(duration_s, 3)
            start, end = _interval(request, local_index, duration_s)

            deliberately_infeasible = local_index in {4, 9}
            coverage = max(request.minimum_coverage_ratio, 0.92)
            reasons: list[str] = []
            if sensor_type == SensorType.SAR:
                side = ObservationSide.LEFT if local_index % 2 == 0 else ObservationSide.RIGHT
                off_nadir = 24.0 + (local_index % 4) * 3.0
                incidence = 30.0 + (local_index % 4) * 2.0
                cloud = None
                sun = None
                if deliberately_infeasible:
                    off_nadir = 65.0
                    incidence = 65.0
                    coverage = max(0.2, request.minimum_coverage_ratio - 0.15)
                    reasons = ["Przekroczony limit geometrii demonstracyjnej"]
            else:
                side = ObservationSide.NADIR if local_index % 3 == 0 else ObservationSide.RIGHT
                off_nadir = 0.0 if side == ObservationSide.NADIR else 12.0 + (local_index % 4) * 4.0
                incidence = None
                cloud_limit = request.max_cloud_cover or 0.35
                cloud = round(max(0.05, cloud_limit - 0.08 - (local_index % 2) * 0.03), 3)
                sun = 32.0 + (local_index % 4) * 5.0
                if deliberately_infeasible:
                    off_nadir = 55.0
                    cloud = min(1.0, cloud_limit + 0.2)
                    sun = 7.0
                    coverage = max(0.2, request.minimum_coverage_ratio - 0.15)
                    reasons = ["Zachmurzenie lub geometria poza limitem demo"]

            global_index += 1
            opportunities.append(
                AcquisitionOpportunity(
                    opportunity_id=f"OPP-DEMO-{global_index:04d}",
                    request_id=request.request_id,
                    satellite_id=satellite_id,
                    sensor_id=sensor.sensor_id,
                    mode_id=mode.mode_id,
                    sensor_type=sensor_type,
                    start_utc=start,
                    end_utc=end,
                    observation_side=side,
                    off_nadir_angle_deg=off_nadir,
                    incidence_angle_deg=incidence,
                    cloud_cover=cloud,
                    sun_elevation_deg=sun,
                    coverage_ratio=coverage,
                    quality_score=(
                        round(rng.uniform(0.72, 0.98), 4)
                        if not deliberately_infeasible
                        else round(rng.uniform(0.18, 0.45), 4)
                    ),
                    estimated_data_volume_mb=round(duration_s * mode.data_rate_mb_s, 3),
                    is_feasible=not deliberately_infeasible,
                    infeasibility_reasons=reasons,
                    source_type=OpportunitySourceType.SYNTHETIC,
                    notes=(
                        "Deterministyczna okazja demonstracyjna; nie stanowi "
                        "potwierdzonej dostępności operatora."
                    ),
                )
            )

    result = AcquisitionOpportunitySet(
        opportunity_set_id="OPPSET-POLAND-DEMO",
        name="Polska — 500 okazji demonstracyjnych",
        version="1.0.0",
        catalog_id=catalog.catalog_id,
        request_set_id=request_set.request_set_id,
        horizon_start_utc=START_UTC,
        horizon_end_utc=END_UTC,
        generated_at_utc=START_UTC,
        random_seed=RANDOM_SEED,
        opportunities=opportunities,
        notes=(
            "Po 10 okazji na zlecenie. Około 20% celowo oznaczono jako "
            "niewykonalne, aby prezentować filtrowanie ograniczeń."
        ),
    )
    result.validate_against(catalog, request_set)
    return result


def build_snapshot() -> PublicConstellationSnapshot:
    base: dict[str, Any] = {
        "OBJECT_ID": "2026-001A",
        "EPOCH": "2026-07-15T00:00:00.000000",
        "MEAN_MOTION": 15.2,
        "ECCENTRICITY": 0.0005,
        "INCLINATION": 97.8,
        "ARG_OF_PERICENTER": 10.0,
        "BSTAR": 0.00001,
        "MEAN_MOTION_DOT": 0.0,
        "MEAN_MOTION_DDOT": 0.0,
        "ELEMENT_SET_NO": 1,
        "REV_AT_EPOCH": 100,
        "CLASSIFICATION_TYPE": "U",
        "EPHEMERIS_TYPE": 0,
    }
    satellites: list[TrackedSatellite] = []
    iceye_records: list[PublicOrbitRecord] = []
    eo_records: list[PublicOrbitRecord] = []
    for index in range(4):
        payload = dict(
            base,
            OBJECT_NAME=f"ICEYE-DEMO-{index + 1}",
            OBJECT_ID=f"2026-{index + 1:03d}A",
            NORAD_CAT_ID=65001 + index,
            RA_OF_ASC_NODE=(35.0 + index * 45.0) % 360.0,
            MEAN_ANOMALY=(20.0 + index * 70.0) % 360.0,
        )
        record = PublicOrbitRecord.from_omm(payload)
        iceye_records.append(record)
        satellites.append(
            TrackedSatellite(
                slot_id=f"SAR-{index + 1:02d}",
                family=SatelliteFamily.ICEYE,
                record=record,
            )
        )
    for index in range(2):
        payload = dict(
            base,
            OBJECT_NAME=f"PLEIADES NEO DEMO {index + 3}",
            OBJECT_ID=f"2026-{index + 11:03d}A",
            NORAD_CAT_ID=66001 + index,
            RA_OF_ASC_NODE=(15.0 + index * 95.0) % 360.0,
            MEAN_ANOMALY=(80.0 + index * 150.0) % 360.0,
        )
        record = PublicOrbitRecord.from_omm(payload)
        eo_records.append(record)
        satellites.append(
            TrackedSatellite(
                slot_id=f"EO-{index + 1:02d}",
                family=SatelliteFamily.PLEIADES_NEO,
                record=record,
            )
        )
    queries = (
        CelestrakQueryResult(
            query_name="ICEYE DEMO OFFLINE",
            records=tuple(iceye_records),
            fetched_at_utc=START_UTC,
            request_url="offline://examples/poland_demo/orbits_omm.json#iceye",
            from_cache=True,
            is_stale=False,
        ),
        CelestrakQueryResult(
            query_name="PLEIADES NEO DEMO OFFLINE",
            records=tuple(eo_records),
            fetched_at_utc=START_UTC,
            request_url="offline://examples/poland_demo/orbits_omm.json#pleiades",
            from_cache=True,
            is_stale=False,
        ),
    )
    return PublicConstellationSnapshot(
        generated_at_utc=START_UTC,
        satellites=tuple(satellites),
        queries=queries,
        warnings=(),
    )


def build_access_result(snapshot: PublicConstellationSnapshot, request_set: ObservationRequestSet) -> AccessCalculationResult:
    featured_request = request_set.requests[0]
    orbit_service = PublicOrbitService(
        client=CelestrakClient(cache_directory=PROJECT_ROOT / "data" / "generated" / "orbits")
    )
    access_service = PublicAccessService(orbit_service=orbit_service)
    result = access_service.calculate_for_request(
        request=featured_request,
        snapshot=snapshot,
        start_utc=START_UTC,
        end_utc=END_UTC,
        step=timedelta(seconds=60),
        selected_mode_ids={"MODE-SAR-ICEYE-STRIP"},
    )
    if len(result.windows) < 3:
        raise RuntimeError("Demo powinno zawierać co najmniej trzy okna dostępu")
    return result


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _aoi_geojson(request_set: ObservationRequestSet) -> dict[str, Any]:
    features = []
    for request in request_set.requests:
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "request_id": request.request_id,
                    "name": request.name,
                    "priority": request.priority,
                    "request_mode": request.request_mode.value,
                },
                "geometry": request.geometry.model_dump(mode="json"),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _scenario(catalog: SystemCatalog, requests: ObservationRequestSet, opportunities: AcquisitionOpportunitySet) -> LoadedScenario:
    return LoadedScenario(
        definition=ScenarioDefinition(
            scenario_id="POLAND_DEMO",
            name="Polska — rozbudowany scenariusz demonstracyjny",
            description="48 godzin, 50 zleceń i 500 okazji SAR/EO.",
            catalog_path=SCENARIO_DIRECTORY / "system.json",
            request_set_path=SCENARIO_DIRECTORY / "requests.json",
            opportunity_set_path=SCENARIO_DIRECTORY / "opportunities.json",
        ),
        catalog=catalog,
        request_set=requests,
        opportunity_set=opportunities,
    )


def generate() -> None:
    source_catalog = json.loads((PROJECT_ROOT / "data" / "scenarios" / "example" / "system.json").read_text(encoding="utf-8"))
    source_catalog["catalog_id"] = "CATALOG-POLAND-DEMO"
    source_catalog["name"] = "Polska — katalog demonstracyjny SAR i EO"
    source_catalog["version"] = "1.0.0"
    source_catalog["notes"] = (
        "Katalog demonstracyjny z czterema slotami SAR i dwoma EO. "
        "Ograniczenia zasobowe są jawnie modelowe."
    )
    catalog = SystemCatalog.model_validate(source_catalog)
    request_set = build_request_set()
    opportunity_set = build_opportunity_set(catalog, request_set)
    snapshot = build_snapshot()
    access_result = build_access_result(snapshot, request_set)

    _write_json(SCENARIO_DIRECTORY / "system.json", catalog.model_dump(mode="json"))
    _write_json(SCENARIO_DIRECTORY / "requests.json", request_set.model_dump(mode="json"))
    _write_json(SCENARIO_DIRECTORY / "opportunities.json", opportunity_set.model_dump(mode="json"))

    scenario = _scenario(catalog, request_set, opportunity_set)
    planning_service = PlanningService()
    greedy = planning_service.run(
        scenario=scenario,
        options=PlanningOptions(algorithm="GREEDY", use_dynamic_transition_model=True),
        schedule_id="SCHEDULE-POLAND-DEMO-GREEDY",
        schedule_name="Polska demo — Greedy",
        created_at_utc=START_UTC,
    )
    cp_sat = planning_service.run(
        scenario=scenario,
        options=PlanningOptions(
            algorithm="CP_SAT",
            use_dynamic_transition_model=True,
            cp_sat_time_limit_s=2.0,
            cp_sat_num_search_workers=1,
            cp_sat_random_seed=RANDOM_SEED,
            cp_sat_force_mandatory_requests=False,
        ),
        schedule_id="SCHEDULE-POLAND-DEMO-CP-SAT",
        schedule_name="Polska demo — CP-SAT",
        created_at_utc=START_UTC,
    )

    _write_json(EXAMPLE_DIRECTORY / "system.json", catalog.model_dump(mode="json"))
    _write_json(EXAMPLE_DIRECTORY / "requests.json", request_set.model_dump(mode="json"))
    _write_json(EXAMPLE_DIRECTORY / "opportunities.json", opportunity_set.model_dump(mode="json"))
    _write_json(EXAMPLE_DIRECTORY / "aoi.geojson", _aoi_geojson(request_set))
    _write_json(EXAMPLE_DIRECTORY / "orbits_omm.json", encode_orbit_snapshot(snapshot))
    _write_json(EXAMPLE_DIRECTORY / "access_windows.json", encode_access_result(access_result))
    _write_json(EXAMPLE_DIRECTORY / "schedule_greedy.json", greedy.schedule.model_dump(mode="json"))
    _write_json(EXAMPLE_DIRECTORY / "schedule_cp_sat.json", cp_sat.schedule.model_dump(mode="json"))
    _write_json(
        EXAMPLE_DIRECTORY / "benchmark_result.json",
        {
            "scenario_id": "POLAND_DEMO",
            "request_count": 50,
            "opportunity_count": 500,
            "greedy": {
                "solver_status": greedy.solver_status,
                "objective_value": greedy.objective_value,
                "fully_satisfied_requests": greedy.fully_satisfied_requests,
                "total_acquisitions": greedy.total_acquisitions,
                "runtime_s": None,
            },
            "cp_sat": {
                "solver_status": cp_sat.solver_status,
                "objective_value": cp_sat.objective_value,
                "fully_satisfied_requests": cp_sat.fully_satisfied_requests,
                "total_acquisitions": cp_sat.total_acquisitions,
                "runtime_s": None,
                "time_limit_s": 2.0,
            },
            "runtime_note": (
                "Czas wykonania zależy od środowiska i nie jest utrwalany "
                "w deterministycznym artefakcie referencyjnym."
            ),
        },
    )
    _write_json(
        EXAMPLE_DIRECTORY / "stk_validation.json",
        {
            "status": "DEMO_REFERENCE",
            "scenario_id": "POLAND_DEMO",
            "reference_request_id": access_result.request_id,
            "public_access_window_count": len(access_result.windows),
            "time_tolerance_s": 180,
            "position_tolerance_km": 25,
            "notes": [
                "Plik jest gotowym przykładem struktury walidacji STK.",
                "Nie stanowi niezależnego potwierdzenia operatora satelitarnego.",
            ],
        },
    )
    report_html = f"""<!doctype html>
<html lang=\"pl\"><head><meta charset=\"utf-8\"><title>SatPlan Poland Demo</title></head>
<body><h1>Satellite Acquisition Planner — Poland Demo</h1>
<p>Horyzont: {START_UTC.isoformat()} – {END_UTC.isoformat()}</p>
<ul><li>6 satelitów</li><li>50 zleceń</li><li>500 okazji</li>
<li>{len(access_result.windows)} referencyjne okna dostępu</li>
<li>Greedy: {greedy.fully_satisfied_requests} zrealizowanych zleceń</li>
<li>CP-SAT: {cp_sat.fully_satisfied_requests} zrealizowanych zleceń</li></ul>
<p>Raport demonstracyjny. Dane operatorów i pogoda nie są pobierane online.</p></body></html>\n"""
    (EXAMPLE_DIRECTORY / "demo_report.html").write_text(report_html, encoding="utf-8", newline="\n")
    readme = """# Poland demo

Kompletny, deterministyczny scenariusz offline do prezentacji SatPlan.

- horyzont: 48 h,
- 6 satelitów: 4 SAR i 2 EO,
- 50 zleceń: 20 SAR, 20 EO, 5 DUAL_OPTIONAL, 5 DUAL_REQUIRED,
- 500 okazji o różnych długościach okien,
- wbudowany snapshot OMM i referencyjne okna dostępu,
- harmonogramy Greedy i CP-SAT,
- przykładowy benchmark, walidacja STK i raport HTML.

Pliki mają charakter demonstracyjny i nie potwierdzają komercyjnej dostępności taskingu.
"""
    (EXAMPLE_DIRECTORY / "README.md").write_text(readme, encoding="utf-8", newline="\n")

    print(
        f"Wygenerowano POLAND_DEMO: {len(request_set.requests)} zleceń, "
        f"{len(opportunity_set.opportunities)} okazji, "
        f"{len(access_result.windows)} okna dostępu."
    )


if __name__ == "__main__":
    generate()
