from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

import pandas as pd
import streamlit as st

from app.catalogs import PUBLIC_MISSION_PROFILES
from app.models.enums import RequestMode, SensorType
from app.models.request import ObservationRequest
from app.custom_requests import (
    build_custom_request,
    serialize_custom_requests,
)
from app.ui.components import render_aoi_editor


def _profiles_section() -> None:
    st.subheader("Publiczne profile sensorów")
    tabs = st.tabs([profile.name for profile in PUBLIC_MISSION_PROFILES.values()])

    for tab, profile in zip(tabs, PUBLIC_MISSION_PROFILES.values()):
        with tab:
            st.write(profile.description)
            metric_columns = st.columns(4)
            metric_columns[0].metric("Operator", profile.operator)
            metric_columns[1].metric("Satelity w modelu", profile.satellite_slots)
            metric_columns[2].metric(
                "Typ sensora", profile.sensor.sensor_type.value
            )
            metric_columns[3].metric(
                "Tryby", len(profile.sensor.imaging_modes)
            )

            st.dataframe(
                pd.DataFrame(profile.mode_rows()),
                use_container_width=True,
                hide_index=True,
            )

            with st.expander("Źródła i status parametrów"):
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Grupa": source.parameter_group,
                                "Pochodzenie": source.origin.value,
                                "Źródło": source.reference,
                                "Uwagi": source.notes or "",
                            }
                            for source in profile.parameter_sources
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )


def _requested_sensor_types(
    request_mode: RequestMode,
    single_sensor: SensorType,
) -> list[SensorType]:
    if request_mode == RequestMode.SINGLE:
        return [single_sensor]
    return [SensorType.SAR, SensorType.OPTICAL]


def _request_form(geometry) -> ObservationRequest | None:
    st.subheader("Nowe zlecenie obserwacyjne")
    existing: list[ObservationRequest] = st.session_state.setdefault(
        "custom_observation_requests", []
    )

    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    default_end = now + timedelta(hours=24)

    with st.form("custom_request_form", border=True):
        first, second = st.columns(2)
        request_id = first.text_input(
            "Identyfikator",
            value=f"REQ-CUSTOM-{len(existing) + 1:03d}",
        )
        name = second.text_input("Nazwa", value="Nowy obszar zainteresowania")

        priority = first.slider("Priorytet", 1, 10, 7)
        is_mandatory = second.checkbox("Zlecenie obowiązkowe", value=False)

        request_mode = first.selectbox(
            "Tryb zlecenia",
            options=list(RequestMode),
            format_func=lambda value: value.value,
        )
        single_sensor = second.selectbox(
            "Sensor dla SINGLE",
            options=list(SensorType),
            format_func=lambda value: value.value,
            disabled=request_mode != RequestMode.SINGLE,
        )

        earliest_date = first.date_input("Początek — data UTC", value=now.date())
        earliest_time = second.time_input(
            "Początek — czas UTC", value=now.time()
        )
        latest_date = first.date_input(
            "Koniec — data UTC", value=default_end.date()
        )
        latest_time = second.time_input(
            "Koniec — czas UTC", value=default_end.time()
        )

        max_resolution_m = first.number_input(
            "Maksymalna rozdzielczość [m]",
            min_value=0.1,
            max_value=100.0,
            value=1.0,
            step=0.1,
        )
        minimum_coverage_percent = second.slider(
            "Minimalne pokrycie", 1, 100, 90, format="%d%%"
        )

        sensors = _requested_sensor_types(request_mode, single_sensor)
        needs_optical = SensorType.OPTICAL in sensors
        needs_sar = SensorType.SAR in sensors

        max_cloud_percent = first.slider(
            "Maksymalne zachmurzenie",
            0,
            100,
            20,
            format="%d%%",
            disabled=not needs_optical,
        )
        max_incidence = second.number_input(
            "Maksymalny kąt padania SAR [°]",
            min_value=0.0,
            max_value=89.0,
            value=40.0,
            step=1.0,
            disabled=not needs_sar,
        )
        max_off_nadir = first.number_input(
            "Maksymalny off-nadir [°]",
            min_value=0.0,
            max_value=89.0,
            value=45.0,
            step=1.0,
        )
        notes = st.text_area("Uwagi", value="")

        submitted = st.form_submit_button(
            "Dodaj zlecenie",
            type="primary",
            disabled=geometry is None,
        )

    if not submitted:
        return None

    earliest = datetime.combine(
        earliest_date,
        earliest_time if isinstance(earliest_time, time) else time(0, 0),
        tzinfo=timezone.utc,
    )
    latest = datetime.combine(
        latest_date,
        latest_time if isinstance(latest_time, time) else time(0, 0),
        tzinfo=timezone.utc,
    )

    try:
        request = build_custom_request(
            request_id=request_id.strip().upper(),
            name=name,
            geometry=geometry,
            priority=priority,
            earliest_start_utc=earliest,
            latest_end_utc=latest,
            request_mode=request_mode,
            requested_sensor_types=sensors,
            max_resolution_m=max_resolution_m,
            minimum_coverage_ratio=minimum_coverage_percent / 100.0,
            max_cloud_cover=(
                max_cloud_percent / 100.0 if needs_optical else None
            ),
            max_incidence_angle_deg=max_incidence if needs_sar else None,
            max_off_nadir_deg=max_off_nadir,
            is_mandatory=is_mandatory,
            notes=notes or None,
        )
    except Exception as error:
        st.error(f"Nie udało się utworzyć zlecenia: {error}")
        return None

    existing.append(request)
    st.session_state["custom_observation_requests"] = existing
    st.success(f"Dodano {request.request_id}")
    return request


def _requests_section() -> None:
    requests: list[ObservationRequest] = st.session_state.get(
        "custom_observation_requests", []
    )
    if not requests:
        return

    st.subheader("Zlecenia utworzone w sesji")
    dataframe = pd.DataFrame(
        [
            {
                "ID": request.request_id,
                "Nazwa": request.name,
                "Geometria": request.geometry.type,
                "Tryb": request.request_mode.value,
                "Sensory": ", ".join(
                    sensor.value for sensor in request.requested_sensor_types
                ),
                "Priorytet": request.priority,
                "Początek UTC": request.earliest_start_utc.isoformat(),
                "Koniec UTC": request.latest_end_utc.isoformat(),
            }
            for request in requests
        ]
    )
    st.dataframe(dataframe, use_container_width=True, hide_index=True)

    action_columns = st.columns([1, 1, 3])
    action_columns[0].download_button(
        "Pobierz JSON",
        data=serialize_custom_requests(requests),
        file_name="custom_requests.json",
        mime="application/json",
    )
    if action_columns[1].button("Wyczyść zlecenia"):
        st.session_state["custom_observation_requests"] = []
        st.rerun()


def render_targets_page() -> None:
    """Renderuje katalog publiczny i dwukierunkowy edytor AOI."""

    st.header("Cele, profile sensorów i zlecenia")
    st.info(
        "Ten moduł definiuje cele i parametry wejściowe. Rzeczywiste "
        "okna dostępności zostaną wyznaczone w kolejnym etapie przez "
        "TLE/OMM + SGP4."
    )

    _profiles_section()
    st.divider()
    geometry = render_aoi_editor(key="target_definition")
    st.divider()
    _request_form(geometry)
    _requests_section()
