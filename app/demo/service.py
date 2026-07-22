from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from app.integrations.access import AccessCalculationResult
from app.models.enums import PlanningAlgorithm
from app.planning.profiles import DecisionProfile
from app.projects.codec import decode_access_result, decode_orbit_snapshot
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
from app.services.orbit_service import PublicConstellationSnapshot
from app.services.planning_service import PlanningService
from app.services.scenario_service import LoadedScenario, ScenarioService


DEMO_STATE_KEY = "satplan_demo_active"
DEMO_SCENARIO_ID = "POLAND_DEMO"
DEMO_ARTIFACT_DIRECTORY = Path("examples") / "poland_demo"


@dataclass(frozen=True, slots=True)
class DemoProjectResult:
    """Kompletny, deterministyczny projekt demonstracyjny działający offline."""

    scenario: LoadedScenario
    planning_result: PlanningResult
    orbit_snapshot: PublicConstellationSnapshot
    access_result: AccessCalculationResult
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

    @property
    def access_window_count(self) -> int:
        return len(self.access_result.windows)

    @property
    def horizon_hours(self) -> float:
        duration = (
            self.scenario.request_set.horizon_end_utc
            - self.scenario.request_set.horizon_start_utc
        )
        return duration.total_seconds() / 3600.0


class DemoProjectService:
    """Ładuje rozbudowany scenariusz Polski i wypełnia stan aplikacji."""

    def __init__(
        self,
        *,
        scenario_service: ScenarioService,
        planning_service: PlanningService,
    ) -> None:
        self.scenario_service = scenario_service
        self.planning_service = planning_service
        self.project_root = scenario_service.project_root

    @property
    def artifact_directory(self) -> Path:
        return self.project_root / DEMO_ARTIFACT_DIRECTORY

    @staticmethod
    def _read_json(path: Path) -> Mapping[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Plik demonstracyjny nie zawiera obiektu JSON: {path}")
        return payload

    def _load_orbit_snapshot(self) -> PublicConstellationSnapshot:
        path = self.artifact_directory / "orbits_omm.json"
        snapshot = decode_orbit_snapshot(self._read_json(path))
        if len(snapshot.satellites) != 6:
            raise ValueError("Snapshot demonstracyjny musi zawierać 6 satelitów")
        return snapshot

    def _load_access_result(self) -> AccessCalculationResult:
        path = self.artifact_directory / "access_windows.json"
        result = decode_access_result(self._read_json(path))
        if not result.windows:
            raise ValueError("Scenariusz demonstracyjny nie zawiera okien dostępu")
        return result

    def build(
        self,
        *,
        algorithm: PlanningAlgorithm = PlanningAlgorithm.GREEDY,
        cp_sat_time_limit_s: float = 5.0,
    ) -> DemoProjectResult:
        scenario = self.scenario_service.load(DEMO_SCENARIO_ID)
        orbit_snapshot = self._load_orbit_snapshot()
        access_result = self._load_access_result()
        request_ids = {
            request.request_id for request in scenario.request_set.requests
        }
        if access_result.request_id not in request_ids:
            raise ValueError(
                "Referencyjne okna dostępu wskazują zlecenie spoza demo"
            )

        options = PlanningOptions(
            algorithm=algorithm,
            decision_profile=DecisionProfile.BALANCED,
            memory_reserve_ratio=0.15,
            use_dynamic_transition_model=True,
            cp_sat_time_limit_s=cp_sat_time_limit_s,
            cp_sat_num_search_workers=1,
            cp_sat_random_seed=20260720,
            cp_sat_force_mandatory_requests=False,
        )
        planning_result = self.planning_service.run(
            scenario=scenario,
            options=options,
            schedule_id=f"SCHEDULE-DEMO-{algorithm.value.replace('_', '-')}",
            schedule_name=(
                "Polska — 48 h / 50 zleceń — "
                f"{algorithm.value.replace('_', '-')}"
            ),
        )
        return DemoProjectResult(
            scenario=scenario,
            planning_result=planning_result,
            orbit_snapshot=orbit_snapshot,
            access_result=access_result,
            loaded_at_utc=datetime.now(timezone.utc),
        )

    def apply_to_state(
        self,
        state: MutableMapping[str, Any],
        result: DemoProjectResult,
    ) -> None:
        for key in (
            OPPORTUNITY_BUILDS_STATE_KEY,
            REPLANNING_RESULT_STATE_KEY,
            BENCHMARK_RESULT_STATE_KEY,
        ):
            state.pop(key, None)

        requests = list(result.scenario.request_set.requests)
        request_by_id = {request.request_id: request for request in requests}
        featured_request = request_by_id[result.access_result.request_id]

        state[CUSTOM_REQUESTS_STATE_KEY] = requests
        state[AOI_STATE_KEY] = featured_request.geometry
        state[ORBIT_SNAPSHOT_STATE_KEY] = result.orbit_snapshot
        state[ACCESS_RESULT_STATE_KEY] = result.access_result
        state[PLANNING_RESULT_STATE_KEY] = result.planning_result
        state[SCHEDULE_HISTORY_STATE_KEY] = [
            build_schedule_history_entry(
                result.planning_result,
                event_type="DEMO_LOAD",
            )
        ]
        state[PROJECT_METADATA_STATE_KEY] = ProjectMetadata(
            project_id="PROJECT-POLAND-DEMO",
            name="Polska — scenariusz demonstracyjny 48 h",
            description=(
                "Rozbudowany scenariusz prezentacyjny: 50 zleceń SAR, EO "
                "i SAR+EO, 500 okazji oraz wbudowane dane OMM i okna dostępu."
            ),
            author="",
            created_at_utc=result.loaded_at_utc,
            exported_at_utc=result.loaded_at_utc,
            component_counts={
                "requests": result.request_count,
                "opportunities": result.opportunity_count,
                "access_windows": result.access_window_count,
                "orbit_objects": len(result.orbit_snapshot.satellites),
                "schedule_entries": result.acquisition_count,
                "schedule_versions": 1,
            },
            notes=[
                "Scenariusz działa offline i nie wymaga CelesTrak ani Open-Meteo.",
                "Okna zleceń mają długość od 2 do 48 godzin.",
                "Dane OMM i okna dostępu są referencyjnymi danymi demo.",
            ],
        )
        state[DEMO_STATE_KEY] = {
            "scenario_id": result.scenario.scenario_id,
            "algorithm": result.planning_result.algorithm.value,
            "loaded_at_utc": result.loaded_at_utc.isoformat(),
            "horizon_hours": result.horizon_hours,
            "request_count": result.request_count,
            "opportunity_count": result.opportunity_count,
            "access_window_count": result.access_window_count,
        }


__all__ = [
    "DEMO_ARTIFACT_DIRECTORY",
    "DEMO_SCENARIO_ID",
    "DEMO_STATE_KEY",
    "DemoProjectResult",
    "DemoProjectService",
]
