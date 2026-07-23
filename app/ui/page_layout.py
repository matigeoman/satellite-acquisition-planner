from __future__ import annotations

from html import escape
from textwrap import dedent
from typing import Iterable

import streamlit as st


def render_page_header(
    title: str,
    description: str,
    *,
    eyebrow: str = "Satellite Acquisition Planner",
    badges: Iterable[str] = (),
) -> None:
    """Renderuje wspólny nagłówek strony bez mieszania logiki domenowej z UI."""

    badge_html = "".join(
        f'<span class="satplan-page-badge">{escape(str(badge))}</span>'
        for badge in badges
    )
    badge_row = (
        f'<div class="satplan-page-badges">{badge_html}</div>'
        if badge_html
        else ""
    )
    st.markdown(
        dedent(
            f"""
            <section class="satplan-page-header" aria-label="Nagłówek modułu">
                <div class="satplan-page-eyebrow">{escape(eyebrow)}</div>
                <h1>{escape(title)}</h1>
                <p>{escape(description)}</p>
                {badge_row}
            </section>
            """
        ),
        unsafe_allow_html=True,
    )


def render_sidebar_heading(title: str, description: str | None = None) -> None:
    """Renderuje zwarty nagłówek grupy kontrolek w panelu bocznym."""

    description_html = (
        f"<p>{escape(description)}</p>"
        if description
        else ""
    )
    st.markdown(
        dedent(
            f"""
            <div class="satplan-sidebar-heading">
                <span>Parametry modułu</span>
                <strong>{escape(title)}</strong>
                {description_html}
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def render_section_header(title: str, description: str | None = None) -> None:
    """Renderuje spójny nagłówek sekcji wewnątrz strony."""

    description_html = (
        f"<p>{escape(description)}</p>"
        if description
        else ""
    )
    st.markdown(
        dedent(
            f"""
            <div class="satplan-section-header">
                <h2>{escape(title)}</h2>
                {description_html}
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


__all__ = [
    "render_page_header",
    "render_section_header",
    "render_sidebar_heading",
]
