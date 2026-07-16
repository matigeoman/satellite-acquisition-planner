from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Iterable

from app.catalogs import PLEIADES_NEO_PUBLIC_PROFILE
from app.integrations.opportunities.public_builder import (
    PublicOpportunityBuildResult,
    calculate_public_quality_score,
)
from app.integrations.weather import (
    CloudAggregation,
    CloudAssessmentService,
    CloudPointValue,
    WindowCloudAssessment,
    build_weather_sampling_locations,
    interpolate_forecast,
)
from app.models.enums import SensorType
from app.models.opportunity import AcquisitionOpportunity
from app.models.request import ObservationRequest


CLOUD_INFEASIBILITY_REASON = (
    "Prognozowane zachmurzenie przekracza limit zlecenia"
)


@dataclass(frozen=True, slots=True)
class OpportunityWeatherChange:
    """Zmiana prognozy i wykonalności jednej okazji optycznej."""

    opportunity_id: str
    request_id: str
    satellite_id: str
    start_utc: datetime
    previous_cloud_cover: float
    refreshed_cloud_cover: float
    previous_is_feasible: bool
    refreshed_is_feasible: bool
    preserved_by_freeze: bool

    @property
    def cloud_delta(self) -> float:
        return self.refreshed_cloud_cover - self.previous_cloud_cover

    @property
    def feasibility_changed(self) -> bool:
        return self.previous_is_feasible != self.refreshed_is_feasible


@dataclass(frozen=True, slots=True)
class PublicWeatherRefreshResult:
    """Wynik aktualizacji pogody dla jednego zlecenia."""

    build_result: PublicOpportunityBuildResult
    changes: tuple[OpportunityWeatherChange, ...]
    refreshed_opportunity_count: int
    preserved_opportunity_count: int
    warning: str | None = None

    @property
    def became_feasible_count(self) -> int:
        return sum(
            not change.previous_is_feasible and change.refreshed_is_feasible
            for change in self.changes
        )

    @property
    def became_infeasible_count(self) -> int:
        return sum(
            change.previous_is_feasible and not change.refreshed_is_feasible
            for change in self.changes
        )


def _normalize_utc(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} musi zawierać strefę czasową")
    return value.astimezone(timezone.utc)


def _opportunity_midpoint(opportunity: AcquisitionOpportunity) -> datetime:
    return opportunity.start_utc + (
        opportunity.end_utc - opportunity.start_utc
    ) / 2


def _window_id_from_opportunity_id(opportunity_id: str) -> str:
    prefix = "OPP-PUBLIC-"
    if opportunity_id.startswith(prefix):
        return f"ACCESS-{opportunity_id.removeprefix(prefix)}"
    return f"ACCESS-{opportunity_id.removeprefix('OPP-')}"


def _percentile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Nie można agregować pustego zbioru prognoz")
    if len(ordered) == 1:
        return ordered[0]
    rank = quantile * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def _aggregate(values: list[float], aggregation: CloudAggregation) -> float:
    if not values:
        raise ValueError("Nie można agregować pustego zbioru prognoz")
    if aggregation == CloudAggregation.MAXIMUM:
        return max(values)
    if aggregation == CloudAggregation.PERCENTILE_75:
        return _percentile(values, 0.75)
    return mean(values)


def _assessment_for_opportunity(
    *,
    request: ObservationRequest,
    opportunity: AcquisitionOpportunity,
    forecasts,
    aggregation: CloudAggregation,
    source_url: str,
    from_cache: bool,
    is_stale: bool,
    warning: str | None,
) -> WindowCloudAssessment:
    timestamp = _opportunity_midpoint(opportunity)
    point_values = tuple(
        interpolate_forecast(forecast, timestamp)
        for forecast in forecasts
    )
    total = _aggregate(
        [value.cloud_cover_percent for value in point_values],
        aggregation,
    )
    max_allowed = float(request.max_cloud_cover or 0.0) * 100.0
    return WindowCloudAssessment(
        window_id=_window_id_from_opportunity_id(opportunity.opportunity_id),
        assessed_at_utc=timestamp,
        aggregation=aggregation,
        cloud_cover_percent=total,
        cloud_cover_low_percent=_aggregate(
            [value.cloud_cover_low_percent for value in point_values],
            aggregation,
        ),
        cloud_cover_mid_percent=_aggregate(
            [value.cloud_cover_mid_percent for value in point_values],
            aggregation,
        ),
        cloud_cover_high_percent=_aggregate(
            [value.cloud_cover_high_percent for value in point_values],
            aggregation,
        ),
        point_values=point_values,
        max_allowed_cloud_cover_percent=max_allowed,
        is_cloud_feasible=total <= max_allowed,
        source_url=source_url,
        from_cache=from_cache,
        is_stale=is_stale,
        warning=warning,
    )


def _updated_opportunity(
    *,
    opportunity: AcquisitionOpportunity,
    assessment: WindowCloudAssessment,
    refreshed_at_utc: datetime,
) -> AcquisitionOpportunity:
    mode = PLEIADES_NEO_PUBLIC_PROFILE.get_mode(opportunity.mode_id)
    reasons = [
        reason
        for reason in opportunity.infeasibility_reasons
        if reason != CLOUD_INFEASIBILITY_REASON
    ]
    if not assessment.is_cloud_feasible:
        reasons.append(CLOUD_INFEASIBILITY_REASON)

    cloud_cover = assessment.cloud_cover_fraction
    quality = calculate_public_quality_score(
        mode=mode,
        coverage_ratio=opportunity.coverage_ratio,
        off_nadir_angle_deg=opportunity.off_nadir_angle_deg,
        cloud_cover=cloud_cover,
        sun_elevation_deg=opportunity.sun_elevation_deg,
    )
    source_reference = (
        "CelesTrak GP/OMM + SGP4 + publiczny profil sensora; "
        "Open-Meteo hourly cloud forecast refreshed "
        f"{refreshed_at_utc.isoformat()}"
    )
    return opportunity.model_copy(
        update={
            "cloud_cover": cloud_cover,
            "quality_score": quality,
            "is_feasible": not reasons,
            "infeasibility_reasons": reasons,
            "source_reference": source_reference,
        }
    )


