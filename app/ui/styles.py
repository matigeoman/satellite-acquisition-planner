from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import streamlit as st


_STYLESHEET_PATH = (
    Path(__file__).resolve().parent
    / "assets"
    / "application.css"
)


@lru_cache(maxsize=1)
def load_application_stylesheet() -> str:
    """Wczytuje arkusz stylów aplikacji tylko raz na proces."""

    return _STYLESHEET_PATH.read_text(encoding="utf-8")


def apply_application_styles() -> None:
    """Osadza wspólny arkusz CSS w aplikacji Streamlit."""

    stylesheet = load_application_stylesheet()
    st.markdown(
        f"<style>{stylesheet}</style>",
        unsafe_allow_html=True,
    )
