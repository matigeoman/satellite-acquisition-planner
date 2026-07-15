from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.models.enums import SensorType
from app.models.opportunity import AcquisitionOpportunity
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request import ObservationRequest
from app.models.request_set import ObservationRequestSet
from app.services.planning_service import PlanningOptions
from app.services.replanning_service import (
    DEFAULT_FREEZE_DURATION,
    ReplanningResult,
    ReplanningService,
)
from app.services.scenario_service import (
    LoadedScenario,
    ScenarioDefinition,
)


@dataclass(frozen=True)
class SatelliteOutage:
    """Czasowa utrata dostępności satelity od wskazanego momentu."""

    satellite_id: str
    effective_from_utc: datetime
    reason: str = "Awaria platformy satelitarnej."

    def __post_init__(self) -> None:
        satellite_id = self.satellite_id.strip().upper()

        if not re.fullmatch(r"(SAR|EO)-[0-9]{2}", satellite_id):
            raise ValueError(
                f"Niepoprawny satellite_id awarii: {self.satellite_id}"
            )

        effective_from = _normalize_utc(
            self.effective_from_utc,
            field_name="effective_from_utc",
        )
        reason = _normalize_reason(self.reason, field_name="reason")

        object.__setattr__(self, "satellite_id", satellite_id)
        object.__setattr__(self, "effective_from_utc", effective_from)
        object.__setattr__(self, "reason", reason)


@dataclass(frozen=True)
class CloudCoverUpdate:
    """Aktualizacja prognozy zachmurzenia dla okazji optycznej."""

    opportunity_id: str
    cloud_cover: float
    reason: str = "Zaktualizowana prognoza zachmurzenia."

    def __post_init__(self) -> None:
        opportunity_id = self.opportunity_id.strip().upper()

        if not re.fullmatch(r"OPP-[A-Z0-9-]+", opportunity_id):
            raise ValueError(
                "Niepoprawny opportunity_id aktualizacji pogody: "
                f"{self.opportunity_id}"
            )

        cloud_cover = float(self.cloud_cover)

        if not 0.0 <= cloud_cover <= 1.0:
            raise ValueError(
                "cloud_cover musi należeć do zakresu [0, 1]"
            )

        reason = _normalize_reason(self.reason, field_name="reason")

        object.__setattr__(self, "opportunity_id", opportunity_id)
        object.__setattr__(self, "cloud_cover", cloud_cover)
        object.__setattr__(self, "reason", reason)


@dataclass(frozen=True)
class UrgentRequestPackage:
    """Nowe pilne zlecenie wraz z dostępnymi okazjami."""

    request: ObservationRequest
    opportunities: tuple[AcquisitionOpportunity, ...]

    def __post_init__(self) -> None:
        opportunities = tuple(self.opportunities)

        if not opportunities:
            raise ValueError(
                "Pilne zlecenie musi posiadać co najmniej jedną okazję"
            )

        opportunity_ids = [
            opportunity.opportunity_id
            for opportunity in opportunities
        ]

        if len(opportunity_ids) != len(set(opportunity_ids)):
            raise ValueError(
                "Okazje pilnego zlecenia zawierają powtórzone identyfikatory"
            )

        for opportunity in opportunities:
            if opportunity.request_id != self.request.request_id:
                raise ValueError(
                    f"Okazja {opportunity.opportunity_id} nie należy do "
                    f"zlecenia {self.request.request_id}"
                )

        object.__setattr__(self, "opportunities", opportunities)


