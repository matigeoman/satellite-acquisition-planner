from __future__ import annotations

import streamlit as st

from app.analysis.experimental_validation import ExperimentalValidationService
from app.io import load_schedule
from app.services.comparison_service import PlanningComparisonService
from app.services.disruption_service import DisruptionReplanningService
from app.services.planning_service import PlanningService
from app.services.orbit_service import PublicOrbitService
from app.integrations.orbits import CelestrakClient
from app.services.replanning_service import ReplanningService
from app.services.scenario_service import LoadedScenario, ScenarioService
from app.ui.paths import PROJECT_ROOT, reference_schedule_path


@st.cache_resource(scope="session", show_spinner=False)
def get_scenario_service() -> ScenarioService:
    """Zwraca współdzielony serwis scenariuszy dla bieżącej sesji."""

    return ScenarioService(project_root=PROJECT_ROOT)


@st.cache_resource(scope="session", show_spinner=False)
def get_planning_service() -> PlanningService:
    """Zwraca współdzielony serwis planowania."""

    return PlanningService()


@st.cache_resource(scope="session", show_spinner=False)
def get_comparison_service() -> PlanningComparisonService:
    """Zwraca serwis porównujący Greedy i CP-SAT."""

    return PlanningComparisonService(
        planning_service=get_planning_service()
    )


@st.cache_resource(scope="session", show_spinner=False)
def get_replanning_service() -> ReplanningService:
    """Zwraca serwis dynamicznego przeplanowania."""

    return ReplanningService(
        planning_service=get_planning_service()
    )


@st.cache_resource(scope="session", show_spinner=False)
def get_disruption_replanning_service() -> DisruptionReplanningService:
    """Zwraca serwis reakcji na zakłócenia operacyjne."""

    return DisruptionReplanningService(
        replanning_service=get_replanning_service()
    )


@st.cache_resource(scope="session", show_spinner=False)
def get_experimental_validation_service() -> ExperimentalValidationService:
    """Zwraca serwis wielokrotnej walidacji eksperymentalnej."""

    return ExperimentalValidationService(
        comparison_service=get_comparison_service()
    )



@st.cache_resource(scope="session", show_spinner=False)
def get_public_orbit_service() -> PublicOrbitService:
    """Zwraca klienta CelesTrak i propagator SGP4 z cache dyskowym."""

    return PublicOrbitService(
        client=CelestrakClient(
            cache_directory=PROJECT_ROOT / "data" / "generated" / "orbits"
        )
    )


@st.cache_resource(scope="session", show_spinner=False)
def load_reference_schedule(
    scenario_id: str,
    algorithm_value: str,
):
    """Wczytuje zapisany harmonogram bazowy i buforuje go w sesji."""

    return load_schedule(
        reference_schedule_path(
            scenario_id=scenario_id,
            algorithm_value=algorithm_value,
        )
    )


@st.cache_resource(scope="session", show_spinner=False)
def load_scenario(scenario_id: str) -> LoadedScenario:
    """Wczytuje scenariusz i buforuje wynik w obrębie sesji."""

    return get_scenario_service().load(scenario_id)
