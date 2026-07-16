from __future__ import annotations

from enum import StrEnum

import streamlit as st


class ApplicationPage(StrEnum):
    """Dostępne moduły aplikacji operacyjnej."""

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
