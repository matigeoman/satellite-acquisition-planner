from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.catalogs import (
    ICEYE_PUBLIC_PROFILE,
    PLEIADES_NEO_PUBLIC_PROFILE,
    PublicMissionProfile,
)
from app.integrations.access import AccessCalculationResult, GeometricAccessWindow
from app.integrations.weather import WindowCloudAssessment
from app.models.enums import OpportunitySourceType, SensorType
from app.models.imaging import ImagingMode
from app.models.opportunity import AcquisitionOpportunity
from app.models.request import ObservationRequest


@dataclass(frozen=True, slots=True)
class PublicOpportunityBuildResult:
    """Wynik konwersji okien publicznych na okazje planistyczne."""

    request_id: str
    generated_at_utc: datetime
    opportunities: tuple[AcquisitionOpportunity, ...]
    weather_assessments: tuple[WindowCloudAssessment, ...]
    skipped_window_ids: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def feasible_opportunities(self) -> tuple[AcquisitionOpportunity, ...]:
        return tuple(
            opportunity
            for opportunity in self.opportunities
            if opportunity.is_feasible
        )

    @property
    def optical_opportunities(self) -> tuple[AcquisitionOpportunity, ...]:
        return tuple(
            opportunity
            for opportunity in self.opportunities
            if opportunity.sensor_type == SensorType.OPTICAL
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "generated_at_utc": self.generated_at_utc.isoformat(),
            "opportunities": [
                opportunity.model_dump(mode="json")
                for opportunity in self.opportunities
            ],
            "weather_assessments": [
                assessment.to_dict()
                for assessment in self.weather_assessments
            ],
            "skipped_window_ids": list(self.skipped_window_ids),
            "warnings": list(self.warnings),
        }


def _profile_for_window(window: GeometricAccessWindow) -> PublicMissionProfile:
    if window.sensor_type == SensorType.SAR:
        return ICEYE_PUBLIC_PROFILE
    return PLEIADES_NEO_PUBLIC_PROFILE


def _mode_for_window(window: GeometricAccessWindow) -> ImagingMode:
    return _profile_for_window(window).get_mode(window.mode_id)


def _peak_point(window: GeometricAccessWindow):
    if not window.path:
        raise ValueError(f"Okno {window.window_id} nie zawiera śladu")
    return min(
        window.path,
        key=lambda point: abs(
            (point.timestamp_utc - window.peak_utc).total_seconds()
        ),
    )


def _acquisition_interval(
    window: GeometricAccessWindow,
    mode: ImagingMode,
) -> tuple[datetime, datetime] | None:
    duration_s = mode.min_acquisition_duration_s
    if window.duration_s + 1e-9 < duration_s:
        return None
    half = timedelta(seconds=duration_s / 2.0)
    start = window.peak_utc - half
    end = window.peak_utc + half
    if start < window.start_utc:
        start = window.start_utc
        end = start + timedelta(seconds=duration_s)
    if end > window.end_utc:
        end = window.end_utc
        start = end - timedelta(seconds=duration_s)
    if start < window.start_utc or end > window.end_utc or start >= end:
        return None
    return start, end


def _quality_score(
    *,
    mode: ImagingMode,
    coverage_ratio: float,
    off_nadir_angle_deg: float,
    cloud_cover: float | None,
    sun_elevation_deg: float | None,
) -> float:
    angle_factor = max(0.2, 1.0 - off_nadir_angle_deg / 90.0)
    weather_factor = 1.0
    if mode.sensor_type == SensorType.OPTICAL:
        if cloud_cover is None or sun_elevation_deg is None:
            return 0.0
        weather_factor = max(0.1, 1.0 - cloud_cover) * max(
            0.2,
            min(1.0, sun_elevation_deg / 30.0),
        )
    return min(
        1.0,
        max(
            0.0,
            mode.quality_factor
            * coverage_ratio
            * angle_factor
            * weather_factor,
        ),
    )


def _opportunity_id(window: GeometricAccessWindow) -> str:
    suffix = window.window_id.removeprefix("ACCESS-")
    return f"OPP-PUBLIC-{suffix}"


