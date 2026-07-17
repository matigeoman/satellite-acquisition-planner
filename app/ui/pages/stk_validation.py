from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from app.catalogs import ICEYE_PUBLIC_PROFILE, PLEIADES_NEO_PUBLIC_PROFILE
from app.integrations.access.models import GeometricAccessWindow
from app.models.request import ObservationRequest
from app.ui.app_context import get_stk_validation_service
from app.ui.orbit_state import get_public_orbit_snapshot
from app.ui.stk_validation_view import (
    access_matches_dataframe,
    aer_matches_dataframe,
    build_access_comparison_figure,
    build_aer_error_figure,
)


_ACCESS_RESULT_STATE_KEY = "public_access_result"
_ACCESS_VALIDATION_STATE_KEY = "stk_access_validation_result"
_AER_VALIDATION_STATE_KEY = "stk_aer_validation_result"


def _mode_lookup():
    modes = (
        *ICEYE_PUBLIC_PROFILE.sensor.imaging_modes,
        *PLEIADES_NEO_PUBLIC_PROFILE.sensor.imaging_modes,
    )
    return {mode.mode_id: mode for mode in modes}


def _request_for_result(result) -> ObservationRequest | None:
    requests: list[ObservationRequest] = st.session_state.get(
        "custom_observation_requests", []
    )
    return next(
        (request for request in requests if request.request_id == result.request_id),
        None,
    )


def _selection_label(value: tuple[str, str], windows) -> str:
    satellite_id, mode_id = value
    first = next(
        window
        for window in windows
        if window.satellite_id == satellite_id and window.mode_id == mode_id
    )
    count = sum(
        window.satellite_id == satellite_id and window.mode_id == mode_id
        for window in windows
    )
    return (
        f"{satellite_id} · {first.satellite_name} · {first.mode_name} "
        f"({count} okien)"
    )


def _render_export_section(
    *,
    request: ObservationRequest,
    result,
    selected_windows: tuple[GeometricAccessWindow, ...],
    satellite,
    mode,
) -> None:
    st.subheader("1. Eksport przypadku walidacyjnego do STK")
    st.write(
        "Paczka zawiera OMM, AOI, parametry trybu, przedział scenariusza, "
        "okna modelu oraz krótką instrukcję konfiguracji raportów Access i AER."
    )
    bundle = get_stk_validation_service().build_bundle(
        request=request,
        satellite=satellite,
        mode=mode,
        windows=selected_windows,
        propagation_step_s=result.propagation_step_s,
    )
    st.download_button(
        "Pobierz paczkę walidacyjną STK",
        data=bundle,
        file_name=(
            f"stk-validation-{request.request_id.lower()}-"
            f"{satellite.slot_id.lower()}-{mode.mode_id.lower()}.zip"
        ),
        mime="application/zip",
        type="primary",
        width="stretch",
    )
    with st.expander("Co ustawić w STK"):
        st.markdown(
            f"""
- **Scenario:** `{request.earliest_start_utc.isoformat()}` – `{request.latest_end_utc.isoformat()}`
- **Satellite:** `{satellite.record.object_name}`, NORAD `{satellite.record.norad_cat_id}`
- **Propagator:** SGP4, elementy z `satellite_omm.json`
- **Cel:** `target.geojson` lub `target_vertices.csv`
- **Tryb:** `{mode.name}` (`{mode.mode_id}`)
- **Access CSV:** Start Time (UTCG), Stop Time (UTCG), Duration (sec)
- **AER CSV opcjonalnie:** Time (UTCG), Azimuth (deg), Elevation (deg), Range (km)
"""
        )


