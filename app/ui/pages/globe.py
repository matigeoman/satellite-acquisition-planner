from __future__ import annotations

import json
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
    st.info(
        "Widok wykorzystuje natywne wykresy Plotly. Nie wymaga Cesium Ion, "
        "tokenów Mapbox, kafelków OpenStreetMap ani własnego komponentu "
        "JavaScript. Główny globus pokazuje Ziemię, ślady naziemne, AOI, "
        "okna dostępu i planowane akwizycje. Druga karta przedstawia "
        "przestrzenną geometrię orbit."
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

    default_start = _default_scene_start().astimezone(timezone.utc)
    with st.container(border=True):
        st.markdown("### Konfiguracja sceny")
        row = st.columns([1.1, 1.0, 1.0])
        start_date = row[0].date_input(
            "Data początku UTC",
            value=default_start.date(),
        )
        start_time = row[1].time_input(
            "Godzina początku UTC",
            value=default_start.time().replace(tzinfo=None),
            step=timedelta(minutes=1),
        )
        horizon_hours = row[2].select_slider(
            "Horyzont śladów",
            options=[3, 6, 12, 24, 36, 48],
            value=_default_horizon_hours(),
            format_func=lambda value: f"{value} h",
        )

        all_slot_ids = [satellite.slot_id for satellite in snapshot.satellites]
        visible_slots = st.multiselect(
            "Satelity w scenie",
            options=all_slot_ids,
            default=all_slot_ids,
        )

        layer_columns = st.columns(5)
        show_ground_tracks = layer_columns[0].toggle(
            "Ślady naziemne",
            value=True,
        )
        show_orbits_3d = layer_columns[1].toggle(
            "Orbity przestrzenne",
            value=True,
        )
        show_aoi = layer_columns[2].toggle(
            "AOI i zlecenia",
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

        with st.expander("Ustawienia zaawansowane"):
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
                    "nawet bez warstwy granic i wybrzeży."
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
        "Moment wizualizacji",
        min_value=0,
        max_value=horizon_minutes,
        value=0,
        step=slider_step,
        format="%d min",
        help=(
            "Określa moment pokazania bieżących pozycji satelitów. "
            "Ślady naziemne obejmują cały wybrany horyzont. "
            "Dla projektu demonstracyjnego domyślnie używane jest 48 h."
        ),
    )
    focus_utc = start_utc + timedelta(minutes=focus_offset_minutes)

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
            height_px=height_px,
        )
    except ValueError as error:
        st.error(f"Nie udało się zbudować globusa Plotly: {error}")
        return

    metrics = st.columns(5)
    metrics[0].metric("Satelity", scene.satellite_count)
    metrics[1].metric("AOI", scene.request_count)
    metrics[2].metric("Okna dostępu", scene.access_window_count)
    metrics[3].metric("Akwizycje w planie", scene.scheduled_acquisition_count)
    metrics[4].metric("Renderer", f"Plotly {plotly.__version__}")

    st.caption(
        f"Ślady: {scene.start_utc.isoformat()} – {scene.end_utc.isoformat()}; "
        f"pozycje bieżące: {scene.focus_utc.isoformat()}. Obracanie globusa "
        "odbywa się bezpośrednio myszą."
    )

    _render_category_legend(
        show_ground_tracks=show_ground_tracks,
        show_aoi=show_aoi,
        show_access=show_access,
        show_schedule=show_schedule,
    )

    operational_tab, spatial_tab = st.tabs(
        ["Globus operacyjny", "Orbity przestrzenne 3D"]
    )
    chart_config = {
        "displaylogo": False,
        "scrollZoom": True,
        "responsive": True,
        "modeBarButtonsToRemove": ["select2d", "lasso2d"],
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
            "Globus operacyjny pokazuje ślady naziemne jako rzut trajektorii "
            "na powierzchnię Ziemi. Pomarańczowe odcinki oznaczają okna "
            "dostępu, a zielone połączenia — akwizycje wybrane przez planner."
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
            "Widok przestrzenny przedstawia satelity na modelowanej "
            "wysokości nad kulą Ziemi. Nie jest zależny od zewnętrznych "
            "tekstur ani usług mapowych."
        )

    export_payload = _scene_export_payload(scene, tracks)
    st.download_button(
        "Pobierz dane wizualizacji JSON",
        data=json.dumps(export_payload, ensure_ascii=False, indent=2),
        file_name=(f"public_orbits_{scene.start_utc.strftime('%Y%m%dT%H%M%SZ')}.json"),
        mime="application/json",
        width="stretch",
    )

    with st.expander("Warstwy i ograniczenia wizualizacji"):
        st.markdown(
            "- **Globus operacyjny:** projekcja ortograficzna Plotly z "
            "wbudowanym oceanem, lądami i lokalną siatką geograficzną.\n"
            "- **Ślad naziemny:** rzut propagowanej trajektorii OMM/SGP4 na "
            "WGS84.\n"
            "- **Orbity przestrzenne:** pozycje wyliczone z szerokości, "
            "długości i wysokości satelity.\n"
            "- **AOI:** geometrie użytkownika zapisane w WGS84.\n"
            "- **Okna dostępu:** fragmenty śladu spełniające publiczny model "
            "geometrii sensora.\n"
            "- **Plan:** połączenie pozycji satelity z celem w czasie "
            "zaplanowanej akwizycji.\n"
            "- Plotly nie potwierdza operacyjnej dostępności operatora; "
            "wizualizuje wyniki modelu publicznego."
        )
