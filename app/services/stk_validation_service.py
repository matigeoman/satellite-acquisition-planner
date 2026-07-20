from __future__ import annotations

from app.integrations.access.models import GeometricAccessWindow
from app.integrations.orbits import TrackedSatellite
from app.integrations.stk_validation import (
    AccessValidationResult,
    AerValidationResult,
    ParsedStkAccessReport,
    ParsedStkAerReport,
    build_stk_validation_bundle,
    compare_access_intervals,
    compare_aer_samples,
    parse_stk_access_report,
    parse_stk_aer_report,
)
from app.models.geometry import TargetGeometry
from app.models.imaging import ImagingMode
from app.models.request import ObservationRequest


class StkValidationService:
    """Fasada eksportu przypadku i walidacji raportów STK."""

    def build_bundle(
        self,
        *,
        request: ObservationRequest,
        satellite: TrackedSatellite,
        mode: ImagingMode,
        windows: tuple[GeometricAccessWindow, ...],
        propagation_step_s: float,
    ) -> bytes:
        return build_stk_validation_bundle(
            request=request,
            satellite=satellite,
            mode=mode,
            windows=windows,
            propagation_step_s=propagation_step_s,
        )

    def parse_access(self, payload: bytes | str) -> ParsedStkAccessReport:
        return parse_stk_access_report(payload)

    def validate_access(
        self,
        *,
        model_windows: tuple[GeometricAccessWindow, ...],
        report: ParsedStkAccessReport,
        tolerance_s: float,
    ) -> AccessValidationResult:
        return compare_access_intervals(
            model_windows,
            report.intervals,
            tolerance_s=tolerance_s,
        )

    def parse_aer(self, payload: bytes | str) -> ParsedStkAerReport:
        return parse_stk_aer_report(payload)

    def validate_aer(
        self,
        *,
        model_windows: tuple[GeometricAccessWindow, ...],
        report: ParsedStkAerReport,
        geometry: TargetGeometry,
        time_tolerance_s: float,
    ) -> AerValidationResult:
        return compare_aer_samples(
            model_windows,
            report.samples,
            geometry=geometry,
            time_tolerance_s=time_tolerance_s,
        )
