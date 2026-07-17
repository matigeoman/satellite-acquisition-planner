from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from app.projects import (
    PROJECT_METADATA_STATE_KEY,
    SCHEDULE_HISTORY_STATE_KEY,
    ProjectArchivePreview,
    ProjectExportResult,
)
from app.projects.service import (
    ACCESS_RESULT_STATE_KEY,
    AOI_STATE_KEY,
    BENCHMARK_RESULT_STATE_KEY,
    CUSTOM_REQUESTS_STATE_KEY,
    OPPORTUNITY_BUILDS_STATE_KEY,
    ORBIT_SNAPSHOT_STATE_KEY,
    PLANNING_RESULT_STATE_KEY,
    REPLANNING_RESULT_STATE_KEY,
)
from app.ui.app_context import get_project_archive_service


_PREVIEW_STATE_KEY = "project_archive_preview"
_EXPORT_STATE_KEY = "project_export_result"


def _state_metrics() -> tuple[int, int, int, int, int, int]:
    requests = st.session_state.get(CUSTOM_REQUESTS_STATE_KEY, ())
    builds = st.session_state.get(OPPORTUNITY_BUILDS_STATE_KEY, {})
    access = st.session_state.get(ACCESS_RESULT_STATE_KEY)
    planning = st.session_state.get(PLANNING_RESULT_STATE_KEY)
    history = st.session_state.get(SCHEDULE_HISTORY_STATE_KEY, ())
    opportunities = sum(len(build.opportunities) for build in builds.values())
    return (
        len(requests),
        opportunities,
        len(getattr(access, "windows", ())),
        len(getattr(getattr(planning, "schedule", None), "active_entries", ())),
        len(history),
        int(st.session_state.get(ORBIT_SNAPSHOT_STATE_KEY) is not None),
    )


def _render_current_state() -> None:
    st.subheader("Bieżący stan projektu")
    requests, opportunities, windows, entries, versions, orbit_snapshot = (
        _state_metrics()
    )
    columns = st.columns(6)
    columns[0].metric("Zlecenia", requests)
    columns[1].metric("Okazje", opportunities)
    columns[2].metric("Okna dostępu", windows)
    columns[3].metric("Akwizycje w planie", entries)
    columns[4].metric("Wersje planu", versions)
    columns[5].metric("Snapshot orbit", "Tak" if orbit_snapshot else "Nie")

    component_rows = [
        {
            "Komponent": "AOI",
            "Stan": "zapisany" if AOI_STATE_KEY in st.session_state else "brak",
        },
        {
            "Komponent": "Orbity publiczne",
            "Stan": (
                "zapisane"
                if ORBIT_SNAPSHOT_STATE_KEY in st.session_state
                else "brak"
            ),
        },
        {
            "Komponent": "Planowanie publiczne",
            "Stan": (
                "zapisane"
                if PLANNING_RESULT_STATE_KEY in st.session_state
                else "brak"
            ),
        },
        {
            "Komponent": "Przeplanowanie",
            "Stan": (
                "zapisane"
                if REPLANNING_RESULT_STATE_KEY in st.session_state
                else "brak"
            ),
        },
        {
            "Komponent": "Benchmark",
            "Stan": (
                "zapisany"
                if BENCHMARK_RESULT_STATE_KEY in st.session_state
                else "brak"
            ),
        },
    ]
    st.dataframe(
        pd.DataFrame(component_rows),
        width="stretch",
        hide_index=True,
    )