@dataclass(frozen=True)
class DisruptionPlan:
    """Zestaw zdarzeń zmieniających dane wejściowe planowania."""

    plan_id: str
    occurred_at_utc: datetime
    satellite_outages: tuple[SatelliteOutage, ...] = ()
    cloud_cover_updates: tuple[CloudCoverUpdate, ...] = ()
    urgent_requests: tuple[UrgentRequestPackage, ...] = ()
    notes: str | None = None

    def __post_init__(self) -> None:
        plan_id = self.plan_id.strip().upper()

        if not re.fullmatch(r"DISRUPTION-[A-Z0-9-]+", plan_id):
            raise ValueError(f"Niepoprawny plan_id: {self.plan_id}")

        occurred_at = _normalize_utc(
            self.occurred_at_utc,
            field_name="occurred_at_utc",
        )
        outages = tuple(self.satellite_outages)
        weather_updates = tuple(self.cloud_cover_updates)
        urgent_requests = tuple(self.urgent_requests)

        _ensure_unique(
            [outage.satellite_id for outage in outages],
            "satellite_id awarii",
        )
        _ensure_unique(
            [update.opportunity_id for update in weather_updates],
            "opportunity_id aktualizacji pogody",
        )
        _ensure_unique(
            [package.request.request_id for package in urgent_requests],
            "request_id pilnego zlecenia",
        )

        all_urgent_opportunity_ids = [
            opportunity.opportunity_id
            for package in urgent_requests
            for opportunity in package.opportunities
        ]
        _ensure_unique(
            all_urgent_opportunity_ids,
            "opportunity_id pilnego zlecenia",
        )

        for outage in outages:
            if outage.effective_from_utc < occurred_at:
                raise ValueError(
                    "Awaria nie może rozpoczynać się przed occurred_at_utc"
                )

        notes = self.notes.strip() if self.notes is not None else None

        if notes == "":
            notes = None

        if notes is not None and len(notes) > 2000:
            raise ValueError("notes nie może przekraczać 2000 znaków")

        object.__setattr__(self, "plan_id", plan_id)
        object.__setattr__(self, "occurred_at_utc", occurred_at)
        object.__setattr__(self, "satellite_outages", outages)
        object.__setattr__(self, "cloud_cover_updates", weather_updates)
        object.__setattr__(self, "urgent_requests", urgent_requests)
        object.__setattr__(self, "notes", notes)


@dataclass(frozen=True)
class DisruptionApplicationResult:
    """Scenariusz po zastosowaniu zakłóceń i lista zmian danych."""

    previous_scenario: LoadedScenario
    disrupted_scenario: LoadedScenario
    plan: DisruptionPlan
    outage_invalidated_opportunity_ids: tuple[str, ...]
    weather_invalidated_opportunity_ids: tuple[str, ...]
    added_request_ids: tuple[str, ...]
    added_opportunity_ids: tuple[str, ...]

    @property
    def invalidated_opportunity_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                set(self.outage_invalidated_opportunity_ids)
                | set(self.weather_invalidated_opportunity_ids)
            )
        )

    @property
    def invalidated_opportunity_count(self) -> int:
        return len(self.invalidated_opportunity_ids)


@dataclass(frozen=True)
class DisruptionReplanningResult:
    """Wynik zastosowania zakłóceń i dynamicznego przeplanowania."""

    application_result: DisruptionApplicationResult
    replanning_result: ReplanningResult

    @property
    def schedule(self):
        return self.replanning_result.schedule

    @property
    def analysis(self):
        return self.replanning_result.analysis

    @property
    def solver_status(self) -> str:
        return self.replanning_result.solver_status

    @property
    def previous_schedule(self):
        return self.replanning_result.previous_schedule

    @property
    def added_opportunity_ids(self) -> list[str]:
        return self.replanning_result.added_opportunity_ids

    @property
    def removed_opportunity_ids(self) -> list[str]:
        return self.replanning_result.removed_opportunity_ids

    @property
    def unchanged_opportunity_ids(self) -> list[str]:
        return (
            self.replanning_result
            .unchanged_replannable_opportunity_ids
        )

    @property
    def previous_objective_value(self) -> float:
        return float(self.previous_schedule.objective_value or 0.0)

    @property
    def new_objective_value(self) -> float:
        return float(self.schedule.objective_value or 0.0)

    @property
    def objective_delta(self) -> float:
        return self.new_objective_value - self.previous_objective_value

    @property
    def invalidated_previous_selection_ids(self) -> list[str]:
        previous_future_ids = (
            self.replanning_result.previous_replannable_opportunity_ids
        )

        return sorted(
            previous_future_ids
            & set(
                self.application_result.invalidated_opportunity_ids
            )
        )


