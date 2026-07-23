from __future__ import annotations

import streamlit as st

from app.analysis.experimental_validation import (
    ExperimentalValidationConfig,
    ExperimentalValidationResult,
)
from app.scenarios.experiment import DEFAULT_EXPERIMENT_PROFILES
from app.ui import (
    build_experiment_improvement_figure,
    build_experiment_metadata_json,
    build_experiment_objective_figure,
    build_experiment_pairs_dataframe,
    build_experiment_profile_dataframe,
    build_experiment_runs_dataframe,
    build_experiment_runtime_figure,
    build_experiment_satisfaction_figure,
    build_experiment_summary_dataframe,
)
from app.ui.app_context import (
    get_experimental_validation_service,
    load_scenario,
)
from app.ui.page_layout import render_page_header, render_sidebar_heading
from app.ui.pages.planning import render_scenario_overview


def render_experiments_page() -> None:
    render_page_header(
        "Walidacja eksperymentalna",
        "Uruchamia powtarzalne warianty scenariusza stresowego i porównuje "
        "jakość harmonogramu z czasem obliczeń dla Greedy, CP-SAT i Hybrid.",
        eyebrow="Metodyka badawcza",
        badges=("Powtórzenia", "Profile degradacji", "Seedy", "Eksport"),
    )

    profile_by_id = {
        profile.profile_id: profile
        for profile in DEFAULT_EXPERIMENT_PROFILES
    }

    with st.sidebar:
        render_sidebar_heading(
            "Eksperyment",
            "Powtórzenia, profile i limit CP-SAT",
        )
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
