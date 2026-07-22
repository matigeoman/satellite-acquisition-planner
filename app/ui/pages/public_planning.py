from __future__ import annotations

import json

import streamlit as st

from app.models.enums import PlanningAlgorithm
from app.projects import record_schedule_history
from app.planning.profiles import DecisionProfile
from app.services.contracts.planning import PlanningOptions, PlanningResult
from app.services.planning_service import PlanningService
from app.ui.app_context import (
    get_planning_service,
    get_public_scenario_service,
)
from app.ui.common import (
    algorithm_display_name,
    decision_profile_display_name,
)
from app.ui.pages.planning import (
    render_planning_result,
    render_scenario_overview,
)


_PUBLIC_PLANNING_RESULT_KEY = "public_planning_result"
_PUBLIC_BUILDS_STATE_KEY = "public_opportunity_builds"


def build_public_schedule_id(algorithm: PlanningAlgorithm) -> str:
    """Buduje identyfikator zgodny ze schematem Schedule także dla CP-SAT."""

    return PlanningService.build_schedule_id(
        scenario_id="PUBLIC",
        algorithm=algorithm,
    )


def _build_scenario():
    requests = st.session_state.get("custom_observation_requests", [])
    builds = st.session_state.get(_PUBLIC_BUILDS_STATE_KEY, {})
    return get_public_scenario_service().build(
        requests=requests,
        builds_by_request_id=builds,
    )