class DisruptionService:
    """Stosuje zdarzenia operacyjne do scenariusza planistycznego."""

    def apply(
        self,
        *,
        scenario: LoadedScenario,
        plan: DisruptionPlan,
    ) -> DisruptionApplicationResult:
        self._validate_plan_horizon(scenario=scenario, plan=plan)

        requests = list(scenario.request_set.requests)
        opportunities = list(scenario.opportunity_set.opportunities)

        existing_request_ids = {
            request.request_id
            for request in requests
        }
        existing_opportunity_ids = {
            opportunity.opportunity_id
            for opportunity in opportunities
        }

        added_request_ids: list[str] = []
        added_opportunity_ids: list[str] = []

        for package in plan.urgent_requests:
            request_id = package.request.request_id

            if request_id in existing_request_ids:
                raise ValueError(
                    f"Pilne zlecenie już istnieje: {request_id}"
                )

            duplicate_opportunity_ids = sorted(
                existing_opportunity_ids
                & {
                    opportunity.opportunity_id
                    for opportunity in package.opportunities
                }
            )

            if duplicate_opportunity_ids:
                raise ValueError(
                    "Okazje pilnego zlecenia już istnieją: "
                    + ", ".join(duplicate_opportunity_ids)
                )

            requests.append(package.request)
            opportunities.extend(package.opportunities)
            existing_request_ids.add(request_id)
            existing_opportunity_ids.update(
                opportunity.opportunity_id
                for opportunity in package.opportunities
            )
            added_request_ids.append(request_id)
            added_opportunity_ids.extend(
                opportunity.opportunity_id
                for opportunity in package.opportunities
            )

        request_by_id = {
            request.request_id: request
            for request in requests
        }
        satellite_ids = {
            satellite.satellite_id
            for satellite in scenario.catalog.satellites
        }

        outage_invalidated: list[str] = []

        for outage in plan.satellite_outages:
            if outage.satellite_id not in satellite_ids:
                raise KeyError(
                    f"Nie znaleziono satelity: {outage.satellite_id}"
                )

            updated_opportunities: list[AcquisitionOpportunity] = []

            for opportunity in opportunities:
                affected = (
                    opportunity.satellite_id == outage.satellite_id
                    and opportunity.start_utc >= outage.effective_from_utc
                )

                if not affected:
                    updated_opportunities.append(opportunity)
                    continue

                reasons = _append_unique_reason(
                    opportunity.infeasibility_reasons,
                    outage.reason,
                )

                if opportunity.is_feasible:
                    outage_invalidated.append(
                        opportunity.opportunity_id
                    )

                updated_opportunities.append(
                    _validated_opportunity_copy(
                        opportunity,
                        {
                            "is_feasible": False,
                            "infeasibility_reasons": reasons,
                        },
                    )
                )

            opportunities = updated_opportunities

        opportunity_index = {
            opportunity.opportunity_id: index
            for index, opportunity in enumerate(opportunities)
        }
        weather_invalidated: list[str] = []

        for update in plan.cloud_cover_updates:
            try:
                index = opportunity_index[update.opportunity_id]
            except KeyError as error:
                raise KeyError(
                    f"Nie znaleziono okazji: {update.opportunity_id}"
                ) from error

            opportunity = opportunities[index]

            if opportunity.sensor_type != SensorType.OPTICAL:
                raise ValueError(
                    "Aktualizacja zachmurzenia może dotyczyć wyłącznie "
                    f"okazji optycznej: {opportunity.opportunity_id}"
                )

            request = request_by_id[opportunity.request_id]
            exceeds_limit = (
                request.max_cloud_cover is not None
                and update.cloud_cover > request.max_cloud_cover
            )

            reasons = list(opportunity.infeasibility_reasons)
            is_feasible = opportunity.is_feasible

            if exceeds_limit:
                reasons = _append_unique_reason(reasons, update.reason)

                if opportunity.is_feasible:
                    weather_invalidated.append(
                        opportunity.opportunity_id
                    )

                is_feasible = False

            opportunities[index] = _validated_opportunity_copy(
                opportunity,
                {
                    "cloud_cover": update.cloud_cover,
                    "is_feasible": is_feasible,
                    "infeasibility_reasons": reasons,
                },
            )

        request_set = _validated_request_set_copy(
            scenario.request_set,
            {
                "requests": requests,
                "generated_at_utc": plan.occurred_at_utc,
                "notes": _append_note(
                    scenario.request_set.notes,
                    f"Zastosowano plan {plan.plan_id}.",
                ),
            },
        )

        opportunity_set = _validated_opportunity_set_copy(
            scenario.opportunity_set,
            {
                "opportunities": opportunities,
                "generated_at_utc": plan.occurred_at_utc,
                "notes": _append_note(
                    scenario.opportunity_set.notes,
                    f"Zastosowano plan {plan.plan_id}.",
                ),
            },
        )

        opportunity_set.validate_against(
            scenario.catalog,
            request_set,
        )

        definition = ScenarioDefinition(
            scenario_id=f"{scenario.scenario_id}-DISRUPTED",
            name=f"{scenario.name} — po zakłóceniu",
            description=(
                f"Scenariusz po zastosowaniu planu {plan.plan_id}."
            ),
            catalog_path=scenario.definition.catalog_path,
            request_set_path=scenario.definition.request_set_path,
            opportunity_set_path=scenario.definition.opportunity_set_path,
        )

        disrupted_scenario = LoadedScenario(
            definition=definition,
            catalog=scenario.catalog,
            request_set=request_set,
            opportunity_set=opportunity_set,
        )

        return DisruptionApplicationResult(
            previous_scenario=scenario,
            disrupted_scenario=disrupted_scenario,
            plan=plan,
            outage_invalidated_opportunity_ids=tuple(
                sorted(set(outage_invalidated))
            ),
            weather_invalidated_opportunity_ids=tuple(
                sorted(set(weather_invalidated))
            ),
            added_request_ids=tuple(sorted(added_request_ids)),
            added_opportunity_ids=tuple(sorted(added_opportunity_ids)),
        )

    @staticmethod
    def _validate_plan_horizon(
        *,
        scenario: LoadedScenario,
        plan: DisruptionPlan,
    ) -> None:
        horizon_start = scenario.request_set.horizon_start_utc
        horizon_end = scenario.request_set.horizon_end_utc

        if not horizon_start <= plan.occurred_at_utc < horizon_end:
            raise ValueError(
                "occurred_at_utc musi znajdować się wewnątrz horyzontu"
            )

        for outage in plan.satellite_outages:
            if not horizon_start <= outage.effective_from_utc < horizon_end:
                raise ValueError(
                    "Moment rozpoczęcia awarii musi znajdować się "
                    "wewnątrz horyzontu"
                )

        for package in plan.urgent_requests:
            request = package.request

            if request.earliest_start_utc < horizon_start:
                raise ValueError(
                    f"Pilne zlecenie {request.request_id} rozpoczyna się "
                    "przed horyzontem"
                )

            if request.latest_end_utc > horizon_end:
                raise ValueError(
                    f"Pilne zlecenie {request.request_id} kończy się "
                    "po horyzoncie"
                )


