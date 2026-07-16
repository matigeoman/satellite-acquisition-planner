from __future__ import annotations

import json
from datetime import timedelta

import streamlit as st

from app.catalogs import ICEYE_PUBLIC_PROFILE, PLEIADES_NEO_PUBLIC_PROFILE
from app.integrations.orbits import CelestrakClientError, OrbitPropagationError
from app.models.enums import SensorType
from app.models.request import ObservationRequest
from app.ui.access_view import (
    access_windows_dataframe,
    build_access_map_figure,
    build_access_timeline_figure,
)
from app.ui.app_context import get_public_access_service
from app.ui.orbit_state import (
    get_public_orbit_snapshot,
    load_public_orbit_snapshot,
)


_ACCESS_RESULT_STATE_KEY = "public_access_result"


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
        if mode.is_active and mode.nominal_resolution_m <= request.max_resolution_m
    ]


def _mode_label(mode) -> str:
    return (
        f"{mode.name} · {mode.nominal_resolution_m:g} m · "
        f"{mode.nominal_scene_width_km:g}×"
        f"{mode.nominal_scene_length_km:g} km"
    )


def render_access_page() -> None:
    """Wyznacza okna dostępu dla zleceń utworzonych na mapie."""

    st.header("Okna dostępu z publicznych orbit")
    st.info(
        "Ten etap łączy zlecenie Point/Polygon, publiczne OMM, propagację "
        "SGP4 oraz publiczne profile ICEYE i Pléiades Neo. Wyniki są "
        "orientacyjnymi oknami geometrycznymi, a nie potwierdzeniem taskingu."
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
            "Tylko lokalny cache",
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

    result = st.session_state.get(_ACCESS_RESULT_STATE_KEY)
    if result is None or result.request_id != request.request_id:
        st.caption(
            "Wybierz tryby i uruchom obliczenia. Wynik zostanie zachowany "
            "w bieżącej sesji aplikacji."
        )
        return

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

    st.warning(
        "Dla EO uwzględniono geometrię i elewację Słońca, ale jeszcze nie "
        "prognozę zachmurzenia. Pokrycie Polygon jest przybliżeniem na "
        "podstawie bounding box i nominalnego footprintu trybu."
    )

    if not result.windows:
        return

    st.subheader("Mapa segmentów dostępu")
    access_map = build_access_map_figure(result, request.geometry)
    st.plotly_chart(
        access_map,
        use_container_width=True,
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
        use_container_width=True,
        config={"displaylogo": False, "responsive": True},
    )

    table = access_windows_dataframe(result)
    st.subheader("Tabela okien")
    st.dataframe(
        table,
        use_container_width=True,
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
