from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from math import sqrt
from typing import Protocol

from app.integrations.orbits import (
    PropagatedState,
    SatelliteGroundTrack,
    TrackedSatellite,
)
from app.services.orbit_service import PublicConstellationSnapshot
from app.tracking.astronomy import assess_visibility
from app.tracking.geometry import (
    ensure_utc,
    interpolate_threshold_crossing,
    topocentric_from_state,
)
from app.tracking.models import (
    LiveSatelliteState,
    LiveTrackingSnapshot,
    ObserverSite,
    OrbitDataQuality,
    PassPrediction,
    PassQuality,
    SkyTrack,
    TopocentricState,
)


class OrbitPropagator(Protocol):
    def propagate_record(
        self,
        record,
        timestamp_utc: datetime,
    ) -> PropagatedState: ...

    def ground_track(
        self,
        satellite: TrackedSatellite,
        *,
        start_utc: datetime,
        duration: timedelta,
        step: timedelta,
    ) -> SatelliteGroundTrack: ...


def orbit_data_quality(age_hours: float) -> OrbitDataQuality:
    """Klasyfikuje wiek elementów orbitalnych do prezentacji operatorowi."""

    if age_hours <= 24.0:
        return OrbitDataQuality.FRESH
    if age_hours <= 72.0:
        return OrbitDataQuality.ACCEPTABLE
    if age_hours <= 168.0:
        return OrbitDataQuality.STALE
    return OrbitDataQuality.VERY_STALE


def _linear_value(
    first_time: datetime,
    first_value: float,
    second_time: datetime,
    second_value: float,
    timestamp: datetime,
) -> float:
    duration = (second_time - first_time).total_seconds()
    if duration <= 0.0:
        return first_value
    fraction = (timestamp - first_time).total_seconds() / duration
    fraction = max(0.0, min(1.0, fraction))
    return first_value + (second_value - first_value) * fraction


def _duration_above_elevation(
    samples: tuple[TopocentricState, ...],
    *,
    start_utc: datetime,
    end_utc: datetime,
    threshold_deg: float,
) -> float:
    total = 0.0
    for first, second in zip(samples, samples[1:]):
        segment_start = max(first.timestamp_utc, start_utc)
        segment_end = min(second.timestamp_utc, end_utc)
        if segment_end <= segment_start:
            continue
        first_elevation = _linear_value(
            first.timestamp_utc,
            first.elevation_deg,
            second.timestamp_utc,
            second.elevation_deg,
            segment_start,
        )
        second_elevation = _linear_value(
            first.timestamp_utc,
            first.elevation_deg,
            second.timestamp_utc,
            second.elevation_deg,
            segment_end,
        )
        duration = (segment_end - segment_start).total_seconds()
        first_above = first_elevation >= threshold_deg
        second_above = second_elevation >= threshold_deg
        if first_above and second_above:
            total += duration
        elif first_above != second_above:
            denominator = second_elevation - first_elevation
            if abs(denominator) < 1e-12:
                total += duration / 2.0
            else:
                crossing = (threshold_deg - first_elevation) / denominator
                crossing = max(0.0, min(1.0, crossing))
                total += duration * ((1.0 - crossing) if first_above else crossing)
    return total


def _visible_duration(
    *,
    observer: ObserverSite,
    states: tuple[PropagatedState, ...],
    samples: tuple[TopocentricState, ...],
    start_utc: datetime,
    end_utc: datetime,
) -> float:
    flags = [
        assess_visibility(
            observer=observer,
            propagated=state,
            topocentric=sample,
        ).is_optically_visible
        for state, sample in zip(states, samples)
    ]
    total = 0.0
    for index, (first, second) in enumerate(zip(samples, samples[1:])):
        segment_start = max(first.timestamp_utc, start_utc)
        segment_end = min(second.timestamp_utc, end_utc)
        if segment_end <= segment_start:
            continue
        duration = (segment_end - segment_start).total_seconds()
        total += duration * (int(flags[index]) + int(flags[index + 1])) / 2.0
    return total


def pass_quality_score(
    *,
    maximum_elevation_deg: float,
    duration_minutes: float,
    time_above_10_deg_minutes: float,
    minimum_range_km: float,
    optically_visible_duration_minutes: float,
) -> float:
    """Zwraca deterministyczny wynik 0–100 do rankingu przelotów."""

    elevation_points = min(50.0, max(0.0, maximum_elevation_deg) / 90.0 * 50.0)
    useful_time_points = min(25.0, max(0.0, time_above_10_deg_minutes) / 10.0 * 25.0)
    duration_points = min(10.0, max(0.0, duration_minutes) / 12.0 * 10.0)
    range_points = max(0.0, min(10.0, (2500.0 - minimum_range_km) / 2000.0 * 10.0))
    optical_points = min(5.0, max(0.0, optically_visible_duration_minutes) / 3.0 * 5.0)
    return round(
        elevation_points
        + useful_time_points
        + duration_points
        + range_points
        + optical_points,
        1,
    )


