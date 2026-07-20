from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.integrations.access import (
    AccessCalculationResult,
    AccessPathPoint,
    GeometricAccessWindow,
)
from app.integrations.opportunities import (
    PublicOpportunityWeatherRefreshService,
    build_public_opportunities,
)
from app.integrations.orbits import SatelliteFamily
from app.integrations.weather import (
    CloudAggregation,
    CloudAssessmentService,
    CloudPointValue,
    HourlyCloudSample,
    WeatherForecastResult,
    WeatherLocation,
    WeatherPointForecast,
    WindowCloudAssessment,
)
from app.models.enums import (
    ObservationSide,
    PlanningAlgorithm,
    RequestMode,
    SensorType,
)
from app.models.geometry import PointGeometry
from app.models.request import ObservationRequest
from app.services.contracts.planning import PlanningOptions
from app.services.planning_service import PlanningService
from app.services.public_replanning_service import PublicReplanningService
from app.services.public_scenario_service import PublicScenarioService
from app.services.replanning_service import ReplanningService


START = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)


class _CloudyClient:
    def fetch_cloud_forecast(
        self,
        locations,
        *,
        start_utc,
        end_utc,
        allow_network=True,
    ) -> WeatherForecastResult:
        samples = tuple(
            HourlyCloudSample(
                timestamp_utc=start_utc + timedelta(hours=index),
                cloud_cover_percent=80.0,
                cloud_cover_low_percent=60.0,
                cloud_cover_mid_percent=30.0,
                cloud_cover_high_percent=10.0,
            )
            for index in range(
                int((end_utc - start_utc).total_seconds() // 3600) + 2
            )
        )
        forecasts = tuple(
            WeatherPointForecast(
                location=location,
                latitude_deg=location.latitude_deg,
                longitude_deg=location.longitude_deg,
                elevation_m=100.0,
                timezone_name="UTC",
                samples=samples,
            )
            for location in locations
        )
        return WeatherForecastResult(
            forecasts=forecasts,
            fetched_at_utc=START,
            request_url="https://api.open-meteo.com/v1/forecast?test=cloudy",
            from_cache=not allow_network,
            is_stale=False,
        )


def _request(request_id: str, longitude: float) -> ObservationRequest:
    return ObservationRequest(
        request_id=request_id,
        name=request_id,
        geometry=PointGeometry(coordinates=(longitude, 52.0)),
        priority=8,
        earliest_start_utc=START,
        latest_end_utc=START + timedelta(hours=5),
        request_mode=RequestMode.SINGLE,
        requested_sensor_types=[SensorType.OPTICAL],
        max_resolution_m=0.3,
        minimum_coverage_ratio=1.0,
        max_cloud_cover=0.2,
        max_off_nadir_deg=45.0,
    )


def _access_result(
    request: ObservationRequest,
    *,
    satellite_id: str,
    peak_utc: datetime,
) -> AccessCalculationResult:
    point = AccessPathPoint(
        timestamp_utc=peak_utc,
        satellite_latitude_deg=50.0,
        satellite_longitude_deg=20.0,
        satellite_altitude_km=620.0,
        off_nadir_angle_deg=10.0,
        incidence_angle_deg=12.0,
        sun_elevation_deg=40.0,
    )
    window_id = (
        f"ACCESS-{request.request_id.removeprefix('REQ-')}-{satellite_id}-"
        "OPT-PLEIADES-NEO-PAN-001"
    )
    window = GeometricAccessWindow(
        window_id=window_id,
        request_id=request.request_id,
        satellite_id=satellite_id,
        satellite_name="PLEIADES NEO TEST",
        norad_cat_id=49001,
        family=SatelliteFamily.PLEIADES_NEO,
        sensor_type=SensorType.OPTICAL,
        mode_id="MODE-OPT-PLEIADES-NEO-PAN",
        mode_name="Pléiades Neo Panchromatic",
        start_utc=peak_utc - timedelta(seconds=40),
        end_utc=peak_utc + timedelta(seconds=40),
        peak_utc=peak_utc,
        observation_side=ObservationSide.NADIR,
        duration_s=80.0,
        coverage_ratio=1.0,
        minimum_off_nadir_deg=10.0,
        maximum_off_nadir_deg=10.0,
        minimum_incidence_angle_deg=12.0,
        maximum_incidence_angle_deg=12.0,
        peak_sun_elevation_deg=40.0,
        orbit_epoch_utc=START - timedelta(hours=1),
        sample_count=1,
        path=(point,),
    )
    return AccessCalculationResult(
        request_id=request.request_id,
        request_name=request.name,
        generated_at_utc=START,
        calculation_start_utc=START,
        calculation_end_utc=START + timedelta(hours=5),
        propagation_step_s=30.0,
        evaluated_satellites=1,
        evaluated_modes=1,
        windows=(window,),
        warnings=(),
    )


def _clear_assessment(window_id: str, request: ObservationRequest):
    location = request.geometry
    point = CloudPointValue(
        location=WeatherLocation(
            location_id=request.request_id,
            longitude_deg=location.coordinates[0],
            latitude_deg=location.coordinates[1],
        ),
        cloud_cover_percent=5.0,
        cloud_cover_low_percent=2.0,
        cloud_cover_mid_percent=2.0,
        cloud_cover_high_percent=1.0,
    )
    return WindowCloudAssessment(
        window_id=window_id,
        assessed_at_utc=START,
        aggregation=CloudAggregation.MAXIMUM,
        cloud_cover_percent=5.0,
        cloud_cover_low_percent=2.0,
        cloud_cover_mid_percent=2.0,
        cloud_cover_high_percent=1.0,
        point_values=(point,),
        max_allowed_cloud_cover_percent=20.0,
        is_cloud_feasible=True,
        source_url="https://api.open-meteo.com/v1/forecast?test=clear",
        from_cache=False,
        is_stale=False,
    )


def _build(request, access):
    return build_public_opportunities(
        request=request,
        access_result=access,
        weather_assessments=(
            _clear_assessment(access.windows[0].window_id, request),
        ),
    )


def test_weather_refresh_preserves_frozen_and_updates_future() -> None:
    request = _request("REQ-PUBLIC-REFRESH", 21.0)
    frozen_access = _access_result(
        request,
        satellite_id="EO-01",
        peak_utc=START + timedelta(minutes=30),
    )
    future_access = _access_result(
        request,
        satellite_id="EO-02",
        peak_utc=START + timedelta(hours=3),
    )
    combined = AccessCalculationResult(
        request_id=request.request_id,
        request_name=request.name,
        generated_at_utc=START,
        calculation_start_utc=START,
        calculation_end_utc=START + timedelta(hours=5),
        propagation_step_s=30.0,
        evaluated_satellites=2,
        evaluated_modes=1,
        windows=(frozen_access.windows[0], future_access.windows[0]),
        warnings=(),
    )
    build = build_public_opportunities(
        request=request,
        access_result=combined,
        weather_assessments=(
            _clear_assessment(frozen_access.windows[0].window_id, request),
            _clear_assessment(future_access.windows[0].window_id, request),
        ),
    )
    service = PublicOpportunityWeatherRefreshService(
        cloud_service=CloudAssessmentService(client=_CloudyClient())
    )
    result = service.refresh_build(
        request=request,
        build_result=build,
        frozen_until_utc=START + timedelta(hours=1),
    )

    by_satellite = {
        opportunity.satellite_id: opportunity
        for opportunity in result.build_result.opportunities
    }
    assert by_satellite["EO-01"].cloud_cover == 0.05
    assert by_satellite["EO-01"].is_feasible
    assert by_satellite["EO-02"].cloud_cover == 0.8
    assert not by_satellite["EO-02"].is_feasible
    assert result.refreshed_opportunity_count == 1
    assert result.became_infeasible_count == 1


def test_public_replanning_removes_cloudy_future_acquisition() -> None:
    frozen_request = _request("REQ-PUBLIC-FROZEN", 21.0)
    future_request = _request("REQ-PUBLIC-FUTURE", 22.0)
    frozen_access = _access_result(
        frozen_request,
        satellite_id="EO-01",
        peak_utc=START + timedelta(minutes=30),
    )
    future_access = _access_result(
        future_request,
        satellite_id="EO-02",
        peak_utc=START + timedelta(hours=3),
    )
    builds = {
        frozen_request.request_id: _build(frozen_request, frozen_access),
        future_request.request_id: _build(future_request, future_access),
    }
    scenario_service = PublicScenarioService()
    scenario = scenario_service.build(
        requests=[frozen_request, future_request],
        builds_by_request_id=builds,
    )
    planning_service = PlanningService()
    previous = planning_service.run(
        scenario=scenario,
        options=PlanningOptions(algorithm=PlanningAlgorithm.GREEDY),
    )
    assert previous.total_acquisitions == 2

    service = PublicReplanningService(
        scenario_service=scenario_service,
        replanning_service=ReplanningService(
            planning_service=planning_service
        ),
        weather_refresh_service=PublicOpportunityWeatherRefreshService(
            cloud_service=CloudAssessmentService(client=_CloudyClient())
        ),
    )
    result = service.run(
        requests=[frozen_request, future_request],
        builds_by_request_id=builds,
        previous_planning_result=previous,
        options=PlanningOptions(algorithm=PlanningAlgorithm.GREEDY),
        replan_at_utc=START + timedelta(minutes=10),
        freeze_duration=timedelta(hours=1),
    )

    assert result.replanning_result.fixed_count == 1
    assert result.became_infeasible_count == 1
    assert result.schedule.total_acquisitions == 1
    assert len(result.replanning_result.removed_opportunity_ids) == 1
