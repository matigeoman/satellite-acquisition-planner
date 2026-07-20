from __future__ import annotations

import re
from collections.abc import Iterable

from app.integrations.orbits.models import (
    PublicOrbitRecord,
    SatelliteFamily,
    TrackedSatellite,
)


_EXCLUDED_NAME_TOKENS = (" DEB", " R/B", "ROCKET BODY")


def _normalized_name(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", value.upper())


def _usable_records(
    records: Iterable[PublicOrbitRecord],
) -> list[PublicOrbitRecord]:
    unique: dict[int, PublicOrbitRecord] = {}
    for record in records:
        upper = record.object_name.upper()
        if any(token in upper for token in _EXCLUDED_NAME_TOKENS):
            continue
        current = unique.get(record.norad_cat_id)
        if current is None or record.epoch_utc > current.epoch_utc:
            unique[record.norad_cat_id] = record
    return list(unique.values())


def select_iceye_records(
    records: Iterable[PublicOrbitRecord],
    *,
    count: int = 4,
) -> tuple[TrackedSatellite, ...]:
    """Wybiera cztery aktualne publiczne obiekty ICEYE."""

    candidates = [
        record
        for record in _usable_records(records)
        if "ICEYE" in _normalized_name(record.object_name)
    ]
    candidates.sort(
        key=lambda record: (
            record.norad_cat_id,
            record.epoch_utc,
        ),
        reverse=True,
    )
    return tuple(
        TrackedSatellite(
            slot_id=f"SAR-{index:02d}",
            family=SatelliteFamily.ICEYE,
            record=record,
        )
        for index, record in enumerate(candidates[:count], start=1)
    )


def select_pleiades_neo_records(
    records: Iterable[PublicOrbitRecord],
    *,
    count: int = 2,
) -> tuple[TrackedSatellite, ...]:
    """Preferuje działające Pléiades Neo 3 i 4, z bezpiecznym fallbackiem."""

    candidates = [
        record
        for record in _usable_records(records)
        if "PLEIADESNEO" in _normalized_name(record.object_name)
    ]
    preferred_order = {
        "PLEIADESNEO3": 0,
        "PLEIADESNEO4": 1,
    }

    def sort_key(record: PublicOrbitRecord) -> tuple[int, int]:
        name = _normalized_name(record.object_name)
        preference = min(
            (
                rank
                for token, rank in preferred_order.items()
                if token in name
            ),
            default=99,
        )
        return preference, -record.norad_cat_id

    candidates.sort(key=sort_key)
    return tuple(
        TrackedSatellite(
            slot_id=f"EO-{index:02d}",
            family=SatelliteFamily.PLEIADES_NEO,
            record=record,
        )
        for index, record in enumerate(candidates[:count], start=1)
    )
