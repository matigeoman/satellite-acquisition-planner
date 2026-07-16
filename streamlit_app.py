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
    render_disruption_page,
    render_experiments_page,
    render_planning_page,
    render_replanning_page,
)
from app.ui.styles import apply_application_styles


_PAGE_RENDERERS = {
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
