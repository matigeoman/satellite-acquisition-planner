from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


st.set_page_config(
    page_title="Satellite Acquisition Planner",
    page_icon=":material/satellite_alt:",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": (
            "Satellite Acquisition Planner — "
            "planowanie akwizycji dla sensorów SAR i optycznych."
        ),
    },
)


from app.ui.navigation import ApplicationPage, render_navigation
from app.ui.pages import (
    render_access_page,
    render_benchmark_page,
    render_disruption_page,
    render_experiments_page,
    render_globe_page,
    render_planning_page,
    render_public_planning_page,
    render_public_replanning_page,
    render_projects_page,
    render_reports_page,
    render_orbits_page,
    render_replanning_page,
    render_targets_page,
    render_stk_validation_page,
)
from app.ui.styles import apply_application_styles


_PAGE_RENDERERS = {
    ApplicationPage.TARGETS: render_targets_page,
    ApplicationPage.ORBITS: render_orbits_page,
    ApplicationPage.ACCESS: render_access_page,
    ApplicationPage.GLOBE: render_globe_page,
    ApplicationPage.PUBLIC_PLANNING: render_public_planning_page,
    ApplicationPage.PUBLIC_REPLANNING: render_public_replanning_page,
    ApplicationPage.STK_VALIDATION: render_stk_validation_page,
    ApplicationPage.BENCHMARKS: render_benchmark_page,
    ApplicationPage.PROJECTS: render_projects_page,
    ApplicationPage.REPORTS: render_reports_page,
    ApplicationPage.PLANNING: render_planning_page,
    ApplicationPage.REPLANNING: render_replanning_page,
    ApplicationPage.DISRUPTIONS: render_disruption_page,
    ApplicationPage.EXPERIMENTS: render_experiments_page,
}


def main() -> None:
    """Uruchamia aplikację i deleguje renderowanie do wybranego modułu."""

    apply_application_styles()

    st.title("Satellite Acquisition Planner")
    st.caption(
        "Operacyjne planowanie, przeplanowanie i walidacja "
        "akwizycji satelitarnych SAR oraz optycznych"
    )

    selected_page = render_navigation()
    _PAGE_RENDERERS[selected_page]()


if __name__ == "__main__":
    main()
