from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
    PassQuality,
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


def _pass_quality_label(value: PassQuality) -> str:
    return {
        PassQuality.EXCELLENT: "bardzo dobry",
        PassQuality.GOOD: "dobry",
        PassQuality.MARGINAL: "graniczny",
        PassQuality.POOR: "słaby",
    }[value]


def _source_dataframe(snapshot: PublicConstellationSnapshot) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Zapytanie": query.query_name,
                "Pobrano UTC": query.fetched_at_utc,
                "Wiek danych [h]": round(query.age_seconds / 3600.0, 2),
                "Źródło": "pamięć lokalna" if query.from_cache else "CelesTrak online",
                "Przeterminowane": query.is_stale,
                "Rekordy": len(query.records),
                "Ostrzeżenie": query.warning,
            }
            for query in snapshot.queries
        ]
    )


def _planner_overlap(pass_prediction: PassPrediction) -> tuple[int, int, str]:
    access_count = 0
    acquisition_count = 0
    request_ids: set[str] = set()
    access_result = st.session_state.get(ACCESS_RESULT_STATE_KEY)
    if access_result is not None:
        for window in access_result.windows:
            if window.satellite_id != pass_prediction.slot_id:
                continue
            if (
                window.end_utc < pass_prediction.aos_utc
                or window.start_utc > pass_prediction.los_utc
            ):
                continue
            access_count += 1
            request_ids.add(window.request_id)

    planning = st.session_state.get(PLANNING_RESULT_STATE_KEY)
    if isinstance(planning, PlanningResult):
        for entry in planning.schedule.active_entries:
            if entry.satellite_id != pass_prediction.slot_id:
                continue
            if (
                entry.end_utc < pass_prediction.aos_utc
                or entry.start_utc > pass_prediction.los_utc
            ):
                continue
            acquisition_count += 1
            request_ids.add(entry.request_id)
    return access_count, acquisition_count, ", ".join(sorted(request_ids))


