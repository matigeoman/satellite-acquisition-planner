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
from app.ui.orbit_view import build_ground_track_figure


_SNAPSHOT_STATE_KEY = "public_orbit_snapshot"


def _load_snapshot(*, allow_network: bool = True):
    service = get_public_orbit_service()
    snapshot = service.load_default_constellation(allow_network=allow_network)
    st.session_state[_SNAPSHOT_STATE_KEY] = snapshot
    return snapshot


def _snapshot_table(snapshot) -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    return pd.DataFrame(
        [
            {
                "Slot planera": satellite.slot_id,
                "Rodzina": (
                    "ICEYE SAR"
                    if satellite.family == SatelliteFamily.ICEYE
                    else "Pléiades Neo EO"
                ),
                "Nazwa publiczna": satellite.record.object_name,
                "NORAD": satellite.record.norad_cat_id,
                "Epoka OMM UTC": satellite.record.epoch_utc.isoformat(),
                "Wiek elementów [h]": round(
                    max(
                        0.0,
                        (now - satellite.record.epoch_utc).total_seconds()
                        / 3600.0,
                    ),
                    1,
                ),
                "Inklinacja [°]": satellite.record.inclination_deg,
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
    st.subheader("Status źródeł orbitalnych")
    columns = st.columns(len(snapshot.queries))
    for column, query in zip(columns, snapshot.queries):
        age_hours = query.age_seconds / 3600.0
        source = "cache" if query.from_cache else "CelesTrak"
        state = "przeterminowany" if query.is_stale else "aktualny"
        column.metric(
            query.query_name,
            f"{len(query.records)} rekordów",
            f"{source}, {state}, {age_hours:.1f} h",
        )

    for warning in snapshot.warnings:
        st.warning(warning)

    st.caption(
        "Aplikacja pobiera jawne dane GP w formacie OMM JSON. Cache ma "
        "ważność 2 godzin, dzięki czemu kolejne odświeżenia interfejsu nie "
        "wysyłają powtarzających się zapytań do CelesTrak."
    )


def render_orbits_page() -> None:
    """Renderuje pobieranie OMM i pierwszą propagację SGP4."""

    st.header("Publiczne orbity i propagacja SGP4")
    st.info(
        "Moduł pobiera publiczne elementy GP/OMM dla 4 satelitów ICEYE "
        "i 2 satelitów Pléiades Neo. Są to orientacyjne dane orbitalne, "
        "a nie efemerydy operacyjne operatorów."
    )

    controls = st.columns([1.2, 1.2, 1.2, 2.4])
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

    snapshot = st.session_state.get(_SNAPSHOT_STATE_KEY)
    if snapshot is None or refresh_clicked:
        try:
            with st.spinner("Pobieranie i walidacja danych CelesTrak..."):
                snapshot = _load_snapshot(allow_network=not offline)
        except CelestrakClientError as error:
            st.error(str(error))
            st.stop()

    _cache_status(snapshot)
    st.subheader("Satelity przypisane do planera")
    st.dataframe(
        _snapshot_table(snapshot),
        use_container_width=True,
        hide_index=True,
        height=330,
    )

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

    st.subheader("Ślady naziemne")
    st.caption(
        f"Początek: {start_utc.isoformat()} · horyzont: {horizon_hours} h · "
        f"krok: {step_seconds} s. Konwersja TEME→WGS84 wykorzystuje "
        "uproszczony obrót GMST; dokładność zostanie później porównana ze STK."
    )
    figure = build_ground_track_figure(tracks)
    st.plotly_chart(figure, use_container_width=True)

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
    st.dataframe(
        first_states,
        use_container_width=True,
        hide_index=True,
    )

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
