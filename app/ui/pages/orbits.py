from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from app.integrations.orbits import (
    CelestrakClientError,
    OrbitPropagationError,
    SatelliteFamily,
)
from app.ui.app_context import get_public_orbit_service
from app.ui.orbit_state import (
    get_public_orbit_snapshot,
    load_public_orbit_snapshot,
)
from app.ui.orbit_view import build_ground_track_figure


def _snapshot_table(snapshot) -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    return pd.DataFrame(
        [
            {
                "Slot": satellite.slot_id,
                "Rodzina": (
                    "ICEYE SAR"
                    if satellite.family == SatelliteFamily.ICEYE
                    else "Pléiades Neo EO"
                ),
                "Obiekt CelesTrak": satellite.record.object_name,
                "NORAD": satellite.record.norad_cat_id,
                "Epoka OMM UTC": satellite.record.epoch_utc.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "Wiek elementów [h]": round(
                    max(
                        0.0,
                        (now - satellite.record.epoch_utc).total_seconds()
                        / 3600.0,
                    ),
                    1,
                ),
                "Inklinacja [°]": round(
                    satellite.record.inclination_deg,
                    4,
                ),
                "Mimośród": satellite.record.eccentricity,
                "Okres [min]": round(
                    satellite.record.orbital_period_minutes,
                    2,
                ),
            }
            for satellite in snapshot.satellites
        ]
    )


def _cache_status(snapshot) -> None:
    st.subheader("Źródła i aktualność danych")
    columns = st.columns(len(snapshot.queries))
    for column, query in zip(columns, snapshot.queries):
        age_hours = query.age_seconds / 3600.0
        source = "cache lokalny" if query.from_cache else "CelesTrak online"
        state = "przeterminowany" if query.is_stale else "aktualny"
        with column.container(border=True):
            st.markdown(f"**{query.query_name}**")
            metric_columns = st.columns(2)
            metric_columns[0].metric("Rekordy", len(query.records))
            metric_columns[1].metric("Wiek cache", f"{age_hours:.1f} h")
            st.caption(f"Źródło: {source} · status: {state}")

    for warning in snapshot.warnings:
        st.warning(warning)


def render_orbits_page() -> None:
    """Renderuje publiczne OMM i propagację SGP4 w czytelnym układzie."""

    st.header("Publiczne orbity i propagacja SGP4")
    st.info(
        "Moduł pobiera publiczne elementy GP/OMM dla 4 satelitów ICEYE "
        "i 2 satelitów Pléiades Neo. Są to dane do modelowania i "
        "orientacyjnego wyznaczania położenia, a nie efemerydy operacyjne."
    )

    with st.container(border=True):
        st.markdown("### Parametry propagacji")
        controls = st.columns([1.2, 1.2, 1.3, 2.0])
        horizon_hours = controls[0].slider(
            "Horyzont śladu [h]",
            min_value=1,
            max_value=12,
            value=3,
        )
        step_seconds = controls[1].select_slider(
            "Krok propagacji [s]",
            options=[30, 60, 90, 120, 180, 300],
            value=60,
        )
        offline = controls[2].toggle(
            "Tylko lokalny cache",
            value=False,
            help="Nie łączy się z CelesTrak. Wymaga wcześniejszego cache.",
        )
        refresh_clicked = controls[3].button(
            "Pobierz lub odśwież OMM",
            type="primary",
            width="stretch",
        )

    snapshot = get_public_orbit_snapshot()
    if snapshot is None or refresh_clicked:
        try:
            with st.spinner("Pobieranie i walidacja danych CelesTrak..."):
                snapshot = load_public_orbit_snapshot(
                    allow_network=not offline
                )
        except CelestrakClientError as error:
            st.error(str(error))
            st.stop()

    sar_count = sum(
        satellite.family == SatelliteFamily.ICEYE
        for satellite in snapshot.satellites
    )
    eo_count = sum(
        satellite.family == SatelliteFamily.PLEIADES_NEO
        for satellite in snapshot.satellites
    )
    summary = st.columns(4)
    summary[0].metric("Satelity łącznie", len(snapshot.satellites))
    summary[1].metric("ICEYE SAR", sar_count)
    summary[2].metric("Pléiades Neo EO", eo_count)
    summary[3].metric(
        "Snapshot UTC",
        snapshot.generated_at_utc.strftime("%H:%M:%S"),
    )

    _cache_status(snapshot)

    if len(snapshot.satellites) != 6:
        st.error(
            "Nie uzyskano pełnego zestawu 4 ICEYE + 2 Pléiades Neo. "
            "Propagacja zostanie wykonana dla dostępnych obiektów."
        )

    start_utc = datetime.now(timezone.utc).replace(microsecond=0)
    try:
        with st.spinner("Propagacja SGP4 i budowanie śladów naziemnych..."):
            tracks = get_public_orbit_service().propagate_snapshot(
                snapshot,
                start_utc=start_utc,
                duration=timedelta(hours=horizon_hours),
                step=timedelta(seconds=step_seconds),
            )
    except (OrbitPropagationError, ValueError) as error:
        st.error(f"Nie udało się wykonać propagacji: {error}")
        st.stop()

    st.subheader("Interaktywna mapa śladów naziemnych")
    all_slot_ids = [track.satellite.slot_id for track in tracks]
    visible_slot_ids = st.multiselect(
        "Widoczne satelity",
        options=all_slot_ids,
        default=all_slot_ids,
        help=(
            "Linie ciągłe i okrągłe markery oznaczają ICEYE SAR. "
            "Linie przerywane i romby oznaczają Pléiades Neo EO."
        ),
    )
    st.caption(
        f"Początek: {start_utc.isoformat()} · horyzont: {horizon_hours} h · "
        f"krok: {step_seconds} s. Najedź na ślad, aby zobaczyć czas UTC, "
        "współrzędne i wysokość."
    )
    figure = build_ground_track_figure(
        tracks,
        visible_slot_ids=set(visible_slot_ids),
    )
    st.plotly_chart(
        figure,
        width="stretch",
        config={
            "displaylogo": False,
            "scrollZoom": True,
            "responsive": True,
        },
    )

    with st.expander("Szczegółowe parametry obiektów orbitalnych"):
        st.dataframe(
            _snapshot_table(snapshot),
            width="stretch",
            hide_index=True,
            height=310,
        )

    first_states = pd.DataFrame(
        [
            {
                "Slot": track.satellite.slot_id,
                "Satelita": track.satellite.record.object_name,
                "Czas UTC": track.states[0].timestamp_utc.isoformat(),
                "Szerokość [°]": round(track.states[0].latitude_deg, 5),
                "Długość [°]": round(track.states[0].longitude_deg, 5),
                "Wysokość [km]": round(track.states[0].altitude_km, 2),
            }
            for track in tracks
            if track.states
        ]
    )
    st.subheader("Pozycje na początku propagacji")
    st.dataframe(first_states, width="stretch", hide_index=True)

    export_payload = {
        "snapshot": snapshot.to_dict(),
        "propagation": {
            "start_utc": start_utc.isoformat(),
            "horizon_hours": horizon_hours,
            "step_seconds": step_seconds,
            "tracks": [track.to_dict() for track in tracks],
        },
    }
    st.download_button(
        "Pobierz OMM i propagację JSON",
        data=json.dumps(export_payload, ensure_ascii=False, indent=2),
        file_name="public_orbits_sgp4.json",
        mime="application/json",
        width="stretch",
    )
