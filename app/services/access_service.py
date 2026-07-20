from __future__ import annotations

from datetime import datetime, timedelta

from app.catalogs import (
    ICEYE_PUBLIC_PROFILE,
    PLEIADES_NEO_PUBLIC_PROFILE,
)
from app.integrations.access import (
    AccessCalculationResult,
    GeometricAccessCalculator,
)
from app.models.request import ObservationRequest
from app.services.orbit_service import (
    PublicConstellationSnapshot,
    PublicOrbitService,
)


class PublicAccessService:
    """Łączy publiczną konstelację, propagację i model dostępu sensorów."""

    def __init__(
        self,
        *,
        orbit_service: PublicOrbitService,
        calculator: GeometricAccessCalculator | None = None,
    ) -> None:
        self.orbit_service = orbit_service
        self.calculator = calculator or GeometricAccessCalculator()

    def calculate_for_request(
        self,
        *,
        request: ObservationRequest,
        snapshot: PublicConstellationSnapshot,
        start_utc: datetime,
        end_utc: datetime,
        step: timedelta,
        selected_mode_ids: set[str] | None = None,
    ) -> AccessCalculationResult:
        if start_utc >= end_utc:
            raise ValueError("start_utc musi być wcześniejsze niż end_utc")
        tracks = self.orbit_service.propagate_snapshot(
            snapshot,
            start_utc=start_utc,
            duration=end_utc - start_utc,
            step=step,
        )
        return self.calculator.calculate(
            request=request,
            tracks=tracks,
            iceye_profile=ICEYE_PUBLIC_PROFILE,
            pleiades_profile=PLEIADES_NEO_PUBLIC_PROFILE,
            calculation_start_utc=start_utc,
            calculation_end_utc=end_utc,
            step=step,
            selected_mode_ids=selected_mode_ids,
        )
