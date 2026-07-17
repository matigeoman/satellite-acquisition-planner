from __future__ import annotations

from math import atan2, cos, degrees, radians, sin, sqrt
from statistics import mean, median

from app.geospatial.aoi import geometry_centroid
from app.integrations.access.geometry import geodetic_to_ecef
from app.integrations.access.models import GeometricAccessWindow
from app.integrations.stk_validation.models import (
    AccessValidationResult,
    AerValidationResult,
    ErrorStatistics,
    MatchedAccessInterval,
    MatchedAerSample,
    StkAccessInterval,
    StkAerSample,
)
from app.models.geometry import TargetGeometry


def _statistics(values: list[float]) -> ErrorStatistics:
    if not values:
        return ErrorStatistics(
            count=0,
            mean_error=0.0,
            mean_absolute_error=0.0,
            root_mean_square_error=0.0,
            median_absolute_error=0.0,
            maximum_absolute_error=0.0,
        )
    absolute = [abs(value) for value in values]
    return ErrorStatistics(
        count=len(values),
        mean_error=mean(values),
        mean_absolute_error=mean(absolute),
        root_mean_square_error=sqrt(mean(value * value for value in values)),
        median_absolute_error=median(absolute),
        maximum_absolute_error=max(absolute),
    )


def compare_access_intervals(
    model_windows: tuple[GeometricAccessWindow, ...] | list[GeometricAccessWindow],
    stk_intervals: tuple[StkAccessInterval, ...] | list[StkAccessInterval],
    *,
    tolerance_s: float = 300.0,
) -> AccessValidationResult:
    """Dopasowuje okna jeden-do-jednego i liczy błędy granic przedziałów."""

    if tolerance_s < 0:
        raise ValueError("tolerance_s nie może być ujemne")
    model = sorted(model_windows, key=lambda window: window.start_utc)
    stk = sorted(stk_intervals, key=lambda interval: interval.start_utc)

    candidates: list[tuple[float, int, int, float]] = []
    for model_index, window in enumerate(model):
        for stk_index, interval in enumerate(stk):
            start_error = (window.start_utc - interval.start_utc).total_seconds()
            end_error = (window.end_utc - interval.end_utc).total_seconds()
            overlap = max(
                0.0,
                (
                    min(window.end_utc, interval.end_utc)
                    - max(window.start_utc, interval.start_utc)
                ).total_seconds(),
            )
            close_enough = (
                overlap > 0.0
                or abs(start_error) <= tolerance_s
                or abs(end_error) <= tolerance_s
            )
            if not close_enough:
                continue
            duration_error = window.duration_s - interval.duration_s
            cost = (
                abs(start_error)
                + abs(end_error)
                + 0.25 * abs(duration_error)
                - 0.1 * overlap
            )
            candidates.append((cost, model_index, stk_index, overlap))

    used_model: set[int] = set()
    used_stk: set[int] = set()
    matched: list[MatchedAccessInterval] = []
    for _, model_index, stk_index, overlap in sorted(candidates):
        if model_index in used_model or stk_index in used_stk:
            continue
        window = model[model_index]
        interval = stk[stk_index]
        start_error = (window.start_utc - interval.start_utc).total_seconds()
        end_error = (window.end_utc - interval.end_utc).total_seconds()
        duration_error = window.duration_s - interval.duration_s
        overlap_ratio = overlap / max(window.duration_s, interval.duration_s, 1e-9)
        matched.append(
            MatchedAccessInterval(
                model_window_id=window.window_id,
                stk_interval_id=interval.interval_id,
                model_start_utc=window.start_utc,
                stk_start_utc=interval.start_utc,
                model_end_utc=window.end_utc,
                stk_end_utc=interval.end_utc,
                model_duration_s=window.duration_s,
                stk_duration_s=interval.duration_s,
                start_error_s=start_error,
                end_error_s=end_error,
                duration_error_s=duration_error,
                overlap_s=overlap,
                overlap_ratio=overlap_ratio,
            )
        )
        used_model.add(model_index)
        used_stk.add(stk_index)

    matched.sort(key=lambda item: item.model_start_utc)
    start_errors = [item.start_error_s for item in matched]
    end_errors = [item.end_error_s for item in matched]
    duration_errors = [item.duration_error_s for item in matched]
    return AccessValidationResult(
        matched=tuple(matched),
        unmatched_model_window_ids=tuple(
            window.window_id
            for index, window in enumerate(model)
            if index not in used_model
        ),
        unmatched_stk_interval_ids=tuple(
            interval.interval_id
            for index, interval in enumerate(stk)
            if index not in used_stk
        ),
        start_error_statistics_s=_statistics(start_errors),
        end_error_statistics_s=_statistics(end_errors),
        duration_error_statistics_s=_statistics(duration_errors),
        mean_overlap_ratio=(
            mean(item.overlap_ratio for item in matched) if matched else 0.0
        ),
        tolerance_s=tolerance_s,
    )


