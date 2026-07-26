from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.integrations.orbits import (
    CelestrakQueryResult,
    ConstellationSelectionMode,
    PinnedSatelliteSelectionError,
    PublicOrbitRecord,
    SatelliteFamily,
    SatellitePin,
)
from app.services.orbit_service import PublicOrbitService


def _omm(name: str, norad: int, epoch_hour: int) -> dict[str, object]:
    return {
        "OBJECT_NAME": name,
        "OBJECT_ID": f"2026-{norad % 1000:03d}A",
        "EPOCH": f"2026-07-26T{epoch_hour:02d}:00:00.000000",
        "MEAN_MOTION": 15.1,
        "ECCENTRICITY": 0.0002,
        "INCLINATION": 97.8,
        "RA_OF_ASC_NODE": 120.0,
        "ARG_OF_PERICENTER": 10.0,
        "MEAN_ANOMALY": 20.0,
        "BSTAR": 0.00001,
        "MEAN_MOTION_DOT": 0.0,
        "MEAN_MOTION_DDOT": 0.0,
        "ELEMENT_SET_NO": 1,
        "REV_AT_EPOCH": 100,
        "NORAD_CAT_ID": norad,
        "CLASSIFICATION_TYPE": "U",
        "EPHEMERIS_TYPE": 0,
    }


def _query(name: str, records: tuple[PublicOrbitRecord, ...]) -> CelestrakQueryResult:
    return CelestrakQueryResult(
        query_name=name,
        records=records,
        fetched_at_utc=datetime(2026, 7, 26, 15, tzinfo=timezone.utc),
        request_url="https://example.invalid/omm",
        from_cache=False,
        is_stale=False,
    )


class FakeClient:
    def __init__(
        self,
        *,
        iceye: tuple[PublicOrbitRecord, ...],
        pleiades: tuple[PublicOrbitRecord, ...],
    ) -> None:
        self.iceye = iceye
        self.pleiades = pleiades

    def fetch_by_name(
        self,
        query_name: str,
        *,
        allow_network: bool = True,
        force_refresh: bool = False,
    ) -> CelestrakQueryResult:
        del allow_network, force_refresh
        if query_name == "ICEYE":
            return _query(query_name, self.iceye)
        return _query(query_name, self.pleiades)


class FakePropagator:
    pass


def test_service_pinned_mode_keeps_exact_slot_assignment() -> None:
    pins = (
        SatellitePin("SAR-01", SatelliteFamily.ICEYE, 68996, "ICEYE-X82"),
        SatellitePin(
            "EO-01",
            SatelliteFamily.PLEIADES_NEO,
            48268,
            "PLEIADES NEO 3",
        ),
    )
    iceye = (
        PublicOrbitRecord.from_omm(_omm("ICEYE-X99", 69999, 23)),
        PublicOrbitRecord.from_omm(_omm("ICEYE-X82", 68996, 12)),
    )
    pleiades = (
        PublicOrbitRecord.from_omm(_omm("PLEIADES NEO 3", 48268, 11)),
    )
    service = PublicOrbitService(
        client=FakeClient(iceye=iceye, pleiades=pleiades),
        propagator=FakePropagator(),
        selection_mode=ConstellationSelectionMode.PINNED,
        pins=pins,
    )

    snapshot = service.load_default_constellation()

    assert snapshot.selection_mode is ConstellationSelectionMode.PINNED
    assert [satellite.slot_id for satellite in snapshot.satellites] == [
        "SAR-01",
        "EO-01",
    ]
    assert [satellite.record.norad_cat_id for satellite in snapshot.satellites] == [
        68996,
        48268,
    ]
    assert snapshot.pins == pins


def test_service_live_mode_uses_dynamic_selection() -> None:
    iceye = tuple(
        PublicOrbitRecord.from_omm(_omm(f"ICEYE-X{index}", 68000 + index, index))
        for index in range(1, 6)
    )
    pleiades = (
        PublicOrbitRecord.from_omm(_omm("PLEIADES NEO 4", 49070, 10)),
        PublicOrbitRecord.from_omm(_omm("PLEIADES NEO 3", 48268, 9)),
    )
    service = PublicOrbitService(
        client=FakeClient(iceye=iceye, pleiades=pleiades),
        propagator=FakePropagator(),
        selection_mode=ConstellationSelectionMode.LIVE,
        pins=(),
    )

    snapshot = service.load_default_constellation()

    assert snapshot.selection_mode is ConstellationSelectionMode.LIVE
    assert len(snapshot.satellites) == 6
    assert snapshot.satellites[0].record.object_name == "ICEYE-X5"
    assert snapshot.pins == ()


def test_service_pinned_mode_fails_instead_of_silent_remapping() -> None:
    pin = SatellitePin("SAR-01", SatelliteFamily.ICEYE, 68996, "ICEYE-X82")
    service = PublicOrbitService(
        client=FakeClient(iceye=(), pleiades=()),
        propagator=FakePropagator(),
        selection_mode=ConstellationSelectionMode.PINNED,
        pins=(pin,),
    )

    with pytest.raises(PinnedSatelliteSelectionError, match="brak NORAD 68996"):
        service.load_default_constellation()
