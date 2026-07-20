from __future__ import annotations

import json
from datetime import timedelta

import streamlit as st

from app.catalogs import ICEYE_PUBLIC_PROFILE, PLEIADES_NEO_PUBLIC_PROFILE
from app.integrations.opportunities import build_public_opportunities
from app.integrations.orbits import CelestrakClientError, OrbitPropagationError
from app.integrations.weather import (
    CloudAggregation,
    OpenMeteoClientError,
)
from app.models.enums import SensorType
from app.models.request import ObservationRequest
from app.ui.access_view import (
    access_windows_dataframe,
    build_access_map_figure,
    build_access_timeline_figure,
    cloud_assessments_dataframe,
    public_opportunities_dataframe,
)
from app.ui.app_context import (
    get_cloud_assessment_service,
    get_public_access_service,
)
from app.ui.orbit_state import (
    get_public_orbit_snapshot,
    load_public_orbit_snapshot,
)


_ACCESS_RESULT_STATE_KEY = "public_access_result"
_PUBLIC_BUILDS_STATE_KEY = "public_opportunity_builds"


def _request_label(request: ObservationRequest) -> str:
    sensors = "/".join(sensor.value for sensor in request.requested_sensor_types)
    return f"{request.request_id} · {request.name} · {sensors}"


def _available_modes(request: ObservationRequest):
    modes = []
    if SensorType.SAR in request.requested_sensor_types:
        modes.extend(ICEYE_PUBLIC_PROFILE.sensor.imaging_modes)
    if SensorType.OPTICAL in request.requested_sensor_types:
        modes.extend(PLEIADES_NEO_PUBLIC_PROFILE.sensor.imaging_modes)
    return [
        mode
        for mode in modes
        if mode.is_active and mode.nominal_resolution_m <= request.resolution_limit_for(mode.sensor_type)
    ]


def _mode_label(mode) -> str:
    return (
        f"{mode.name} · {mode.nominal_resolution_m:g} m · "
        f"{mode.nominal_scene_width_km:g}×"
        f"{mode.nominal_scene_length_km:g} km"
    )


def _aggregation_label(value: CloudAggregation) -> str:
    labels = {
        CloudAggregation.MAXIMUM: "Maksimum — wariant konserwatywny",
        CloudAggregation.PERCENTILE_75: "75. percentyl",
        CloudAggregation.MEAN: "Średnia z punktów AOI",
    }
    return labels[value]


def _render_access_result(
    *,
    result,
    request: ObservationRequest,
) -> None:
    for warning in result.warnings:
        st.warning(warning)

    metrics = st.columns(5)
    metrics[0].metric("Okna dostępu", len(result.windows))
    metrics[1].metric("Satelity analizowane", result.evaluated_satellites)
    metrics[2].metric("Tryby analizowane", result.evaluated_modes)
    metrics[3].metric(
        "Satelity z dostępem",
        len(result.satellite_ids_with_access),
    )
    metrics[4].metric("Krok", f"{result.propagation_step_s:g} s")

    st.caption(
        "Pokrycie Polygon pozostaje przybliżeniem opartym na bounding box "
        "AOI i nominalnym prostokątnym footprintcie trybu."
    )

    if not result.windows:
        return

    st.subheader("Mapa segmentów dostępu")
    access_map = build_access_map_figure(result, request.geometry)
    st.plotly_chart(
        access_map,
        width="stretch",
        config={
            "displaylogo": False,
            "scrollZoom": True,
            "responsive": True,
        },
    )

    st.subheader("Oś czasu okien")
    timeline = build_access_timeline_figure(result)
    st.plotly_chart(
        timeline,
        width="stretch",
        config={"displaylogo": False, "responsive": True},
    )

    table = access_windows_dataframe(result)
    st.subheader("Tabela okien")
    st.dataframe(
        table,
        width="stretch",
        hide_index=True,
        height=420,
        column_config={
            "Pokrycie": st.column_config.ProgressColumn(
                "Pokrycie",
                min_value=0.0,
                max_value=1.0,
                format="percent",
            )
        },
    )

    export_columns = st.columns(2)
    export_columns[0].download_button(
        "Pobierz okna JSON",
        data=json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        file_name=f"{request.request_id.lower()}_access_windows.json",
        mime="application/json",
        width="stretch",
    )
    export_columns[1].download_button(
        "Pobierz tabelę CSV",
        data=table.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{request.request_id.lower()}_access_windows.csv",
        mime="text/csv",
        width="stretch",
    )


