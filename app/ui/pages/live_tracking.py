from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import pandas as pd
import streamlit as st

from app.integrations.orbits import (
    CelestrakClientError,
    OrbitPropagationError,
    SatelliteGroundTrack,
)
from app.projects.service import (
    ACCESS_RESULT_STATE_KEY,
    PLANNING_RESULT_STATE_KEY,
)
from app.services.contracts import PlanningResult
from app.services.orbit_service import PublicConstellationSnapshot
from app.tracking import (
    LiveTrackingService,
    ObserverSite,
    OpticalVisibility,
    OrbitDataQuality,
    PassPrediction,
)
from app.ui.app_context import (
    get_live_tracking_service,
    get_public_orbit_service,
)
from app.ui.orbit_state import (
    get_public_orbit_snapshot,
    load_public_orbit_snapshot,
)
from app.visualization import (
    build_live_ground_map_figure,
    build_sky_map_figure,
)


_TRACKING_MODE_KEY = "live_tracking_mode"
_TRACKING_PLAYING_KEY = "live_tracking_playing"
_TRACKING_SPEED_KEY = "live_tracking_speed"
_TRACKING_SIM_START_KEY = "live_tracking_sim_start"
_TRACKING_ANCHOR_SIM_KEY = "live_tracking_anchor_sim"
_TRACKING_ANCHOR_WALL_KEY = "live_tracking_anchor_wall"
_TRACKING_SIGNATURE_KEY = "live_tracking_signature"


_OBSERVER_PRESETS = {
    "WAT Warszawa": ObserverSite(
        name="WAT Warszawa",
        latitude_deg=52.2532,
        longitude_deg=20.8997,
        altitude_m=110.0,
    ),
    "Warszawa — centrum": ObserverSite(
        name="Warszawa",
        latitude_deg=52.2297,
        longitude_deg=21.0122,
        altitude_m=100.0,
    ),
    "Białystok": ObserverSite(
        name="Białystok",
        latitude_deg=53.1325,
        longitude_deg=23.1688,
        altitude_m=145.0,
    ),
    "Gdańsk": ObserverSite(
        name="Gdańsk",
        latitude_deg=54.3520,
        longitude_deg=18.6466,
        altitude_m=15.0,
    ),
    "Kraków": ObserverSite(
        name="Kraków",
        latitude_deg=50.0647,
        longitude_deg=19.9450,
        altitude_m=220.0,
    ),
}


def _snapshot_hash(snapshot: PublicConstellationSnapshot) -> tuple:
    return tuple(
        (
            satellite.slot_id,
            satellite.record.norad_cat_id,
            satellite.record.epoch_utc.isoformat(),
            satellite.record.mean_motion_rev_per_day,
        )
        for satellite in snapshot.satellites
    )


@st.cache_data(
    ttl=300,
    show_spinner=False,
    hash_funcs={PublicConstellationSnapshot: _snapshot_hash},
)
def _cached_pass_predictions(
    snapshot: PublicConstellationSnapshot,
    observer: ObserverSite,
    start_utc: datetime,
    duration_hours: int,
    minimum_elevation_deg: float,
    slot_ids: tuple[str, ...],
) -> tuple[PassPrediction, ...]:
    rounded_start = start_utc.replace(second=0, microsecond=0)
    return LiveTrackingService().predict_passes(
        snapshot,
        observer=observer,
        start_utc=rounded_start,
        duration=timedelta(hours=duration_hours),
        step=timedelta(seconds=30),
        minimum_elevation_deg=minimum_elevation_deg,
        slot_ids=slot_ids,
    )


