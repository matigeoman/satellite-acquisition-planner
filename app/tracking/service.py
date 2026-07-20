from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
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
            age_hours = abs(
                (timestamp - satellite.record.epoch_utc).total_seconds()
            ) / 3600.0
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
                track.states[index + 1]
                if index + 1 < len(track.states)
                else None
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
                previous is not None
                and previous.elevation_deg >= minimum_elevation_deg
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
                    satellite_illuminated_at_maximum=(
                        visibility.satellite_illuminated
                    ),
                    observer_sun_elevation_at_maximum_deg=(
                        visibility.observer_sun_elevation_deg
                    ),
                    optical_visibility_at_maximum=(
                        visibility.optical_visibility
                    ),
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
