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


def render_navigation() -> ApplicationPage:
    """Renderuje pogrupowaną nawigację w panelu bocznym."""

    with st.sidebar:
        st.subheader("Nawigacja")
        section = st.radio(
            "Obszar",
            options=list(NavigationSection),
            format_func=lambda value: value.value,
            key="satplan_navigation_section",
        )
        selected = st.radio(
            "Widok",
            options=PAGE_GROUPS[section],
            format_func=lambda value: value.value,
            label_visibility="collapsed",
            key=f"satplan_navigation_page_{section.name.lower()}",
        )
        st.divider()
        st.caption(f"Satellite Acquisition Planner · {__version__}")

    return selected


__all__ = [
    "ApplicationPage",
    "NavigationSection",
    "PAGE_GROUPS",
    "render_navigation",
]
