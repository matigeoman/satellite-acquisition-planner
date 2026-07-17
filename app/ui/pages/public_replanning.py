from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from app.integrations.weather import CloudAggregation, OpenMeteoClientError
from app.models.enums import PlanningAlgorithm
from app.services.contracts.planning import PlanningOptions, PlanningResult
from app.services.contracts.public_replanning import PublicReplanningResult
from app.ui.app_context import get_public_replanning_service
from app.ui.common import algorithm_display_name, combine_utc
from app.ui.pages.replanning import render_replanning_result


_PUBLIC_PLANNING_RESULT_KEY = "public_planning_result"
_PUBLIC_REPLANNING_RESULT_KEY = "public_replanning_result"
_PUBLIC_BUILDS_STATE_KEY = "public_opportunity_builds"
_CUSTOM_REQUESTS_STATE_KEY = "custom_observation_requests"


def _aggregation_label(value: CloudAggregation) -> str:
    return {
        CloudAggregation.MAXIMUM: "Maksimum — konserwatywnie",
        CloudAggregation.PERCENTILE_75: "75. percentyl",
        CloudAggregation.MEAN: "Średnia nad AOI",
    }[value]


def _default_replan_at(result: PlanningResult) -> datetime:
    horizon_start = result.schedule.horizon_start_utc
    horizon_end = result.schedule.horizon_end_utc
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    if horizon_start <= now < horizon_end:
        return now
    return min(
        horizon_start + (horizon_end - horizon_start) / 3,
        horizon_end - timedelta(minutes=1),
    )


def _weather_changes_dataframe(result: PublicReplanningResult) -> pd.DataFrame:
    rows = []
    for change in result.weather_changes:
        rows.append(
            {
                "opportunity_id": change.opportunity_id,
                "request_id": change.request_id,
                "satellite_id": change.satellite_id,
                "start_utc": change.start_utc,
                "cloud_before": change.previous_cloud_cover,
                "cloud_after": change.refreshed_cloud_cover,
                "cloud_delta_percent": change.cloud_delta * 100.0,
                "feasible_before": change.previous_is_feasible,
                "feasible_after": change.refreshed_is_feasible,
                "feasibility_changed": change.feasibility_changed,
            }
        )
    return pd.DataFrame(rows)