def build_public_opportunities(
    *,
    request: ObservationRequest,
    access_result: AccessCalculationResult,
    weather_assessments: tuple[WindowCloudAssessment, ...] = (),
) -> PublicOpportunityBuildResult:
    """Konwertuje okna na pełne AcquisitionOpportunity dla solverów."""

    if request.request_id != access_result.request_id:
        raise ValueError("Zlecenie jest niezgodne z wynikiem okien dostępu")

    assessments_by_window = {
        assessment.window_id: assessment
        for assessment in weather_assessments
    }
    opportunities: list[AcquisitionOpportunity] = []
    skipped: list[str] = []
    warnings: list[str] = []

    for window in access_result.windows:
        profile = _profile_for_window(window)
        mode = _mode_for_window(window)
        interval = _acquisition_interval(window, mode)
        if interval is None:
            skipped.append(window.window_id)
            continue
        start_utc, end_utc = interval
        peak = _peak_point(window)
        cloud_cover: float | None = None
        sun_elevation: float | None = None
        incidence: float | None = peak.incidence_angle_deg
        infeasibility_reasons: list[str] = []
        source_reference = (
            "CelesTrak GP/OMM + SGP4 + publiczny profil sensora"
        )

        if window.sensor_type == SensorType.OPTICAL:
            incidence = None
            sun_elevation = peak.sun_elevation_deg
            assessment = assessments_by_window.get(window.window_id)
            if assessment is None:
                skipped.append(window.window_id)
                continue
            cloud_cover = assessment.cloud_cover_fraction
            source_reference += "; Open-Meteo hourly cloud forecast"
            if not assessment.is_cloud_feasible:
                infeasibility_reasons.append(
                    "Prognozowane zachmurzenie przekracza limit zlecenia"
                )
            if assessment.warning and assessment.warning not in warnings:
                warnings.append(assessment.warning)

        quality = _quality_score(
            mode=mode,
            coverage_ratio=window.coverage_ratio,
            off_nadir_angle_deg=peak.off_nadir_angle_deg,
            cloud_cover=cloud_cover,
            sun_elevation_deg=sun_elevation,
        )
        duration_s = (end_utc - start_utc).total_seconds()
        notes = (
            f"Źródłowe okno: {window.window_id}. Obiekt publiczny: "
            f"{window.satellite_name}; NORAD {window.norad_cat_id}. "
            "Okazja ma charakter modelowy i nie potwierdza dostępności "
            "komercyjnego taskingu operatora."
        )
        opportunities.append(
            AcquisitionOpportunity(
                opportunity_id=_opportunity_id(window),
                request_id=request.request_id,
                satellite_id=window.satellite_id,
                sensor_id=profile.sensor.sensor_id,
                mode_id=mode.mode_id,
                sensor_type=mode.sensor_type,
                start_utc=start_utc,
                end_utc=end_utc,
                observation_side=window.observation_side,
                off_nadir_angle_deg=peak.off_nadir_angle_deg,
                incidence_angle_deg=incidence,
                cloud_cover=cloud_cover,
                sun_elevation_deg=sun_elevation,
                coverage_ratio=window.coverage_ratio,
                quality_score=quality,
                estimated_data_volume_mb=duration_s * mode.data_rate_mb_s,
                is_feasible=not infeasibility_reasons,
                infeasibility_reasons=infeasibility_reasons,
                source_type=OpportunitySourceType.PUBLIC_DATA,
                source_reference=source_reference,
                notes=notes,
            )
        )

    if skipped:
        warnings.append(
            "Pominięto okna bez kompletnej prognozy EO albo zbyt krótkie "
            "dla minimalnego czasu trybu."
        )
    opportunities.sort(
        key=lambda opportunity: (
            opportunity.start_utc,
            opportunity.satellite_id,
            opportunity.mode_id,
        )
    )
    return PublicOpportunityBuildResult(
        request_id=request.request_id,
        generated_at_utc=datetime.now(timezone.utc),
        opportunities=tuple(opportunities),
        weather_assessments=weather_assessments,
        skipped_window_ids=tuple(skipped),
        warnings=tuple(warnings),
    )
