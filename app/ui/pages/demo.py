from __future__ import annotations

import pandas as pd
import streamlit as st

from app.demo import DEMO_STATE_KEY
from app.models.enums import PlanningAlgorithm
from app.projects.service import PLANNING_RESULT_STATE_KEY
from app.services.contracts import PlanningResult
from app.ui.app_context import get_demo_project_service
from app.ui.pages.planning import render_planning_result, render_scenario_overview


_DEMO_RESULT_STATE_KEY = "satplan_demo_result"


def _render_demo_loader() -> None:
    with st.container(border=True):
        st.markdown("### Wczytaj gotowy projekt demonstracyjny")
        st.write(
            "Scenariusz działa całkowicie offline. Zawiera 6 satelitów, "
            "50 zleceń SAR/EO/SAR+EO, 500 okazji, 48-godzinny horyzont "
            "oraz gotowe dane OMM i referencyjne okna dostępu nad Polską."
        )
        first, second = st.columns([1.2, 1.0])
        algorithm_value = first.radio(
            "Algorytm harmonogramowania",
            options=[
                PlanningAlgorithm.GREEDY.value,
                PlanningAlgorithm.CP_SAT.value,
                PlanningAlgorithm.HYBRID.value,
            ],
            index=2,
            format_func=lambda value: value.replace("_", "-"),
            horizontal=True,
        )
        cp_sat_limit = second.select_slider(
            "Limit CP-SAT",
            options=[1.0, 2.0, 5.0, 10.0],
            value=5.0,
            format_func=lambda value: f"{value:g} s",
            disabled=algorithm_value == PlanningAlgorithm.GREEDY.value,
        )
        load_clicked = st.button(
            "Wczytaj scenariusz demonstracyjny Polski",
            type="primary",
            width="stretch",
        )

    if not load_clicked:
        return

    try:
        with st.spinner("Przygotowywanie harmonogramu demonstracyjnego..."):
            result = get_demo_project_service().build(
                algorithm=PlanningAlgorithm(algorithm_value),
                cp_sat_time_limit_s=float(cp_sat_limit),
            )
            get_demo_project_service().apply_to_state(st.session_state, result)
    except Exception as error:
        st.session_state.pop(_DEMO_RESULT_STATE_KEY, None)
        st.error("Nie udało się przygotować scenariusza demonstracyjnego.")
        st.exception(error)
    else:
        st.session_state[_DEMO_RESULT_STATE_KEY] = result
        st.success(
            "Scenariusz został wczytany. Zlecenia, orbity OMM, okna dostępu, "
            "harmonogram, metadane projektu i historia planu są dostępne "
            "w pozostałych modułach."
        )
        st.rerun()


def _render_loaded_demo() -> None:
    planning = st.session_state.get(PLANNING_RESULT_STATE_KEY)
    demo_state = st.session_state.get(DEMO_STATE_KEY)
    if not isinstance(planning, PlanningResult) or not demo_state:
        st.info(
            "Wczytaj scenariusz, aby uruchomić planowanie, eksport projektu "
            "i generator raportu bez pobierania danych z Internetu."
        )
        return

    st.markdown("### Aktywny projekt demonstracyjny")
    metrics = st.columns(6)
    metrics[0].metric("Satelity", planning.scenario.satellite_count)
    metrics[1].metric("Zlecenia", planning.scenario.active_request_count)
    metrics[2].metric("Okazje", planning.scenario.opportunity_count)
    metrics[3].metric(
        "Okna dostępu",
        int(demo_state.get("access_window_count", 0)),
    )
    metrics[4].metric("Akwizycje", planning.total_acquisitions)
    metrics[5].metric(
        "Zrealizowane",
        (
            f"{planning.fully_satisfied_requests}/"
            f"{planning.analysis.total_active_requests}"
        ),
    )

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Scenariusz": planning.scenario.name,
                    "Algorytm": planning.algorithm.value.replace("_", "-"),
                    "Status solvera": planning.solver_status,
                    "Funkcja celu": round(planning.objective_value, 3),
                    "Czas [s]": planning.wall_clock_runtime_s,
                    "Wczytano UTC": demo_state.get("loaded_at_utc", ""),
                }
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    with st.expander("Podgląd scenariusza i harmonogramu", expanded=False):
        render_scenario_overview(planning.scenario)
        render_planning_result(planning)

    st.info(
        "Dalsza praca: „Globus operacyjny” pokazuje ślady i okna "
        "dostępu, „Projekty” umożliwiają eksport ZIP, „Raporty” generują "
        "DOCX/XLSX/HTML, a „Planowanie scenariuszy referencyjnych” "
        "porównuje Greedy, CP-SAT i Hybrid na tych samych 50 zleceniach."
    )


def render_demo_page() -> None:
    """Udostępnia gotowy, offline'owy scenariusz prezentacyjny Polski."""

    st.header("Start i scenariusz demonstracyjny")
    st.info(
        "Scenariusz referencyjny pozwala rozpocząć pracę bez ręcznego "
        "tworzenia AOI i bez zależności od bieżącej dostępności CelesTrak "
        "oraz Open-Meteo."
    )
    _render_demo_loader()
    _render_loaded_demo()
    st.caption(
        "Dane demonstracyjne służą do prezentacji i testów regresyjnych. "
        "Nie reprezentują potwierdzonego taskingu operatorów."
    )


__all__ = ["render_demo_page"]
