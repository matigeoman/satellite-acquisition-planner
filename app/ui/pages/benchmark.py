from __future__ import annotations

import streamlit as st

from app.analysis.algorithm_benchmark import (
    AlgorithmBenchmarkConfig,
    AlgorithmBenchmarkResult,
)
from app.ui.app_context import get_algorithm_benchmark_service, load_scenario
from app.ui.benchmark_view import (
    build_benchmark_export_zip,
    build_benchmark_improvement_figure,
    build_benchmark_objective_figure,
    build_benchmark_pairs_dataframe,
    build_benchmark_rejections_figure,
    build_benchmark_runtime_figure,
    build_benchmark_runs_dataframe,
    build_benchmark_satisfaction_figure,
    build_benchmark_summary_dataframe,
)
from app.ui.pages.planning import render_scenario_overview


_REQUEST_COUNT_OPTIONS = [20, 50, 100, 200, 500]
_TIME_LIMIT_OPTIONS = [0.5, 1.0, 2.0, 5.0, 10.0, 30.0]


def render_benchmark_page() -> None:
    st.header("Benchmarki")
    st.write(
        "Porównanie skalowalności Greedy i CP-SAT dla zagnieżdżonych "
        "scenariuszy od 20 do 500 zleceń. Każde zlecenie posiada "
        "dziesięć okazji akwizycji."
    )

    with st.sidebar:
        st.header("Parametry benchmarku")
        request_counts = st.multiselect(
            "Liczba zleceń",
            options=_REQUEST_COUNT_OPTIONS,
            default=[20, 50, 100],
            key="benchmark_request_counts",
        )
        repetitions = st.slider(
            "Powtórzenia",
            min_value=1,
            max_value=5,
            value=1,
            step=1,
            key="benchmark_repetitions",
        )
        cp_sat_limits = st.multiselect(
            "Limity czasu CP-SAT",
            options=_TIME_LIMIT_OPTIONS,
            default=[2.0],
            format_func=lambda value: f"{value:g} s",
            key="benchmark_cp_limits",
        )
        workers = st.selectbox(
            "Wątki CP-SAT",
            options=[1, 2, 4, 8],
            index=0,
            key="benchmark_workers",
        )
        base_seed = st.number_input(
            "Ziarno bazowe",
            min_value=0,
            value=20260717,
            step=1,
            key="benchmark_seed",
        )
        memory_reserve_percent = st.slider(
            "Rezerwa pamięci",
            min_value=0,
            max_value=50,
            value=15,
            step=1,
            format="%d%%",
            key="benchmark_memory_reserve",
        )
        dynamic_constraints = st.checkbox(
            "Dynamiczne ograniczenia operacyjne",
            value=True,
            key="benchmark_dynamic_constraints",
        )

        estimated_budget = len(request_counts) * repetitions * sum(cp_sat_limits)
        total_runs = len(request_counts) * repetitions * (1 + len(cp_sat_limits))
        st.caption(
            f"Planowane przebiegi: {total_runs}. Minimalny budżet "
            f"solvera CP-SAT: około {estimated_budget:.1f} s."
        )
        if any(value >= 200 for value in request_counts):
            st.warning(
                "Warianty 200 i 500 zleceń tworzą odpowiednio 2000 "
                "i 5000 okazji. Budowa modelu może trwać dłużej niż "
                "sam ustawiony limit solvera."
            )
        submitted = st.button(
            "Uruchom benchmark Greedy vs CP-SAT",
            type="primary",
            width="stretch",
            key="run_algorithm_benchmark",
        )

    scenario = load_scenario("STRESS")
    render_scenario_overview(scenario)

    with st.expander("Metodyka eksperymentu", expanded=False):
        st.markdown(
            """
- Scenariusze są zagnieżdżone: większy wariant zawiera wszystkie zlecenia mniejszego.
- Każde zlecenie ma 10 okazji, dlatego 500 zleceń oznacza 5000 okazji.
- Greedy jest uruchamiany raz dla każdego powtórzenia, a CP-SAT osobno dla każdego limitu czasu.
- Każde powtórzenie używa jednego wspólnego `random_seed` dla wszystkich limitów CP-SAT, aby porównanie 2/5/10/30 s nie było zaburzone zmianą ziarna.
- Błąd lub status `UNKNOWN` nie zatrzymuje całej serii; zostaje zapisany jako nieudany przebieg.
            """
        )

    if submitted:
        if not request_counts:
            st.error("Wybierz co najmniej jeden rozmiar problemu.")
        elif not cp_sat_limits:
            st.error("Wybierz co najmniej jeden limit czasu CP-SAT.")
        else:
            try:
                config = AlgorithmBenchmarkConfig(
                    request_counts=tuple(request_counts),
                    repetitions=repetitions,
                    cp_sat_time_limits_s=tuple(cp_sat_limits),
                    cp_sat_num_search_workers=int(workers),
                    base_seed=int(base_seed),
                    memory_reserve_ratio=(memory_reserve_percent / 100.0),
                    use_dynamic_transition_model=dynamic_constraints,
                )
                with st.spinner("Budowanie scenariuszy i uruchamianie benchmarku..."):
                    result = get_algorithm_benchmark_service().run(
                        base_scenario=scenario,
                        config=config,
                    )
                st.session_state["algorithm_benchmark_result"] = result
                st.success("Benchmark zakończony.")
            except Exception as error:
                st.session_state.pop("algorithm_benchmark_result", None)
                st.error("Benchmark zakończył się błędem.")
                st.exception(error)

    result = st.session_state.get("algorithm_benchmark_result")
    if result is None:
        st.info("Ustaw parametry i uruchom benchmark.")
        return
    if not isinstance(result, AlgorithmBenchmarkResult):
        st.session_state.pop("algorithm_benchmark_result", None)
        st.error("Stan aplikacji zawiera niepoprawny wynik benchmarku.")
        return

    render_benchmark_result(result)


