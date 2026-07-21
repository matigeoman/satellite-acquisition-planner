from __future__ import annotations

from enum import StrEnum

import streamlit as st

from app.version import __version__


class ApplicationPage(StrEnum):
    """Ekrany dostępne w aplikacji."""

    DEMO = "Start i demo"
    TARGETS = "Cele i zlecenia"
    ORBITS = "Orbity i dane OMM"
    ACCESS = "Okna dostępu i pogoda"
    GLOBE = "Globus operacyjny"
    LIVE_TRACKING = "Śledzenie i przeloty"
    PUBLIC_PLANNING = "Planowanie na danych publicznych"
    PUBLIC_REPLANNING = "Przeplanowanie na danych publicznych"
    STK_VALIDATION = "Walidacja względem STK"
    BENCHMARKS = "Benchmarki"
    PROJECTS = "Projekty"
    REPORTS = "Raporty"
    PLANNING = "Planowanie scenariuszy referencyjnych"
    REPLANNING = "Przeplanowanie scenariuszy referencyjnych"
    DISRUPTIONS = "Analiza zakłóceń"
    EXPERIMENTS = "Eksperymenty porównawcze"


class NavigationSection(StrEnum):
    """Grupy porządkujące moduły w panelu bocznym."""

    OPERATIONS = "Przepływ operacyjny"
    ANALYSIS = "Analiza i walidacja"
    PROJECT = "Projekt i wyniki"


PAGE_GROUPS: dict[NavigationSection, tuple[ApplicationPage, ...]] = {
    NavigationSection.OPERATIONS: (
        ApplicationPage.DEMO,
        ApplicationPage.TARGETS,
        ApplicationPage.ORBITS,
        ApplicationPage.ACCESS,
        ApplicationPage.GLOBE,
        ApplicationPage.LIVE_TRACKING,
        ApplicationPage.PUBLIC_PLANNING,
        ApplicationPage.PUBLIC_REPLANNING,
    ),
    NavigationSection.ANALYSIS: (
        ApplicationPage.STK_VALIDATION,
        ApplicationPage.BENCHMARKS,
        ApplicationPage.PLANNING,
        ApplicationPage.REPLANNING,
        ApplicationPage.DISRUPTIONS,
        ApplicationPage.EXPERIMENTS,
    ),
    NavigationSection.PROJECT: (
        ApplicationPage.PROJECTS,
        ApplicationPage.REPORTS,
    ),
}


PAGE_DESCRIPTIONS: dict[ApplicationPage, str] = {
    ApplicationPage.DEMO: (
        "Gotowy scenariusz Polski i szybki punkt wejścia do całego przepływu."
    ),
    ApplicationPage.TARGETS: "Definicja AOI, parametrów i priorytetów zleceń.",
    ApplicationPage.ORBITS: "Publiczne OMM/GP, przypisanie satelitów i propagacja SGP4.",
    ApplicationPage.ACCESS: "Geometria dostępu, profile sensorów i zachmurzenie EO.",
    ApplicationPage.GLOBE: "Interaktywny globus z orbitami, AOI, oknami i planem.",
    ApplicationPage.LIVE_TRACKING: (
        "Mapa nieba, ślad naziemny i predykcja AOS/MAX/LOS."
    ),
    ApplicationPage.PUBLIC_PLANNING: (
        "Budowa harmonogramu Greedy lub CP-SAT z danych publicznych."
    ),
    ApplicationPage.PUBLIC_REPLANNING: (
        "Aktualizacja harmonogramu przy zachowaniu okna zamrożonego."
    ),
    ApplicationPage.STK_VALIDATION: "Porównanie wyników publicznych z eksportem STK.",
    ApplicationPage.BENCHMARKS: "Skalowalność, jakość i czasy Greedy oraz CP-SAT.",
    ApplicationPage.PROJECTS: "Zapis, import i wersjonowanie pełnego stanu pracy.",
    ApplicationPage.REPORTS: "Eksport wyników do HTML, DOCX, XLSX i JSON.",
    ApplicationPage.PLANNING: "Planowanie na kontrolowanych scenariuszach referencyjnych.",
    ApplicationPage.REPLANNING: "Regresyjne testy przeplanowania scenariuszy.",
    ApplicationPage.DISRUPTIONS: "Wpływ awarii, pogody i blokad zasobów.",
    ApplicationPage.EXPERIMENTS: "Powtarzalne porównania algorytmów i profili.",
}


_SECTION_HINTS: dict[NavigationSection, str] = {
    NavigationSection.OPERATIONS: (
        "Od utworzenia celu do planowania i obserwacji konstelacji."
    ),
    NavigationSection.ANALYSIS: (
        "Walidacja, testy porównawcze i zachowanie systemu pod zakłóceniami."
    ),
    NavigationSection.PROJECT: (
        "Archiwizacja projektu i przygotowanie materiałów wynikowych."
    ),
}


def _render_brand() -> None:
    st.markdown(
        f"""
        <div class="satplan-brand">
            <div class="satplan-brand-mark">SAP</div>
            <div class="satplan-brand-copy">
                <strong>Satellite Acquisition Planner</strong>
                <span>wersja {__version__}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_navigation() -> ApplicationPage:
    """Renderuje pogrupowaną nawigację w panelu bocznym."""

    with st.sidebar:
        _render_brand()
        st.markdown('<div class="satplan-sidebar-label">Nawigacja</div>', unsafe_allow_html=True)
        section = st.radio(
            "Obszar",
            options=list(NavigationSection),
            format_func=lambda value: value.value,
            key="satplan_navigation_section",
        )
        st.caption(_SECTION_HINTS[section])
        st.divider()
        selected = st.radio(
            "Widok",
            options=PAGE_GROUPS[section],
            format_func=lambda value: value.value,
            label_visibility="collapsed",
            key=f"satplan_navigation_page_{section.name.lower()}",
        )
        st.markdown(
            f"""
            <div class="satplan-sidebar-context">
                <span>Aktywny moduł</span>
                <strong>{selected.value}</strong>
                <p>{PAGE_DESCRIPTIONS[selected]}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Planowanie SAR i EO · OMM/SGP4 · Greedy/CP-SAT")

    return selected


__all__ = [
    "ApplicationPage",
    "NavigationSection",
    "PAGE_DESCRIPTIONS",
    "PAGE_GROUPS",
    "render_navigation",
]
