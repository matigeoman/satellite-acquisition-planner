from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from app.analysis.algorithm_benchmark import (
    AlgorithmBenchmarkConfig,
    AlgorithmBenchmarkResult,
    BenchmarkPairRecord,
    BenchmarkRunRecord,
    BenchmarkSummaryRecord,
)
from app.analysis.schedule import analyze_schedule
from app.geospatial.aoi import (
    target_geometry_from_geojson,
    target_geometry_to_feature,
)
from app.integrations.access import (
    AccessCalculationResult,
    AccessPathPoint,
    GeometricAccessWindow,
)
from app.integrations.opportunities import (
    OpportunityWeatherChange,
    PublicOpportunityBuildResult,
)
from app.integrations.orbits import (
    CelestrakQueryResult,
    PublicOrbitRecord,
    SatelliteFamily,
    TrackedSatellite,
)
from app.integrations.weather import (
    CloudAggregation,
    CloudPointValue,
    WeatherLocation,
    WindowCloudAssessment,
)
from app.models.catalog import SystemCatalog
from app.models.downlink_set import DownlinkOpportunitySet
from app.models.enums import ObservationSide, ScheduleEntryStatus, SensorType
from app.models.opportunity import AcquisitionOpportunity
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request import ObservationRequest
from app.models.request_set import ObservationRequestSet
from app.models.schedule import Schedule
from app.planning.fixed import FixedOpportunityAssignment
from app.services.contracts import (
    PlanningOptions,
    PlanningResult,
    PublicReplanningResult,
    ReplanningResult,
)
from app.services.orbit_service import PublicConstellationSnapshot
from app.services.scenario_service import LoadedScenario, ScenarioDefinition


def parse_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Czas w archiwum musi zawierać strefę czasową")
    return parsed.astimezone(timezone.utc)


def jsonable(value: Any) -> Any:
    """Konwertuje modele, dataclasses, enumy i daty na JSON."""

    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(item) for item in value]
    return value


def encode_orbit_snapshot(snapshot: PublicConstellationSnapshot) -> dict[str, Any]:
    return {
        "generated_at_utc": snapshot.generated_at_utc.isoformat(),
        "satellites": [
            {
                "slot_id": item.slot_id,
                "family": item.family.value,
                "raw_omm": dict(item.record.raw_omm),
            }
            for item in snapshot.satellites
        ],
        "queries": [
            {
                "query_name": query.query_name,
                "fetched_at_utc": query.fetched_at_utc.isoformat(),
                "request_url": query.request_url,
                "from_cache": query.from_cache,
                "is_stale": query.is_stale,
                "warning": query.warning,
                "records": [dict(record.raw_omm) for record in query.records],
            }
            for query in snapshot.queries
        ],
        "warnings": list(snapshot.warnings),
    }


def decode_orbit_snapshot(payload: Mapping[str, Any]) -> PublicConstellationSnapshot:
    queries = tuple(
        CelestrakQueryResult(
            query_name=str(item["query_name"]),
            records=tuple(
                PublicOrbitRecord.from_omm(record)
                for record in item.get("records", ())
            ),
            fetched_at_utc=parse_utc(item["fetched_at_utc"]),
            request_url=str(item.get("request_url", "")),
            from_cache=bool(item.get("from_cache", False)),
            is_stale=bool(item.get("is_stale", False)),
            warning=(
                str(item["warning"])
                if item.get("warning") is not None
                else None
            ),
        )
        for item in payload.get("queries", ())
    )
    satellites = tuple(
        TrackedSatellite(
            slot_id=str(item["slot_id"]),
            family=SatelliteFamily(str(item["family"])),
            record=PublicOrbitRecord.from_omm(item["raw_omm"]),
        )
        for item in payload.get("satellites", ())
    )
    if not satellites:
        raise ValueError("Snapshot orbitalny nie zawiera satelitów")
    return PublicConstellationSnapshot(
        generated_at_utc=parse_utc(payload["generated_at_utc"]),
        satellites=satellites,
        queries=queries,
        warnings=tuple(str(item) for item in payload.get("warnings", ())),
    )