def _render_opportunity_builder(
    *,
    result,
    request: ObservationRequest,
) -> None:
    if not result.windows:
        return

    optical_window_count = sum(
        window.sensor_type == SensorType.OPTICAL for window in result.windows
    )
    st.divider()
    st.header("Prognoza zachmurzenia i okazje dla solvera")
    st.info(
        "Okna geometryczne są teraz przekształcane do pełnych obiektów "
        "AcquisitionOpportunity. Dla Pléiades Neo program pobiera godzinową "
        "prognozę zachmurzenia Open-Meteo, interpoluje ją do czasu akwizycji "
        "i porównuje z limitem zlecenia."
    )

    with st.container(border=True):
        left, middle, right = st.columns([1.5, 1.1, 1.1])
        aggregation = left.selectbox(
            "Agregacja zachmurzenia nad AOI",
            options=list(CloudAggregation),
            index=0,
            format_func=_aggregation_label,
            disabled=optical_window_count == 0,
        )
        sampling_points = middle.select_slider(
            "Maksymalna liczba punktów AOI",
            options=[1, 3, 5, 7, 9],
            value=9,
            disabled=optical_window_count == 0,
        )
        weather_offline = right.toggle(
            "Tylko cache pogody",
            value=False,
            disabled=optical_window_count == 0,
            help=(
                "Nie łączy się z Open-Meteo. Wymaga wcześniejszego cache "
                "dla dokładnie tego AOI i zakresu czasu."
            ),
        )
        if optical_window_count:
            st.caption(
                f"Okna optyczne wymagające prognozy: {optical_window_count}. "
                f"Limit zlecenia: {request.max_cloud_cover:.0%}."
            )
        else:
            st.caption(
                "Wybrane okna są wyłącznie SAR — prognoza zachmurzenia nie "
                "jest pobierana."
            )

        build_clicked = st.button(
            "Pobierz pogodę i utwórz okazje planistyczne"
            if optical_window_count
            else "Utwórz okazje planistyczne",
            type="primary",
            width="stretch",
        )

    if build_clicked:
        try:
            assessments = ()
            if optical_window_count:
                with st.spinner(
                    "Pobieranie Open-Meteo i próbkowanie zachmurzenia nad AOI..."
                ):
                    assessments = (
                        get_cloud_assessment_service().assess_windows(
                            request=request,
                            windows=result.windows,
                            aggregation=aggregation,
                            maximum_sampling_points=sampling_points,
                            allow_network=not weather_offline,
                        )
                    )
            build_result = build_public_opportunities(
                request=request,
                access_result=result,
                weather_assessments=assessments,
            )
        except (OpenMeteoClientError, ValueError) as error:
            st.error(f"Nie udało się utworzyć okazji: {error}")
            return

        builds = st.session_state.setdefault(_PUBLIC_BUILDS_STATE_KEY, {})
        builds[request.request_id] = build_result
        st.success(
            "Okazje zapisano w sesji. Są dostępne w module "
            "„Planowanie publiczne”."
        )

    build_result = st.session_state.get(_PUBLIC_BUILDS_STATE_KEY, {}).get(
        request.request_id
    )
    if build_result is None:
        return

    for warning in build_result.warnings:
        st.warning(warning)

    build_metrics = st.columns(6)
    build_metrics[0].metric("Okazje", len(build_result.opportunities))
    build_metrics[1].metric(
        "Wykonalne",
        len(build_result.feasible_opportunities),
    )
    build_metrics[2].metric(
        "SAR",
        sum(
            opportunity.sensor_type == SensorType.SAR
            for opportunity in build_result.opportunities
        ),
    )
    build_metrics[3].metric(
        "EO",
        len(build_result.optical_opportunities),
    )
    build_metrics[4].metric(
        "EO odrzucone przez chmury",
        sum(
            opportunity.sensor_type == SensorType.OPTICAL
            and not opportunity.is_feasible
            for opportunity in build_result.opportunities
        ),
    )
    build_metrics[5].metric(
        "Okna pominięte",
        len(build_result.skipped_window_ids),
    )

    if build_result.weather_assessments:
        st.subheader("Ocena zachmurzenia okien EO")
        weather_table = cloud_assessments_dataframe(
            build_result.weather_assessments
        )
        st.dataframe(
            weather_table,
            width="stretch",
            hide_index=True,
            height=380,
            column_config={
                column: st.column_config.ProgressColumn(
                    column,
                    min_value=0.0,
                    max_value=1.0,
                    format="percent",
                )
                for column in (
                    "Zachmurzenie",
                    "Chmury niskie",
                    "Chmury średnie",
                    "Chmury wysokie",
                    "Limit",
                )
            },
        )

    st.subheader("AcquisitionOpportunity")
    opportunity_table = public_opportunities_dataframe(build_result)
    st.dataframe(
        opportunity_table,
        width="stretch",
        hide_index=True,
        height=500,
        column_config={
            "Zachmurzenie": st.column_config.ProgressColumn(
                "Zachmurzenie",
                min_value=0.0,
                max_value=1.0,
                format="percent",
            ),
            "Pokrycie": st.column_config.ProgressColumn(
                "Pokrycie",
                min_value=0.0,
                max_value=1.0,
                format="percent",
            ),
            "Jakość": st.column_config.ProgressColumn(
                "Jakość",
                min_value=0.0,
                max_value=1.0,
                format="percent",
            ),
        },
    )

    export = st.columns(2)
    export[0].download_button(
        "Pobierz wynik z pogodą JSON",
        data=json.dumps(build_result.to_dict(), ensure_ascii=False, indent=2),
        file_name=f"{request.request_id.lower()}_public_opportunities.json",
        mime="application/json",
        width="stretch",
    )
    export[1].download_button(
        "Pobierz okazje CSV",
        data=opportunity_table.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{request.request_id.lower()}_public_opportunities.csv",
        mime="text/csv",
        width="stretch",
    )


