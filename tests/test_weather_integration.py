from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.integrations.access import AccessPathPoint, GeometricAccessWindow
from app.integrations.orbits import SatelliteFamily
from app.integrations.weather import (
    CloudAggregation,
    CloudAssessmentService,
    HourlyCloudSample,
    OpenMeteoClient,
    WeatherLocation,
    WeatherPointForecast,
    build_weather_sampling_locations,
    interpolate_forecast,
)
from app.models.enums import ObservationSide, RequestMode, SensorType
from app.models.geometry import PointGeometry, PolygonGeometry
from app.models.request import ObservationRequest


def _point_request(start: datetime) -> ObservationRequest:
    return ObservationRequest(
        request_id="REQ-WEATHER-POINT",
        name="Weather point",
        geometry=PointGeometry(coordinates=(21.0, 52.0)),
        priority=8,
        earliest_start_utc=start,
        latest_end_utc=start + timedelta(hours=2),
        request_mode=RequestMode.SINGLE,
        requested_sensor_types=[SensorType.OPTICAL],
        max_resolution_m=0.3,
        minimum_coverage_ratio=1.0,
        max_cloud_cover=0.2,
        max_off_nadir_deg=45.0,
    )


def _optical_window(start: datetime) -> GeometricAccessWindow:
    peak = start + timedelta(minutes=30)
    point = AccessPathPoint(
        timestamp_utc=peak,
        satellite_latitude_deg=50.0,
        satellite_longitude_deg=20.0,
        satellite_altitude_km=620.0,
        off_nadir_angle_deg=10.0,
        incidence_angle_deg=12.0,
        sun_elevation_deg=35.0,
    )
    return GeometricAccessWindow(
        window_id="ACCESS-WEATHER-POINT-EO-01-OPT-PAN-001",
        request_id="REQ-WEATHER-POINT",
        satellite_id="EO-01",
        satellite_name="PLEIADES NEO 3",
        norad_cat_id=49001,
        family=SatelliteFamily.PLEIADES_NEO,
        sensor_type=SensorType.OPTICAL,
        mode_id="MODE-OPT-PLEIADES-NEO-PAN",
        mode_name="Pléiades Neo Panchromatic",
        start_utc=peak - timedelta(seconds=30),
        end_utc=peak + timedelta(seconds=30),
        peak_utc=peak,
        observation_side=ObservationSide.NADIR,
        duration_s=60.0,
        coverage_ratio=1.0,
        minimum_off_nadir_deg=9.0,
        maximum_off_nadir_deg=11.0,
        minimum_incidence_angle_deg=11.0,
        maximum_incidence_angle_deg=13.0,
        peak_sun_elevation_deg=35.0,
        orbit_epoch_utc=start - timedelta(hours=1),
        sample_count=1,
        path=(point,),
    )


def _response_payload(
    *,
    latitude: float,
    longitude: float,
    values: tuple[float, float],
) -> dict[str, object]:
    return {
        "latitude": latitude,
        "longitude": longitude,
        "elevation": 100.0,
        "timezone": "GMT",
        "hourly": {
            "time": ["2026-07-16T12:00", "2026-07-16T13:00"],
            "cloud_cover": list(values),
            "cloud_cover_low": [10.0, 20.0],
            "cloud_cover_mid": [5.0, 15.0],
            "cloud_cover_high": [2.0, 8.0],
        },
    }


def test_point_sampling_uses_single_location() -> None:
    locations = build_weather_sampling_locations(
        PointGeometry(coordinates=(21.0, 52.0))
    )
    assert len(locations) == 1
    assert locations[0].location_id == "AOI-POINT"


def test_polygon_sampling_is_bounded_and_inside_extent() -> None:
    polygon = PolygonGeometry(
        coordinates=[
            [
                (20.0, 51.0),
                (22.0, 51.0),
                (22.0, 53.0),
                (20.0, 53.0),
                (20.0, 51.0),
            ]
        ]
    )
    locations = build_weather_sampling_locations(
        polygon,
        maximum_points=7,
    )
    assert 1 <= len(locations) <= 7
    assert all(20.0 <= item.longitude_deg <= 22.0 for item in locations)
    assert all(51.0 <= item.latitude_deg <= 53.0 for item in locations)