class DisruptionReplanningService:
    """Stosuje zakłócenia i uruchamia dynamiczne przeplanowanie."""

    def __init__(
        self,
        *,
        disruption_service: DisruptionService | None = None,
        replanning_service: ReplanningService | None = None,
    ) -> None:
        self.disruption_service = disruption_service or DisruptionService()
        self.replanning_service = replanning_service or ReplanningService()

    def run(
        self,
        *,
        scenario: LoadedScenario,
        previous_schedule,
        plan: DisruptionPlan,
        options: PlanningOptions,
        replan_at_utc: datetime,
        freeze_duration: timedelta = DEFAULT_FREEZE_DURATION,
        schedule_id: str | None = None,
        schedule_name: str | None = None,
    ) -> DisruptionReplanningResult:
        replan_at = _normalize_utc(
            replan_at_utc,
            field_name="replan_at_utc",
        )

        if freeze_duration <= timedelta(0):
            raise ValueError("freeze_duration musi być większe od zera")

        frozen_until = min(
            replan_at + freeze_duration,
            scenario.request_set.horizon_end_utc,
        )

        if plan.occurred_at_utc > replan_at:
            raise ValueError(
                "Plan zakłóceń nie może wystąpić po momencie przeplanowania"
            )

        for outage in plan.satellite_outages:
            if outage.effective_from_utc < frozen_until:
                raise ValueError(
                    "Awaria w tym modelu demonstracyjnym musi rozpoczynać "
                    "się po zakończeniu okna zamrożonego"
                )

        original_opportunity_by_id = {
            opportunity.opportunity_id: opportunity
            for opportunity in scenario.opportunity_set.opportunities
        }

        for update in plan.cloud_cover_updates:
            opportunity = original_opportunity_by_id.get(
                update.opportunity_id
            )

            if opportunity is not None and opportunity.start_utc < frozen_until:
                raise ValueError(
                    "Aktualizacja pogody nie może zmieniać okazji "
                    "w oknie zamrożonym"
                )

        for package in plan.urgent_requests:
            for opportunity in package.opportunities:
                if opportunity.start_utc < frozen_until:
                    raise ValueError(
                        "Okazja pilnego zlecenia nie może rozpoczynać się "
                        "w oknie zamrożonym"
                    )

        application_result = self.disruption_service.apply(
            scenario=scenario,
            plan=plan,
        )

        replanning_result = self.replanning_service.run(
            scenario=application_result.disrupted_scenario,
            previous_schedule=previous_schedule,
            options=options,
            replan_at_utc=replan_at,
            freeze_duration=freeze_duration,
            schedule_id=schedule_id,
            schedule_name=schedule_name,
        )

        return DisruptionReplanningResult(
            application_result=application_result,
            replanning_result=replanning_result,
        )