def _resolve_observer() -> ObserverSite:
    with st.container(border=True):
        st.markdown("### Punkt obserwacyjny")
        preset_name = st.selectbox(
            "Lokalizacja",
            options=[*_OBSERVER_PRESETS, "Własna lokalizacja"],
        )
        if preset_name != "Własna lokalizacja":
            preset = _OBSERVER_PRESETS[preset_name]
            st.caption(
                f"{preset.latitude_deg:.4f}°, {preset.longitude_deg:.4f}° · "
                f"{preset.altitude_m:.0f} m n.p.m."
            )
            return preset

        columns = st.columns(3)
        latitude = columns[0].number_input(
            "Szerokość [°]",
            min_value=-90.0,
            max_value=90.0,
            value=52.2297,
            step=0.0001,
            format="%.4f",
        )
        longitude = columns[1].number_input(
            "Długość [°]",
            min_value=-180.0,
            max_value=180.0,
            value=21.0122,
            step=0.0001,
            format="%.4f",
        )
        altitude = columns[2].number_input(
            "Wysokość [m]",
            min_value=-500.0,
            max_value=10000.0,
            value=100.0,
            step=10.0,
        )
        return ObserverSite(
            name="Własna lokalizacja",
            latitude_deg=float(latitude),
            longitude_deg=float(longitude),
            altitude_m=float(altitude),
        )


def _initialize_time_anchor(
    *,
    mode: str,
    playing: bool,
    speed: int,
    simulation_start: datetime,
) -> None:
    signature = (mode, playing, speed, simulation_start.isoformat())
    if st.session_state.get(_TRACKING_SIGNATURE_KEY) == signature:
        return
    st.session_state[_TRACKING_SIGNATURE_KEY] = signature
    st.session_state[_TRACKING_ANCHOR_SIM_KEY] = simulation_start
    st.session_state[_TRACKING_ANCHOR_WALL_KEY] = datetime.now(timezone.utc)


def _current_focus_time() -> datetime:
    mode = st.session_state.get(_TRACKING_MODE_KEY, "Na żywo")
    if mode == "Na żywo":
        return datetime.now(timezone.utc)

    base = st.session_state.get(_TRACKING_ANCHOR_SIM_KEY)
    wall = st.session_state.get(_TRACKING_ANCHOR_WALL_KEY)
    if not isinstance(base, datetime) or not isinstance(wall, datetime):
        return datetime.now(timezone.utc)
    if not st.session_state.get(_TRACKING_PLAYING_KEY, False):
        return base
    elapsed = datetime.now(timezone.utc) - wall
    speed = int(st.session_state.get(_TRACKING_SPEED_KEY, 1))
    return base + elapsed * speed


def _render_time_controls(snapshot: PublicConstellationSnapshot) -> None:
    with st.container(border=True):
        st.markdown("### Czas i propagacja")
        first = st.columns([1.1, 1.0, 1.0, 1.0])
        mode = first[0].radio(
            "Tryb czasu",
            options=["Na żywo", "Symulacja"],
            horizontal=True,
            key=_TRACKING_MODE_KEY,
        )
        playing = first[1].toggle(
            "Odtwarzanie",
            value=mode == "Na żywo",
            disabled=mode == "Na żywo",
            key=_TRACKING_PLAYING_KEY,
        )
        speed = first[2].select_slider(
            "Prędkość",
            options=[1, 10, 60],
            value=1,
            format_func=lambda value: f"{value}×",
            disabled=mode == "Na żywo" or not playing,
            key=_TRACKING_SPEED_KEY,
        )
        first[3].metric("Obiekty OMM", len(snapshot.satellites))

        default_time = min(
            satellite.record.epoch_utc for satellite in snapshot.satellites
        )
        if mode == "Symulacja":
            second = st.columns(2)
            selected_date = second[0].date_input(
                "Data UTC",
                value=default_time.date(),
                key="live_tracking_date",
            )
            selected_time = second[1].time_input(
                "Godzina UTC",
                value=default_time.time().replace(tzinfo=None),
                # Streamlit wymaga kroku od 60 sekund do 23 godzin.
                step=timedelta(minutes=1),
                key="live_tracking_time",
            )
            simulation_start = datetime.combine(
                selected_date,
                selected_time,
                tzinfo=timezone.utc,
            )
        else:
            simulation_start = datetime.now(timezone.utc)

        _initialize_time_anchor(
            mode=mode,
            playing=bool(playing),
            speed=int(speed),
            simulation_start=simulation_start,
        )


