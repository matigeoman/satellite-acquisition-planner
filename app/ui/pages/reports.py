from __future__ import annotations

import pandas as pd
import streamlit as st

from app.projects import PROJECT_METADATA_STATE_KEY
from app.projects.service import (
    ACCESS_RESULT_STATE_KEY,
    BENCHMARK_RESULT_STATE_KEY,
    CUSTOM_REQUESTS_STATE_KEY,
    OPPORTUNITY_BUILDS_STATE_KEY,
    ORBIT_SNAPSHOT_STATE_KEY,
    PLANNING_RESULT_STATE_KEY,
)
from app.reporting import ScientificReportConfig, ScientificReportPackage
from app.ui.app_context import get_scientific_report_service


_REPORT_STATE_KEY = "scientific_report_package"


def _component_rows() -> list[dict[str, str]]:
    checks = (
        ("Zlecenia", CUSTOM_REQUESTS_STATE_KEY),
        ("Dane orbitalne", ORBIT_SNAPSHOT_STATE_KEY),
        ("Okna dostępu", ACCESS_RESULT_STATE_KEY),
        ("Okazje", OPPORTUNITY_BUILDS_STATE_KEY),
        ("Harmonogram", PLANNING_RESULT_STATE_KEY),
        ("Benchmark", BENCHMARK_RESULT_STATE_KEY),
        ("Walidacja dostępu STK", "stk_access_validation_result"),
        ("Walidacja AER STK", "stk_aer_validation_result"),
    )
    return [
        {
            "Komponent": label,
            "Stan": "dostępny" if st.session_state.get(key) is not None else "brak",
        }
        for label, key in checks
    ]


def _render_input_state() -> None:
    rows = _component_rows()
    available = sum(row["Stan"] == "dostępny" for row in rows)
    columns = st.columns(4)
    columns[0].metric("Komponenty dostępne", available)
    columns[1].metric(
        "Zlecenia",
        len(st.session_state.get(CUSTOM_REQUESTS_STATE_KEY, ())),
    )
    builds = st.session_state.get(OPPORTUNITY_BUILDS_STATE_KEY, {})
    columns[2].metric(
        "Okazje",
        sum(len(build.opportunities) for build in builds.values()),
    )
    planning = st.session_state.get(PLANNING_RESULT_STATE_KEY)
    columns[3].metric(
        "Akwizycje w planie",
        len(getattr(getattr(planning, "schedule", None), "active_entries", ())),
    )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _render_build_form() -> None:
    metadata = st.session_state.get(PROJECT_METADATA_STATE_KEY)
    default_title = "Raport z planowania akwizycji satelitarnych"
    default_author = getattr(metadata, "author", "")
    default_description = getattr(metadata, "description", "")

    with st.form("scientific_report_form", border=True):
        st.markdown("### Konfiguracja raportu")
        title = st.text_input("Tytuł raportu", value=default_title, max_chars=250)
        first, second = st.columns(2)
        author = first.text_input("Autor", value=default_author, max_chars=200)
        institution = second.text_input(
            "Instytucja",
            value="Wojskowa Akademia Techniczna",
            max_chars=250,
        )
        description = st.text_area(
            "Opis celu eksperymentu",
            value=default_description,
            max_chars=4000,
        )
        options = st.columns(4)
        include_raw = options[0].checkbox("Pełne tabele CSV", value=True)
        include_methodology = options[1].checkbox("Metodyka", value=True)
        include_stk = options[2].checkbox("Walidacja STK", value=True)
        include_benchmarks = options[3].checkbox("Benchmarki", value=True)
        include_limitations = st.checkbox(
            "Założenia, ograniczenia i poprawna interpretacja wyników",
            value=True,
        )
        submitted = st.form_submit_button(
            "Zbuduj pakiet raportowy",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return
    config = ScientificReportConfig(
        title=title,
        author=author,
        institution=institution,
        description=description,
        include_raw_tables=include_raw,
        include_methodology=include_methodology,
        include_limitations=include_limitations,
        include_stk_validation=include_stk,
        include_benchmarks=include_benchmarks,
    )
    try:
        with st.spinner("Generowanie HTML, DOCX, XLSX, wykresów i tabel..."):
            result = get_scientific_report_service().build(
                st.session_state,
                config=config,
            )
    except Exception as error:
        st.session_state.pop(_REPORT_STATE_KEY, None)
        st.error("Nie udało się wygenerować raportu.")
        st.exception(error)
    else:
        st.session_state[_REPORT_STATE_KEY] = result
        st.success("Pakiet raportowy został wygenerowany.")


def _render_downloads() -> None:
    result = st.session_state.get(_REPORT_STATE_KEY)
    if not isinstance(result, ScientificReportPackage):
        return

    for warning in result.warnings:
        st.warning(warning)
    st.caption(
        f"Wygenerowano: {result.generated_at_utc.isoformat()} · "
        f"pliki: {len(result.included_files)} · "
        f"rozmiar ZIP: {result.size_bytes / 1024:.1f} KiB"
    )
    st.download_button(
        "Pobierz kompletny pakiet raportowy ZIP",
        data=result.archive_bytes,
        file_name=result.suggested_filename,
        mime="application/zip",
        type="primary",
        width="stretch",
    )
    columns = st.columns(4)
    columns[0].download_button(
        "Raport HTML",
        data=result.html_bytes,
        file_name="report.html",
        mime="text/html",
        width="stretch",
    )
    columns[1].download_button(
        "Raport Word",
        data=result.docx_bytes,
        file_name="report.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        width="stretch",
    )
    columns[2].download_button(
        "Wyniki Excel",
        data=result.xlsx_bytes,
        file_name="results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
    columns[3].download_button(
        "Dane źródłowe JSON",
        data=result.json_bytes,
        file_name="report.json",
        mime="application/json",
        width="stretch",
    )
    with st.expander("Zawartość pakietu"):
        st.code("\n".join(result.included_files), language="text")


def render_reports_page() -> None:
    """Generuje raport naukowy i komplet tabel z bieżącej sesji."""

    st.header("Raporty")
    st.info(
        "Moduł buduje spójny pakiet do pracy dyplomowej: samodzielny HTML, "
        "edytowalny DOCX, skoroszyt XLSX, tabele CSV, wykresy PNG oraz dane źródłowe JSON."
    )
    _render_input_state()
    _render_build_form()
    _render_downloads()
    st.caption(
        "Raport rozdziela wyniki modelu publicznego od ograniczeń operacyjnych "
        "i automatycznie dodaje zastrzeżenia dotyczące OMM/SGP4, pogody i taskingu."
    )


__all__ = ["render_reports_page"]
