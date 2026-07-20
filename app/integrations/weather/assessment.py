from __future__ import annotations

from bisect import bisect_left
from datetime import datetime, timedelta, timezone
from math import ceil
from statistics import mean

from app.integrations.access import GeometricAccessWindow
from app.integrations.weather.client import OpenMeteoClient
from app.integrations.weather.models import (
    CloudAggregation,
    CloudPointValue,
    HourlyCloudSample,
    WeatherPointForecast,
    WindowCloudAssessment,
)
from app.integrations.weather.sampling import build_weather_sampling_locations
from app.models.enums import SensorType
from app.models.request import ObservationRequest


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Czas musi zawierać strefę czasową")
    return value.astimezone(timezone.utc)


def _interpolate_component(
    left: HourlyCloudSample,
    right: HourlyCloudSample,
    timestamp: datetime,
    attribute: str,
) -> float:
    if left.timestamp_utc == right.timestamp_utc:
        return float(getattr(left, attribute))
    elapsed = (timestamp - left.timestamp_utc).total_seconds()
    total = (right.timestamp_utc - left.timestamp_utc).total_seconds()
    fraction = min(1.0, max(0.0, elapsed / total))
    return float(getattr(left, attribute)) + fraction * (
        float(getattr(right, attribute)) - float(getattr(left, attribute))
    )


def interpolate_forecast(
    forecast: WeatherPointForecast,
    timestamp_utc: datetime,
) -> CloudPointValue:
    """Interpoluje liniowo prognozę godzinową do czasu akwizycji."""

    timestamp = _as_utc(timestamp_utc)
    samples = forecast.samples
    times = [sample.timestamp_utc for sample in samples]
    position = bisect_left(times, timestamp)
    if position <= 0:
        left = right = samples[0]
    elif position >= len(samples):
        left = right = samples[-1]
    else:
        left = samples[position - 1]
        right = samples[position]

    return CloudPointValue(
        location=forecast.location,
        cloud_cover_percent=_interpolate_component(
            left, right, timestamp, "cloud_cover_percent"
        ),
        cloud_cover_low_percent=_interpolate_component(
            left, right, timestamp, "cloud_cover_low_percent"
        ),
        cloud_cover_mid_percent=_interpolate_component(
            left, right, timestamp, "cloud_cover_mid_percent"
        ),
        cloud_cover_high_percent=_interpolate_component(
            left, right, timestamp, "cloud_cover_high_percent"
        ),
    )


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("Nie można agregować pustej listy")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = percentile * (len(ordered) - 1)
    lower = int(rank)
    upper = ceil(rank)
    if lower == upper:
        return ordered[lower]
    fraction = rank - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def _aggregate(values: list[float], aggregation: CloudAggregation) -> float:
    if aggregation == CloudAggregation.MAXIMUM:
        return max(values)
    if aggregation == CloudAggregation.PERCENTILE_75:
        return _percentile(values, 0.75)
    return mean(values)


class CloudAssessmentService:
    """Przypisuje prognozę zachmurzenia do okien optycznych."""

    def __init__(self, *, client: OpenMeteoClient) -> None:
        self.client = client

    def assess_windows(
        self,
        *,
        request: ObservationRequest,
        windows: tuple[GeometricAccessWindow, ...],
        aggregation: CloudAggregation = CloudAggregation.MAXIMUM,
        maximum_sampling_points: int = 9,
        allow_network: bool = True,
    ) -> tuple[WindowCloudAssessment, ...]:
        optical_windows = tuple(
            window for window in windows if window.sensor_type == SensorType.OPTICAL
        )
        if not optical_windows:
            return ()
        if request.max_cloud_cover is None:
            raise ValueError("Zlecenie EO wymaga max_cloud_cover")

        locations = build_weather_sampling_locations(
            request.geometry,
            maximum_points=maximum_sampling_points,
        )
        earliest = min(window.peak_utc for window in optical_windows) - timedelta(hours=1)
        latest = max(window.peak_utc for window in optical_windows) + timedelta(hours=1)
        forecast_result = self.client.fetch_cloud_forecast(
            locations,
            start_utc=earliest,
            end_utc=latest,
            allow_network=allow_network,
        )

        assessments: list[WindowCloudAssessment] = []
        max_allowed_percent = request.max_cloud_cover * 100.0
        for window in optical_windows:
            point_values = tuple(
                interpolate_forecast(forecast, window.peak_utc)
                for forecast in forecast_result.forecasts
            )
            total = _aggregate(
                [value.cloud_cover_percent for value in point_values],
                aggregation,
            )
            assessments.append(
                WindowCloudAssessment(
                    window_id=window.window_id,
                    assessed_at_utc=window.peak_utc,
                    aggregation=aggregation,
                    cloud_cover_percent=total,
                    cloud_cover_low_percent=_aggregate(
                        [value.cloud_cover_low_percent for value in point_values],
                        aggregation,
                    ),
                    cloud_cover_mid_percent=_aggregate(
                        [value.cloud_cover_mid_percent for value in point_values],
                        aggregation,
                    ),
                    cloud_cover_high_percent=_aggregate(
                        [value.cloud_cover_high_percent for value in point_values],
                        aggregation,
                    ),
                    point_values=point_values,
                    max_allowed_cloud_cover_percent=max_allowed_percent,
                    is_cloud_feasible=total <= max_allowed_percent,
                    source_url=forecast_result.request_url,
                    from_cache=forecast_result.from_cache,
                    is_stale=forecast_result.is_stale,
                    warning=forecast_result.warning,
                )
            )
        return tuple(assessments)
