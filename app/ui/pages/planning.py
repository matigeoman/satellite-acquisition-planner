from __future__ import annotations

import plotly.express as px
import streamlit as st

from app.models.enums import PlanningAlgorithm
from app.planning.conflict_graph import build_opportunity_conflict_graph
from app.planning.profiles import DecisionProfile
from app.services.comparison_service import PlanningComparisonResult
from app.services.planning_service import PlanningOptions, PlanningResult
from app.services.scenario_service import LoadedScenario
from app.ui import (
    build_comparison_gantt_figure,
    build_downlink_entries_dataframe,
    build_comparison_metrics,
    build_comparison_summary_dataframe,
    build_gantt_figure,
    build_memory_timeline_dataframe,
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
    format_percent,
)
from app.ui.app_context import (
    get_comparison_service,
    get_planning_service,
    get_scenario_service,
    load_scenario,
)
from app.ui.common import algorithm_display_name
from app.ui.page_layout import render_page_header, render_sidebar_heading


def render_planning_page() -> None:
    render_page_header(
        "Planowanie i porównanie algorytmów",
        "Budowa harmonogramów referencyjnych, porównanie funkcji celu oraz "
        "diagnostyka ograniczeń, pamięci, downlinku i grafu konfliktów.",
        eyebrow="Scenariusze referencyjne",
        badges=("Greedy 2.0", "CP-SAT", "Hybrid", "Profile decyzyjne"),
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
        render_sidebar_heading(
            "Planowanie",
            "Scenariusz, algorytm i profil decyzyjny",
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
                    PlanningAlgorithm.HYBRID.value,
                ],
                index=2,
                format_func=algorithm_display_name,
                horizontal=True,
            )

            decision_profile_value = st.selectbox(
                "Profil decyzyjny",
                options=[profile.value for profile in DecisionProfile],
                index=1,
                format_func=lambda value: {
                    "CUSTOM": "Własne wagi",
                    "BALANCED": "Zrównoważony",
                    "EMERGENCY": "Reagowanie kryzysowe",
                    "QUALITY_FIRST": "Najwyższa jakość",
                    "THROUGHPUT": "Maksymalna przepustowość",
                    "SAR_EO_FUSION": "Fuzja SAR–EO",
                }[value],
                help=(
                    "Jawne profile preferencji inspirowane podejściem "
                    "wielokryterialnym. Profil inny niż Własne wagi "
                    "ustawia wagi automatycznie."
                ),
            )
            custom_profile = (
                decision_profile_value == DecisionProfile.CUSTOM.value
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

            with st.expander("Pamięć dynamiczna i downlink", expanded=True):
                enable_downlink_planning = st.checkbox(
                    "Planuj transmisję do stacji naziemnych",
                    value=True,
                    help=(
                        "Akwizycje zwiększają zajętość pamięci, a wybrane "
                        "okna downlinku zwalniają ją na osi czasu."
                    ),
                )
                require_full_downlink = st.checkbox(
                    "Opróżnij pamięć do końca horyzontu",
                    value=True,
                    disabled=not enable_downlink_planning,
                    help=(
                        "Wymaga transmisji wszystkich danych, w tym danych "
                        "znajdujących się w pamięci na początku horyzontu."
                    ),
                )
                allow_simultaneous_imaging_downlink = st.checkbox(
                    "Pozwól na jednoczesne obrazowanie i downlink",
                    value=False,
                    disabled=not enable_downlink_planning,
                )
                downlink_capacity_reserve_percent = st.slider(
                    "Rezerwa przepustowości downlinku",
                    min_value=0,
                    max_value=50,
                    value=10,
                    step=1,
                    format="%d%%",
                    disabled=not enable_downlink_planning,
                    help=(
                        "Margines na narzut protokołów, zakłócenia i "
                        "niepewność jakości łącza."
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
                    disabled=not custom_profile,
                )

                quality_weight = st.number_input(
                    "Waga jakości",
                    min_value=0.0,
                    value=3.0,
                    step=0.5,
                    disabled=not custom_profile,
                )

                coverage_weight = st.number_input(
                    "Waga pokrycia",
                    min_value=0.0,
                    value=2.0,
                    step=0.5,
                    disabled=not custom_profile,
                )

                mandatory_bonus = st.number_input(
                    "Premia za zlecenie obowiązkowe",
                    min_value=0.0,
                    value=100.0,
                    step=10.0,
                    disabled=not custom_profile,
                )

                dual_optional_second_bonus = (
                    st.number_input(
                        "Premia za drugi sensor DUAL_OPTIONAL",
                        min_value=0.0,
                        value=5.0,
                        step=1.0,
                        disabled=not custom_profile,
                    )
                )

            with st.expander("Heurystyka badawcza Greedy / Hybrid"):
                use_opportunity_cost_heuristic = st.checkbox(
                    "Uwzględnij koszt utraconych okazji",
                    value=True,
                    disabled=not custom_profile,
                    help=(
                        "Ranking uwzględnia rzadkość okien, czas, pamięć "
                        "i wartość konfliktujących okazji."
                    ),
                )
                scarcity_bonus_weight = st.number_input(
                    "Premia za rzadkość okazji",
                    min_value=0.0,
                    value=2.0,
                    step=0.25,
                    disabled=not custom_profile,
                )
                conflict_cost_weight = st.number_input(
                    "Waga kosztu konfliktów",
                    min_value=0.0,
                    value=0.20,
                    step=0.05,
                    disabled=not custom_profile,
                )
                hybrid_neighborhood_request_limit = st.number_input(
                    "Maks. zleceń w sąsiedztwie Hybrid",
                    min_value=2,
                    max_value=100,
                    value=12,
                    step=1,
                )
                hybrid_max_neighborhoods = st.number_input(
                    "Maks. liczba sąsiedztw Hybrid",
                    min_value=1,
                    max_value=30,
                    value=6,
                    step=1,
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
        decision_profile=DecisionProfile(decision_profile_value),
        memory_reserve_ratio=(
            memory_reserve_percent
            / 100.0
        ),
        enable_downlink_planning=enable_downlink_planning,
        require_full_downlink=require_full_downlink,
        allow_simultaneous_imaging_downlink=(
            allow_simultaneous_imaging_downlink
        ),
        downlink_capacity_reserve_ratio=(
            downlink_capacity_reserve_percent / 100.0
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
        use_opportunity_cost_heuristic=use_opportunity_cost_heuristic,
        scarcity_bonus_weight=float(scarcity_bonus_weight),
        conflict_cost_weight=float(conflict_cost_weight),
        hybrid_neighborhood_request_limit=int(
            hybrid_neighborhood_request_limit
        ),
        hybrid_max_neighborhoods=int(hybrid_max_neighborhoods),
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

    first, second, third, fourth, fifth, sixth = st.columns(6)

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

    fifth.metric(
        "Okna downlinku",
        scenario.downlink_opportunity_count,
    )

    sixth.metric(
        "Stacje naziemne",
        scenario.ground_station_count,
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
        resources_tab,
        conflict_graph_tab,
        export_tab,
    ) = st.tabs(
        [
            "Gantt",
            "Mapa",
            "Harmonogram",
            "Zlecenia",
            "Satelity",
            "Pamięć i downlink",
            "Graf konfliktów",
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

    downlink_dataframe = build_downlink_entries_dataframe(result)
    memory_dataframe = build_memory_timeline_dataframe(result)

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

    with resources_tab:
        st.markdown("### Dynamiczna pamięć i transmisja danych")
        if not result.options.enable_downlink_planning:
            st.info(
                "Zintegrowane planowanie downlinku było wyłączone dla tego uruchomienia."
            )
        elif not result.schedule.resource_summaries:
            st.warning("Brak podsumowania zasobów w harmonogramie.")
        else:
            totals = st.columns(4)
            totals[0].metric(
                "Okna downlinku", result.schedule.selected_downlink_windows
            )
            totals[1].metric(
                "Wysłane dane",
                f"{result.schedule.total_downlinked_data_mb:,.0f} MB",
            )
            totals[2].metric(
                "Dane z akwizycji",
                f"{result.schedule.total_data_volume_mb:,.0f} MB",
            )
            complete_count = sum(
                summary.delivery_complete
                for summary in result.schedule.resource_summaries
            )
            totals[3].metric(
                "Pamięć opróżniona",
                f"{complete_count}/{len(result.schedule.resource_summaries)}",
            )

            if not memory_dataframe.empty:
                figure = px.line(
                    memory_dataframe,
                    x="timestamp_utc",
                    y="memory_used_mb",
                    color="satellite_id",
                    markers=True,
                    hover_data=[
                        "event_type",
                        "reference_id",
                        "delta_mb",
                        "memory_limit_mb",
                    ],
                    title="Zajętość pamięci pokładowej w czasie",
                )
                st.plotly_chart(
                    figure,
                    width="stretch",
                    key=f"memory_timeline_{schedule_key}",
                    config={"displaylogo": False, "scrollZoom": True},
                )

            st.markdown("#### Wybrane okna transmisji")
            if downlink_dataframe.empty:
                st.info("Solver nie musiał wykorzystywać żadnego okna downlinku.")
            else:
                downlink_display = build_percentage_display_dataframe(
                    downlink_dataframe, ["capacity_utilization_ratio"]
                )
                st.dataframe(
                    downlink_display,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "capacity_utilization_ratio": st.column_config.ProgressColumn(
                            "Wykorzystanie okna",
                            min_value=0.0,
                            max_value=100.0,
                            format="%.1f%%",
                        )
                    },
                )

            st.markdown("#### Zdarzenia pamięci")
            st.dataframe(
                memory_dataframe,
                width="stretch",
                height=420,
                hide_index=True,
            )

    with conflict_graph_tab:
        st.markdown("### Graf niewykonalności okazji")
        st.caption(
            "Węzeł oznacza wykonalną okazję akwizycyjną, a krawędź — "
            "parę okazji, których nie można wybrać jednocześnie z powodu "
            "alternatyw tego samego zlecenia, niezgodnej pary SAR–EO albo "
            "konfliktu przejścia satelity."
        )
        try:
            graph = build_opportunity_conflict_graph(
                catalog=result.scenario.catalog,
                request_set=result.scenario.request_set,
                opportunity_set=result.scenario.opportunity_set,
                config=result.options,
            )
        except (KeyError, TypeError, ValueError) as error:
            st.warning(f"Nie udało się zbudować grafu konfliktów: {error}")
        else:
            components = graph.connected_components()
            graph_metrics = st.columns(5)
            graph_metrics[0].metric("Węzły", graph.node_count)
            graph_metrics[1].metric("Krawędzie", graph.edge_count)
            graph_metrics[2].metric("Gęstość", f"{graph.density:.4f}")
            graph_metrics[3].metric("Komponenty", len(components))
            graph_metrics[4].metric(
                "Największy komponent",
                max((len(component) for component in components), default=0),
            )

            reason_rows = [
                {"przyczyna": reason, "liczba_krawędzi": count}
                for reason, count in graph.reason_counts().items()
            ]
            if reason_rows:
                st.dataframe(
                    reason_rows,
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info("W tym scenariuszu nie wykryto konfliktów parowych.")

            degree_rows = sorted(
                (
                    {
                        "opportunity_id": opportunity_id,
                        "stopień": graph.degree(opportunity_id),
                    }
                    for opportunity_id in graph.opportunity_ids
                ),
                key=lambda row: (-row["stopień"], row["opportunity_id"]),
            )[:25]
            st.markdown("#### Najbardziej konfliktowe okazje")
            st.dataframe(
                degree_rows,
                width="stretch",
                hide_index=True,
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

        first, second, third = st.columns(3)

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

        with third:
            st.download_button(
                "Pobierz downlink CSV",
                data=downlink_dataframe.to_csv(index=False).encode("utf-8-sig"),
                file_name=(
                    json_filename.removesuffix(".json") + "_downlinks.csv"
                ),
                mime="text/csv",
                on_click="ignore",
                width="stretch",
                disabled=downlink_dataframe.empty,
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
