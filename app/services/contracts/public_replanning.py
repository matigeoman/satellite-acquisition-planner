from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.integrations.opportunities import (
    OpportunityWeatherChange,
    PublicOpportunityBuildResult,
)
from app.services.contracts.replanning import ReplanningResult


@dataclass(frozen=True, slots=True)
class PublicReplanningResult:
    """Wynik aktualizacji pogody i przeplanowania scenariusza publicznego."""

    replanning_result: ReplanningResult
    refreshed_builds_by_request_id: dict[
        str,
        PublicOpportunityBuildResult,
    ]
    weather_changes: tuple[OpportunityWeatherChange, ...]
    refreshed_at_utc: datetime
    warnings: tuple[str, ...] = ()

    @property
    def schedule(self):
        return self.replanning_result.schedule

    @property
    def planning_result(self):
        return self.replanning_result.planning_result

    @property
    def refreshed_opportunity_count(self) -> int:
        return len(self.weather_changes)

    @property
    def cloud_changed_count(self) -> int:
        return sum(abs(change.cloud_delta) > 1e-9 for change in self.weather_changes)

    @property
    def became_feasible_count(self) -> int:
        return sum(
            not change.previous_is_feasible and change.refreshed_is_feasible
            for change in self.weather_changes
        )

    @property
    def became_infeasible_count(self) -> int:
        return sum(
            change.previous_is_feasible and not change.refreshed_is_feasible
            for change in self.weather_changes
        )
