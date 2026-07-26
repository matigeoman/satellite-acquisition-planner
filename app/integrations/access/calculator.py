from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.catalogs import PublicMissionProfile
from app.geospatial.aoi import geometry_centroid
from app.integrations.access.geometry import (
    approximate_coverage_ratio,
    geodetic_to_ecef,
    observation_side,
    solar_elevation_deg,
    target_look_angles,
)
from app.integrations.access.models import (
    AccessCalculationResult,
    AccessPathPoint,
    GeometricAccessWindow,
)
from app.integrations.orbits import (
    PropagatedState,
    SatelliteFamily,
    SatelliteGroundTrack,
    Sgp4OrbitPropagator,
)
from app.models.enums import (
    LookSideCapability,
    ObservationSide,
    SensorType,
)
from app.models.imaging import ImagingMode
from app.models.request import ObservationRequest


@dataclass(frozen=True, slots=True)
class _EvaluatedSample:
    path_point: AccessPathPoint
    observation_side: ObservationSide
    is_valid: bool


@dataclass(frozen=True, slots=True)
class _EvaluationContext:
    request: ObservationRequest
    profile: PublicMissionProfile
    mode: ImagingMode
    coverage_ratio: float
    target_longitude_deg: float
    target_latitude_deg: float
    target_ecef: tuple[float, float, float]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Czas musi zawierać strefę czasową")
    return value.astimezone(timezone.utc)


def _sensor_type_for_family(family: SatelliteFamily) -> SensorType:
    if family == SatelliteFamily.ICEYE:
        return SensorType.SAR
    return SensorType.OPTICAL


def _profile_for_family(
    family: SatelliteFamily,
    *,
    iceye_profile: PublicMissionProfile,
    pleiades_profile: PublicMissionProfile,
) -> PublicMissionProfile:
    if family == SatelliteFamily.ICEYE:
        return iceye_profile
    return pleiades_profile


def _side_allowed(
    capability: LookSideCapability,
    side: ObservationSide,
) -> bool:
    if capability == LookSideCapability.BOTH:
        return True
    if capability == LookSideCapability.NADIR_ONLY:
        return side == ObservationSide.NADIR
    if capability == LookSideCapability.LEFT:
        return side in {ObservationSide.LEFT, ObservationSide.NADIR}
    return side in {ObservationSide.RIGHT, ObservationSide.NADIR}


def _sample_is_valid(
    *,
    request: ObservationRequest,
    profile: PublicMissionProfile,
    mode: ImagingMode,
    side: ObservationSide,
    off_nadir_deg: float,
    incidence_deg: float,
    sun_elevation: float | None,
    coverage_ratio: float,
) -> bool:
    if mode.nominal_resolution_m > request.resolution_limit_for(mode.sensor_type):
        return False
    if coverage_ratio < request.minimum_coverage_ratio:
        return False
    if off_nadir_deg > mode.max_off_nadir_deg:
        return False
    if (
        request.max_off_nadir_deg is not None
        and off_nadir_deg > request.max_off_nadir_deg
    ):
        return False
    if incidence_deg >= 90.0:
        return False
    if not _side_allowed(profile.sensor.look_side_capability, side):
        return False

    if mode.sensor_type == SensorType.SAR:
        if (
            mode.min_incidence_angle_deg is not None
            and incidence_deg < mode.min_incidence_angle_deg
        ):
            return False
        if (
            mode.max_incidence_angle_deg is not None
            and incidence_deg > mode.max_incidence_angle_deg
        ):
            return False
        if (
            request.max_incidence_angle_deg is not None
            and incidence_deg > request.max_incidence_angle_deg
        ):
            return False
        return True

    minimum_sun = profile.sensor.minimum_sun_elevation_deg
    return (
        sun_elevation is not None
        and minimum_sun is not None
        and sun_elevation >= minimum_sun
    )


