from __future__ import annotations

import streamlit as st

from app.analysis.experimental_validation import ExperimentalValidationService
from app.services.benchmark_service import AlgorithmBenchmarkService
from app.io import load_schedule
from app.services.comparison_service import PlanningComparisonService
from app.services.disruption_service import DisruptionReplanningService
from app.services.planning_service import PlanningService
from app.services.orbit_service import PublicOrbitService
from app.services.access_service import PublicAccessService
from app.integrations.orbits import CelestrakClient
from app.integrations.weather import CloudAssessmentService, OpenMeteoClient
from app.integrations.opportunities import PublicOpportunityWeatherRefreshService
from app.services.replanning_service import ReplanningService
from app.services.public_scenario_service import PublicScenarioService
from app.services.public_replanning_service import PublicReplanningService
from app.services.scenario_service import LoadedScenario, ScenarioService
from app.services.stk_validation_service import StkValidationService
from app.projects import ProjectArchiveService
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
def get_algorithm_benchmark_service() -> AlgorithmBenchmarkService:
    """Zwraca serwis benchmarków skalowalności Greedy i CP-SAT."""

    return AlgorithmBenchmarkService(
        planning_service=get_planning_service()
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
def get_public_access_service() -> PublicAccessService:
    """Zwraca serwis wyznaczania publicznych okien dostępu."""

    return PublicAccessService(orbit_service=get_public_orbit_service())


@st.cache_resource(scope="session", show_spinner=False)
def get_cloud_assessment_service() -> CloudAssessmentService:
    """Zwraca klienta Open-Meteo z cache prognozy zachmurzenia."""

    return CloudAssessmentService(
        client=OpenMeteoClient(
            cache_directory=PROJECT_ROOT / "data" / "generated" / "weather"
        )
    )


@st.cache_resource(scope="session", show_spinner=False)
def get_public_scenario_service() -> PublicScenarioService:
    """Zwraca budowniczego scenariusza z danych publicznych sesji."""

    return PublicScenarioService()


@st.cache_resource(scope="session", show_spinner=False)
def get_public_replanning_service() -> PublicReplanningService:
    """Zwraca serwis odświeżania pogody i przeplanowania publicznego."""

    return PublicReplanningService(
        scenario_service=get_public_scenario_service(),
        replanning_service=get_replanning_service(),
        weather_refresh_service=PublicOpportunityWeatherRefreshService(
            cloud_service=get_cloud_assessment_service()
        ),
    )


@st.cache_resource(scope="session", show_spinner=False)
def get_stk_validation_service() -> StkValidationService:
    """Zwraca serwis eksportu i porównania raportów STK."""

    return StkValidationService()


@st.cache_resource(scope="session", show_spinner=False)
def get_project_archive_service() -> ProjectArchiveService:
    """Zwraca serwis przenośnych archiwów projektu."""

    return ProjectArchiveService()


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
