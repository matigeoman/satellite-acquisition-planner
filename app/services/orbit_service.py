from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.integrations.orbits import (
    CelestrakClient,
    CelestrakQueryResult,
    SatelliteGroundTrack,
    Sgp4OrbitPropagator,
    TrackedSatellite,
    select_iceye_records,
    select_pleiades_neo_records,
)


@dataclass(frozen=True, slots=True)
class PublicConstellationSnapshot:
    """Sześć publicznie śledzonych satelitów używanych przez planer."""

    generated_at_utc: datetime
    satellites: tuple[TrackedSatellite, ...]
    queries: tuple[CelestrakQueryResult, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at_utc": self.generated_at_utc.isoformat(),
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
        }


class PublicOrbitService:
    """Łączy CelesTrak, selekcję 4+2 i propagację SGP4."""

    def __init__(
        self,
        *,
        client: CelestrakClient,
        propagator: Sgp4OrbitPropagator | None = None,
    ) -> None:
        self.client = client
        self.propagator = propagator or Sgp4OrbitPropagator()

    def load_default_constellation(
        self,
        *,
        allow_network: bool = True,
    ) -> PublicConstellationSnapshot:
        iceye_query = self.client.fetch_by_name(
            "ICEYE",
            allow_network=allow_network,
        )
        pleiades_query = self.client.fetch_by_name(
            "PLEIADES NEO",
            allow_network=allow_network,
        )

        iceye = select_iceye_records(iceye_query.records, count=4)
        pleiades = select_pleiades_neo_records(
            pleiades_query.records,
            count=2,
        )
        warnings: list[str] = []
        for query in (iceye_query, pleiades_query):
            if query.warning:
                warnings.append(query.warning)
        if len(iceye) < 4:
            warnings.append(
                f"CelesTrak zwrócił tylko {len(iceye)} użyteczne obiekty ICEYE."
            )
        if len(pleiades) < 2:
            warnings.append(
                "Nie odnaleziono obu publicznych obiektów Pléiades Neo 3/4."
            )

        return PublicConstellationSnapshot(
            generated_at_utc=datetime.now(timezone.utc),
            satellites=tuple((*iceye, *pleiades)),
            queries=(iceye_query, pleiades_query),
            warnings=tuple(warnings),
        )

    def propagate_snapshot(
        self,
        snapshot: PublicConstellationSnapshot,
        *,
        start_utc: datetime,
        duration: timedelta,
        step: timedelta,
    ) -> tuple[SatelliteGroundTrack, ...]:
        return tuple(
            self.propagator.ground_track(
                satellite,
                start_utc=start_utc,
                duration=duration,
                step=step,
            )
            for satellite in snapshot.satellites
        )