def render_public_replanning_page() -> None:
    """Odświeża pogodę i przeplanowuje publiczny harmonogram."""

    st.header("Dynamiczne przeplanowanie publiczne")
    st.info(
        "Moduł odświeża prognozę Open-Meteo dla przyszłych okazji EO, "
        "zachowuje akwizycje wykonane i znajdujące się w oknie zamrożonym, "
        "a pozostałą część harmonogramu przelicza Greedy albo CP-SAT."
    )

    previous_result = st.session_state.get(_PUBLIC_PLANNING_RESULT_KEY)
    if not isinstance(previous_result, PlanningResult):
        st.warning(
            "Najpierw uruchom solver w module „Planowanie publiczne”."
        )
        return

    builds = st.session_state.get(_PUBLIC_BUILDS_STATE_KEY, {})
    requests = st.session_state.get(_CUSTOM_REQUESTS_STATE_KEY, [])
    if not builds or not requests:
        st.warning(
            "Brak zleceń albo okazji publicznych w bieżącej sesji. "
            "Wróć do modułu „Okna dostępu”."
        )
        return

    default_replan = _default_replan_at(previous_result)
    schedule = previous_result.schedule

    with st.container(border=True):
        st.markdown("### Parametry operacyjne")
        first, second, third, fourth = st.columns([1.2, 1.1, 1.0, 1.0])
        replan_date = first.date_input(
            "Data przeplanowania UTC",
            value=default_replan.date(),
            min_value=schedule.horizon_start_utc.date(),
            max_value=schedule.horizon_end_utc.date(),
        )
        replan_time = second.time_input(
            "Godzina przeplanowania UTC",
            value=default_replan.time().replace(tzinfo=None),
            step=timedelta(minutes=5),
        )
        freeze_hours = third.select_slider(
            "Okno zamrożone",
            options=[0.5, 1.0, 2.0, 3.0, 4.0, 6.0],
            value=2.0,
            format_func=lambda value: f"{value:g} h",
        )
        algorithm_value = fourth.radio(
            "Algorytm",
            options=[
                PlanningAlgorithm.GREEDY.value,
                PlanningAlgorithm.CP_SAT.value,
            ],
            index=(
                1
                if previous_result.algorithm == PlanningAlgorithm.CP_SAT
                else 0
            ),
            format_func=algorithm_display_name,
            horizontal=True,
        )

        st.markdown("### Aktualizacja pogody")
        weather_columns = st.columns([1.4, 1.0, 1.0])
        aggregation = weather_columns[0].selectbox(
            "Agregacja zachmurzenia nad AOI",
            options=list(CloudAggregation),
            index=0,
            format_func=_aggregation_label,
        )
        sampling_points = weather_columns[1].select_slider(
            "Punkty próbkowania AOI",
            options=[1, 3, 5, 7, 9],
            value=9,
        )
        weather_offline = weather_columns[2].toggle(
            "Tylko cache pogody",
            value=False,
            help=(
                "Bez połączenia z Open-Meteo. Używa ostatniego zgodnego "
                "zapisu z data/generated/weather."
            ),
        )

        with st.expander("Ustawienia solvera"):
            solver_columns = st.columns(4)
            memory_reserve_percent = solver_columns[0].slider(
                "Rezerwa pamięci",
                min_value=0,
                max_value=50,
                value=15,
                step=1,
                format="%d%%",
            )
            cp_sat_time_limit = solver_columns[1].select_slider(
                "Limit CP-SAT",
                options=[1.0, 5.0, 10.0, 30.0],
                value=10.0,
                format_func=lambda value: f"{value:g} s",
            )
            cp_sat_workers = solver_columns[2].number_input(
                "Wątki CP-SAT",
                min_value=1,
                max_value=16,
                value=1,
                step=1,
            )
            force_mandatory = solver_columns[3].checkbox(
                "Wymuś obowiązkowe",
                value=True,
            )

        submitted = st.button(
            "Odśwież pogodę i przeplanuj",
            type="primary",
            width="stretch",
        )

    replan_at = combine_utc(replan_date, replan_time)
    frozen_until = min(
        replan_at + timedelta(hours=float(freeze_hours)),
        schedule.horizon_end_utc,
    )
    overview = st.columns(5)
    overview[0].metric("Poprzedni algorytm", previous_result.algorithm.value)
    overview[1].metric("Poprzednie akwizycje", schedule.total_acquisitions)
    overview[2].metric("Moment przeplanowania", replan_at.strftime("%H:%M UTC"))
    overview[3].metric("Koniec blokady", frozen_until.strftime("%H:%M UTC"))
    overview[4].metric("Zlecenia", len(previous_result.scenario.request_set.requests))

    if submitted:
        options = PlanningOptions(
            algorithm=PlanningAlgorithm(algorithm_value),
            memory_reserve_ratio=memory_reserve_percent / 100.0,
            use_dynamic_transition_model=(
                previous_result.options.use_dynamic_transition_model
            ),
            eo_stabilization_time_s=(
                previous_result.options.eo_stabilization_time_s
            ),
            sar_stabilization_time_s=(
                previous_result.options.sar_stabilization_time_s
            ),
            sar_side_switch_penalty_s=(
                previous_result.options.sar_side_switch_penalty_s
            ),
            sar_mode_switch_penalty_s=(
                previous_result.options.sar_mode_switch_penalty_s
            ),
            sar_slew_rate_deg_s=(
                previous_result.options.sar_slew_rate_deg_s
            ),
            sar_pass_gap_s=previous_result.options.sar_pass_gap_s,
            sar_max_acquisitions_per_pass=(
                previous_result.options.sar_max_acquisitions_per_pass
            ),
            cp_sat_time_limit_s=float(cp_sat_time_limit),
            cp_sat_num_search_workers=int(cp_sat_workers),
            cp_sat_force_mandatory_requests=force_mandatory,
        )
        try:
            with st.spinner(
                "Aktualizacja prognozy, zamrażanie bliskiego planu i "
                "ponowne uruchomienie solvera..."
            ):
                result = get_public_replanning_service().run(
                    requests=requests,
                    builds_by_request_id=builds,
                    previous_planning_result=previous_result,
                    options=options,
                    replan_at_utc=replan_at,
                    freeze_duration=timedelta(hours=float(freeze_hours)),
                    aggregation=aggregation,
                    maximum_sampling_points=int(sampling_points),
                    allow_network=not weather_offline,
                )
        except (OpenMeteoClientError, ValueError) as error:
            st.session_state.pop(_PUBLIC_REPLANNING_RESULT_KEY, None)
            st.error(f"Nie udało się wykonać przeplanowania: {error}")
            return
        except Exception as error:
            st.session_state.pop(_PUBLIC_REPLANNING_RESULT_KEY, None)
            st.error("Dynamiczne przeplanowanie zakończyło się błędem.")
            st.exception(error)
            return

        st.session_state[_PUBLIC_REPLANNING_RESULT_KEY] = result
        st.session_state[_PUBLIC_BUILDS_STATE_KEY] = (
            result.refreshed_builds_by_request_id
        )
        st.session_state[_PUBLIC_PLANNING_RESULT_KEY] = result.planning_result
        st.success(
            "Prognoza została odświeżona, a nowy harmonogram zapisano "
            "w sesji. Globus automatycznie użyje nowego planu."
        )

    result = st.session_state.get(_PUBLIC_REPLANNING_RESULT_KEY)
    if not isinstance(result, PublicReplanningResult):
        st.caption(
            "Najbliższe dwie godziny są domyślnie zamrożone. Pogoda jest "
            "odświeżana wyłącznie dla okazji zaczynających się po tej granicy."
        )
        return

    for warning in result.warnings:
        st.warning(warning)

    st.divider()
    st.subheader("Wpływ aktualizacji zachmurzenia")
    weather_metrics = st.columns(5)
    weather_metrics[0].metric(
        "Odświeżone okazje EO",
        result.refreshed_opportunity_count,
    )
    weather_metrics[1].metric("Zmiana zachmurzenia", result.cloud_changed_count)
    weather_metrics[2].metric("Stały się wykonalne", result.became_feasible_count)
    weather_metrics[3].metric(
        "Stały się niewykonalne",
        result.became_infeasible_count,
    )
    weather_metrics[4].metric(
        "Aktualizacja UTC",
        result.refreshed_at_utc.strftime("%H:%M:%S"),
    )

    weather_table = _weather_changes_dataframe(result)
    if weather_table.empty:
        st.info(
            "Brak przyszłych okazji EO poza oknem zamrożonym. "
            "Harmonogram został przeplanowany bez nowych danych pogodowych."
        )
    else:
        st.dataframe(
            weather_table,
            width="stretch",
            hide_index=True,
            height=360,
            column_config={
                "cloud_before": st.column_config.ProgressColumn(
                    "Chmury przed",
                    min_value=0.0,
                    max_value=1.0,
                    format="percent",
                ),
                "cloud_after": st.column_config.ProgressColumn(
                    "Chmury po",
                    min_value=0.0,
                    max_value=1.0,
                    format="percent",
                ),
                "cloud_delta_percent": st.column_config.NumberColumn(
                    "Zmiana",
                    format="%+.1f%%",
                ),
            },
        )
        st.download_button(
            "Pobierz zmiany pogody CSV",
            data=weather_table.to_csv(index=False).encode("utf-8-sig"),
            file_name="public_weather_replanning_changes.csv",
            mime="text/csv",
            width="stretch",
        )

    render_replanning_result(result.replanning_result)


__all__ = ["render_public_replanning_page"]