def encode_access_result(result: AccessCalculationResult) -> dict[str, Any]:
    return result.to_dict()


def _decode_access_point(payload: Mapping[str, Any]) -> AccessPathPoint:
    return AccessPathPoint(
        timestamp_utc=parse_utc(payload["timestamp_utc"]),
        satellite_latitude_deg=float(payload["satellite_latitude_deg"]),
        satellite_longitude_deg=float(payload["satellite_longitude_deg"]),
        satellite_altitude_km=float(payload["satellite_altitude_km"]),
        off_nadir_angle_deg=float(payload["off_nadir_angle_deg"]),
        incidence_angle_deg=float(payload["incidence_angle_deg"]),
        sun_elevation_deg=(
            float(payload["sun_elevation_deg"])
            if payload.get("sun_elevation_deg") is not None
            else None
        ),
    )


def _decode_access_window(payload: Mapping[str, Any]) -> GeometricAccessWindow:
    return GeometricAccessWindow(
        window_id=str(payload["window_id"]),
        request_id=str(payload["request_id"]),
        satellite_id=str(payload["satellite_id"]),
        satellite_name=str(payload["satellite_name"]),
        norad_cat_id=int(payload["norad_cat_id"]),
        family=SatelliteFamily(str(payload["family"])),
        sensor_type=SensorType(str(payload["sensor_type"])),
        mode_id=str(payload["mode_id"]),
        mode_name=str(payload["mode_name"]),
        start_utc=parse_utc(payload["start_utc"]),
        end_utc=parse_utc(payload["end_utc"]),
        peak_utc=parse_utc(payload["peak_utc"]),
        observation_side=ObservationSide(str(payload["observation_side"])),
        duration_s=float(payload["duration_s"]),
        coverage_ratio=float(payload["coverage_ratio"]),
        minimum_off_nadir_deg=float(payload["minimum_off_nadir_deg"]),
        maximum_off_nadir_deg=float(payload["maximum_off_nadir_deg"]),
        minimum_incidence_angle_deg=float(
            payload["minimum_incidence_angle_deg"]
        ),
        maximum_incidence_angle_deg=float(
            payload["maximum_incidence_angle_deg"]
        ),
        peak_sun_elevation_deg=(
            float(payload["peak_sun_elevation_deg"])
            if payload.get("peak_sun_elevation_deg") is not None
            else None
        ),
        orbit_epoch_utc=parse_utc(payload["orbit_epoch_utc"]),
        sample_count=int(payload["sample_count"]),
        path=tuple(
            _decode_access_point(item) for item in payload.get("path", ())
        ),
        notes=tuple(str(item) for item in payload.get("notes", ())),
    )


def decode_access_result(payload: Mapping[str, Any]) -> AccessCalculationResult:
    return AccessCalculationResult(
        request_id=str(payload["request_id"]),
        request_name=str(payload["request_name"]),
        generated_at_utc=parse_utc(payload["generated_at_utc"]),
        calculation_start_utc=parse_utc(payload["calculation_start_utc"]),
        calculation_end_utc=parse_utc(payload["calculation_end_utc"]),
        propagation_step_s=float(payload["propagation_step_s"]),
        evaluated_satellites=int(payload["evaluated_satellites"]),
        evaluated_modes=int(payload["evaluated_modes"]),
        windows=tuple(
            _decode_access_window(item) for item in payload.get("windows", ())
        ),
        warnings=tuple(str(item) for item in payload.get("warnings", ())),
    )


def _decode_weather_location(payload: Mapping[str, Any]) -> WeatherLocation:
    return WeatherLocation(
        location_id=str(payload["location_id"]),
        longitude_deg=float(payload["longitude_deg"]),
        latitude_deg=float(payload["latitude_deg"]),
    )


