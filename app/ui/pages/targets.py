from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

import pandas as pd
import streamlit as st

from app.catalogs import PUBLIC_MISSION_PROFILES
from app.custom_requests import (
    build_custom_request,
    serialize_custom_requests,
)
from app.models.enums import RequestMode, SensorType
from app.models.geometry import TargetGeometry
from app.models.request import ObservationRequest
from app.ui.components import render_aoi_editor


_REQUEST_STRATEGIES: tuple[str, ...] = (
    "SAR_ONLY",
    "EO_ONLY",
    "DUAL_REQUIRED",
    "DUAL_OPTIONAL",
)

_REQUEST_STRATEGY_LABELS: dict[str, str] = {
    "SAR_ONLY": "Tylko SAR",
    "EO_ONLY": "Tylko EO (optyczne)",
    "DUAL_REQUIRED": "SAR + EO — oba wymagane",
    "DUAL_OPTIONAL": "SAR + EO — drugi sensor opcjonalny",
}

_REQUEST_STRATEGY_HELP: dict[str, str] = {
    "SAR_ONLY": (
        "Jedna akwizycja radarowa wystarcza do realizacji zlecenia. "
        "Zachmurzenie nie ogranicza wykonania."
    ),
    "EO_ONLY": (
        "Jedna akwizycja optyczna wystarcza do realizacji zlecenia. "
        "Okazje są filtrowane według zachmurzenia i oświetlenia."
    ),
    "DUAL_REQUIRED": (
        "Zlecenie jest ukończone dopiero po zaplanowaniu jednej "
        "akwizycji SAR oraz jednej akwizycji EO."
    ),
    "DUAL_OPTIONAL": (
        "Jedna akwizycja wystarcza, ale wykonanie SAR i EO daje "
        "dodatkową wartość w funkcji celu."
    ),
}


def _profiles_section() -> None:
    st.subheader("Publiczne profile sensorów")
    tabs = st.tabs([profile.name for profile in PUBLIC_MISSION_PROFILES.values()])

    for tab, profile in zip(tabs, PUBLIC_MISSION_PROFILES.values()):
        with tab:
            st.write(profile.description)
            metric_columns = st.columns(4)
            metric_columns[0].metric("Operator", profile.operator)
            metric_columns[1].metric("Satelity w modelu", profile.satellite_slots)
            metric_columns[2].metric("Typ sensora", profile.sensor.sensor_type.value)
            metric_columns[3].metric("Tryby", len(profile.sensor.imaging_modes))

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


def resolve_request_strategy(
    strategy: str,
) -> tuple[RequestMode, list[SensorType]]:
    """Zamienia czytelny wariant formularza na konfigurację modelu."""

    if strategy == "SAR_ONLY":
        return RequestMode.SINGLE, [SensorType.SAR]
    if strategy == "EO_ONLY":
        return RequestMode.SINGLE, [SensorType.OPTICAL]
    if strategy == "DUAL_REQUIRED":
        return RequestMode.DUAL_REQUIRED, [SensorType.SAR, SensorType.OPTICAL]
    if strategy == "DUAL_OPTIONAL":
        return RequestMode.DUAL_OPTIONAL, [SensorType.SAR, SensorType.OPTICAL]
    raise ValueError(f"Nieznany wariant obserwacji: {strategy}")


def _request_form(geometry: TargetGeometry | None) -> ObservationRequest | None:
    st.subheader("Nowe zlecenie obserwacyjne")
    existing: list[ObservationRequest] = st.session_state.setdefault(
        "custom_observation_requests", []
    )

    strategy = st.radio(
        "Rodzaj obserwacji",
        options=_REQUEST_STRATEGIES,
        format_func=lambda value: _REQUEST_STRATEGY_LABELS[value],
        horizontal=True,
        key="custom_request_strategy",
    )
    request_mode, sensors = resolve_request_strategy(strategy)
    needs_optical = SensorType.OPTICAL in sensors
    needs_sar = SensorType.SAR in sensors
    st.caption(_REQUEST_STRATEGY_HELP[strategy])

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

        mode_summary = {
            RequestMode.SINGLE: "SINGLE",
            RequestMode.DUAL_REQUIRED: "DUAL_REQUIRED",
            RequestMode.DUAL_OPTIONAL: "DUAL_OPTIONAL",
        }[request_mode]
        st.info(
            f"Konfiguracja modelu: **{mode_summary}** · sensory: "
            + " + ".join(sensor.value for sensor in sensors)
        )

        earliest_date = first.date_input("Początek — data UTC", value=now.date())
        earliest_time = second.time_input("Początek — czas UTC", value=now.time())
        latest_date = first.date_input("Koniec — data UTC", value=default_end.date())
        latest_time = second.time_input("Koniec — czas UTC", value=default_end.time())

        sar_resolution_m: float | None = None
        optical_resolution_m: float | None = None
        if needs_sar:
            sar_resolution_m = first.number_input(
                "Maksymalna rozdzielczość SAR [m]",
                min_value=0.1,
                max_value=100.0,
                value=1.0,
                step=0.1,
            )
        if needs_optical:
            optical_resolution_m = second.number_input(
                "Maksymalna GSD EO [m]",
                min_value=0.1,
                max_value=100.0,
                value=0.5,
                step=0.1,
            )

        minimum_coverage_percent = second.slider(
            "Minimalne pokrycie", 1, 100, 90, format="%d%%"
        )
        max_cloud_percent = first.slider(
            "Maksymalne zachmurzenie EO",
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

    resolution_values = [
        value for value in (sar_resolution_m, optical_resolution_m) if value is not None
    ]
    if not resolution_values:
        st.error("Nie udało się ustalić limitu rozdzielczości.")
        return None

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
            max_resolution_m=max(resolution_values),
            max_sar_resolution_m=sar_resolution_m,
            max_optical_resolution_m=optical_resolution_m,
            minimum_coverage_ratio=minimum_coverage_percent / 100.0,
            max_cloud_cover=(max_cloud_percent / 100.0 if needs_optical else None),
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
                "Sensory": " + ".join(
                    sensor.value for sensor in request.requested_sensor_types
                ),
                "SAR [m]": (
                    request.resolution_limit_for(SensorType.SAR)
                    if request.requires_sar
                    else "—"
                ),
                "EO [m]": (
                    request.resolution_limit_for(SensorType.OPTICAL)
                    if request.requires_optical
                    else "—"
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
        "Zaznacz AOI, a następnie wybierz obserwację SAR, EO albo zlecenie "
        "łączone SAR + EO. Każdy sensor może mieć osobny limit rozdzielczości."
    )

    _profiles_section()
    st.divider()
    geometry = render_aoi_editor(key="target_definition")
    st.divider()
    _request_form(geometry)
    _requests_section()
