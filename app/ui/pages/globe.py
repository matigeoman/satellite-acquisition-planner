from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import streamlit as st

from app.integrations.orbits import CelestrakClientError, OrbitPropagationError
from app.services.contracts.planning import PlanningResult
from app.ui.app_context import get_public_orbit_service
from app.ui.components.cesium_globe import CESIUM_VERSION, render_cesium_globe
from app.ui.orbit_state import get_public_orbit_snapshot, load_public_orbit_snapshot
from app.visualization import build_cesium_scene


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


def render_globe_page() -> None:
    """Renderuje animowany globus 3D z orbitami i planem akwizycji."""

    st.header("Globus operacyjny 3D")
    st.info(
        "Widok pokazuje pozycje satelitów, ground tracki na powierzchni "
        "Ziemi, AOI, okna dostępu i ostatni harmonogram publiczny. "
        "Domyślnie eksponowane są ground tracki, a pełne orbity 3D można "
        "włączyć osobno."
    )

    snapshot = get_public_orbit_snapshot()
    if snapshot is None:
        st.warning(
            "Brak danych orbitalnych w sesji. Najpierw pobierz OMM w module "
            "„Orbity publiczne” albo użyj przycisku poniżej."
        )
        if st.button(
            "Pobierz OMM do widoku 3D",
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
        row = st.columns([1.15, 1.0, 1.0])
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
            "Horyzont animacji",
            options=[1, 2, 3, 6, 12, 24],
            value=3,
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
            "Ground tracki",
            value=True,
        )
        show_orbits_3d = layer_columns[1].toggle(
            "Orbity 3D",
            value=False,
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
                "Wysokość globusa",
                options=[650, 760, 820, 920, 1040],
                value=760,
                format_func=lambda value: f"{value} px",
            )
            show_footprints = advanced[2].toggle(
                "Nominalne footprinty",
                value=True,
                disabled=access_result is None,
                help=(
                    "Przybliżona scena trybu obrazowania, a nie operacyjny "
                    "footprint operatora."
                ),
            )

    if not visible_slots:
        st.warning("Wybierz co najmniej jeden satelita do wizualizacji.")
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
        with st.spinner("Propagacja SGP4 i budowanie animowanej sceny CZML..."):
            tracks = get_public_orbit_service().propagate_snapshot(
                selected_snapshot,
                start_utc=start_utc,
                duration=timedelta(hours=horizon_hours),
                step=timedelta(seconds=step_seconds),
            )
            scene = build_cesium_scene(
                tracks=tracks,
                requests=requests,
                access_result=access_result,
                planning_result=planning_result,
                show_aoi=show_aoi,
                show_orbits_3d=show_orbits_3d,
                show_ground_tracks=show_ground_tracks,
                show_access_windows=show_access,
                show_footprints=show_footprints,
                show_schedule=show_schedule,
            )
    except (OrbitPropagationError, ValueError) as error:
        st.error(f"Nie udało się zbudować globusa 3D: {error}")
        return

    metrics = st.columns(5)
    metrics[0].metric("Satelity", scene.satellite_count)
    metrics[1].metric("AOI", scene.request_count)
    metrics[2].metric("Okna dostępu", scene.access_window_count)
    metrics[3].metric("Akwizycje w planie", scene.scheduled_acquisition_count)
    metrics[4].metric("CesiumJS", CESIUM_VERSION)

    st.caption(
        f"Scena: {scene.start_utc.isoformat()} – {scene.end_utc.isoformat()}. "
        "Przycisk „Pokaż Ziemię” przywraca pełny globus, a „Cała scena” "
        "dopasowuje kamerę do wszystkich obiektów."
    )
    render_cesium_globe(scene, height_px=height_px)

    st.download_button(
        "Pobierz scenę CZML",
        data=scene.to_json(indent=2),
        file_name=(f"public_globe_{scene.start_utc.strftime('%Y%m%dT%H%M%SZ')}.czml"),
        mime="application/json",
        width="stretch",
    )

    with st.expander("Warstwy i ograniczenia wizualizacji"):
        st.markdown(
            "- **Ground track:** rzut propagowanej trajektorii na WGS84.\n"
            "- **Orbita 3D:** pozycja satelity na rzeczywistej wysokości modelu.\n"
            "- **AOI:** geometrie WGS84 z modułu zleceń.\n"
            "- **Footprint:** nominalny rozmiar sceny trybu, bez pełnego "
            "modelu orientacji wiązki.\n"
            "- **Okna dostępu:** pomarańczowa wiązka dla najlepszego punktu "
            "okna.\n"
            "- **Plan:** zielona wiązka widoczna w czasie akwizycji.\n"
            "- Gdy kafelki mapowe nie zadziałają, Cesium pozostawia widoczną "
            "niebieską elipsoidę Ziemi."
        )
        st.code(
            json.dumps(
                {
                    "start_utc": scene.start_utc.isoformat(),
                    "end_utc": scene.end_utc.isoformat(),
                    "satellites": scene.satellite_count,
                    "requests": scene.request_count,
                    "access_windows": scene.access_window_count,
                    "scheduled_acquisitions": scene.scheduled_acquisition_count,
                    "ground_tracks": show_ground_tracks,
                    "orbits_3d": show_orbits_3d,
                    "footprints": show_footprints,
                },
                ensure_ascii=False,
                indent=2,
            ),
            language="json",
        )
