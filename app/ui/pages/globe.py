from __future__ import annotations

import json
from math import sqrt
from datetime import datetime, timedelta, timezone

import plotly
import streamlit as st

from app.integrations.orbits import CelestrakClientError, OrbitPropagationError
from app.services.contracts.planning import PlanningResult
from app.ui.app_context import get_public_orbit_service
from app.ui.orbit_state import get_public_orbit_snapshot, load_public_orbit_snapshot
from app.visualization import build_plotly_globe_scene


_ACCESS_RESULT_STATE_KEY = "public_access_result"
_PUBLIC_PLANNING_RESULT_KEY = "public_planning_result"
_CUSTOM_REQUESTS_STATE_KEY = "custom_observation_requests"


def _default_scene_start() -> datetime:
    planning_result = st.session_state.get(_PUBLIC_PLANNING_RESULT_KEY)
    if isinstance(planning_result, PlanningResult):
        return planning_result.schedule.horizon_start_utc

    access_result = st.session_state.get(_ACCESS_RESULT_STATE_KEY)
    if access_result is not None:
        return access_result.calculation_start_utc

    requests = st.session_state.get(_CUSTOM_REQUESTS_STATE_KEY, [])
    if requests:
        return min(request.earliest_start_utc for request in requests)

    return datetime.now(timezone.utc).replace(microsecond=0)


def _default_horizon_hours() -> int:
    """Dopasowuje horyzont widoku do aktywnego demo lub danych sesji."""

    planning_result = st.session_state.get(_PUBLIC_PLANNING_RESULT_KEY)
    if isinstance(planning_result, PlanningResult):
        duration = (
            planning_result.schedule.horizon_end_utc
            - planning_result.schedule.horizon_start_utc
        )
        hours = duration.total_seconds() / 3600.0
        for option in (48, 36, 24, 12, 6, 3):
            if hours >= option:
                return option

    access_result = st.session_state.get(_ACCESS_RESULT_STATE_KEY)
    if access_result is not None:
        duration = (
            access_result.calculation_end_utc - access_result.calculation_start_utc
        )
        hours = duration.total_seconds() / 3600.0
        for option in (48, 36, 24, 12, 6, 3):
            if hours >= option:
                return option

    return 3


def _scene_export_payload(scene, tracks) -> dict:
    return {
        "renderer": f"Plotly {plotly.__version__}",
        "start_utc": scene.start_utc.isoformat(),
        "end_utc": scene.end_utc.isoformat(),
        "focus_utc": scene.focus_utc.isoformat(),
        "satellite_count": scene.satellite_count,
        "request_count": scene.request_count,
        "access_window_count": scene.access_window_count,
        "scheduled_acquisition_count": scene.scheduled_acquisition_count,
        "tracks": [track.to_dict() for track in tracks],
    }


def _render_category_legend(
    *,
    show_ground_tracks: bool,
    show_aoi: bool,
    show_access: bool,
    show_schedule: bool,
) -> None:
    items = []
    if show_ground_tracks:
        items.extend(
            [
                ("#ff636a", "ICEYE SAR"),
                ("#50a9ff", "Pléiades Neo EO"),
            ]
        )
    if show_aoi:
        items.append(("#fbbf24", "AOI i zlecenia"))
    if show_access:
        items.append(("#f59e0b", "Okna dostępu"))
    if show_schedule:
        items.append(("#34d399", "Planowane akwizycje"))
    if not items:
        return
    chips = "".join(
        (
            '<span style="display:inline-flex;align-items:center;gap:0.45rem;'
            "padding:0.38rem 0.72rem;border:1px solid rgba(148,163,184,.30);"
            "border-radius:999px;background:rgba(15,23,42,.78);"
            'font-size:0.92rem;font-weight:650;white-space:nowrap;">'
            f'<span style="width:0.72rem;height:0.72rem;border-radius:50%;'
            f'background:{color};box-shadow:0 0 0 2px rgba(255,255,255,.12);">'
            "</span>"
            f"{label}</span>"
        )
        for color, label in items
    )
    st.markdown(
        '<div style="display:flex;flex-wrap:wrap;gap:0.55rem;'
        'margin:0.2rem 0 0.7rem 0;">' + chips + "</div>",
        unsafe_allow_html=True,
    )