def _model_aer(
    *,
    satellite_latitude_deg: float,
    satellite_longitude_deg: float,
    satellite_altitude_km: float,
    target_latitude_deg: float,
    target_longitude_deg: float,
) -> tuple[float, float, float]:
    satellite = geodetic_to_ecef(
        satellite_latitude_deg,
        satellite_longitude_deg,
        satellite_altitude_km,
    )
    target = geodetic_to_ecef(target_latitude_deg, target_longitude_deg, 0.0)
    dx, dy, dz = tuple(
        satellite_component - target_component
        for satellite_component, target_component in zip(satellite, target)
    )
    latitude = radians(target_latitude_deg)
    longitude = radians(target_longitude_deg)
    east = -sin(longitude) * dx + cos(longitude) * dy
    north = (
        -sin(latitude) * cos(longitude) * dx
        - sin(latitude) * sin(longitude) * dy
        + cos(latitude) * dz
    )
    up = (
        cos(latitude) * cos(longitude) * dx
        + cos(latitude) * sin(longitude) * dy
        + sin(latitude) * dz
    )
    range_km = sqrt(east * east + north * north + up * up)
    azimuth = degrees(atan2(east, north)) % 360.0
    elevation = degrees(atan2(up, sqrt(east * east + north * north)))
    return azimuth, elevation, range_km


def _circular_error_deg(model_value: float, reference_value: float) -> float:
    return (model_value - reference_value + 180.0) % 360.0 - 180.0


def compare_aer_samples(
    model_windows: tuple[GeometricAccessWindow, ...] | list[GeometricAccessWindow],
    stk_samples: tuple[StkAerSample, ...] | list[StkAerSample],
    *,
    geometry: TargetGeometry,
    time_tolerance_s: float = 30.0,
) -> AerValidationResult:
    """Porównuje raport AER z najbliższymi próbkami śladu modelu."""

    if time_tolerance_s < 0:
        raise ValueError("time_tolerance_s nie może być ujemne")
    longitude, latitude = geometry_centroid(geometry)
    model_points = sorted(
        {
            point.timestamp_utc: point
            for window in model_windows
            for point in window.path
        }.values(),
        key=lambda point: point.timestamp_utc,
    )

    matched: list[MatchedAerSample] = []
    unmatched = 0
    for sample in stk_samples:
        if not model_points:
            unmatched += 1
            continue
        point = min(
            model_points,
            key=lambda candidate: abs(
                (candidate.timestamp_utc - sample.timestamp_utc).total_seconds()
            ),
        )
        offset = (point.timestamp_utc - sample.timestamp_utc).total_seconds()
        if abs(offset) > time_tolerance_s:
            unmatched += 1
            continue
        azimuth, elevation, range_km = _model_aer(
            satellite_latitude_deg=point.satellite_latitude_deg,
            satellite_longitude_deg=point.satellite_longitude_deg,
            satellite_altitude_km=point.satellite_altitude_km,
            target_latitude_deg=latitude,
            target_longitude_deg=longitude,
        )
        matched.append(
            MatchedAerSample(
                timestamp_utc=sample.timestamp_utc,
                model_timestamp_utc=point.timestamp_utc,
                time_offset_s=offset,
                model_azimuth_deg=azimuth,
                stk_azimuth_deg=sample.azimuth_deg,
                azimuth_error_deg=_circular_error_deg(
                    azimuth, sample.azimuth_deg
                ),
                model_elevation_deg=elevation,
                stk_elevation_deg=sample.elevation_deg,
                elevation_error_deg=elevation - sample.elevation_deg,
                model_range_km=range_km,
                stk_range_km=sample.range_km,
                range_error_km=range_km - sample.range_km,
            )
        )

    return AerValidationResult(
        matched=tuple(matched),
        unmatched_stk_sample_count=unmatched,
        azimuth_error_statistics_deg=_statistics(
            [item.azimuth_error_deg for item in matched]
        ),
        elevation_error_statistics_deg=_statistics(
            [item.elevation_error_deg for item in matched]
        ),
        range_error_statistics_km=_statistics(
            [item.range_error_km for item in matched]
        ),
        time_tolerance_s=time_tolerance_s,
    )
