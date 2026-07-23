from __future__ import annotations

from datetime import timedelta

import streamlit as st

from app.models.enums import PlanningAlgorithm
from app.planning.profiles import DecisionProfile
from app.scenarios.disruption import build_configurable_disruption_plan
from app.services.disruption_service import DisruptionReplanningResult
from app.services.planning_service import PlanningOptions
from app.ui import (
    build_disruption_changes_dataframe,
    build_disruption_events_dataframe,
    build_disruption_metrics,
    build_schedule_download_filename,
    build_schedule_json,
)
from app.ui.app_context import (
    get_disruption_replanning_service,
    get_scenario_service,
    load_reference_schedule,
    load_scenario,
)
from app.ui.common import algorithm_display_name, combine_utc
from app.ui.page_layout import render_page_header, render_sidebar_heading
from app.ui.pages.planning import render_result_tabs, render_scenario_overview


def render_disruption_page() -> None:
    render_page_header(
        "Symulacja zakłóceń operacyjnych",
        "Konfiguruje awarię satelity, zmianę zachmurzenia i pilne "
        "zlecenie, a następnie ponownie optymalizuje harmonogram.",
        eyebrow="Odporność operacyjna",
        badges=("Awaria", "Pogoda", "Zlecenie pilne", "Replanning"),
    )

    definitions = {
        definition.scenario_id: definition
        for definition in get_scenario_service().definitions
    }

    with st.sidebar:
        render_sidebar_heading("Zakłócenie", "Zdarzenia i algorytm reakcji")
        scenario_id = st.selectbox(
            "Scenariusz",
            options=list(definitions),
            format_func=lambda value: definitions[value].name,
            key="disruption_scenario",
        )
        previous_algorithm = st.selectbox(
            "Harmonogram bazowy",
            options=["CP_SAT", "GREEDY"],
            format_func=algorithm_display_name,
            key="disruption_previous_algorithm",
        )
        replanning_algorithm = st.radio(
            "Algorytm reakcji",
            options=["HYBRID", "CP_SAT", "GREEDY"],
            format_func=algorithm_display_name,
            horizontal=True,
            key="disruption_algorithm",
        )

    try:
        scenario = load_scenario(scenario_id)
        previous_schedule = load_reference_schedule(
            scenario_id,
            previous_algorithm,
        )
    except Exception as error:
        st.error("Nie udało się wczytać scenariusza zakłócenia.")
        st.exception(error)
        return

    default_replan_at = min(
        scenario.request_set.horizon_start_utc + timedelta(hours=6),
        scenario.request_set.horizon_end_utc - timedelta(minutes=1),
    )

    with st.sidebar:
        replan_date = st.date_input(
            "Data zdarzenia [UTC]",
            value=default_replan_at.date(),
            min_value=scenario.request_set.horizon_start_utc.date(),
            max_value=scenario.request_set.horizon_end_utc.date(),
            key="disruption_date",
        )
        replan_time = st.time_input(
            "Godzina zdarzenia [UTC]",
            value=default_replan_at.time().replace(tzinfo=None),
            step=timedelta(minutes=15),
            key="disruption_time",
        )
        freeze_hours = st.slider(
            "Okno zamrożone [h]",
            min_value=0.5,
            max_value=6.0,
            value=2.0,
            step=0.5,
            key="disruption_freeze_hours",
        )

    replan_at_utc = combine_utc(replan_date, replan_time)
    frozen_until = min(
        replan_at_utc + timedelta(hours=freeze_hours),
        scenario.request_set.horizon_end_utc,
    )
    future_entries = [
        entry
        for entry in previous_schedule.active_entries
        if entry.start_utc >= frozen_until
    ]
    future_satellites = sorted(
        {entry.satellite_id for entry in future_entries}
    )

    with st.sidebar:
        st.subheader("Zdarzenia")
        include_outage = st.checkbox(
            "Awaria satelity",
            value=True,
            key="disruption_include_outage",
        )
        outage_satellite_id = st.selectbox(
            "Satelita objęty awarią",
            options=future_satellites or ["BRAK"],
            disabled=not include_outage or not future_satellites,
            key="disruption_outage_satellite",
        )

    request_by_id = {
        request.request_id: request
        for request in scenario.request_set.requests
    }
    optical_future_entries = [
        entry
        for entry in future_entries
        if entry.sensor_type.value == "OPTICAL"
        and not request_by_id[entry.request_id].is_mandatory
        and (
            not include_outage
            or entry.satellite_id != outage_satellite_id
        )
    ]
    optical_ids = [entry.opportunity_id for entry in optical_future_entries]
    optical_by_id = {
        entry.opportunity_id: entry for entry in optical_future_entries
    }

    with st.sidebar:
        include_weather = st.checkbox(
            "Pogorszenie zachmurzenia",
            value=bool(optical_ids),
            disabled=not optical_ids,
            key="disruption_include_weather",
        )
        weather_opportunity_id = st.selectbox(
            "Przyszła akwizycja optyczna",
            options=optical_ids or ["BRAK"],
            format_func=lambda opportunity_id: (
                opportunity_id
                if opportunity_id == "BRAK"
                else (
                    f"{opportunity_id} · "
                    f"{optical_by_id[opportunity_id].satellite_id} · "
                    f"{optical_by_id[opportunity_id].start_utc.strftime('%H:%M')}"
                )
            ),
            disabled=not include_weather or not optical_ids,
            key="disruption_weather_opportunity",
        )
        include_urgent = st.checkbox(
            "Nowe pilne zlecenie",
            value=True,
            key="disruption_include_urgent",
        )
        urgent_priority = st.slider(
            "Priorytet pilnego zlecenia",
            min_value=1,
            max_value=10,
            value=10,
            disabled=not include_urgent,
            key="disruption_urgent_priority",
        )
        cp_sat_time_limit = st.select_slider(
            "Limit CP-SAT",
            options=[1.0, 2.0, 5.0, 10.0, 30.0],
            value=10.0,
            format_func=lambda value: f"{value:g} s",
            key="disruption_cp_limit",
        )
        submitted = st.button(
            "Zastosuj zdarzenia i przeplanuj",
            type="primary",
            width="stretch",
            key="run_disruption",
        )

    render_scenario_overview(scenario)
    st.caption(
        f"Zdarzenie: {replan_at_utc.isoformat()} · "
        f"koniec okna zamrożonego: {frozen_until.isoformat()}"
    )

    if submitted:
        try:
            plan = build_configurable_disruption_plan(
                scenario=scenario,
                previous_schedule=previous_schedule,
                replan_at_utc=replan_at_utc,
                freeze_duration=timedelta(hours=freeze_hours),
                include_outage=include_outage,
                outage_satellite_id=(
                    outage_satellite_id if include_outage else None
                ),
                include_weather=include_weather,
                weather_opportunity_id=(
                    weather_opportunity_id if include_weather else None
                ),
                include_urgent_request=include_urgent,
                urgent_priority=urgent_priority,
            )
            options = PlanningOptions(
                algorithm=PlanningAlgorithm(replanning_algorithm),
                decision_profile=(
                    DecisionProfile.BALANCED
                    if replanning_algorithm == PlanningAlgorithm.HYBRID.value
                    else DecisionProfile.CUSTOM
                ),
                memory_reserve_ratio=0.0,
                cp_sat_time_limit_s=float(cp_sat_time_limit),
                cp_sat_num_search_workers=1,
                cp_sat_force_mandatory_requests=True,
            )
            with st.spinner("Stosowanie zdarzeń i optymalizacja..."):
                result = get_disruption_replanning_service().run(
                    scenario=scenario,
                    previous_schedule=previous_schedule,
                    plan=plan,
                    options=options,
                    replan_at_utc=replan_at_utc,
                    freeze_duration=timedelta(hours=freeze_hours),
                )
            st.session_state["disruption_result"] = result
            st.success("Reakcja na zakłócenie została obliczona.")
        except Exception as error:
            st.session_state.pop("disruption_result", None)
            st.error("Nie udało się przeplanować po zakłóceniu.")
            st.exception(error)

    result = st.session_state.get("disruption_result")

    if result is None:
        st.info("Skonfiguruj zdarzenia i uruchom symulację.")
        return

    if not isinstance(result, DisruptionReplanningResult):
        st.session_state.pop("disruption_result", None)
        st.error("Stan aplikacji zawiera niepoprawny wynik zakłócenia.")
        return

    render_disruption_result(result)