class PublicOpportunityWeatherRefreshService:
    """Odświeża pogodę przyszłych okazji EO bez zmiany ich geometrii."""

    def __init__(self, *, cloud_service: CloudAssessmentService) -> None:
        self.cloud_service = cloud_service

    def refresh_build(
        self,
        *,
        request: ObservationRequest,
        build_result: PublicOpportunityBuildResult,
        frozen_until_utc: datetime,
        aggregation: CloudAggregation = CloudAggregation.MAXIMUM,
        maximum_sampling_points: int = 9,
        allow_network: bool = True,
    ) -> PublicWeatherRefreshResult:
        if build_result.request_id != request.request_id:
            raise ValueError("Wynik okazji jest niezgodny ze zleceniem")
        if SensorType.OPTICAL not in request.requested_sensor_types:
            return PublicWeatherRefreshResult(
                build_result=build_result,
                changes=(),
                refreshed_opportunity_count=0,
                preserved_opportunity_count=len(build_result.opportunities),
            )
        if request.max_cloud_cover is None:
            raise ValueError("Zlecenie EO wymaga max_cloud_cover")

        frozen_until = _normalize_utc(
            frozen_until_utc,
            field_name="frozen_until_utc",
        )
        optical_to_refresh = tuple(
            opportunity
            for opportunity in build_result.opportunities
            if opportunity.sensor_type == SensorType.OPTICAL
            and opportunity.start_utc >= frozen_until
        )
        if not optical_to_refresh:
            return PublicWeatherRefreshResult(
                build_result=build_result,
                changes=(),
                refreshed_opportunity_count=0,
                preserved_opportunity_count=len(build_result.opportunities),
            )

        locations = build_weather_sampling_locations(
            request.geometry,
            maximum_points=maximum_sampling_points,
        )
        timestamps = [
            _opportunity_midpoint(opportunity)
            for opportunity in optical_to_refresh
        ]
        forecast = self.cloud_service.client.fetch_cloud_forecast(
            locations,
            start_utc=min(timestamps) - timedelta(hours=1),
            end_utc=max(timestamps) + timedelta(hours=1),
            allow_network=allow_network,
        )
        refreshed_at = datetime.now(timezone.utc)
        refresh_ids = {
            opportunity.opportunity_id for opportunity in optical_to_refresh
        }
        old_assessments = {
            assessment.window_id: assessment
            for assessment in build_result.weather_assessments
        }
        new_assessments: list[WindowCloudAssessment] = []
        updated_opportunities: list[AcquisitionOpportunity] = []
        changes: list[OpportunityWeatherChange] = []

        for opportunity in build_result.opportunities:
            window_id = _window_id_from_opportunity_id(
                opportunity.opportunity_id
            )
            if opportunity.opportunity_id not in refresh_ids:
                updated_opportunities.append(opportunity)
                old_assessment = old_assessments.get(window_id)
                if old_assessment is not None:
                    new_assessments.append(old_assessment)
                continue

            assessment = _assessment_for_opportunity(
                request=request,
                opportunity=opportunity,
                forecasts=forecast.forecasts,
                aggregation=aggregation,
                source_url=forecast.request_url,
                from_cache=forecast.from_cache,
                is_stale=forecast.is_stale,
                warning=forecast.warning,
            )
            updated = _updated_opportunity(
                opportunity=opportunity,
                assessment=assessment,
                refreshed_at_utc=refreshed_at,
            )
            updated_opportunities.append(updated)
            new_assessments.append(assessment)
            changes.append(
                OpportunityWeatherChange(
                    opportunity_id=opportunity.opportunity_id,
                    request_id=request.request_id,
                    satellite_id=opportunity.satellite_id,
                    start_utc=opportunity.start_utc,
                    previous_cloud_cover=float(opportunity.cloud_cover or 0.0),
                    refreshed_cloud_cover=float(updated.cloud_cover or 0.0),
                    previous_is_feasible=opportunity.is_feasible,
                    refreshed_is_feasible=updated.is_feasible,
                    preserved_by_freeze=False,
                )
            )

        warnings = list(build_result.warnings)
        if forecast.warning and forecast.warning not in warnings:
            warnings.append(forecast.warning)
        updated_opportunities.sort(
            key=lambda opportunity: (
                opportunity.start_utc,
                opportunity.satellite_id,
                opportunity.mode_id,
            )
        )
        new_assessments.sort(
            key=lambda assessment: (
                assessment.assessed_at_utc,
                assessment.window_id,
            )
        )
        refreshed_build = PublicOpportunityBuildResult(
            request_id=request.request_id,
            generated_at_utc=refreshed_at,
            opportunities=tuple(updated_opportunities),
            weather_assessments=tuple(new_assessments),
            skipped_window_ids=build_result.skipped_window_ids,
            warnings=tuple(warnings),
        )
        return PublicWeatherRefreshResult(
            build_result=refreshed_build,
            changes=tuple(changes),
            refreshed_opportunity_count=len(changes),
            preserved_opportunity_count=(
                len(build_result.opportunities) - len(changes)
            ),
            warning=forecast.warning,
        )


__all__ = [
    "CLOUD_INFEASIBILITY_REASON",
    "OpportunityWeatherChange",
    "PublicOpportunityWeatherRefreshService",
    "PublicWeatherRefreshResult",
]
