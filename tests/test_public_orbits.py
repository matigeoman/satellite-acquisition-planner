from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.integrations.orbits import (
    CelestrakClient,
    CelestrakClientError,
    PublicOrbitRecord,
    SatelliteFamily,
    Sgp4OrbitPropagator,
    select_iceye_records,
    select_pleiades_neo_records,
)


SAMPLE_OMM = {
    "OBJECT_NAME": "ISS (ZARYA)",
    "OBJECT_ID": "1998-067A",
    "EPOCH": "2019-12-09T16:38:29.363423",
    "MEAN_MOTION": 15.50103472,
    "ECCENTRICITY": 0.0007417,
    "INCLINATION": 51.6439,
    "RA_OF_ASC_NODE": 211.2001,
    "ARG_OF_PERICENTER": 17.6667,
    "MEAN_ANOMALY": 85.6398,
    "EPHEMERIS_TYPE": 0,
    "CLASSIFICATION_TYPE": "U",
    "NORAD_CAT_ID": 25544,
    "ELEMENT_SET_NO": 999,
    "REV_AT_EPOCH": 20248,
    "BSTAR": 3.8792e-05,
    "MEAN_MOTION_DOT": 1.764e-05,
    "MEAN_MOTION_DDOT": 0.0,
}


def _omm(name: str, norad: int, epoch_hour: int = 12) -> dict[str, object]:
    payload = dict(SAMPLE_OMM)
    payload.update(
        {
            "OBJECT_NAME": name,
            "OBJECT_ID": f"2025-{norad % 1000:03d}A",
            "NORAD_CAT_ID": norad,
            "EPOCH": f"2026-07-16T{epoch_hour:02d}:00:00.000000",
            "INCLINATION": 97.8,
            "MEAN_MOTION": 15.2,
        }
    )
    return payload


def test_public_orbit_record_parses_omm_and_period() -> None:
    record = PublicOrbitRecord.from_omm(SAMPLE_OMM)

    assert record.object_name == "ISS (ZARYA)"
    assert record.norad_cat_id == 25544
    assert record.epoch_utc.tzinfo is not None
    assert record.orbital_period_minutes == pytest.approx(92.897, rel=1e-4)


def test_celestrak_client_uses_fresh_cache_without_second_request(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    now = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)

    def transport(url: str, _timeout: float) -> bytes:
        calls.append(url)
        return json.dumps([_omm("ICEYE-X99", 65001)]).encode()

    client = CelestrakClient(
        cache_directory=tmp_path,
        transport=transport,
        now_provider=lambda: now,
    )

    first = client.fetch_by_name("ICEYE")
    second = client.fetch_by_name("ICEYE")

    assert first.from_cache is False
    assert second.from_cache is True
    assert second.is_stale is False
    assert len(calls) == 1


def test_celestrak_client_falls_back_to_stale_cache(tmp_path: Path) -> None:
    current = [datetime(2026, 7, 16, 12, tzinfo=timezone.utc)]

    def working(_url: str, _timeout: float) -> bytes:
        return json.dumps([_omm("ICEYE-X99", 65001)]).encode()

    client = CelestrakClient(
        cache_directory=tmp_path,
        transport=working,
        now_provider=lambda: current[0],
    )
    client.fetch_by_name("ICEYE")

    current[0] += timedelta(hours=3)

    def failing(_url: str, _timeout: float) -> bytes:
        raise TimeoutError("test timeout")

    client.transport = failing
    result = client.fetch_by_name("ICEYE")

    assert result.from_cache is True
    assert result.is_stale is True
    assert "ostatniego cache" in (result.warning or "")


def test_celestrak_offline_without_cache_is_explicit(tmp_path: Path) -> None:
    client = CelestrakClient(cache_directory=tmp_path)

    with pytest.raises(CelestrakClientError, match="Brak lokalnego cache"):
        client.fetch_by_name("ICEYE", allow_network=False)


