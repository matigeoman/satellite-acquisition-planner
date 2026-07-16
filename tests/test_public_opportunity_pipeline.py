from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.integrations.access import (
    AccessCalculationResult,
    AccessPathPoint,
    GeometricAccessWindow,
)
from app.integrations.opportunities import build_public_opportunities
from app.integrations.orbits import SatelliteFamily
from app.integrations.weather import (
    CloudAggregation,
    CloudPointValue,
    WeatherLocation,
    WindowCloudAssessment,
)
from app.models.enums import (
    ObservationSide,
    OpportunitySourceType,
    PlanningAlgorithm,
    RequestMode,
    SensorType,
)
from app.models.geometry import PointGeometry
from app.models.request import ObservationRequest
from app.services.contracts.planning import PlanningOptions
from app.services.planning_service import PlanningService
from app.services.public_scenario_service import PublicScenarioService


def _request(sensor_type: SensorType, start: datetime) -> ObservationRequest:
    return ObservationRequest(
        request_id=f"REQ-PUBLIC-{sensor_type.value}",
        name=f"Public {sensor_type.value}",
        geometry=PointGeometry(coordinates=(21.0, 52.0)),
        priority=9,
        earliest_start_utc=start,
        latest_end_utc=start + timedelta(minutes=5),
        request_mode=RequestMode.SINGLE,
        requested_sensor_types=[sensor_type],
        max_resolution_m=1.0,
        minimum_coverage_ratio=1.0,
        max_cloud_cover=0.2 if sensor_type == SensorType.OPTICAL else None,
        max_incidence_angle_deg=40.0 if sensor_type == SensorType.SAR else None,
        max_off_nadir_deg=45.0,
    )


def _window(sensor_type: SensorType, start: datetime) -> GeometricAccessWindow:
    if sensor_type == SensorType.SAR:
        window_id = "ACCESS-PUBLIC-SAR-SAR-01-SAR-ICEYE-SPOT-001"
        satellite_id = "SAR-01"
        family = SatelliteFamily.ICEYE
        mode_id = "MODE-SAR-ICEYE-SPOT"
        mode_name = "ICEYE Spot"
        side = ObservationSide.RIGHT
        incidence = 30.0
        sun = None
        name = "ICEYE-X99"
        norad = 65001
    else:
        window_id = "ACCESS-PUBLIC-OPTICAL-EO-01-OPT-PLEIADES-NEO-PAN-001"
        satellite_id = "EO-01"
        family = SatelliteFamily.PLEIADES_NEO
        mode_id = "MODE-OPT-PLEIADES-NEO-PAN"
        mode_name = "Pléiades Neo Panchromatic"
        side = ObservationSide.NADIR
        incidence = 10.0
        sun = 40.0
        name = "PLEIADES NEO 3"
        norad = 49001
    peak = start + timedelta(minutes=1)
    point = AccessPathPoint(
        timestamp_utc=peak,
        satellite_latitude_deg=50.0,
        satellite_longitude_deg=20.0,
        satellite_altitude_km=620.0,
        off_nadir_angle_deg=10.0 if sensor_type == SensorType.OPTICAL else 25.0,
        incidence_angle_deg=incidence,
        sun_elevation_deg=sun,
    )
    return GeometricAccessWindow(
        window_id=window_id,
        request_id=f"REQ-PUBLIC-{sensor_type.value}",
        satellite_id=satellite_id,
        satellite_name=name,
        norad_cat_id=norad,
        family=family,
        sensor_type=sensor_type,
        mode_id=mode_id,
        mode_name=mode_name,
        start_utc=peak - timedelta(seconds=40),
        end_utc=peak + timedelta(seconds=40),
        peak_utc=peak,
        observation_side=side,
        duration_s=80.0,
        coverage_ratio=1.0,
        minimum_off_nadir_deg=point.off_nadir_angle_deg,
        maximum_off_nadir_deg=point.off_nadir_angle_deg,
        minimum_incidence_angle_deg=incidence,
        maximum_incidence_angle_deg=incidence,
        peak_sun_elevation_deg=sun,
        orbit_epoch_utc=start - timedelta(hours=1),
        sample_count=1,
        path=(point,),
    )


