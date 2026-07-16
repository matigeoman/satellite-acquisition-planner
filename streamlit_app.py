from __future__ import annotations

import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(
    __file__
).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from app.analysis.experimental_validation import (
    ExperimentalValidationConfig,
    ExperimentalValidationResult,
    ExperimentalValidationService,
)
from app.models.enums import PlanningAlgorithm
from app.schedule_loader import load_schedule
from app.scenarios.disruption import (
    build_configurable_disruption_plan,
)
from app.scenarios.experiment import DEFAULT_EXPERIMENT_PROFILES
from app.services.comparison_service import (
    PlanningComparisonResult,
    PlanningComparisonService,
)
from app.services.disruption_service import (
    DisruptionReplanningResult,
    DisruptionReplanningService,
)
from app.services.planning_service import (
    PlanningOptions,
    PlanningResult,
    PlanningService,
)
from app.services.replanning_service import (
    ReplanningResult,
    ReplanningService,
)
from app.services.scenario_service import (
    LoadedScenario,
    ScenarioService,
)
from app.ui import (
    build_comparison_gantt_figure,
    build_comparison_metrics,
    build_comparison_summary_dataframe,
    build_gantt_figure,
    build_objective_comparison_figure,
    build_percentage_display_dataframe,
    build_planning_metrics,
    build_request_comparison_dataframe,
    build_request_counts_comparison_figure,
    build_request_map_dataframe,
    build_request_map_figure,
    build_request_status_dataframe,
    build_satellite_usage_dataframe,
    build_schedule_download_filename,
    build_schedule_entries_dataframe,
    build_schedule_json,
    build_unfulfilled_requests_dataframe,
    build_disruption_changes_dataframe,
    build_disruption_events_dataframe,
    build_disruption_metrics,
    build_experiment_improvement_figure,
    build_experiment_metadata_json,
    build_experiment_objective_figure,
    build_experiment_pairs_dataframe,
    build_experiment_profile_dataframe,
    build_experiment_runs_dataframe,
    build_experiment_runtime_figure,
    build_experiment_satisfaction_figure,
    build_experiment_summary_dataframe,
    build_replanning_changes_dataframe,
    build_replanning_metrics,
    format_percent,
)


st.set_page_config(
    page_title="Satellite Acquisition Planner",
    page_icon=":material/satellite_alt:",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": (
            "Satellite Acquisition Planner — "
            "planowanie akwizycji dla sensorów "
            "SAR i optycznych."
        ),
    },
)