def test_constellation_selection_assigns_four_plus_two_slots() -> None:
    iceye_records = [
        PublicOrbitRecord.from_omm(_omm(f"ICEYE-X{index}", 64000 + index))
        for index in range(1, 7)
    ]
    pleiades_records = [
        PublicOrbitRecord.from_omm(_omm("PLEIADES NEO 4", 49000)),
        PublicOrbitRecord.from_omm(_omm("PLEIADES NEO 3", 48000)),
        PublicOrbitRecord.from_omm(_omm("PLEIADES NEO 5 DEB", 50000)),
    ]

    iceye = select_iceye_records(iceye_records)
    pleiades = select_pleiades_neo_records(pleiades_records)

    assert [satellite.slot_id for satellite in iceye] == [
        "SAR-01",
        "SAR-02",
        "SAR-03",
        "SAR-04",
    ]
    assert all(satellite.family == SatelliteFamily.ICEYE for satellite in iceye)
    assert [satellite.record.object_name for satellite in pleiades] == [
        "PLEIADES NEO 3",
        "PLEIADES NEO 4",
    ]


def test_sgp4_propagation_returns_plausible_earth_position() -> None:
    record = PublicOrbitRecord.from_omm(SAMPLE_OMM)
    propagator = Sgp4OrbitPropagator()

    state = propagator.propagate_record(
        record,
        datetime(2019, 12, 9, 20, 42, tzinfo=timezone.utc),
    )

    assert -90 <= state.latitude_deg <= 90
    assert -180 <= state.longitude_deg <= 180
    assert 350 <= state.altitude_km <= 500
    assert len(state.teme_position_km) == 3


def test_celestrak_url_explicitly_requests_json() -> None:
    url = CelestrakClient.build_name_query_url("PLEIADES NEO")

    assert "NAME=PLEIADES+NEO" in url
    assert "FORMAT=JSON" in url


def test_celestrak_force_refresh_bypasses_fresh_cache(tmp_path: Path) -> None:
    calls: list[str] = []
    current = [datetime(2026, 7, 16, 12, tzinfo=timezone.utc)]

    def transport(url: str, _timeout: float) -> bytes:
        calls.append(url)
        norad = 65000 + len(calls)
        return json.dumps([_omm(f"ICEYE-X{len(calls)}", norad)]).encode()

    client = CelestrakClient(
        cache_directory=tmp_path,
        transport=transport,
        now_provider=lambda: current[0],
    )

    first = client.fetch_by_name("ICEYE")
    current[0] += timedelta(minutes=5)
    refreshed = client.fetch_by_name("ICEYE", force_refresh=True)

    assert first.from_cache is False
    assert refreshed.from_cache is False
    assert refreshed.records[0].norad_cat_id == 65002
    assert len(calls) == 2


def test_celestrak_rejects_force_refresh_in_offline_mode(tmp_path: Path) -> None:
    client = CelestrakClient(cache_directory=tmp_path)

    with pytest.raises(ValueError, match="allow_network=True"):
        client.fetch_by_name(
            "ICEYE",
            allow_network=False,
            force_refresh=True,
        )


def test_force_refresh_failure_uses_fresh_cache_without_marking_it_stale(
    tmp_path: Path,
) -> None:
    current = [datetime(2026, 7, 16, 12, tzinfo=timezone.utc)]

    def working(_url: str, _timeout: float) -> bytes:
        return json.dumps([_omm("ICEYE-X99", 65001)]).encode()

    client = CelestrakClient(
        cache_directory=tmp_path,
        transport=working,
        now_provider=lambda: current[0],
    )
    client.fetch_by_name("ICEYE")
    current[0] += timedelta(minutes=5)

    def failing(_url: str, _timeout: float) -> bytes:
        raise TimeoutError("forced refresh timeout")

    client.transport = failing
    result = client.fetch_by_name("ICEYE", force_refresh=True)

    assert result.from_cache is True
    assert result.is_stale is False
    assert "ostatniego cache" in (result.warning or "")