def _pass_dataframe(passes: tuple[PassPrediction, ...]) -> pd.DataFrame:
    rows = [
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
            ">10° [min]": round(item.time_above_10_deg_minutes, 1),
            "Widoczny optycznie [min]": round(
                item.optically_visible_duration_minutes, 1
            ),
            "Jakość": _pass_quality_label(item.quality),
            "Wynik [0–100]": item.quality_score,
            "Widoczność": _visibility_label(item.optical_visibility_at_maximum),
        }
        for item in passes
    ]
    for item, row in zip(passes, rows):
        access_count, acquisition_count, request_ids = _planner_overlap(item)
        row["Okna dostępu"] = access_count
        row["Akwizycje"] = acquisition_count
        row["Powiązane zlecenia"] = request_ids or None
    return pd.DataFrame(rows)


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
    show_ground_tracks: bool,
    show_footprint: bool,
    show_terminator: bool,
    earth_projection: str,
    pass_quality_filter: tuple[str, ...],
    optical_only: bool,
    planner_only: bool,
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
    primary_metrics = st.columns(4)
    primary_metrics[0].metric("Czas UTC", focus_utc.strftime("%H:%M:%S"))
    primary_metrics[1].metric(
        "Nad horyzontem",
        sum(item.topocentric.is_above_horizon for item in states),
    )
    primary_metrics[2].metric("Satelita", current.slot_id)
    primary_metrics[3].metric(
        "Elewacja",
        f"{current.topocentric.elevation_deg:.1f}°",
    )

    selected_record = next(
        satellite.record
        for satellite in snapshot.satellites
        if satellite.slot_id == current.slot_id
    )
    geometry_metrics = st.columns(4)
    geometry_metrics[0].metric(
        "Azymut",
        f"{current.topocentric.azimuth_deg:.1f}°",
    )
    geometry_metrics[1].metric(
        "Odległość",
        f"{current.topocentric.range_km:.0f} km",
    )
    geometry_metrics[2].metric(
        "Wiek OMM",
        f"{current.orbit_data_age_hours:.1f} h",
    )
    geometry_metrics[3].metric(
        "Okres orbity",
        f"{selected_record.orbital_period_minutes:.1f} min",
    )

    st.caption(
        f"{focus_utc.isoformat()} · {current.object_name} · "
        f"{_visibility_label(current.visibility.optical_visibility)} · "
        f"dane orbitalne: {_quality_label(current.orbit_data_quality)}. "
        "Pozycja jest propagowana z OMM/SGP4; nie jest telemetrią pokładową."
    )

    chart_config = {
        "displaylogo": False,
        "responsive": True,
        "scrollZoom": True,
        "modeBarButtonsToRemove": ["select2d", "lasso2d"],
        "toImageButtonOptions": {"format": "png", "scale": 2},
    }
    sky_tab, earth_tab, passes_tab, context_tab = st.tabs(
        ["Mapa nieba", "Mapa Ziemi", "Najbliższe przeloty", "Kontekst planera"]
    )
    with sky_tab:
        st.plotly_chart(
            build_sky_map_figure(
                states=states,
                tracks=sky_tracks,
                minimum_elevation_deg=0.0,
                selected_slot_id=selected_slot_id,
            ),
            width="stretch",
            config=chart_config,
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
                    "Widoczność": _visibility_label(item.visibility.optical_visibility),
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
                show_ground_tracks=show_ground_tracks,
                show_footprint=show_footprint,
                show_terminator=show_terminator,
                projection_type=earth_projection,
            ),
            width="stretch",
            config=chart_config,
        )
        st.caption(
            "Zielony okrąg jest referencyjnym footprintem prezentacyjnym. "
            "Nie zastępuje geometrii konkretnego trybu obrazowania. "
            "Linia kropkowana pokazuje terminator dnia i nocy."
        )

    with passes_tab:
        filtered_passes = tuple(
            item
            for item in passes
            if (not pass_quality_filter or item.quality.value in pass_quality_filter)
            and (not optical_only or item.optically_visible_duration_s > 0.0)
            and (not planner_only or any(_planner_overlap(item)[:2]))
        )
        if not filtered_passes:
            st.info("Brak przelotów spełniających wybrany próg elewacji.")
        else:
            st.dataframe(
                _pass_dataframe(filtered_passes),
                width="stretch",
                hide_index=True,
                height=520,
            )
            st.download_button(
                "Pobierz predykcję przelotów JSON",
                data=pd.Series([item.to_dict() for item in filtered_passes]).to_json(
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

    st.header("Śledzenie i przeloty")
    st.caption(
        "Bieżąca propagacja OMM/SGP4, lokalna mapa nieba i predykcja "
        "przelotów AOS/MAX/LOS. Tryb działa online oraz na danych offline "
        "scenariusza demonstracyjnego."
    )

    snapshot = get_public_orbit_snapshot()
    if snapshot is None:
        st.warning(
            "Brak danych OMM w sesji. Wczytaj POLAND_DEMO albo pobierz "
            "aktualny zestaw z CelesTrak."
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
        f"Zestaw OMM: {snapshot.generated_at_utc.isoformat()} · "
        f"{len(snapshot.satellites)} obiektów"
    )
    if source_columns[1].button("Odśwież OMM online", width="stretch"):
        try:
            snapshot = load_public_orbit_snapshot(
                allow_network=True,
                force_refresh=True,
            )
            _cached_pass_predictions.clear()
        except CelestrakClientError as error:
            st.error(str(error))
        else:
            st.success("Dane OMM zostały odświeżone.")
            st.rerun()
    if source_columns[2].button("Użyj danych offline", width="stretch"):
        try:
            snapshot = load_public_orbit_snapshot(allow_network=False)
        except CelestrakClientError as error:
            st.error(str(error))
        else:
            st.success("Wczytano lokalną pamięć podręczną OMM.")
            st.rerun()

    with st.expander("Źródło i jakość danych orbitalnych", expanded=False):
        if snapshot.queries:
            st.dataframe(
                _source_dataframe(snapshot),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info(
                "Zestaw demonstracyjny nie zawiera historii zapytań "
                "sieciowych. Epoki OMM są nadal prezentowane dla każdego obiektu."
            )
        oldest_age = max(
            abs(
                (
                    datetime.now(timezone.utc) - satellite.record.epoch_utc
                ).total_seconds()
            )
            / 3600.0
            for satellite in snapshot.satellites
        )
        if oldest_age > 168.0:
            st.warning(
                f"Najstarsza epoka OMM ma {oldest_age / 24.0:.1f} dnia. "
                "Predykcja długoterminowa może mieć istotny błąd położenia."
            )
        elif oldest_age > 72.0:
            st.warning(
                f"Najstarsza epoka OMM ma {oldest_age:.1f} h. "
                "Przed użyciem operacyjnym odśwież dane."
            )

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
                "Promień pokrycia",
                options=[25, 50, 75, 100, 150, 250],
                value=75,
                format_func=lambda value: f"{value} km",
            )
        )

        if not selected_slots:
            st.warning("Wybierz co najmniej jednego satelitę.")
            return
        selected_slot = st.selectbox(
            "Satelita wyróżniony",
            options=list(selected_slots),
        )
        map_columns = st.columns([1.0, 1.0, 1.0, 1.2])
        show_ground_tracks = map_columns[0].toggle("Ślad naziemny", value=True)
        show_footprint = map_columns[1].toggle("Obszar pokrycia", value=True)
        show_terminator = map_columns[2].toggle("Granica dnia i nocy", value=True)
        earth_projection_label = map_columns[3].selectbox(
            "Widok Ziemi",
            options=["Mapa globalna", "Globus śledzący"],
        )
        earth_projection = (
            "orthographic"
            if earth_projection_label == "Globus śledzący"
            else "natural earth"
        )

        filter_columns = st.columns([1.5, 1.0, 1.0])
        pass_quality_filter = tuple(
            filter_columns[0].multiselect(
                "Jakość przelotu",
                options=[quality.value for quality in PassQuality],
                default=[quality.value for quality in PassQuality],
                format_func=lambda value: _pass_quality_label(PassQuality(value)),
            )
        )
        optical_only = filter_columns[1].toggle(
            "Tylko widoczne optycznie",
            value=False,
        )
        planner_only = filter_columns[2].toggle(
            "Tylko powiązane z harmonogramem",
            value=False,
        )

    _render_live_fragment(
        snapshot=snapshot,
        observer=observer,
        slot_ids=selected_slots,
        selected_slot_id=selected_slot,
        minimum_elevation_deg=minimum_elevation,
        forecast_hours=forecast_hours,
        footprint_radius_km=footprint_radius,
        show_ground_tracks=show_ground_tracks,
        show_footprint=show_footprint,
        show_terminator=show_terminator,
        earth_projection=earth_projection,
        pass_quality_filter=pass_quality_filter,
        optical_only=optical_only,
        planner_only=planner_only,
    )


__all__ = ["render_live_tracking_page"]