def _decode_cloud_point(payload: Mapping[str, Any]) -> CloudPointValue:
    return CloudPointValue(
        location=_decode_weather_location(payload["location"]),
        cloud_cover_percent=float(payload["cloud_cover_percent"]),
        cloud_cover_low_percent=float(payload["cloud_cover_low_percent"]),
        cloud_cover_mid_percent=float(payload["cloud_cover_mid_percent"]),
        cloud_cover_high_percent=float(payload["cloud_cover_high_percent"]),
    )


def decode_cloud_assessment(payload: Mapping[str, Any]) -> WindowCloudAssessment:
    return WindowCloudAssessment(
        window_id=str(payload["window_id"]),
        assessed_at_utc=parse_utc(payload["assessed_at_utc"]),
        aggregation=CloudAggregation(str(payload["aggregation"])),
        cloud_cover_percent=float(payload["cloud_cover_percent"]),
        cloud_cover_low_percent=float(payload["cloud_cover_low_percent"]),
        cloud_cover_mid_percent=float(payload["cloud_cover_mid_percent"]),
        cloud_cover_high_percent=float(payload["cloud_cover_high_percent"]),
        point_values=tuple(
            _decode_cloud_point(item)
            for item in payload.get("point_values", ())
        ),
        max_allowed_cloud_cover_percent=float(
            payload["max_allowed_cloud_cover_percent"]
        ),
        is_cloud_feasible=bool(payload["is_cloud_feasible"]),
        source_url=str(payload["source_url"]),
        from_cache=bool(payload["from_cache"]),
        is_stale=bool(payload["is_stale"]),
        warning=(
            str(payload["warning"])
            if payload.get("warning") is not None
            else None
        ),
    )


def encode_opportunity_builds(
    builds: Mapping[str, PublicOpportunityBuildResult],
) -> dict[str, Any]:
    return {
        request_id: build.to_dict()
        for request_id, build in sorted(builds.items())
    }


def decode_opportunity_builds(
    payload: Mapping[str, Any],
) -> dict[str, PublicOpportunityBuildResult]:
    result: dict[str, PublicOpportunityBuildResult] = {}
    for request_id, item in payload.items():
        build = PublicOpportunityBuildResult(
            request_id=str(item["request_id"]),
            generated_at_utc=parse_utc(item["generated_at_utc"]),
            opportunities=tuple(
                AcquisitionOpportunity.model_validate(opportunity)
                for opportunity in item.get("opportunities", ())
            ),
            weather_assessments=tuple(
                decode_cloud_assessment(assessment)
                for assessment in item.get("weather_assessments", ())
            ),
            skipped_window_ids=tuple(
                str(value) for value in item.get("skipped_window_ids", ())
            ),
            warnings=tuple(str(value) for value in item.get("warnings", ())),
        )
        if build.request_id != request_id:
            raise ValueError(
                "Klucz opportunity_builds jest niezgodny z request_id"
            )
        result[request_id] = build
    return result


def encode_scenario(scenario: LoadedScenario) -> dict[str, Any]:
    payload = {
        "definition": {
            "scenario_id": scenario.definition.scenario_id,
            "name": scenario.definition.name,
            "description": scenario.definition.description,
        },
        "catalog": scenario.catalog.model_dump(mode="json"),
        "request_set": scenario.request_set.model_dump(mode="json"),
        "opportunity_set": scenario.opportunity_set.model_dump(mode="json"),
    }
    if scenario.downlink_set is not None:
        payload["downlink_set"] = scenario.downlink_set.model_dump(mode="json")
    return payload


