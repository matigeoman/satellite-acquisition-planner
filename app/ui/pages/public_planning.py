from __future__ import annotations

import json

import streamlit as st

from app.models.enums import PlanningAlgorithm
from app.services.contracts.planning import PlanningOptions, PlanningResult
from app.ui.app_context import (
    get_planning_service,
    get_public_scenario_service,
)
from app.ui.common import algorithm_display_name
from app.ui.pages.planning import (
    render_planning_result,
    render_scenario_overview,
)


_PUBLIC_PLANNING_RESULT_KEY = "public_planning_result"
_PUBLIC_BUILDS_STATE_KEY = "public_opportunity_builds"


def _build_scenario():
    requests = st.session_state.get("custom_observation_requests", [])
    builds = st.session_state.get(_PUBLIC_BUILDS_STATE_KEY, {})
    return get_public_scenario_service().build(
        requests=requests,
        builds_by_request_id=builds,
    )


def render_public_planning_page() -> None:
    """Uruchamia Greedy lub CP-SAT na okazjach publicznych z sesji."""

    st.header("Planowanie publicznych okazji")
    st.info(
        "Ten moduł używa pełnych AcquisitionOpportunity zbudowanych z "
        "CelesTrak GP/OMM, propagacji SGP4, publicznych profili sensorów i "
        "prognozy Open-Meteo dla EO. Ograniczenia pamięci i limitów dobowych "
        "pozostają jawnymi parametrami modelowymi."
    )

    try:
        scenario = _build_scenario()
    except ValueError as error:
        st.warning(str(error))
        st.caption(
            "W module „Okna dostępu” wyznacz okna dla jednego lub kilku "
            "zleceń, a następnie utwórz okazje planistyczne."
        )
        return

    render_scenario_overview(scenario)
    all_count = len(scenario.opportunity_set.opportunities)
    infeasible_count = len(scenario.opportunity_set.infeasible_opportunities)
    st.caption(
        f"Łącznie okazji: {all_count}; odrzuconych przed solverem: "
        f"{infeasible_count}. Solver korzysta wyłącznie z okazji wykonalnych."
    )

    with st.container(border=True):
        st.markdown("### Konfiguracja solvera")
        first, second, third, fourth = st.columns([1.2, 1.1, 1.1, 1.1])
        algorithm_value = first.radio(
            "Algorytm",
            options=[
                PlanningAlgorithm.GREEDY.value,
                PlanningAlgorithm.CP_SAT.value,
            ],
            format_func=algorithm_display_name,
            horizontal=True,
        )
        memory_reserve_percent = second.slider(
            "Rezerwa pamięci",
            min_value=0,
            max_value=50,
            value=15,
            step=1,
            format="%d%%",
        )
        cp_sat_time_limit_s = third.select_slider(
            "Limit CP-SAT",
            options=[1.0, 5.0, 10.0, 30.0],
            value=10.0,
            format_func=lambda value: f"{value:g} s",
        )
        cp_sat_workers = fourth.number_input(
            "Wątki CP-SAT",
            min_value=1,
            max_value=16,
            value=1,
            step=1,
        )

        with st.expander("Wagi funkcji celu"):
            weights = st.columns(5)
            priority_weight = weights[0].number_input(
                "Priorytet",
                min_value=0.0,
                value=10.0,
                step=1.0,
            )
            quality_weight = weights[1].number_input(
                "Jakość",
                min_value=0.0,
                value=3.0,
                step=0.5,
            )
            coverage_weight = weights[2].number_input(
                "Pokrycie",
                min_value=0.0,
                value=2.0,
                step=0.5,
            )
            mandatory_bonus = weights[3].number_input(
                "Obowiązkowe",
                min_value=0.0,
                value=100.0,
                step=10.0,
            )
            dual_optional_bonus = weights[4].number_input(
                "Drugi sensor",
                min_value=0.0,
                value=5.0,
                step=1.0,
            )

        force_mandatory = st.checkbox(
            "Wymuś zlecenia obowiązkowe w CP-SAT",
            value=True,
        )
        run_clicked = st.button(
            "Uruchom planowanie publiczne",
            type="primary",
            width="stretch",
        )

    if run_clicked:
        options = PlanningOptions(
            algorithm=PlanningAlgorithm(algorithm_value),
            memory_reserve_ratio=memory_reserve_percent / 100.0,
            priority_weight=float(priority_weight),
            quality_weight=float(quality_weight),
            coverage_weight=float(coverage_weight),
            mandatory_bonus=float(mandatory_bonus),
            dual_optional_second_bonus=float(dual_optional_bonus),
            cp_sat_time_limit_s=float(cp_sat_time_limit_s),
            cp_sat_num_search_workers=int(cp_sat_workers),
            cp_sat_force_mandatory_requests=force_mandatory,
        )
        try:
            with st.spinner(
                f"Uruchamianie {algorithm_display_name(algorithm_value)}..."
            ):
                result = get_planning_service().run(
                    scenario=scenario,
                    options=options,
                    schedule_id=(
                        f"SCHEDULE-PUBLIC-{PlanningAlgorithm(algorithm_value).value}"
                    ),
                    schedule_name=(
                        "Publiczne orbity i pogoda — "
                        f"{algorithm_display_name(algorithm_value)}"
                    ),
                )
        except Exception as error:
            st.session_state.pop(_PUBLIC_PLANNING_RESULT_KEY, None)
            st.error("Planowanie publiczne zakończyło się błędem.")
            st.exception(error)
            return
        st.session_state[_PUBLIC_PLANNING_RESULT_KEY] = result
        st.success("Planowanie publiczne zakończone.")

    result = st.session_state.get(_PUBLIC_PLANNING_RESULT_KEY)
    if result is not None:
        if not isinstance(result, PlanningResult):
            st.session_state.pop(_PUBLIC_PLANNING_RESULT_KEY, None)
            st.error("Stan sesji zawiera niepoprawny wynik planowania.")
            return
        current_request_ids = {
            request.request_id for request in scenario.request_set.requests
        }
        result_request_ids = {
            request.request_id for request in result.scenario.request_set.requests
        }
        if current_request_ids == result_request_ids:
            render_planning_result(result)

    with st.expander("Eksport danych wejściowych scenariusza publicznego"):
        exports = st.columns(3)
        exports[0].download_button(
            "Katalog systemu",
            data=json.dumps(
                scenario.catalog.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ),
            file_name="public_system_catalog.json",
            mime="application/json",
            width="stretch",
        )
        exports[1].download_button(
            "Zlecenia",
            data=json.dumps(
                scenario.request_set.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ),
            file_name="public_requests.json",
            mime="application/json",
            width="stretch",
        )
        exports[2].download_button(
            "Okazje",
            data=json.dumps(
                scenario.opportunity_set.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ),
            file_name="public_opportunities.json",
            mime="application/json",
            width="stretch",
        )
