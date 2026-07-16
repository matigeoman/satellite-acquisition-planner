"""Komponenty wielokrotnego użytku dla aplikacji Streamlit."""


def render_aoi_editor(*args, **kwargs):
    """Ładuje komponent mapowy dopiero w działającej aplikacji Streamlit."""

    from app.ui.components.aoi_editor import render_aoi_editor as renderer

    return renderer(*args, **kwargs)


__all__ = ["render_aoi_editor"]