def decode_scenario(payload: Mapping[str, Any]) -> LoadedScenario:
    definition_payload = payload.get("definition", {})
    catalog = SystemCatalog.model_validate(payload["catalog"])
    request_set = ObservationRequestSet.model_validate(payload["request_set"])
    opportunity_set = AcquisitionOpportunitySet.model_validate(
        payload["opportunity_set"]
    )
    opportunity_set.validate_against(catalog, request_set)
    downlink_payload = payload.get("downlink_set")
    downlink_set = (
        DownlinkOpportunitySet.model_validate(downlink_payload)
        if downlink_payload is not None
        else None
    )
    if downlink_set is not None:
        downlink_set.validate_against(catalog)
        if (
            downlink_set.horizon_start_utc != request_set.horizon_start_utc
            or downlink_set.horizon_end_utc != request_set.horizon_end_utc
        ):
            raise ValueError(
                "Horyzont downlinków w archiwum jest niezgodny ze scenariuszem"
            )
    definition = ScenarioDefinition(
        scenario_id=str(definition_payload.get("scenario_id", "PUBLIC")),
        name=str(definition_payload.get("name", "Projekt zaimportowany")),
        description=str(
            definition_payload.get(
                "description",
                "Scenariusz odtworzony z archiwum projektu.",
            )
        ),
        catalog_path=Path("archive/system.json"),
        request_set_path=Path("archive/requests.json"),
        opportunity_set_path=Path("archive/opportunities.json"),
        downlink_set_path=(
            Path("archive/downlinks.json")
            if downlink_set is not None
            else None
        ),
    )
    return LoadedScenario(
        definition=definition,
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        downlink_set=downlink_set,
    )


def encode_planning_options(options: PlanningOptions) -> dict[str, Any]:
    return jsonable(asdict(options))


def decode_planning_options(payload: Mapping[str, Any]) -> PlanningOptions:
    return PlanningOptions(**dict(payload))


def encode_planning_result(result: PlanningResult) -> dict[str, Any]:
    return {
        "scenario": encode_scenario(result.scenario),
        "options": encode_planning_options(result.options),
        "schedule": result.schedule.model_dump(mode="json"),
        "solver_status": result.solver_status,
        "started_at_utc": result.started_at_utc.isoformat(),
        "completed_at_utc": result.completed_at_utc.isoformat(),
        "wall_clock_runtime_s": result.wall_clock_runtime_s,
        "analysis_summary": jsonable(result.analysis),
    }


def decode_planning_result(payload: Mapping[str, Any]) -> PlanningResult:
    scenario = decode_scenario(payload["scenario"])
    schedule = Schedule.model_validate(payload["schedule"])
    analysis = analyze_schedule(
        catalog=scenario.catalog,
        request_set=scenario.request_set,
        opportunity_set=scenario.opportunity_set,
        schedule=schedule,
    )
    return PlanningResult(
        scenario=scenario,
        options=decode_planning_options(payload["options"]),
        schedule=schedule,
        analysis=analysis,
        solver_status=str(payload["solver_status"]),
        started_at_utc=parse_utc(payload["started_at_utc"]),
        completed_at_utc=parse_utc(payload["completed_at_utc"]),
        wall_clock_runtime_s=float(payload["wall_clock_runtime_s"]),
    )


def encode_public_replanning_result(
    result: PublicReplanningResult,
) -> dict[str, Any]:
    replanning = result.replanning_result
    return {
        "planning_result": encode_planning_result(result.planning_result),
        "previous_schedule": replanning.previous_schedule.model_dump(mode="json"),
        "replan_at_utc": replanning.replan_at_utc.isoformat(),
        "frozen_until_utc": replanning.frozen_until_utc.isoformat(),
        "fixed_assignments": jsonable(replanning.fixed_assignments),
        "refreshed_builds_by_request_id": encode_opportunity_builds(
            result.refreshed_builds_by_request_id
        ),
        "weather_changes": jsonable(result.weather_changes),
        "refreshed_at_utc": result.refreshed_at_utc.isoformat(),
        "warnings": list(result.warnings),
    }