def _render_access_validation(
    *,
    selected_windows: tuple[GeometricAccessWindow, ...],
) -> None:
    st.subheader("2. Porównanie raportu Access")
    access_file = st.file_uploader(
        "Raport Access z STK (.csv lub .txt)",
        type=["csv", "txt"],
        key="stk_access_report_upload",
    )
    default_tolerance = max(120, int(st.session_state[_ACCESS_RESULT_STATE_KEY].propagation_step_s * 3))
    tolerance_s = st.slider(
        "Maksymalna różnica używana do dopasowania okien [s]",
        min_value=0,
        max_value=1800,
        value=default_tolerance,
        step=10,
    )
    if access_file is None:
        st.caption(
            "Parser rozpoznaje przecinek, średnik i tabulator oraz czasy UTCG "
            "w typowym formacie STK."
        )
        return

    try:
        report = get_stk_validation_service().parse_access(access_file.getvalue())
        validation = get_stk_validation_service().validate_access(
            model_windows=selected_windows,
            report=report,
            tolerance_s=float(tolerance_s),
        )
    except ValueError as error:
        st.error(f"Nie udało się odczytać raportu Access: {error}")
        return

    st.session_state[_ACCESS_VALIDATION_STATE_KEY] = validation
    for warning in report.warnings:
        st.warning(warning)
    st.caption(
        "Rozpoznane kolumny: "
        + ", ".join(f"{key} = {value}" for key, value in report.detected_columns.items())
    )

    metrics = st.columns(6)
    metrics[0].metric("Okna modelu", validation.model_window_count)
    metrics[1].metric("Okna STK", validation.stk_interval_count)
    metrics[2].metric("Dopasowane", len(validation.matched))
    metrics[3].metric("Skuteczność", f"{validation.match_rate:.0%}")
    metrics[4].metric(
        "MAE granicy startu",
        f"{validation.start_error_statistics_s.mean_absolute_error:.1f} s",
    )
    metrics[5].metric(
        "MAE długości",
        f"{validation.duration_error_statistics_s.mean_absolute_error:.1f} s",
    )

    st.plotly_chart(
        build_access_comparison_figure(selected_windows, report.intervals),
        use_container_width=True,
        config={"displaylogo": False, "responsive": True},
    )
    table = access_matches_dataframe(validation)
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        height=420,
        column_config={
            "Współczynnik nakładania": st.column_config.ProgressColumn(
                "Współczynnik nakładania",
                min_value=0.0,
                max_value=1.0,
                format="percent",
            )
        },
    )

    with st.expander("Niedopasowane okna"):
        st.write(
            "Model:",
            list(validation.unmatched_model_window_ids) or "brak",
        )
        st.write(
            "STK:",
            list(validation.unmatched_stk_interval_ids) or "brak",
        )

    downloads = st.columns(2)
    downloads[0].download_button(
        "Pobierz raport walidacji JSON",
        data=json.dumps(validation.to_dict(), ensure_ascii=False, indent=2),
        file_name="stk_access_validation.json",
        mime="application/json",
        width="stretch",
    )
    downloads[1].download_button(
        "Pobierz dopasowania CSV",
        data=table.to_csv(index=False).encode("utf-8-sig"),
        file_name="stk_access_matches.csv",
        mime="text/csv",
        width="stretch",
    )


def _render_aer_validation(
    *,
    selected_windows: tuple[GeometricAccessWindow, ...],
    request: ObservationRequest,
) -> None:
    st.subheader("3. Opcjonalne porównanie AER")
    st.caption(
        "Porównanie AER sprawdza azymut, elewację i zasięg do centroidu AOI. "
        "Dla dużego Polygon jest to walidacja geometrii centroidu, nie całego footprintu."
    )
    aer_file = st.file_uploader(
        "Raport AER z STK (.csv lub .txt)",
        type=["csv", "txt"],
        key="stk_aer_report_upload",
    )
    tolerance_s = st.slider(
        "Tolerancja dopasowania próbek AER [s]",
        min_value=0,
        max_value=300,
        value=max(30, int(st.session_state[_ACCESS_RESULT_STATE_KEY].propagation_step_s)),
        step=5,
    )
    if aer_file is None:
        return

    try:
        report = get_stk_validation_service().parse_aer(aer_file.getvalue())
        validation = get_stk_validation_service().validate_aer(
            model_windows=selected_windows,
            report=report,
            geometry=request.geometry,
            time_tolerance_s=float(tolerance_s),
        )
    except ValueError as error:
        st.error(f"Nie udało się odczytać raportu AER: {error}")
        return

    st.session_state[_AER_VALIDATION_STATE_KEY] = validation
    for warning in report.warnings:
        st.warning(warning)

    metrics = st.columns(5)
    metrics[0].metric("Próbki dopasowane", len(validation.matched))
    metrics[1].metric("Skuteczność", f"{validation.match_rate:.0%}")
    metrics[2].metric(
        "MAE azymutu",
        f"{validation.azimuth_error_statistics_deg.mean_absolute_error:.3f}°",
    )
    metrics[3].metric(
        "MAE elewacji",
        f"{validation.elevation_error_statistics_deg.mean_absolute_error:.3f}°",
    )
    metrics[4].metric(
        "MAE zasięgu",
        f"{validation.range_error_statistics_km.mean_absolute_error:.3f} km",
    )

    st.plotly_chart(
        build_aer_error_figure(validation),
        use_container_width=True,
        config={"displaylogo": False, "responsive": True},
    )
    table = aer_matches_dataframe(validation)
    st.dataframe(table, use_container_width=True, hide_index=True, height=430)
    downloads = st.columns(2)
    downloads[0].download_button(
        "Pobierz AER JSON",
        data=json.dumps(validation.to_dict(), ensure_ascii=False, indent=2),
        file_name="stk_aer_validation.json",
        mime="application/json",
        width="stretch",
    )
    downloads[1].download_button(
        "Pobierz AER CSV",
        data=table.to_csv(index=False).encode("utf-8-sig"),
        file_name="stk_aer_matches.csv",
        mime="text/csv",
        width="stretch",
    )


