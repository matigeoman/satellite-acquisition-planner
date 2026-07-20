from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, MutableMapping

from app.models.enums import PlanningAlgorithm
from app.projects.history import (
    PROJECT_METADATA_STATE_KEY,
    SCHEDULE_HISTORY_STATE_KEY,
    build_schedule_history_entry,
)
from app.projects.models import ProjectMetadata
from app.projects.service import (
    ACCESS_RESULT_STATE_KEY,
    AOI_STATE_KEY,
    BENCHMARK_RESULT_STATE_KEY,
    CUSTOM_REQUESTS_STATE_KEY,
    OPPORTUNITY_BUILDS_STATE_KEY,
    ORBIT_SNAPSHOT_STATE_KEY,
    PLANNING_RESULT_STATE_KEY,
    REPLANNING_RESULT_STATE_KEY,
)
from app.services.contracts import PlanningOptions, PlanningResult
from app.services.planning_service import PlanningService
from app.services.scenario_service import LoadedScenario, ScenarioService


DEMO_STATE_KEY = "satplan_demo_active"
DEMO_SCENARIO_ID = "EXAMPLE"


@dataclass(frozen=True, slots=True)
class DemoProjectResult:
    """Wynik przygotowania deterministycznego projektu demonstracyjnego."""

    scenario: LoadedScenario
    planning_result: PlanningResult
    loaded_at_utc: datetime

    @property
    def request_count(self) -> int:
        return self.scenario.active_request_count

    @property
    def opportunity_count(self) -> int:
        return self.scenario.opportunity_count

    @property
    def acquisition_count(self) -> int:
        return self.planning_result.total_acquisitions


class DemoProjectService:
    """Ładuje gotowy scenariusz Polski i zapisuje go w stanie aplikacji."""

    def __init__(
        self,
        *,
        scenario_service: ScenarioService,
        planning_service: PlanningService,
    ) -> None:
        self.scenario_service = scenario_service
        self.planning_service = planning_service

    def build(
        self,
        *,
        algorithm: PlanningAlgorithm = PlanningAlgorithm.GREEDY,
        cp_sat_time_limit_s: float = 5.0,
    ) -> DemoProjectResult:
        scenario = self.scenario_service.load(DEMO_SCENARIO_ID)
        options = PlanningOptions(
            algorithm=algorithm,
            memory_reserve_ratio=0.15,
            use_dynamic_transition_model=True,
            cp_sat_time_limit_s=cp_sat_time_limit_s,
            cp_sat_num_search_workers=1,
            cp_sat_random_seed=20260717,
        )
        planning_result = self.planning_service.run(
            scenario=scenario,
            options=options,
            schedule_id=f"SCHEDULE-DEMO-{algorithm.value.replace('_', '-')}",
            schedule_name=(
                "Polska — scenariusz demonstracyjny — "
                f"{algorithm.value.replace('_', '-')}"
            ),
        )
        return DemoProjectResult(
            scenario=scenario,
            planning_result=planning_result,
            loaded_at_utc=datetime.now(timezone.utc),
        )

    def apply_to_state(
        self,
        state: MutableMapping[str, Any],
        result: DemoProjectResult,
    ) -> None:
        for key in (
            ORBIT_SNAPSHOT_STATE_KEY,
            ACCESS_RESULT_STATE_KEY,
            OPPORTUNITY_BUILDS_STATE_KEY,
            REPLANNING_RESULT_STATE_KEY,
            BENCHMARK_RESULT_STATE_KEY,
        ):
            state.pop(key, None)

        requests = list(result.scenario.request_set.requests)
        state[CUSTOM_REQUESTS_STATE_KEY] = requests
        if requests:
            state[AOI_STATE_KEY] = requests[0].geometry
        state[PLANNING_RESULT_STATE_KEY] = result.planning_result
        state[SCHEDULE_HISTORY_STATE_KEY] = [
            build_schedule_history_entry(
                result.planning_result,
                event_type="DEMO_LOAD",
            )
        ]
        state[PROJECT_METADATA_STATE_KEY] = ProjectMetadata(
            project_id="PROJECT-POLAND-DEMO",
            name="Polska — scenariusz demonstracyjny",
            description=(
                "Deterministyczny scenariusz prezentacyjny obejmujący "
                "zlecenia SAR, EO i podwójne oraz gotowy harmonogram."
            ),
            author="",
            created_at_utc=result.loaded_at_utc,
            exported_at_utc=result.loaded_at_utc,
            component_counts={
                "requests": result.request_count,
                "opportunities": result.opportunity_count,
                "schedule_entries": result.acquisition_count,
                "schedule_versions": 1,
            },
            notes=[
                "Scenariusz demonstracyjny korzysta z danych referencyjnych "
                "dołączonych do repozytorium.",
                "Nie wymaga połączenia z CelesTrak ani Open-Meteo.",
            ],
        )
        state[DEMO_STATE_KEY] = {
            "scenario_id": result.scenario.scenario_id,
            "algorithm": result.planning_result.algorithm.value,
            "loaded_at_utc": result.loaded_at_utc.isoformat(),
        }


__all__ = [
    "DEMO_SCENARIO_ID",
    "DEMO_STATE_KEY",
    "DemoProjectResult",
    "DemoProjectService",
]
