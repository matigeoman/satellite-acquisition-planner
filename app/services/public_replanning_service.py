from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.integrations.opportunities import (
    PublicOpportunityBuildResult,
    PublicOpportunityWeatherRefreshService,
)
from app.integrations.weather import CloudAggregation
from app.models.request import ObservationRequest
from app.services.contracts.planning import PlanningOptions, PlanningResult
from app.services.contracts.public_replanning import PublicReplanningResult
from app.services.public_scenario_service import PublicScenarioService
from app.services.replanning_service import (
    DEFAULT_FREEZE_DURATION,
    ReplanningService,
)


class PublicReplanningService:
    """Aktualizuje pogodę i przeplanowuje publiczny harmonogram."""

    def __init__(
        self,
        *,
        scenario_service: PublicScenarioService,
        replanning_service: ReplanningService,
        weather_refresh_service: PublicOpportunityWeatherRefreshService,
    ) -> None:
        self.scenario_service = scenario_service
        self.replanning_service = replanning_service
        self.weather_refresh_service = weather_refresh_service

    def run(
        self,
        *,
        requests: list[ObservationRequest],
        builds_by_request_id: dict[str, PublicOpportunityBuildResult],
        previous_planning_result: PlanningResult,
        options: PlanningOptions,
        replan_at_utc: datetime,
        freeze_duration: timedelta = DEFAULT_FREEZE_DURATION,
        aggregation: CloudAggregation = CloudAggregation.MAXIMUM,
        maximum_sampling_points: int = 9,
        allow_network: bool = True,
    ) -> PublicReplanningResult:
        if previous_planning_result.scenario.scenario_id != "PUBLIC":
            raise ValueError(
                "Poprzedni wynik nie pochodzi ze scenariusza publicznego"
            )
        replan_at = self._normalize_utc(replan_at_utc)
        if freeze_duration <= timedelta(0):
            raise ValueError("freeze_duration musi być większe od zera")

        previous_scenario = previous_planning_result.scenario
        horizon_start = previous_scenario.request_set.horizon_start_utc
        horizon_end = previous_scenario.request_set.horizon_end_utc
        if not horizon_start <= replan_at < horizon_end:
            raise ValueError(
                "replan_at_utc musi znajdować się wewnątrz horyzontu "
                "poprzedniego harmonogramu"
            )
        frozen_until = min(replan_at + freeze_duration, horizon_end)
        requests_by_id = {request.request_id: request for request in requests}
        required_request_ids = {
            request.request_id
            for request in previous_scenario.request_set.requests
        }
        missing_requests = required_request_ids - requests_by_id.keys()
        if missing_requests:
            raise ValueError(
                "Brak zleceń wymaganych przez poprzedni harmonogram: "
                + ", ".join(sorted(missing_requests))
            )

        additional_request_ids = {
            request_id
            for request_id in builds_by_request_id
            if request_id in requests_by_id
            and horizon_start
            <= requests_by_id[request_id].earliest_start_utc
            < requests_by_id[request_id].latest_end_utc
            <= horizon_end
        } - required_request_ids
        included_request_ids = required_request_ids | additional_request_ids

        refreshed_builds: dict[str, PublicOpportunityBuildResult] = {}
        weather_changes = []
        warnings: list[str] = []
        if additional_request_ids:
            warnings.append(
                "Do przeplanowania dołączono nowe zlecenia posiadające "
                "okazje i mieszczące się w poprzednim horyzoncie: "
                + ", ".join(sorted(additional_request_ids))
            )
        for request_id in sorted(included_request_ids):
            build = builds_by_request_id.get(request_id)
            if build is None:
                raise ValueError(
                    "Brak okazji publicznych dla zlecenia " f"{request_id}"
                )
            refresh = self.weather_refresh_service.refresh_build(
                request=requests_by_id[request_id],
                build_result=build,
                frozen_until_utc=frozen_until,
                aggregation=aggregation,
                maximum_sampling_points=maximum_sampling_points,
                allow_network=allow_network,
            )
            refreshed_builds[request_id] = refresh.build_result
            weather_changes.extend(refresh.changes)
            if refresh.warning and refresh.warning not in warnings:
                warnings.append(refresh.warning)

        refreshed_scenario = self.scenario_service.build(
            requests=[
                requests_by_id[request_id]
                for request_id in sorted(included_request_ids)
            ],
            builds_by_request_id=refreshed_builds,
        )
        replanning_result = self.replanning_service.run(
            scenario=refreshed_scenario,
            previous_schedule=previous_planning_result.schedule,
            options=options,
            replan_at_utc=replan_at,
            freeze_duration=freeze_duration,
            schedule_name=(
                "Publiczne orbity i pogoda — dynamiczne przeplanowanie"
            ),
        )
        return PublicReplanningResult(
            replanning_result=replanning_result,
            refreshed_builds_by_request_id=refreshed_builds,
            weather_changes=tuple(weather_changes),
            refreshed_at_utc=datetime.now(timezone.utc),
            warnings=tuple(warnings),
        )

    @staticmethod
    def _normalize_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("replan_at_utc musi zawierać strefę czasową")
        return value.astimezone(timezone.utc)


__all__ = ["PublicReplanningService"]
