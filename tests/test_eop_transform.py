from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.integrations.orbits.coordinates import (
    EarthFixedTransformQuality,
    teme_to_earth_fixed,
)
from app.integrations.orbits.eop import EopDataKind, EopRangeError, EopTable


FIXTURES = Path(__file__).parent / "fixtures" / "stk_validation"
SCENARIO_EPOCH = datetime(2026, 7, 19, 8, 0, tzinfo=timezone.utc)


def test_eop_parser_interpolates_daily_values() -> None:
    table = EopTable.from_file(FIXTURES / "eop_2026_07_19_20.txt")
    value = table.interpolate(SCENARIO_EPOCH)

    assert table.frame == "ITRF2020"
    assert value.kind == EopDataKind.OBSERVED
    assert value.interpolation_fraction == pytest.approx(1.0 / 3.0)
    assert value.ut1_minus_utc_s == pytest.approx(0.009740133333333333)
    assert value.polar_motion_x_arcsec == pytest.approx(0.21539233333333332)
    assert value.polar_motion_y_arcsec == pytest.approx(0.37298433333333336)


def test_eop_parser_rejects_out_of_range_timestamp() -> None:
    table = EopTable.from_file(FIXTURES / "eop_2026_07_19_20.txt")

    with pytest.raises(EopRangeError):
        table.interpolate(datetime(2026, 7, 18, tzinfo=timezone.utc))


def test_teme_to_itrf_matches_stk_13_reference_within_two_centimetres() -> None:
    table = EopTable.from_file(FIXTURES / "eop_2026_07_19_20.txt")
    path = FIXTURES / "teme_itrf_reference_2026_07_19.csv"

    with path.open(newline="", encoding="utf-8") as handle:
        rows = tuple(csv.DictReader(handle))

    assert rows
    for row in rows:
        timestamp = SCENARIO_EPOCH + timedelta(
            seconds=float(row["seconds_from_epoch"])
        )
        teme_km = tuple(
            float(row[name]) / 1000.0
            for name in ("teme_x_m", "teme_y_m", "teme_z_m")
        )
        expected_itrf_km = tuple(
            float(row[name]) / 1000.0
            for name in ("itrf_x_m", "itrf_y_m", "itrf_z_m")
        )

        transformed = teme_to_earth_fixed(
            teme_km,
            timestamp,
            eop_table=table,
            strict_eop=True,
        )
        error_m = sum(
            ((actual - expected) * 1000.0) ** 2
            for actual, expected in zip(
                transformed.position_km,
                expected_itrf_km,
            )
        ) ** 0.5

        assert transformed.frame == "ITRF2020"
        assert transformed.quality == EarthFixedTransformQuality.EOP_OBSERVED
        assert error_m < 0.02, (row["satellite"], row["seconds_from_epoch"], error_m)


def test_transform_falls_back_explicitly_without_eop() -> None:
    result = teme_to_earth_fixed(
        (7000.0, 0.0, 0.0),
        SCENARIO_EPOCH,
    )

    assert result.frame == "PEF_APPROX"
    assert result.quality == EarthFixedTransformQuality.UTC_GMST_APPROX
    assert result.eop_applied is False


def test_eop_client_uses_cache_and_rejects_expired_fallback(tmp_path: Path) -> None:
    from app.integrations.orbits import CelestrakEopClient, EopClientError

    payload = (FIXTURES / "eop_2026_07_19_20.txt").read_bytes()
    current = [datetime(2026, 7, 26, 14, tzinfo=timezone.utc)]

    def working(_url: str, _timeout: float) -> bytes:
        return payload

    client = CelestrakEopClient(
        cache_directory=tmp_path,
        transport=working,
        now_provider=lambda: current[0],
    )
    fresh = client.fetch()
    cached = client.fetch()

    assert fresh.from_cache is False
    assert cached.from_cache is True
    assert cached.is_stale is False

    current[0] += timedelta(days=8)

    def failing(_url: str, _timeout: float) -> bytes:
        raise TimeoutError("test timeout")

    client.transport = failing
    with pytest.raises(EopClientError, match="maksymalny wiek"):
        client.fetch()