def render_access_page() -> None:
    """Wyznacza okna, prognozę zachmurzenia i okazje planistyczne."""

    st.header("Okna dostępu z publicznych orbit")
    st.info(
        "Moduł łączy zlecenie Point/Polygon, publiczne OMM, propagację "
        "SGP4 oraz profile ICEYE i Pléiades Neo. Wyniki są orientacyjnymi "
        "oknami modelowymi, a nie potwierdzeniem komercyjnego taskingu."
    )

    requests: list[ObservationRequest] = st.session_state.get(
        "custom_observation_requests",
        [],
    )
    if not requests:
        st.warning(
            "Najpierw przejdź do modułu „Cele i zlecenia”, narysuj AOI i "
            "dodaj co najmniej jedno zlecenie obserwacyjne."
        )
        return

    requests_by_id = {request.request_id: request for request in requests}
    request_id = st.selectbox(
        "Zlecenie do analizy",
        options=list(requests_by_id),
        format_func=lambda value: _request_label(requests_by_id[value]),
    )
    request = requests_by_id[request_id]
    modes = _available_modes(request)
    if not modes:
        st.error(
            "Żaden publiczny tryb sensora nie spełnia wymaganej "
            "rozdzielczości tego zlecenia."
        )
        return

    with st.container(border=True):
        st.markdown("### Parametry obliczeń")
        first, second, third = st.columns([1.2, 2.3, 1.2])
        step_seconds = first.select_slider(
            "Krok propagacji [s]",
            options=[10, 20, 30, 60, 90, 120],
            value=30,
            help=(
                "Mniejszy krok dokładniej lokalizuje granice okna, ale "
                "zwiększa czas obliczeń."
            ),
        )
        modes_by_id = {mode.mode_id: mode for mode in modes}
        selected_mode_ids = second.multiselect(
            "Tryby obrazowania",
            options=list(modes_by_id),
            default=list(modes_by_id),
            format_func=lambda value: _mode_label(modes_by_id[value]),
        )
        offline = third.toggle(
            "Tylko lokalny cache orbit",
            value=False,
            help="Nie pobiera OMM z sieci. Wymaga wcześniejszego cache.",
        )

        horizon_hours = (
            request.latest_end_utc - request.earliest_start_utc
        ).total_seconds() / 3600.0
        st.caption(
            f"Okno zlecenia: {request.earliest_start_utc.isoformat()} → "
            f"{request.latest_end_utc.isoformat()} ({horizon_hours:.1f} h)."
        )
        if horizon_hours > 72:
            st.warning(
                "Okno zlecenia przekracza 72 godziny. Obliczenia mogą być "
                "wyraźnie wolniejsze; rozważ krótszy zakres."
            )

        calculate = st.button(
            "Wyznacz okna dostępu",
            type="primary",
            width="stretch",
            disabled=not selected_mode_ids,
        )

    if calculate:
        snapshot = get_public_orbit_snapshot()
        if snapshot is None:
            try:
                with st.spinner("Pobieranie publicznych OMM..."):
                    snapshot = load_public_orbit_snapshot(
                        allow_network=not offline
                    )
            except CelestrakClientError as error:
                st.error(str(error))
                return

        try:
            with st.spinner(
                "Propagacja SGP4 i sprawdzanie geometrii wszystkich trybów..."
            ):
                result = get_public_access_service().calculate_for_request(
                    request=request,
                    snapshot=snapshot,
                    start_utc=request.earliest_start_utc,
                    end_utc=request.latest_end_utc,
                    step=timedelta(seconds=step_seconds),
                    selected_mode_ids=set(selected_mode_ids),
                )
        except (OrbitPropagationError, ValueError) as error:
            st.error(f"Nie udało się wyznaczyć okien dostępu: {error}")
            return
        st.session_state[_ACCESS_RESULT_STATE_KEY] = result
        st.session_state.get(_PUBLIC_BUILDS_STATE_KEY, {}).pop(
            request.request_id,
            None,
        )

    result = st.session_state.get(_ACCESS_RESULT_STATE_KEY)
    if result is None or result.request_id != request.request_id:
        st.caption(
            "Wybierz tryby i uruchom obliczenia. Wynik zostanie zachowany "
            "w bieżącej sesji aplikacji."
        )
        return

    _render_access_result(result=result, request=request)
    _render_opportunity_builder(result=result, request=request)
