from __future__ import annotations

from datetime import timedelta

import streamlit as st

from app.models.enums import PlanningAlgorithm
from app.planning.profiles import DecisionProfile
from app.services.planning_service import PlanningOptions
from app.services.replanning_service import ReplanningResult
from app.ui import (
    build_replanning_changes_dataframe,
    build_replanning_metrics,
    build_schedule_download_filename,
    build_schedule_json,
)
from app.ui.app_context import (
    get_replanning_service,
    get_scenario_service,
    load_reference_schedule,
    load_scenario,
)
from app.ui.common import algorithm_display_name, combine_utc
from app.ui.page_layout import render_page_header, render_sidebar_heading
from app.ui.pages.planning import render_result_tabs, render_scenario_overview


def render_replanning_page() -> None:
    render_page_header(
        "Dynamiczne przeplanowanie",
        "Zachowuje akwizycje już wykonane i znajdujące się w oknie "
        "zamrożonym, a pozostałą część horyzontu planuje ponownie.",
        eyebrow="Ciągłość planu",
        badges=("Frozen horizon", "Greedy", "CP-SAT", "Hybrid"),
    )

    definitions = {
        definition.scenario_id: definition
        for definition in get_scenario_service().definitions
    }

    with st.sidebar:
        render_sidebar_heading(
            "Przeplanowanie",
            "Scenariusz, algorytm i okno zamrożone",
        )
        scenario_id = st.selectbox(
            "Scenariusz",
            options=list(definitions),
            format_func=lambda value: definitions[value].name,
            key="replanning_scenario",
        )
        previous_algorithm = st.selectbox(
            "Harmonogram bazowy",
            options=["CP_SAT", "GREEDY"],
            format_func=lambda value: (
                f"{algorithm_display_name(value)} — zapisany plik"
            ),
            key="replanning_previous_algorithm",
        )
        replanning_algorithm = st.radio(
            "Algorytm przeplanowania",
            options=["HYBRID", "CP_SAT", "GREEDY"],
            format_func=algorithm_display_name,
            horizontal=True,
            key="replanning_algorithm",
        )

    try:
        scenario = load_scenario(scenario_id)
        previous_schedule = load_reference_schedule(
            scenario_id,
            previous_algorithm,
        )
    except Exception as error:
        st.error("Nie udało się wczytać danych przeplanowania.")
        st.exception(error)
        return

    default_replan_at = min(
        scenario.request_set.horizon_start_utc + timedelta(hours=6),
        scenario.request_set.horizon_end_utc - timedelta(minutes=1),
    )

    with st.sidebar:
        replan_date = st.date_input(
            "Data przeplanowania [UTC]",
            value=default_replan_at.date(),
            min_value=scenario.request_set.horizon_start_utc.date(),
            max_value=scenario.request_set.horizon_end_utc.date(),
            key="replanning_date",
        )
        replan_time = st.time_input(
            "Godzina przeplanowania [UTC]",
            value=default_replan_at.time().replace(tzinfo=None),
            step=timedelta(minutes=15),
            key="replanning_time",
        )
        freeze_hours = st.slider(
            "Okno zamrożone [h]",
            min_value=0.5,
            max_value=6.0,
            value=2.0,
            step=0.5,
            key="replanning_freeze_hours",
        )
        memory_reserve_percent = st.slider(
            "Rezerwa pamięci",
            min_value=0,
            max_value=50,
            value=0,
            step=1,
            format="%d%%",
            key="replanning_memory_reserve",
        )
        cp_sat_time_limit = st.select_slider(
            "Limit CP-SAT",
            options=[1.0, 2.0, 5.0, 10.0, 30.0],
            value=10.0,
            format_func=lambda value: f"{value:g} s",
            key="replanning_cp_limit",
        )
        submitted = st.button(
            "Uruchom przeplanowanie",
            type="primary",
            width="stretch",
            key="run_replanning",
        )

    replan_at_utc = combine_utc(replan_date, replan_time)
    render_scenario_overview(scenario)

    st.info(
        "Akwizycje zakończone przed momentem przeplanowania otrzymają "
        "status EXECUTED. Akwizycje rozpoczynające się przed końcem "
        "okna zamrożonego otrzymają status FROZEN."
    )

    if submitted:
        try:
            options = PlanningOptions(
                algorithm=PlanningAlgorithm(replanning_algorithm),
                decision_profile=(
                    DecisionProfile.BALANCED
                    if replanning_algorithm == PlanningAlgorithm.HYBRID.value
                    else DecisionProfile.CUSTOM
                ),
                memory_reserve_ratio=memory_reserve_percent / 100.0,
                cp_sat_time_limit_s=float(cp_sat_time_limit),
                cp_sat_num_search_workers=1,
                cp_sat_force_mandatory_requests=True,
            )
            with st.spinner("Przeplanowywanie pozostałej części doby..."):
                result = get_replanning_service().run(
                    scenario=scenario,
                    previous_schedule=previous_schedule,
                    options=options,
                    replan_at_utc=replan_at_utc,
                    freeze_duration=timedelta(hours=freeze_hours),
                )
            st.session_state["replanning_result"] = result
            st.success("Przeplanowanie zakończone.")
        except Exception as error:
            st.session_state.pop("replanning_result", None)
            st.error("Przeplanowanie zakończyło się błędem.")
            st.exception(error)

    result = st.session_state.get("replanning_result")

    if result is None:
        st.info("Ustaw parametry i uruchom przeplanowanie.")
        return

    if not isinstance(result, ReplanningResult):
        st.session_state.pop("replanning_result", None)
        st.error("Stan aplikacji zawiera niepoprawny wynik przeplanowania.")
        return

    render_replanning_result(result)