def render_benchmark_result(result: AlgorithmBenchmarkResult) -> None:
    st.divider()
    st.subheader("Wyniki benchmarku")

    metrics = st.columns(6)
    metrics[0].metric("Przebiegi", len(result.run_records))
    metrics[1].metric("Poprawne", result.successful_run_count)
    metrics[2].metric("Błędy", result.failed_run_count)
    metrics[3].metric(
        "CP-SAT lepszy",
        f"{result.cp_sat_better_count}/{len(result.pair_records)}",
    )
    metrics[4].metric(
        "Średnia poprawa celu",
        f"{result.mean_objective_improvement_pct:+.2f}%",
    )
    metrics[5].metric("Czas całkowity", f"{result.wall_clock_runtime_s:.2f} s")

    summary = build_benchmark_summary_dataframe(result)
    pairs = build_benchmark_pairs_dataframe(result)
    runs = build_benchmark_runs_dataframe(result)
    result_key = result.started_at_utc.strftime("%Y%m%d%H%M%S%f")

    charts_tab, summary_tab, runs_tab, diagnostics_tab, export_tab = st.tabs(
        ["Wykresy", "Podsumowanie", "Przebiegi", "Diagnostyka", "Eksport"]
    )

    with charts_tab:
        first, second = st.columns(2)
        first.plotly_chart(
            build_benchmark_runtime_figure(result),
            width="stretch",
            key=f"benchmark_runtime_{result_key}",
            config={"displaylogo": False},
        )
        second.plotly_chart(
            build_benchmark_objective_figure(result),
            width="stretch",
            key=f"benchmark_objective_{result_key}",
            config={"displaylogo": False},
        )
        third, fourth = st.columns(2)
        third.plotly_chart(
            build_benchmark_satisfaction_figure(result),
            width="stretch",
            key=f"benchmark_satisfaction_{result_key}",
            config={"displaylogo": False},
        )
        fourth.plotly_chart(
            build_benchmark_improvement_figure(result),
            width="stretch",
            key=f"benchmark_improvement_{result_key}",
            config={"displaylogo": False},
        )

    with summary_tab:
        st.dataframe(summary, width="stretch", hide_index=True, height=420)
        st.markdown("### Porównania CP-SAT względem Greedy")
        st.dataframe(pairs, width="stretch", hide_index=True, height=360)

    with runs_tab:
        st.dataframe(runs, width="stretch", hide_index=True, height=520)

    with diagnostics_tab:
        st.plotly_chart(
            build_benchmark_rejections_figure(result),
            width="stretch",
            key=f"benchmark_rejections_{result_key}",
            config={"displaylogo": False},
        )
        failed = runs[~runs["successful"]]
        if failed.empty:
            st.success("Wszystkie przebiegi zakończyły się poprawnie.")
        else:
            st.warning(f"Nieudane przebiegi: {len(failed)}")
            st.dataframe(
                failed[
                    [
                        "request_count",
                        "repetition",
                        "algorithm_variant",
                        "solver_status",
                        "runtime_s",
                        "error_message",
                    ]
                ],
                width="stretch",
                hide_index=True,
            )

    with export_tab:
        archive = build_benchmark_export_zip(result)
        st.download_button(
            "Pobierz kompletny pakiet benchmarku ZIP",
            data=archive,
            file_name="algorithm_benchmark_results.zip",
            mime="application/zip",
            on_click="ignore",
            width="stretch",
        )
        st.caption(
            "Pakiet zawiera benchmark_runs.csv, benchmark_pairs.csv, "
            "benchmark_summary.csv, benchmark_results.json oraz "
            "benchmark_charts.html."
        )


__all__ = ["render_benchmark_page", "render_benchmark_result"]