def _quality_label(value: OrbitDataQuality) -> str:
    return {
        OrbitDataQuality.FRESH: "świeże",
        OrbitDataQuality.ACCEPTABLE: "akceptowalne",
        OrbitDataQuality.STALE: "stare",
        OrbitDataQuality.VERY_STALE: "bardzo stare",
    }[value]


def _visibility_label(value: OpticalVisibility) -> str:
    return {
        OpticalVisibility.VISIBLE: "widoczny optycznie",
        OpticalVisibility.BELOW_HORIZON: "pod horyzontem",
        OpticalVisibility.SATELLITE_IN_SHADOW: "w cieniu Ziemi",
        OpticalVisibility.SKY_TOO_BRIGHT: "niebo zbyt jasne",
    }[value]


def _pass_dataframe(passes: tuple[PassPrediction, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Satelita": item.slot_id,
                "Nazwa": item.object_name,
                "AOS UTC": item.aos_utc,
                "MAX UTC": item.maximum_utc,
                "LOS UTC": item.los_utc,
                "Maks. elewacja [°]": round(item.maximum_elevation_deg, 1),
                "Czas [min]": round(item.duration_minutes, 1),
                "Azymut AOS [°]": round(item.aos_azimuth_deg, 1),
                "Azymut LOS [°]": round(item.los_azimuth_deg, 1),
                "Min. odległość [km]": round(item.minimum_range_km),
                "Widoczność": _visibility_label(
                    item.optical_visibility_at_maximum
                ),
            }
            for item in passes
        ]
    )


