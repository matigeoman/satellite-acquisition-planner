from __future__ import annotations

from enum import StrEnum

import streamlit as st


class ApplicationPage(StrEnum):
    """Dostępne moduły aplikacji operacyjnej."""

    TARGETS = "Cele i zlecenia"
    ORBITS = "Orbity publiczne"
    ACCESS = "Okna dostępu"
    GLOBE = "Globus i orbity"
    PUBLIC_PLANNING = "Planowanie publiczne"
    PUBLIC_REPLANNING = "Przeplanowanie publiczne"
    STK_VALIDATION = "Walidacja STK"
    BENCHMARKS = "Benchmarki algorytmów"
    PLANNING = "Planowanie"
    REPLANNING = "Dynamiczne przeplanowanie"
    DISRUPTIONS = "Zakłócenia"
    EXPERIMENTS = "Eksperymenty"


def render_navigation() -> ApplicationPage:
    """Renderuje wspólną nawigację w panelu bocznym."""

    with st.sidebar:
        st.subheader("Moduł aplikacji")
        selected = st.radio(
            "Nawigacja",
            options=list(ApplicationPage),
            format_func=lambda page: page.value,
            label_visibility="collapsed",
        )
        st.divider()

    return selected
