from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.integrations.orbits import (
    DEFAULT_CONSTELLATION_PINS,
    CelestrakClient,
    CelestrakEopClient,
    CelestrakQueryResult,
    ConstellationSelectionMode,
    EopClientError,
    EopQueryResult,
    OrbitFreshness,
    SatelliteGroundTrack,
    SatellitePin,
    Sgp4OrbitPropagator,
    TrackedSatellite,
    select_iceye_records,
    select_pinned_records,
    select_pleiades_neo_records,
    validate_pins,
)


@dataclass(frozen=True, slots=True)
class PublicConstellationSnapshot:
    """Publiczna konstelacja przypisana do slotów planera."""

    generated_at_utc: datetime
    satellites: tuple[TrackedSatellite, ...]
    queries: tuple[CelestrakQueryResult, ...]
    warnings: tuple[str, ...]
    selection_mode: ConstellationSelectionMode = ConstellationSelectionMode.LIVE
    pins: tuple[SatellitePin, ...] = ()
    eop_query: EopQueryResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at_utc": self.generated_at_utc.isoformat(),
            "selection_mode": self.selection_mode.value,
            "pins": [pin.to_dict() for pin in self.pins],
            "satellites": [satellite.to_dict() for satellite in self.satellites],
            "queries": [
                {
                    "query_name": query.query_name,
                    "fetched_at_utc": query.fetched_at_utc.isoformat(),
                    "request_url": query.request_url,
                    "from_cache": query.from_cache,
                    "is_stale": query.is_stale,
                    "warning": query.warning,
                    "record_count": len(query.records),
                }
                for query in self.queries
            ],
            "warnings": list(self.warnings),
            "eop": (
                None
                if self.eop_query is None
                else {
                    "fetched_at_utc": self.eop_query.fetched_at_utc.isoformat(),
                    "request_url": self.eop_query.request_url,
                    "from_cache": self.eop_query.from_cache,
                    "is_stale": self.eop_query.is_stale,
                    "warning": self.eop_query.warning,
                    "frame": self.eop_query.table.frame,
                    "start_utc": self.eop_query.table.start_utc.isoformat(),
                    "end_utc": self.eop_query.table.end_utc.isoformat(),
                }
            ),
        }


class ExpiredOrbitDataError(RuntimeError):
    """Elementy orbitalne są zbyt stare dla żądanej chwili propagacji."""


class PublicOrbitService:
    """Łączy CelesTrak, wybór PINNED/LIVE oraz propagację SGP4."""

    def __init__(
        self,
        *,
        client: CelestrakClient,
        propagator: Sgp4OrbitPropagator | None = None,
        eop_client: CelestrakEopClient | None = None,
        selection_mode: ConstellationSelectionMode = (
            ConstellationSelectionMode.PINNED
        ),
        pins: Sequence[SatellitePin] = DEFAULT_CONSTELLATION_PINS,
        strict_pins: bool = True,
    ) -> None:
        self.client = client
        self.propagator = propagator or Sgp4OrbitPropagator()
        self.eop_client = eop_client
        self.selection_mode = ConstellationSelectionMode(selection_mode)
        self.pins = tuple(pins)
        self.strict_pins = strict_pins
        if self.pins:
            validate_pins(self.pins)
        elif self.selection_mode is ConstellationSelectionMode.PINNED:
            raise ValueError("Tryb PINNED wymaga co najmniej jednego przypiętego satelity")

    def _select_constellation(
        self,
        *,
        iceye_query: CelestrakQueryResult,
        pleiades_query: CelestrakQueryResult,
        mode: ConstellationSelectionMode,
    ) -> tuple[TrackedSatellite, ...]:
        if mode is ConstellationSelectionMode.PINNED:
            return select_pinned_records(
                (*iceye_query.records, *pleiades_query.records),
                pins=self.pins,
                strict=self.strict_pins,
            )

        iceye = select_iceye_records(iceye_query.records, count=4)
        pleiades = select_pleiades_neo_records(
            pleiades_query.records,
            count=2,
        )
        return tuple((*iceye, *pleiades))

    def load_default_constellation(
        self,
        *,
        allow_network: bool = True,
        force_refresh: bool = False,
        selection_mode: ConstellationSelectionMode | None = None,
    ) -> PublicConstellationSnapshot:
        mode = self.selection_mode if selection_mode is None else selection_mode
        mode = ConstellationSelectionMode(mode)

        iceye_query = self.client.fetch_by_name(
            "ICEYE",
            allow_network=allow_network,
            force_refresh=force_refresh,
        )
        pleiades_query = self.client.fetch_by_name(
            "PLEIADES NEO",
            allow_network=allow_network,
            force_refresh=force_refresh,
        )
        satellites = self._select_constellation(
            iceye_query=iceye_query,
            pleiades_query=pleiades_query,
            mode=mode,
        )

        warnings: list[str] = []
        eop_query: EopQueryResult | None = None
        if self.eop_client is not None:
            try:
                eop_query = self.eop_client.fetch(
                    allow_network=allow_network,
                    force_refresh=force_refresh,
                )
                self.propagator.set_eop_table(eop_query.table)
                if eop_query.warning:
                    warnings.append(eop_query.warning)
            except EopClientError as error:
                self.propagator.set_eop_table(None)
                warnings.append(
                    "Nie udało się wczytać EOP; transformacja Earth Fixed "
                    f"korzysta z trybu przybliżonego: {error}"
                )

        for query in (iceye_query, pleiades_query):
            if query.warning:
                warnings.append(query.warning)

        expected_count = (
            len(self.pins)
            if mode is ConstellationSelectionMode.PINNED
            else 6
        )
        if len(satellites) < expected_count:
            warnings.append(
                f"Tryb {mode.value} zwrócił {len(satellites)} z "
                f"{expected_count} oczekiwanych obiektów publicznych."
            )

        return PublicConstellationSnapshot(
            generated_at_utc=datetime.now(timezone.utc),
            satellites=satellites,
            queries=(iceye_query, pleiades_query),
            warnings=tuple(warnings),
            selection_mode=mode,
            pins=self.pins if mode is ConstellationSelectionMode.PINNED else (),
            eop_query=eop_query,
        )

    def propagate_snapshot(
        self,
        snapshot: PublicConstellationSnapshot,
        *,
        start_utc: datetime,
        duration: timedelta,
        step: timedelta,
        allow_expired_orbits: bool = False,
    ) -> tuple[SatelliteGroundTrack, ...]:
        expired = [
            satellite
            for satellite in snapshot.satellites
            if satellite.record.freshness_at(start_utc) == OrbitFreshness.EXPIRED
        ]
        if expired and not allow_expired_orbits:
            details = ", ".join(
                f"{satellite.slot_id}/{satellite.record.object_name} "
                f"({satellite.record.age_at(start_utc).total_seconds() / 3600.0:.1f} h)"
                for satellite in expired
            )
            raise ExpiredOrbitDataError(
                "Elementy OMM przekroczyły dopuszczalny wiek 72 h: " + details
            )
        return tuple(
            self.propagator.ground_track(
                satellite,
                start_utc=start_utc,
                duration=duration,
                step=step,
            )
            for satellite in snapshot.satellites
        )