def _render_export() -> None:
    service = get_project_archive_service()
    metadata = st.session_state.get(PROJECT_METADATA_STATE_KEY)
    default_name = getattr(metadata, "name", "Projekt SatPlan")
    default_description = getattr(metadata, "description", "")
    default_author = getattr(metadata, "author", "")

    with st.form("project_export_form", border=True):
        st.markdown("### Eksport projektu")
        first, second = st.columns(2)
        project_name = first.text_input(
            "Nazwa projektu",
            value=default_name,
            max_chars=150,
        )
        author = second.text_input(
            "Autor",
            value=default_author,
            max_chars=150,
        )
        description = st.text_area(
            "Opis projektu",
            value=default_description,
            max_chars=2000,
        )
        export_clicked = st.form_submit_button(
            "Zbuduj archiwum projektu",
            type="primary",
            width="stretch",
        )

    if export_clicked:
        try:
            export_result = service.export_project(
                st.session_state,
                project_name=project_name,
                description=description,
                author=author,
            )
        except Exception as error:
            st.session_state.pop(_EXPORT_STATE_KEY, None)
            st.error("Nie udało się zbudować archiwum projektu.")
            st.exception(error)
        else:
            st.session_state[_EXPORT_STATE_KEY] = export_result
            st.session_state[PROJECT_METADATA_STATE_KEY] = export_result.metadata
            st.success("Archiwum zostało zbudowane i zweryfikowane lokalnie.")

    result = st.session_state.get(_EXPORT_STATE_KEY)
    if not isinstance(result, ProjectExportResult):
        return

    for warning in result.warnings:
        st.warning(warning)
    st.caption(
        f"Pliki: {len(result.included_files)} · "
        f"rozmiar ZIP: {len(result.archive_bytes) / 1024:.1f} KiB · "
        f"schemat: {result.metadata.schema_version}"
    )
    st.download_button(
        "Pobierz pełny projekt SatPlan",
        data=result.archive_bytes,
        file_name=service.suggested_filename(result.metadata.name),
        mime="application/zip",
        type="primary",
        width="stretch",
    )
    with st.expander("Zawartość archiwum"):
        st.code("\n".join(result.included_files), language="text")


def _preview_dataframe(preview: ProjectArchivePreview) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Parametr": "Nazwa", "Wartość": preview.metadata.name},
            {"Parametr": "ID", "Wartość": preview.metadata.project_id},
            {
                "Parametr": "Utworzono UTC",
                "Wartość": preview.metadata.created_at_utc.isoformat(),
            },
            {
                "Parametr": "Wyeksportowano UTC",
                "Wartość": preview.metadata.exported_at_utc.isoformat(),
            },
            {
                "Parametr": "Wersja aplikacji",
                "Wartość": preview.metadata.application_version,
            },
            {
                "Parametr": "Wersja schematu",
                "Wartość": preview.metadata.schema_version,
            },
            {"Parametr": "Pliki", "Wartość": preview.file_count},
            {
                "Parametr": "Rozmiar po rozpakowaniu",
                "Wartość": f"{preview.uncompressed_size_bytes / 1024:.1f} KiB",
            },
        ]
    )


def _render_import() -> None:
    service = get_project_archive_service()
    st.markdown("### Import projektu")
    st.caption(
        "Najpierw wykonywana jest walidacja ZIP, manifestu SHA-256, schematu "
        "oraz relacji między zleceniami, okazjami i harmonogramem. Bieżąca "
        "sesja nie jest zmieniana, dopóki nie zatwierdzisz importu."
    )
    uploaded = st.file_uploader(
        "Wczytaj archiwum .zip",
        type=["zip"],
        key="project_archive_upload",
    )
    if st.button(
        "Sprawdź archiwum",
        disabled=uploaded is None,
        width="stretch",
    ):
        try:
            preview = service.preview_archive(uploaded.getvalue())
        except Exception as error:
            st.session_state.pop(_PREVIEW_STATE_KEY, None)
            st.error("Archiwum nie przeszło walidacji.")
            st.exception(error)
        else:
            st.session_state[_PREVIEW_STATE_KEY] = preview
            st.success("Archiwum jest spójne i może zostać przywrócone.")

    preview = st.session_state.get(_PREVIEW_STATE_KEY)
    if not isinstance(preview, ProjectArchivePreview):
        return

    st.dataframe(
        _preview_dataframe(preview),
        width="stretch",
        hide_index=True,
    )
    metrics = st.columns(4)
    metrics[0].metric("Zlecenia", preview.request_count)
    metrics[1].metric("Okazje", preview.opportunity_count)
    metrics[2].metric("Wersje planu", preview.schedule_count)
    metrics[3].metric("Komponenty", len(preview.present_components))
    st.write("**Wykryte komponenty:** " + ", ".join(preview.present_components))
    for warning in preview.warnings:
        st.warning(warning)

    confirm = st.checkbox(
        "Rozumiem, że bieżący projekt sesji zostanie zastąpiony",
        key="confirm_project_restore",
    )
    if st.button(
        "Wczytaj projekt i przywróć sesję",
        type="primary",
        disabled=not confirm,
        width="stretch",
    ):
        service.apply_preview(st.session_state, preview)
        st.session_state.pop(_PREVIEW_STATE_KEY, None)
        st.session_state.pop(_EXPORT_STATE_KEY, None)
        st.success("Projekt został przywrócony.")
        st.rerun()