def render_disruption_result(
    result: DisruptionReplanningResult,
) -> None:
    metrics = build_disruption_metrics(result)

    st.divider()
    st.subheader("Wynik reakcji na zakłócenie")

    first_row = st.columns(6)
    first_row[0].metric("Status solvera", metrics.solver_status)
    first_row[1].metric("Status harmonogramu", metrics.schedule_status)
    first_row[2].metric(
        "Nowa funkcja celu",
        f"{metrics.new_objective_value:.3f}",
        delta=f"{metrics.objective_delta:+.3f}",
    )
    first_row[3].metric("Dodane", metrics.added_count)
    first_row[4].metric("Usunięte", metrics.removed_count)
    first_row[5].metric("Bez zmian", metrics.unchanged_count)

    second_row = st.columns(6)
    second_row[0].metric(
        "Awaria — unieważnione",
        metrics.outage_invalidated_count,
    )
    second_row[1].metric(
        "Pogoda — unieważnione",
        metrics.weather_invalidated_count,
    )
    second_row[2].metric(
        "Utracone wcześniejsze wybory",
        metrics.invalidated_previous_selection_count,
    )
    second_row[3].metric(
        "Pilne zlecenia",
        metrics.added_urgent_request_count,
    )
    second_row[4].metric(
        "Zrealizowane",
        f"{metrics.fully_satisfied_requests}/{metrics.total_active_requests}",
    )
    second_row[5].metric(
        "Obowiązkowe",
        f"{metrics.mandatory_satisfied_requests}/{metrics.mandatory_requests}",
    )

    event_dataframe = build_disruption_events_dataframe(result)
    change_dataframe = build_disruption_changes_dataframe(result)

    events_tab, changes_tab = st.tabs(["Zdarzenia", "Zmiany harmonogramu"])

    with events_tab:
        st.dataframe(
            event_dataframe,
            width="stretch",
            hide_index=True,
        )

    with changes_tab:
        if change_dataframe.empty:
            st.info("Zakłócenie nie zmieniło przyszłych akwizycji.")
        else:
            st.dataframe(
                change_dataframe,
                width="stretch",
                hide_index=True,
                height=400,
            )

    downloads = st.columns(3)
    downloads[0].download_button(
        "Pobierz harmonogram JSON",
        data=build_schedule_json(result.replanning_result.planning_result),
        file_name=build_schedule_download_filename(
            result.replanning_result.planning_result
        ),
        mime="application/json",
        on_click="ignore",
        width="stretch",
    )
    downloads[1].download_button(
        "Pobierz zdarzenia CSV",
        data=event_dataframe.to_csv(index=False).encode("utf-8-sig"),
        file_name="disruption_events.csv",
        mime="text/csv",
        on_click="ignore",
        width="stretch",
    )
    downloads[2].download_button(
        "Pobierz zmiany CSV",
        data=change_dataframe.to_csv(index=False).encode("utf-8-sig"),
        file_name="disruption_changes.csv",
        mime="text/csv",
        on_click="ignore",
        width="stretch",
    )

    st.markdown("### Harmonogram po zakłóceniu")
    render_result_tabs(result.replanning_result.planning_result)