def render_replanning_result(result: ReplanningResult) -> None:
    metrics = build_replanning_metrics(result)

    st.divider()
    st.subheader("Wynik dynamicznego przeplanowania")

    first_row = st.columns(6)
    first_row[0].metric("Status solvera", metrics.solver_status)
    first_row[1].metric("Status harmonogramu", metrics.schedule_status)
    first_row[2].metric(
        "Nowa funkcja celu",
        f"{metrics.new_objective_value:.3f}",
        delta=f"{metrics.objective_delta:+.3f}",
    )
    first_row[3].metric("Wykonane", metrics.executed_count)
    first_row[4].metric("Zamrożone", metrics.frozen_count)
    first_row[5].metric("Stałe łącznie", metrics.fixed_count)

    second_row = st.columns(5)
    second_row[0].metric("Bez zmian", metrics.unchanged_count)
    second_row[1].metric("Dodane", metrics.added_count)
    second_row[2].metric("Usunięte", metrics.removed_count)
    second_row[3].metric("Akwizycje", metrics.total_acquisitions)
    second_row[4].metric(
        "Zrealizowane zlecenia",
        f"{metrics.fully_satisfied_requests}/{metrics.total_active_requests}",
    )

    st.caption(
        f"Moment przeplanowania: {result.replan_at_utc.isoformat()} · "
        f"koniec okna zamrożonego: {result.frozen_until_utc.isoformat()}"
    )

    changes = build_replanning_changes_dataframe(result)
    st.markdown("### Zmiany po oknie zamrożonym")

    if changes.empty:
        st.info("Brak przyszłych akwizycji do porównania.")
    else:
        selected_changes = st.multiselect(
            "Typ zmiany",
            options=["UNCHANGED", "ADDED", "REMOVED"],
            default=["ADDED", "REMOVED"],
            key=f"replanning_change_filter_{result.schedule.schedule_id}",
        )
        displayed = changes.loc[
            changes["change_type"].isin(selected_changes)
        ]
        if displayed.empty:
            st.info(
                "Brak rekordów dla wybranych typów zmian. "
                "Zaznacz „Bez zmian”, aby zobaczyć zachowane akwizycje."
            )
        else:
            st.dataframe(
                displayed,
                width="stretch",
                hide_index=True,
                height=360,
            )

    first, second = st.columns(2)
    first.download_button(
        "Pobierz nowy harmonogram JSON",
        data=build_schedule_json(result.planning_result),
        file_name=build_schedule_download_filename(result.planning_result),
        mime="application/json",
        on_click="ignore",
        width="stretch",
    )
    second.download_button(
        "Pobierz zmiany CSV",
        data=changes.to_csv(index=False).encode("utf-8-sig"),
        file_name="replanning_changes.csv",
        mime="text/csv",
        on_click="ignore",
        width="stretch",
    )

    st.markdown("### Harmonogram wynikowy")
    render_result_tabs(result.planning_result)
