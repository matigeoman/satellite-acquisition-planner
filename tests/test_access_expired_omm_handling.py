from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.access_service import PublicAccessService


class _OrbitServiceStub:
    def __init__(self) -> None:
        self.allow_expired_orbits: bool | None = None

    def propagate_snapshot(
        self,
        snapshot,
        *,
        start_utc,
        duration,
        step,
        allow_expired_orbits=False,
    ):
        self.allow_expired_orbits = allow_expired_orbits
        return ("TRACK",)


class _CalculatorStub:
    def calculate(self, **kwargs):
        return kwargs


def test_access_service_forwards_expired_orbit_override() -> None:
    orbit_service = _OrbitServiceStub()
    service = PublicAccessService(
        orbit_service=orbit_service,
        calculator=_CalculatorStub(),
    )
    start = datetime(2026, 7, 15, tzinfo=timezone.utc)

    result = service.calculate_for_request(
        request="REQUEST",
        snapshot="SNAPSHOT",
        start_utc=start,
        end_utc=start + timedelta(hours=1),
        step=timedelta(seconds=30),
        selected_mode_ids={"MODE"},
        allow_expired_orbits=True,
    )

    assert orbit_service.allow_expired_orbits is True
    assert result["tracks"] == ("TRACK",)
    assert result["selected_mode_ids"] == {"MODE"}


def test_access_page_handles_expired_omm_without_traceback() -> None:
    source = Path("app/ui/pages/access.py").read_text(encoding="utf-8")

    assert "except ExpiredOrbitDataError as error:" in source
    assert "Tryb demonstracyjny: dopuść OMM starsze niż 72 h" in source
    assert "allow_expired_orbits=allow_expired_orbits" in source
    assert "Okna są orientacyjne" in source