def render_globe_page() -> None:
    """Renderuje niezależny od Cesium globus operacyjny i orbity 3D."""

    st.header("Globus operacyjny")
    st.caption(
        "Interaktywny obraz konstelacji z publicznych OMM/GP i propagacji "
        "SGP4. Warstwy obejmują ślady naziemne, AOI, okna dostępu oraz "
        "akwizycje wybrane przez planer. Widok działa bez tokenów mapowych."
    )

    snapshot = get_public_orbit_snapshot()
    if snapshot is None:
        st.warning(
            "Brak danych orbitalnych w sesji. Najpierw pobierz OMM w module "
            "„Orbity i dane OMM” albo użyj przycisku poniżej."
        )
        if st.button(
            "Pobierz OMM do wizualizacji",
            type="primary",
            width="stretch",
        ):
            try:
                with st.spinner("Pobieranie publicznych elementów OMM..."):
                    snapshot = load_public_orbit_snapshot(allow_network=True)
            except CelestrakClientError as error:
                st.error(str(error))
                return
        else:
            return

    requests = st.session_state.get(_CUSTOM_REQUESTS_STATE_KEY, [])
    access_result = st.session_state.get(_ACCESS_RESULT_STATE_KEY)
    planning_result = st.session_state.get(_PUBLIC_PLANNING_RESULT_KEY)
    if planning_result is not None and not isinstance(
        planning_result,
        PlanningResult,
    ):
        planning_result = None

    source_metrics = st.columns(4)
    source_metrics[0].metric("Obiekty OMM", len(snapshot.satellites))
    source_metrics[1].metric("AOI w sesji", len(requests))
    source_metrics[2].metric(
        "Okna dostępu",
        len(access_result.windows) if access_result is not None else 0,
    )
    source_metrics[3].metric(
        "Aktywny plan",
        (
            len(planning_result.schedule.active_entries)
            if planning_result is not None
            else 0
        ),
    )

    default_start = _default_scene_start().astimezone(timezone.utc)
    with st.container(border=True):
        st.markdown("### Konfiguracja sceny")
        time_columns = st.columns([1.0, 1.0, 1.0])
        start_date = time_columns[0].date_input(
            "Data początku UTC",
            value=default_start.date(),
        )
        start_time = time_columns[1].time_input(
            "Godzina początku UTC",
            value=default_start.time().replace(tzinfo=None),
            step=timedelta(minutes=1),
        )
        horizon_hours = time_columns[2].select_slider(
            "Horyzont śladów",
            options=[3, 6, 12, 24, 36, 48],
            value=_default_horizon_hours(),
            format_func=lambda value: f"{value} h",
        )

        all_slot_ids = [satellite.slot_id for satellite in snapshot.satellites]
        selection_columns = st.columns([1.6, 1.0, 1.0])
        visible_slots = selection_columns[0].multiselect(
            "Satelity w scenie",
            options=all_slot_ids,
            default=all_slot_ids,
        )
        highlighted_slot_id = selection_columns[1].selectbox(
            "Satelita wyróżniony",
            options=visible_slots or all_slot_ids,
        )
        camera_mode = selection_columns[2].selectbox(
            "Centrowanie globusa",
            options=[
                "Polska i Europa",
                "Wybrany satelita",
                "Widok globalny",
            ],
        )

        st.markdown("#### Warstwy")
        layer_columns = st.columns(6)
        show_ground_tracks = layer_columns[0].toggle(
            "Ślady naziemne",
            value=True,
        )
        show_orbits_3d = layer_columns[1].toggle(
            "Orbity 3D",
            value=True,
        )
        show_aoi = layer_columns[2].toggle(
            "AOI",
            value=True,
            disabled=not requests,
        )
        show_access = layer_columns[3].toggle(
            "Okna dostępu",
            value=True,
            disabled=access_result is None,
        )
        show_schedule = layer_columns[4].toggle(
            "Plan akwizycji",
            value=True,
            disabled=planning_result is None,
        )
        show_satellite_labels = layer_columns[5].toggle(
            "Etykiety",
            value=True,
        )

        with st.expander("Ustawienia renderowania", expanded=False):
            advanced = st.columns(3)
            step_seconds = advanced[0].select_slider(
                "Krok propagacji",
                options=[30, 60, 90, 120, 180, 300],
                value=60,
                format_func=lambda value: f"{value} s",
            )
            height_px = advanced[1].select_slider(
                "Wysokość wykresów",
                options=[620, 700, 780, 860, 940],
                value=780,
                format_func=lambda value: f"{value} px",
            )
            show_graticule = advanced[2].toggle(
                "Siatka geograficzna",
                value=True,
                help=(
                    "Siatka jest rysowana lokalnie i pozostaje widoczna "
                    "bez zewnętrznych usług mapowych."
                ),
            )

    if not visible_slots:
        st.warning("Wybierz co najmniej jednego satelitę do wizualizacji.")
        return

    start_utc = datetime.combine(
        start_date,
        start_time,
        tzinfo=timezone.utc,
    )
    selected_slot_ids = set(visible_slots)
    selected_satellites = tuple(
        satellite
        for satellite in snapshot.satellites
        if satellite.slot_id in selected_slot_ids
    )
    selected_snapshot = type(snapshot)(
        generated_at_utc=snapshot.generated_at_utc,
        satellites=selected_satellites,
        queries=snapshot.queries,
        warnings=snapshot.warnings,
    )

    try:
        with st.spinner("Propagacja SGP4 i przygotowanie śladów..."):
            tracks = get_public_orbit_service().propagate_snapshot(
                selected_snapshot,
                start_utc=start_utc,
                duration=timedelta(hours=horizon_hours),
                step=timedelta(seconds=step_seconds),
            )
    except (OrbitPropagationError, ValueError) as error:
        st.error(f"Nie udało się przygotować danych wizualizacji: {error}")
        return

    horizon_minutes = horizon_hours * 60
    slider_step = max(1, step_seconds // 60)
    focus_offset_minutes = st.slider(
        "Oś czasu sceny",
        min_value=0,
        max_value=horizon_minutes,
        value=0,
        step=slider_step,
        format="%d min",
        help=(
            "Pozycje satelitów są pokazywane dla wybranej chwili, natomiast "
            "ślady obejmują cały horyzont propagacji."
        ),
    )
    focus_utc = start_utc + timedelta(minutes=focus_offset_minutes)

    highlighted_track = next(
        track
        for track in tracks
        if track.satellite.slot_id == highlighted_slot_id
    )
    highlighted_state = min(
        highlighted_track.states,
        key=lambda state: abs(
            (state.timestamp_utc - focus_utc).total_seconds()
        ),
    )
    speed_km_s = sqrt(
        sum(value * value for value in highlighted_state.teme_velocity_km_s)
    )

    if camera_mode == "Wybrany satelita":
        center_longitude_deg = highlighted_state.longitude_deg
        center_latitude_deg = highlighted_state.latitude_deg
        projection_scale = 1.42
    elif camera_mode == "Widok globalny":
        center_longitude_deg = 0.0
        center_latitude_deg = 10.0
        projection_scale = 1.02
    else:
        center_longitude_deg = 19.0
        center_latitude_deg = 52.0
        projection_scale = 1.22

    try:
        scene = build_plotly_globe_scene(
            tracks=tracks,
            requests=requests,
            access_result=access_result,
            planning_result=planning_result,
            focus_utc=focus_utc,
            show_ground_tracks=show_ground_tracks,
            show_orbits_3d=show_orbits_3d,
            show_aoi=show_aoi,
            show_access_windows=show_access,
            show_schedule=show_schedule,
            show_graticule=show_graticule,
            highlighted_slot_id=highlighted_slot_id,
            show_satellite_labels=show_satellite_labels,
            center_longitude_deg=center_longitude_deg,
            center_latitude_deg=center_latitude_deg,
            projection_scale=projection_scale,
            height_px=height_px,
        )
    except ValueError as error:
        st.error(f"Nie udało się zbudować globusa Plotly: {error}")
        return

    focus_metrics = st.columns(6)
    focus_metrics[0].metric("Czas UTC", focus_utc.strftime("%H:%M:%S"))
    focus_metrics[1].metric("Satelita", highlighted_slot_id)
    focus_metrics[2].metric(
        "Szerokość",
        f"{highlighted_state.latitude_deg:.2f}°",
    )
    focus_metrics[3].metric(
        "Długość",
        f"{highlighted_state.longitude_deg:.2f}°",
    )
    focus_metrics[4].metric(
        "Wysokość",
        f"{highlighted_state.altitude_km:.0f} km",
    )
    focus_metrics[5].metric("Prędkość", f"{speed_km_s:.2f} km/s")

    st.caption(
        f"Propagacja: {scene.start_utc.isoformat()} – "
        f"{scene.end_utc.isoformat()} · pozycja: {scene.focus_utc.isoformat()} · "
        f"renderer Plotly {plotly.__version__}."
    )

    _render_category_legend(
        show_ground_tracks=show_ground_tracks,
        show_aoi=show_aoi,
        show_access=show_access,
        show_schedule=show_schedule,
    )

    operational_tab, spatial_tab, data_tab = st.tabs(
        ["Globus operacyjny", "Orbity przestrzenne 3D", "Dane sceny"]
    )
    chart_config = {
        "displaylogo": False,
        "scrollZoom": True,
        "responsive": True,
        "modeBarButtonsToRemove": ["select2d", "lasso2d"],
        "toImageButtonOptions": {
            "format": "png",
            "filename": "satplan-operational-globe",
            "scale": 2,
        },
    }
    with operational_tab:
        st.plotly_chart(
            scene.operational_figure,
            width="stretch",
            config=chart_config,
            key="satplan_operational_globe",
            theme=None,
        )
        st.caption(
            "Obracaj globus myszą i użyj kółka do zmiany skali. Wyróżniony "
            "satelita ma większy znacznik oraz mocniejszy ślad. Pomarańczowe "
            "odcinki oznaczają okna dostępu, a zielone — plan akwizycji."
        )

    with spatial_tab:
        st.plotly_chart(
            scene.spatial_figure,
            width="stretch",
            config=chart_config,
            key="satplan_spatial_orbits",
            theme=None,
        )
        st.caption(
            "Widok 3D przedstawia modelowaną geometrię orbit i wysokość "
            "satelitów nad kulą Ziemi. Kamera pozostaje zachowana między "
            "kolejnymi zmianami warstw."
        )

    with data_tab:
        rows = []
        for track in tracks:
            state = min(
                track.states,
                key=lambda item: abs(
                    (item.timestamp_utc - focus_utc).total_seconds()
                ),
            )
            velocity = sqrt(
                sum(value * value for value in state.teme_velocity_km_s)
            )
            rows.append(
                {
                    "Satelita": track.satellite.slot_id,
                    "Rodzina": track.satellite.family.value,
                    "Obiekt": track.satellite.record.object_name,
                    "NORAD": track.satellite.record.norad_cat_id,
                    "Szerokość [°]": round(state.latitude_deg, 4),
                    "Długość [°]": round(state.longitude_deg, 4),
                    "Wysokość [km]": round(state.altitude_km, 2),
                    "Prędkość [km/s]": round(velocity, 3),
                    "Epoka OMM": track.satellite.record.epoch_utc,
                }
            )
        st.dataframe(rows, width="stretch", hide_index=True)

    export_payload = _scene_export_payload(scene, tracks)
    st.download_button(
        "Pobierz dane wizualizacji JSON",
        data=json.dumps(export_payload, ensure_ascii=False, indent=2),
        file_name=(
            f"public_orbits_{scene.start_utc.strftime('%Y%m%dT%H%M%SZ')}.json"
        ),
        mime="application/json",
        width="stretch",
    )

    with st.expander("Metodyka i ograniczenia wizualizacji"):
        st.markdown(
            """
- **Globus operacyjny:** lokalna projekcja ortograficzna Plotly.
- **Ślad naziemny:** rzut propagowanej trajektorii OMM/SGP4 na WGS84.
- **Orbity przestrzenne:** pozycje wyliczone z szerokości, długości i wysokości satelity.
- **AOI:** geometrie użytkownika zapisane w WGS84.
- **Okna dostępu:** fragmenty śladu spełniające model geometrii sensora.
- **Plan:** połączenie pozycji satelity z celem w czasie zaplanowanej akwizycji.
- Wizualizacja nie stanowi potwierdzenia operacyjnego taskingu operatora satelity.
            """
        )