def _normalize_utc(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} musi zawierać strefę czasową")

    return value.astimezone(timezone.utc)


def _normalize_reason(value: str, *, field_name: str) -> str:
    reason = value.strip()

    if not reason:
        raise ValueError(f"{field_name} nie może być pusty")

    if len(reason) > 500:
        raise ValueError(f"{field_name} nie może przekraczać 500 znaków")

    return reason


def _ensure_unique(values: Iterable[str], description: str) -> None:
    value_list = list(values)

    if len(value_list) != len(set(value_list)):
        raise ValueError(f"Powtórzony {description}")


def _append_unique_reason(reasons: Iterable[str], reason: str) -> list[str]:
    result = list(reasons)

    if reason not in result:
        result.append(reason)

    return result


def _append_note(existing: str | None, addition: str) -> str:
    if existing:
        combined = f"{existing.rstrip()} {addition}"
    else:
        combined = addition

    return combined[:2000]


def _validated_opportunity_copy(
    opportunity: AcquisitionOpportunity,
    updates: dict[str, object],
) -> AcquisitionOpportunity:
    data = opportunity.model_dump()
    data.update(updates)
    return AcquisitionOpportunity.model_validate(data)


def _validated_request_set_copy(
    request_set: ObservationRequestSet,
    updates: dict[str, object],
) -> ObservationRequestSet:
    data = request_set.model_dump()
    data.update(updates)
    return ObservationRequestSet.model_validate(data)


def _validated_opportunity_set_copy(
    opportunity_set: AcquisitionOpportunitySet,
    updates: dict[str, object],
) -> AcquisitionOpportunitySet:
    data = opportunity_set.model_dump()
    data.update(updates)
    return AcquisitionOpportunitySet.model_validate(data)