def apply_application_styles() -> None:
    """Ustawia czytelniejszą skalę interfejsu na monitorach Full HD i 4K."""

    st.markdown(
        """
        <style>
        /*
         * Globalna skala typografii.
         * Streamlit bazuje głównie na jednostkach rem, dlatego zmiana rozmiaru
         * elementu html zwiększa równomiernie tekst, kontrolki i odstępy.
         */
        html {
            font-size: 18px;
        }

        /*
         * Ograniczenie szerokości treści zapobiega rozciąganiu metryk i tabel
         * na całą szerokość monitora 4K.
         */
        [data-testid="stAppViewContainer"] .main .block-container {
            max-width: 1720px;
            padding-top: 2rem;
            padding-right: 2.5rem;
            padding-bottom: 3rem;
            padding-left: 2.5rem;
            margin-right: auto;
            margin-left: auto;
        }

        /*
         * Szerszy panel boczny ułatwia obsługę formularzy i suwaków.
         */
        [data-testid="stSidebar"] {
            min-width: 350px;
            max-width: 350px;
        }

        [data-testid="stSidebar"] > div:first-child {
            width: 350px;
        }

        /*
         * Nagłówki i zwykły tekst.
         */
        h1 {
            font-size: 2.35rem !important;
            line-height: 1.18 !important;
            margin-bottom: 0.75rem !important;
        }

        h2 {
            font-size: 1.75rem !important;
            line-height: 1.25 !important;
            margin-top: 1.5rem !important;
        }

        h3 {
            font-size: 1.35rem !important;
            line-height: 1.3 !important;
        }

        p,
        li,
        label,
        [data-testid="stMarkdownContainer"] {
            font-size: 1rem;
            line-height: 1.55;
        }

        [data-testid="stCaptionContainer"] {
            font-size: 0.92rem;
            line-height: 1.45;
        }

        /*
         * Metryki na dashboardach.
         */
        [data-testid="stMetricLabel"] {
            font-size: 0.95rem;
        }

        [data-testid="stMetricValue"] {
            font-size: 2rem;
            line-height: 1.15;
        }

        [data-testid="stMetricDelta"] {
            font-size: 0.9rem;
        }

        /*
         * Formularze i kontrolki.
         */
        [data-testid="stWidgetLabel"] p,
        [data-testid="stRadio"] label,
        [data-testid="stCheckbox"] label {
            font-size: 0.98rem !important;
        }

        input,
        textarea,
        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div {
            min-height: 2.65rem;
            font-size: 1rem !important;
        }

        [data-testid="stButton"] button,
        [data-testid="stDownloadButton"] button,
        [data-testid="baseButton-primary"],
        [data-testid="baseButton-secondary"] {
            min-height: 2.75rem;
            padding: 0.55rem 1rem;
            font-size: 1rem !important;
            font-weight: 600;
        }

        /*
         * Czytelniejsze zakładki, alerty i ekspandery.
         */
        [data-baseweb="tab"] {
            min-height: 3rem;
            font-size: 1rem;
        }

        [data-testid="stAlertContainer"] {
            font-size: 0.98rem;
        }

        [data-testid="stExpander"] summary {
            font-size: 1rem;
            min-height: 2.75rem;
        }

        /*
         * Tabele i ramki danych.
         */
        [data-testid="stDataFrame"] {
            font-size: 0.95rem;
        }

        /*
         * Na bardzo szerokich ekranach zwiększamy skalę jeszcze nieznacznie.
         */
        @media (min-width: 2200px) {
            html {
                font-size: 20px;
            }

            [data-testid="stAppViewContainer"] .main .block-container {
                max-width: 1840px;
            }

            [data-testid="stSidebar"] {
                min-width: 380px;
                max-width: 380px;
            }

            [data-testid="stSidebar"] > div:first-child {
                width: 380px;
            }
        }

        /*
         * Na mniejszych ekranach zachowujemy miejsce na treść.
         */
        @media (max-width: 1100px) {
            html {
                font-size: 16px;
            }

            [data-testid="stAppViewContainer"] .main .block-container {
                padding-right: 1.25rem;
                padding-left: 1.25rem;
            }

            [data-testid="stSidebar"] {
                min-width: 300px;
                max-width: 300px;
            }

            [data-testid="stSidebar"] > div:first-child {
                width: 300px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource(
    scope="session",
    show_spinner=False,
)
def get_scenario_service() -> ScenarioService:
    return ScenarioService(
        project_root=PROJECT_ROOT
    )


@st.cache_resource(
    scope="session",
    show_spinner=False,
)
def get_planning_service() -> PlanningService:
    return PlanningService()


@st.cache_resource(
    scope="session",
    show_spinner=False,
)
def get_comparison_service() -> PlanningComparisonService:
    return PlanningComparisonService(
        planning_service=get_planning_service()
    )


@st.cache_resource(
    scope="session",
    show_spinner=False,
)
def get_replanning_service() -> ReplanningService:
    return ReplanningService(
        planning_service=get_planning_service()
    )


@st.cache_resource(
    scope="session",
    show_spinner=False,
)
def get_disruption_replanning_service() -> DisruptionReplanningService:
    return DisruptionReplanningService(
        replanning_service=get_replanning_service()
    )


@st.cache_resource(
    scope="session",
    show_spinner=False,
)
def get_experimental_validation_service() -> ExperimentalValidationService:
    return ExperimentalValidationService(
        comparison_service=get_comparison_service()
    )


@st.cache_resource(
    scope="session",
    show_spinner=False,
)
def load_reference_schedule(
    scenario_id: str,
    algorithm_value: str,
):
    return load_schedule(
        reference_schedule_path(
            scenario_id=scenario_id,
            algorithm_value=algorithm_value,
        )
    )


@st.cache_resource(
    scope="session",
    show_spinner=False,
)
def load_scenario(
    scenario_id: str,
) -> LoadedScenario:
    return get_scenario_service().load(
        scenario_id
    )


def main() -> None:
    apply_application_styles()

    st.title(
        "Satellite Acquisition Planner"
    )

    st.caption(
        "Operacyjne planowanie, przeplanowanie i walidacja "
        "akwizycji satelitarnych SAR oraz optycznych"
    )

    with st.sidebar:
        st.subheader("Moduł aplikacji")
        page = st.radio(
            "Nawigacja",
            options=[
                "Planowanie",
                "Dynamiczne przeplanowanie",
                "Zakłócenia",
                "Eksperymenty",
            ],
            label_visibility="collapsed",
        )
        st.divider()

    if page == "Planowanie":
        render_planning_page()
    elif page == "Dynamiczne przeplanowanie":
        render_replanning_page()
    elif page == "Zakłócenia":
        render_disruption_page()
    else:
        render_experiments_page()


def render_planning_page() -> None:
    st.header("Planowanie i porównanie algorytmów")

    scenario_service = (
        get_scenario_service()
    )

    definitions_by_id = {
        definition.scenario_id: definition
        for definition
        in scenario_service.definitions
    }

    (
        submitted,
        comparison_mode,
        scenario_id,
        _algorithm,
        options,
    ) = render_sidebar_form(
        definitions_by_id
    )

    try:
        selected_scenario = load_scenario(
            scenario_id
        )
    except Exception as error:
        st.error(
            "Nie udało się załadować scenariusza."
        )

        st.exception(
            error
        )

        st.stop()

    render_scenario_overview(
        selected_scenario
    )

    if submitted:
        if comparison_mode:
            run_comparison(
                scenario=selected_scenario,
                options=options,
            )
        else:
            run_planning(
                scenario=selected_scenario,
                options=options,
            )

    if comparison_mode:
        comparison = st.session_state.get(
            "comparison_result"
        )

        if comparison is None:
            st.info(
                "Uruchom porównanie Greedy i CP-SAT "
                "z panelu bocznego."
            )
            return

        if not isinstance(
            comparison,
            PlanningComparisonResult,
        ):
            st.session_state.pop(
                "comparison_result",
                None,
            )
            st.error(
                "Stan aplikacji zawiera niepoprawne porównanie."
            )
            return

        render_comparison_result(
            comparison
        )
        return

    result = st.session_state.get(
        "planning_result"
    )

    if result is None:
        st.info(
            "Skonfiguruj parametry w panelu bocznym "
            "i uruchom planowanie."
        )

        return

    if not isinstance(
        result,
        PlanningResult,
    ):
        st.session_state.pop(
            "planning_result",
            None,
        )

        st.error(
            "Stan aplikacji zawiera niepoprawny wynik."
        )

        return

    render_planning_result(
        result
    )



def render_replanning_page() -> None:
    st.header("Dynamiczne przeplanowanie")
    st.write(
        "Zachowuje akwizycje już wykonane i znajdujące się w "
        "oknie zamrożonym, a pozostałą część horyzontu planuje ponownie."
    )

    definitions = {
        definition.scenario_id: definition
        for definition in get_scenario_service().definitions
    }

    with st.sidebar:
        st.header("Parametry przeplanowania")
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
            options=["CP_SAT", "GREEDY"],
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


def render_disruption_page() -> None:
    st.header("Symulacja zakłóceń operacyjnych")
    st.write(
        "Konfiguruje awarię satelity, zmianę zachmurzenia i pilne "
        "zlecenie, a następnie ponownie optymalizuje harmonogram."
    )

    definitions = {
        definition.scenario_id: definition
        for definition in get_scenario_service().definitions
    }

    with st.sidebar:
        st.header("Parametry zakłócenia")
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
            options=["CP_SAT", "GREEDY"],
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


def render_experiments_page() -> None:
    st.header("Walidacja eksperymentalna Greedy i CP-SAT")
    st.write(
        "Uruchamia powtarzalne warianty scenariusza stresowego i "
        "porównuje jakość harmonogramu z czasem obliczeń."
    )

    profile_by_id = {
        profile.profile_id: profile
        for profile in DEFAULT_EXPERIMENT_PROFILES
    }

    with st.sidebar:
        st.header("Parametry eksperymentu")
        selected_profile_ids = st.multiselect(
            "Profile degradacji",
            options=list(profile_by_id),
            default=list(profile_by_id),
            format_func=lambda value: profile_by_id[value].name,
            key="experiment_profiles",
        )
        repetitions = st.slider(
            "Powtórzenia na profil",
            min_value=1,
            max_value=10,
            value=3,
            step=1,
            key="experiment_repetitions",
        )
        cp_sat_time_limit = st.select_slider(
            "Limit CP-SAT na przebieg",
            options=[0.5, 1.0, 2.0, 5.0, 10.0],
            value=2.0,
            format_func=lambda value: f"{value:g} s",
            key="experiment_cp_limit",
        )
        base_seed = st.number_input(
            "Ziarno bazowe",
            min_value=0,
            value=20260720,
            step=1,
            key="experiment_seed",
        )
        memory_reserve_percent = st.slider(
            "Rezerwa pamięci",
            min_value=0,
            max_value=50,
            value=15,
            step=1,
            format="%d%%",
            key="experiment_memory_reserve",
        )
        estimated_solver_time = (
            len(selected_profile_ids)
            * repetitions
            * cp_sat_time_limit
        )
        st.caption(
            "Szacowany minimalny czas solvera CP-SAT: "
            f"około {estimated_solver_time:.1f} s."
        )
        submitted = st.button(
            "Uruchom eksperyment",
            type="primary",
            width="stretch",
            key="run_experiment",
        )

    scenario = load_scenario("STRESS")
    render_scenario_overview(scenario)

    if submitted:
        if not selected_profile_ids:
            st.error("Wybierz co najmniej jeden profil degradacji.")
        else:
            try:
                config = ExperimentalValidationConfig(
                    profiles=tuple(
                        profile_by_id[profile_id]
                        for profile_id in selected_profile_ids
                    ),
                    repetitions=repetitions,
                    base_seed=int(base_seed),
                    memory_reserve_ratio=(
                        memory_reserve_percent / 100.0
                    ),
                    cp_sat_time_limit_s=float(cp_sat_time_limit),
                    cp_sat_num_search_workers=1,
                )
                run_count = len(config.profiles) * config.repetitions * 2
                with st.spinner(
                    f"Uruchamianie {run_count} przebiegów planerów..."
                ):
                    result = get_experimental_validation_service().run(
                        base_scenario=scenario,
                        config=config,
                    )
                st.session_state["experimental_validation_result"] = result
                st.success("Walidacja eksperymentalna zakończona.")
            except Exception as error:
                st.session_state.pop(
                    "experimental_validation_result",
                    None,
                )
                st.error("Eksperyment zakończył się błędem.")
                st.exception(error)

    result = st.session_state.get("experimental_validation_result")

    if result is None:
        st.info("Wybierz profile i uruchom eksperyment.")
        return

    if not isinstance(result, ExperimentalValidationResult):
        st.session_state.pop("experimental_validation_result", None)
        st.error("Stan aplikacji zawiera niepoprawny wynik eksperymentu.")
        return

    render_experimental_validation_result(result)


def render_experimental_validation_result(
    result: ExperimentalValidationResult,
) -> None:
    st.divider()
    st.subheader("Wyniki walidacji")

    pair_count = len(result.pair_records)
    metrics = st.columns(5)
    metrics[0].metric("Porównania", pair_count)
    metrics[1].metric(
        "CP-SAT lepszy",
        f"{result.cp_sat_better_objective_count}/{pair_count}",
    )
    metrics[2].metric(
        "CP-SAT nie gorszy",
        f"{result.cp_sat_not_worse_objective_count}/{pair_count}",
    )
    metrics[3].metric(
        "Średnia poprawa celu",
        f"{result.mean_objective_improvement_pct:+.2f}%",
    )
    metrics[4].metric(
        "Czas eksperymentu",
        f"{result.wall_clock_runtime_s:.2f} s",
    )

    profile_dataframe = build_experiment_profile_dataframe(result)
    summary_dataframe = build_experiment_summary_dataframe(result)
    pair_dataframe = build_experiment_pairs_dataframe(result)
    run_dataframe = build_experiment_runs_dataframe(result)

    charts_tab, summary_tab, runs_tab, export_tab = st.tabs(
        ["Wykresy", "Podsumowanie", "Przebiegi", "Eksport"]
    )

    result_key = result.started_at_utc.strftime("%Y%m%d%H%M%S%f")

    with charts_tab:
        first, second = st.columns(2)
        first.plotly_chart(
            build_experiment_objective_figure(result),
            width="stretch",
            key=f"experiment_objective_{result_key}",
            config={"displaylogo": False},
        )
        second.plotly_chart(
            build_experiment_satisfaction_figure(result),
            width="stretch",
            key=f"experiment_satisfaction_{result_key}",
            config={"displaylogo": False},
        )
        third, fourth = st.columns(2)
        third.plotly_chart(
            build_experiment_runtime_figure(result),
            width="stretch",
            key=f"experiment_runtime_{result_key}",
            config={"displaylogo": False},
        )
        fourth.plotly_chart(
            build_experiment_improvement_figure(result),
            width="stretch",
            key=f"experiment_improvement_{result_key}",
            config={"displaylogo": False},
        )

    with summary_tab:
        st.markdown("### Wynik według profilu")
        st.dataframe(
            profile_dataframe,
            width="stretch",
            hide_index=True,
        )
        st.markdown("### Statystyki algorytmów")
        st.dataframe(
            summary_dataframe,
            width="stretch",
            hide_index=True,
            height=360,
        )

    with runs_tab:
        st.markdown("### Porównania parami")
        st.dataframe(
            pair_dataframe,
            width="stretch",
            hide_index=True,
            height=360,
        )
        with st.expander("Wszystkie pojedyncze przebiegi"):
            st.dataframe(
                run_dataframe,
                width="stretch",
                hide_index=True,
                height=420,
            )

    with export_tab:
        downloads = st.columns(4)
        downloads[0].download_button(
            "Podsumowanie CSV",
            data=summary_dataframe.to_csv(index=False).encode("utf-8-sig"),
            file_name="experimental_validation_summary.csv",
            mime="text/csv",
            on_click="ignore",
            width="stretch",
        )
        downloads[1].download_button(
            "Porównania CSV",
            data=pair_dataframe.to_csv(index=False).encode("utf-8-sig"),
            file_name="experimental_validation_pairs.csv",
            mime="text/csv",
            on_click="ignore",
            width="stretch",
        )
        downloads[2].download_button(
            "Przebiegi CSV",
            data=run_dataframe.to_csv(index=False).encode("utf-8-sig"),
            file_name="experimental_validation_runs.csv",
            mime="text/csv",
            on_click="ignore",
            width="stretch",
        )
        downloads[3].download_button(
            "Metadane JSON",
            data=build_experiment_metadata_json(result),
            file_name="experimental_validation_metadata.json",
            mime="application/json",
            on_click="ignore",
            width="stretch",
        )


def reference_schedule_path(
    *,
    scenario_id: str,
    algorithm_value: str,
) -> Path:
    normalized_scenario = scenario_id.strip().upper()
    normalized_algorithm = algorithm_value.strip().upper()

    if normalized_scenario == "EXAMPLE":
        scenario_prefix = "example_schedule"
    elif normalized_scenario == "STRESS":
        scenario_prefix = "stress_schedule"
    else:
        raise ValueError(f"Nieobsługiwany scenariusz: {scenario_id}")

    if normalized_algorithm not in {"GREEDY", "CP_SAT"}:
        raise ValueError(f"Nieobsługiwany algorytm: {algorithm_value}")

    return (
        PROJECT_ROOT
        / "data"
        / f"{scenario_prefix}_{normalized_algorithm.lower()}.json"
    )


def combine_utc(selected_date, selected_time: time) -> datetime:
    return datetime.combine(
        selected_date,
        selected_time.replace(tzinfo=None),
    ).replace(tzinfo=timezone.utc)



def render_sidebar_form(
    definitions_by_id,
) -> tuple[
    bool,
    bool,
    str,
    PlanningAlgorithm,
    PlanningOptions,
]:
    with st.sidebar:
        st.header(
            "Konfiguracja planowania"
        )

        with st.form(
            "planning_configuration",
            clear_on_submit=False,
            border=True,
        ):
            scenario_id = st.selectbox(
                "Scenariusz",
                options=list(
                    definitions_by_id
                ),
                format_func=lambda identifier: (
                    definitions_by_id[
                        identifier
                    ].name
                ),
                help=(
                    "Wybierz zestaw zleceń, okazji "
                    "akwizycyjnych i ograniczeń systemu."
                ),
            )

            comparison_mode = st.checkbox(
                "Porównaj Greedy i CP-SAT",
                value=False,
                help=(
                    "Uruchamia oba algorytmy z tymi samymi "
                    "wagami i ograniczeniami."
                ),
            )

            algorithm_value = st.radio(
                "Algorytm pojedynczy",
                options=[
                    PlanningAlgorithm.GREEDY.value,
                    PlanningAlgorithm.CP_SAT.value,
                ],
                format_func=algorithm_display_name,
                horizontal=True,
            )

            memory_reserve_percent = st.slider(
                "Rezerwa pamięci",
                min_value=0,
                max_value=50,
                value=15,
                step=1,
                format="%d%%",
                help=(
                    "Część pamięci pokładowej wyłączona "
                    "z bieżącego planowania."
                ),
            )

            st.caption(
                "W trybie porównania wybór algorytmu "
                "pojedynczego jest ignorowany."
            )

            st.divider()

            st.subheader(
                "Parametry CP-SAT"
            )

            cp_sat_time_limit_s = (
                st.select_slider(
                    "Limit czasu solvera",
                    options=[
                        1.0,
                        5.0,
                        10.0,
                        30.0,
                    ],
                    value=10.0,
                    format_func=lambda value: (
                        f"{value:g} s"
                    ),
                )
            )

            cp_sat_num_search_workers = (
                st.number_input(
                    "Liczba wątków solvera",
                    min_value=1,
                    max_value=16,
                    value=1,
                    step=1,
                    help=(
                        "Jeden wątek zapewnia najbardziej "
                        "powtarzalny benchmark."
                    ),
                )
            )

            cp_sat_force_mandatory_requests = (
                st.checkbox(
                    "Wymuś realizację zleceń obowiązkowych",
                    value=True,
                )
            )

            with st.expander(
                "Wagi funkcji celu"
            ):
                priority_weight = st.number_input(
                    "Waga priorytetu",
                    min_value=0.0,
                    value=10.0,
                    step=1.0,
                )

                quality_weight = st.number_input(
                    "Waga jakości",
                    min_value=0.0,
                    value=3.0,
                    step=0.5,
                )

                coverage_weight = st.number_input(
                    "Waga pokrycia",
                    min_value=0.0,
                    value=2.0,
                    step=0.5,
                )

                mandatory_bonus = st.number_input(
                    "Premia za zlecenie obowiązkowe",
                    min_value=0.0,
                    value=100.0,
                    step=10.0,
                )

                dual_optional_second_bonus = (
                    st.number_input(
                        "Premia za drugi sensor DUAL_OPTIONAL",
                        min_value=0.0,
                        value=5.0,
                        step=1.0,
                    )
                )

            submitted = st.form_submit_button(
                "Uruchom planowanie",
                type="primary",
            )

        selected_definition = (
            definitions_by_id[
                scenario_id
            ]
        )

        st.caption(
            selected_definition.description
        )

    algorithm = PlanningAlgorithm(
        algorithm_value
    )

    options = PlanningOptions(
        algorithm=algorithm,
        memory_reserve_ratio=(
            memory_reserve_percent
            / 100.0
        ),
        priority_weight=float(
            priority_weight
        ),
        quality_weight=float(
            quality_weight
        ),
        coverage_weight=float(
            coverage_weight
        ),
        mandatory_bonus=float(
            mandatory_bonus
        ),
        dual_optional_second_bonus=float(
            dual_optional_second_bonus
        ),
        cp_sat_time_limit_s=float(
            cp_sat_time_limit_s
        ),
        cp_sat_num_search_workers=int(
            cp_sat_num_search_workers
        ),
        cp_sat_force_mandatory_requests=(
            cp_sat_force_mandatory_requests
        ),
    )

    return (
        submitted,
        comparison_mode,
        scenario_id,
        algorithm,
        options,
    )


def run_planning(
    *,
    scenario: LoadedScenario,
    options: PlanningOptions,
) -> None:
    planning_service = (
        get_planning_service()
    )

    algorithm_name = (
        algorithm_display_name(
            options.algorithm.value
        )
    )

    try:
        with st.spinner(
            f"Uruchamianie {algorithm_name}..."
        ):
            result = planning_service.run(
                scenario=scenario,
                options=options,
            )

        st.session_state[
            "planning_result"
        ] = result

        st.session_state.pop(
            "comparison_result",
            None,
        )

        st.success(
            "Planowanie zakończone."
        )

    except Exception as error:
        st.session_state.pop(
            "planning_result",
            None,
        )

        st.error(
            "Planowanie zakończyło się błędem."
        )

        st.exception(
            error
        )



def run_comparison(
    *,
    scenario: LoadedScenario,
    options: PlanningOptions,
) -> None:
    comparison_service = (
        get_comparison_service()
    )

    try:
        with st.spinner(
            "Uruchamianie Greedy i CP-SAT..."
        ):
            comparison = comparison_service.run(
                scenario=scenario,
                options=options,
            )

        st.session_state[
            "comparison_result"
        ] = comparison

        st.session_state.pop(
            "planning_result",
            None,
        )

        st.success(
            "Porównanie algorytmów zakończone."
        )

    except Exception as error:
        st.session_state.pop(
            "comparison_result",
            None,
        )

        st.error(
            "Porównanie zakończyło się błędem."
        )

        st.exception(
            error
        )


def render_comparison_result(
    comparison: PlanningComparisonResult,
) -> None:
    metrics = build_comparison_metrics(
        comparison
    )

    st.divider()
    st.subheader(
        "Porównanie Greedy vs CP-SAT"
    )

    first_row = st.columns(6)

    first_row[0].metric(
        "Funkcja celu CP-SAT",
        f"{metrics.cp_sat_objective:.3f}",
        delta=(
            f"{metrics.objective_difference:+.3f} "
            "vs Greedy"
        ),
    )

    first_row[1].metric(
        "Poprawa celu",
        f"{metrics.objective_improvement_pct:.2f}%",
    )

    first_row[2].metric(
        "Zrealizowane CP-SAT",
        metrics.cp_sat_fully_satisfied,
        delta=(
            f"{metrics.fully_satisfied_difference:+d}"
        ),
    )

    first_row[3].metric(
        "Nieprzypisane CP-SAT",
        metrics.cp_sat_unassigned,
        delta=(
            f"{-metrics.unassigned_reduction:+d}"
        ),
        delta_color="inverse",
    )

    first_row[4].metric(
        "Akwizycje CP-SAT",
        metrics.cp_sat_acquisitions,
        delta=(
            f"{metrics.acquisition_difference:+d}"
        ),
    )

    first_row[5].metric(
        "Status CP-SAT",
        metrics.cp_sat_solver_status,
    )

    second_row = st.columns(4)

    second_row[0].metric(
        "Cel Greedy",
        f"{metrics.greedy_objective:.3f}",
    )

    second_row[1].metric(
        "Zrealizowane Greedy",
        metrics.greedy_fully_satisfied,
    )

    second_row[2].metric(
        "Czas Greedy",
        f"{metrics.greedy_runtime_s:.4f} s",
    )

    second_row[3].metric(
        "Czas CP-SAT",
        f"{metrics.cp_sat_runtime_s:.3f} s",
    )

    st.caption(
        f"Scenariusz: {comparison.scenario.name} · "
        f"łączny czas porównania: "
        f"{comparison.wall_clock_runtime_s:.3f} s"
    )

    render_comparison_tabs(
        comparison
    )


def render_comparison_tabs(
    comparison: PlanningComparisonResult,
) -> None:
    (
        summary_tab,
        requests_tab,
        gantt_tab,
        export_tab,
    ) = st.tabs(
        [
            "Podsumowanie",
            "Różnice zleceń",
            "Gantt porównawczy",
            "Eksport porównania",
        ]
    )

    summary_dataframe = (
        build_comparison_summary_dataframe(
            comparison
        )
    )

    request_dataframe = (
        build_request_comparison_dataframe(
            comparison
        )
    )

    comparison_key = (
        comparison.scenario.scenario_id
    )

    with summary_tab:
        first_chart, second_chart = st.columns(2)

        with first_chart:
            st.plotly_chart(
                build_objective_comparison_figure(
                    comparison
                ),
                width="stretch",
                key=(
                    "comparison_objective_"
                    f"{comparison_key}"
                ),
                config={
                    "displaylogo": False,
                },
            )

        with second_chart:
            st.plotly_chart(
                build_request_counts_comparison_figure(
                    comparison
                ),
                width="stretch",
                key=(
                    "comparison_requests_"
                    f"{comparison_key}"
                ),
                config={
                    "displaylogo": False,
                },
            )

        st.markdown(
            "### Zestawienie KPI"
        )

        summary_display_dataframe = (
            build_percentage_display_dataframe(
                summary_dataframe,
                ["satisfaction_ratio"],
            )
        )

        st.dataframe(
            summary_display_dataframe,
            width="stretch",
            hide_index=True,
            column_config={
                "objective_value": (
                    st.column_config.NumberColumn(
                        "Funkcja celu",
                        format="%.3f",
                    )
                ),
                "satisfaction_ratio": (
                    st.column_config.ProgressColumn(
                        "Realizacja",
                        min_value=0.0,
                        max_value=100.0,
                        format="%.1f%%",
                    )
                ),
                "solver_runtime_s": (
                    st.column_config.NumberColumn(
                        "Czas solvera [s]",
                        format="%.4f",
                    )
                ),
                "wall_clock_runtime_s": (
                    st.column_config.NumberColumn(
                        "Czas usługi [s]",
                        format="%.4f",
                    )
                ),
            },
        )

    with requests_tab:
        st.markdown(
            "### Zlecenia różniące wyniki algorytmów"
        )

        outcome_options = sorted(
            request_dataframe[
                "status_outcome"
            ].unique()
        )

        relation_options = sorted(
            request_dataframe[
                "selection_relation"
            ].unique()
        )

        first_filter, second_filter, third_filter = (
            st.columns(
                [
                    3,
                    3,
                    2,
                ]
            )
        )

        with first_filter:
            selected_outcomes = st.multiselect(
                "Porównanie statusu",
                options=outcome_options,
                default=[
                    outcome
                    for outcome in outcome_options
                    if outcome != "SAME_STATUS"
                ],
                key=(
                    "comparison_outcomes_"
                    f"{comparison_key}"
                ),
            )

        with second_filter:
            selected_relations = st.multiselect(
                "Relacja wyboru okazji",
                options=relation_options,
                default=[
                    relation
                    for relation in relation_options
                    if relation
                    not in {
                        "BOTH_SAME",
                        "NEITHER",
                    }
                ],
                key=(
                    "comparison_relations_"
                    f"{comparison_key}"
                ),
            )

        with third_filter:
            mandatory_only = st.checkbox(
                "Tylko obowiązkowe",
                value=False,
                key=(
                    "comparison_mandatory_"
                    f"{comparison_key}"
                ),
            )

        displayed_requests = request_dataframe.loc[
            (
                request_dataframe[
                    "status_outcome"
                ].isin(
                    selected_outcomes
                )
            )
            | (
                request_dataframe[
                    "selection_relation"
                ].isin(
                    selected_relations
                )
            )
        ]

        if mandatory_only:
            displayed_requests = displayed_requests.loc[
                displayed_requests[
                    "is_mandatory"
                ]
            ]

        if displayed_requests.empty:
            st.info(
                "Brak zleceń spełniających filtry."
            )
        else:
            st.dataframe(
                displayed_requests,
                width="stretch",
                height=520,
                hide_index=True,
            )

        st.caption(
            "CP_SAT_BETTER oznacza wyższy poziom "
            "realizacji zlecenia. BOTH_DIFFERENT "
            "oznacza, że oba algorytmy wybrały zlecenie, "
            "ale użyły innych okazji akwizycyjnych."
        )

    with gantt_tab:
        st.markdown(
            "### Harmonogramy na wspólnej osi czasu"
        )

        st.plotly_chart(
            build_comparison_gantt_figure(
                comparison
            ),
            width="stretch",
            key=(
                "comparison_gantt_"
                f"{comparison_key}"
            ),
            config={
                "displaylogo": False,
                "scrollZoom": True,
            },
        )

    with export_tab:
        st.markdown(
            "### Eksport porównania"
        )

        summary_csv = summary_dataframe.to_csv(
            index=False
        ).encode(
            "utf-8-sig"
        )

        requests_csv = request_dataframe.to_csv(
            index=False
        ).encode(
            "utf-8-sig"
        )

        first, second = st.columns(2)

        with first:
            st.download_button(
                "Pobierz KPI porównania CSV",
                data=summary_csv,
                file_name=(
                    "comparison_"
                    f"{comparison_key.lower()}_kpi.csv"
                ),
                mime="text/csv",
                on_click="ignore",
                width="stretch",
            )

        with second:
            st.download_button(
                "Pobierz różnice zleceń CSV",
                data=requests_csv,
                file_name=(
                    "comparison_"
                    f"{comparison_key.lower()}_requests.csv"
                ),
                mime="text/csv",
                on_click="ignore",
                width="stretch",
            )


def render_scenario_overview(
    scenario: LoadedScenario,
) -> None:
    st.subheader(
        "Scenariusz"
    )

    first, second, third, fourth = (
        st.columns(4)
    )

    first.metric(
        "Aktywne zlecenia",
        scenario.active_request_count,
    )

    second.metric(
        "Zlecenia obowiązkowe",
        scenario.mandatory_request_count,
    )

    third.metric(
        "Okazje wykonalne",
        scenario.feasible_opportunity_count,
    )

    fourth.metric(
        "Satelity",
        scenario.satellite_count,
    )

    st.caption(
        f"{scenario.name} · "
        f"horyzont "
        f"{scenario.request_set.horizon_start_utc.isoformat()} "
        f"— "
        f"{scenario.request_set.horizon_end_utc.isoformat()}"
    )


def render_planning_result(
    result: PlanningResult,
) -> None:
    metrics = build_planning_metrics(
        result
    )

    st.divider()

    st.subheader(
        "Wynik planowania"
    )

    if metrics.schedule_status == "FEASIBLE":
        st.success(
            "Harmonogram jest wykonalny."
        )
    elif metrics.schedule_status == "INFEASIBLE":
        st.warning(
            "Harmonogram nie realizuje wszystkich "
            "wymaganych zleceń obowiązkowych."
        )
    else:
        st.info(
            f"Status harmonogramu: "
            f"{metrics.schedule_status}"
        )

    first_row = st.columns(6)

    first_row[0].metric(
        "Algorytm",
        algorithm_display_name(
            metrics.algorithm
        ),
    )

    first_row[1].metric(
        "Status solvera",
        metrics.solver_status,
    )

    first_row[2].metric(
        "Funkcja celu",
        f"{metrics.objective_value:.3f}",
    )

    first_row[3].metric(
        "Zrealizowane zlecenia",
        (
            f"{metrics.fully_satisfied_requests}"
            f"/{metrics.total_active_requests}"
        ),
    )

    first_row[4].metric(
        "Akwizycje",
        metrics.total_acquisitions,
    )

    first_row[5].metric(
        "Czas solvera",
        f"{metrics.solver_runtime_s:.3f} s",
    )

    second_row = st.columns(5)

    second_row[0].metric(
        "Realizacja",
        format_percent(
            metrics.satisfaction_ratio,
            digits=1,
        ),
    )

    second_row[1].metric(
        "Obowiązkowe",
        (
            f"{metrics.mandatory_satisfied_requests}"
            f"/{metrics.mandatory_requests}"
        ),
    )

    second_row[2].metric(
        "Nieprzypisane",
        metrics.unassigned_requests,
    )

    second_row[3].metric(
        "SAR",
        metrics.sar_acquisitions,
    )

    second_row[4].metric(
        "Optyczne",
        metrics.optical_acquisitions,
    )

    st.caption(
        f"Scenariusz: {metrics.scenario_name} · "
        f"rezerwa pamięci: "
        f"{format_percent(result.schedule.memory_reserve_ratio)} · "
        f"całkowity czas usługi: "
        f"{metrics.wall_clock_runtime_s:.3f} s"
    )

    render_result_tabs(
        result
    )


def render_result_tabs(
    result: PlanningResult,
) -> None:
    (
        gantt_tab,
        map_tab,
        schedule_tab,
        requests_tab,
        satellites_tab,
        export_tab,
    ) = st.tabs(
        [
            "Gantt",
            "Mapa",
            "Harmonogram",
            "Zlecenia",
            "Satelity",
            "Eksport",
        ]
    )

    entries_dataframe = (
        build_schedule_entries_dataframe(
            result
        )
    )

    request_dataframe = (
        build_request_status_dataframe(
            result
        )
    )

    request_map_dataframe = (
        build_request_map_dataframe(
            result
        )
    )

    unfulfilled_dataframe = (
        build_unfulfilled_requests_dataframe(
            result
        )
    )

    satellite_dataframe = (
        build_satellite_usage_dataframe(
            result
        )
    )

    schedule_key = (
        result.schedule.schedule_id
    )

    with gantt_tab:
        st.markdown(
            "### Oś czasu akwizycji"
        )

        if entries_dataframe.empty:
            st.warning(
                "Harmonogram nie zawiera aktywnych akwizycji."
            )
        else:
            satellite_options = [
                satellite.satellite_id
                for satellite
                in result.scenario.catalog.satellites
            ]

            sensor_options = sorted(
                entries_dataframe[
                    "sensor_type"
                ].dropna().unique()
            )

            first_filter, second_filter, third_filter = (
                st.columns(
                    [
                        3,
                        2,
                        2,
                    ]
                )
            )

            with first_filter:
                selected_satellites = st.multiselect(
                    "Satelity",
                    options=satellite_options,
                    default=satellite_options,
                    key=(
                        "gantt_satellites_"
                        f"{schedule_key}"
                    ),
                )

            with second_filter:
                selected_sensor_types = st.multiselect(
                    "Typy sensorów",
                    options=sensor_options,
                    default=sensor_options,
                    key=(
                        "gantt_sensors_"
                        f"{schedule_key}"
                    ),
                )

            with third_filter:
                full_horizon = st.checkbox(
                    "Pełny horyzont 24 h",
                    value=False,
                    key=(
                        "gantt_full_horizon_"
                        f"{schedule_key}"
                    ),
                )

            if (
                not selected_satellites
                or not selected_sensor_types
            ):
                st.info(
                    "Wybierz co najmniej jednego satelitę "
                    "i jeden typ sensora."
                )
            else:
                figure = build_gantt_figure(
                    result,
                    satellite_ids=selected_satellites,
                    sensor_types=selected_sensor_types,
                    full_horizon=full_horizon,
                )

                st.plotly_chart(
                    figure,
                    width="stretch",
                    height="content",
                    key=(
                        "gantt_chart_"
                        f"{schedule_key}"
                    ),
                    on_select="ignore",
                    config={
                        "displaylogo": False,
                        "scrollZoom": True,
                    },
                )

                st.caption(
                    "Najedź kursorem na akwizycję, aby "
                    "wyświetlić szczegóły. Użyj dolnego "
                    "suwaka albo narzędzi powiększenia."
                )

    with map_tab:
        st.markdown(
            "### Geometrie zleceń obserwacyjnych"
        )

        status_options = sorted(
            request_map_dataframe[
                "fulfillment_status"
            ].unique()
        )

        geometry_options = sorted(
            request_map_dataframe[
                "geometry_type"
            ].unique()
        )

        first_filter, second_filter, third_filter = (
            st.columns(
                [
                    3,
                    2,
                    2,
                ]
            )
        )

        with first_filter:
            selected_statuses = st.multiselect(
                "Status realizacji",
                options=status_options,
                default=status_options,
                key=(
                    "map_statuses_"
                    f"{schedule_key}"
                ),
            )

        with second_filter:
            selected_geometry_types = st.multiselect(
                "Typ geometrii",
                options=geometry_options,
                default=geometry_options,
                key=(
                    "map_geometries_"
                    f"{schedule_key}"
                ),
            )

        with third_filter:
            mandatory_only = st.checkbox(
                "Tylko obowiązkowe",
                value=False,
                key=(
                    "map_mandatory_"
                    f"{schedule_key}"
                ),
            )

        if (
            not selected_statuses
            or not selected_geometry_types
        ):
            st.info(
                "Wybierz co najmniej jeden status "
                "i jeden typ geometrii."
            )
        else:
            map_figure = build_request_map_figure(
                result,
                fulfillment_statuses=selected_statuses,
                geometry_types=(
                    selected_geometry_types
                ),
                mandatory_only=mandatory_only,
            )

            st.plotly_chart(
                map_figure,
                width="stretch",
                height="content",
                key=(
                    "request_map_"
                    f"{schedule_key}"
                ),
                on_select="ignore",
                config={
                    "displaylogo": False,
                    "scrollZoom": True,
                },
            )

            visible_request_count = (
                map_figure.layout.meta[
                    "request_count"
                ]
            )

            st.caption(
                f"Widoczne zlecenia: "
                f"{visible_request_count}. "
                "Większy punkt oznacza zlecenie "
                "obowiązkowe, a grubsza obwódka — "
                "obowiązkowy poligon."
            )

    with schedule_tab:
        st.markdown(
            "### Zaplanowane akwizycje"
        )

        if entries_dataframe.empty:
            st.warning(
                "Harmonogram nie zawiera aktywnych akwizycji."
            )
        else:
            sensor_options = [
                "WSZYSTKIE",
                *sorted(
                    entries_dataframe[
                        "sensor_type"
                    ].unique()
                ),
            ]

            selected_sensor = st.selectbox(
                "Filtr typu sensora",
                options=sensor_options,
                key="schedule_sensor_filter",
            )

            displayed_entries = (
                entries_dataframe
                if selected_sensor == "WSZYSTKIE"
                else entries_dataframe.loc[
                    entries_dataframe[
                        "sensor_type"
                    ]
                    == selected_sensor
                ]
            )

            st.dataframe(
                displayed_entries,
                width="stretch",
                height=520,
                hide_index=True,
                column_config={
                    "duration_s": (
                        st.column_config.NumberColumn(
                            "Czas [s]",
                            format="%.3f",
                        )
                    ),
                    "estimated_data_volume_mb": (
                        st.column_config.NumberColumn(
                            "Dane [MB]",
                            format="%.3f",
                        )
                    ),
                    "objective_contribution": (
                        st.column_config.NumberColumn(
                            "Wkład do celu",
                            format="%.3f",
                        )
                    ),
                    "quality_score": (
                        st.column_config.NumberColumn(
                            "Jakość",
                            format="%.3f",
                        )
                    ),
                    "coverage_ratio": (
                        st.column_config.NumberColumn(
                            "Pokrycie",
                            format="%.3f",
                        )
                    ),
                },
            )

    with requests_tab:
        st.markdown(
            "### Realizacja zleceń"
        )

        status_options = sorted(
            request_dataframe[
                "fulfillment_status"
            ].unique()
        )

        selected_statuses = st.multiselect(
            "Status realizacji",
            options=status_options,
            default=status_options,
            key="request_status_filter",
        )

        displayed_requests = request_dataframe.loc[
            request_dataframe[
                "fulfillment_status"
            ].isin(
                selected_statuses
            )
        ]

        st.dataframe(
            displayed_requests,
            width="stretch",
            height=480,
            hide_index=True,
        )

        st.markdown(
            "### Zlecenia niezrealizowane"
        )

        if unfulfilled_dataframe.empty:
            st.success(
                "Wszystkie zlecenia zostały "
                "w pełni zrealizowane."
            )
        else:
            st.dataframe(
                unfulfilled_dataframe,
                width="stretch",
                height=320,
                hide_index=True,
            )

    with satellites_tab:
        st.markdown(
            "### Wykorzystanie zasobów satelitów"
        )

        satellite_display_dataframe = (
            build_percentage_display_dataframe(
                satellite_dataframe,
                [
                    "acquisition_utilization_ratio",
                    "imaging_utilization_ratio",
                    "memory_utilization_ratio",
                ],
            )
        )

        st.dataframe(
            satellite_display_dataframe,
            width="stretch",
            height=420,
            hide_index=True,
            column_config={
                "acquisition_utilization_ratio": (
                    st.column_config.ProgressColumn(
                        "Akwizycje",
                        min_value=0.0,
                        max_value=100.0,
                        format="%.1f%%",
                    )
                ),
                "imaging_utilization_ratio": (
                    st.column_config.ProgressColumn(
                        "Czas obrazowania",
                        min_value=0.0,
                        max_value=100.0,
                        format="%.1f%%",
                    )
                ),
                "memory_utilization_ratio": (
                    st.column_config.ProgressColumn(
                        "Pamięć",
                        min_value=0.0,
                        max_value=100.0,
                        format="%.1f%%",
                    )
                ),
            },
        )

        st.caption(
            "Wykorzystanie zasobów jest prezentowane "
            "jako procent odpowiedniego limitu."
        )

    with export_tab:
        st.markdown(
            "### Eksport wyników"
        )

        schedule_json = build_schedule_json(
            result
        )

        json_filename = (
            build_schedule_download_filename(
                result
            )
        )

        csv_filename = (
            json_filename
            .removesuffix(".json")
            + "_entries.csv"
        )

        first, second = st.columns(2)

        with first:
            st.download_button(
                "Pobierz harmonogram JSON",
                data=schedule_json,
                file_name=json_filename,
                mime="application/json",
                on_click="ignore",
                type="primary",
                width="stretch",
            )

        with second:
            st.download_button(
                "Pobierz akwizycje CSV",
                data=entries_dataframe.to_csv(
                    index=False
                ).encode(
                    "utf-8-sig"
                ),
                file_name=csv_filename,
                mime="text/csv",
                on_click="ignore",
                width="stretch",
            )

        st.markdown(
            "### Metadane"
        )

        st.json(
            {
                "schedule_id": (
                    result.schedule.schedule_id
                ),
                "scenario_id": (
                    result.scenario.scenario_id
                ),
                "algorithm": (
                    result.algorithm.value
                ),
                "solver_status": (
                    result.solver_status
                ),
                "schedule_status": (
                    result.schedule.status.value
                ),
                "objective_value": (
                    result.objective_value
                ),
                "created_at_utc": (
                    result
                    .schedule
                    .created_at_utc
                    .isoformat()
                ),
            },
            expanded=False,
        )


def algorithm_display_name(
    algorithm_value: str,
) -> str:
    if (
        algorithm_value
        == PlanningAlgorithm.GREEDY.value
    ):
        return "Greedy"

    if (
        algorithm_value
        == PlanningAlgorithm.CP_SAT.value
    ):
        return "CP-SAT"

    return algorithm_value.replace(
        "_",
        "-",
    )


if __name__ == "__main__":
    main()
