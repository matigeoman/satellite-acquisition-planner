from __future__ import annotations

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
    SatelliteFamily,
    SatelliteGroundTrack,
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
    if mode.nominal_resolution_m > request.max_resolution_m:
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
                abs(
                    sample.path_point.incidence_angle_deg
                    - target_incidence
                ),
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
) -> tuple[str, ...]:
    notes = [
        "Okno wyznaczono z publicznych GP/OMM i dyskretnej propagacji SGP4.",
    ]
    if request.geometry.type == "Polygon":
        notes.append(
            "Pokrycie poligonu jest oszacowaniem na podstawie bounding box AOI "
            "i nominalnego prostokątnego footprintu trybu."
        )
    if mode.sensor_type == SensorType.OPTICAL:
        notes.append(
            "Uwzględniono elewację Słońca, ale zachmurzenie zostanie "
            "dołączone w kolejnym etapie."
        )
    return tuple(notes)


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
) -> list[GeometricAccessWindow]:
    if not track.states:
        return []

    target_longitude, target_latitude = geometry_centroid(request.geometry)
    target_ecef = geodetic_to_ecef(target_latitude, target_longitude)
    satellite_ecef = [
        geodetic_to_ecef(
            state.latitude_deg,
            state.longitude_deg,
            state.altitude_km,
        )
        for state in track.states
    ]

    evaluated: list[_EvaluatedSample] = []
    for index, state in enumerate(track.states):
        previous_index = max(0, index - 1)
        next_index = min(len(track.states) - 1, index + 1)
        side = ObservationSide(
            observation_side(
                previous_satellite_ecef=satellite_ecef[previous_index],
                satellite_ecef=satellite_ecef[index],
                next_satellite_ecef=satellite_ecef[next_index],
                target_ecef=target_ecef,
            )
        )
        off_nadir, incidence = target_look_angles(
            satellite_latitude_deg=state.latitude_deg,
            satellite_longitude_deg=state.longitude_deg,
            satellite_altitude_km=state.altitude_km,
            target_latitude_deg=target_latitude,
            target_longitude_deg=target_longitude,
        )
        sun_elevation = None
        if mode.sensor_type == SensorType.OPTICAL:
            sun_elevation = solar_elevation_deg(
                timestamp_utc=state.timestamp_utc,
                latitude_deg=target_latitude,
                longitude_deg=target_longitude,
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
        evaluated.append(
            _EvaluatedSample(
                path_point=path_point,
                observation_side=side,
                is_valid=_sample_is_valid(
                    request=request,
                    profile=profile,
                    mode=mode,
                    side=side,
                    off_nadir_deg=off_nadir,
                    incidence_deg=incidence,
                    sun_elevation=sun_elevation,
                    coverage_ratio=coverage_ratio,
                ),
            )
        )

    groups: list[list[_EvaluatedSample]] = []
    active: list[_EvaluatedSample] = []
    for sample in evaluated:
        if sample.is_valid:
            active.append(sample)
            continue
        if active:
            groups.append(active)
            active = []
    if active:
        groups.append(active)

    windows: list[GeometricAccessWindow] = []
    half_step = step / 2
    notes = _window_notes(request=request, mode=mode)
    for group_index, group in enumerate(groups, start=1):
        start = max(
            calculation_start,
            group[0].path_point.timestamp_utc - half_step,
        )
        end = min(
            calculation_end,
            group[-1].path_point.timestamp_utc + half_step,
        )
        duration_s = (end - start).total_seconds()
        if duration_s < mode.min_acquisition_duration_s:
            continue

        peak = _peak_sample(group, mode)
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
                peak_sun_elevation_deg=(
                    peak.path_point.sun_elevation_deg
                ),
                orbit_epoch_utc=track.satellite.record.epoch_utc,
                sample_count=len(group),
                path=tuple(sample.path_point for sample in group),
                notes=notes,
            )
        )
    return windows


class GeometricAccessCalculator:
    """Wyznacza publiczne okna dostępu dla Point/Polygon w WGS84."""

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
                if mode.nominal_resolution_m > request.max_resolution_m:
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