def _access_result(
    sensor_type: SensorType,
    start: datetime,
) -> AccessCalculationResult:
    window = _window(sensor_type, start)
    return AccessCalculationResult(
        request_id=window.request_id,
        request_name="Public test",
        generated_at_utc=start,
        calculation_start_utc=start,
        calculation_end_utc=start + timedelta(minutes=5),
        propagation_step_s=30.0,
        evaluated_satellites=1,
        evaluated_modes=1,
        windows=(window,),
        warnings=(),
    )


def _assessment(window_id: str, percent: float) -> WindowCloudAssessment:
    location = WeatherLocation("AOI", 21.0, 52.0)
    return WindowCloudAssessment(
        window_id=window_id,
        assessed_at_utc=datetime(2026, 7, 16, 12, 1, tzinfo=timezone.utc),
        aggregation=CloudAggregation.MAXIMUM,
        cloud_cover_percent=percent,
        cloud_cover_low_percent=percent / 2.0,
        cloud_cover_mid_percent=percent / 3.0,
        cloud_cover_high_percent=percent / 4.0,
        point_values=(
            CloudPointValue(
                location=location,
                cloud_cover_percent=percent,
                cloud_cover_low_percent=percent / 2.0,
                cloud_cover_mid_percent=percent / 3.0,
                cloud_cover_high_percent=percent / 4.0,
            ),
        ),
        max_allowed_cloud_cover_percent=20.0,
        is_cloud_feasible=percent <= 20.0,
        source_url="https://api.open-meteo.com/v1/forecast?test=1",
        from_cache=False,
        is_stale=False,
    )


def test_sar_window_becomes_feasible_public_opportunity() -> None:
    start = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)
    request = _request(SensorType.SAR, start)
    result = build_public_opportunities(
        request=request,
        access_result=_access_result(SensorType.SAR, start),
    )
    opportunity = result.opportunities[0]
    assert opportunity.is_feasible
    assert opportunity.incidence_angle_deg == 30.0
    assert opportunity.cloud_cover is None
    assert opportunity.source_type == OpportunitySourceType.PUBLIC_DATA


def test_optical_cloud_limit_marks_opportunity_infeasible() -> None:
    start = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)
    request = _request(SensorType.OPTICAL, start)
    access = _access_result(SensorType.OPTICAL, start)
    result = build_public_opportunities(
        request=request,
        access_result=access,
        weather_assessments=(_assessment(access.windows[0].window_id, 40.0),),
    )
    opportunity = result.opportunities[0]
    assert not opportunity.is_feasible
    assert opportunity.cloud_cover == 0.4
    assert opportunity.infeasibility_reasons


def test_optical_clear_window_is_available_for_planning() -> None:
    start = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)
    request = _request(SensorType.OPTICAL, start)
    access = _access_result(SensorType.OPTICAL, start)
    result = build_public_opportunities(
        request=request,
        access_result=access,
        weather_assessments=(_assessment(access.windows[0].window_id, 10.0),),
    )
    opportunity = result.opportunities[0]
    assert opportunity.is_available_for_planning
    assert opportunity.quality_score > 0.0
    assert opportunity.sensor_id == "SENSOR-EO-PLEIADES-NEO-PUBLIC"


def test_public_scenario_runs_greedy_and_cp_sat() -> None:
    start = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)
    request = _request(SensorType.SAR, start)
    build = build_public_opportunities(
        request=request,
        access_result=_access_result(SensorType.SAR, start),
    )
    scenario = PublicScenarioService().build(
        requests=[request],
        builds_by_request_id={request.request_id: build},
    )
    greedy = PlanningService().run(
        scenario=scenario,
        options=PlanningOptions(algorithm=PlanningAlgorithm.GREEDY),
    )
    cp_sat = PlanningService().run(
        scenario=scenario,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.CP_SAT,
            cp_sat_time_limit_s=1.0,
        ),
    )
    assert greedy.total_acquisitions == 1
    assert cp_sat.total_acquisitions == 1