def decode_public_replanning_result(
    payload: Mapping[str, Any],
) -> PublicReplanningResult:
    planning_result = decode_planning_result(payload["planning_result"])
    fixed_assignments = tuple(
        FixedOpportunityAssignment(
            opportunity_id=str(item["opportunity_id"]),
            status=ScheduleEntryStatus(str(item["status"])),
            lock_reason=(
                str(item["lock_reason"])
                if item.get("lock_reason") is not None
                else None
            ),
        )
        for item in payload.get("fixed_assignments", ())
    )
    replanning = ReplanningResult(
        previous_schedule=Schedule.model_validate(payload["previous_schedule"]),
        planning_result=planning_result,
        replan_at_utc=parse_utc(payload["replan_at_utc"]),
        frozen_until_utc=parse_utc(payload["frozen_until_utc"]),
        fixed_assignments=fixed_assignments,
    )
    changes = tuple(
        OpportunityWeatherChange(
            opportunity_id=str(item["opportunity_id"]),
            request_id=str(item["request_id"]),
            satellite_id=str(item["satellite_id"]),
            start_utc=parse_utc(item["start_utc"]),
            previous_cloud_cover=float(item["previous_cloud_cover"]),
            refreshed_cloud_cover=float(item["refreshed_cloud_cover"]),
            previous_is_feasible=bool(item["previous_is_feasible"]),
            refreshed_is_feasible=bool(item["refreshed_is_feasible"]),
            preserved_by_freeze=bool(item["preserved_by_freeze"]),
        )
        for item in payload.get("weather_changes", ())
    )
    return PublicReplanningResult(
        replanning_result=replanning,
        refreshed_builds_by_request_id=decode_opportunity_builds(
            payload.get("refreshed_builds_by_request_id", {})
        ),
        weather_changes=changes,
        refreshed_at_utc=parse_utc(payload["refreshed_at_utc"]),
        warnings=tuple(str(item) for item in payload.get("warnings", ())),
    )


def encode_benchmark_result(result: AlgorithmBenchmarkResult) -> dict[str, Any]:
    return jsonable(result)


def decode_benchmark_result(payload: Mapping[str, Any]) -> AlgorithmBenchmarkResult:
    return AlgorithmBenchmarkResult(
        base_scenario_id=str(payload["base_scenario_id"]),
        config=AlgorithmBenchmarkConfig(**dict(payload["config"])),
        run_records=tuple(
            BenchmarkRunRecord(**dict(item))
            for item in payload.get("run_records", ())
        ),
        pair_records=tuple(
            BenchmarkPairRecord(**dict(item))
            for item in payload.get("pair_records", ())
        ),
        summary_records=tuple(
            BenchmarkSummaryRecord(**dict(item))
            for item in payload.get("summary_records", ())
        ),
        started_at_utc=parse_utc(payload["started_at_utc"]),
        completed_at_utc=parse_utc(payload["completed_at_utc"]),
        wall_clock_runtime_s=float(payload["wall_clock_runtime_s"]),
    )


def encode_aoi(geometry: Any) -> dict[str, Any]:
    return target_geometry_to_feature(geometry)


def decode_aoi(payload: Mapping[str, Any]) -> Any:
    return target_geometry_from_geojson(payload)


def encode_requests(requests: list[ObservationRequest]) -> list[dict[str, Any]]:
    return [request.model_dump(mode="json") for request in requests]


def decode_requests(payload: list[Mapping[str, Any]]) -> list[ObservationRequest]:
    requests = [ObservationRequest.model_validate(item) for item in payload]
    identifiers = [request.request_id for request in requests]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Archiwum zawiera zduplikowane request_id")
    return requests


__all__ = [
    "decode_access_result",
    "decode_aoi",
    "decode_benchmark_result",
    "decode_cloud_assessment",
    "decode_opportunity_builds",
    "decode_orbit_snapshot",
    "decode_planning_result",
    "decode_public_replanning_result",
    "decode_requests",
    "encode_access_result",
    "encode_aoi",
    "encode_benchmark_result",
    "encode_opportunity_builds",
    "encode_orbit_snapshot",
    "encode_planning_result",
    "encode_public_replanning_result",
    "encode_requests",
    "jsonable",
    "parse_utc",
]
