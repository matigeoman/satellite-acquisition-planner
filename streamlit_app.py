from __future__ import annotations

import sys
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


from app.models.enums import PlanningAlgorithm
from app.services.planning_service import (
    PlanningOptions,
    PlanningResult,
    PlanningService,
)
from app.services.scenario_service import (
    LoadedScenario,
    ScenarioService,
)
from app.ui import (
    build_gantt_figure,
    build_planning_metrics,
    build_request_map_dataframe,
    build_request_map_figure,
    build_request_status_dataframe,
    build_satellite_usage_dataframe,
    build_schedule_download_filename,
    build_schedule_entries_dataframe,
    build_schedule_json,
    build_unfulfilled_requests_dataframe,
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
def load_scenario(
    scenario_id: str,
) -> LoadedScenario:
    return get_scenario_service().load(
        scenario_id
    )


def main() -> None:
    st.title(
        "Satellite Acquisition Planner"
    )

    st.caption(
        "Planowanie akwizycji dla konstelacji "
        "satelitów SAR i optycznych"
    )

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
        run_planning(
            scenario=selected_scenario,
            options=options,
        )

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


def render_sidebar_form(
    definitions_by_id,
) -> tuple[
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

            algorithm_value = st.radio(
                "Algorytm",
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

        st.dataframe(
            satellite_dataframe,
            width="stretch",
            height=420,
            hide_index=True,
            column_config={
                "acquisition_utilization_ratio": (
                    st.column_config.ProgressColumn(
                        "Akwizycje",
                        min_value=0.0,
                        max_value=1.0,
                        format="%.1f%%",
                    )
                ),
                "imaging_utilization_ratio": (
                    st.column_config.ProgressColumn(
                        "Czas obrazowania",
                        min_value=0.0,
                        max_value=1.0,
                        format="%.1f%%",
                    )
                ),
                "memory_utilization_ratio": (
                    st.column_config.ProgressColumn(
                        "Pamięć",
                        min_value=0.0,
                        max_value=1.0,
                        format="%.1f%%",
                    )
                ),
            },
        )

        st.caption(
            "Współczynniki wykorzystania są zapisane "
            "w zakresie 0–1."
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