def _render_history() -> None:
    history = st.session_state.get(SCHEDULE_HISTORY_STATE_KEY, ())
    if not history:
        st.info("Historia harmonogramów pojawi się po uruchomieniu planowania.")
        return
    rows = [
        {
            "Wersja": index,
            "Typ": item.get("event_type", ""),
            "Harmonogram": item.get("schedule", {}).get("schedule_id", ""),
            "Algorytm": item.get("algorithm", ""),
            "Status solvera": item.get("solver_status", ""),
            "Cel": item.get("objective_value", 0.0),
            "Zrealizowane zlecenia": item.get(
                "fully_satisfied_requests", 0
            ),
            "Akwizycje": item.get("total_acquisitions", 0),
            "Dodane": len(item.get("added_opportunity_ids", ())),
            "Usunięte": len(item.get("removed_opportunity_ids", ())),
            "Zapisano UTC": item.get("recorded_at_utc", ""),
        }
        for index, item in enumerate(history, start=1)
    ]
    st.dataframe(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
        height=360,
    )


def _render_clear_project() -> None:
    service = get_project_archive_service()
    with st.expander("Wyczyść bieżący projekt", expanded=False):
        st.warning(
            "Usunięte zostaną AOI, zlecenia, snapshot orbit, okna, okazje, "
            "harmonogram, przeplanowanie, benchmark i historia wersji."
        )
        confirmation = st.text_input(
            "Wpisz USUŃ PROJEKT",
            key="clear_project_confirmation",
        )
        if st.button(
            "Wyczyść dane projektu",
            disabled=confirmation.strip().upper() != "USUŃ PROJEKT",
        ):
            service.clear_project(st.session_state)
            st.session_state.pop(_PREVIEW_STATE_KEY, None)
            st.session_state.pop(_EXPORT_STATE_KEY, None)
            st.success("Stan projektu został wyczyszczony.")
            st.rerun()


def render_projects_page() -> None:
    """Zarządza pełnym eksportem i odtworzeniem projektu SatPlan."""

    st.header("Projekty i scenariusze")
    st.info(
        "Zapisuje bieżący pipeline od AOI i zleceń przez snapshot OMM, "
        "okna dostępu, pogodę i okazje aż do harmonogramu, historii "
        "przeplanowania oraz benchmarku."
    )
    _render_current_state()
    export_tab, import_tab, history_tab = st.tabs(
        ["Eksport", "Import", "Historia harmonogramów"]
    )
    with export_tab:
        _render_export()
    with import_tab:
        _render_import()
    with history_tab:
        _render_history()
    st.divider()
    _render_clear_project()
    st.caption(
        "Snapshot projektu jest deterministycznym zapisem danych wejściowych "
        "użytych w obliczeniach; bieżące źródła publiczne mogą później ulec zmianie."
    )


__all__ = ["render_projects_page"]