def render_public_planning_page() -> None:
    """Uruchamia Greedy, CP-SAT albo Hybrid na danych publicznych."""

    st.header("Planowanie na danych publicznych")
    st.info(
        "Moduł używa okazji akwizycyjnych zbudowanych z "
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
        first, second, third, fourth, fifth = st.columns(
            [1.35, 1.35, 1.0, 1.0, 0.9]
        )
        algorithm_value = first.radio(
            "Algorytm",
            options=[
                PlanningAlgorithm.GREEDY.value,
                PlanningAlgorithm.CP_SAT.value,
                PlanningAlgorithm.HYBRID.value,
            ],
            index=2,
            format_func=algorithm_display_name,
            horizontal=True,
        )
        decision_profile_value = second.selectbox(
            "Profil decyzyjny",
            options=[profile.value for profile in DecisionProfile],
            index=1,
            format_func=decision_profile_display_name,
            help=(
                "Profil ustawia jawne wagi priorytetu, jakości, pokrycia "
                "i kosztu utraconych okazji."
            ),
        )
        custom_profile = decision_profile_value == DecisionProfile.CUSTOM.value
        memory_reserve_percent = third.slider(
            "Rezerwa pamięci",
            min_value=0,
            max_value=50,
            value=15,
            step=1,
            format="%d%%",
        )
        cp_sat_time_limit_s = fourth.select_slider(
            "Budżet CP-SAT",
            options=[1.0, 5.0, 10.0, 30.0],
            value=10.0,
            format_func=lambda value: f"{value:g} s",
            disabled=algorithm_value == PlanningAlgorithm.GREEDY.value,
        )
        cp_sat_workers = fifth.number_input(
            "Wątki CP-SAT",
            min_value=1,
            max_value=16,
            value=1,
            step=1,
            disabled=algorithm_value == PlanningAlgorithm.GREEDY.value,
        )

        with st.expander("Wagi funkcji celu"):
            weights = st.columns(5)
            priority_weight = weights[0].number_input(
                "Priorytet",
                min_value=0.0,
                value=10.0,
                step=1.0,
                disabled=not custom_profile,
            )
            quality_weight = weights[1].number_input(
                "Jakość",
                min_value=0.0,
                value=3.0,
                step=0.5,
                disabled=not custom_profile,
            )
            coverage_weight = weights[2].number_input(
                "Pokrycie",
                min_value=0.0,
                value=2.0,
                step=0.5,
                disabled=not custom_profile,
            )
            mandatory_bonus = weights[3].number_input(
                "Obowiązkowe",
                min_value=0.0,
                value=100.0,
                step=10.0,
                disabled=not custom_profile,
            )
            dual_optional_bonus = weights[4].number_input(
                "Drugi sensor",
                min_value=0.0,
                value=5.0,
                step=1.0,
                disabled=not custom_profile,
            )

        force_mandatory = st.checkbox(
            "Wymuś zlecenia obowiązkowe w CP-SAT",
            value=True,
        )

        with st.expander("Ograniczenia operacyjne", expanded=True):
            use_dynamic_transition_model = st.checkbox(
                "Dynamiczne przeorientowanie Pléiades Neo i ICEYE",
                value=True,
                help=(
                    "Zastępuje stałą przerwę modelem zależnym od kierunku "
                    "obserwacji, strony LEFT/RIGHT i zmiany trybu SAR."
                ),
            )
            first_operational, second_operational = st.columns(2)
            eo_stabilization_time_s = first_operational.number_input(
                "Stabilizacja EO [s]",
                min_value=0.0,
                value=3.0,
                step=1.0,
            )
            sar_stabilization_time_s = second_operational.number_input(
                "Stabilizacja SAR [s]",
                min_value=0.0,
                value=10.0,
                step=1.0,
            )
            sar_side_switch_penalty_s = first_operational.number_input(
                "Zmiana LEFT/RIGHT [s]",
                min_value=0.0,
                value=60.0,
                step=5.0,
            )
            sar_mode_switch_penalty_s = second_operational.number_input(
                "Zmiana kategorii trybu SAR [s]",
                min_value=0.0,
                value=15.0,
                step=5.0,
            )
            sar_slew_rate_deg_s = first_operational.number_input(
                "Prędkość zwrotu SAR [°/s]",
                min_value=0.1,
                value=2.0,
                step=0.1,
            )
            sar_pass_gap_minutes = second_operational.number_input(
                "Przerwa rozdzielająca przeloty SAR [min]",
                min_value=1.0,
                value=15.0,
                step=1.0,
            )
            sar_max_acquisitions_per_pass = st.slider(
                "Maksymalna liczba akwizycji ICEYE w jednym przelocie",
                min_value=1,
                max_value=10,
                value=3,
                step=1,
            )
            st.caption(
                "Pléiades Neo: interpolacja 10°/7 s, 30°/12 s i "
                "60°/20 s. Parametry ICEYE są jawnymi założeniami modelu."
            )

        run_clicked = st.button(
            "Uruchom planowanie publiczne",
            type="primary",
            width="stretch",
        )

    if run_clicked:
        options = PlanningOptions(
            algorithm=PlanningAlgorithm(algorithm_value),
            decision_profile=DecisionProfile(decision_profile_value),
            memory_reserve_ratio=memory_reserve_percent / 100.0,
            use_dynamic_transition_model=use_dynamic_transition_model,
            eo_stabilization_time_s=float(eo_stabilization_time_s),
            sar_stabilization_time_s=float(sar_stabilization_time_s),
            sar_side_switch_penalty_s=float(sar_side_switch_penalty_s),
            sar_mode_switch_penalty_s=float(sar_mode_switch_penalty_s),
            sar_slew_rate_deg_s=float(sar_slew_rate_deg_s),
            sar_pass_gap_s=float(sar_pass_gap_minutes) * 60.0,
            sar_max_acquisitions_per_pass=int(sar_max_acquisitions_per_pass),
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
            algorithm = PlanningAlgorithm(algorithm_value)
            planning_service = get_planning_service()
            with st.spinner(
                f"Uruchamianie {algorithm_display_name(algorithm_value)}..."
            ):
                result = planning_service.run(
                    scenario=scenario,
                    options=options,
                    schedule_id=build_public_schedule_id(algorithm),
                    schedule_name=(
                        "Publiczne orbity i pogoda — "
                        f"{algorithm_display_name(algorithm_value)}"
                    ),
                )
        except Exception as error:
            st.session_state.pop(_PUBLIC_PLANNING_RESULT_KEY, None)
            st.error("Planowanie zakończyło się błędem.")
            st.exception(error)
            return
        st.session_state[_PUBLIC_PLANNING_RESULT_KEY] = result
        record_schedule_history(
            st.session_state,
            result,
            event_type="INITIAL_PLANNING",
        )
        st.success("Planowanie zakończone.")

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

    with st.expander("Eksport danych wejściowych"):
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