def render_stk_validation_page() -> None:
    """Eksportuje przypadek i porównuje publiczny model z raportami STK."""

    st.header("Walidacja względem STK")
    st.info(
        "Moduł porównuje własne okna SGP4 z raportem STK dla tego samego "
        "satelity, AOI, czasu i trybu. STK pełni rolę środowiska referencyjnego, "
        "a nie źródła harmonogramu."
    )

    result = st.session_state.get(_ACCESS_RESULT_STATE_KEY)
    if result is None or not result.windows:
        st.warning(
            "Najpierw wyznacz okna w module „Okna dostępu”. Walidacja działa "
            "na ostatnim wyniku zapisanym w bieżącej sesji."
        )
        return
    request = _request_for_result(result)
    if request is None:
        st.error("Nie odnaleziono zlecenia odpowiadającego ostatnim oknom.")
        return
    snapshot = get_public_orbit_snapshot()
    if snapshot is None:
        st.warning("Najpierw wczytaj publiczne OMM w module „Orbity publiczne”.")
        return

    selections = sorted(
        {(window.satellite_id, window.mode_id) for window in result.windows}
    )
    selected = st.selectbox(
        "Przypadek satelita–tryb",
        options=selections,
        format_func=lambda value: _selection_label(value, result.windows),
    )
    satellite_id, mode_id = selected
    selected_windows = tuple(
        window
        for window in result.windows
        if window.satellite_id == satellite_id and window.mode_id == mode_id
    )
    satellite = next(
        item for item in snapshot.satellites if item.slot_id == satellite_id
    )
    mode = _mode_lookup()[mode_id]

    summary = st.columns(5)
    summary[0].metric("Zlecenie", request.request_id)
    summary[1].metric("Satelita", satellite_id)
    summary[2].metric("NORAD", satellite.record.norad_cat_id)
    summary[3].metric("Tryb", mode.name)
    summary[4].metric("Okna modelu", len(selected_windows))

    _render_export_section(
        request=request,
        result=result,
        selected_windows=selected_windows,
        satellite=satellite,
        mode=mode,
    )
    st.divider()
    _render_access_validation(selected_windows=selected_windows)
    st.divider()
    _render_aer_validation(
        selected_windows=selected_windows,
        request=request,
    )

    with st.expander("Założenia i ograniczenia walidacji"):
        st.markdown(
            """
- Publiczne OMM/TLE nie są precyzyjnymi efemerydami operatora.
- Granice okien modelu zależą od kroku dyskretnej propagacji.
- Parametry sensorów pochodzą z publicznych profili, nie z operacyjnego planu operatora.
- Dla Polygon pokrycie jest przybliżane nominalnym prostokątnym footprintem.
- Różnice względem STK należy interpretować jako ocenę modelu publicznego, nie błąd systemu operatora.
"""
        )