def _operational_context_dataframe(
    *,
    selected_slot_id: str,
    start_utc: datetime,
    end_utc: datetime,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    access_result = st.session_state.get(ACCESS_RESULT_STATE_KEY)
    if access_result is not None:
        for window in access_result.windows:
            if window.satellite_id != selected_slot_id:
                continue
            if window.end_utc < start_utc or window.start_utc > end_utc:
                continue
            rows.append(
                {
                    "Typ": "Okno dostępu",
                    "Początek UTC": window.start_utc,
                    "Koniec UTC": window.end_utc,
                    "Zlecenie": window.request_id,
                    "Tryb": window.mode_name,
                    "Status": "dostępne",
                }
            )

    planning = st.session_state.get(PLANNING_RESULT_STATE_KEY)
    if isinstance(planning, PlanningResult):
        for entry in planning.schedule.active_entries:
            if entry.satellite_id != selected_slot_id:
                continue
            if entry.end_utc < start_utc or entry.start_utc > end_utc:
                continue
            rows.append(
                {
                    "Typ": "Akwizycja",
                    "Początek UTC": entry.start_utc,
                    "Koniec UTC": entry.end_utc,
                    "Zlecenie": entry.request_id,
                    "Tryb": entry.mode_id,
                    "Status": entry.status.value,
                }
            )
    return pd.DataFrame(rows).sort_values("Początek UTC") if rows else pd.DataFrame()


@st.fragment(run_every="2s")
def _render_live_fragment(
    *,
    snapshot: PublicConstellationSnapshot,
    observer: ObserverSite,
    slot_ids: tuple[str, ...],
    selected_slot_id: str,
    minimum_elevation_deg: float,
    forecast_hours: int,
    footprint_radius_km: float,
) -> None:
    focus_utc = _current_focus_time()
    service = get_live_tracking_service()
    try:
        states = service.current_states(
            snapshot,
            observer=observer,
            timestamp_utc=focus_utc,
            slot_ids=slot_ids,
        )
        sky_tracks = service.sky_tracks(
            snapshot,
            observer=observer,
            start_utc=focus_utc,
            duration=timedelta(minutes=45),
            step=timedelta(seconds=30),
            slot_ids=slot_ids,
        )
        map_tracks: tuple[SatelliteGroundTrack, ...] = tuple(
            get_public_orbit_service().propagate_snapshot(
                type(snapshot)(
                    generated_at_utc=snapshot.generated_at_utc,
                    satellites=tuple(
                        satellite
                        for satellite in snapshot.satellites
                        if satellite.slot_id in slot_ids
                    ),
                    queries=snapshot.queries,
                    warnings=snapshot.warnings,
                ),
                start_utc=focus_utc - timedelta(minutes=45),
                duration=timedelta(minutes=90),
                step=timedelta(minutes=1),
            )
        )
        passes = _cached_pass_predictions(
            snapshot,
            observer,
            focus_utc,
            forecast_hours,
            minimum_elevation_deg,
            slot_ids,
        )
    except (OrbitPropagationError, ValueError) as error:
        st.error(f"Nie udało się wyznaczyć śledzenia: {error}")
        return

    current = next(
        (item for item in states if item.slot_id == selected_slot_id),
        states[0],
    )
    metrics = st.columns(7)
    metrics[0].metric("Czas UTC", focus_utc.strftime("%H:%M:%S"))
    metrics[1].metric("Nad horyzontem", sum(s.topocentric.is_above_horizon for s in states))
    metrics[2].metric("Satelita", current.slot_id)
    metrics[3].metric("Elewacja", f"{current.topocentric.elevation_deg:.1f}°")
    metrics[4].metric("Azymut", f"{current.topocentric.azimuth_deg:.1f}°")
    metrics[5].metric("Odległość", f"{current.topocentric.range_km:.0f} km")
    metrics[6].metric("OMM age", f"{current.orbit_data_age_hours:.1f} h")

    st.caption(
        f"{focus_utc.isoformat()} · {current.object_name} · "
        f"{_visibility_label(current.visibility.optical_visibility)} · "
        f"dane orbitalne: {_quality_label(current.orbit_data_quality)}. "
        "Pozycja jest propagowana z OMM/SGP4; nie jest telemetrią pokładową."
    )

    sky_tab, earth_tab, passes_tab, context_tab = st.tabs(
        ["Mapa nieba", "Mapa Ziemi", "Najbliższe przeloty", "Kontekst planera"]
    )
    with sky_tab:
        st.plotly_chart(
            build_sky_map_figure(
                states=states,
                tracks=sky_tracks,
                minimum_elevation_deg=0.0,
            ),
            width="stretch",
            config={"displaylogo": False, "responsive": True},
        )
        state_table = pd.DataFrame(
            [
                {
                    "Satelita": item.slot_id,
                    "Nazwa": item.object_name,
                    "Azymut [°]": round(item.topocentric.azimuth_deg, 2),
                    "Elewacja [°]": round(item.topocentric.elevation_deg, 2),
                    "Odległość [km]": round(item.topocentric.range_km, 1),
                    "Prędkość radialna [km/s]": (
                        round(item.topocentric.range_rate_km_s, 4)
                        if item.topocentric.range_rate_km_s is not None
                        else None
                    ),
                    "Wysokość [km]": round(item.propagated.altitude_km, 1),
                    "Prędkość orbitalna [km/s]": round(item.speed_km_s, 3),
                    "Widoczność": _visibility_label(
                        item.visibility.optical_visibility
                    ),
                    "Jakość OMM": _quality_label(item.orbit_data_quality),
                }
                for item in states
            ]
        )
        st.dataframe(state_table, width="stretch", hide_index=True)

    with earth_tab:
        st.plotly_chart(
            build_live_ground_map_figure(
                observer=observer,
                states=states,
                tracks=map_tracks,
                timestamp_utc=focus_utc,
                selected_slot_id=selected_slot_id,
                footprint_radius_km=footprint_radius_km,
            ),
            width="stretch",
            config={"displaylogo": False, "responsive": True},
        )
        st.caption(
            "Zielony okrąg jest referencyjnym footprintem prezentacyjnym. "
            "Nie zastępuje geometrii konkretnego trybu obrazowania. "
            "Linia kropkowana pokazuje terminator dnia i nocy."
        )

    with passes_tab:
        if not passes:
            st.info("Brak przelotów spełniających wybrany próg elewacji.")
        else:
            st.dataframe(
                _pass_dataframe(passes),
                width="stretch",
                hide_index=True,
                height=520,
            )
            st.download_button(
                "Pobierz predykcję przelotów JSON",
                data=pd.Series([item.to_dict() for item in passes]).to_json(
                    force_ascii=False,
                    orient="values",
                    date_format="iso",
                    indent=2,
                ),
                file_name="satplan-pass-predictions.json",
                mime="application/json",
                width="stretch",
            )

    with context_tab:
        context = _operational_context_dataframe(
            selected_slot_id=selected_slot_id,
            start_utc=focus_utc,
            end_utc=focus_utc + timedelta(hours=forecast_hours),
        )
        if context.empty:
            st.info(
                "Dla wybranego satelity nie ma w tym przedziale aktywnych "
                "okien access ani zaplanowanych akwizycji w stanie sesji."
            )
        else:
            st.dataframe(context, width="stretch", hide_index=True)


def render_live_tracking_page() -> None:
    """Renderuje mapę nieba, pozycje SGP4 i predykcję przelotów."""

    st.header("Śledzenie satelitów na żywo")
    st.info(
        "Moduł propaguje publiczne OMM przez SGP4, przelicza pozycję do "
        "lokalnego układu azymut–elewacja i przewiduje przeloty AOS/MAX/LOS. "
        "Tryb działa również offline na danych scenariusza demonstracyjnego."
    )

    snapshot = get_public_orbit_snapshot()
    if snapshot is None:
        st.warning(
            "Brak danych OMM w sesji. Wczytaj Poland Demo albo pobierz "
            "publiczny snapshot CelesTrak."
        )
        if st.button("Pobierz OMM", type="primary", width="stretch"):
            try:
                snapshot = load_public_orbit_snapshot(allow_network=True)
            except CelestrakClientError as error:
                st.error(str(error))
                return
        else:
            return

    source_columns = st.columns([1.3, 1.0, 1.0])
    source_columns[0].caption(
        f"Snapshot: {snapshot.generated_at_utc.isoformat()} · "
        f"{len(snapshot.satellites)} obiektów"
    )
    if source_columns[1].button("Odśwież OMM online", width="stretch"):
        try:
            snapshot = load_public_orbit_snapshot(allow_network=True)
        except CelestrakClientError as error:
            st.error(str(error))
        else:
            st.success("Snapshot OMM został odświeżony.")
            st.rerun()
    if source_columns[2].button("Użyj cache offline", width="stretch"):
        try:
            snapshot = load_public_orbit_snapshot(allow_network=False)
        except CelestrakClientError as error:
            st.error(str(error))
        else:
            st.success("Wczytano lokalny cache OMM.")
            st.rerun()

    observer = _resolve_observer()
    _render_time_controls(snapshot)

    with st.container(border=True):
        st.markdown("### Konfiguracja śledzenia")
        all_slot_ids = tuple(satellite.slot_id for satellite in snapshot.satellites)
        columns = st.columns([1.5, 1.0, 1.0, 1.0])
        selected_slots = tuple(
            columns[0].multiselect(
                "Satelity",
                options=list(all_slot_ids),
                default=list(all_slot_ids),
            )
        )
        minimum_elevation = float(
            columns[1].select_slider(
                "Próg przelotu",
                options=[0, 5, 10, 15, 20, 30],
                value=5,
                format_func=lambda value: f"{value}°",
            )
        )
        forecast_hours = int(
            columns[2].select_slider(
                "Prognoza",
                options=[6, 12, 24, 48],
                value=24,
                format_func=lambda value: f"{value} h",
            )
        )
        footprint_radius = float(
            columns[3].select_slider(
                "Footprint",
                options=[25, 50, 75, 100, 150, 250],
                value=75,
                format_func=lambda value: f"{value} km",
            )
        )

        if not selected_slots:
            st.warning("Wybierz co najmniej jeden satelita.")
            return
        selected_slot = st.selectbox(
            "Satelita wyróżniony",
            options=list(selected_slots),
        )

    _render_live_fragment(
        snapshot=snapshot,
        observer=observer,
        slot_ids=selected_slots,
        selected_slot_id=selected_slot,
        minimum_elevation_deg=minimum_elevation,
        forecast_hours=forecast_hours,
        footprint_radius_km=footprint_radius,
    )


__all__ = ["render_live_tracking_page"]