def _evaluate_state(
    *,
    state: PropagatedState,
    previous_state: PropagatedState,
    next_state: PropagatedState,
    context: _EvaluationContext,
) -> _EvaluatedSample:
    previous_ecef = geodetic_to_ecef(
        previous_state.latitude_deg,
        previous_state.longitude_deg,
        previous_state.altitude_km,
    )
    satellite_ecef = geodetic_to_ecef(
        state.latitude_deg,
        state.longitude_deg,
        state.altitude_km,
    )
    next_ecef = geodetic_to_ecef(
        next_state.latitude_deg,
        next_state.longitude_deg,
        next_state.altitude_km,
    )
    side = ObservationSide(
        observation_side(
            previous_satellite_ecef=previous_ecef,
            satellite_ecef=satellite_ecef,
            next_satellite_ecef=next_ecef,
            target_ecef=context.target_ecef,
        )
    )
    off_nadir, incidence = target_look_angles(
        satellite_latitude_deg=state.latitude_deg,
        satellite_longitude_deg=state.longitude_deg,
        satellite_altitude_km=state.altitude_km,
        target_latitude_deg=context.target_latitude_deg,
        target_longitude_deg=context.target_longitude_deg,
    )
    sun_elevation = None
    if context.mode.sensor_type == SensorType.OPTICAL:
        sun_elevation = solar_elevation_deg(
            timestamp_utc=state.timestamp_utc,
            latitude_deg=context.target_latitude_deg,
            longitude_deg=context.target_longitude_deg,
        )
    path_point = AccessPathPoint(
        timestamp_utc=state.timestamp_utc,
        satellite_latitude_deg=state.latitude_deg,
        satellite_longitude_deg=state.longitude_deg,
        satellite_altitude_km=state.altitude_km,
        off_nadir_angle_deg=off_nadir,
        incidence_angle_deg=incidence,
        sun_elevation_deg=sun_elevation,
    )
    return _EvaluatedSample(
        path_point=path_point,
        observation_side=side,
        is_valid=_sample_is_valid(
            request=context.request,
            profile=context.profile,
            mode=context.mode,
            side=side,
            off_nadir_deg=off_nadir,
            incidence_deg=incidence,
            sun_elevation=sun_elevation,
            coverage_ratio=context.coverage_ratio,
        ),
    )


def _peak_sample(
    samples: list[_EvaluatedSample],
    mode: ImagingMode,
) -> _EvaluatedSample:
    if mode.sensor_type == SensorType.SAR:
        minimum = mode.min_incidence_angle_deg or 0.0
        maximum = mode.max_incidence_angle_deg or minimum
        target_incidence = (minimum + maximum) / 2.0
        return min(
            samples,
            key=lambda sample: (
                abs(sample.path_point.incidence_angle_deg - target_incidence),
                sample.path_point.off_nadir_angle_deg,
            ),
        )

    return min(
        samples,
        key=lambda sample: (
            sample.path_point.off_nadir_angle_deg,
            -(sample.path_point.sun_elevation_deg or -90.0),
        ),
    )


def _window_notes(
    *,
    request: ObservationRequest,
    mode: ImagingMode,
    refined_boundaries: bool,
    boundary_tolerance_s: float,
) -> tuple[str, ...]:
    notes = [
        "Okno wyznaczono z publicznych GP/OMM i propagacji SGP4.",
    ]
    if refined_boundaries:
        notes.append(
            "Granice okna doprecyzowano bisekcją SGP4 do tolerancji "
            f"{boundary_tolerance_s:.3f} s."
        )
    else:
        notes.append(
            "Granice okna oszacowano w połowie pomiędzy sąsiednimi próbkami."
        )
    if request.geometry.type == "Polygon":
        notes.append(
            "Pokrycie poligonu obliczono z pola przecięcia AOI i wycentrowanego "
            "prostokątnego footprintu w lokalnym odwzorowaniu WGS84."
        )
    if mode.sensor_type == SensorType.OPTICAL:
        notes.append(
            "Okno geometryczne uwzględnia elewację Słońca. Prognoza "
            "zachmurzenia jest przypisywana podczas budowy okazji EO."
        )
    return tuple(notes)


def _midpoint(first: datetime, second: datetime) -> datetime:
    return first + (second - first) / 2