def pass_quality(score: float) -> PassQuality:
    if score >= 80.0:
        return PassQuality.EXCELLENT
    if score >= 60.0:
        return PassQuality.GOOD
    if score >= 40.0:
        return PassQuality.MARGINAL
    return PassQuality.POOR


def _speed_km_s(state: PropagatedState) -> float:
    return sqrt(sum(value * value for value in state.teme_velocity_km_s))


def _selected_satellites(
    snapshot: PublicConstellationSnapshot,
    slot_ids: Iterable[str] | None,
) -> tuple[TrackedSatellite, ...]:
    if slot_ids is None:
        return snapshot.satellites
    selected = set(slot_ids)
    return tuple(
        satellite for satellite in snapshot.satellites if satellite.slot_id in selected
    )


class LiveTrackingService:
    """Propaguje bieżący stan i przewiduje lokalne przeloty satelitów."""

    def __init__(self, propagator: OrbitPropagator | None = None) -> None:
        if propagator is None:
            from app.integrations.orbits import Sgp4OrbitPropagator

            propagator = Sgp4OrbitPropagator()
        self.propagator = propagator

    def current_states(
        self,
        snapshot: PublicConstellationSnapshot,
        *,
        observer: ObserverSite,
        timestamp_utc: datetime,
        slot_ids: Iterable[str] | None = None,
    ) -> tuple[LiveSatelliteState, ...]:
        timestamp = ensure_utc(timestamp_utc)
        result: list[LiveSatelliteState] = []
        for satellite in _selected_satellites(snapshot, slot_ids):
            propagated = self.propagator.propagate_record(
                satellite.record,
                timestamp,
            )
            next_state = self.propagator.propagate_record(
                satellite.record,
                timestamp + timedelta(seconds=1),
            )
            topocentric = topocentric_from_state(
                observer=observer,
                state=propagated,
                next_state=next_state,
            )
            age_hours = (
                abs((timestamp - satellite.record.epoch_utc).total_seconds()) / 3600.0
            )
            result.append(
                LiveSatelliteState(
                    slot_id=satellite.slot_id,
                    object_name=satellite.record.object_name,
                    norad_cat_id=satellite.record.norad_cat_id,
                    family=satellite.family,
                    propagated=propagated,
                    topocentric=topocentric,
                    visibility=assess_visibility(
                        observer=observer,
                        propagated=propagated,
                        topocentric=topocentric,
                    ),
                    speed_km_s=_speed_km_s(propagated),
                    orbit_data_age_hours=age_hours,
                    orbit_data_quality=orbit_data_quality(age_hours),
                )
            )
        return tuple(result)

    def sky_tracks(
        self,
        snapshot: PublicConstellationSnapshot,
        *,
        observer: ObserverSite,
        start_utc: datetime,
        duration: timedelta = timedelta(minutes=45),
        step: timedelta = timedelta(seconds=30),
        slot_ids: Iterable[str] | None = None,
    ) -> tuple[SkyTrack, ...]:
        tracks: list[SkyTrack] = []
        for satellite in _selected_satellites(snapshot, slot_ids):
            ground_track = self.propagator.ground_track(
                satellite,
                start_utc=ensure_utc(start_utc),
                duration=duration,
                step=step,
            )
            samples = self._topocentric_samples(
                observer=observer,
                track=ground_track,
            )
            tracks.append(
                SkyTrack(
                    slot_id=satellite.slot_id,
                    object_name=satellite.record.object_name,
                    family=satellite.family,
                    samples=samples,
                )
            )
        return tuple(tracks)

    @staticmethod
    def _topocentric_samples(
        *,
        observer: ObserverSite,
        track: SatelliteGroundTrack,
    ) -> tuple[TopocentricState, ...]:
        result: list[TopocentricState] = []
        for index, state in enumerate(track.states):
            next_state = (
                track.states[index + 1] if index + 1 < len(track.states) else None
            )
            result.append(
                topocentric_from_state(
                    observer=observer,
                    state=state,
                    next_state=next_state,
                )
            )
        return tuple(result)

    def predict_passes(
        self,
        snapshot: PublicConstellationSnapshot,
        *,
        observer: ObserverSite,
        start_utc: datetime,
        duration: timedelta = timedelta(hours=24),
        step: timedelta = timedelta(seconds=30),
        minimum_elevation_deg: float = 5.0,
        slot_ids: Iterable[str] | None = None,
    ) -> tuple[PassPrediction, ...]:
        if duration.total_seconds() <= 0.0:
            raise ValueError("duration musi być dodatnie")
        if step.total_seconds() <= 0.0:
            raise ValueError("step musi być dodatni")
        if not 0.0 <= minimum_elevation_deg < 90.0:
            raise ValueError("minimum_elevation_deg musi należeć do [0, 90)")

        passes: list[PassPrediction] = []
        for satellite in _selected_satellites(snapshot, slot_ids):
            track = self.propagator.ground_track(
                satellite,
                start_utc=ensure_utc(start_utc),
                duration=duration,
                step=step,
            )
            samples = self._topocentric_samples(observer=observer, track=track)
            passes.extend(
                self._passes_for_satellite(
                    observer=observer,
                    satellite=satellite,
                    states=track.states,
                    samples=samples,
                    minimum_elevation_deg=minimum_elevation_deg,
                )
            )
        return tuple(sorted(passes, key=lambda item: item.aos_utc))

    @staticmethod
    def _passes_for_satellite(
        *,
        observer: ObserverSite,
        satellite: TrackedSatellite,
        states: tuple[PropagatedState, ...],
        samples: tuple[TopocentricState, ...],
        minimum_elevation_deg: float,
    ) -> list[PassPrediction]:
        if len(states) != len(samples):
            raise ValueError("Liczba stanów i próbek topocentrycznych jest różna")
        if not samples:
            return []

        result: list[PassPrediction] = []
        active_indices: list[int] = []
        aos: TopocentricState | None = None

        for index, sample in enumerate(samples):
            above = sample.elevation_deg >= minimum_elevation_deg
            previous = samples[index - 1] if index > 0 else None
            previous_above = (
                previous is not None and previous.elevation_deg >= minimum_elevation_deg
            )

            if above and not previous_above:
                if previous is None:
                    aos = sample
                else:
                    aos = interpolate_threshold_crossing(
                        previous,
                        sample,
                        threshold_deg=minimum_elevation_deg,
                    )
                active_indices = [index]
            elif above:
                active_indices.append(index)

            leaving = not above and previous_above
            at_end = above and index == len(samples) - 1
            if not leaving and not at_end:
                continue

            if leaving and previous is not None:
                los = interpolate_threshold_crossing(
                    previous,
                    sample,
                    threshold_deg=minimum_elevation_deg,
                )
            else:
                los = sample

            if not active_indices or aos is None:
                active_indices = []
                aos = None
                continue

            maximum_index = max(
                active_indices,
                key=lambda item: samples[item].elevation_deg,
            )
            maximum_sample = samples[maximum_index]
            maximum_state = states[maximum_index]
            visibility = assess_visibility(
                observer=observer,
                propagated=maximum_state,
                topocentric=maximum_sample,
            )
            time_above_10 = _duration_above_elevation(
                samples,
                start_utc=aos.timestamp_utc,
                end_utc=los.timestamp_utc,
                threshold_deg=10.0,
            )
            visible_duration = _visible_duration(
                observer=observer,
                states=states,
                samples=samples,
                start_utc=aos.timestamp_utc,
                end_utc=los.timestamp_utc,
            )
            duration_minutes = (
                los.timestamp_utc - aos.timestamp_utc
            ).total_seconds() / 60.0
            quality_score = pass_quality_score(
                maximum_elevation_deg=maximum_sample.elevation_deg,
                duration_minutes=duration_minutes,
                time_above_10_deg_minutes=time_above_10 / 60.0,
                minimum_range_km=maximum_sample.range_km,
                optically_visible_duration_minutes=visible_duration / 60.0,
            )
            result.append(
                PassPrediction(
                    slot_id=satellite.slot_id,
                    object_name=satellite.record.object_name,
                    norad_cat_id=satellite.record.norad_cat_id,
                    family=satellite.family,
                    aos_utc=aos.timestamp_utc,
                    maximum_utc=maximum_sample.timestamp_utc,
                    los_utc=los.timestamp_utc,
                    aos_azimuth_deg=aos.azimuth_deg,
                    maximum_elevation_deg=maximum_sample.elevation_deg,
                    los_azimuth_deg=los.azimuth_deg,
                    minimum_range_km=maximum_sample.range_km,
                    satellite_illuminated_at_maximum=(visibility.satellite_illuminated),
                    observer_sun_elevation_at_maximum_deg=(
                        visibility.observer_sun_elevation_deg
                    ),
                    optical_visibility_at_maximum=(visibility.optical_visibility),
                    time_above_10_deg_s=time_above_10,
                    optically_visible_duration_s=visible_duration,
                    quality_score=quality_score,
                    quality=pass_quality(quality_score),
                )
            )
            active_indices = []
            aos = None

        return result

    def build_snapshot(
        self,
        snapshot: PublicConstellationSnapshot,
        *,
        observer: ObserverSite,
        timestamp_utc: datetime,
        sky_duration: timedelta = timedelta(minutes=45),
        pass_duration: timedelta = timedelta(hours=24),
        minimum_elevation_deg: float = 5.0,
        slot_ids: Iterable[str] | None = None,
    ) -> LiveTrackingSnapshot:
        timestamp = ensure_utc(timestamp_utc)
        return LiveTrackingSnapshot(
            observer=observer,
            timestamp_utc=timestamp,
            satellites=self.current_states(
                snapshot,
                observer=observer,
                timestamp_utc=timestamp,
                slot_ids=slot_ids,
            ),
            sky_tracks=self.sky_tracks(
                snapshot,
                observer=observer,
                start_utc=timestamp,
                duration=sky_duration,
                slot_ids=slot_ids,
            ),
            passes=self.predict_passes(
                snapshot,
                observer=observer,
                start_utc=timestamp,
                duration=pass_duration,
                minimum_elevation_deg=minimum_elevation_deg,
                slot_ids=slot_ids,
            ),
        )
