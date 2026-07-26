from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from app.integrations.orbits.models import (
    PublicOrbitRecord,
    SatelliteFamily,
    SatellitePin,
    TrackedSatellite,
)


_EXCLUDED_NAME_TOKENS = (" DEB", " R/B", "ROCKET BODY")

# Reprodukowalna konstelacja sześciu obiektów. Numery NORAD są jawną
# konfiguracją slotów, a nie wynikiem dynamicznego odkrywania obiektów.
DEFAULT_CONSTELLATION_PINS: tuple[SatellitePin, ...] = (
    SatellitePin("SAR-01", SatelliteFamily.ICEYE, 68996, "ICEYE-X82"),
    SatellitePin("SAR-02", SatelliteFamily.ICEYE, 60539, "ICEYE-X43"),
    SatellitePin("SAR-03", SatelliteFamily.ICEYE, 60546, "ICEYE-X39"),
    SatellitePin("SAR-04", SatelliteFamily.ICEYE, 60549, "ICEYE-X40"),
    SatellitePin("EO-01", SatelliteFamily.PLEIADES_NEO, 48268, "PLEIADES NEO 3"),
    SatellitePin("EO-02", SatelliteFamily.PLEIADES_NEO, 49070, "PLEIADES NEO 4"),
)


class PinnedSatelliteSelectionError(RuntimeError):
    """Brakuje co najmniej jednego przypiętego obiektu albo jego nazwa jest niezgodna."""


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


def validate_pins(pins: Sequence[SatellitePin]) -> None:
    """Odrzuca niejednoznaczne przypisania slotów i numerów NORAD."""

    if not pins:
        raise ValueError("Lista przypiętych satelitów nie może być pusta")

    slot_ids = [pin.slot_id for pin in pins]
    duplicate_slots = sorted({slot for slot in slot_ids if slot_ids.count(slot) > 1})
    if duplicate_slots:
        raise ValueError("Powielone przypięte sloty: " + ", ".join(duplicate_slots))

    norad_ids = [pin.norad_cat_id for pin in pins]
    duplicate_norad = sorted(
        {norad for norad in norad_ids if norad_ids.count(norad) > 1}
    )
    if duplicate_norad:
        raise ValueError(
            "Powielone przypięte numery NORAD: "
            + ", ".join(str(value) for value in duplicate_norad)
        )


def select_pinned_records(
    records: Iterable[PublicOrbitRecord],
    *,
    pins: Sequence[SatellitePin] = DEFAULT_CONSTELLATION_PINS,
    strict: bool = True,
) -> tuple[TrackedSatellite, ...]:
    """Przypisuje dokładne obiekty NORAD do slotów w stałej kolejności."""

    validate_pins(pins)
    by_norad = {record.norad_cat_id: record for record in _usable_records(records)}
    selected: list[TrackedSatellite] = []
    errors: list[str] = []

    for pin in pins:
        record = by_norad.get(pin.norad_cat_id)
        if record is None:
            errors.append(f"{pin.slot_id}: brak NORAD {pin.norad_cat_id}")
            continue

        expected = _normalized_name(pin.expected_name_token)
        actual = _normalized_name(record.object_name)
        if expected not in actual:
            errors.append(
                f"{pin.slot_id}: niezgodna nazwa NORAD {pin.norad_cat_id} "
                f"({record.object_name!r}, oczekiwano {pin.expected_name_token!r})"
            )
            continue

        if pin.family is SatelliteFamily.ICEYE and "ICEYE" not in actual:
            errors.append(f"{pin.slot_id}: NORAD {pin.norad_cat_id} nie jest obiektem ICEYE")
            continue
        if pin.family is SatelliteFamily.PLEIADES_NEO and "PLEIADESNEO" not in actual:
            errors.append(
                f"{pin.slot_id}: NORAD {pin.norad_cat_id} nie jest obiektem Pléiades Neo"
            )
            continue

        selected.append(
            TrackedSatellite(
                slot_id=pin.slot_id,
                family=pin.family,
                record=record,
            )
        )

    if errors and strict:
        raise PinnedSatelliteSelectionError(
            "Nie można odtworzyć przypiętej konstelacji: " + "; ".join(errors)
        )
    return tuple(selected)


def select_iceye_records(
    records: Iterable[PublicOrbitRecord],
    *,
    count: int = 4,
) -> tuple[TrackedSatellite, ...]:
    """Tryb LIVE: wybiera rekordy ICEYE o najnowszej epoce OMM."""

    if count < 0:
        raise ValueError("Liczba wybieranych obiektów nie może być ujemna")
    candidates = [
        record
        for record in _usable_records(records)
        if "ICEYE" in _normalized_name(record.object_name)
    ]
    candidates.sort(
        key=lambda record: (
            record.epoch_utc,
            record.norad_cat_id,
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
    """Tryb LIVE: preferuje Pléiades Neo 3 i 4."""

    if count < 0:
        raise ValueError("Liczba wybieranych obiektów nie może być ujemna")
    candidates = [
        record
        for record in _usable_records(records)
        if "PLEIADESNEO" in _normalized_name(record.object_name)
    ]
    preferred_order = {
        "PLEIADESNEO3": 0,
        "PLEIADESNEO4": 1,
    }

    def sort_key(record: PublicOrbitRecord) -> tuple[int, float, int]:
        name = _normalized_name(record.object_name)
        preference = min(
            (rank for token, rank in preferred_order.items() if token in name),
            default=99,
        )
        return preference, -record.epoch_utc.timestamp(), -record.norad_cat_id

    candidates.sort(key=sort_key)
    return tuple(
        TrackedSatellite(
            slot_id=f"EO-{index:02d}",
            family=SatelliteFamily.PLEIADES_NEO,
            record=record,
        )
        for index, record in enumerate(candidates[:count], start=1)
    )


__all__ = [
    "DEFAULT_CONSTELLATION_PINS",
    "PinnedSatelliteSelectionError",
    "select_iceye_records",
    "select_pinned_records",
    "select_pleiades_neo_records",
    "validate_pins",
]