def _valid_ranges(evaluated: list[_EvaluatedSample]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start_index: int | None = None
    for index, sample in enumerate(evaluated):
        if sample.is_valid and start_index is None:
            start_index = index
        elif not sample.is_valid and start_index is not None:
            ranges.append((start_index, index - 1))
            start_index = None
    if start_index is not None:
        ranges.append((start_index, len(evaluated) - 1))
    return ranges


def _refine_boundary(
    *,
    invalid_time: datetime,
    valid_time: datetime,
    tolerance_s: float,
    evaluate_at: Callable[[datetime], _EvaluatedSample],
) -> datetime:
    left = min(invalid_time, valid_time)
    right = max(invalid_time, valid_time)
    left_valid = evaluate_at(left).is_valid
    right_valid = evaluate_at(right).is_valid
    if left_valid == right_valid:
        return _midpoint(left, right)

    while (right - left).total_seconds() > tolerance_s:
        middle = _midpoint(left, right)
        middle_valid = evaluate_at(middle).is_valid
        if middle_valid == left_valid:
            left = middle
        else:
            right = middle

    return _midpoint(left, right)


def _build_windows(
    *,
    request: ObservationRequest,
    track: SatelliteGroundTrack,
    profile: PublicMissionProfile,
    mode: ImagingMode,
    calculation_start: datetime,
    calculation_end: datetime,
    step: timedelta,
    coverage_ratio: float,
    propagator: Sgp4OrbitPropagator | None,
    boundary_tolerance_s: float,
) -> list[GeometricAccessWindow]:
    if not track.states:
        return []

    margin = step
    states = [
        state
        for state in track.states
        if calculation_start - margin
        <= state.timestamp_utc
        <= calculation_end + margin
    ]
    if not states:
        return []

    target_longitude, target_latitude = geometry_centroid(request.geometry)
    context = _EvaluationContext(
        request=request,
        profile=profile,
        mode=mode,
        coverage_ratio=coverage_ratio,
        target_longitude_deg=target_longitude,
        target_latitude_deg=target_latitude,
        target_ecef=geodetic_to_ecef(target_latitude, target_longitude),
    )

    evaluated: list[_EvaluatedSample] = []
    for index, state in enumerate(states):
        previous_state = states[max(0, index - 1)]
        next_state = states[min(len(states) - 1, index + 1)]
        evaluated.append(
            _evaluate_state(
                state=state,
                previous_state=previous_state,
                next_state=next_state,
                context=context,
            )
        )

    satrec = None
    if propagator is not None:
        satrec = propagator.build_satrec(track.satellite.record)

    evaluation_cache: dict[datetime, _EvaluatedSample] = {}

    def evaluate_at(timestamp: datetime) -> _EvaluatedSample:
        cached = evaluation_cache.get(timestamp)
        if cached is not None:
            return cached
        if propagator is None or satrec is None:
            raise RuntimeError("Brak propagatora do doprecyzowania granicy")
        probe = timedelta(seconds=max(1.0, boundary_tolerance_s))
        previous_state = propagator.propagate_satrec(
            satellite=satrec,
            record=track.satellite.record,
            timestamp_utc=timestamp - probe,
        )
        state = propagator.propagate_satrec(
            satellite=satrec,
            record=track.satellite.record,
            timestamp_utc=timestamp,
        )
        next_state = propagator.propagate_satrec(
            satellite=satrec,
            record=track.satellite.record,
            timestamp_utc=timestamp + probe,
        )
        result = _evaluate_state(
            state=state,
            previous_state=previous_state,
            next_state=next_state,
            context=context,
        )
        evaluation_cache[timestamp] = result
        return result

    windows: list[GeometricAccessWindow] = []
    for group_index, (start_index, end_index) in enumerate(
        _valid_ranges(evaluated),
        start=1,
    ):
        group = evaluated[start_index : end_index + 1]
        first_time = group[0].path_point.timestamp_utc
        last_time = group[-1].path_point.timestamp_utc

        if start_index > 0:
            previous_time = evaluated[start_index - 1].path_point.timestamp_utc
            if propagator is None:
                start = _midpoint(previous_time, first_time)
            else:
                start = _refine_boundary(
                    invalid_time=previous_time,
                    valid_time=first_time,
                    tolerance_s=boundary_tolerance_s,
                    evaluate_at=evaluate_at,
                )
        else:
            start = first_time

        if end_index + 1 < len(evaluated):
            next_time = evaluated[end_index + 1].path_point.timestamp_utc
            if propagator is None:
                end = _midpoint(last_time, next_time)
            else:
                end = _refine_boundary(
                    invalid_time=next_time,
                    valid_time=last_time,
                    tolerance_s=boundary_tolerance_s,
                    evaluate_at=evaluate_at,
                )
        else:
            end = last_time

        start = max(calculation_start, start)
        end = min(calculation_end, end)
        duration_s = (end - start).total_seconds()
        if duration_s < mode.min_acquisition_duration_s:
            continue

        peak = _peak_sample(group, mode)
        refined_boundaries = propagator is not None and (
            start_index > 0 or end_index + 1 < len(evaluated)
        )
        notes = _window_notes(
            request=request,
            mode=mode,
            refined_boundaries=refined_boundaries,
            boundary_tolerance_s=boundary_tolerance_s,
        )
        off_nadir_values = [
            sample.path_point.off_nadir_angle_deg for sample in group
        ]
        incidence_values = [
            sample.path_point.incidence_angle_deg for sample in group
        ]
        windows.append(
            GeometricAccessWindow(
                window_id=(
                    f"ACCESS-{request.request_id.removeprefix('REQ-')}-"
                    f"{track.satellite.slot_id}-{mode.mode_id.removeprefix('MODE-')}-"
                    f"{group_index:03d}"
                ),
                request_id=request.request_id,
                satellite_id=track.satellite.slot_id,
                satellite_name=track.satellite.record.object_name,
                norad_cat_id=track.satellite.record.norad_cat_id,
                family=track.satellite.family,
                sensor_type=mode.sensor_type,
                mode_id=mode.mode_id,
                mode_name=mode.name,
                start_utc=start,
                end_utc=end,
                peak_utc=peak.path_point.timestamp_utc,
                observation_side=peak.observation_side,
                duration_s=duration_s,
                coverage_ratio=coverage_ratio,
                minimum_off_nadir_deg=min(off_nadir_values),
                maximum_off_nadir_deg=max(off_nadir_values),
                minimum_incidence_angle_deg=min(incidence_values),
                maximum_incidence_angle_deg=max(incidence_values),
                peak_sun_elevation_deg=peak.path_point.sun_elevation_deg,
                orbit_epoch_utc=track.satellite.record.epoch_utc,
                sample_count=len(group),
                path=tuple(sample.path_point for sample in group),
                notes=notes,
            )
        )
    return windows


class GeometricAccessCalculator:
    """Wyznacza publiczne okna dostępu dla Point/Polygon w WGS84."""

    def __init__(
        self,
        *,
        propagator: Sgp4OrbitPropagator | None = None,
        boundary_tolerance_s: float = 1.0,
    ) -> None:
        if boundary_tolerance_s <= 0.0:
            raise ValueError("boundary_tolerance_s musi być dodatnie")
        self.propagator = propagator
        self.boundary_tolerance_s = boundary_tolerance_s

    def calculate(
        self,
        *,
        request: ObservationRequest,
        tracks: tuple[SatelliteGroundTrack, ...],
        iceye_profile: PublicMissionProfile,
        pleiades_profile: PublicMissionProfile,
        calculation_start_utc: datetime,
        calculation_end_utc: datetime,
        step: timedelta,
        selected_mode_ids: set[str] | None = None,
    ) -> AccessCalculationResult:
        calculation_start = _as_utc(calculation_start_utc)
        calculation_end = _as_utc(calculation_end_utc)
        if calculation_start >= calculation_end:
            raise ValueError("Początek obliczeń musi poprzedzać koniec")
        if step.total_seconds() <= 0:
            raise ValueError("Krok propagacji musi być dodatni")

        request_start = max(calculation_start, request.earliest_start_utc)
        request_end = min(calculation_end, request.latest_end_utc)
        if request_start >= request_end:
            raise ValueError("Zakres obliczeń nie przecina okna zlecenia")

        windows: list[GeometricAccessWindow] = []
        evaluated_mode_ids: set[str] = set()
        evaluated_satellites = 0
        warnings: list[str] = []

        for track in tracks:
            sensor_type = _sensor_type_for_family(track.satellite.family)
            if sensor_type not in request.requested_sensor_types:
                continue

            evaluated_satellites += 1
            profile = _profile_for_family(
                track.satellite.family,
                iceye_profile=iceye_profile,
                pleiades_profile=pleiades_profile,
            )
            for mode in profile.sensor.imaging_modes:
                if not mode.is_active:
                    continue
                if selected_mode_ids and mode.mode_id not in selected_mode_ids:
                    continue
                if mode.nominal_resolution_m > request.resolution_limit_for(
                    mode.sensor_type
                ):
                    continue

                evaluated_mode_ids.add(mode.mode_id)
                coverage_ratio = approximate_coverage_ratio(
                    request.geometry,
                    scene_width_km=mode.nominal_scene_width_km,
                    scene_length_km=mode.nominal_scene_length_km,
                )
                if coverage_ratio < request.minimum_coverage_ratio:
                    continue
                windows.extend(
                    _build_windows(
                        request=request,
                        track=track,
                        profile=profile,
                        mode=mode,
                        calculation_start=request_start,
                        calculation_end=request_end,
                        step=step,
                        coverage_ratio=coverage_ratio,
                        propagator=self.propagator,
                        boundary_tolerance_s=self.boundary_tolerance_s,
                    )
                )

        if evaluated_satellites == 0:
            warnings.append(
                "Brak publicznych satelitów zgodnych z typem sensora zlecenia."
            )
        if not evaluated_mode_ids:
            warnings.append(
                "Brak aktywnych trybów spełniających wymaganie rozdzielczości."
            )
        if not windows:
            warnings.append(
                "W zadanym horyzoncie nie znaleziono okien spełniających "
                "model geometrii, oświetlenia i pokrycia."
            )

        windows.sort(
            key=lambda window: (
                window.start_utc,
                window.satellite_id,
                window.mode_id,
            )
        )
        return AccessCalculationResult(
            request_id=request.request_id,
            request_name=request.name,
            generated_at_utc=datetime.now(timezone.utc),
            calculation_start_utc=request_start,
            calculation_end_utc=request_end,
            propagation_step_s=step.total_seconds(),
            evaluated_satellites=evaluated_satellites,
            evaluated_modes=len(evaluated_mode_ids),
            windows=tuple(windows),
            warnings=tuple(warnings),
        )