def test_open_meteo_client_parses_and_reuses_cache(tmp_path: Path) -> None:
    calls: list[str] = []

    def transport(url: str, _timeout: float) -> bytes:
        calls.append(url)
        return json.dumps(
            _response_payload(
                latitude=52.0,
                longitude=21.0,
                values=(10.0, 30.0),
            )
        ).encode()

    now = datetime(2026, 7, 16, 11, tzinfo=timezone.utc)
    client = OpenMeteoClient(
        cache_directory=tmp_path,
        transport=transport,
        now_provider=lambda: now,
    )
    location = WeatherLocation("AOI", 21.0, 52.0)
    first = client.fetch_cloud_forecast(
        (location,),
        start_utc=now,
        end_utc=now + timedelta(hours=2),
    )
    second = client.fetch_cloud_forecast(
        (location,),
        start_utc=now,
        end_utc=now + timedelta(hours=2),
    )

    assert len(calls) == 1
    assert not first.from_cache
    assert second.from_cache
    assert first.forecasts[0].samples[1].cloud_cover_percent == 30.0
    assert "cloud_cover_low" in first.request_url


def test_open_meteo_offline_uses_existing_cache(tmp_path: Path) -> None:
    now = datetime(2026, 7, 16, 11, tzinfo=timezone.utc)
    location = WeatherLocation("AOI", 21.0, 52.0)
    client = OpenMeteoClient(
        cache_directory=tmp_path,
        transport=lambda _url, _timeout: json.dumps(
            _response_payload(
                latitude=52.0,
                longitude=21.0,
                values=(10.0, 20.0),
            )
        ).encode(),
        now_provider=lambda: now,
    )
    client.fetch_cloud_forecast(
        (location,),
        start_utc=now,
        end_utc=now + timedelta(hours=2),
    )
    result = client.fetch_cloud_forecast(
        (location,),
        start_utc=now,
        end_utc=now + timedelta(hours=2),
        allow_network=False,
    )
    assert result.from_cache
    assert not result.is_stale


def test_interpolation_uses_time_between_hourly_samples() -> None:
    start = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)
    forecast = WeatherPointForecast(
        location=WeatherLocation("AOI", 21.0, 52.0),
        latitude_deg=52.0,
        longitude_deg=21.0,
        elevation_m=100.0,
        timezone_name="UTC",
        samples=(
            HourlyCloudSample(start, 10.0, 0.0, 0.0, 0.0),
            HourlyCloudSample(
                start + timedelta(hours=1),
                30.0,
                20.0,
                10.0,
                5.0,
            ),
        ),
    )
    value = interpolate_forecast(
        forecast,
        start + timedelta(minutes=30),
    )
    assert value.cloud_cover_percent == pytest.approx(20.0)
    assert value.cloud_cover_low_percent == pytest.approx(10.0)


def test_cloud_assessment_rejects_window_above_limit(tmp_path: Path) -> None:
    start = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)
    payload = _response_payload(
        latitude=52.0,
        longitude=21.0,
        values=(30.0, 50.0),
    )
    client = OpenMeteoClient(
        cache_directory=tmp_path,
        transport=lambda _url, _timeout: json.dumps(payload).encode(),
        now_provider=lambda: start,
    )
    assessment = CloudAssessmentService(client=client).assess_windows(
        request=_point_request(start),
        windows=(_optical_window(start),),
        aggregation=CloudAggregation.MAXIMUM,
    )[0]
    assert assessment.cloud_cover_percent == pytest.approx(40.0)
    assert not assessment.is_cloud_feasible
    assert assessment.max_allowed_cloud_cover_percent == 20.0
