from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from app.integrations.orbits import OrbitFreshness
from app.ui.pages.globe import _resolve_scene_start


def _snapshot_with_expiration(
    expired_at_utc: datetime,
) -> Any:
    def freshness_at(timestamp_utc: datetime) -> object:
        if timestamp_utc == expired_at_utc:
            return OrbitFreshness.EXPIRED

        return object()

    record = SimpleNamespace(
        freshness_at=freshness_at,
    )
    satellite = SimpleNamespace(record=record)

    return SimpleNamespace(
        satellites=(satellite,),
    )


def test_scene_start_keeps_supported_time() -> None:
    candidate = datetime(
        2026, 8, 4, 9,
        tzinfo=timezone.utc,
    )
    fallback = datetime(
        2026, 8, 4, 10,
        tzinfo=timezone.utc,
    )
    unrelated_time = datetime(
        2026, 8, 24, 9,
        tzinfo=timezone.utc,
    )

    result = _resolve_scene_start(
        snapshot=_snapshot_with_expiration(
            unrelated_time
        ),
        candidates=(candidate,),
        fallback_utc=fallback,
    )

    assert result == candidate


def test_scene_start_rejects_expired_time() -> None:
    expired_candidate = datetime(
        2026, 8, 24, 9,
        tzinfo=timezone.utc,
    )
    fallback = datetime(
        2026, 8, 4, 10,
        tzinfo=timezone.utc,
    )

    result = _resolve_scene_start(
        snapshot=_snapshot_with_expiration(
            expired_candidate
        ),
        candidates=(expired_candidate,),
        fallback_utc=fallback,
    )

    assert result == fallback
